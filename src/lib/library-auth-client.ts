"use client"

import { useEffect, useSyncExternalStore } from 'react'

export interface LibraryAuthSnapshot {
  status: 'loading' | 'anonymous' | 'authenticated'
  user?: { phone: string }
  expiresAt?: number
}

type Fetcher = (url: string, init: RequestInit) => Promise<Response>
const INITIAL_SNAPSHOT: LibraryAuthSnapshot = { status: 'loading' }
const RESET_EVENT = 'weibull:library-session-reset'
const REQUIRED_EVENT = 'weibull:library-auth-required'

export function createLibraryAuthClient(options: {
  fetcher?: Fetcher
  onReset?: () => void
} = {}) {
  const fetcher = options.fetcher ?? ((url, init) => fetch(url, init))
  let snapshot = INITIAL_SNAPSHOT
  let revision = 0
  let pending: Promise<LibraryAuthSnapshot> | undefined
  let pendingLogout: Promise<void> | undefined
  let expiryTimer: ReturnType<typeof setTimeout> | undefined
  const listeners = new Set<() => void>()

  function publish(next: LibraryAuthSnapshot) {
    if (expiryTimer) clearTimeout(expiryTimer)
    if (next.status === 'authenticated' && next.expiresAt) {
      expiryTimer = setTimeout(() => invalidate(), Math.max(0, Math.min(next.expiresAt - Date.now(), 2 ** 31 - 1)))
      if (typeof expiryTimer === 'object' && 'unref' in expiryTimer) expiryTimer.unref()
    }
    if (next.status !== 'authenticated') options.onReset?.()
    snapshot = next
    listeners.forEach(listener => listener())
    return snapshot
  }

  function fromResponse(data: { authenticated?: boolean; user?: { phone: string }; expiresAt?: number }): LibraryAuthSnapshot {
    return data.authenticated ? { status: 'authenticated', user: data.user, expiresAt: data.expiresAt } : { status: 'anonymous' }
  }

  function invalidate() {
    revision++
    pending = undefined
    return publish({ status: 'anonymous' })
  }

  function refresh() {
    // The browser still has its old cookie until the logout response arrives.
    if (pendingLogout) return Promise.resolve(snapshot)
    if (pending) return pending
    const current = revision
    const request = fetcher('/api/auth/session', { cache: 'no-store', credentials: 'same-origin' })
      .then(async response => {
        if (!response.ok) throw new Error('暂时无法确认登录状态。')
        const data = await response.json()
        return current === revision ? publish(fromResponse(data)) : snapshot
      }).catch(() => current === revision ? publish({ status: 'anonymous' }) : snapshot)
      .finally(() => { if (pending === request) pending = undefined })
    pending = request
    return request
  }

  async function login(phone: string, password: string) {
    if (pendingLogout) await pendingLogout
    const current = ++revision
    pending = undefined
    const response = await fetcher('/api/auth/login', {
      method: 'POST', cache: 'no-store', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ phone, password }),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok || !data.authenticated) throw new Error(data.error || '暂时无法登录，请稍后重试。')
    if (current !== revision) return snapshot
    return publish(fromResponse(data))
  }

  function logout() {
    if (pendingLogout) return pendingLogout
    const request = Promise.resolve().then(async () => {
      const response = await fetcher('/api/auth/logout', { method: 'POST', cache: 'no-store', credentials: 'same-origin' })
      if (!response.ok) throw new Error('退出未完成，请重试。')
    }).finally(() => {
      invalidate()
      if (pendingLogout === request) pendingLogout = undefined
    })
    pendingLogout = request
    invalidate()
    return request
  }

  return {
    getSnapshot: () => snapshot,
    getServerSnapshot: () => INITIAL_SNAPSHOT,
    subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener) } },
    refresh, login, logout, invalidate,
  }
}

export const libraryAuthClient = createLibraryAuthClient({
  onReset: () => { if (typeof window !== 'undefined') window.dispatchEvent(new Event(RESET_EVENT)) },
})

export function useLibrarySession() {
  const snapshot = useSyncExternalStore(libraryAuthClient.subscribe, libraryAuthClient.getSnapshot, libraryAuthClient.getServerSnapshot)
  useEffect(() => { void libraryAuthClient.refresh() }, [])
  return snapshot
}

if (typeof window !== 'undefined') {
  window.addEventListener(REQUIRED_EVENT, () => libraryAuthClient.invalidate())
  window.addEventListener('focus', () => { void libraryAuthClient.refresh() })
}
