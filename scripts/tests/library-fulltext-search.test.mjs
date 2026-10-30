import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import matter from 'gray-matter'
import { compileLibraryMarkdown } from '../../src/lib/library-markdown-compiler.mjs'
import { loadServerModule } from './helpers/load-server-module.mjs'

const searchModule = loadServerModule('src/lib/server/library-search.ts')
const { searchLibrary, enrichLibrarySearchHits } = searchModule

function write(file, content) {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, content)
}

const metadata = (title, extra = {}) => ({ title, author: 'Alex Doe', year: 2024, type: '期刊', tags: [], ...extra })

async function withLibrary(run) {
  const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'weibull-fulltext-'))
  const root = path.join(workspace, 'library')
  write(path.join(root, 'library.json'), JSON.stringify({ schema_version: 1 }))
  write(path.join(root, 'references.json'), '{}')
  fs.mkdirSync(path.join(root, 'assets'), { recursive: true })
  const original = path.join(root, 'content', '182-001-pdf原文.md')
  const translation = path.join(root, 'content', '182-001-pdf翻译.md')
  write(original, matter.stringify('# Estimation\n\n## Likelihood\n\nMaximum likelihood estimates the three-parameter Weibull distribution from small samples with shape $\\beta$ and location $\\gamma$.\n\n## Notes\n\n- Censored observations contribute survival probabilities.\n- Newton updates need valid parameter bounds.\n\n| Procedure | Use |\n| --- | --- |\n| KaplanMeier | Censoring |\n\n```text\nNewtonRaphson(x)\n```\n\n## References\n\n[1] BIBLIOGRAPHY_ONLY book.\n', metadata('Weibull estimation', { doi: '10.1234/likelihood' })))
  write(translation, matter.stringify('# 参数估计\n\n## 似然方法\n\n三参数威布尔分布的极大似然估计利用样本估计形状参数与位置参数，小样本情况下需要检查似然边界。\n\n## 其他\n\n偏差校正可以使用模拟研究进行评估。\n', metadata('威布尔参数估计')))
  write(path.join(root, 'content', '182-002-pdf原文.md'), matter.stringify('# Reliability\n\nPreventive maintenance improves availability of repairable systems.\n', metadata('Maintenance scheduling', { author: 'Else Author' })))
  write(path.join(root, 'content', '421-001-pdf原文.md'), matter.stringify('# Survival book\n\nReliability of censored Weibull observations requires a survival model and sample treatment.\n', metadata('Survival book', { type: '书籍' })))
  const saved = process.env.WEIBULL_LIBRARY_ROOT
  process.env.WEIBULL_LIBRARY_ROOT = root
  try { await run({ root, workspace, original, translation }) }
  finally {
    if (saved === undefined) delete process.env.WEIBULL_LIBRARY_ROOT
    else process.env.WEIBULL_LIBRARY_ROOT = saved
    fs.rmSync(workspace, { recursive: true, force: true })
  }
}

test('full-text search finds Chinese terms, English phrases and a short passage in actual paragraphs', () => withLibrary(async () => {
  const chinese = searchLibrary('极大似然估计')
  assert.ok(chinese.results.length)
  assert.equal(chinese.results[0].slug, '182-001')
  assert.equal(chinese.results[0].version, '翻译')
  assert.match(chinese.results[0].excerpt, /极大似然估计/)
  assert.match(chinese.results[0].section, /似然方法/)
  const english = searchLibrary('maximum likelihood')
  assert.equal(english.results[0].version, '原文')
  assert.match(english.results[0].text, /Maximum likelihood/)
  const passage = searchLibrary('estimating the Weibull shape and location parameters using small samples')
  assert.equal(passage.results[0].slug, '182-001')
  assert.match(passage.results[0].text, /shape.*location/)
  assert.equal(searchLibrary('BIBLIOGRAPHY_ONLY').total, 0)
}))

test('number, DOI and author identity queries preserve catalog lookup and return meaningful excerpts', () => withLibrary(async () => {
  const byNumber = searchLibrary('182-001')
  assert.ok(byNumber.total)
  assert.ok(byNumber.results.every(hit => hit.slug === '182-001'))
  assert.match(byNumber.results[0].text, /Maximum likelihood|极大似然/)
  assert.equal(searchLibrary('10.1234/likelihood').results[0].slug, '182-001')
  assert.equal(searchLibrary('Else Author').results[0].slug, '182-002')
  const title = searchLibrary('Weibull estimation')
  assert.match(title.results[0].text, /Maximum likelihood|极大似然/)
}))

test('source selection and private notes stay outside search; changing selection invalidates the index', () => withLibrary(async ({ root, workspace }) => {
  const source = path.join(workspace, 'source')
  write(path.join(source, '182-001-pdf原文.md'), '# Selected\n\nSELECTED_MARKER available in public body.\n')
  write(path.join(source, '182-002-pdf原文.md'), '# Unselected\n\nUNSELECTED_MARKER private neighbour.\n')
  write(path.join(source, '182-001-笔记.md'), matter.stringify('PRIVATE_NOTE_MARKER assessment.', { id: '182-001', 年份: 2024 }))
  const descriptor = { schema_version: 2, mode: 'source', sources: [{ root: source, papers: [{ id: '182-001', metadata: metadata('Selected') }] }] }
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  assert.equal(searchLibrary('SELECTED_MARKER').results[0].slug, '182-001')
  assert.equal(searchLibrary('PRIVATE_NOTE_MARKER').total, 0)
  assert.equal(searchLibrary('UNSELECTED_MARKER').total, 0)
  descriptor.sources[0].papers = [{ id: '182-002', metadata: metadata('Now selected') }]
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  assert.equal(searchLibrary('SELECTED_MARKER').total, 0)
  assert.equal(searchLibrary('UNSELECTED_MARKER').results[0].slug, '182-002')
}))

test('changed same-length source content refreshes search without restarting the process', () => withLibrary(async ({ original }) => {
  const before = fs.readFileSync(original, 'utf8')
  write(original, before + '\n## Update\n\nCACHE_OLD_MARKER.\n')
  assert.ok(searchLibrary('CACHE_OLD_MARKER').total)
  write(original, before + '\n## Update\n\nCACHE_NEW_MARKER.\n')
  assert.equal(searchLibrary('CACHE_OLD_MARKER').total, 0)
  assert.ok(searchLibrary('CACHE_NEW_MARKER').total)
}))

test('each paragraph, table, tight-list and code search anchor exists in the shared rendered article', () => withLibrary(async () => {
  const storage = loadServerModule('src/lib/server/literature.ts')
  for (const query of ['极大似然估计', 'maximum likelihood', 'Censored observations', 'KaplanMeier', 'NewtonRaphson']) {
    const hit = searchLibrary(query).results[0]
    assert.ok(hit, query)
    const compiled = await compileLibraryMarkdown(storage.readPaper(hit.slug, hit.version))
    const target = new URL(hit.href, 'http://local').hash.slice(1)
    assert.ok(compiled.html.includes(`id="${target}"`), `${query}: ${target}`)
    assert.equal((compiled.html.match(new RegExp(`id="${target}"`, 'g')) || []).length, 1)
    assert.ok(hit.startLine > 0)
    assert.ok(hit.endLine >= hit.startLine)
  }
}))

test('search paging, long passages and public type filters are bounded', () => withLibrary(async ({ original }) => {
  write(original, matter.stringify('# Many paragraphs\n\n' + Array.from({ length: 45 }, (_, index) => `Repeatedneedle passage ${index} has sufficient information for a retrieval test.`).join('\n\n') + '\n\n' + 'Repeatedneedle long context. '.repeat(150), metadata('Many paragraphs')))
  const first = searchLibrary('Repeatedneedle', { limit: 100 })
  assert.equal(first.results.length, 30)
  assert.ok(first.total > 45)
  assert.ok(first.results.every(hit => hit.text.length <= 1600 && hit.excerpt.length <= 362))
  const next = searchLibrary('Repeatedneedle', { limit: 10, offset: 30 })
  assert.ok(next.results.every(hit => !first.results.some(previous => previous.id === hit.id)))
  assert.equal(searchLibrary('Repeatedneedle', { offset: first.total }).results.length, 0)
  assert.ok(searchLibrary('Reliability', { type: 'book' }).results.every(hit => hit.slug === '421-001'))
  assert.ok(searchLibrary('Weibull', { type: 'journal-conf' }).results.every(hit => hit.slug !== '421-001'))
  assert.equal(searchLibrary('  ').total, 0)
}))

test('explanatory paragraphs rank ahead of keyword lists and isolated index terms', () => withLibrary(async ({ original, translation }) => {
  write(original, matter.stringify('# Background\n\nKeywords: maximum likelihood, Weibull, estimation.\n\nMaximum likelihood\n\nMaximum likelihood estimates the unknown parameters from the observed sample by maximizing its likelihood function, and its location boundary needs careful examination.\n', metadata('Likelihood background')))
  fs.unlinkSync(translation)
  const results = searchLibrary('maximum likelihood').results
  assert.match(results[0].text, /maximizing its likelihood/)
  assert.ok(results.some(hit => hit.text.startsWith('Keywords:')))
}))

test('AI evidence retains nearby definitions, display equations and conditions within the matched section', () => withLibrary(async ({ original, translation }) => {
  write(original, matter.stringify('# Distribution theory\n\n## Distribution\n\nAssume a positive shape beta and positive scale eta.\n\nThe Weibull CDF is defined by the following expression:\n\n$$\nF(t)=1-\\exp[-((t-\\gamma)/\\eta)^\\beta].\n$$\n\nThe support condition is t greater than gamma; the CDF is zero outside this range.\n\n## Distribution\n\nOTHER_SECTION_MARKER concerns an unrelated distribution.\n', metadata('Distribution theory')))
  fs.unlinkSync(translation)
  const hit = searchLibrary('Weibull CDF').results.find(item => item.text.includes('following expression'))
  assert.ok(hit)
  assert.equal(hit.context, undefined)
  assert.doesNotMatch(hit.text, /F\(t\)/)
  const [enriched] = enrichLibrarySearchHits([hit])
  assert.equal(enriched.href, hit.href)
  assert.equal(enriched.text, hit.text)
  assert.equal(enriched.excerpt, hit.excerpt)
  assert.equal(enriched.startLine, hit.startLine)
  assert.equal(enriched.endLine, hit.endLine)
  assert.match(enriched.context, /positive shape beta and positive scale eta/)
  assert.match(enriched.context, /\$\$\nF\(t\)=1-/)
  assert.match(enriched.context, /support condition is t greater than gamma/)
  assert.doesNotMatch(enriched.context, /OTHER_SECTION_MARKER/)
  assert.ok(enriched.contextStartLine < hit.startLine)
  assert.ok(enriched.contextEndLine > hit.endLine)
  const compiled = await compileLibraryMarkdown(fs.readFileSync(original, 'utf8'))
  assert.ok(compiled.html.includes(`id="${new URL(enriched.href, 'http://local').hash.slice(1)}"`))
}))

test('AI neighbour windows stay bounded and do not jump across long intervening paragraphs', () => withLibrary(async ({ original, translation }) => {
  write(original, matter.stringify('# Bounds\n\n## One section\n\nBoundaryneedle identifies the relevant theorem for this local evidence window.\n\n' + 'Long unrelated intervening paragraph. '.repeat(30) + '\n\nDISTANT_MARKER must not be joined by skipping the long paragraph.\n\n## Large paragraph\n\n' + 'Chunkneedle theorem explanation. '.repeat(90), metadata('Bounded evidence')))
  fs.unlinkSync(translation)
  const hit = searchLibrary('Boundaryneedle').results[0]
  const [enriched] = enrichLibrarySearchHits([hit])
  assert.ok(enriched.context.length <= 1800)
  assert.doesNotMatch(enriched.context, /DISTANT_MARKER|Long unrelated/)
  const chunk = searchLibrary('Chunkneedle').results[0]
  const [long] = enrichLibrarySearchHits([chunk])
  assert.equal(long.context, chunk.text)
  assert.ok(long.context.length <= 1800)
}))

test('search HTTP handler rejects invalid selectors and caps, and returns structured hits', () => withLibrary(async () => {
  const route = loadServerModule('src/app/api/library/search/route.ts')
  const request = query => ({ nextUrl: new URL('http://local/api/library/search?' + query) })
  for (const query of ['q=x&type=private', 'q=x&limit=31', 'q=x&limit=NaN', 'q=x&offset=-1', 'q=' + 'x'.repeat(2001)]) {
    assert.equal((await route.GET(request(query))).status, 400)
  }
  const response = await route.GET(request('q=likelihood&limit=2'))
  assert.equal(response.status, 200)
  assert.equal(response.headers.get('cache-control'), 'no-store')
  const data = await response.json()
  assert.ok(data.total)
  assert.ok(data.results.length <= 2)
  assert.ok(data.terms.includes('likelihood'))
}))
