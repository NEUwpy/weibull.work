export type LibraryVersion = '原文' | '翻译'

/** Public, selected-library excerpts shared by search results and answer citations. */
export interface LibrarySearchHit {
  id: string
  slug: string
  title: string
  version: LibraryVersion
  section: string
  startLine: number
  endLine: number
  text: string
  excerpt: string
  href: string
  score: number
  /** Optional neighbouring source blocks for AI; the matched paragraph and its link stay unchanged. */
  context?: string
  contextStartLine?: number
  contextEndLine?: number
}

export interface LibrarySearchResponse {
  query: string
  total: number
  results: LibrarySearchHit[]
  terms: string[]
}

export interface LibraryEvidence extends LibrarySearchHit {
  citation: number
}
