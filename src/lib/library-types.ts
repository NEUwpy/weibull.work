import documentTypes from '../data/library-types.json'

export type LibraryTypeFilter = 'all' | 'book' | 'paper'

export function libraryTypeLabel(type?: string): string {
  return type && Object.hasOwn(documentTypes, type) ? type : '待核实'
}

/** Shared by card counts, card filtering and full-text filtering. */
export function matchesLibraryType(paper: { type?: string }, filter: LibraryTypeFilter | 'journal' | 'journal-conf' = 'all'): boolean {
  if (filter === 'all') return true
  if (filter === 'journal-conf') return paper.type === '期刊' || paper.type === '会议'
  if (filter === 'journal') return paper.type === '期刊'
  return documentTypes[paper.type as keyof typeof documentTypes] === filter
}
