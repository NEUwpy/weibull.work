import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { existsSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { loadServerModule } from './helpers/load-server-module.mjs'

test('sync imports JSON, merges edits on both sites and protects concurrent or conflicting updates', async t => {
  const local = mkdtempSync(path.join(tmpdir(), 'weibull-favorites-local-'))
  const remote = mkdtempSync(path.join(tmpdir(), 'weibull-favorites-remote-'))
  const phone = '18800000000'
  const other = '19900000000'
  const peer = 'fixture-nas/weibull-frontend'
  const ownerKey = createHash('sha256').update(phone).digest('hex')
  const previous = new Map()
  function setEnv(name, value) {
    if (!previous.has(name)) previous.set(name, process.env[name])
    process.env[name] = value
  }
  t.after(() => {
    for (const [name, value] of previous) {
      if (value === undefined) delete process.env[name]
      else process.env[name] = value
    }
    rmSync(local, { recursive: true, force: true })
    rmSync(remote, { recursive: true, force: true })
  })
  setEnv('WEIBULL_FAVORITES_STORAGE', 'sqlite')
  setEnv('WEIBULL_LIBRARY_AUTH_MODE', 'sms')
  setEnv('WEIBULL_LIBRARY_PHONE', phone)
  setEnv('WEIBULL_LIBRARY_ACCOUNT_ID', 'legacy-owner')
  const initial = [
    { id: 'group-a', name: '试验研究', paperIds: ['182-001'] },
    { id: 'group-b', name: '估计方法', paperIds: ['182-002'], subfolders: [{ id: 'child-a', name: '原理依据' }] },
  ]
  writeFileSync(path.join(local, `${ownerKey}.json`), JSON.stringify({ version: 1, folders: initial }))
  const sync = loadServerModule('src/lib/server/library-favorites-sync.ts')
  const favorites = loadServerModule('src/lib/server/library-favorites.ts')
  const from = dir => setEnv('WEIBULL_FAVORITES_DIR', dir)
  const database = 'library-favorites.sqlite3'
  const json = value => JSON.parse(JSON.stringify(value))

  async function localState() {
    from(local)
    return sync.readLibraryFavoriteSync(peer)
  }

  async function exchange(dryRun = false) {
    const sent = await localState()
    from(remote)
    const reply = await sync.receiveLibraryFavoriteSync({ ...sent, dryRun })
    from(local)
    if (!dryRun) await sync.applyLibraryFavoriteSync(peer, sent, reply)
    return json(reply)
  }

  const readRemote = async () => {
    from(remote)
    return json(await favorites.readLibraryFavorites(phone))
  }

  assert.deepEqual(await exchange(true), { folders: initial, modified: true })
  assert.equal(existsSync(path.join(local, database)), false)
  assert.equal(existsSync(path.join(remote, database)), false)
  assert.deepEqual((await exchange()).folders, initial)
  assert.deepEqual(json((await localState()).baseline), initial)
  assert.deepEqual(await readRemote(), initial)
  await favorites.updateLibraryFavorites(other, { action: 'create', name: '另一个账号', paperIds: ['182-010'] }, null)
  await favorites.updateLibraryFavorites(phone, { action: 'add', folderId: 'group-a', paperIds: ['182-003'] })
  from(local)
  await favorites.updateLibraryFavorites(phone, { action: 'move', folderId: 'group-b', subfolderId: 'child-a', paperIds: ['182-002'] })
  const merged = (await exchange()).folders
  assert.deepEqual(merged[0].paperIds, ['182-001', '182-003'])
  assert.deepEqual(merged[1].paperSubfolders, { '182-002': 'child-a' })
  assert.deepEqual(await readRemote(), merged)
  assert.deepEqual(json((await localState()).folders), merged)
  assert.deepEqual((await exchange()).folders, merged)

  from(remote)
  await favorites.updateLibraryFavorites(phone, { action: 'remove', folderId: 'group-a', paperIds: ['182-001'] })
  const pushed = await localState()
  from(remote)
  const reply = await sync.receiveLibraryFavoriteSync({ ...pushed, dryRun: false })
  from(local)
  await favorites.updateLibraryFavorites(phone, { action: 'add', folderId: 'group-b', paperIds: ['182-004'] })
  await assert.rejects(sync.applyLibraryFavoriteSync(peer, pushed, reply), /同步期间有更新/)
  const retried = (await exchange()).folders
  assert.deepEqual(retried[0].paperIds, ['182-003'])
  assert.deepEqual(retried[1].paperIds, ['182-002', '182-004'])

  from(remote)
  await favorites.updateLibraryFavorites(phone, { action: 'add', folderId: 'group-a', paperIds: ['182-005'] })
  from(local)
  await favorites.updateLibraryFavorites(phone, { action: 'add', folderId: 'group-a', paperIds: ['182-006'] })
  await assert.rejects(exchange(), /有冲突.*试验研究/)
  assert.deepEqual((await readRemote())[0].paperIds, ['182-003', '182-005'])
  assert.equal((await favorites.readLibraryFavorites(other, null))[0].name, '另一个账号')
  assert.deepEqual(json((await localState()).folders[0].paperIds), ['182-003', '182-006'])
  from(remote)
  await assert.rejects(sync.receiveLibraryFavoriteSync({ ownerKey: 'wrong', folders: [], baseline: null, dryRun: false }), /手机号不同/)
})
