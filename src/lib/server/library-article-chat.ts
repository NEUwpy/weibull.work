import type OpenAI from 'openai'
import { readPaper, readPaperMetadata } from './literature'
import { enrichLibrarySearchHits, libraryAnchoredPassages, librarySectionPassages, searchLibrary, startLibrarySearchPrewarm } from './library-search'
import { processLibraryContent } from '../library-markdown'
import { buildSearchQueries, evidenceContext, selectLibraryEvidence } from '../library-rag'
import { MAX_ARTICLE_CHAT_HISTORY, MAX_ARTICLE_QUOTES, MAX_ARTICLE_QUOTE_CHARS, type LibraryArticleQuestion } from '../library-article-chat'
import type { LibraryChatEvent } from '../chat-stream'
import { isContentSlug } from './content-files'

type Messages = OpenAI.Chat.Completions.ChatCompletionMessageParam[]
const answerTokens = 4096
const bytes = (text: string) => Buffer.byteLength(text, 'utf8')
const readingTool: OpenAI.Chat.Completions.ChatCompletionTool = {
  type: 'function',
  function: {
    name: 'read_article_passages',
    description: '补查当前文献的一处具体原文。只有已经提供的资料不足时才调用，给出章节、图表编号或中英文关键词。',
    parameters: { type: 'object', properties: { query: { type: 'string' } }, required: ['query'] },
  },
}

export function parseArticleQuestion(value: unknown): LibraryArticleQuestion | null {
  if (!value || typeof value !== 'object') return null
  const { slug, quotes = [], history = [] } = value as Partial<LibraryArticleQuestion>
  if (typeof slug !== 'string' || slug.length > 120 || !isContentSlug(slug)) return null
  if (!Array.isArray(quotes) || quotes.length > MAX_ARTICLE_QUOTES || quotes.some(quote =>
    !quote || typeof quote.text !== 'string' || !quote.text.trim() || quote.text.length > MAX_ARTICLE_QUOTE_CHARS ||
    (quote.version !== undefined && quote.version !== '原文' && quote.version !== '翻译') ||
    (quote.anchor !== undefined && (typeof quote.anchor !== 'string' || !/^(passage-|ref-)\d+$/.test(quote.anchor))) ||
    (quote.section !== undefined && (typeof quote.section !== 'string' || quote.section.length > 240)))) return null
  if (!Array.isArray(history) || history.length > MAX_ARTICLE_CHAT_HISTORY || history.some(turn =>
    !turn || typeof turn.question !== 'string' || turn.question.length > 2000 || typeof turn.answer !== 'string' || turn.answer.length > 4000)) return null
  return { slug,
    quotes: quotes.map(({ text, version, anchor, section }) => ({ text: text.trim(), version, anchor, section })),
    history: history.map(({ question, answer }) => ({ question, answer })) }
}

export function readArticleQuestion(scope: LibraryArticleQuestion) {
  const paper = readPaperMetadata(scope.slug)
  if (!paper?.availableVersions.length) return null
  const version = paper.availableVersions.includes('原文') ? '原文' : '翻译'
  const raw = readPaper(paper.slug, version)
  if (!raw?.trim()) return null
  return { scope: { ...scope, slug: paper.slug, version } as const, paper, source: processLibraryContent(raw) }
}

export function articleInputBudget(model: string, baseURL: string, configured = process.env.WEIBULL_ARTICLE_CONTEXT_TOKENS): number {
  const limit = Number(configured) || (baseURL.replace(/\/$/, '') === 'https://api.deepseek.com' && model === 'deepseek-flash' ? 1048576 : 32768)
  // UTF-8 bytes conservatively approximate token usage across Chinese, English and TeX.
  return Math.max(0, Math.floor(limit) - answerTokens - 2048)
}

function mainContents(headings: { level: number; text: string }[]) {
  if (!headings.length) return []
  const min = Math.min(...headings.map(heading => heading.level))
  const root = headings.filter(heading => heading.level === min)
  const level = root.length === 1 && headings.length > 1 ? min + 1 : min
  return headings.filter(heading => heading.level <= level).map(heading => heading.text)
}

export async function answerArticleQuestion({
  article, question, client, model, baseURL, instructions, signal, send,
}: {
  article: NonNullable<ReturnType<typeof readArticleQuestion>>
  question: string
  client: OpenAI
  model: string
  baseURL: string
  instructions: string
  signal: AbortSignal
  send: (event: LibraryChatEvent) => void
}) {
  const { source, paper, scope } = article
  const budget = articleInputBudget(model, baseURL)
  const overview = {
    文献: paper.display_title || paper.title, 版本: scope.version, 类型: paper.type,
    文献介绍: paper.summary?.slice(0, 1600) || undefined, 作者摘要: source.abstract?.slice(0, 2400) || undefined,
    目录: mainContents(source.headings).map(title => title.slice(0, 160)).slice(0, 64),
  }
  const body = [source.body.trim(), source.referenceList.length
    ? `## ${source.referenceTitle}\n\n${source.referenceList.join('\n\n')}` : ''].filter(Boolean).join('\n\n')
  const fixed = `问题：${question}\n\n文献总览：${JSON.stringify(overview)}`
  const base: Messages = [{ role: 'system', content: instructions + '\n\n以用户当前问题所用的语言回答，用户明确指定回答语言时按其要求。范围限于当前文献。以提供的正文和参考资料为依据，用户选段可能来自译文，仅用于明确提问对象，与原文有出入时以原文为准。总览用于定位。保留适用条件，区分作者陈述与解释。图像链接和图注不代表读到了图像。若仅有片段，明确证据范围及缺口。引用编号只能使用参考资料提供的编号。' }]
  const within = (text: string, limit: number) => bytes(text) <= limit
  const reserved = Math.max(2400, Math.min(22000, Math.floor(budget / 5)))
  const available = budget - bytes(base[0].content as string) - bytes(fixed)
  const history: LibraryArticleQuestion['history'] = []
  const quoted = JSON.stringify(scope.quotes)
  if (!within(quoted, available - reserved - 1600)) {
    send({ error: '本次选段与总览超出模型输入预算，请减少选段后重试。' })
    return false
  }
  for (const turn of [...scope.history].reverse()) {
    if (within(JSON.stringify([turn, ...history]), Math.max(0, Math.min(available / 6, available - bytes(quoted) - reserved - 1600)))) history.unshift(turn)
  }
  const prefix = `${fixed}\n\n用户选段：${quoted}\n\n此前对话：${JSON.stringify(history)}`
  const room = Math.max(1024, budget - bytes(base[0].content as string) - bytes(prefix) - reserved)
  const full = within(body, room)
  send({ stage: 'searching', message: full ? '正在准备本篇全文…' : '正在本篇定位参考资料…' })
  await startLibrarySearchPrewarm()
  signal.throwIfAborted()
  const priorQuestion = history.at(-1)?.question
  const anchors = scope.quotes.flatMap(quote => quote.anchor && quote.version === scope.version ? [quote.anchor] : [])
  const anchored = libraryAnchoredPassages(scope, anchors)
  const sectionPassages = librarySectionPassages(scope, 6)
  const find = (query: string) => buildSearchQueries(query, [], 4)
    .map(text => searchLibrary(text, { document: scope, limit: 20 }).results)
  const limits = { maxPassages: 12, maxPerPaper: 12, maxContextChars: Math.floor(reserved / 3) }
  const prepare = (rankings: ReturnType<typeof find>) =>
    selectLibraryEvidence(rankings.map(enrichLibrarySearchHits), limits)
  let evidence = prepare([...find(question), ...(priorQuestion ? find(priorQuestion) : []), anchored, sectionPassages])
  const coverage = full ? '已提供本篇全文' : '长文 · 本次提供相关正文片段'
  let sections = full ? [] : Array.from(new Set(evidence.map(hit => hit.section)))
  const reading = full ? `全文 Markdown：\n${body}` : ''

  function publishEvidence() {
    send({ coverage, sections, evidence: evidence.map(({ context, contextStartLine, contextEndLine, ...hit }) => ({ ...hit, text: hit.excerpt })) })
  }

  async function respond(canReadMore: boolean): Promise<{ received: boolean; query?: string }> {
    const references = JSON.stringify(evidenceContext(evidence))
    const messages: Messages = [...base, { role: 'user', content: `${prefix}\n\n${reading}\n\n参考资料：${references}` }]
    const response = await client.chat.completions.create({
      model, messages, stream: true, max_tokens: answerTokens, temperature: .3,
      ...(canReadMore ? { tools: [readingTool], tool_choice: 'auto' as const } : {}),
      ...{ thinking: { type: 'disabled' } },
    }, { signal })
    let args = ''
    let received = false
    for await (const chunk of response) {
      const choice = chunk.choices[0]
      const text = choice?.delta.content
      if (text) { received = true; send({ content: text }) }
      for (const call of choice?.delta.tool_calls || []) if (call.index === 0) args += call.function?.arguments || ''
      if (choice?.finish_reason === 'length') send({ content: '\n\n（回答达到长度上限，可缩小范围后继续询问。）' })
    }
    let query: unknown
    if (canReadMore && !received && args) try { query = JSON.parse(args).query } catch { /* Continue with the original evidence. */ }
    return { received, query: typeof query === 'string' ? query.trim().slice(0, 500) : undefined }
  }

  publishEvidence()
  send({ stage: 'answering', message: '正在根据本篇资料生成回答…' })
  const first = await respond(!full)
  if (first.received || full) return first.received
  if (first.query) {
    send({ stage: 'searching', message: '正在补查本篇原文…' })
    evidence = prepare([...find(first.query), evidence])
    sections = Array.from(new Set(evidence.map(hit => hit.section)))
    publishEvidence()
  }
  send({ stage: 'answering', message: '正在综合本篇原文…' })
  return (await respond(false)).received
}
