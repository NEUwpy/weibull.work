import type { LibraryEvidence, LibrarySearchHit } from './library-search-types'
import { INITIAL_METHOD_TREE } from './methods'

const methodNamesByAbbreviation = new Map(INITIAL_METHOD_TREE.flatMap(group =>
  (group.children ?? []).map(method => [method.shortName.toUpperCase(), method.name] as const)))
const methodNamePattern = new RegExp(Array.from(new Set(methodNamesByAbbreviation.values()))
  .sort((left, right) => right.length - left.length)
  .map(name => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  .join('|'), 'g')

function queryKey(query: string): string {
  return query.normalize('NFKC').toLocaleLowerCase().replace(/\s+/g, ' ').trim()
}

function namedMethodTerms(question: string): string[] {
  return Array.from(new Set(question.match(/\b[A-Z][A-Z0-9_-]{1,9}\b/g) || [])).slice(0, 3)
}

function namedMethodNames(question: string, terms = namedMethodTerms(question)): string[] {
  const writtenNames = question.normalize('NFKC').match(methodNamePattern) ?? []
  const expandedNames = terms.flatMap(term => methodNamesByAbbreviation.get(term) ?? [])
  return Array.from(new Set([...writtenNames, ...expandedNames])).slice(0, 3)
}

/** Keep the exact question first and preserve independent searches for methods and the broader topic. */
export function buildSearchQueries(question: string, generated: unknown, maxQueries = 6, recommendPapers = false,
  focusedQueries: string[] = [],
): string[] {
  const output: string[] = []
  const seen = new Set<string>()
  // Preserve distinct named methods even if a generated paraphrase omits or expands them wrongly.
  const namedTerms = namedMethodTerms(question)
  const methodNames = recommendPapers ? namedMethodNames(question, namedTerms) : []
  // An independent broad search keeps work on other estimators in scope for this compound topic.
  const smallSampleTopic = recommendPapers && /小样本/.test(question) && /参数估计|估参/.test(question)
    ? '小样本 参数估计'
    : undefined
  // Leave room for a generated expression that covers another condition, such as censoring.
  const priorityNameCount = Math.max(0, maxQueries - namedTerms.length - (smallSampleTopic ? 1 : 0) - 1 - Math.max(1, focusedQueries.length))
  const variants = Array.isArray(generated) ? generated : []
  const candidates = [question, ...namedTerms, smallSampleTopic,
    ...methodNames.slice(0, priorityNameCount), ...focusedQueries, ...variants, ...methodNames.slice(priorityNameCount)]
  for (const candidate of candidates) {
    if (typeof candidate !== 'string') continue
    const query = candidate.trim().slice(0, output.length ? 160 : 2000)
    const key = queryKey(query)
    if (!key || seen.has(key)) continue
    output.push(query)
    seen.add(key)
    if (output.length >= maxQueries) break
  }
  return output
}

interface RecommendationQueryExpansion {
  queries?: unknown
  mechanism_queries?: unknown
  comparison_query?: unknown
}

function focusedQuery(value: unknown): string {
  return typeof value === 'string' ? value.trim().replace(/\s+/g, ' ').slice(0, 120).trimEnd() : ''
}

const tuningTerminology = /\btuning[- ]+(?:parameters?|constants?)\b|(?:调优|调节|调谐)(?:参数|常数|量)/i

export function buildRecommendationSearchPlan(question: string, expansion: RecommendationQueryExpansion, maxQueries: number) {
  const generatedMechanisms = Array.isArray(expansion.mechanism_queries) ? expansion.mechanism_queries : []
  const mechanisms = new Map<string, string>()
  for (const value of generatedMechanisms) {
    const query = focusedQuery(value)
    if (query && !mechanisms.has(queryKey(query))) mechanisms.set(queryKey(query), query)
    if (mechanisms.size === 2) break
  }
  const generatedFocus = Array.from(mechanisms.values())
  const usesTuningTerminology = generatedFocus.some(query => tuningTerminology.test(queryKey(query)))
  // The two terms are used by different estimator families. Longer AI-generated phrases can require all modifiers to match.
  const mechanismTerms = usesTuningTerminology ? ['tuning parameter', 'tuning constant'] : generatedFocus
  const mechanismKeys = new Set(mechanismTerms.map(queryKey))
  const comparison = focusedQuery(expansion.comparison_query)
  const comparisonKey = queryKey(comparison)
  const focused = [...mechanismTerms]
  if (comparisonKey && !mechanismKeys.has(comparisonKey)) focused.push(comparison)
  const variants = Array.isArray(expansion.queries) ? expansion.queries : []
  const queries = buildSearchQueries(question, [...variants, ...generatedFocus], maxQueries, true, focused)
  const methodNames = namedMethodNames(question)
  return {
    queries,
    mechanismQueries: queries.filter(query => mechanismKeys.has(queryKey(query))),
    comparisonQuery: comparisonKey ? queries.find(query => queryKey(query) === comparisonKey) : undefined,
    methodQueries: queries.filter(query => methodNames.includes(query)),
  }
}

export function evidenceContext(evidence: LibraryEvidence[]) {
  return evidence.map(({ citation, slug, title, version, section, href, text }) => ({
    citation, slug, title, version, section, href, text,
  }))
}

/** Fuse independent rankings without comparing scores from differently worded queries. */
export function selectLibraryEvidence(
  rankings: LibrarySearchHit[][],
  limits: { maxPassages: number; maxPerPaper: number; maxContextChars: number },
): LibraryEvidence[] {
  const candidates = new Map<string, { hit: LibrarySearchHit; weight: number }>()
  rankings.forEach((ranking, queryIndex) => {
    const seen = new Set<string>()
    ranking.forEach((hit, index) => {
      if (seen.has(hit.id) || !hit.text.trim() || hit.startLine < 1) return
      seen.add(hit.id)
      const previous = candidates.get(hit.id)
      const weight = (queryIndex === 0 ? 1.25 : 1) / (50 + index + 1)
      candidates.set(hit.id, { hit, weight: (previous?.weight || 0) + weight })
    })
  })
  const selected: LibraryEvidence[] = []
  const perPaper = new Map<string, number>()
  const texts = new Set<string>()
  for (const { hit } of Array.from(candidates.values()).sort((a, b) => b.weight - a.weight || a.hit.id.localeCompare(b.hit.id))) {
    if (selected.length >= limits.maxPassages) break
    const text = hit.context || hit.text
    const normalized = text.normalize('NFKC').toLowerCase().replace(/\s+/g, '')
    if (texts.has(normalized) || (perPaper.get(hit.slug) || 0) >= limits.maxPerPaper) continue
    const candidate: LibraryEvidence = { ...hit, text, citation: selected.length + 1 }
    if (JSON.stringify(evidenceContext([...selected, candidate])).length > limits.maxContextChars) continue
    selected.push(candidate)
    texts.add(normalized)
    perPaper.set(hit.slug, (perPaper.get(hit.slug) || 0) + 1)
  }
  return selected
}

/** Only IDs present in server-side candidates can become model-selected evidence. */
export function orderEvidenceCandidates(candidates: LibraryEvidence[], ids: unknown): LibraryEvidence[] {
  if (!Array.isArray(ids)) throw new Error('Invalid evidence selection')
  const byId = new Map(candidates.map(candidate => [candidate.id, candidate]))
  const seen = new Set<string>()
  return ids.flatMap(id => {
    if (typeof id !== 'string' || seen.has(id) || !byId.has(id)) return []
    seen.add(id)
    return [byId.get(id)!]
  })
}

/** Reserve a few candidates from each search before fusion can crowd out a comparison object. */
export function poolLibraryCandidates(
  rankings: LibrarySearchHit[][],
  limits: { maxPassages: number; maxPerPaper: number; maxContextChars: number },
  focusedRankings: LibrarySearchHit[][] = [],
): LibraryEvidence[] {
  const fused = selectLibraryEvidence(rankings, limits)
  // Interleave focused rankings so the context budget sees each search purpose early.
  const depth = Math.max(0, ...focusedRankings.map(ranking => ranking.length))
  const preferred = Array.from({ length: depth }, (_, rank) =>
    focusedRankings.flatMap(ranking => ranking.slice(rank, rank + 1))).flat()
  return selectLibraryEvidence([[...preferred, ...rankings.flatMap(ranking => ranking.slice(0, 2)), ...fused]], limits)
}
