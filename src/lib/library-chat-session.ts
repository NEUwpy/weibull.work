import type { LibraryEvidence } from './library-search-types'

export interface LibraryChatRequest { id: number; question: string }
export interface LibraryChatAnswer {
  id: number
  content: string
  evidence?: LibraryEvidence[]
  queries?: string[]
  error?: string
  stopped?: boolean
  coverage?: string
  sections?: string[]
}
export interface LibraryChatSession {
  request: LibraryChatRequest
  answer: LibraryChatAnswer | null
  modelLabel: string
  active: boolean
}

const STORAGE_KEY = 'weibull:library-chat:v1'
let current: LibraryChatSession | null = null

export function readLibraryChatSession(): LibraryChatSession | null {
  if (current || typeof window === 'undefined') return current
  try {
    const saved = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) || 'null')
    if (saved && Number.isSafeInteger(saved.request?.id) && typeof saved.request.question === 'string'
      && typeof saved.active === 'boolean' && typeof saved.modelLabel === 'string'
      && (saved.answer === null || (saved.answer?.id === saved.request.id && typeof saved.answer.content === 'string'))) {
      current = saved
    }
  } catch { /* Storage may be unavailable; route navigation still retains the in-memory session. */ }
  return current
}

function save(session: LibraryChatSession) {
  current = session
  try { window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session)) } catch { /* Keep the in-memory session. */ }
}

export function startLibraryChat(request: LibraryChatRequest) {
  save({ request, answer: null, modelLabel: 'DeepSeek V4.1 Flash', active: true })
}

export function cacheLibraryChatAnswer(requestId: number, answer: LibraryChatAnswer, modelLabel: string) {
  const session = readLibraryChatSession()
  if (session?.request.id === requestId) save({ ...session, answer, modelLabel })
}

export function setLibraryChatActive(active: boolean) {
  const session = readLibraryChatSession()
  if (session) save({ ...session, active })
}
