import { createHash } from 'node:crypto'
import { readLibraryDocuments, type PaperMetadata } from './literature'
import { extractLibraryPassages, libraryPassageId, type LibraryPassage } from '../library-markdown'
import { createLiteratureIndex, fold } from '../literature-search.mjs'
import type { LibrarySearchHit, LibrarySearchResponse } from '../library-search-types'

export interface LibrarySearchOptions {
  limit?: number
  offset?: number
  type?: 'all' | 'book' | 'journal-conf'
}

const MAX_PASSAGE_CHARS = 1600
const MAX_CONTEXT_CHARS = 1800
const STOP_WORDS = new Set(('a an the and or of to in on for is are was were be been by with as at from that this it its how what why which ' +
  'can could would should do does did not about between into than then also these those through using used ' +
  '的 了 和 与 及 是 在 对 将 为 或 由 中 上 下 地 得 一种 一个 进行 可以 如何 什么 为什么 哪些 是否 问题 方法 研究 这个 那个 以及 关于').split(' '))
const segmenter = new Intl.Segmenter('zh', { granularity: 'word' })
const wordPattern = new RegExp('^[\\p{L}\\p{N}_-]+$', 'u')

/** Words plus CJK bigrams retain unfamiliar technical names without a dictionary service. */
function tokenize(value: string): string[] {
  const normalized = fold(value)
  const terms = new Set<string>()
  for (const entry of Array.from(segmenter.segment(normalized))) {
    const word = entry.segment
    if (!entry.isWordLike || STOP_WORDS.has(word)) continue
    if (/[\u3400-\u9fff]/.test(word)) {
      if (word.length > 1) terms.add(word)
      for (let index = 0; index < word.length - 1; index++) {
        const pair = word.slice(index, index + 2)
        if (!STOP_WORDS.has(pair)) terms.add(pair)
      }
    } else if (wordPattern.test(word)) terms.add(word)
  }
  return Array.from(terms)
}

export const libraryQueryTerms = (value: string): string[] => tokenize(value).slice(0, 64)

interface IndexedPassage {
  hit: LibrarySearchHit
  paper: PaperMetadata
  normalized: string
  frequencies: Map<string, number>
  length: number
}

let cachedSignature = ''
let cachedPassages: IndexedPassage[] = []
let cachedPapers: PaperMetadata[] = []
let cachedContextBlocks = new Map<string, LibraryPassage[]>()

function frequency(value: string): Map<string, number> {
  const counts = new Map<string, number>()
  // Segmenting sentences repeatedly keeps term frequency rather than only a presence set.
  for (const sentence of value.split(/[。！？.!?;；\n]+/)) {
    for (const term of tokenize(sentence)) counts.set(term, (counts.get(term) || 0) + 1)
  }
  return counts
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
  const documents = readLibraryDocuments()
  const signature = createHash('sha256')
  for (const document of documents) signature.update(JSON.stringify([document.paper, document.version, document.raw]))
  const digest = signature.digest('hex')
  if (digest === cachedSignature) return { passages: cachedPassages, papers: cachedPapers }
  const passages: IndexedPassage[] = []
  const papers = new Map<string, PaperMetadata>()
  const contextBlocks = new Map<string, LibraryPassage[]>()
  for (const document of documents) {
    papers.set(document.paper.slug, document.paper)
    const blocks = extractLibraryPassages(document.raw, true)
    contextBlocks.set(`${document.paper.slug}:${document.version}`, blocks)
    for (const passage of blocks) {
      if (passage.kind === 'math') continue
      const chunks = pieces(passage.text)
      chunks.forEach((text, index) => {
        const readable = plain(text)
        if (!readable) return
        const frequencies = frequency(readable)
        const hit: LibrarySearchHit = {
          id: `${document.paper.slug}:${document.version}:${passage.startLine}:${index}`,
          slug: document.paper.slug, title: document.paper.title, version: document.version,
          section: passage.section, startLine: passage.startLine, endLine: passage.endLine,
          text, excerpt: readable, score: 0,
          href: `/library/${encodeURIComponent(document.paper.slug)}?version=${encodeURIComponent(document.version)}#${libraryPassageId(passage.startLine)}`,
        }
        passages.push({ hit, paper: document.paper, normalized: fold(readable), frequencies,
          length: Math.max(1, Array.from(frequencies.values()).reduce((sum, count) => sum + count, 0)) })
      })
    }
  }
  cachedSignature = digest
  cachedPassages = passages
  cachedPapers = Array.from(papers.values())
  cachedContextBlocks = contextBlocks
  return { passages, papers: cachedPapers }
}

/** Add a bounded local evidence window without changing the search match or destination. */
export function enrichLibrarySearchHits(hits: LibrarySearchHit[]): LibrarySearchHit[] {
  readIndex()
  return hits.map(hit => {
    const blocks = cachedContextBlocks.get(`${hit.slug}:${hit.version}`)
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
  return !type || type === 'all' || (type === 'book' ? paper.type === '书籍' : paper.type === '期刊' || paper.type === '会议')
}

function excerpt(value: string, terms: string[]): string {
  const normalized = fold(value)
  const matches = terms.map(term => normalized.indexOf(term)).filter(index => index >= 0)
  const start = Math.max(0, (matches.length ? Math.min(...matches) : 0) - 70)
  const end = Math.min(value.length, start + 360)
  return `${start ? '…' : ''}${value.slice(start, end)}${end < value.length ? '…' : ''}`
}

/** Re-read the selected source snapshot; only an unchanged snapshot reuses its in-memory index. */
export function searchLibrary(query: string, options: LibrarySearchOptions = {}): LibrarySearchResponse {
  const q = query.trim().slice(0, 2000)
  const terms = libraryQueryTerms(q)
  if (!q) return { query: q, total: 0, results: [], terms }
  const { passages, papers } = readIndex()
  const catalog = createLiteratureIndex(papers.filter(paper => matchesType(paper, options.type)))
  const catalogMatches = catalog.search(q) as { record: PaperMetadata; score: number; fields: string[] }[]
  const identityQuery = /^\d{3}-\d{3}$/.test(q) || /^10\.\d{4,9}\//.test(q)
  const identities = new Set(catalogMatches.map(match => match.record.slug))
  const candidates = passages.filter(passage => matchesType(passage.paper, options.type) && (!identityQuery || identities.has(passage.hit.slug)))
  const documentFrequencies = new Map<string, number>()
  for (const term of terms) documentFrequencies.set(term, candidates.filter(candidate => candidate.frequencies.has(term)).length)
  const averageLength = candidates.reduce((sum, passage) => sum + passage.length, 0) / Math.max(1, candidates.length)
  const hits = new Map<string, LibrarySearchHit>()
  const normalizedQuery = fold(q).replace(/\s+/g, ' ')
  const escapedQuery = normalizedQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const exactPhrase = new RegExp(`${/^[a-z0-9_]/.test(normalizedQuery) ? '(?<![a-z0-9_])' : ''}${escapedQuery}${/[a-z0-9_]$/.test(normalizedQuery) ? '(?![a-z0-9_])' : ''}`)
  for (const passage of candidates) {
    let score = 0
    let matched = 0
    for (const term of terms) {
      const tf = passage.frequencies.get(term) || 0
      if (!tf) continue
      matched++
      const df = documentFrequencies.get(term) || 0
      const idf = Math.log(1 + (candidates.length - df + .5) / (df + .5))
      score += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * passage.length / averageLength))
    }
    if (normalizedQuery.length <= 200 && exactPhrase.test(passage.normalized)) score += 12
    if (!score) continue
    // A short exact term remains useful; longer passages gain from broad query coverage.
    score *= .3 + .7 * matched / Math.max(1, terms.length)
    // Keyword lists and isolated index entries are discoverable, but explanatory prose is more useful.
    if (passage.normalized.length < 20) score *= .15
    else if (passage.normalized.length < 50) score *= .5
    if (/^(?:关\s*键\s*词|关键词和短语|key\s*words(?:\s+and\s+phrases)?)\s*[:：]?/i.test(passage.normalized)) score *= .18
    hits.set(passage.hit.id, { ...passage.hit, score, excerpt: excerpt(passage.hit.excerpt, terms) })
  }
  // Retain the existing identity search for author, DOI, number and title queries.
  for (const match of catalogMatches) {
    const matching = Array.from(hits.values()).filter(hit => hit.slug === match.record.slug).sort((a, b) => b.score - a.score)[0]
    const first = (matching && candidates.find(passage => passage.hit.id === matching.id))
      ?? candidates.find(passage => passage.hit.slug === match.record.slug && passage.hit.version === '翻译' && passage.hit.text.length >= 40)
      ?? candidates.find(passage => passage.hit.slug === match.record.slug && passage.hit.text.length >= 40)
      ?? candidates.find(passage => passage.hit.slug === match.record.slug)
    if (!first) continue
    const existing = hits.get(first.hit.id)
    const score = Math.max(existing?.score || 0, 10 + match.score / 25)
    hits.set(first.hit.id, { ...first.hit, score, excerpt: excerpt(first.hit.excerpt, terms) })
  }
  const ranked = Array.from(hits.values()).sort((left, right) => right.score - left.score || left.id.localeCompare(right.id))
  const limit = Number.isFinite(options.limit) ? Math.max(1, Math.min(30, Math.floor(options.limit!))) : 10
  const offset = Number.isFinite(options.offset) ? Math.max(0, Math.floor(options.offset!)) : 0
  return { query: q, total: ranked.length, results: ranked.slice(offset, offset + limit), terms }
}
