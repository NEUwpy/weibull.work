import { readLibraryDocuments, type LibraryDocument, type PaperMetadata } from './literature'
import { extractLibraryPassages, libraryPassageId, type LibraryPassage } from '../library-markdown'
import { createLiteratureIndex, fold, titleKey } from '../literature-search.mjs'
import type { LibrarySearchHit, LibrarySearchResponse } from '../library-search-types'
import { libraryMathExcerpt } from '../library-math-markdown'
import { setImmediate, setTimeout } from 'node:timers'
import { matchesLibraryType, type LibraryTypeFilter } from '../library-types'
import { matchesLibraryCategory } from '../library-categories'
import { compareLibraryOrder, type LibrarySort } from '../library-sort'

export interface LibrarySearchOptions {
  limit?: number
  offset?: number
  type?: LibraryTypeFilter | 'journal' | 'journal-conf'
  scope?: 'auto' | 'text'
  category?: string
  sort?: LibrarySort
}

const MAX_PASSAGE_CHARS = 1600
const MAX_CONTEXT_CHARS = 1800
const STOP_WORDS = new Set(('a an the and or of to in on for is are was were be been by with as at from that this it its how what why which ' +
  'can could would should do does did not about between into than then also these those through using used ' +
  '的 了 和 与 及 是 在 对 将 为 或 由 中 上 下 地 得 一种 一个 进行 可以 如何 什么 为什么 哪些 是否 问题 方法 研究 这个 那个 以及 关于').split(' '))
const segmenter = new Intl.Segmenter('zh', { granularity: 'word' })
const wordPattern = new RegExp('^[\\p{L}\\p{N}_-]+$', 'u')

/** Segmenter words plus adjacent Han bigrams preserve names split into single characters. */
function tokenize(value: string): string[] {
  const normalized = fold(value)
  const terms = new Set<string>()
  for (const entry of Array.from(segmenter.segment(normalized))) {
    const word = entry.segment
    if (!entry.isWordLike || STOP_WORDS.has(word)) continue
    if (/[\u3400-\u9fff]/.test(word)) {
      terms.add(word)
    } else if (wordPattern.test(word)) terms.add(word)
  }
  for (const run of normalized.match(/[\u3400-\u9fff]+/g) || []) {
    for (let index = 0; index < run.length - 1; index++) {
      const pair = run.slice(index, index + 2)
      if (!STOP_WORDS.has(pair)) terms.add(pair)
    }
  }
  return Array.from(terms)
}

interface QueryProfile { terms: string[]; strict: boolean }

function queryProfile(value: string): QueryProfile {
  const normalized = fold(value).trim()
  const tokens = Array.from(segmenter.segment(normalized)).filter(entry => entry.isWordLike && !STOP_WORDS.has(entry.segment))
  const hanRuns = normalized.match(/[\u3400-\u9fff]+/g) || []
  const latin = tokens.filter(entry => !/[\u3400-\u9fff]/.test(entry.segment)).map(entry => entry.segment)
  // Short keyword input expresses complete concepts. Do not silently turn 矩估计 into 估计.
  // A question/sentence instead uses coverage over its informative words and adjacent character pairs.
  const sentence = /[。！？!?;；\n]|(?:如何|为什么|什么|哪些|是否|怎么|怎样|请|解释|介绍|说明|比较|能否)/.test(normalized)
  const strict = !sentence && normalized.length <= 48 && latin.length <= 6 && hanRuns.length <= 6 && hanRuns.every(run => run.length <= 12)
  if (strict) {
    return { strict, terms: Array.from(new Set([...hanRuns.filter(run => !STOP_WORDS.has(run)), ...latin])).slice(0, 64) }
  }
  return { strict, terms: tokenize(normalized).slice(0, 64) }
}

export const libraryQueryTerms = (value: string): string[] => queryProfile(value).terms

function termPattern(term: string): RegExp {
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`${/^[a-z0-9_]/.test(term) ? '(?<![a-z0-9_])' : ''}${escaped}${/[a-z0-9_]$/.test(term) ? '(?![a-z0-9_])' : ''}`, 'g')
}

function keywordList(value: string): boolean {
  return /^(?:关\s*键\s*词|关键词和短语|key\s*words(?:\s+and\s+phrases)?)\s*[:：]?/i.test(value)
}

interface IndexedPassage {
  hit: LibrarySearchHit
  paper: PaperMetadata
  normalized: string
  length: number
}

interface DocumentIndex {
  raw: string
  metadata: string
  passages: IndexedPassage[]
  blocks: LibraryPassage[]
}

interface SearchIndexCache {
  documents: LibraryDocument[] | null
  byDocument: Map<string, DocumentIndex>
  passages: IndexedPassage[]
  papers: PaperMetadata[]
  contextBlocks: Map<string, LibraryPassage[]>
  catalogs: Map<string, ReturnType<typeof createLiteratureIndex>>
  warming?: Promise<void>
  warmTimer?: ReturnType<typeof setTimeout>
  refresh?: () => Promise<void>
}

// The Node startup hook and API bundle share this process-local representation.
// Change this namespace if the indexed representation/normalization changes during HMR.
const indexCacheKey = Symbol.for('weibull.library-search.v4')
const indexCaches = globalThis as unknown as Record<symbol, SearchIndexCache>
const indexCache = indexCaches[indexCacheKey] ??= {
  documents: null, byDocument: new Map(), passages: [], papers: [], contextBlocks: new Map(), catalogs: new Map(),
}

function pieces(text: string): string[] {
  const chunks: string[] = []
  for (let start = 0; start < text.length;) {
    let end = Math.min(start + MAX_PASSAGE_CHARS, text.length)
    if (end < text.length) {
      const boundary = Math.max(text.lastIndexOf('\n', end), text.lastIndexOf('。', end), text.lastIndexOf('. ', end))
      if (boundary > start + MAX_PASSAGE_CHARS / 2) end = boundary + 1
    }
    chunks.push(text.slice(start, end).trim())
    start = end
  }
  return chunks.filter(Boolean)
}

function plain(value: string): string {
  return value.replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/<[^>]+>/g, '')
    .replace(/[`*#]/g, '').replace(/\s+/g, ' ').trim()
}

function readIndex(): { passages: IndexedPassage[]; papers: PaperMetadata[] } {
  let documents = readLibraryDocuments()
  while (documents !== indexCache.documents) {
    const update = updateIndex(documents)
    while (!update.next().done) { /* Synchronous callers share the same builder. */ }
    documents = readLibraryDocuments()
  }
  return indexCache
}

function* updateIndex(documents: LibraryDocument[]): Generator<void> {
  const passages: IndexedPassage[] = []
  const papers = new Map<string, PaperMetadata>()
  const contextBlocks = new Map<string, LibraryPassage[]>()
  const nextDocuments = new Map<string, DocumentIndex>()
  for (const document of documents) {
    papers.set(document.paper.slug, document.paper)
    const key = `${document.paper.slug}:${document.version}`
    const metadata = JSON.stringify(document.paper)
    const previous = indexCache.byDocument.get(key)
    if (previous?.raw === document.raw && previous.metadata === metadata) {
      passages.push(...previous.passages)
      contextBlocks.set(key, previous.blocks)
      nextDocuments.set(key, previous)
      continue
    }
    const blocks = extractLibraryPassages(document.raw, true)
    const ownPassages: IndexedPassage[] = []
    contextBlocks.set(key, blocks)
    for (const passage of blocks) {
      if (passage.kind === 'math') continue
      const chunks = pieces(passage.text)
      chunks.forEach((text, index) => {
        const readable = plain(text)
        if (!readable) return
        const hit: LibrarySearchHit = {
          id: `${document.paper.slug}:${document.version}:${passage.startLine}:${index}`,
          slug: document.paper.slug, title: document.paper.title, version: document.version,
          display_title: document.paper.display_title, original_title: document.paper.original_title,
          original_language: document.paper.original_language,
          section: passage.section, startLine: passage.startLine, endLine: passage.endLine,
          text, excerpt: readable, score: 0,
          href: `/library/${encodeURIComponent(document.paper.slug)}?version=${encodeURIComponent(document.version)}#${libraryPassageId(passage.startLine)}`,
        }
        ownPassages.push({ hit, paper: document.paper, normalized: fold(readable),
          // Query terms are matched directly; corpus-wide Intl tokenization is unnecessary.
          length: Math.max(1, (readable.match(/[A-Za-z0-9_]+|[^\s]/g) || []).length) })
      })
    }
    passages.push(...ownPassages)
    nextDocuments.set(key, { raw: document.raw, metadata, passages: ownPassages, blocks })
    yield
  }
  // A source may change while automatic warming yields between documents.
  // Publish a complete, current snapshot instead of replacing it with an older build.
  if (readLibraryDocuments() !== documents) return
  indexCache.documents = documents
  indexCache.byDocument = nextDocuments
  indexCache.passages = passages
  indexCache.papers = Array.from(papers.values())
  indexCache.contextBlocks = contextBlocks
  indexCache.catalogs.clear()
}

/** Called by the Node startup hook, before users submit the first search. */
export function warmLibrarySearch(): void { readIndex() }

/** Share one incremental build across startup, automatic checks and waiting requests. */
export function prepareLibrarySearch(): Promise<void> {
  if (indexCache.warming) return indexCache.warming
  indexCache.warming = (async () => {
    let documents = readLibraryDocuments()
    if (documents === indexCache.documents) return
    const started = Date.now()
    do {
      const update = updateIndex(documents)
      while (!update.next().done) await new Promise<void>(resolve => setImmediate(resolve))
      documents = readLibraryDocuments()
    } while (documents !== indexCache.documents)
    console.info('[library-search] Index ready', { documents: documents.length,
      papers: indexCache.papers.length, passages: indexCache.passages.length, elapsedMs: Date.now() - started })
  })().finally(() => { indexCache.warming = undefined })
  return indexCache.warming
}

/** The global timer survives Next module boundaries/HMR and does not keep Node alive. */
export function startLibrarySearchPrewarm(): Promise<void> {
  indexCache.refresh = prepareLibrarySearch
  if (!indexCache.warmTimer) {
    const schedule = () => {
      indexCache.warmTimer = setTimeout(() => {
        void indexCache.refresh!().catch(error => {
          // Source mounts and partially written selections may recover on the next check.
          console.warn('Library search warm-up unavailable:', error instanceof Error ? error.name : 'Unknown error')
        }).finally(schedule)
      }, 10_000)
      indexCache.warmTimer.unref()
    }
    schedule()
  }
  return prepareLibrarySearch()
}

/** Add a bounded local evidence window without changing the search match or destination. */
export function enrichLibrarySearchHits(hits: LibrarySearchHit[]): LibrarySearchHit[] {
  readIndex()
  return hits.map(hit => {
    const blocks = indexCache.contextBlocks.get(`${hit.slug}:${hit.version}`)
    const center = blocks?.findIndex(block => block.startLine === hit.startLine && block.endLine === hit.endLine) ?? -1
    if (!blocks || center < 0 || !blocks[center].text.includes(hit.text)) return hit
    const seed = blocks[center]
    // A very long paragraph is already split into search chunks; keep that exact chunk.
    if (seed.text.length > MAX_CONTEXT_CHARS) {
      return { ...hit, context: hit.text, contextStartLine: hit.startLine, contextEndLine: hit.endLine }
    }
    let left = center
    let right = center
    let length = seed.text.length
    let before = true
    let after = true
    for (let round = 0; round < 3 && (before || after); round++) {
      // Definitions commonly introduce the following display equation; include it first.
      for (const direction of ['after', 'before'] as const) {
        if (direction === 'after' ? !after : !before) continue
        const next = direction === 'after' ? right + 1 : left - 1
        const block = blocks[next]
        const edge = blocks[direction === 'after' ? right : left]
        const gap = block && (direction === 'after' ? block.startLine - edge.endLine : edge.startLine - block.endLine)
        const shortEnough = block && block.text.length <= (block.kind === 'math' ? 1200 : 700)
        if (!block || block.sectionStartLine !== seed.sectionStartLine || !shortEnough || gap > 8 || length + block.text.length + 2 > MAX_CONTEXT_CHARS) {
          if (direction === 'after') after = false
          else before = false
          continue
        }
        length += block.text.length + 2
        if (direction === 'after') right = next
        else left = next
      }
    }
    return { ...hit, context: blocks.slice(left, right + 1).map(block => block.text).join('\n\n'),
      contextStartLine: blocks[left].startLine, contextEndLine: blocks[right].endLine }
  })
}

function matchesType(paper: PaperMetadata, type: LibrarySearchOptions['type']): boolean {
  return matchesLibraryType(paper, type)
}

function qualityFactor(passage: IndexedPassage): number {
  const length = passage.normalized.length
  return (length < 20 ? .15 : length < 50 ? .5 : 1) * (keywordList(passage.normalized) ? .18 : 1)
}

/** Match and rank the current in-memory index after inexpensive source metadata checks. */
export function searchLibrary(query: string, options: LibrarySearchOptions = {}): LibrarySearchResponse<LibrarySearchHit> {
  const q = query.trim().slice(0, 2000)
  const { terms, strict } = queryProfile(q)
  if (!q) return { query: q, total: 0, results: [], terms }
  const { passages, papers } = readIndex()
  const matches = (paper: PaperMetadata) => matchesType(paper, options.type) && matchesLibraryCategory(paper, options.category)
  const catalogKey = JSON.stringify([options.type || 'all', options.category || 'all'])
  let catalog = indexCache.catalogs.get(catalogKey)
  if (!catalog) {
    catalog = createLiteratureIndex(papers.filter(matches).map(paper => ({ ...paper,
      title: paper.display_title || paper.title, title_en: paper.original_title || paper.title_en })))
    indexCache.catalogs.set(catalogKey, catalog)
  }
  const catalogMatches = (options.scope === 'text' ? [] : catalog.search(q)) as { record: PaperMetadata; score: number; fields: string[] }[]
  const identifierQuery = options.scope !== 'text' && (/^\d{3}-\d{3}$/.test(q) || /^10\.\d{4,9}\//.test(q))
  const compactQuery = titleKey(q)
  const identities = catalogMatches.filter(match =>
    (identifierQuery && match.fields.some(field => field === 'id' || field === 'doi')) ||
    match.fields.includes('author') ||
    [match.record.title, match.record.title_en].some(title => title && titleKey(title) === compactQuery))
  const identitySlugs = new Set(identities.map(match => match.record.slug))
  const candidates = passages.filter(passage => matches(passage.paper) && (!identifierQuery || identitySlugs.has(passage.hit.slug)))
  const patterns = terms.map(termPattern)
  const queryWeights = terms.map(term => /[\u3400-\u9fff]/.test(term) && term.length === 1 ? .2 : 1)
  const totalWeight = queryWeights.reduce((sum, weight) => sum + weight, 0)
  const counts = candidates.map(passage => patterns.map(pattern => passage.normalized.match(pattern)?.length || 0))
  const documentFrequencies = new Map<string, number>()
  terms.forEach((term, index) => documentFrequencies.set(term, counts.filter(row => row[index] > 0).length))
  const averageLength = candidates.reduce((sum, passage) => sum + passage.length, 0) / Math.max(1, candidates.length)
  const hits = new Map<string, LibrarySearchHit>()
  const normalizedQuery = fold(q).replace(/\s+/g, ' ')
  const exactPhrase = termPattern(normalizedQuery)
  candidates.forEach((passage, row) => {
    let score = 0
    let matched = 0
    let matchedWeight = 0
    terms.forEach((term, index) => {
      const tf = counts[row][index]
      if (!tf) return
      matched++
      matchedWeight += queryWeights[index]
      const df = documentFrequencies.get(term) || 0
      const idf = Math.log(1 + (candidates.length - df + .5) / (df + .5))
      score += queryWeights[index] * idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * passage.length / averageLength))
    })
    const coverage = matchedWeight / Math.max(1, totalWeight)
    if (!matched || (strict ? matched !== terms.length : matched < Math.min(2, terms.length) || coverage < .3)) return
    if (normalizedQuery.length <= 200 && passage.normalized.match(exactPhrase)) score += 12
    score *= (.3 + .7 * coverage) * qualityFactor(passage)
    hits.set(passage.hit.id, { ...passage.hit, score, excerpt: libraryMathExcerpt(passage.hit.text, terms) })
  })
  // Only explicit identities may introduce an article without a matching body paragraph.
  // Ordinary metadata keywords never manufacture body matches or override their ranking.
  for (const match of identities) {
    const matching = Array.from(hits.values()).filter(hit => hit.slug === match.record.slug).sort((a, b) => b.score - a.score)[0]
    const identityScore = 10 + match.score / 25
    if (matching) {
      hits.set(matching.id, { ...matching, score: Math.max(matching.score, identityScore) })
      continue
    }
    const representatives = candidates.filter(passage => passage.hit.slug === match.record.slug)
      .sort((left, right) => {
        const quality = (passage: IndexedPassage) => qualityFactor(passage) * (passage.hit.text.length >= 120 ? 1 : .3) * (passage.hit.version === '翻译' ? 1.1 : 1)
        return quality(right) - quality(left) || left.hit.startLine - right.hit.startLine
      })
    const first = representatives[0]
    if (!first) continue
    hits.set(first.hit.id, { ...first.hit, score: identityScore, excerpt: libraryMathExcerpt(first.hit.text, terms) })
  }
  const bySlug = new Map(papers.map(paper => [paper.slug, paper]))
  const ranked = Array.from(hits.values()).sort((left, right) => {
    if (options.sort && options.sort !== 'relevance') {
      const order = compareLibraryOrder(bySlug.get(left.slug)!, bySlug.get(right.slug)!, options.sort)
      if (order) return order
    }
    return right.score - left.score || left.id.localeCompare(right.id)
  })
  const limit = Number.isFinite(options.limit) ? Math.max(1, Math.min(30, Math.floor(options.limit!))) : 10
  const offset = Number.isFinite(options.offset) ? Math.max(0, Math.floor(options.offset!)) : 0
  return { query: q, total: ranked.length, results: ranked.slice(offset, offset + limit), terms }
}
