import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import vm from 'node:vm'
import { createRequire } from 'node:module'
import ts from 'typescript'
import { isContentSlug, resolveContentFile } from '../../src/lib/server/content-files.ts'
import { getMoonshotClient, hasMoonshotKey } from '../../src/lib/server/moonshot-client.ts'

const require = createRequire(import.meta.url)

// Exercise the actual handlers with Next's response objects, without starting a server.
function loadRoute(relative, overrides = {}, globals = {}) {
  const file = path.resolve(relative)
  const source = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
  }).outputText
  const module = { exports: {} }
  const dependencies = {
    '@/lib/server/content-files': { isContentSlug, resolveContentFile },
    '@/lib/server/moonshot-client': { getMoonshotClient, hasMoonshotKey },
    '@/lib/config': { getApiBaseUrl: () => 'http://simulation.test' },
    ...overrides,
  }
  vm.runInNewContext(source, {
    exports: module.exports,
    module,
    require: name => dependencies[name] ?? require(name),
    process,
    URL,
    TextDecoder,
    TextEncoder,
    ReadableStream,
    console,
    ...globals,
  }, { filename: file })
  return module.exports
}

test('content identifiers reject paths and permit existing literature names', () => {
  assert.equal(isContentSlug('182-088'), true)
  for (const invalid of ['../outside', 'a/b', 'a\\b', '_template', 'a%2fb', 'a\0b']) {
    assert.equal(isContentSlug(invalid), false)
  }
})

test('file resolver restricts inventory and real paths', () => {
  const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'weibull-content-'))
  const root = path.join(workspace, 'content')
  const outside = path.join(workspace, 'outside')
  fs.mkdirSync(root)
  fs.mkdirSync(outside)
  const known = path.join(root, '182-088-pdf原文.md')
  const link = path.join(root, 'linked.md')
  fs.writeFileSync(known, 'fixture')
  try {
    assert.equal(resolveContentFile(root, path.basename(known)), fs.realpathSync(known))
    assert.equal(resolveContentFile(root, 'missing.md'), null)
    assert.equal(resolveContentFile(root, '../outside.md'), null)
    fs.symlinkSync(outside, link, process.platform === 'win32' ? 'junction' : 'dir')
    assert.equal(resolveContentFile(root, 'linked.md'), null)
  } finally {
    if (fs.existsSync(link)) fs.unlinkSync(link)
    fs.unlinkSync(known)
    fs.rmdirSync(root)
    fs.rmdirSync(outside)
    fs.rmdirSync(workspace)
  }
})

test('content routes reject invalid selectors and still serve known documents', async () => {
  const literature = loadRoute('src/app/api/content/route.ts')
  const algorithms = loadRoute('src/app/api/algorithms/route.ts')
  assert.equal((await literature.GET({ url: 'http://local/?slug=182-088&type=invalid' })).status, 400)
  assert.equal((await literature.GET({ url: 'http://local/?slug=..%2Foutside&type=原文' })).status, 400)
  assert.equal((await algorithms.GET({ nextUrl: new URL('http://local/?slug=..%2Foutside') })).status, 400)
  assert.equal((await algorithms.GET({ nextUrl: new URL('http://local/?slug=mdm') })).status, 200)
  assert.equal((await algorithms.GET({ nextUrl: new URL('http://local/?slug=does-not-exist') })).status, 404)
  const file = fs.readdirSync('src/content').find(name => name.endsWith('-pdf原文.md'))
  const slug = file.slice(0, -'-pdf原文.md'.length)
  assert.equal((await literature.GET({ url: `http://local/?slug=${encodeURIComponent(slug)}&type=原文` })).status, 200)
})

test('chat can load and list models without a key; POST returns a controlled 503', async () => {
  const saved = process.env.MOONSHOT_API_KEY
  delete process.env.MOONSHOT_API_KEY
  try {
    assert.equal(hasMoonshotKey(), false)
    assert.throws(() => getMoonshotClient('https://example.invalid'), /not configured/)
    const route = loadRoute('src/app/api/chat/route.ts')
    assert.equal((await route.GET()).status, 200)
    assert.equal((await route.POST({ json: () => { throw new Error('must not read request') } })).status, 503)
  } finally {
    if (saved === undefined) delete process.env.MOONSHOT_API_KEY
    else process.env.MOONSHOT_API_KEY = saved
  }
  const config = JSON.parse(fs.readFileSync('src/app/api/chat/config.json', 'utf8'))
  assert.equal(Object.hasOwn(config.moonshot, 'apiKey'), false)
})

test('simulation proxy retains failure rows, metrics and an explicit zero seed', async () => {
  let forwarded
  const backend = {
    rows: [{ est_beta: null, converged: false, error: 'failed fixture' }],
    metrics: { valid_count: 0, failure_count: 1 }, count: 1, success: true,
  }
  const route = loadRoute('src/app/api/studies/simulate/route.ts', {}, {
    fetch: async (_url, options) => {
      forwarded = JSON.parse(options.body)
      return { ok: true, json: async () => backend }
    },
  })
  const response = await route.POST({ json: async () => ({ methodId: 'mdm', params: { beta: 2, eta: 1, n: 7, rep: 1, seed: 0 } }) })
  const result = await response.json()
  assert.equal(forwarded.seed, 0)
  assert.deepEqual(result.rows, backend.rows)
  assert.deepEqual(result.metrics, backend.metrics)
})

test('simulation proxy preserves backend rejection and rejects missing params', async () => {
  const route = loadRoute('src/app/api/studies/simulate/route.ts', {}, {
    fetch: async () => ({ ok: false, status: 429, json: async () => ({ detail: 'busy' }) }),
  })
  assert.equal((await route.POST({ json: async () => ({ methodId: 'mdm' }) })).status, 400)
  assert.equal((await route.POST({ json: async () => ({ methodId: 'mdm', params: { beta: 2, eta: 1, n: 7 } }) })).status, 429)
})
