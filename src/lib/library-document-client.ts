import type { LibraryVersion } from './library-search-types'

type References = Record<string, string>
type Fetcher = (url: string, init: RequestInit) => Promise<Response>
interface CacheOptions {
  fetcher?: Fetcher
  now?: () => number
  maxEntries?: number
  maxBytes?: number
  ttlMs?: number
}

export class LibraryAuthenticationError extends Error {
  readonly code = 'AUTH_REQUIRED'
  constructor() { super('登录后即可阅读原文与译文。'); this.name = 'LibraryAuthenticationError' }
}

function authenticationRequired(): never {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event('weibull:library-auth-required'))
  throw new LibraryAuthenticationError()
}

/** Short-lived, bounded browser memory; no persistent copy of library content. */
export function createLibraryDocumentClient(options: CacheOptions = {}) {
  const fetcher = options.fetcher || ((url, init) => fetch(url, init))
  const now = options.now || Date.now
  const maxEntries = options.maxEntries ?? 16
  const maxBytes = options.maxBytes ?? 8 * 1024 * 1024
  const ttl = options.ttlMs ?? 5 * 60 * 1000
  const cache = new Map<string, { promise: Promise<unknown>; bytes: number; expires: number | null }>()
  let bytes = 0
  let generation = 0

  function clear() {
    generation++
    cache.clear()
    bytes = 0
  }

  function remove(key: string) {
    const entry = cache.get(key)
    if (entry) bytes -= entry.bytes
    cache.delete(key)
  }

  function trim() {
    for (const [key, entry] of Array.from(cache)) {
      if (cache.size <= maxEntries && bytes <= maxBytes) break
      if (entry.expires !== null) remove(key)
    }
    // Rapid navigation may leave old reads in flight; retain only the newest keys.
    while (cache.size > maxEntries) remove(cache.keys().next().value!)
  }

  function read<T>(url: string, load: () => Promise<T>): Promise<T> {
    const found = cache.get(url)
    if (found && (found.expires === null || found.expires > now())) {
      cache.delete(url)
      cache.set(url, found)
      return found.promise as Promise<T>
    }
    if (found) remove(url)
    const currentGeneration = generation
    const entry = { promise: Promise.resolve() as Promise<unknown>, bytes: 0, expires: null as number | null }
    entry.promise = load().then(value => {
      if (currentGeneration !== generation) throw new DOMException('阅读会话已更新。', 'AbortError')
      if (cache.get(url) === entry) {
        entry.bytes = (typeof value === 'string' ? value.length : JSON.stringify(value).length) * 2
        entry.expires = now() + ttl
        bytes += entry.bytes
        trim()
      }
      return value
    }, cause => {
      if (cache.get(url) === entry) remove(url)
      throw cause
    })
    cache.set(url, entry)
    trim()
    return entry.promise as Promise<T>
  }

  function readFile(slug: string, version: LibraryVersion): Promise<string | null> {
    const url = '/api/content?' + new URLSearchParams({ slug, type: version })
    const currentGeneration = generation
    return read(url, async () => {
      const response = await fetcher(url, { cache: 'no-store' })
      if (currentGeneration !== generation) throw new DOMException('阅读会话已更新。', 'AbortError')
      if (response.status === 401) return authenticationRequired()
      if (response.status === 404) return null
      if (!response.ok) throw new Error('文献库暂时不可用，请稍后重试。')
      return response.text()
    })
  }

  function readReferences(slug: string, version: LibraryVersion): Promise<References> {
    const url = '/api/library/references?' + new URLSearchParams({ slug, type: version })
    const currentGeneration = generation
    return read(url, async () => {
      const response = await fetcher(url, { cache: 'no-store' })
      if (currentGeneration !== generation) throw new DOMException('阅读会话已更新。', 'AbortError')
      if (response.status === 401) return authenticationRequired()
      if (!response.ok) throw new Error('文献引用暂时不可用，请稍后重试。')
      return response.json()
    })
  }

  return { readFile, readReferences, clear }
}

export const libraryDocumentClient = createLibraryDocumentClient()
if (typeof window !== 'undefined') {
  window.addEventListener('weibull:library-session-reset', () => libraryDocumentClient.clear())
}
type LibraryClient = ReturnType<typeof createLibraryDocumentClient>
type Schedule = (start: () => void) => () => void
let backgroundRequests = 0
const backgroundQueue: { job: () => Promise<unknown>; stopped: () => boolean; resolve: () => void }[] = []

function drainBackgroundQueue() {
  for (let index = backgroundQueue.length - 1; index >= 0; index--) {
    if (backgroundQueue[index].stopped()) backgroundQueue.splice(index, 1)[0].resolve()
  }
  while (backgroundRequests < 2 && backgroundQueue.length) {
    const task = backgroundQueue.shift()!
    backgroundRequests++
    void (async () => {
      try { await task.job() } catch { /* Foreground reads retry failed requests. */ }
      finally { backgroundRequests--; task.resolve(); drainBackgroundQueue() }
    })()
  }
}

function runBackground(job: () => Promise<unknown>, stopped: () => boolean): Promise<void> {
  return new Promise(resolve => {
    backgroundQueue.push({ job, stopped, resolve })
    drainBackgroundQueue()
  })
}

function afterResultsPaint(start: () => void): () => void {
  let idle: number | undefined
  const timer = window.setTimeout(() => {
    if (typeof window.requestIdleCallback === 'function') idle = window.requestIdleCallback(start, { timeout: 800 })
    else start()
  }, 200)
  return () => { window.clearTimeout(timer); if (idle !== undefined) window.cancelIdleCallback(idle) }
}

/** Delay until results are visible, then read at most four distinct versions with two requests in flight. */
export function scheduleLibraryResultPrefetch(
  hits: readonly { slug: string; version: LibraryVersion }[],
  client: LibraryClient = libraryDocumentClient,
  schedule: Schedule = afterResultsPaint,
): () => void {
  const seen = new Set<string>()
  const jobs: (() => Promise<unknown>)[] = []
  for (const hit of hits) {
    const key = `${hit.slug}:${hit.version}`
    if (seen.has(key)) continue
    seen.add(key)
    jobs.push(() => client.readFile(hit.slug, hit.version), () => client.readReferences(hit.slug, hit.version))
    if (seen.size === 4) break
  }
  let stopped = false
  let next = 0
  async function worker() {
    while (!stopped && next < jobs.length) {
      const job = jobs[next++]
      await runBackground(job, () => stopped)
    }
  }
  const cancelScheduled = schedule(() => { if (!stopped) { void worker(); void worker() } })
  return () => { stopped = true; cancelScheduled(); drainBackgroundQueue() }
}
