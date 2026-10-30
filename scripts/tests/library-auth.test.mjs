import test from 'node:test'
import assert from 'node:assert/strict'
import { scryptSync } from 'node:crypto'
import { loadServerModule } from './helpers/load-server-module.mjs'

const phone = '18800000000'
const password = 'test-password-only'
const salt = '0123456789abcdef0123456789abcdef'
const passwordHash = `scrypt:${salt}:${scryptSync(password, salt, 64).toString('hex')}`
const envNames = ['WEIBULL_LIBRARY_PHONE', 'WEIBULL_LIBRARY_PASSWORD_HASH', 'WEIBULL_SESSION_SECRET']
const globals = { Request, Response }

async function withAuth(run) {
  const saved = envNames.map(name => process.env[name])
  process.env.WEIBULL_LIBRARY_PHONE = phone
  process.env.WEIBULL_LIBRARY_PASSWORD_HASH = passwordHash
  process.env.WEIBULL_SESSION_SECRET = 'test-signing-secret-is-at-least-32-characters'
  try { await run(loadServerModule('src/lib/server/library-auth.ts', {}, globals)) }
  finally { envNames.forEach((name, index) => { if (saved[index] === undefined) delete process.env[name]; else process.env[name] = saved[index] }) }
}

function loginRequest(fields = { phone, password }, headers = {}) {
  return new Request('http://localhost:3000/api/auth/login', { method: 'POST',
    headers: { 'Content-Type': 'application/json', Origin: 'http://localhost:3000', ...headers }, body: JSON.stringify(fields) })
}

function requestWithCookie(cookie, url = 'http://localhost:3000/api/content?slug=182-001&type=原文') {
  return new Request(url, { headers: { Cookie: cookie.split(';')[0] } })
}

test('the configured account gets a seven-day HttpOnly session; altered, expired and rotated credentials fail closed', () => withAuth(async auth => {
  assert.equal(auth.getLibrarySession(new Request('http://localhost:3000')).authenticated, false)
  const response = await auth.loginLibrary(loginRequest())
  assert.equal(response.status, 200)
  const data = await response.json()
  assert.equal(data.authenticated, true)
  assert.deepEqual(data.user, { phone })
  const cookie = response.headers.get('set-cookie')
  assert.match(cookie, /HttpOnly/)
  assert.match(cookie, /SameSite=Lax/)
  assert.match(cookie, /Max-Age=604800/)
  assert.doesNotMatch(cookie, /Secure/)
  assert.match(response.headers.get('cache-control'), /no-store/)
  assert.equal(auth.getLibrarySession(requestWithCookie(cookie)).authenticated, true)
  assert.equal(auth.getLibrarySession(requestWithCookie(cookie), data.expiresAt).authenticated, false)
  const token = cookie.split(';')[0]
  const tampered = token.slice(0, -1) + (token.endsWith('A') ? 'B' : 'A')
  assert.equal(auth.getLibrarySession(requestWithCookie(tampered)).authenticated, false)
  process.env.WEIBULL_LIBRARY_PASSWORD_HASH = `scrypt:${salt}:${'0'.repeat(128)}`
  assert.equal(auth.getLibrarySession(requestWithCookie(cookie)).authenticated, false)
}))

test('login rejects other accounts, cross-origin writes, missing configuration and repeated failures', () => withAuth(async auth => {
  assert.equal((await auth.loginLibrary(loginRequest({ phone: '19900000000', password }))).status, 401)
  assert.equal((await auth.loginLibrary(loginRequest({ phone, password: 'wrong' }, { Origin: 'https://elsewhere.example' }))).status, 403)
  for (let index = 0; index < 6; index++) {
    assert.equal((await auth.loginLibrary(loginRequest({ phone, password: 'wrong' }, { 'cf-connecting-ip': 'rate-test' }))).status, 401)
  }
  const limited = await auth.loginLibrary(loginRequest(undefined, { 'cf-connecting-ip': 'rate-test' }))
  assert.equal(limited.status, 429)
  assert.ok(Number(limited.headers.get('retry-after')) > 0)
  delete process.env.WEIBULL_SESSION_SECRET
  assert.equal((await auth.loginLibrary(loginRequest())).status, 503)
  assert.equal(auth.getLibrarySession(new Request('http://localhost:3000')).authenticated, false)
}))

test('HTTPS sessions are Secure and logout clears the cookie only on the same origin', () => withAuth(async auth => {
  const response = await auth.loginLibrary(new Request('https://weibull.example/api/auth/login', { method: 'POST',
    headers: { Origin: 'https://weibull.example', 'Content-Type': 'application/json' }, body: JSON.stringify({ phone, password }) }))
  assert.equal(response.status, 200)
  assert.match(response.headers.get('set-cookie'), /; Secure/)
  const denied = auth.logoutLibrary(new Request('https://weibull.example/api/auth/logout', { method: 'POST', headers: { Origin: 'https://elsewhere.example' } }))
  assert.equal(denied.status, 403)
  const logout = auth.logoutLibrary(new Request('https://weibull.example/api/auth/logout', { method: 'POST', headers: { Origin: 'https://weibull.example' } }))
  assert.equal(logout.status, 200)
  assert.match(logout.headers.get('set-cookie'), /Max-Age=0/)
  assert.deepEqual(await logout.json(), { authenticated: false })
}))

test('raw original and translated content reject unauthenticated reads before consulting library storage', () => withAuth(async () => {
  const unreadableLibrary = new Proxy({}, { get() { throw new Error('Storage must not be read') } })
  const content = loadServerModule('src/app/api/content/route.ts', { '@/lib/server/literature': unreadableLibrary }, globals)
  for (const version of ['原文', '翻译']) {
    const response = await content.GET(new Request(`http://localhost:3000/api/content?slug=182-001&type=${version}`))
    assert.equal(response.status, 401)
    assert.equal((await response.json()).code, 'AUTH_REQUIRED')
    assert.match(response.headers.get('cache-control'), /no-store/)
  }
}))

test('figure and reference handlers remain public without a session', async () => {
  const publicLibrary = {
    readReferences: () => ({ 1: '182-002' }),
    resolveLibraryAsset: () => ({ path: 'public-fixture.png', contentType: 'image/png' }),
    LibraryConfigurationError: class extends Error {},
  }
  const references = loadServerModule('src/app/api/library/references/route.ts', { '@/lib/server/literature': publicLibrary }, globals)
  const assets = loadServerModule('src/app/api/library/assets/[...segments]/route.ts', {
    '@/lib/server/literature': publicLibrary, fs: { readFileSync: () => Buffer.from('public-image') },
  }, globals)
  const referenceRequest = new Request('http://localhost:3000/api/library/references?slug=182-001&type=原文')
  referenceRequest.nextUrl = new URL(referenceRequest.url)
  const referenceResponse = await references.GET(referenceRequest)
  assert.equal(referenceResponse.status, 200)
  assert.deepEqual(await referenceResponse.json(), { 1: '182-002' })
  const imageResponse = await assets.GET(new Request('http://localhost:3000/api/library/assets/182-001-图片/images/a.png'),
    { params: { segments: ['182-001-图片', 'images', 'a.png'] } })
  assert.equal(imageResponse.status, 200)
  assert.equal(await imageResponse.text(), 'public-image')
})

test('authenticated content reads retain body and private cache headers', () => withAuth(async auth => {
  const response = await auth.loginLibrary(loginRequest())
  const content = loadServerModule('src/app/api/content/route.ts', { '@/lib/server/literature': {
    readPaper: () => 'ORIGINAL_BODY', LibraryConfigurationError: class extends Error {},
  } }, globals)
  const result = await content.GET(requestWithCookie(response.headers.get('set-cookie')))
  assert.equal(result.status, 200)
  assert.equal(await result.text(), 'ORIGINAL_BODY')
  assert.equal(result.headers.get('cache-control'), 'private, no-store')
  assert.equal(result.headers.get('vary'), 'Cookie')
}))

test('public metadata and search expose introductions and excerpts without raw source or neighbouring context', async () => {
  const paper = { slug: '182-001', title: 'Selected paper', author: 'Author', year: 2024, tags: [], summary: 'Public introduction', privateNotes: 'PRIVATE_NOTES' }
  const metadata = loadServerModule('src/app/api/library/papers/[slug]/route.ts', { '@/lib/server/literature': {
    readLibraryDocuments: () => [{ paper, version: '原文', raw: 'COMPLETE_DOCUMENT' }, { paper, version: '翻译', raw: 'TRANSLATION_DOCUMENT' }],
    getLibraryPaths: () => ({ mode: 'source' }), LibraryConfigurationError: class extends Error {},
  } }, globals)
  const response = await metadata.GET(new Request('http://localhost:3000/api/library/papers/182-001'), { params: { slug: '182-001' } })
  assert.equal(response.status, 200)
  const body = await response.json()
  assert.deepEqual(body.versions, ['原文', '翻译'])
  assert.equal(body.paper.summary, 'Public introduction')
  assert.doesNotMatch(JSON.stringify(body), /COMPLETE_DOCUMENT|TRANSLATION_DOCUMENT|PRIVATE_NOTES|raw/)

  const search = loadServerModule('src/app/api/library/search/route.ts', {
    '@/lib/server/library-search': { searchLibrary: () => ({ query: 'weibull', total: 1, terms: ['weibull'], results: [{
      id: 'one', slug: '182-001', title: 'Selected paper', version: '原文', excerpt: 'Visible Weibull excerpt',
      text: 'COMPLETE_PASSAGE', context: 'NEIGHBOUR_CONTEXT', contextStartLine: 1, contextEndLine: 30,
    }] }) },
    '@/lib/server/literature': { LibraryConfigurationError: class extends Error {} },
  }, globals)
  const searchRequest = new Request('http://localhost:3000/api/library/search?q=weibull')
  searchRequest.nextUrl = new URL(searchRequest.url)
  const searchResponse = await search.GET(searchRequest)
  const searchBody = await searchResponse.json()
  assert.equal(searchResponse.status, 200)
  assert.equal(searchBody.results[0].excerpt, 'Visible Weibull excerpt')
  assert.doesNotMatch(JSON.stringify(searchBody), /COMPLETE_PASSAGE|NEIGHBOUR_CONTEXT|contextStartLine|contextEndLine/)
})
