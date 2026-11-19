import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, rmSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { DatabaseSync } from 'node:sqlite'
import { loadServerModule } from './helpers/load-server-module.mjs'

const site = 'https://library.example'
const owner = '18800000000'
const reader = '19900000000'

test('SMS verification registers once, isolates collections, preserves the legacy SQLite identity and revokes logout', async t => {
  const directory = mkdtempSync(path.join(os.tmpdir(), 'weibull-sms-test-'))
  let db
  t.after(() => {
    db?.close()
    rmSync(directory, { recursive: true, force: true })
  })
  for (const [name, value] of Object.entries({
    WEIBULL_LIBRARY_AUTH_MODE: 'sms', WEIBULL_LIBRARY_PHONE: owner, WEIBULL_LIBRARY_ACCOUNT_ID: 'library-owner',
    WEIBULL_FAVORITES_DIR: directory, WEIBULL_FAVORITES_STORAGE: 'sqlite',
    WEIBULL_SESSION_SECRET: 'test-only-signing-secret-for-sms-fixture',
    WEIBULL_SMS_ACCESS_KEY_ID: 'sample-key', WEIBULL_SMS_ACCESS_KEY_SECRET: 'sample-secret',
    WEIBULL_SMS_SIGN_NAME: '测试', WEIBULL_SMS_TEMPLATE_CODE: 'sample-template',
  })) {
    const old = process.env[name]
    process.env[name] = value
    t.after(() => { if (old === undefined) delete process.env[name]; else process.env[name] = old })
  }

  const sent = new Map()
  const auth = loadServerModule('src/lib/server/library-auth.ts', {}, {
    Request, Response, URLSearchParams,
    fetch: async (url, init) => {
      const endpoint = new URL(url)
      assert.equal(endpoint.origin, 'https://dypnsapi.aliyuncs.com')
      assert.equal(init.method, 'POST')
      assert.equal(init.headers['x-acs-action'], 'SendSmsVerifyCode')
      assert.match(init.headers.Authorization, /^ACS3-HMAC-SHA256 Credential=sample-key,.+Signature=[a-f0-9]{64}$/)
      const { code } = JSON.parse(endpoint.searchParams.get('TemplateParam'))
      assert.match(code, /^\d{6}$/)
      sent.set(endpoint.searchParams.get('PhoneNumber'), code)
      return Response.json({ Code: 'OK', Success: true })
    },
  })
  const favorites = loadServerModule('src/lib/server/library-favorites.ts')
  const makeFolder = name => ({ action: 'create', name, paperIds: [] })
  await favorites.updateLibraryFavorites(owner, makeFolder('原有收藏'))

  function post(action, fields, headers = {}) {
    return new Request(`${site}/api/auth/${action}`, {
      method: 'POST', headers: { Origin: site, 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(fields),
    })
  }
  const withSession = response => new Request(site, { headers: { Cookie: response.headers.get('set-cookie').split(';')[0] } })
  const logIn = (phone, code = sent.get(phone)) => auth.loginLibrary(post('login', { phone, code }))

  assert.equal((await auth.sendLibraryLoginCode(post('code', { phone: owner }, { Origin: 'https://elsewhere.example' }))).status, 403)
  assert.equal((await logIn(owner, '012345')).status, 401)
  assert.equal((await auth.loginLibrary(post('login', { phone: owner, password: 'old-form' }))).status, 400)
  assert.equal((await auth.sendLibraryLoginCode(post('code', { phone: `+86${owner}` }))).status, 200)
  assert.equal((await auth.sendLibraryLoginCode(post('code', { phone: owner }))).status, 429)
  db = new DatabaseSync(path.join(directory, 'library-favorites.sqlite3'))
  assert.equal(db.prepare('SELECT COUNT(*) AS count FROM library_phone_users').get().count, 0)
  const ownerLogins = await Promise.all([logIn(owner), logIn(owner)])
  assert.deepEqual(ownerLogins.map(response => response.status).sort(), [200, 401])
  const owned = withSession(ownerLogins.find(response => response.ok))
  assert.equal(auth.requireLibraryLogin(owned), null)
  const ownerSession = auth.getLibrarySession(owned)
  const sessionJson = await auth.librarySessionResponse(owned).json()
  assert.equal(sessionJson.loginMode, 'sms')
  assert.equal(sessionJson.legacyAccountId, undefined)
  assert.equal((await favorites.readLibraryFavorites(owner, ownerSession.legacyAccountId))[0].name, '原有收藏')

  assert.equal((await auth.sendLibraryLoginCode(post('code', { phone: reader }))).status, 200)
  const invalid = sent.get(reader) === '000000' ? '000001' : '000000'
  for (let index = 0; index < 5; index++) assert.equal((await logIn(reader, invalid)).status, 401)
  assert.equal((await logIn(reader)).status, 401)
  db.prepare('UPDATE library_sms_requests SET requested_at = ? WHERE phone = ?').run(Date.now() - 301_000, reader)
  assert.equal((await logIn(reader)).status, 401)
  assert.equal((await auth.sendLibraryLoginCode(post('code', { phone: reader }))).status, 200)
  const readerLogin = await logIn(reader)
  assert.equal(readerLogin.status, 200)
  assert.match(readerLogin.headers.get('set-cookie'), /HttpOnly.*Secure/)
  const reading = withSession(readerLogin)
  assert.equal(auth.requireLibraryLogin(reading).status, 403)
  const readerSession = auth.getLibrarySession(reading)
  assert.equal(readerSession.legacyAccountId, null)
  assert.equal((await favorites.readLibraryFavorites(reader, readerSession.legacyAccountId)).length, 0)
  await favorites.updateLibraryFavorites(reader, makeFolder('自建主题'), readerSession.legacyAccountId)
  assert.equal((await favorites.readLibraryFavorites(owner, ownerSession.legacyAccountId)).length, 1)
  assert.equal(auth.logoutLibrary(post('logout', {}, { Cookie: reading.headers.get('cookie') })).status, 200)
  assert.equal(auth.getLibrarySession(reading).authenticated, false)
  db.prepare('UPDATE library_sms_requests SET requested_at = ? WHERE phone = ?').run(Date.now() - 301_000, reader)
  assert.equal((await auth.sendLibraryLoginCode(post('code', { phone: reader }))).status, 200)
  const next = withSession(await logIn(`86${reader}`, sent.get(reader)))
  assert.equal(db.prepare('SELECT COUNT(*) AS count FROM library_phone_users WHERE phone = ?').get(reader).count, 1)
  assert.equal((await favorites.readLibraryFavorites(reader, auth.getLibrarySession(next).legacyAccountId))[0].name, '自建主题')
})
