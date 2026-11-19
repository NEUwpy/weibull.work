import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { createHash, scryptSync } from 'node:crypto'
import os from 'node:os'
import path from 'node:path'
import { loadServerModule } from './helpers/load-server-module.mjs'

function favoritesEnvironment(t, settings = {}) {
  const directory = mkdtempSync(path.join(os.tmpdir(), 'weibull-favorites-'))
  const environment = {
    WEIBULL_FAVORITES_DIR: directory,
    WEIBULL_FAVORITES_STORAGE: '',
    WEIBULL_LIBRARY_ACCOUNT_ID: '',
    ...settings,
  }
  const before = Object.fromEntries(Object.keys(environment).map(key => [key, process.env[key]]))
  Object.assign(process.env, environment)
  t.after(() => {
    for (const [key, value] of Object.entries(before)) {
      if (value === undefined) delete process.env[key]
      else process.env[key] = value
    }
    rmSync(directory, { recursive: true, force: true })
  })
  return directory
}

async function checkFavorites(t, mode) {
  const origin = 'http://localhost:3000'
  const phone = '18800000000'
  const password = 'fixture-password'
  const salt = '0123456789abcdef0123456789abcdef'
  const directory = favoritesEnvironment(t, {
    WEIBULL_FAVORITES_STORAGE: mode,
    WEIBULL_LIBRARY_PHONE: phone,
    WEIBULL_LIBRARY_PASSWORD_HASH: `scrypt:${salt}:${scryptSync(password, salt, 64).toString('hex')}`,
    WEIBULL_SESSION_SECRET: 'temporary-signing-fixture-at-least-32-characters',
  })

  const auth = loadServerModule('src/lib/server/library-auth.ts', {}, { Response })
  const loadRoute = () => loadServerModule('src/app/api/library/favorites/route.ts', {
    '@/lib/server/library-auth': auth,
    '@/lib/server/literature': { readPaperMetadata(id) {
      if (['182-001', '182-002', '182-003'].includes(id)) return { slug: id, type: '期刊' }
      if (id === '400-001') return { slug: id, type: '书籍' }
      return null
    } },
  }, { Response })
  async function login(phone) {
    const response = await auth.loginLibrary(new Request(`${origin}/api/auth/login`, {
      method: 'POST', headers: { Origin: origin, 'Content-Type': 'application/json' }, body: JSON.stringify({ phone, password }),
    }))
    assert.equal(response.status, 200)
    return response.headers.get('set-cookie').split(';')[0]
  }

  let route = loadRoute()
  const url = `${origin}/api/library/favorites`
  const get = cookie => route.GET(new Request(url, { headers: cookie ? { Cookie: cookie } : {} }))
  const post = (cookie, body, source = origin) => route.POST(new Request(url, {
    method: 'POST', headers: { Cookie: cookie, Origin: source, 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }))
  assert.equal((await get()).status, 401)
  const cookie = await login(phone)
  const initial = await get(cookie)
  assert.equal(initial.headers.get('cache-control'), 'private, no-store')
  assert.deepEqual((await initial.json()).folders, [])

  const missing = { action: 'add', folderId: 'default', paperIds: ['182-001'] }
  assert.equal((await post(cookie, missing)).status, 404)
  const first = await (await post(cookie, { action: 'create', name: '按用途整理', paperIds: [] })).json()
  const folderId = first.folder.id
  const add = { action: 'add', folderId, paperIds: ['182-001', '182-002'] }
  assert.equal((await post('', add)).status, 401)
  assert.equal((await post(cookie, add, 'https://elsewhere.example')).status, 403)
  assert.equal((await post(cookie, { ...add, paperIds: ['182-001', '400-001'] })).status, 400)
  assert.deepEqual((await (await get(cookie)).json()).folders[0].paperIds, [])

  const [saved, second] = await Promise.all([
    post(cookie, add), post(cookie, { ...add, paperIds: ['182-002', '182-003', '182-003'] }),
  ])
  assert.equal(saved.status, 200)
  assert.equal(second.status, 200)
  assert.equal((await (await post(cookie, add)).json()).changed, 0)

  const create = { action: 'create', name: ' 小样本研究 ', paperIds: ['182-001', '182-002'] }
  const created = await (await post(cookie, create)).json()
  const retry = await (await post(cookie, create)).json()
  assert.equal(retry.folder.id, created.folder.id)
  assert.equal(retry.changed, 0)
  assert.equal(retry.folder.name, '小样本研究')
  const removed = await (await post(cookie, { action: 'remove', folderId: created.folder.id, paperIds: ['182-001'] })).json()
  assert.deepEqual(removed.folder.paperIds, ['182-002'])

  route = loadRoute()
  const restored = (await (await get(cookie)).json()).folders
  assert.deepEqual(restored[0].paperIds.sort(), ['182-001', '182-002', '182-003'])
  assert.deepEqual(restored[1].paperIds, ['182-002'])

  const recommendations = { ...add, relations: { '182-001': 'principle', '182-002': 'method-transfer' } }
  const classified = await (await post(cookie, recommendations)).json()
  const [principle, transfer] = classified.folder.subfolders
  assert.deepEqual([principle.name, transfer.name], ['原理依据', '方法借鉴'])
  assert.equal(classified.changed, 2)
  assert.deepEqual(classified.folder.paperSubfolders, { '182-001': principle.id, '182-002': transfer.id })

  const custom = await (await post(cookie, { action: 'create-subfolder', folderId, name: '读书笔记' })).json()
  const customId = custom.folder.subfolders.find(child => child.name === '读书笔记').id
  const move = { action: 'move', folderId, paperIds: ['182-001'], subfolderId: customId }
  assert.equal((await post(cookie, { ...move, folderId: created.folder.id })).status, 404)
  assert.equal((await (await post(cookie, move)).json()).changed, 1)
  assert.equal((await (await post(cookie, { ...move, paperIds: ['182-009'] })).json()).changed, 0)
  assert.equal((await (await post(cookie, recommendations)).json()).changed, 0)
  route = loadRoute()
  const afterMove = (await (await get(cookie)).json()).folders[0]
  assert.equal(afterMove.paperSubfolders['182-001'], customId)
  assert.deepEqual(afterMove.paperIds.sort(), ['182-001', '182-002', '182-003'])

  const unfiled = await (await post(cookie, { ...move, subfolderId: undefined })).json()
  assert.equal(unfiled.folder.paperSubfolders['182-001'], undefined)
  assert.ok(unfiled.folder.paperIds.includes('182-001'))
  const cleaned = await (await post(cookie, { action: 'remove', folderId, paperIds: ['182-002'] })).json()
  assert.equal(cleaned.folder.paperSubfolders, undefined)
  assert.equal(cleaned.folder.subfolders.length, 3)

  const otherPhone = '19900000000'
  process.env.WEIBULL_LIBRARY_PHONE = otherPhone
  assert.equal((await get(cookie)).status, 401)
  const otherCookie = await login(otherPhone)
  const other = (await (await get(otherCookie)).json()).folders
  assert.deepEqual(other, [])
  assert.equal((await post(otherCookie, { ...add, folderId: created.folder.id })).status, 404)
  const stored = readdirSync(directory)
  assert.equal(stored.length, 1)
  assert.match(stored[0], mode === 'sqlite' ? /^library-favorites\.sqlite3$/ : /^[a-f0-9]{64}\.json$/)
}

test('JSON folders are saved for the signed-in account and concurrent imports deduplicate', t => checkFavorites(t, ''))
test('SQLite folders are saved for the signed-in account and concurrent imports deduplicate', t => checkFavorites(t, 'sqlite'))

test('SQLite imports the old JSON collection as a regular folder and leaves the file intact', async t => {
  const directory = favoritesEnvironment(t, { WEIBULL_LIBRARY_ACCOUNT_ID: 'library-owner' })
  const phone = '18800000000'
  const replacement = '19900000000'
  const storage = loadServerModule('src/lib/server/library-favorites.ts')
  const { folder } = await storage.updateLibraryFavorites(phone, { action: 'create', name: '此前收藏', paperIds: ['182-002'] })
  const file = path.join(directory, readdirSync(directory)[0])
  const child = { id: '91ef54b2-d730-4252-b5b6-ec7317e4e258', name: '原理依据' }
  const old = { id: 'default', name: '我的收藏', paperIds: ['182-003', '182-001'], subfolders: [child], paperSubfolders: { '182-003': child.id } }
  writeFileSync(file, JSON.stringify({ version: 1, folders: [old, folder] }))
  const original = readFileSync(file, 'utf8')
  const folders = await storage.readLibraryFavorites(phone)
  assert.deepEqual(JSON.parse(JSON.stringify(folders)), [JSON.parse(JSON.stringify(folder)), { ...old, name: '此前收藏 2' }])

  process.env.WEIBULL_FAVORITES_STORAGE = 'sqlite'
  writeFileSync(file, '{invalid-json')
  await assert.rejects(storage.readLibraryFavorites(phone), /JSON/)
  writeFileSync(file, original)
  assert.deepEqual(JSON.parse(JSON.stringify(await storage.readLibraryFavorites(phone))), JSON.parse(JSON.stringify(folders)))
  assert.deepEqual(Array.from((await storage.readLibraryFavorites(replacement))[1].paperIds), ['182-003', '182-001'])

  await storage.updateLibraryFavorites(phone, { action: 'remove', folderId: folder.id, paperIds: ['182-002'] })
  const fresh = loadServerModule('src/lib/server/library-favorites.ts')
  assert.deepEqual(Array.from((await fresh.readLibraryFavorites(replacement))[0].paperIds), [])
  assert.equal(readFileSync(file, 'utf8'), original)

  process.env.WEIBULL_FAVORITES_STORAGE = 'json'
  assert.deepEqual(Array.from((await fresh.readLibraryFavorites(phone))[0].paperIds), ['182-002'])
})

test('a version-1 SQLite collection upgrades in place and can be organized afterwards', async t => {
  const { DatabaseSync } = await import('node:sqlite')
  const directory = favoritesEnvironment(t, { WEIBULL_FAVORITES_STORAGE: 'sqlite' })
  const phone = '18800000000'
  const otherPhone = '19900000000'
  const file = path.join(directory, 'library-favorites.sqlite3')
  const account = 'phone:' + createHash('sha256').update(phone).digest('hex')
  const otherAccount = 'phone:' + createHash('sha256').update(otherPhone).digest('hex')
  const legacy = new DatabaseSync(file)
  try {
    legacy.exec(`
      CREATE TABLE favorite_users (id TEXT PRIMARY KEY NOT NULL) STRICT;
      CREATE TABLE favorite_folders (
        user_id TEXT NOT NULL REFERENCES favorite_users(id), id TEXT NOT NULL, name TEXT NOT NULL, position INTEGER NOT NULL,
        PRIMARY KEY (user_id, id), UNIQUE (user_id, name)
      ) STRICT;
      CREATE TABLE favorite_papers (
        user_id TEXT NOT NULL, folder_id TEXT NOT NULL, paper_id TEXT NOT NULL, position INTEGER NOT NULL,
        PRIMARY KEY (user_id, folder_id, paper_id),
        FOREIGN KEY (user_id, folder_id) REFERENCES favorite_folders(user_id, id) ON DELETE CASCADE
      ) STRICT;
      PRAGMA user_version = 1;
    `)
    legacy.prepare('INSERT INTO favorite_users VALUES (?)').run(account)
    legacy.prepare('INSERT INTO favorite_folders VALUES (?, ?, ?, 0)').run(account, 'default', '我的收藏')
    legacy.prepare('INSERT INTO favorite_papers VALUES (?, ?, ?, 0)').run(account, 'default', '182-001')
    legacy.prepare('INSERT INTO favorite_users VALUES (?)').run(otherAccount)
    legacy.prepare('INSERT INTO favorite_folders VALUES (?, ?, ?, 0)').run(otherAccount, 'default', '我的收藏')
  } finally { legacy.close() }

  const storage = loadServerModule('src/lib/server/library-favorites.ts')
  assert.deepEqual(Array.from(await storage.readLibraryFavorites(otherPhone)), [])
  const initial = await storage.readLibraryFavorites(phone)
  assert.equal(initial[0].name, '此前收藏')
  assert.deepEqual(Array.from(initial[0].paperIds), ['182-001'])
  assert.equal(initial[0].paperSubfolders, undefined)
  const result = await storage.updateLibraryFavorites(phone, {
    action: 'add', folderId: 'default', paperIds: ['182-001'], relations: { '182-001': 'principle' },
  })
  assert.equal(result.folder.paperSubfolders['182-001'], result.folder.subfolders[0].id)
  const upgraded = new DatabaseSync(file, { readOnly: true })
  try {
    assert.equal(upgraded.prepare('PRAGMA user_version').get().user_version, 2)
    assert.equal(upgraded.prepare('SELECT name FROM favorite_folders WHERE user_id = ?').get(account).name, '此前收藏')
    assert.equal(upgraded.prepare('SELECT COUNT(*) AS count FROM favorite_folders WHERE user_id = ?').get(otherAccount).count, 0)
    assert.deepEqual(upgraded.prepare('PRAGMA foreign_key_check').all(), [])
  } finally { upgraded.close() }
})

test('JSON skips an empty legacy folder and does not recreate it on the next write', async t => {
  const directory = favoritesEnvironment(t)
  const phone = '18800000000'
  const file = path.join(directory, createHash('sha256').update(phone).digest('hex') + '.json')
  writeFileSync(file, JSON.stringify({ version: 1, folders: [{ id: 'default', name: '我的收藏', paperIds: [] }] }))
  const storage = loadServerModule('src/lib/server/library-favorites.ts')
  assert.deepEqual(Array.from(await storage.readLibraryFavorites(phone)), [])
  const created = await storage.updateLibraryFavorites(phone, { action: 'create', name: '自建主题', paperIds: [] })
  assert.deepEqual(JSON.parse(readFileSync(file, 'utf8')).folders.map(folder => folder.id), [created.folder.id])
})
