import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { setImmediate } from 'node:timers'
import * as markdown from '../../src/lib/library-markdown.ts'
import { loadServerModule } from './helpers/load-server-module.mjs'

const nextTurn = () => new Promise(resolve => setImmediate(resolve))
const cacheKey = Symbol.for('weibull.library-search.v4')

async function withLibrary(run) {
  const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'weibull-prewarm-'))
  const root = path.join(workspace, 'library')
  const source = path.join(workspace, 'source')
  fs.mkdirSync(root)
  fs.mkdirSync(source)
  const original = path.join(source, '182-001-pdf原文.md')
  fs.writeFileSync(original, '# First paper\n\nInitialneedle describes a public method.\n')
  fs.writeFileSync(path.join(source, '182-002-pdf原文.md'), '# Second paper\n\nAddedneedle describes a newly selected method.\n')
  const ticket = id => ({ id, metadata: { title: id, year: 2024, author: 'Test', type: '期刊' } })
  const select = ids => fs.writeFileSync(path.join(root, 'library.json'), JSON.stringify({ schema_version: 2,
    mode: 'source', sources: [{ root: source, papers: ids.map(ticket) }] }))
  select(['182-001'])
  fs.writeFileSync(path.join(root, 'references.json'), '{}')
  const previousRoot = process.env.WEIBULL_LIBRARY_ROOT
  process.env.WEIBULL_LIBRARY_ROOT = root
  const shared = {}
  const timers = []
  let parses = 0
  const overrides = {
    'node:timers': { setImmediate, setTimeout(callback, delay) {
      const timer = { callback, delay, detached: false, unref() { this.detached = true } }
      timers.push(timer)
      return timer
    } },
    '../library-markdown': { ...markdown, extractLibraryPassages(...args) {
      parses++
      return markdown.extractLibraryPassages(...args)
    } },
  }
  const warnings = []
  const load = () => loadServerModule('src/lib/server/library-search.ts', overrides, {
    globalThis: shared, console: { info() {}, warn(...args) { warnings.push(args) } },
  })
  const tick = async () => {
    timers.at(-1).callback()
    await shared[cacheKey].warming?.catch(() => {})
    await nextTurn()
  }
  try { await run({ load, shared, timers, warnings, select, original, root, tick, parses: () => parses }) }
  finally {
    if (previousRoot === undefined) delete process.env.WEIBULL_LIBRARY_ROOT
    else process.env.WEIBULL_LIBRARY_ROOT = previousRoot
    fs.rmSync(workspace, { recursive: true, force: true })
  }
}

test('automatic warming sees a larger selection before any search and shares one timer across modules', () => withLibrary(async ({ load, timers, select, tick, parses }) => {
  const startup = load()
  await startup.startLibrarySearchPrewarm()
  assert.equal(parses(), 1)
  const route = load()
  await route.startLibrarySearchPrewarm()
  assert.equal(timers.length, 1)
  assert.equal(timers[0].delay, 10_000)
  assert.ok(timers[0].detached)
  select(['182-001', '182-002'])
  await tick()
  assert.equal(parses(), 2)
  assert.equal(timers.length, 2)
  const read = fs.readFileSync
  let bodyReads = 0
  fs.readFileSync = function(file, ...args) {
    if (String(file).endsWith('.md')) bodyReads++
    return read.call(this, file, ...args)
  }
  try {
    assert.ok(route.searchLibrary('Addedneedle').total)
    await tick()
    assert.equal(bodyReads, 0)
    assert.equal(parses(), 2)
  } finally { fs.readFileSync = read }
  select(['182-001'])
  await tick()
  assert.equal(route.searchLibrary('Addedneedle').total, 0)
  assert.equal(parses(), 2)
}))

test('incremental warming yields, joins concurrent requests and discards a source snapshot changed mid-build', () => withLibrary(async ({ load, shared, original, parses }) => {
  const search = load()
  await search.startLibrarySearchPrewarm()
  fs.appendFileSync(original, '\nStaleneedle is an intermediate save.\n')
  const warming = search.prepareLibrarySearch()
  assert.equal(search.prepareLibrarySearch(), warming)
  assert.equal(search.startLibrarySearchPrewarm(), warming)
  assert.ok(shared[cacheKey].warming)
  // The source can be saved again while the builder has yielded to other work.
  fs.writeFileSync(original, '# First paper\n\nCurrentneedle is the final saved method.\n')
  let yielded = false
  setImmediate(() => { yielded = true })
  await warming
  assert.ok(yielded)
  assert.equal(parses(), 3)
  assert.ok(search.searchLibrary('Currentneedle').total)
  assert.equal(search.searchLibrary('Staleneedle').total, 0)
  assert.equal(shared[cacheKey].warming, undefined)
}))

test('automatic warming retries a broken selection without serving removed sources after recovery', () => withLibrary(async ({ load, root, timers, warnings, select, tick }) => {
  const search = load()
  fs.writeFileSync(path.join(root, 'library.json'), '{incomplete')
  await assert.rejects(search.startLibrarySearchPrewarm(), /配置错误/)
  assert.equal(timers.length, 1)
  await tick()
  assert.equal(warnings.length, 1)
  assert.equal(timers.length, 2)
  select(['182-002'])
  await tick()
  assert.ok(search.searchLibrary('Addedneedle').total)
  assert.equal(search.searchLibrary('Initialneedle').total, 0)
}))

test('HTTP search waits for an active warm-up before reading the shared index', async () => {
  let finish
  let searches = 0
  const ready = new Promise(resolve => { finish = resolve })
  const route = loadServerModule('src/app/api/library/search/route.ts', {
    '@/lib/server/library-search': {
      startLibrarySearchPrewarm: () => ready,
      searchLibrary: () => { searches++; return { query: 'test', total: 0, terms: [], results: [] } },
    },
  })
  const response = route.GET({ nextUrl: new URL('http://local/api/library/search?q=test') })
  await nextTurn()
  assert.equal(searches, 0)
  finish()
  assert.equal((await response).status, 200)
  assert.equal(searches, 1)
})
