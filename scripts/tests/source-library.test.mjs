import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import matter from 'gray-matter'
import { createHash } from 'node:crypto'
import { loadServerModule as load } from './helpers/load-server-module.mjs'

const storage = load('src/lib/server/literature.ts')
const { getLibraryPaths, listPapers, readPaper, readPreferredPaper, readPaperMetadata, readLibraryDocuments, readReferences, resolveLibraryAsset } = storage
const id = '182-046'
const noteData = {
  id, 中文标题: '源库中文题名', 英文标题: 'Source paper title', 年份: 2025,
  期刊或类型: 'Reliability Engineering and System Safety', 作者: 'Author A', 单位: 'Research Institute',
  文献类型: '期刊', 出版简称: 'RESS', 关键词: ['Weibull', 'MDM', 'MDM'], 关联方法: 'mdm',
}

test('derived cross-paper references are versioned, selected and content-bound', () => withSource(({ root, source, directory, original, translation, descriptor }) => {
  const hash = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex')
  const relative = file => path.relative(source, file).split(path.sep).join('/')
  const other = '182-047'
  const target = path.join(directory, `${other}-pdf原文.md`)
  write(target, '# Target\n')
  const indexFile = path.join(source, '110', 'references.json')
  descriptor.reference_index = { root: source, file: '110/references.json' }
  descriptor.sources[0].papers.push({ id:other, metadata:{title:'Target',year:2024,author:'Target Author',tags:[]} })
  const targetInfo = { id: other, directory: relative(directory), path: relative(target), sha256: hash(target), doi:'10.1000/selected-target' }
  const index = { schema_version: 1, root: source,
    targets: { target: targetInfo, private: { ...targetInfo, id: '182-999' } },
    documents: {
      [relative(original)]: { sha256: hash(original), links: { 1: { target: 'target' }, 2: { target: 'private' } } },
      [relative(translation)]: { sha256: hash(translation), links: { 9: { target: 'target' } } },
    } }
  write(indexFile, JSON.stringify(index))
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  assert.equal(readLibraryDocuments().find(document => document.paper.slug === other).paper.doi, '10.1000/selected-target')
  assert.equal(listPapers().some(paper => paper.slug === '182-999'), false)
  assert.equal(JSON.stringify(readReferences(id, '原文')), JSON.stringify({ 1: other }))
  assert.equal(JSON.stringify(readReferences(id, '翻译')), JSON.stringify({ 9: other }))
  write(original, '# Changed source\n')
  // No stale-number fallback to the legacy table, even though that table still exists.
  assert.equal(JSON.stringify(readReferences(id, '原文')), '{}')
  write(target, '# Changed target\n')
  assert.equal(readLibraryDocuments().find(document => document.paper.slug === other).paper.doi, undefined)
  assert.equal(JSON.stringify(readReferences(id, '翻译')), '{}')
  write(indexFile, 'broken JSON')
  assert.equal(JSON.stringify(readReferences(id)), '{}')
}))

test('source reader retains an explicit numeric-parentheses display hint', () => withSource(({ original }) => {
  write(original, '---\ncitation_style: numeric-parentheses\n---\n# Original\n')
  assert.equal(matter(readPaper(id, '原文')).data.citation_style, 'numeric-parentheses')
}))

test('explicit retained v1 book source joins the source selection without exposing unselected neighbours', () => withSource(({ workspace, root, descriptor }) => {
  const books = path.join(workspace, 'preserved-books')
  const book = '421-001'
  const raw = matter.stringify('# Preserved corrected book\n\n![Figure](/421-001-图片/one.png)\n', {
    title: 'Preserved book', year: 2006, author: 'Author', type: '书籍', tags: [],
  })
  write(path.join(books, 'content', `${book}-pdf原文.md`), raw)
  write(path.join(books, 'content', '421-999-pdf原文.md'), raw)
  write(path.join(books, 'assets', `${book}-图片`, 'one.png'), 'book image')
  write(path.join(books, 'assets', '421-999-图片', 'one.png'), 'private neighbour')
  descriptor.sources.push({ root: books, layout: 'v1', papers: [book] })
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  assert.ok(listPapers().some(paper => paper.slug === book && paper.type === '书籍'))
  assert.equal(matter(readPaper(book, '原文')).content, matter(raw).content)
  assert.equal(fs.readFileSync(resolveLibraryAsset([`${book}-图片`, 'one.png']).path, 'utf8'), 'book image')
  assert.equal(readPaper('421-999', '原文'), null)
  assert.equal(resolveLibraryAsset(['421-999-图片', 'one.png']), null)
  assert.equal(resolveLibraryAsset([`${book}-图片`, '..', 'content']), null)
}))

function write(file, text) {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, text)
}

function withSource(run) {
  const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'weibull-source-library-'))
  const root = path.join(workspace, 'selection')
  const source = path.join(workspace, '100科研文献管理')
  const directory = path.join(source, '180_AI辅助参数估计', '182_传统参数估计方法')
  const note = path.join(directory, `${id}-笔记.md`)
  const original = path.join(directory, `${id}-pdf原文.md`)
  const translation = path.join(directory, `${id}-pdf翻译.md`)
  const images = path.join(directory, `${id}-图片`)
  const descriptor = { schema_version: 2, mode: 'source', sources: [{ root: source, papers: [id] }] }
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  write(path.join(root, 'references.json'), JSON.stringify({ [id]: { 7: id } }))
  write(note, matter.stringify('## 一句话总结\n\nPUBLIC_NOTE_SUMMARY_994\n\n## 研究判断\n\nPRIVATE_NOTE_993\n', noteData))
  write(original, '## Methods\n\nSOURCE_ORIGINAL_123\n')
  write(translation, '## 方法\n\nSOURCE_TRANSLATION_456\n')
  write(path.join(images, 'images', '图 1.png'), Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))
  const saved = process.env.WEIBULL_LIBRARY_ROOT
  process.env.WEIBULL_LIBRARY_ROOT = root
  return Promise.resolve().then(() => run({ workspace, root, source, directory, note, original, translation, images, descriptor }))
    .finally(() => {
      if (saved === undefined) delete process.env.WEIBULL_LIBRARY_ROOT
      else process.env.WEIBULL_LIBRARY_ROOT = saved
      const relative = path.relative(os.tmpdir(), workspace)
      assert.ok(relative.startsWith('weibull-source-library-') && !relative.includes(path.sep))
      fs.rmSync(workspace, { recursive: true, force: true })
    })
}

test('structured source credits survive public catalog and API reads without exposing private note fields', () => withSource(async ({ note, root, descriptor }) => {
  const credits = { authors: [{ name: '新署名', name_en: 'New Signature', units: ['u'] }], institutions: [{ id: 'u', name: 'Example University' }] }
  write(note, matter.stringify('## 一句话总结\n\nPublic summary\n\n## 对我的研究启发\n\nPRIVATE_CREDIT_NOTE\n', { ...noteData, credits }))
  assert.equal(listPapers()[0].credits.authors[0].name_en, 'New Signature')
  // A registered scalar catalog must retain compiled source credits too.
  descriptor.sources[0].papers = [{ id, metadata: { title: 'Registered', author: '新署名', year: 2025, type: '期刊', tags: [], credits } }]
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  const endpoint = load('src/app/api/library/papers/[slug]/route.ts', { '@/lib/server/literature': storage })
  const response = await endpoint.GET({}, { params: { slug: id } })
  const body = await response.json()
  assert.deepEqual(JSON.parse(JSON.stringify(body.paper.credits)), credits)
  assert.doesNotMatch(JSON.stringify(body), /PRIVATE_CREDIT_NOTE|对我的研究启发/)
}))

test('source selection holds configuration only and maps Chinese note metadata without copying its private body', () => withSource(({ root, original, translation, note }) => {
  const before = [original, translation, note].map(file => fs.readFileSync(file, 'utf8'))
  assert.equal(getLibraryPaths().mode, 'source')
  const [paper] = listPapers()
  assert.equal(paper.slug, id)
  assert.equal(paper.title, noteData.中文标题)
  assert.equal(paper.title_en, noteData.英文标题)
  assert.equal(paper.author, noteData.作者)
  assert.equal(paper.affiliation, noteData.单位)
  assert.equal(paper.publication, noteData.期刊或类型)
  assert.equal(paper.short_publication, 'RESS')
  assert.equal(paper.type, '期刊')
  assert.equal(paper.category.key, '180/182')
  assert.equal(readPaperMetadata(id).category.name, '传统估计方法')
  assert.equal(readLibraryDocuments()[0].paper.category.key, '180/182')
  assert.equal(paper.year, 2025)
  assert.deepEqual(Array.from(paper.tags), ['Weibull', 'MDM'])
  assert.equal(paper.summary, 'PUBLIC_NOTE_SUMMARY_994')
  assert.equal(paper.related_method_id, 'mdm')
  const preferred = readPreferredPaper(id)
  assert.match(preferred.body, /SOURCE_TRANSLATION_456/)
  assert.match(preferred.raw, /PUBLIC_NOTE_SUMMARY_994/)
  assert.doesNotMatch(preferred.raw, /PRIVATE_NOTE_993|研究判断|期刊或类型|工艺类型/)
  assert.deepEqual([original, translation, note].map(file => fs.readFileSync(file, 'utf8')), before)
  assert.deepEqual(fs.readdirSync(root).sort(), ['library.json', 'references.json'])
}))

test('each document English frontmatter overrides the shared note and translation remains preferred', () => withSource(({ original, translation }) => {
  write(original, matter.stringify('Original body.', { title: 'Original explicit title', author: 'Original author', year: 2020 }))
  write(translation, matter.stringify('Translated body.', {
    title: '译文明确题名', author: 'Translated author', year: 2024, tags: ['MLE'], summary: 'Explicit abstract',
  }))
  assert.equal(listPapers()[0].title, '译文明确题名')
  assert.equal(readPreferredPaper(id).metadata.author, 'Translated author')
  assert.equal(readPreferredPaper(id).metadata.year, 2024)
  assert.equal(readPreferredPaper(id).metadata.summary, 'PUBLIC_NOTE_SUMMARY_994')
  assert.equal(matter(readPaper(id, '原文')).data.title, 'Original explicit title')
  fs.unlinkSync(translation)
  assert.equal(readPreferredPaper(id).metadata.title, 'Original explicit title')
  assert.equal(readPreferredPaper(id).metadata.year, 2020)
}))

test('website JSON catalog overrides document YAML and Chinese notes without rewriting either source', () => withSource(({ root, descriptor, translation, note }) => {
  write(translation, matter.stringify('## 原文内容\n\nSOURCE_TRANSLATION_456', {
    title: 'Markdown title', year: 2021, author: 'Markdown author', tags: ['Markdown tag'], summary: 'Markdown summary',
  }))
  const before = [translation, note].map(file => fs.readFileSync(file, 'utf8'))
  const metadata = {
    title: 'JSON题名', title_en: 'JSON English title', author: 'Catalog author', year: 2024,
    affiliation: 'Catalog Institute', publication: 'Catalog Journal', short_publication: 'CJ',
    type: '期刊', tags: ['Catalog tag'], summary: 'Catalog summary', related_method_id: 'mle',
  }
  descriptor.sources[0].papers = [{ id, metadata }]
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  const [paper] = listPapers()
  for (const [key, value] of Object.entries(metadata)) {
    const expected = key === 'summary' ? 'PUBLIC_NOTE_SUMMARY_994' : value
    assert.equal(JSON.stringify(paper[key]), JSON.stringify(expected), key)
    assert.equal(JSON.stringify(readPreferredPaper(id).metadata[key]), JSON.stringify(expected), key)
  }
  assert.match(readPreferredPaper(id).body, /SOURCE_TRANSLATION_456/)
  metadata.title = 'Updated catalog title'
  metadata.year = 2026
  metadata.type = '书籍'
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  assert.equal(listPapers()[0].title, 'Updated catalog title')
  assert.equal(listPapers()[0].type, '书籍')
  assert.equal(readPreferredPaper(id).metadata.type, '书籍')
  assert.equal(readPreferredPaper(id).metadata.year, 2026)
  assert.deepEqual([translation, note].map(file => fs.readFileSync(file, 'utf8')), before)
}))

test('topic follows the actual source folder even when its paper number has another prefix', () => withSource(({ root, source, descriptor }) => {
  const directory = path.join(source, '180_AI辅助参数估计', '184_深度学习参数估计')
  const original = path.join(directory, '182-047-pdf原文.md')
  write(original, '# Moved long ago\n\nSOURCE_ACTUAL_FOLDER_473.\n')
  descriptor.sources[0].papers.push({ id: '182-047', metadata: { title: 'Actual folder', author: 'Author', year: 2025, type: '期刊' } })
  const selection = JSON.stringify(descriptor)
  write(path.join(root, 'library.json'), selection)
  assert.equal(readPaperMetadata('182-047').category.key, '180/184')
  assert.equal(readLibraryDocuments().find(document => document.paper.slug === '182-047').paper.category.key, '180/184')
  assert.equal(fs.readFileSync(path.join(root, 'library.json'), 'utf8'), selection)
  assert.match(fs.readFileSync(original, 'utf8'), /SOURCE_ACTUAL_FOLDER_473/)
}))

test('catalog metadata is sufficient for plain Markdown with neither YAML nor a note', () => withSource(({ root, descriptor, note, original, translation }) => {
  fs.unlinkSync(note)
  write(original, 'Source original plain text.\n')
  write(translation, '源库译文，不需要网站专用表头。\n')
  descriptor.sources[0].papers = [{ id, metadata: { title: 'Catalog-only title', year: 2025, author: 'Catalog author' } }]
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  assert.equal(listPapers()[0].title, 'Catalog-only title')
  assert.equal(listPapers()[0].author, 'Catalog author')
  assert.equal(listPapers()[0].year, 2025)
  assert.match(readPaper(id, '原文'), /Source original plain text/)
  assert.match(readPreferredPaper(id).body, /源库译文/)
  assert.equal(fs.existsSync(note), false)
  assert.equal(fs.readFileSync(translation, 'utf8'), '源库译文，不需要网站专用表头。\n')
}))

test('complete catalog cards and introductions only read the cached note summary, never original or translated bodies', () => withSource(async ({ root, source, descriptor }) => {
  const metadata = { title: 'Catalog introduction', year: 2025, author: 'Catalog author', doi: '10.1000/catalog', summary: 'Public abstract' }
  descriptor.sources[0].papers = [{ id, metadata }]
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  const route = load('src/app/api/library/papers/[slug]/route.ts', { '@/lib/server/literature': storage })
  const read = fs.readFileSync
  let noteReads = 0
  fs.readFileSync = function (file, ...args) {
    if (typeof file === 'string' && file.startsWith(source) && /-pdf(?:原文|翻译)\.md$/.test(file)) throw new Error('Catalog opened a full-text document')
    if (typeof file === 'string' && file.startsWith(source) && file.endsWith('-笔记.md')) noteReads++
    return read.call(this, file, ...args)
  }
  try {
    const [paper] = listPapers()
    assert.equal(paper.title, metadata.title)
    assert.equal(paper.doi, metadata.doi)
    assert.deepEqual(Array.from(paper.availableVersions), ['原文', '翻译'])
    assert.equal(readPaperMetadata(id).summary, 'PUBLIC_NOTE_SUMMARY_994')
    const response = await route.GET({}, { params: { slug: id } })
    assert.equal(response.status, 200)
    const payload = await response.json()
    assert.equal(payload.paper.title, metadata.title)
    assert.equal(payload.paper.summary, 'PUBLIC_NOTE_SUMMARY_994')
    assert.doesNotMatch(JSON.stringify(payload), /PRIVATE_NOTE_993|SOURCE_ORIGINAL_123|SOURCE_TRANSLATION_456/)
    assert.equal(noteReads, 1)
  } finally { fs.readFileSync = read }
}))

test('title presentation reads a bounded cached original header, refreshes note titles and does not replace catalog facts', () => withSource(async ({ root, original, note, descriptor }) => {
  const canonical = 'An original English paper title'
  descriptor.sources[0].papers = [{ id, metadata: { title: canonical, year: 2025 } }]
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  write(original, '# ' + canonical + '\n\n' + 'Body text. '.repeat(2000) + 'SECRET_BEYOND_HEADER')
  const open = fs.openSync, read = fs.readSync, close = fs.closeSync, fullRead = fs.readFileSync
  const handles = new Set()
  let headerBytes = 0
  fs.openSync = function (file, ...args) { const handle = open.call(this, file, ...args); if (file === original) handles.add(handle); return handle }
  fs.closeSync = function (handle) { handles.delete(handle); return close.call(this, handle) }
  fs.readSync = function (handle, buffer, ...args) {
    const bytes = read.call(this, handle, buffer, ...args)
    if (handles.has(handle)) { headerBytes += bytes; assert.doesNotMatch(buffer.toString('utf8'), /SECRET_BEYOND_HEADER/) }
    return bytes
  }
  fs.readFileSync = function (file, ...args) { if (file === original) throw new Error('A card opened the complete original'); return fullRead.call(this, file, ...args) }
  try {
    const [paper] = listPapers()
    assert.equal(paper.title, canonical)
    assert.equal(paper.display_title, noteData.中文标题)
    assert.equal(paper.original_language, 'en')
    listPapers()
    assert.equal(headerBytes, 8192)
    write(note, matter.stringify('## 一句话总结\n\nPUBLIC_NOTE_SUMMARY_994', { ...noteData, 中文标题: '更新后的中文译名' }))
    assert.equal(listPapers()[0].display_title, '更新后的中文译名')
    assert.equal(headerBytes, 8192)
    const route = load('src/app/api/library/papers/[slug]/route.ts', { '@/lib/server/literature': storage })
    const payload = await (await route.GET({}, { params: { slug: id } })).json()
    assert.equal(payload.paper.display_title, '更新后的中文译名')
    assert.equal(payload.paper.original_language, 'en')
    assert.doesNotMatch(JSON.stringify(payload), /PRIVATE_NOTE_993|SECRET_BEYOND_HEADER|sourceHeading|sourceTitle/)
  } finally { fs.openSync = open; fs.readSync = read; fs.closeSync = close; fs.readFileSync = fullRead }
  write(original, '# 中文原文标题\n\n正文内容。')
  assert.equal(listPapers()[0].original_language, 'zh')
}))

test('missing selected roots keep catalog entries and recover without blocking available documents', () => withSource(async ({ root, source, descriptor }) => {
  const missingRoot = path.join(source, 'not-yet-mounted')
  const missingId = '182-047'
  descriptor.sources[0].papers = [{ id, metadata: { title: 'Available paper', year: 2025 } }]
  descriptor.sources.push({ root: missingRoot, papers: [{ id: missingId, metadata: { title: 'Missing paper', year: 2024, summary: 'Kept introduction' } }] })
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  const cards = listPapers()
  assert.equal(cards.length, 2)
  assert.equal(cards.find(paper => paper.slug === missingId).availableVersions.length, 0)
  assert.equal(readLibraryDocuments().length, 2)
  assert.equal(readPaper(missingId, '原文'), null)
  const route = load('src/app/api/library/papers/[slug]/route.ts', { '@/lib/server/literature': storage })
  const response = await route.GET({}, { params: { slug: missingId } })
  assert.equal(response.status, 200)
  const payload = await response.json()
  assert.deepEqual(payload.versions, [])
  assert.equal(payload.paper.summary, 'Kept introduction')
  assert.equal((await route.GET({}, { params: { slug: '182-999' } })).status, 404)
  write(path.join(missingRoot, `${missingId}-pdf原文.md`), '# Mounted document\n\nNEWLY_MOUNTED_EVIDENCE\n')
  assert.deepEqual(Array.from(readPaperMetadata(missingId).availableVersions), ['原文'])
  assert.equal(readLibraryDocuments().length, 3)
  assert.match(readLibraryDocuments().find(document => document.paper.slug === missingId).raw, /NEWLY_MOUNTED_EVIDENCE/)
}))

test('missing versions become unavailable and leave the shared search corpus until restored', () => withSource(({ root, descriptor, original, translation }) => {
  descriptor.sources[0].papers = [{ id, metadata: { title: 'Retained catalog paper', year: 2025 } }]
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  assert.equal(readLibraryDocuments().length, 2)
  fs.unlinkSync(translation)
  assert.deepEqual(Array.from(readPaperMetadata(id).availableVersions), ['原文'])
  assert.equal(readLibraryDocuments().length, 1)
  fs.unlinkSync(original)
  assert.equal(listPapers()[0].availableVersions.length, 0)
  assert.equal(listPapers()[0].title, 'Retained catalog paper')
  assert.equal(readLibraryDocuments().length, 0)
  write(translation, '# Restored translation\n')
  assert.deepEqual(Array.from(readPaperMetadata(id).availableVersions), ['翻译'])
  assert.equal(readLibraryDocuments().length, 1)
}))

test('source selection accepts string IDs alongside catalog objects', () => withSource(({ root, descriptor, directory }) => {
  write(path.join(directory, '182-047-pdf原文.md'), 'Second paper without YAML.\n')
  descriptor.sources[0].papers = [id, { id: '182-047', metadata: { title: 'Second catalog title', year: 2023 } }]
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  const papers = new Map(listPapers().map(paper => [paper.slug, paper]))
  assert.equal(papers.size, 2)
  assert.equal(papers.get(id).title, noteData.中文标题)
  assert.equal(papers.get('182-047').title, 'Second catalog title')
  assert.match(readPaper('182-047', '原文'), /Second paper/)
}))

test('catalog objects reject missing or path IDs, duplicates, unknown fields and invalid metadata containers', () => withSource(({ root, descriptor }) => {
  const invalid = [
    {}, null, { id: '../private' }, { id: '182-046/笔记' }, { id: 182046 },
    { id, metadata: null }, { id, metadata: [] }, { id, metadata: 'title' },
    { id, metadata: { title: 'Valid', year: 2025, private_note: 'PRIVATE_NOTE_993' } },
  ]
  for (const entry of invalid) {
    descriptor.sources[0].papers = [entry]
    write(path.join(root, 'library.json'), JSON.stringify(descriptor))
    assert.throws(listPapers, /编号|metadata|未支持字段/, JSON.stringify(entry))
  }
  descriptor.sources[0].papers = [id, { id, metadata: { title: 'Duplicate', year: 2025 } }]
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  assert.throws(listPapers, /重复/)
}))

test('invalid catalog field types fail rather than falling back to valid source metadata', () => withSource(({ root, descriptor }) => {
  for (const [field, value] of [
    ['title', { text: 'Invalid React child' }], ['author', 7], ['publication', ['Journal']],
    ['tags', { name: 'tag' }], ['tags', [7]], ['year', ['2025']], ['summary', false], ['author', 0],
  ]) {
    descriptor.sources[0].papers = [{ id, metadata: { title: 'Catalog title', year: 2025, [field]: value } }]
    write(path.join(root, 'library.json'), JSON.stringify(descriptor))
    assert.throws(listPapers, /字符串|标题|年份|关键词|字段格式/, `${field}: ${JSON.stringify(value)}`)
  }
}))

test('source body, note metadata, selection and references are read again after edits', () => withSource(({ root, original, translation, note, descriptor }) => {
  assert.match(readPaper(id, '翻译'), /SOURCE_TRANSLATION_456/)
  write(translation, '## 结果\n\nCHANGED_AT_SOURCE_789\n')
  assert.match(readPreferredPaper(id).body, /CHANGED_AT_SOURCE_789/)
  write(note, matter.stringify('## 一句话总结\n\nUpdated summary.', { ...noteData, 年份: 2026 }))
  assert.equal(listPapers()[0].year, 2026)
  assert.equal(listPapers()[0].summary, 'Updated summary.')
  write(path.join(root, 'references.json'), JSON.stringify({ [id]: { 9: id } }))
  assert.equal(readReferences(id)['9'], id)
  fs.unlinkSync(translation)
  assert.match(readPreferredPaper(id).body, /SOURCE_ORIGINAL_123/)
  descriptor.sources[0].papers = []
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  assert.equal(listPapers().length, 0)
  assert.equal(readPaper(id, '原文'), null)
  assert.ok(fs.existsSync(original))
}))

test('relative images adapt to the same existing asset route and preserve source files', () => withSource(({ translation, images }) => {
  const body = `![编号路径](${id}-图片/images/%E5%9B%BE%201.png)\n![OCR路径](images/%E5%9B%BE%201.png)\n![当前目录](./${id}-图片/images/%E5%9B%BE%201.png)\n![旧网址](/${id}-图片/images/%E5%9B%BE%201.png)\n![远程](https://example.test/figure.png)\n`
  write(translation, body)
  const raw = readPaper(id, '翻译')
  for (const alt of ['编号路径', 'OCR路径', '当前目录', '旧网址']) {
    assert.ok(raw.includes(`![${alt}](/${id}-图片/images/%E5%9B%BE%201.png)`), alt)
  }
  assert.match(raw, /https:\/\/example\.test\/figure\.png/)
  const asset = resolveLibraryAsset([`${id}-图片`, 'images', '图 1.png'])
  assert.equal(asset.path, fs.realpathSync(path.join(images, 'images', '图 1.png')))
  assert.equal(asset.contentType, 'image/png')
  assert.equal(fs.readFileSync(translation, 'utf8'), body)
}))

test('an incomplete image cannot consume a later valid image across newlines', () => withSource(({ translation }) => {
  const body = '![](images/broken.png\n\nText between images.\n\n![后图](images/%E5%9B%BE%201.png)\n'
  write(translation, body)
  const before = fs.readFileSync(translation)
  const adapted = readPaper(id, '翻译')
  assert.ok(adapted.includes('![](images/broken.png\n\nText between images.'))
  assert.ok(adapted.includes(`![后图](/${id}-图片/images/%E5%9B%BE%201.png)`))
  assert.notEqual(resolveLibraryAsset([`${id}-图片`, 'images', '图 1.png']), null)
  assert.deepEqual(fs.readFileSync(translation), before)
}))

test('the note summary is public while YAML abstracts and all other note sections stay private', () => withSource(({ note, root, descriptor }) => {
  for (const heading of ['## 一句话总结', '## 1. 一句话总结']) {
    write(note, matter.stringify(`${heading}\n\nPUBLIC_NOTE_SUMMARY_994\n\n## 2. 研究判断\n\nPRIVATE_NOTE_993`, {
      ...noteData, 摘要: 'PRIVATE_NOTE_ABSTRACT_995',
    }))
    assert.equal(listPapers()[0].summary, 'PUBLIC_NOTE_SUMMARY_994')
    assert.doesNotMatch(JSON.stringify(listPapers()), /PRIVATE_NOTE_ABSTRACT_995|PRIVATE_NOTE_993/)
    assert.doesNotMatch(readPaper(id, '翻译'), /PRIVATE_NOTE_ABSTRACT_995|PRIVATE_NOTE_993/)
  }
  descriptor.sources[0].papers = [{ id, metadata: { summary: 'Public catalog abstract.' } }]
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  assert.equal(listPapers()[0].summary, 'PUBLIC_NOTE_SUMMARY_994')
  write(note, matter.stringify('## 核心内容\n\nPRIVATE_NOTE_993', noteData))
  assert.equal(listPapers()[0].summary, 'Public catalog abstract.')
}))

test('editing the selected note refreshes cards and introductions without rewriting the catalog snapshot', () => withSource(({ note, root, descriptor }) => {
  descriptor.sources[0].papers = [{ id, metadata: {
    title: 'Complete public catalog', year: 2025, summary: 'Stored fallback snapshot',
  } }]
  const file = path.join(root, 'library.json')
  write(file, JSON.stringify(descriptor))
  const before = fs.readFileSync(file, 'utf8')
  assert.equal(listPapers()[0].summary, 'PUBLIC_NOTE_SUMMARY_994')
  write(note, matter.stringify('## 一句话总结\n\nEdited note summary with $x=1$.\n\n## 不足\nPRIVATE_NOTE_993', noteData))
  assert.equal(listPapers()[0].summary, 'Edited note summary with $x=1$.')
  assert.equal(readPaperMetadata(id).summary, listPapers()[0].summary)
  assert.equal(fs.readFileSync(file, 'utf8'), before)
  fs.unlinkSync(note)
  assert.equal(readPaperMetadata(id).summary, 'Stored fallback snapshot')
}))

test('only selected IDs are readable and image extensions do not expose notes or unrelated files', () => withSource(({ directory, images, root }) => {
  write(path.join(directory, '182-047-pdf原文.md'), 'UNSELECTED_BODY_888')
  write(path.join(directory, '182-047-图片', 'private.png'), 'PRIVATE_IMAGE_888')
  write(path.join(images, 'private.json'), '{"secret":true}')
  write(path.join(images, 'private.md'), 'PRIVATE_NOTE_993')
  write(path.join(root, 'references.json'), JSON.stringify({ [id]: { 7: id }, '182-047': { 1: id } }))
  assert.equal(listPapers().length, 1)
  assert.equal(readPaper('182-047', '原文'), null)
  assert.equal(readPreferredPaper('182-047'), null)
  assert.equal(JSON.stringify(readReferences('182-047')), '{}')
  for (const slug of [`${id}-笔记`, '../outside', '182-046/笔记']) assert.equal(readPaper(slug, '原文'), null)
  for (const segments of [
    ['182-047-图片', 'private.png'], [`${id}-图片`, 'private.json'], [`${id}-图片`, 'private.md'],
    [`${id}-图片`, '..', `${id}-笔记.md`], [`${id}-图片`, 'images', '..\\private.json'],
  ]) assert.equal(resolveLibraryAsset(segments), null)
}))

test('historical duplicates are ignored while two current source locations fail instead of selecting silently', () => withSource(({ source, directory }) => {
  for (const archive of ['历史', '_archive', 'archive', '190_待处理与日志']) {
    write(path.join(directory, archive, `${id}-pdf原文.md`), 'HISTORICAL_333')
  }
  assert.equal(listPapers().length, 1)
  assert.doesNotMatch(readPaper(id, '原文'), /HISTORICAL_333/)
  write(path.join(source, 'another-active-topic', `${id}-pdf原文.md`), 'AMBIGUOUS_444')
  assert.throws(listPapers, /多个目录|多个版本|歧义/)
  assert.throws(() => readPaper(id, '原文'), /多个目录|多个版本|歧义/)
}))

test('an exact category directory disambiguates a historical reused ID without publishing its neighbour', () => withSource(({ root, source, directory, descriptor }) => {
  const other = path.join(source, 'another-active-topic')
  write(path.join(other, `${id}-pdf原文.md`), 'OTHER_TOPIC_BODY_449')
  write(path.join(other, `${id}-图片`, 'other.png'), 'OTHER_TOPIC_IMAGE_449')
  descriptor.sources[0].root = directory
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  assert.equal(listPapers().length, 1)
  assert.match(readPaper(id, '原文'), /SOURCE_ORIGINAL_123/)
  assert.doesNotMatch(readPaper(id, '原文'), /OTHER_TOPIC_BODY_449/)
  assert.equal(resolveLibraryAsset([`${id}-图片`, 'other.png']), null)
}))

test('the recorded 144-003 rename resolves only to selected 171-003 and normalizes source references', () => withSource(async ({ root, directory, descriptor }) => {
  write(path.join(directory, '171-003-pdf原文.md'), 'CANONICAL_RENAMED_BODY_171\n')
  write(path.join(directory, '171-003-图片', 'figure.png'), 'RENAMED_IMAGE_171')
  descriptor.sources[0].papers.push({ id: '171-003', metadata: { title: 'Renamed paper', year: 2024 } })
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  write(path.join(root, 'references.json'), JSON.stringify({
    '144-003': { 1: id }, [id]: { 3: '144-003', 4: '182-047' },
  }))
  assert.deepEqual(Array.from(listPapers(), paper => paper.slug).sort(), ['171-003', id])
  assert.match(readPaper('144-003', '原文'), /CANONICAL_RENAMED_BODY_171/)
  assert.equal(readPaper('144-003', '原文'), readPaper('171-003', '原文'))
  assert.match(readPreferredPaper('144-003').body, /CANONICAL_RENAMED_BODY_171/)
  assert.equal(readReferences(id)['3'], '171-003')
  assert.equal(readReferences(id)['4'], undefined)
  assert.equal(readReferences('144-003')['1'], id)
  assert.equal(readReferences('171-003')['1'], id)
  assert.equal(resolveLibraryAsset(['144-003-图片', 'figure.png']).path,
    fs.realpathSync(path.join(directory, '171-003-图片', 'figure.png')))
  // Identity and source selection are tested with an already authenticated reader.
  const content = load('src/app/api/content/route.ts', { '@/lib/server/literature': storage,
    '@/lib/server/library-auth': { requireLibraryLogin: () => null } })
  assert.equal((await content.GET({ url: 'http://test/?slug=144-003&type=原文' })).status, 200)
  write(path.join(root, 'references.json'), JSON.stringify({ '144-003': { 1: id }, '171-003': { 2: id } }))
  assert.equal(readReferences('144-003')['1'], undefined)
  assert.equal(readReferences('144-003')['2'], id)
  descriptor.sources[0].papers = [id]
  write(path.join(root, 'library.json'), JSON.stringify(descriptor))
  assert.equal(readPaper('144-003', '原文'), null)
  assert.equal(readPreferredPaper('144-003'), null)
  assert.equal((await content.GET({ url: 'http://test/?slug=144-003&type=原文' })).status, 404)
  assert.equal(JSON.stringify(readReferences('144-003')), '{}')
  assert.equal(resolveLibraryAsset(['144-003-图片', 'figure.png']), null)
}))

test('v1 rollback keeps the original 144-003 body, assets and reference IDs', () => withSource(({ workspace }) => {
  const legacy = path.join(workspace, 'legacy-v1')
  write(path.join(legacy, 'library.json'), '{"schema_version":1}')
  write(path.join(legacy, 'references.json'), JSON.stringify({ '144-003': { 1: '144-003' } }))
  write(path.join(legacy, 'content', '144-003-pdf原文.md'), matter.stringify('LEGACY_BODY_144', { title: 'Legacy', year: 2023 }))
  write(path.join(legacy, 'content', '171-003-pdf原文.md'), matter.stringify('OTHER_BODY_171', { title: 'Other', year: 2024 }))
  write(path.join(legacy, 'assets', '144-003-图片', 'figure.png'), 'LEGACY_IMAGE_144')
  process.env.WEIBULL_LIBRARY_ROOT = legacy
  assert.equal(getLibraryPaths().mode, 'external')
  assert.match(readPaper('144-003', '原文'), /LEGACY_BODY_144/)
  assert.doesNotMatch(readPaper('144-003', '原文'), /OTHER_BODY_171/)
  assert.equal(readReferences('144-003')['1'], '144-003')
  assert.equal(resolveLibraryAsset(['144-003-图片', 'figure.png']).path,
    fs.realpathSync(path.join(legacy, 'assets', '144-003-图片', 'figure.png')))
}))

test('missing metadata, inconsistent identity and ambiguous image locations are reported explicitly', () => withSource(({ note, translation, images }) => {
  const { 年份: _year, ...withoutYear } = noteData
  write(note, matter.stringify('', withoutYear))
  assert.throws(listPapers, /年份/)
  write(note, matter.stringify('', { ...noteData, id: '182-099' }))
  assert.throws(() => readPaper(id, '翻译'), /编号/)
  write(note, matter.stringify('', noteData))
  write(path.join(images, 'duplicate.png'), 'flat')
  write(path.join(images, 'images', 'duplicate.png'), 'nested')
  write(translation, '![图](images/duplicate.png)')
  assert.throws(() => readPaper(id, '翻译'), /歧义/)
}))

test('linked source directories and image folders cannot escape the configured source root', () => withSource(({ workspace, root, source, images, descriptor }) => {
  const outside = path.join(workspace, 'outside')
  write(path.join(outside, '182-047-pdf原文.md'), 'PRIVATE_SOURCE_555')
  write(path.join(outside, 'secret.png'), 'PRIVATE_IMAGE_555')
  const type = process.platform === 'win32' ? 'junction' : 'dir'
  const linkedDirectory = path.join(source, 'linked')
  const linkedImages = path.join(images, 'linked')
  fs.symlinkSync(outside, linkedDirectory, type)
  fs.symlinkSync(outside, linkedImages, type)
  try {
    assert.equal(listPapers().length, 1)
    assert.equal(readPaper('182-047', '原文'), null)
    assert.equal(resolveLibraryAsset([`${id}-图片`, 'linked', 'secret.png']), null)
    const savedImages = images + '-saved'
    fs.renameSync(images, savedImages)
    fs.symlinkSync(outside, images, type)
    try { assert.equal(resolveLibraryAsset([`${id}-图片`, 'secret.png']), null) }
    finally { fs.unlinkSync(images); fs.renameSync(savedImages, images) }
    descriptor.sources[0].papers = ['182-047']
    write(path.join(root, 'library.json'), JSON.stringify(descriptor))
    const [unavailable] = listPapers()
    assert.equal(unavailable.slug, '182-047')
    assert.equal(unavailable.availableVersions.length, 0)
    assert.equal(readPaper('182-047', '原文'), null)
  } finally {
    fs.unlinkSync(linkedDirectory)
    fs.unlinkSync(linkedImages)
  }
}))

test('authenticated content, asset, references and public chat consume selected source data without external AI calls', () => withSource(async ({ translation, root, directory }) => {
  write(translation, '## 方法\n\nMethod.\n\n## 结果\n\nLIVE_SOURCE_RESULT_738\n\n## 讨论\n\nNOT_SELECTED_SECTION_291\n')
  write(path.join(directory, '182-047-pdf原文.md'), 'UNSELECTED_BODY_888')
  write(path.join(directory, '182-047-图片', 'private.png'), 'PRIVATE_IMAGE_888')
  write(path.join(root, 'references.json'), JSON.stringify({ [id]: { 7: id, 8: '182-047' } }))
  const dependencies = { '@/lib/server/literature': storage,
    '@/lib/server/library-auth': { requireLibraryLogin: () => null } }
  const content = load('src/app/api/content/route.ts', dependencies)
  const references = load('src/app/api/library/references/route.ts', dependencies)
  const assets = load('src/app/api/library/assets/[...segments]/route.ts', dependencies)
  const response = await content.GET({ url: `http://test/?slug=${id}&type=翻译` })
  assert.equal(response.status, 200)
  const responseBody = await response.text()
  assert.match(responseBody, /LIVE_SOURCE_RESULT_738/)
  assert.doesNotMatch(responseBody, /PRIVATE_NOTE_993|PRIVATE_SHORT_SUMMARY_994/)
  assert.equal((await content.GET({ url: 'http://test/?slug=182-047&type=原文' })).status, 404)
  assert.equal((await content.GET({ url: `http://test/?slug=${id}-笔记&type=原文` })).status, 404)
  assert.deepEqual(await (await references.GET({ nextUrl: new URL(`http://test/?slug=${id}`) })).json(), { 7: id })
  const image = await assets.GET({}, { params: { segments: [`${id}-图片`, 'images', '图 1.png'] } })
  assert.equal(image.status, 200)
  assert.equal(image.headers.get('content-type'), 'image/png')
  assert.equal((await assets.GET({}, { params: { segments: ['182-047-图片', 'private.png'] } })).status, 404)
  assert.equal((await assets.GET({}, { params: { segments: [`${id}-图片`, '..', `${id}-笔记.md`] } })).status, 404)
  const calls = []
  const client = { chat: { completions: { create: async request => {
    calls.push(request)
    if (request.stream) return (async function* () { yield { choices: [{ delta: { content: 'offline answer' } }] } })()
    if (request.messages[0].content.startsWith('你筛选')) {
      const candidates = JSON.parse(request.messages[1].content.split('候选段落：\n')[1])
      return { choices: [{ message: { content: JSON.stringify({ ranked_ids: candidates.filter(item => item.text.includes('LIVE_SOURCE_RESULT_738')).map(item => item.id) }) } }] }
    }
    const selected = { queries: ['LIVE_SOURCE_RESULT_738'] }
    return { choices: [{ message: { content: JSON.stringify(selected) } }] }
  } } } }
  const chat = load('src/app/api/chat/route.ts', {
    '@/lib/server/library-chat-log': { createLibraryChatLog: () => ({ record() {}, flush: async () => {} }) },
    ...dependencies,
    '@/lib/server/deepseek-client': { hasDeepSeekKey: () => true, getDeepSeekClient: () => client,
      getDeepSeekSettings: () => ({ model: 'deepseek-flash', label: 'DeepSeek V4.1 Flash' }) },
  })
  const answer = await chat.POST({ json: async () => ({ question: 'LIVE_SOURCE_RESULT_738' }) })
  assert.match(await answer.text(), /offline answer/)
  assert.equal(calls.length, 3)
  assert.match(calls[2].messages[1].content, /LIVE_SOURCE_RESULT_738/)
  assert.doesNotMatch(JSON.stringify(calls), /NOT_SELECTED_SECTION_291|PRIVATE_NOTE_993|PRIVATE_SHORT_SUMMARY_994|UNSELECTED_BODY_888/)
}))
