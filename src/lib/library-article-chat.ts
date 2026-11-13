import type { LibraryVersion } from './library-search-types'

export const MAX_ARTICLE_QUOTES = 5
export const MAX_ARTICLE_QUOTE_CHARS = 6000
export const MAX_ARTICLE_CHAT_HISTORY = 6

export interface LibraryArticleQuote {
  text: string
  version?: LibraryVersion
  anchor?: string
  section?: string
}

export interface LibraryArticleQuestion {
  slug: string
  quotes: LibraryArticleQuote[]
  history: { question: string; answer: string }[]
}
