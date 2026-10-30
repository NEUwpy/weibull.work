import type { LibraryEvidence, LibrarySearchHit } from './library-search-types'

/** Keep the exact question as the first search; model output only adds bounded variants. */
export function buildSearchQueries(question: string, generated: unknown, maxQueries = 6): string[] {
  const output: string[] = []
  const seen = new Set<string>()
  // Preserve distinct named methods even if a generated paraphrase omits or expands them wrongly.
  const namedTerms = Array.from(new Set(question.match(/\b[A-Z][A-Z0-9_-]{1,9}\b/g) || [])).slice(0, 3)
  const candidates = [question, ...namedTerms, ...(Array.isArray(generated) ? generated : [])]
  for (const candidate of candidates) {
    if (typeof candidate !== 'string') continue
    const query = candidate.trim().slice(0, output.length ? 160 : 2000)
    const key = query.normalize('NFKC').toLocaleLowerCase().replace(/\s+/g, ' ')
    if (!key || seen.has(key)) continue
    output.push(query)
    seen.add(key)
    if (output.length >= maxQueries) break
  }
  return output
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
): LibraryEvidence[] {
  const fused = selectLibraryEvidence(rankings, limits)
  return selectLibraryEvidence([[...rankings.flatMap(ranking => ranking.slice(0, 2)), ...fused]], limits)
}
