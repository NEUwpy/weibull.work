import test from 'node:test'
import assert from 'node:assert/strict'
import { scryptSync } from 'node:crypto'
import { mkdtempSync, rmSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { DatabaseSync } from 'node:sqlite'
import { loadServerModule } from './helpers/load-server-module.mjs'

const site = 'https://library.example'
const owner = '18800000000'
const reader = '19900000000'
const earlierReader = '17700000000'
const newReader = '16600000000'
const opensAt = Date.parse('2026-12-01T09:00:00+08:00')
const closesAt = opensAt + 10 * 60_000
const ownerPassword = 'previous-owner-password'
const readerPassword = '可靠性图书馆 long passphrase'

test('scheduled registration creates one account for both login methods and preserves earlier accounts', async t => {
  const directory = mkdtempSync(path.join(os.tmpdir(), 'weibull-sms-test-'))
  const db = new DatabaseSync(path.join(directory, 'library-favorites.sqlite3'))
  t.after(() => {
    db.close()
    rmSync(directory, { recursive: true, force: true })
  })
  const salt = '0123456789abcdef0123456789abcdef'
  for (const [name, value] of Object.entries({
    WEIBULL_LIBRARY_AUTH_MODE: undefined, WEIBULL_LIBRARY_PHONE: owner, WEIBULL_LIBRARY_ACCOUNT_ID: 'library-owner',
    WEIBULL_LIBRARY_PASSWORD_HASH: `scrypt:${salt}:${scryptSync(ownerPassword, salt, 64).toString('hex')}`,
    WEIBULL_LIBRARY_REGISTRATION_OPENS_AT: undefined, WEIBULL_LIBRARY_REGISTRATION_CLOSES_AT: undefined,
    WEIBULL_FAVORITES_DIR: directory, WEIBULL_FAVORITES_STORAGE: 'sqlite',
    WEIBULL_SESSION_SECRET: 'test-only-signing-secret-for-sms-fixture',
    WEIBULL_SMS_ACCESS_KEY_ID: 'sample-key', WEIBULL_SMS_ACCESS_KEY_SECRET: 'sample-secret',
    WEIBULL_SMS_SIGN_NAME: '测试', WEIBULL_SMS_TEMPLATE_CODE: 'sample-template',
  })) {
    const old = process.env[name]
    if (value === undefined) delete process.env[name]; else process.env[name] = value
    t.after(() => { if (old === undefined) delete process.env[name]; else process.env[name] = old })
  }

  db.exec(`
    CREATE TABLE library_phone_users (phone TEXT PRIMARY KEY NOT NULL, legacy_account_id TEXT UNIQUE, created_at INTEGER NOT NULL) STRICT;
    CREATE TABLE library_sms_requests (id TEXT PRIMARY KEY NOT NULL, phone TEXT NOT NULL, source TEXT NOT NULL, requested_at INTEGER NOT NULL, digest TEXT, attempts INTEGER NOT NULL DEFAULT 0) STRICT;
  `)
  db.prepare('INSERT INTO library_phone_users (phone, created_at) VALUES (?, ?)').run(earlierReader, opensAt - 60_000)

  const sent = new Map()
  let now = opensAt - 1
  class TestDate extends Date { static now() { return now } }
  const auth = loadServerModule('src/lib/server/library-auth.ts', {}, {
    Request, Response, URLSearchParams, Date: TestDate,
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
  const sendCode = (phone, purpose = 'login') => auth.sendLibraryLoginCode(post('code', { phone, purpose }))
  const logIn = (phone, code = sent.get(phone)) => auth.loginLibrary(post('login', { phone, code }))
  const logInWithPassword = (phone, password) => auth.loginLibrary(post('login', { phone, password }))
  const register = (phone, code = sent.get(phone), password = readerPassword, headers) => auth.registerLibrary(post('register', { phone, code, password }, headers))
  const session = () => auth.librarySessionResponse(new Request(site)).json()

  assert.equal((await session()).loginMode, 'sms')
  assert.equal((await session()).registrationWindow, null)
  assert.equal((await sendCode(reader, 'register')).status, 403)
  assert.equal((await register(reader, '123456')).status, 403)
  assert.equal((await sendCode(reader)).status, 200)
  assert.equal(sent.has(reader), false)
  assert.equal((await logIn(reader, '123456')).status, 401)
  assert.equal((await logInWithPassword(reader, readerPassword)).status, 401)
  assert.equal((await auth.sendLibraryLoginCode(post('code', { phone: owner }, { Origin: 'https://elsewhere.example' }))).status, 403)
  const ownerByPassword = withSession(await logInWithPassword(owner, ownerPassword))
  assert.equal(auth.requireLibraryLogin(ownerByPassword), null)
  const ownerSession = auth.getLibrarySession(ownerByPassword)
  assert.equal((await favorites.readLibraryFavorites(owner, ownerSession.legacyAccountId))[0].name, '原有收藏')
  assert.equal((await sendCode(`+86${owner}`)).status, 200)
  assert.equal((await sendCode(owner)).status, 429)
  const ownerLogins = await Promise.all([logIn(owner), logIn(owner)])
  assert.deepEqual(ownerLogins.map(response => response.status).sort(), [200, 401])
  const ownerByCode = withSession(ownerLogins.find(response => response.ok))
  assert.equal(auth.getLibrarySession(ownerByCode).legacyAccountId, ownerSession.legacyAccountId)
  assert.equal((await auth.librarySessionResponse(ownerByCode).json()).legacyAccountId, undefined)
  assert.equal((await sendCode(earlierReader)).status, 200)
  assert.equal((await logIn(earlierReader)).status, 200)

  process.env.WEIBULL_LIBRARY_REGISTRATION_OPENS_AT = '2026-02-30T09:00:00+08:00'
  process.env.WEIBULL_LIBRARY_REGISTRATION_CLOSES_AT = new Date(closesAt).toISOString().replace('.000Z', 'Z')
  assert.equal((await session()).registrationWindow, null)
  process.env.WEIBULL_LIBRARY_REGISTRATION_OPENS_AT = '2026-12-01T09:00:00+08:00'
  assert.deepEqual((await session()).registrationWindow, { opensAt, closesAt })
  assert.equal((await sendCode(reader, 'register')).status, 403)
  now = opensAt
  assert.equal((await sendCode(reader, 'register')).status, 200)
  assert.equal((await logIn(reader)).status, 401)
  assert.equal((await register(reader, sent.get(reader), 'too-short')).status, 400)
  const invalid = sent.get(reader) === '000000' ? '000001' : '000000'
  for (let index = 0; index < 5; index++) {
    assert.equal((await register(reader, invalid, readerPassword, { 'cf-connecting-ip': 'bad-code-test' })).status, 401)
  }
  assert.equal((await register(reader)).status, 401)
  now += 301_000
  assert.equal((await register(reader)).status, 401)
  assert.equal((await sendCode(reader, 'register')).status, 200)
  const registrations = await Promise.all([register(reader), register(reader)])
  assert.deepEqual(registrations.map(response => response.status).sort(), [200, 401])
  const readerLogin = registrations.find(response => response.ok)
  assert.match(readerLogin.headers.get('set-cookie'), /HttpOnly.*Secure/)
  const reading = withSession(readerLogin)
  assert.equal(auth.requireLibraryLogin(reading).status, 403)
  const readerSession = auth.getLibrarySession(reading)
  assert.equal(readerSession.legacyAccountId, null)
  assert.match(db.prepare('SELECT password_hash FROM library_phone_users WHERE phone = ?').get(reader).password_hash, /^scrypt:[a-f0-9]{32}:[a-f0-9]{128}$/)
  assert.equal((await favorites.readLibraryFavorites(reader, readerSession.legacyAccountId)).length, 0)
  await favorites.updateLibraryFavorites(reader, makeFolder('自建主题'), readerSession.legacyAccountId)
  assert.equal((await favorites.readLibraryFavorites(owner, ownerSession.legacyAccountId)).length, 1)
  assert.equal(auth.logoutLibrary(post('logout', {}, { Cookie: reading.headers.get('cookie') })).status, 200)
  assert.equal(auth.getLibrarySession(reading).authenticated, false)

  now = closesAt - 1
  assert.equal((await sendCode(newReader, 'register')).status, 200)
  now = closesAt
  assert.equal((await sendCode(newReader, 'register')).status, 403)
  assert.equal((await register(newReader)).status, 403)
  assert.equal((await logIn(newReader)).status, 401)
  assert.equal((await logInWithPassword(reader, 'incorrect password')).status, 401)
  const passwordSession = withSession(await logInWithPassword(`+86${reader}`, readerPassword))
  assert.equal(auth.getLibrarySession(passwordSession).user.phone, reader)
  assert.equal((await favorites.readLibraryFavorites(reader, auth.getLibrarySession(passwordSession).legacyAccountId))[0].name, '自建主题')
  assert.equal(auth.logoutLibrary(post('logout', {}, { Cookie: passwordSession.headers.get('cookie') })).status, 200)
  assert.equal(auth.getLibrarySession(passwordSession).authenticated, false)
  assert.equal((await sendCode(reader)).status, 200)
  const next = withSession(await logIn(`86${reader}`, sent.get(reader)))
  assert.equal(db.prepare('SELECT COUNT(*) AS count FROM library_phone_users WHERE phone = ?').get(reader).count, 1)
  assert.equal((await favorites.readLibraryFavorites(reader, auth.getLibrarySession(next).legacyAccountId))[0].name, '自建主题')
})
