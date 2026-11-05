import fs from 'node:fs'
import path from 'node:path'
import { NextResponse } from 'next/server'
import { loadCaseCatalog } from '@/lib/server/case-catalog'
import { getDeepSeekClient, getDeepSeekSettings, hasDeepSeekKey } from '@/lib/server/deepseek-client'
import { selectCaseSearchMatches } from '@/lib/case-search'
import { natureLabels, observationLabels, type CatalogSummary } from '@/lib/case-datasets'

export const dynamic = 'force-dynamic'
export const maxDuration = 120

export async function POST(request: Request) {
  let body: unknown
  try { body = await request.json() } catch { return NextResponse.json({ error: '搜索内容格式无效。' }, { status: 400 }) }
  const question = body && typeof body === 'object' && 'question' in body ? body.question : null
  if (typeof question !== 'string' || !question.trim() || question.length > 2000) {
    return NextResponse.json({ error: '请输入搜索需求，最长2000字。' }, { status: 400 })
  }
  if (!hasDeepSeekKey()) return NextResponse.json({ error: 'AI 搜索暂未配置，仍可使用普通搜索。' }, { status: 503 })
  try {
    const { records, groups } = loadCaseCatalog()
    if (!records.length) return NextResponse.json({ question: question.trim(), results: [] })
    const member = (item: CatalogSummary) => ({ name: item.name, scale: item.scale,
      nature: natureLabels[item.nature.kind], observation: observationLabels[item.nature.observation],
      quantity: item.nature.quantity, unit: item.nature.unit, note: item.nature.note,
      can_calculate: item.can_calculate, role: item.role })
    const catalog = records.map(entry => ({ id: entry.id, name: entry.name,
      nature: natureLabels[entry.nature.kind], tags: entry.nature.tags, scale: entry.scale,
      description: entry.is_group ? entry.description : entry.nature.note,
      sources: Array.from(new Set(entry.sources.map(source => source.paper_id))),
      members: entry.is_group ? groups.get(entry.id)!.members.map(member) : [member(entry)] }))
    const response = await getDeepSeekClient().chat.completions.create({
      model: getDeepSeekSettings().model,
      messages: [
        { role: 'system', content: fs.readFileSync(path.join(process.cwd(), 'src/content/prompts/case_search.md'), 'utf8') },
        { role: 'user', content: JSON.stringify({ question: question.trim(), catalog }) },
      ],
      response_format: { type: 'json_object' }, max_tokens: 2048, temperature: 0, stream: false,
      ...{ thinking: { type: 'disabled' } },
    }, { signal: request.signal })
    const selection = JSON.parse(response.choices[0]?.message?.content || '{}')
    return NextResponse.json({ question: question.trim(), results: selectCaseSearchMatches(records, selection.matches) },
      { headers: { 'Cache-Control': 'no-store' } })
  } catch (error) {
    const value = error as { status?: number; name?: string }
    if (request.signal.aborted) return new NextResponse(null, { status: 499 })
    console.warn('[case-search]', { status: value.status, name: value.name })
    return NextResponse.json({ error: value.status === 402 ? 'AI 搜索额度不足，仍可使用普通搜索。'
      : value.status === 429 ? 'AI 搜索繁忙，请稍后重试。'
      : value.name === 'APIConnectionTimeoutError' ? 'AI 搜索响应超时，请重试。'
      : 'AI 搜索暂时不可用，请重试或使用普通搜索。' }, { status: 502 })
  }
}
