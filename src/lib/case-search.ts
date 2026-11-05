import type { CatalogEntry } from './case-datasets'

export type CaseSearchMatch = { entry: CatalogEntry; reason: string }
export type CaseSearchResponse = { question: string; results: CaseSearchMatch[] }

/** Model output can only rank entries in the current server-owned catalog. */
export function selectCaseSearchMatches(entries: CatalogEntry[], selection: unknown): CaseSearchMatch[] {
  if (!Array.isArray(selection)) throw new Error('Invalid case selection')
  const byId = new Map(entries.map(entry => [entry.id, entry]))
  const seen = new Set<string>()
  return selection.flatMap(match => {
    if (!match || typeof match.id !== 'string' || typeof match.reason !== 'string' || !match.reason.trim()
      || seen.has(match.id) || !byId.has(match.id)) return []
    seen.add(match.id)
    return [{ entry: byId.get(match.id)!, reason: match.reason.trim().slice(0, 300) }]
  }).slice(0, 20)
}
