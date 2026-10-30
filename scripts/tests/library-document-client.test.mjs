import test from 'node:test'
import assert from 'node:assert/strict'
import { createLibraryDocumentClient, scheduleLibraryResultPrefetch, LibraryAuthenticationError } from '../../src/lib/library-document-client.ts'

const tick = () => new Promise(resolve => setImmediate(resolve))
function deferred() {
  let resolve
  const promise = new Promise(done => { resolve = done })
  return { promise, resolve }
}

test('logout cache clearing rejects previous in-flight reads and requires fresh content', async () => {
  const gate = deferred()
  let calls = 0
  const client = createLibraryDocumentClient({ fetcher: async () => {
    calls++
    return calls === 1 ? gate.promise : new Response('# New session')
  } })
  const beforeLogout = client.readFile('A', '原文')
  const rejection = assert.rejects(beforeLogout, { name: 'AbortError' })
  client.clear()
  gate.resolve(new Response('# Previous session'))
  await rejection
  assert.equal(await client.readFile('A', '原文'), '# New session')
  assert.equal(calls, 2)
})

test('401 bodies and references become authentication errors and are never cached', async () => {
  let calls = 0
  const client = createLibraryDocumentClient({ fetcher: async () => { calls++; return new Response('AUTH_REQUIRED', { status: 401 }) } })
  await assert.rejects(client.readFile('A', '原文'), LibraryAuthenticationError)
  await assert.rejects(client.readFile('A', '原文'), LibraryAuthenticationError)
  await assert.rejects(client.readReferences('A', '原文'), LibraryAuthenticationError)
  assert.equal(calls, 3)
})

test('a previous session delayed 401 cannot invalidate a newly loaded session', async () => {
  const previousWindow = globalThis.window
  let invalidations = 0
  globalThis.window = { dispatchEvent: () => { invalidations++ } }
  try {
    for (const method of ['readFile', 'readReferences']) {
      const gate = deferred()
      let calls = 0
      const client = createLibraryDocumentClient({ fetcher: async () => {
        calls++
        return calls === 1 ? gate.promise : new Response(method === 'readFile' ? '# Current session' : '{}')
      } })
      const old = client[method]('A', '原文')
      const rejection = assert.rejects(old, { name: 'AbortError' })
      client.clear()
      const current = await client[method]('A', '原文')
      gate.resolve(new Response('AUTH_REQUIRED', { status: 401 }))
      await rejection
      assert.deepEqual(await client[method]('A', '原文'), current)
      assert.equal(calls, 2)
    }
    assert.equal(invalidations, 0)
  } finally {
    if (previousWindow === undefined) delete globalThis.window
    else globalThis.window = previousWindow
  }
})

test('reader joins in-flight prefetches and reuses completed body and version-specific references', async () => {
  const calls = []
  const gates = new Map()
  const client = createLibraryDocumentClient({ fetcher: url => {
    calls.push(url)
    const gate = deferred()
    gates.set(url, gate)
    return gate.promise
  } })
  const body = client.readFile('182-030', '翻译')
  const references = client.readReferences('182-030', '翻译')
  assert.equal(client.readFile('182-030', '翻译'), body)
  assert.equal(client.readReferences('182-030', '翻译'), references)
  for (const [url, gate] of gates) gate.resolve(new Response(url.includes('/references?') ? JSON.stringify({ 1: '182-046' }) : '# 正文'))
  assert.equal(await body, '# 正文')
  assert.deepEqual(await references, { 1: '182-046' })
  assert.equal(await client.readFile('182-030', '翻译'), '# 正文')
  assert.deepEqual(await client.readReferences('182-030', '翻译'), { 1: '182-046' })
  assert.equal(calls.length, 2)
})

test('versions remain distinct, missing variants are remembered and failed requests retry', async () => {
  const calls = []
  let fail = true
  const client = createLibraryDocumentClient({ fetcher: async url => {
    calls.push(url)
    if (url.includes('/references?') && fail) { fail = false; return new Response('', { status: 503 }) }
    return new Response(url.includes('/references?') ? '{}' : '# Original', { status: url.includes(encodeURIComponent('翻译')) ? 404 : 200 })
  } })
  assert.equal(await client.readFile('A', '翻译'), null)
  assert.equal(await client.readFile('A', '翻译'), null)
  assert.equal(await client.readFile('A', '原文'), '# Original')
  await assert.rejects(client.readReferences('A', '原文'), /引用暂时不可用/)
  assert.deepEqual(await client.readReferences('A', '原文'), {})
  assert.equal(calls.length, 4)
})

test('cache expires and evicts old entries by entry count and approximate byte budget', async () => {
  let now = 0
  let calls = 0
  const client = createLibraryDocumentClient({ now: () => now, ttlMs: 10, maxEntries: 2, maxBytes: 20,
    fetcher: async () => { calls++; return new Response('123456') } })
  await client.readFile('A', '原文')
  await client.readFile('B', '原文') // two 12-byte strings exceed the 20-byte cache.
  await client.readFile('A', '原文')
  assert.equal(calls, 3)
  now = 11
  await client.readFile('A', '原文')
  assert.equal(calls, 4)
  const countBound = createLibraryDocumentClient({ maxEntries: 1, fetcher: async () => { calls++; return new Response('x') } })
  await countBound.readFile('A', '原文')
  await countBound.readFile('B', '原文')
  await countBound.readFile('A', '原文')
  assert.equal(calls, 7)
})

test('prefetch starts only after scheduling, deduplicates versions, and caps work at four documents with two requests', async () => {
  const calls = []
  const gates = []
  let running = 0
  let maximum = 0
  const client = createLibraryDocumentClient({ fetcher: url => {
    calls.push(url)
    running++
    maximum = Math.max(maximum, running)
    const gate = deferred()
    gates.push({ gate, url })
    return gate.promise.then(response => { running--; return response })
  } })
  let start
  scheduleLibraryResultPrefetch([{ slug: 'A', version: '翻译' }, { slug: 'A', version: '翻译' },
    { slug: 'B', version: '原文' }, { slug: 'C', version: '翻译' }, { slug: 'D', version: '原文' }, { slug: 'E', version: '原文' }], client,
    callback => { start = callback; return () => {} })
  assert.equal(calls.length, 0) // Search rendering is outside this deferred work.
  start()
  assert.equal(calls.length, 2)
  while (gates.length) {
    const { gate, url } = gates.shift()
    gate.resolve(new Response(url.includes('/references?') ? '{}' : '# Text'))
    await tick()
  }
  assert.equal(calls.length, 8)
  assert.equal(maximum, 2)
  assert.equal(calls.some(url => url.includes('slug=E')), false)
})

test('changing a query or page cancels unstarted work while started data stays reusable', async () => {
  const calls = []
  const gates = []
  const client = createLibraryDocumentClient({ fetcher: url => { calls.push(url); const gate = deferred(); gates.push({ url, gate }); return gate.promise } })
  let start
  let cancelled = false
  const cancel = scheduleLibraryResultPrefetch([{ slug: 'A', version: '原文' }, { slug: 'B', version: '原文' }], client,
    callback => { start = callback; return () => { cancelled = true } })
  start()
  cancel()
  for (const { url, gate } of gates) gate.resolve(new Response(url.includes('/references?') ? '{}' : '# A'))
  await tick()
  assert.equal(cancelled, true)
  assert.equal(calls.length, 2)
  assert.equal(await client.readFile('A', '原文'), '# A')
  assert.equal(calls.length, 2)

  let later
  const cancelBeforeStart = scheduleLibraryResultPrefetch([{ slug: 'C', version: '原文' }], client,
    callback => { later = callback; return () => {} })
  cancelBeforeStart()
  later()
  assert.equal(calls.length, 2)
})

test('prefetch batches share two background slots while foreground reads start immediately', async () => {
  const calls = []
  const gates = []
  let running = 0
  let maximum = 0
  const client = createLibraryDocumentClient({ fetcher: url => {
    const foreground = url.includes('slug=FOREGROUND')
    calls.push(url)
    if (!foreground) { running++; maximum = Math.max(maximum, running) }
    const gate = deferred()
    gates.push({ url, gate })
    return gate.promise.then(response => { if (!foreground) running--; return response })
  } })
  const starts = []
  const schedule = callback => { starts.push(callback); return () => {} }
  const cancelOld = scheduleLibraryResultPrefetch([{ slug: 'OLD', version: '原文' }, { slug: 'UNSTARTED', version: '原文' }], client, schedule)
  starts.shift()()
  assert.equal(running, 2)
  cancelOld()
  const cancelNew = scheduleLibraryResultPrefetch([{ slug: 'NEW', version: '翻译' }], client, schedule)
  starts.shift()()
  assert.equal(calls.length, 2) // New work waits for the old batch's running requests.
  const foreground = client.readFile('FOREGROUND', '原文')
  const foregroundReferences = client.readReferences('FOREGROUND', '原文')
  assert.equal(calls.length, 4) // Reader requests never wait for a background slot.
  assert.equal(client.readFile('OLD', '原文'), client.readFile('OLD', '原文'))
  while (gates.length) {
    const { gate, url } = gates.shift()
    gate.resolve(new Response(url.includes('/references?') ? '{}' : '# Text'))
    await tick()
  }
  await Promise.all([foreground, foregroundReferences])
  cancelNew()
  assert.equal(maximum, 2)
  assert.equal(calls.filter(url => url.includes('slug=NEW')).length, 2)
  assert.equal(calls.some(url => url.includes('slug=UNSTARTED')), false)
})
