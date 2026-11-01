import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import vm from 'node:vm'
import { createRequire } from 'node:module'
import ts from 'typescript'

const require = createRequire(import.meta.url)
const repository = process.cwd()

function fixture(run) {
  const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'weibull-runtime-data-'))
  const software = path.join(workspace, 'software')
  const data = path.join(workspace, 'data')
  fs.mkdirSync(software)
  const env = { WEIBULL_DATA_ROOT: '../data' }
  function write(relative, content = 'fixture', root = data) {
    const file = path.join(root, relative)
    fs.mkdirSync(path.dirname(file), { recursive: true })
    fs.writeFileSync(file, content)
    return file
  }
  const context = vm.createContext({ process: { env, cwd: () => software }, console, URL, Uint8Array })
  const cache = new Map()
  function load(relative) {
    const file = path.resolve(repository, relative)
    if (cache.has(file)) return cache.get(file).exports
    const module = { exports: {} }
    cache.set(file, module)
    const source = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
    }).outputText
    const localRequire = name => {
      if (name.startsWith('@/')) return load('src/' + name.slice(2) + '.ts')
      if (name.startsWith('.')) return load(path.relative(repository, path.resolve(path.dirname(file), name)) + '.ts')
      return require(name)
    }
    vm.runInContext(`(function(require, module, exports) { ${source}\n})`, context, { filename: file })(localRequire, module, module.exports)
    return module.exports
  }
  return Promise.resolve().then(() => run({ workspace, software, data, env, write, load }))
    .finally(() => fs.rmSync(workspace, { recursive: true, force: true }))
}

test('runtime assets read CSV/JSON from a relative external root without an embedded fallback', () => fixture(async ({ write, software, env, load }) => {
  const external = 'beta,eta\n2,1000\n'
  write('public/studies/mdm/chunks/sample.csv', external)
  write('public/studies/mdm/chunks/sample.csv', 'wrong embedded copy', software)
  write('public/ai/data/metrics.json', '{"ok":true}')
  write('public/case-studies/mdm/example/data.json', '{"samples":1}')
  const route = load('src/app/api/data/assets/[...path]/route.ts')
  for (const [segments, content] of [
    [['studies', 'mdm', 'chunks', 'sample.csv'], external],
    [['ai', 'data', 'metrics.json'], '{"ok":true}'],
    [['case-studies', 'mdm', 'example', 'data.json'], '{"samples":1}'],
  ]) {
    const response = await route.GET({}, { params: { path: segments } })
    assert.equal(response.status, 200)
    assert.equal(await response.text(), content)
    assert.equal(response.headers.get('x-content-type-options'), 'nosniff')
  }
  write('public/ai/data/metrics.json', '{"ok":false}')
  assert.equal(await (await route.GET({}, { params: { path: ['ai', 'data', 'metrics.json'] } })).text(), '{"ok":false}')
  env.WEIBULL_DATA_ROOT = '../missing-data'
  const absent = await route.GET({}, { params: { path: ['studies', 'mdm', 'chunks', 'sample.csv'] } })
  assert.equal(absent.status, 503)
  assert.match((await absent.json()).error, /WEIBULL_DATA_ROOT/)
}))

test('data roots default to a sibling and accept an absolute configured location', () => fixture(({ software, data, env, load }) => {
  const { getDataRoot } = load('src/lib/server/data-root.ts')
  delete env.WEIBULL_DATA_ROOT
  assert.equal(getDataRoot(), path.resolve(software, '../weibull-data'))
  env.WEIBULL_DATA_ROOT = '  ' + data + '  '
  assert.equal(getDataRoot(), data)
}))

test('runtime assets reject private namespaces, source files, traversal, casing and missing files', () => fixture(async ({ write, load }) => {
  write('public/ai/data/metrics.json', '{}')
  const route = load('src/app/api/data/assets/[...path]/route.ts')
  for (const segments of [
    ['models', 'private.json'], ['experiments', 'result.json'], ['ai', 'data', 'source.md'],
    ['studies', 'mdm', '..', 'secret.json'], ['ai', 'data', 'a/b.json'], ['ai', 'data', 'a\\b.json'],
    ['ai', 'data', 'C:secret.json'], ['ai', 'data', 'bad\0.json'], ['ai', 'data', 1], [],
  ]) assert.equal((await route.GET({}, { params: { path: segments } })).status, 400)
  assert.equal((await route.GET({}, { params: { path: ['ai', 'data', 'Metrics.json'] } })).status, 404)
  assert.equal((await route.GET({}, { params: { path: ['ai', 'data', 'missing.json'] } })).status, 404)
}))

test('runtime file resolver prevents external symlink access', () => fixture(async ({ workspace, write, load }) => {
  const directory = path.dirname(write('public/studies/mdm/chunks/known.csv'))
  const privateDir = path.join(workspace, 'private')
  fs.mkdirSync(privateDir)
  fs.writeFileSync(path.join(privateDir, 'secret.csv'), 'private')
  fs.symlinkSync(privateDir, path.join(directory, 'linked'), process.platform === 'win32' ? 'junction' : 'dir')
  const route = load('src/app/api/data/assets/[...path]/route.ts')
  assert.equal((await route.GET({}, { params: { path: ['studies', 'mdm', 'chunks', 'linked', 'secret.csv'] } })).status, 404)
  for (const [relative, link] of [['models/private.json', 'model-link'], ['public/models/private.json', 'public-model-link']]) {
    const model = write(relative, 'private model')
    fs.symlinkSync(path.dirname(model), path.join(directory, link), process.platform === 'win32' ? 'junction' : 'dir')
    assert.equal((await route.GET({}, { params: { path: ['studies', 'mdm', 'chunks', link, 'private.json'] } })).status, 404)
  }
}))

test('both chunk APIs enumerate external files, parse parameters and report missing datasets', () => fixture(async ({ write, software, load }) => {
  const filename = 'b2_e1000_g500_n7_rep10_seed42_step60.csv'
  write(`public/studies/mdm/chunks/${filename}`)
  write(`public/studies/mdm/demo1/chunks/${filename}`)
  write('public/studies/mdm/chunks/readme.md')
  write('public/studies/mdm/chunks/b9_n99.csv', 'embedded only', software)
  const method = load('src/app/api/studies/[methodId]/chunks/route.ts')
  const study = load('src/app/api/studies/[methodId]/[studyId]/chunks/route.ts')
  for (const [route, params] of [[method, { methodId: 'MDM' }], [study, { methodId: 'mdm', studyId: 'demo1' }]]) {
    const response = await route.GET({}, { params })
    const body = await response.json()
    assert.equal(response.status, 200)
    assert.deepEqual(body.chunks, [filename])
    assert.deepEqual(body.parsedParams.n, [7])
    assert.equal(body.total, 1)
  }
  assert.equal((await method.GET({}, { params: { methodId: '../mdm' } })).status, 400)
  assert.equal((await study.GET({}, { params: { methodId: 'mdm', studyId: '..' } })).status, 400)
  assert.equal((await method.GET({}, { params: { methodId: 'mle' } })).status, 503)
  assert.equal((await study.GET({}, { params: { methodId: 'mdm', studyId: 'demo2' } })).status, 503)
}))

test('existing browser data URLs rewrite to runtime assets and keep query strings', () => fixture(async ({ load }) => {
  const { NextRequest } = require('next/server')
  const { middleware } = load('src/middleware.ts')
  for (const pathname of ['/studies/mdm/chunks/a.csv', '/ai/data/a.json', '/case-studies/mdm/example/data.csv']) {
    const response = middleware(new NextRequest('http://local.test' + pathname + '?v=1'))
    const rewritten = new URL(response.headers.get('x-middleware-rewrite'))
    assert.equal(rewritten.pathname, '/api/data/assets' + pathname)
    assert.equal(rewritten.search, '?v=1')
  }
  for (const pathname of ['/methods/mdm', '/library/182-046', '/ai/model.png', '/studies/mdm/demo1/config.md', '/case-studies/mdm/example/config.md']) {
    assert.equal(middleware(new NextRequest('http://local.test' + pathname)).headers.has('x-middleware-rewrite'), false)
  }
  const image = middleware(new NextRequest('http://local.test/182-046-%E5%9B%BE%E7%89%87/a.jpg'))
  assert.match(decodeURIComponent(image.headers.get('x-middleware-rewrite')), /\/api\/library\/assets\/182-046-图片\/a.jpg/)
}))

test('study and case configuration APIs continue to read software metadata', () => fixture(async ({ write, software, load }) => {
  write('public/studies/mdm/demo1/config.md', '---\nid: demo1\nname: Local configuration\n---\n', software)
  write('public/case-studies/mdm/verification-example/config.md', '---\nid: verification-example\nname: Local case\n---\n', software)
  const studies = load('src/app/api/studies/[methodId]/route.ts')
  const cases = load('src/app/api/case-studies/mdm/route.ts')
  const single = load('src/app/api/case-studies/mdm/[caseId]/route.ts')
  assert.equal((await (await studies.GET({}, { params: { methodId: 'mdm' } })).json()).studies[0].name, 'Local configuration')
  assert.equal((await (await cases.GET()).json()).cases[0].name, 'Local case')
  assert.equal((await (await single.GET({}, { params: { caseId: 'verification-example' } })).json()).config.csvFile, '/case-studies/mdm/verification-example/data.csv')
}))
