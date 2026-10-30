import test from 'node:test'
import assert from 'node:assert/strict'
import { createLibraryAuthClient } from '../../src/lib/library-auth-client.ts'

function deferred() {
  let resolve
  const promise = new Promise(done => { resolve = done })
  return { promise, resolve }
}
const json = value => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } })

test('session checks join one request and anonymous state discards user data', async () => {
  const gate = deferred()
  let calls = 0
  const auth = createLibraryAuthClient({ fetcher: () => { calls++; return gate.promise } })
  const session = auth.refresh()
  assert.equal(auth.refresh(), session)
  gate.resolve(json({ authenticated: false, user: { phone: 'untrusted' } }))
  assert.deepEqual(await session, { status: 'anonymous' })
  assert.equal(calls, 1)
})

test('login sends credentials only to the login endpoint and keeps only session data', async () => {
  const calls = []
  const auth = createLibraryAuthClient({ fetcher: async (url, init) => {
    calls.push({ url, init })
    return json({ authenticated: true, user: { phone: 'test-account' }, expiresAt: Date.now() + 60_000 })
  } })
  await auth.login('test-account', 'test-password')
  assert.equal(calls[0].url, '/api/auth/login')
  assert.deepEqual(JSON.parse(calls[0].init.body), { phone: 'test-account', password: 'test-password' })
  assert.equal(calls[0].init.credentials, 'same-origin')
  assert.equal(auth.getSnapshot().status, 'authenticated')
  assert.equal(JSON.stringify(auth.getSnapshot()).includes('test-password'), false)
})

test('a rejected login shows the server message without authenticating', async () => {
  const auth = createLibraryAuthClient({ fetcher: async () => new Response(JSON.stringify({ error: '手机号或密码不正确。' }), { status: 401 }) })
  await assert.rejects(auth.login('test', 'wrong'), /手机号或密码不正确/)
  assert.notEqual(auth.getSnapshot().status, 'authenticated')
})

test('logout resets access before the request finishes and an older session check cannot restore it', async () => {
  const sessionGate = deferred()
  const logoutGate = deferred()
  let resets = 0
  const auth = createLibraryAuthClient({ onReset: () => { resets++ }, fetcher: url => url.endsWith('/logout') ? logoutGate.promise : sessionGate.promise })
  const session = auth.refresh()
  const logout = auth.logout()
  assert.equal(auth.getSnapshot().status, 'anonymous')
  assert.equal(resets, 1)
  sessionGate.resolve(json({ authenticated: true, user: { phone: 'old-session' } }))
  await session
  assert.equal(auth.getSnapshot().status, 'anonymous')
  logoutGate.resolve(json({ authenticated: false }))
  await logout
})

test('an older session response cannot overwrite a successful login', async () => {
  const gate = deferred()
  const auth = createLibraryAuthClient({ fetcher: url => url.endsWith('/session') ? gate.promise : Promise.resolve(json({ authenticated: true, user: { phone: 'current' } })) })
  const old = auth.refresh()
  await auth.login('current', 'test')
  gate.resolve(json({ authenticated: false }))
  await old
  assert.equal(auth.getSnapshot().user.phone, 'current')
})

test('focus and mount session checks cannot restore the old cookie while logout is pending', async () => {
  const gate = deferred()
  let sessionCalls = 0
  let resets = 0
  let serverLoggedOut = false
  const auth = createLibraryAuthClient({ onReset: () => { resets++ }, fetcher: async url => {
    if (url.endsWith('/login')) return json({ authenticated: true, user: { phone: 'current' } })
    if (url.endsWith('/logout')) return gate.promise
    sessionCalls++
    return json({ authenticated: !serverLoggedOut, user: { phone: 'old-cookie' } })
  } })
  await auth.login('current', 'test')
  const logout = auth.logout()
  assert.equal(auth.logout(), logout)
  assert.equal((await auth.refresh()).status, 'anonymous')
  assert.equal((await auth.refresh()).status, 'anonymous')
  assert.equal(sessionCalls, 0)
  serverLoggedOut = true
  gate.resolve(json({ authenticated: false }))
  await logout
  assert.equal(auth.getSnapshot().status, 'anonymous')
  assert.equal(resets, 2)
  assert.equal((await auth.refresh()).status, 'anonymous')
  assert.equal(sessionCalls, 1)
})

test('a new login waits for the previous logout cookie response', async () => {
  const gate = deferred()
  const calls = []
  const auth = createLibraryAuthClient({ fetcher: async url => {
    calls.push(url)
    return url.endsWith('/logout') ? gate.promise : json({ authenticated: true, user: { phone: 'new-session' } })
  } })
  const logout = auth.logout()
  const login = auth.login('new-session', 'test')
  await Promise.resolve()
  assert.deepEqual(calls, ['/api/auth/logout'])
  gate.resolve(json({ authenticated: false }))
  await logout
  await login
  assert.deepEqual(calls, ['/api/auth/logout', '/api/auth/login'])
  assert.equal(auth.getSnapshot().user.phone, 'new-session')
})

test('session expiry revokes access and notifies cache reset listeners', async () => {
  let resets = 0
  const auth = createLibraryAuthClient({ onReset: () => { resets++ }, fetcher: async () => json({ authenticated: true, expiresAt: Date.now() + 15 }) })
  await auth.refresh()
  assert.equal(auth.getSnapshot().status, 'authenticated')
  await new Promise(resolve => setTimeout(resolve, 40))
  assert.equal(auth.getSnapshot().status, 'anonymous')
  assert.equal(resets, 1)
})
