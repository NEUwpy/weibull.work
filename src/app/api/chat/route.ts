import { NextRequest, NextResponse } from 'next/server'
import fs from 'node:fs'
import path from 'node:path'
import config from './config.json'
import { getDeepSeekClient, getDeepSeekSettings, hasDeepSeekKey } from '@/lib/server/deepseek-client'
import { createLibraryChatLog } from '@/lib/server/library-chat-log'
import { searchLibrary, enrichLibrarySearchHits, startLibrarySearchPrewarm } from '@/lib/server/library-search'
import { buildSearchQueries, evidenceContext, selectLibraryEvidence, orderEvidenceCandidates, poolLibraryCandidates } from '@/lib/library-rag'
import { requireLibraryLogin } from '@/lib/server/library-auth'
import { answerArticleQuestion, parseArticleQuestion, readArticleQuestion } from '@/lib/server/library-article-chat'

export const dynamic = 'force-dynamic'
export const maxDuration = 180

function prompt(name: string): string {
  return fs.readFileSync(path.join(process.cwd(), 'src/content/prompts', name), 'utf8')
}

function failureInfo(error: unknown) {
  const value = error && typeof error === 'object' ? error as { name?: unknown; status?: unknown; code?: unknown } : {}
  return {
    name: typeof value.name === 'string' ? value.name.slice(0, 64) : 'UnknownError',
    status: typeof value.status === 'number' ? value.status : undefined,
    code: typeof value.code === 'string' && /^[a-z0-9_]{1,64}$/i.test(value.code) ? value.code : undefined,
  }
}

export async function POST(request: NextRequest) {
  if (!hasDeepSeekKey()) return NextResponse.json({ error: '文献问答暂未配置，请联系管理员。' }, { status: 503 })
  let body: unknown
  try { body = await request.json() } catch { return NextResponse.json({ error: '问题格式无效。' }, { status: 400 }) }
  const question = body && typeof body === 'object' && 'question' in body ? body.question : null
  if (typeof question !== 'string' || !question.trim() || question.length > 2000) {
    return NextResponse.json({ error: '请输入问题，最长2000字。' }, { status: 400 })
  }
  let article: ReturnType<typeof readArticleQuestion> = null
  if (body && typeof body === 'object' && 'article' in body) {
    const denied = requireLibraryLogin(request)
    if (denied) return denied
    const scope = parseArticleQuestion(body.article)
    if (!scope) return NextResponse.json({ error: '文献范围或引用内容无效。' }, { status: 400 })
    try {
      article = readArticleQuestion(scope)
    } catch (error) {
      console.error('[library-chat]', { stage: 'article', ...failureInfo(error) })
      return NextResponse.json({ error: '文献暂时无法读取，请稍后重试。' }, { status: 503 })
    }
    if (!article) return NextResponse.json({ error: '本篇暂无可读取的正文。' }, { status: 404 })
  }

  const controller = new AbortController()
  const abort = () => controller.abort()
  request.signal?.addEventListener('abort', abort, { once: true })
  if (request.signal?.aborted) abort()
  const encoder = new TextEncoder()
  const log = createLibraryChatLog()
  log.record('start', { model: getDeepSeekSettings().model,
    ...(article ? { slug: article.scope.slug, version: article.scope.version } : { question: question.trim() }) })
  const stream = new ReadableStream({
    async start(output) {
      let closed = false
      let stage = 'expanding'
      let answerChars = 0
      let outcome = 'interrupted'
      const send = (value: Record<string, unknown>) => {
        if (value.stage) log.record('stage', { stage: value.stage })
        if (!closed && !controller.signal.aborted) output.enqueue(encoder.encode(`data: ${JSON.stringify(value)}\n\n`))
      }
      try {
        const client = getDeepSeekClient()
        const { model, baseURL } = getDeepSeekSettings()
        if (article) {
          stage = 'article'
          const received = await answerArticleQuestion({ article, question: question.trim(), client, model, baseURL,
            instructions: prompt('rag_evidence_answer.md'), signal: controller.signal,
            send: event => { if (event.content) answerChars += event.content.length; send({ ...event }) },
          })
          if (!received) send({ error: '模型没有返回正文，请重试。' })
          outcome = received ? 'completed' : 'empty'
          send({ done: true })
          return
        }
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
        } catch (error) {
          if (controller.signal.aborted) return
          console.warn('[library-chat]', { stage, ...failureInfo(error) })
          log.record('warning', { stage, ...failureInfo(error) })
          // Direct corpus retrieval remains usable when query expansion is unavailable.
        }
        const queries = buildSearchQueries(question, variants, config.retrieval.maxQueries)
        stage = 'searching'
        send({ stage: 'searching', message: '正在查找相关正文并筛选参考段落…' })
        await startLibrarySearchPrewarm()
        if (controller.signal.aborted) return
        const rankings = queries.map(query => searchLibrary(query, { limit: config.retrieval.candidatesPerQuery }).results)
        const candidateLimits = { maxPassages: config.retrieval.maxRerankCandidates, maxPerPaper: 5, maxContextChars: config.retrieval.maxRerankChars }
        const pooled = poolLibraryCandidates(rankings, candidateLimits)
        const candidates = selectLibraryEvidence([enrichLibrarySearchHits(pooled)], candidateLimits)
        let ranked = candidates
        if (candidates.length) {
          stage = 'screening'
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
        log.record('retrieval', { queries, candidates: candidates.length,
          sources: evidence.map(({ id, slug, version, startLine, endLine, citation }) => ({ id, slug, version, startLine, endLine, citation })) })
        // The model receives the full selected context below; browsers receive previews only.
        send({ evidence: evidence.map(({ context, contextStartLine, contextEndLine, ...hit }) => ({ ...hit, text: hit.excerpt })), queries })
        stage = 'answering'
        send({ stage: 'answering', message: evidence.length
          ? `已选取 ${evidence.length} 段资料，正在生成带出处的回答…`
          : '本次未找到可用的库内依据，正在整理一般性说明…' })
        const response = await client.chat.completions.create({
          model,
          messages: [
            { role: 'system', content: prompt('rag_evidence_answer.md') + '\n\n用中文回答。' },
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
          if (text) { received = true; answerChars += text.length; send({ content: text }) }
          if (chunk.choices[0]?.finish_reason === 'length') send({ content: '\n\n（回答达到长度上限，可缩小问题后继续询问。）' })
        }
        if (!received) send({ error: '模型没有返回正文，请重试。' })
        outcome = received ? 'completed' : 'empty'
        send({ done: true })
      } catch (error) {
        if (controller.signal.aborted) return
        // Log only classifications; provider messages, requests and credentials stay out of logs.
        const { status, name, code } = failureInfo(error)
        console.error('[library-chat]', { stage, status, name, code })
        outcome = 'failed'
        log.record('error', { stage, status, name, code })
        send({ error: status === 401 ? '问答接口认证失败，请检查本机配置。'
          : status === 402 ? '问答接口额度不足。'
          : status === 429 ? '问答接口繁忙，请稍后重试。'
          : name === 'APIConnectionTimeoutError' ? '问答接口响应超时，请重试。'
          : name === 'APIConnectionError' ? '暂时无法连接问答接口，请重试。'
          : stage === 'screening' && (name === 'SyntaxError' || name === 'Error' && !status) ? '参考资料筛选未完成，请重新点击 AI 问答。'
          : stage === 'searching' ? '文献检索失败，请稍后重试。'
          : '文献问答暂时不可用，请稍后重试。' })
      } finally {
        request.signal?.removeEventListener('abort', abort)
        closed = true
        try { output.close() } catch { /* Client already cancelled the stream. */ }
        log.record('finish', { outcome: controller.signal.aborted ? 'cancelled' : outcome, stage, answerChars })
        await log.flush()
      }
    },
    cancel() { abort() },
  })
  return new NextResponse(stream, { headers: {
    'Content-Type': 'text/event-stream; charset=utf-8',
    'Cache-Control': article ? 'private, no-store, no-transform' : 'no-cache, no-transform',
    'X-Accel-Buffering': 'no',
  } })
}

export async function GET() {
  const { model, label } = getDeepSeekSettings()
  return NextResponse.json({ provider: 'deepseek', model, label, configured: hasDeepSeekKey() })
}
