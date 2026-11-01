import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { loadServerModule } from './helpers/load-server-module.mjs'

const { getLibraryPaths, listPapers, readPaper, readPreferredPaper, readLibraryDocuments, readReferences, resolveLibraryAsset, LibraryConfigurationError } = loadServerModule('src/lib/server/literature.ts')

function fixture(run) {
  const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'weibull-library-test-'))
  const root = path.join(workspace, 'weibull-data', 'literature')
  const saved = process.env.WEIBULL_LIBRARY_ROOT
  const savedDataRoot = process.env.WEIBULL_DATA_ROOT
  fs.mkdirSync(path.join(root, 'content'), { recursive: true })
  fs.mkdirSync(path.join(root, 'assets'))
  fs.writeFileSync(path.join(root, 'library.json'), JSON.stringify({ schema_version: 1 }))
  fs.writeFileSync(path.join(root, 'references.json'), '{}')
  process.env.WEIBULL_LIBRARY_ROOT = root
  delete process.env.WEIBULL_DATA_ROOT
  try {
    run({ workspace, root, content: path.join(root, 'content'), assets: path.join(root, 'assets') })
  } finally {
    if (saved === undefined) delete process.env.WEIBULL_LIBRARY_ROOT
    else process.env.WEIBULL_LIBRARY_ROOT = saved
    if (savedDataRoot === undefined) delete process.env.WEIBULL_DATA_ROOT
    else process.env.WEIBULL_DATA_ROOT = savedDataRoot
    const relative = path.relative(os.tmpdir(), workspace)
    assert.ok(relative.startsWith('weibull-library-test-') && !relative.includes(path.sep))
    fs.rmSync(workspace, { recursive: true, force: true })
  }
}

function document(title, body = '# Body', fields = '') {
  return `---\ntitle: ${title}\n${fields}---\n\n${body}\n`
}

test('unset or empty configuration reads the sibling external library, including cache refreshes', () => fixture(({ workspace, root, content, assets }) => {
  const software = path.join(workspace, 'weibull')
  fs.mkdirSync(path.join(software, 'src/content'), { recursive: true })
  fs.writeFileSync(path.join(software, 'src/content/900-002-pdf原文.md'), document('Embedded decoy'))
  const raw = document('Sibling library')
  const file = path.join(content, '900-001-pdf原文.md')
  fs.writeFileSync(file, raw)
  fs.writeFileSync(path.join(root, 'references.json'), '{"900-001":{"1":"900-001"}}')
  fs.mkdirSync(path.join(assets, '900-001-图片'))
  fs.writeFileSync(path.join(assets, '900-001-图片', 'figure.png'), 'image bytes')
  const previousDirectory = process.cwd()
  process.chdir(software)
  try {
    for (const setting of [undefined, '']) {
      if (setting === undefined) delete process.env.WEIBULL_LIBRARY_ROOT
      else process.env.WEIBULL_LIBRARY_ROOT = setting
      assert.equal(getLibraryPaths().mode, 'external')
      assert.equal(getLibraryPaths().root, fs.realpathSync(root))
      assert.equal(listPapers().length, 1)
      assert.equal(readPreferredPaper('900-001').raw, raw)
      assert.equal(readPaper('900-002', '原文'), null)
      assert.equal(readReferences('900-001')['1'], '900-001')
      assert.equal(resolveLibraryAsset(['900-001-图片', 'figure.png']).path, fs.realpathSync(path.join(assets, '900-001-图片', 'figure.png')))
      assert.equal(readLibraryDocuments()[0].raw, raw)
    }
    fs.writeFileSync(file, document('Changed sibling library'))
    assert.match(readLibraryDocuments()[0].raw, /Changed sibling library/)
    fs.unlinkSync(path.join(root, 'library.json'))
    assert.throws(readLibraryDocuments, LibraryConfigurationError)
    assert.throws(listPapers, LibraryConfigurationError)
  } finally {
    process.chdir(previousDirectory)
  }
}))

test('the default library follows WEIBULL_DATA_ROOT and cached reads follow root changes', () => fixture(({ workspace, root, content }) => {
  const customData = path.join(workspace, 'mounted-data')
  const customRoot = path.join(customData, 'literature')
  fs.mkdirSync(path.join(customRoot, 'content'), { recursive: true })
  fs.mkdirSync(path.join(customRoot, 'assets'))
  fs.writeFileSync(path.join(customRoot, 'library.json'), '{"schema_version":1}')
  fs.writeFileSync(path.join(customRoot, 'references.json'), '{}')
  fs.writeFileSync(path.join(customRoot, 'content/900-001-pdf原文.md'), document('Custom data root'))
  fs.writeFileSync(path.join(content, '900-001-pdf原文.md'), document('Explicit library root'))
  process.env.WEIBULL_DATA_ROOT = customData
  // A library-specific override still takes precedence over the general data root.
  assert.equal(getLibraryPaths().root, fs.realpathSync(root))
  assert.match(readLibraryDocuments()[0].raw, /Explicit library root/)
  delete process.env.WEIBULL_LIBRARY_ROOT
  assert.equal(getLibraryPaths().root, fs.realpathSync(customRoot))
  assert.match(readLibraryDocuments()[0].raw, /Custom data root/)
  process.env.WEIBULL_DATA_ROOT = path.dirname(root)
  assert.equal(getLibraryPaths().root, fs.realpathSync(root))
  assert.match(readLibraryDocuments()[0].raw, /Explicit library root/)
  process.env.WEIBULL_DATA_ROOT = path.relative(process.cwd(), customData)
  assert.equal(getLibraryPaths().root, fs.realpathSync(customRoot))
  assert.match(readLibraryDocuments()[0].raw, /Custom data root/)
}))

test('external documents prefer translation and preserve metadata defaults and title requirement', () => fixture(({ content }) => {
  fs.writeFileSync(path.join(content, '900-001-pdf原文.md'), document('Original'))
  fs.writeFileSync(path.join(content, '900-001-pdf翻译.md'), document('译文', '# 译文正文', 'year: 2024\ntags: [WMLE]\n'))
  fs.writeFileSync(path.join(content, '900-002-pdf原文.md'), '# no frontmatter')
  const papers = listPapers()
  assert.equal(papers.length, 1)
  assert.equal(papers[0].slug, '900-001')
  assert.equal(papers[0].title, '译文')
  assert.equal(papers[0].author, 'Unknown')
  assert.equal(papers[0].type, '文献')
  assert.equal(papers[0].year, 2024)
  assert.equal(papers[0].tags[0], 'WMLE')
  assert.equal(papers[0].summary, '')
  const paper = readPreferredPaper('900-001')
  assert.equal(paper.metadata.title, '译文')
  assert.ok(paper.body.includes('# 译文正文'))
  assert.ok(readPaper('900-001', '原文').includes('Original'))
  assert.equal(readPaper('900-001', 'invalid'), null)
}))

test('external mode never mixes embedded documents, images or references', () => fixture(() => {
  assert.equal(listPapers().length, 0)
  assert.equal(readPaper('182-088', '原文'), null)
  assert.equal(readPreferredPaper('182-088'), null)
  assert.equal(JSON.stringify(readReferences('181-004')), '{}')
  assert.equal(resolveLibraryAsset(['182-088-图片', 'images', 'da0b41459560b4d7f368ef439ec1d843501fadf2b705cddba503584e45682f1f.jpg']), null)
}))

test('runtime imports, edits, deletions and reference updates are visible without reload', () => fixture(({ root, content }) => {
  assert.equal(listPapers().length, 0)
  const file = path.join(content, '900-001-pdf原文.md')
  fs.writeFileSync(file, document('Added'))
  assert.equal(listPapers()[0].title, 'Added')
  fs.writeFileSync(file, document('Edited'))
  assert.equal(readPreferredPaper('900-001').metadata.title, 'Edited')
  fs.writeFileSync(path.join(root, 'references.json'), JSON.stringify({ '900-001': { 7: '900-002' } }))
  assert.equal(readReferences('900-001')['7'], '900-002')
  fs.writeFileSync(path.join(root, 'references.json'), JSON.stringify({ '900-001': { 7: '900-003' } }))
  assert.equal(readReferences('900-001')['7'], '900-003')
  fs.unlinkSync(file)
  assert.equal(listPapers().length, 0)
  assert.equal(readPreferredPaper('900-001'), null)
}))

test('UTF-8 and legacy GBK documents decode through the same reader', () => fixture(({ content }) => {
  fs.writeFileSync(path.join(content, '900-001-pdf原文.md'), Buffer.from([0xd6, 0xd0, 0xce, 0xc4]))
  assert.equal(readPaper('900-001', '原文'), '中文')
  fs.writeFileSync(path.join(content, '900-001-pdf翻译.md'), '中文 UTF-8')
  assert.equal(readPaper('900-001', '翻译'), '中文 UTF-8')
}))

test('a configured missing, relative, malformed or incomplete root fails explicitly', () => fixture(({ workspace, root }) => {
  for (const configured of [path.join(workspace, 'missing'), '.', path.join(root, 'references.json')]) {
    process.env.WEIBULL_LIBRARY_ROOT = configured
    for (const read of [getLibraryPaths, listPapers, () => readPaper('182-088', '原文'), () => resolveLibraryAsset(['182-088-图片', 'a.jpg'])]) {
      assert.throws(read, LibraryConfigurationError)
    }
  }
  process.env.WEIBULL_LIBRARY_ROOT = root
  for (const descriptor of ['invalid json', '{}', '{"schema_version":2}', 'null']) {
    fs.writeFileSync(path.join(root, 'library.json'), descriptor)
    assert.throws(getLibraryPaths, LibraryConfigurationError)
  }
  fs.writeFileSync(path.join(root, 'library.json'), '{"schema_version":1}')
  fs.unlinkSync(path.join(root, 'references.json'))
  assert.throws(getLibraryPaths, LibraryConfigurationError)
}))

test('references reject invalid data instead of falling back or exposing inherited keys', () => fixture(({ root }) => {
  fs.writeFileSync(path.join(root, 'references.json'), 'invalid json')
  assert.throws(() => readReferences('900-001'), LibraryConfigurationError)
  fs.writeFileSync(path.join(root, 'references.json'), '{"900-001":{"7":8}}')
  assert.throws(() => readReferences('900-001'), LibraryConfigurationError)
  fs.writeFileSync(path.join(root, 'references.json'), '{}')
  assert.equal(JSON.stringify(readReferences('constructor')), '{}')
  assert.equal(JSON.stringify(readReferences('../outside')), '{}')
}))

test('asset serving permits nested and spaced paper images and reports their actual media types', () => fixture(({ assets }) => {
  const images = path.join(assets, '900-001-图片', 'images', 'nested folder')
  fs.mkdirSync(images, { recursive: true })
  for (const [extension, expected] of [['png', 'image/png'], ['jpg', 'image/jpeg'], ['jpeg', 'image/jpeg'], ['gif', 'image/gif'], ['webp', 'image/webp'], ['svg', 'image/svg+xml'], ['avif', 'image/avif'], ['pdf', 'application/pdf']]) {
    const file = path.join(images, `图 1.${extension}`)
    fs.writeFileSync(file, 'fixture')
    const asset = resolveLibraryAsset(['900-001-图片', 'images', 'nested folder', `图 1.${extension}`])
    assert.equal(asset.path, fs.realpathSync(file))
    assert.equal(asset.contentType, expected)
  }
  fs.writeFileSync(path.join(images, 'private.json'), '{}')
  assert.equal(resolveLibraryAsset(['900-001-图片', 'images', 'nested folder', 'private.json']), null)
}))

test('path selectors, casing, unrelated assets and directories are not file access', () => fixture(({ content, assets }) => {
  fs.writeFileSync(path.join(content, 'Paper-pdf原文.md'), document('Case'))
  fs.mkdirSync(path.join(assets, 'Paper-图片'))
  fs.writeFileSync(path.join(assets, 'Paper-图片', 'Photo.JPG'), 'fixture')
  assert.equal(readPaper('Paper', '原文') !== null, true)
  assert.equal(readPaper('paper', '原文'), null)
  for (const slug of ['../outside', 'a/b', 'a\\b', 'a%2fb', '_private', 'a\0b']) assert.equal(readPaper(slug, '原文'), null)
  for (const segments of [[], ['Paper-图片'], ['Paper-图片', '.'], ['Paper-图片', '..', 'Photo.JPG'], ['Paper-图片', '../Photo.JPG'], ['Paper-图片', '..\\Photo.JPG'], ['Paper-图片', 'Photo.JPG:stream'], ['Paper-图片', 'photo.JPG'], ['paper-图片', 'Photo.JPG'], ['other', 'Photo.JPG'], ['Paper-图片', 'missing.jpg']]) {
    assert.equal(resolveLibraryAsset(segments), null)
  }
}))

test('directory links escaping the library root cannot expose assets or substitute content', () => fixture(({ workspace, root, assets }) => {
  const outside = path.join(workspace, 'outside')
  fs.mkdirSync(outside)
  fs.writeFileSync(path.join(outside, 'secret.png'), 'secret')
  fs.writeFileSync(path.join(outside, '900-001-pdf原文.md'), document('Outside'))
  const linkType = process.platform === 'win32' ? 'junction' : 'dir'
  const linkedAssets = path.join(assets, '900-001-图片')
  fs.symlinkSync(outside, linkedAssets, linkType)
  assert.equal(resolveLibraryAsset(['900-001-图片', 'secret.png']), null)
  fs.unlinkSync(linkedAssets)
  fs.rmdirSync(path.join(root, 'content'))
  fs.symlinkSync(outside, path.join(root, 'content'), linkType)
  assert.throws(getLibraryPaths, LibraryConfigurationError)
  assert.throws(() => readPaper('900-001', '原文'), LibraryConfigurationError)
}))
