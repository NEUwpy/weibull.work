import { NextRequest, NextResponse } from 'next/server'
import fs from 'node:fs'
import path from 'node:path'
import config from './config.json'
import { getDeepSeekClient, getDeepSeekSettings, hasDeepSeekKey } from '@/lib/server/deepseek-client'
import { searchLibrary, enrichLibrarySearchHits } from '@/lib/server/library-search'
import { buildSearchQueries, evidenceContext, selectLibraryEvidence, orderEvidenceCandidates, poolLibraryCandidates } from '@/lib/library-rag'

export const dynamic = 'force-dynamic'
export const maxDuration = 180

function prompt(name: string): string {
  return fs.readFileSync(path.join(process.cwd(), 'src/content/prompts', name), 'utf8')
}

export async function POST(request: NextRequest) {
  if (!hasDeepSeekKey()) return NextResponse.json({ error: '文献问答暂未配置，请联系管理员。' }, { status: 503 })
  let body: unknown
  try { body = await request.json() } catch { return NextResponse.json({ error: '问题格式无效。' }, { status: 400 }) }
  const question = body && typeof body === 'object' && 'question' in body ? body.question : null
  if (typeof question !== 'string' || !question.trim() || question.length > 2000) {
    return NextResponse.json({ error: '请输入问题，最长2000字。' }, { status: 400 })
  }

  const controller = new AbortController()
  const abort = () => controller.abort()
  request.signal?.addEventListener('abort', abort, { once: true })
  if (request.signal?.aborted) abort()
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    async start(output) {
      let closed = false
      const send = (value: Record<string, unknown>) => {
        if (!closed && !controller.signal.aborted) output.enqueue(encoder.encode(`data: ${JSON.stringify(value)}\n\n`))
      }
      try {
        const client = getDeepSeekClient()
        const { model } = getDeepSeekSettings()
        send({ stage: 'expanding', message: '正在分析问题，准备检索表达…' })
        let variants: unknown = []
        try {
          const expansion = await client.chat.completions.create({
            model,
            messages: [{ role: 'system', content: prompt('rag_search_queries.md') }, { role: 'user', content: question.trim() }],
            response_format: { type: 'json_object' },
            max_tokens: 768,
            temperature: 0.2,
            stream: false,
            ...{ thinking: { type: 'disabled' } },
          }, { signal: controller.signal })
          variants = JSON.parse(expansion.choices[0]?.message?.content || '{}').queries
        } catch {
          if (controller.signal.aborted) return
          // Direct corpus retrieval remains usable when query expansion is unavailable.
        }
        const queries = buildSearchQueries(question, variants, config.retrieval.maxQueries)
        send({ stage: 'searching', message: '正在查找相关正文并筛选参考段落…' })
        const rankings = queries.map(query => searchLibrary(query, { limit: config.retrieval.candidatesPerQuery }).results)
        const candidateLimits = { maxPassages: config.retrieval.maxRerankCandidates, maxPerPaper: 5, maxContextChars: config.retrieval.maxRerankChars }
        const pooled = poolLibraryCandidates(rankings, candidateLimits)
        const candidates = selectLibraryEvidence([enrichLibrarySearchHits(pooled)], candidateLimits)
        let ranked = candidates
        if (candidates.length) {
          send({ stage: 'screening', message: '正在核对候选段落是否能支持这个问题…' })
          const screening = await client.chat.completions.create({
            model,
            messages: [
              { role: 'system', content: prompt('rag_screen_evidence.md') },
              { role: 'user', content: `问题：${question.trim()}\n\n候选段落：\n${JSON.stringify(candidates.map(({ id, slug, title, version, section, text }) => ({ id, slug, title, version, section, text })))}` },
            ],
            response_format: { type: 'json_object' },
            max_tokens: 1024,
            temperature: 0,
            stream: false,
            ...{ thinking: { type: 'disabled' } },
          }, { signal: controller.signal })
          const ids = JSON.parse(screening.choices[0]?.message?.content || '{}').ranked_ids
          ranked = orderEvidenceCandidates(candidates, ids)
        }
        const evidence = selectLibraryEvidence([ranked], config.retrieval)
        send({ evidence, queries })
        send({ stage: 'answering', message: evidence.length
          ? `已选取 ${evidence.length} 段资料，正在生成带出处的回答…`
          : '本次未找到可用的库内依据，正在整理一般性说明…' })
        const response = await client.chat.completions.create({
          model,
          messages: [
            { role: 'system', content: prompt('rag_evidence_answer.md') },
            { role: 'user', content: `问题：${question.trim()}\n\n参考资料：\n${JSON.stringify(evidenceContext(evidence))}` },
          ],
          max_tokens: 4096,
          temperature: 0.3,
          stream: true,
          ...{ thinking: { type: 'disabled' } },
        }, { signal: controller.signal })
        let received = false
        for await (const chunk of response) {
          const text = chunk.choices[0]?.delta?.content
          if (text) { received = true; send({ content: text }) }
          if (chunk.choices[0]?.finish_reason === 'length') send({ content: '\n\n（回答达到长度上限，可缩小问题后继续询问。）' })
        }
        if (!received) send({ error: '模型没有返回正文，请重试。' })
        send({ done: true })
      } catch (error) {
        const status = error && typeof error === 'object' && 'status' in error ? error.status : undefined
        send({ error: status === 401 ? '问答接口认证失败，请检查本机配置。'
          : status === 402 ? '问答接口额度不足。'
          : status === 429 ? '问答接口繁忙，请稍后重试。' : '文献问答暂时不可用，请稍后重试。' })
      } finally {
        request.signal?.removeEventListener('abort', abort)
        closed = true
        try { output.close() } catch { /* Client already cancelled the stream. */ }
      }
    },
    cancel() { abort() },
  })
  return new NextResponse(stream, { headers: {
    'Content-Type': 'text/event-stream; charset=utf-8',
    'Cache-Control': 'no-cache, no-transform',
    'X-Accel-Buffering': 'no',
  } })
}

export async function GET() {
  const { model, label } = getDeepSeekSettings()
  return NextResponse.json({ provider: 'deepseek', model, label, configured: hasDeepSeekKey() })
}
