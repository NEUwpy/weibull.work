import type { LibraryTitlePresentation } from './library-titles'

export type LibraryVersion = '原文' | '翻译'

/** Public, selected-library excerpts shared by search results and answer citations. */
export interface LibrarySearchHit extends LibraryTitlePresentation {
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

/** Search exposes a bounded excerpt; complete passages stay on the server. */
export type LibrarySearchPreview = Omit<LibrarySearchHit, 'text' | 'context' | 'contextStartLine' | 'contextEndLine'>

export interface LibrarySearchResponse<Hit = LibrarySearchPreview> {
  query: string
  total: number
  results: Hit[]
  terms: string[]
}

export interface LibraryEvidence extends LibrarySearchHit {
  citation: number
}
