import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import vm from 'node:vm'
import { createRequire } from 'node:module'
import ts from 'typescript'
import { isContentSlug, resolveContentFile } from '../../src/lib/server/content-files.ts'
import { exportLibrary, checkLibrary, importPapers } from '../library-data.mjs'

const require = createRequire(import.meta.url)
function load(relative, overrides = {}) {
  const source = ts.transpileModule(fs.readFileSync(relative, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
  }).outputText
  const module = { exports: {} }
  const dependencies = { './content-files': { isContentSlug, resolveContentFile },
    '@/lib/server/content-files': { isContentSlug, resolveContentFile }, ...overrides }
  vm.runInNewContext(source, { module, exports: module.exports,
    require: name => dependencies[name] ?? require(name), process, console,
    URL, TextDecoder, TextEncoder, ReadableStream, Uint8Array,
    setTimeout: (...args) => { const timer = setTimeout(...args); timer.unref(); return timer },
  }, { filename: relative })
  return module.exports
}

function withFixture(run) {
  const parent = fs.mkdtempSync(path.join(os.tmpdir(), 'weibull-library-integration-'))
  const root = path.join(parent, 'library')
  fs.mkdirSync(path.join(root, 'content'), { recursive: true })
  fs.mkdirSync(path.join(root, 'assets/audit-paper-图片/images'), { recursive: true })
  fs.writeFileSync(path.join(root, 'library.json'), '{"schema_version":1}')
  fs.writeFileSync(path.join(root, 'references.json'), '{"audit-paper":{"1":"audit-paper"}}')
  fs.writeFileSync(path.join(root, 'content/audit-paper-pdf翻译.md'),
    '---\ntitle: 外挂测试文献\ntags: [MDM]\n---\n# 方法\n方法内容\n## 结果\nEXTERNAL_RESULT_739\n## 讨论\nNOT_THIS_SECTION_912\n')
  fs.writeFileSync(path.join(root, 'assets/audit-paper-图片/images/a b.png'), Buffer.from([137,80,78,71,13,10,26,10]))
  const saved = process.env.WEIBULL_LIBRARY_ROOT
  process.env.WEIBULL_LIBRARY_ROOT = root
  return Promise.resolve().then(() => run(root)).finally(() => {
    if (saved === undefined) delete process.env.WEIBULL_LIBRARY_ROOT
    else process.env.WEIBULL_LIBRARY_ROOT = saved
    fs.rmSync(parent, { recursive: true, force: true })
  })
}

test('actual content, references and image handlers use the same external source', () => withFixture(async root => {
  const storage = load('src/lib/server/literature.ts')
  const dependencies = { '@/lib/server/literature': storage }
  const content = load('src/app/api/content/route.ts', dependencies)
  const references = load('src/app/api/library/references/route.ts', dependencies)
  const assets = load('src/app/api/library/assets/[...segments]/route.ts', dependencies)
  const read = await content.GET({ url: 'http://test/?slug=audit-paper&type=翻译' })
  assert.equal(read.status, 200)
  assert.equal(await read.text(), fs.readFileSync(path.join(root, 'content/audit-paper-pdf翻译.md'), 'utf8'))
  assert.equal((await content.GET({ url: 'http://test/?slug=182-088&type=原文' })).status, 404)
  const ref = await references.GET({ nextUrl: new URL('http://test/?slug=audit-paper') })
  assert.deepEqual(await ref.json(), { 1: 'audit-paper' })
  const asset = await assets.GET({}, { params: { segments: ['audit-paper-图片', 'images', 'a b.png'] } })
  assert.equal(asset.status, 200)
  assert.equal(asset.headers.get('content-type'), 'image/png')
  assert.deepEqual(Buffer.from(await asset.arrayBuffer()), fs.readFileSync(path.join(root, 'assets/audit-paper-图片/images/a b.png')))
  assert.equal((await assets.GET({}, { params: { segments: ['..', 'references.json'] } })).status, 404)
}))

test('legacy asset URLs rewrite before public files and leave product routes alone', () => {
  const { NextRequest } = require('next/server')
  const { middleware } = load('src/middleware.ts')
  const response = middleware(new NextRequest('http://test/182-046-%E5%9B%BE%E7%89%87/images/a%20b.png'))
  const target = new URL(response.headers.get('x-middleware-rewrite'))
  assert.equal(decodeURIComponent(target.pathname), '/api/library/assets/182-046-图片/images/a b.png')
  for (const pathname of ['/methods/mdm', '/studies/mdm/chunks/1.csv', '/library/182-046', '/ai/model.png']) {
    assert.equal(middleware(new NextRequest('http://test' + pathname)).headers.get('x-middleware-rewrite'), null)
  }
})

test('chat stages receive actual external headings and selected section without paid APIs', () => withFixture(async () => {
  const storage = load('src/lib/server/literature.ts')
  const calls = []
  const client = { chat: { completions: { create: async request => {
    calls.push(request)
    if (request.stream) return (async function* () { yield { choices: [{ delta: { content: 'offline answer' } }] } })()
    const body = calls.length === 1 ? { relevant_papers: [{ slug: 'audit-paper' }] }
      : { relevant_sections: [{ paper_slug: 'audit-paper', paper_title: '外挂测试文献', section_heading: '结果' }] }
    return { choices: [{ message: { content: JSON.stringify(body) } }] }
  } } } }
  const chat = load('src/app/api/chat/route.ts', {
    '@/lib/server/literature': storage,
    '@/lib/server/moonshot-client': { hasMoonshotKey: () => true, getMoonshotClient: () => client },
  })
  const response = await chat.POST({ json: async () => ({ question: '结果如何', papers: [{ slug: 'audit-paper', title: '外挂测试文献' }] }) })
  const stream = await response.text()
  assert.equal(calls.length, 3)
  assert.match(calls[1].messages[0].content, /外挂测试文献/)
  assert.match(calls[1].messages[0].content, /结果/)
  assert.match(calls[2].messages[0].content, /EXTERNAL_RESULT_739/)
  assert.doesNotMatch(calls[2].messages[0].content, /NOT_THIS_SECTION_912/)
  assert.match(stream, /offline answer/)
  assert.match(stream, /audit-paper/)
}))

test('export preserves bytes, checks conflicts before overwrite, and verifies corruption', async () => {
  const parent = fs.mkdtempSync(path.join(os.tmpdir(), 'weibull-library-export-'))
  try {
    const repo = path.join(parent, 'repo')
    fs.mkdirSync(path.join(repo, 'src/content'), { recursive: true })
    fs.mkdirSync(path.join(repo, 'src/data'), { recursive: true })
    fs.mkdirSync(path.join(repo, 'public/audit-paper-图片'), { recursive: true })
    const raw = Buffer.from('---\r\ntitle: Test\r\n---\r\n# Test\r\n')
    fs.writeFileSync(path.join(repo, 'src/content/audit-paper-pdf原文.md'), raw)
    fs.writeFileSync(path.join(repo, 'src/data/references.json'), '{}')
    fs.writeFileSync(path.join(repo, 'public/audit-paper-图片/fig.png'), Buffer.from([0,1,2,3]))
    const destination = path.join(parent, 'library')
    assert.equal(exportLibrary(repo, destination).files, 3)
    assert.deepEqual(fs.readFileSync(path.join(destination, 'content/audit-paper-pdf原文.md')), raw)
    assert.equal(checkLibrary(destination, true).verifiedFiles, 3)
    assert.throws(() => exportLibrary(repo, destination), /exists/)
    fs.appendFileSync(path.join(destination, 'content/audit-paper-pdf原文.md'), 'changed')
    assert.throws(() => checkLibrary(destination, true), /hash mismatch/)
  } finally { fs.rmSync(parent, { recursive: true, force: true }) }
})

test('numbered imports add independent data, are repeatable, and reject conflicts before writes', () => withFixture(async root => {
  const batch = path.join(path.dirname(root), 'batch')
  fs.mkdirSync(batch)
  fs.writeFileSync(path.join(batch, 'new-paper-pdf原文.md'), '---\ntitle: New paper\n---\n# New\n')
  fs.mkdirSync(path.join(batch, 'new-paper-图片'))
  fs.writeFileSync(path.join(batch, 'new-paper-图片/fig.png'), 'bytes')
  assert.equal(importPapers(batch, root).importedFiles, 2)
  assert.equal(importPapers(batch, root).unchangedFiles, 2)
  fs.writeFileSync(path.join(batch, 'audit-paper-pdf翻译.md'), '---\ntitle: conflicting old paper\n---\n')
  fs.writeFileSync(path.join(batch, 'another-new-pdf原文.md'), '---\ntitle: New candidate\n---\n')
  assert.throws(() => importPapers(batch, root), /Conflict; nothing imported/)
  assert.equal(fs.existsSync(path.join(root, 'content/another-new-pdf原文.md')), false)
}))
