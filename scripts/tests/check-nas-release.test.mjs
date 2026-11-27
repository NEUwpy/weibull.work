import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { checkFavorites, checkReleaseData, mappedFile } from '../check-nas-release.mjs'

const digest = bytes => createHash('sha256').update(bytes).digest('hex')

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'weibull-release-'))
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  function write(file, value) {
    const target = path.join(root, file)
    fs.mkdirSync(path.dirname(target), { recursive: true })
    const bytes = Buffer.isBuffer(value) ? value : Buffer.from(JSON.stringify(value))
    fs.writeFileSync(target, bytes)
    return { sha256: digest(bytes), bytes: bytes.length }
  }
  function bind(source, target) {
    return { type: 'bind', source: path.join(root, source), target, read_only: true }
  }

  write('data/library/library.json', { unreachable: true })
  write('tickets/library.json', {
    schema_version: 2, mode: 'source', sources: [{ root: '/sources', papers: ['182-001'] }],
    reference_index: { root: '/sources', file: 'references-index.json' },
  })
  write('tickets/references.json', {})
  write('sources/182-001/182-001-pdf原文.md', Buffer.from('fixture'))
  write('sources/references-index.json', { schema_version: 1, root: '/sources' })
  write('data/cases/catalog.json', { schema_version: 1, groups: [{ members: [{ id: 'case-1' }] }] })
  write('data/cases/index.json', { schema_version: 1, records: [{ id: 'case-1', file: 'records/case-1.json' }] })
  write('data/cases/records/case-1.json', { id: 'case-1' })

  const dir = 'monte-carlo/fixture'
  const excel = write(`data/${dir}/workbook.xlsx`, Buffer.from('original workbook bytes'))
  const view = write(`data/${dir}/workbook.json`, { id: 'book-1', sha256: excel.sha256 })
  const code = write(`data/${dir}/frozen/main.py`, Buffer.from('fixture source'))
  const manifest = write(`data/${dir}/manifest.json`, { schemaVersion: 1, id: 'book-1',
    files: { 'workbook.xlsx': { ...excel, role: 'workbook' }, 'workbook.json': { ...view, role: 'view' },
      'frozen/main.py': { ...code, role: 'code' } },
  })
  const frontend = {
    environment: { WEIBULL_DATA_ROOT: '/data', WEIBULL_LIBRARY_ROOT: '/data/library' },
    volumes: [bind('data', '/data'), bind('tickets', '/data/library'), bind('sources', '/sources')],
  }
  const entries = [{ id: 'book-1', directory: dir, manifestSha256: manifest.sha256, workbookSha256: excel.sha256 }]
  function errors() {
    const failures = []
    checkReleaseData(frontend, entries, (label, run) => {
      try { run() } catch (error) { failures.push([label, error.message]) }
    })
    return failures
  }
  return { root, write, frontend, errors }
}

test('release data checks the deeper mount and validates the candidate workbook archive', t => {
  const f = fixture(t)
  assert.equal(mappedFile(f.frontend.volumes, '/data/library/library.json'), path.join(f.root, 'tickets', 'library.json'))
  assert.throws(() => mappedFile(f.frontend.volumes, '/database/library/library.json'), /只读宿主挂载/)
  assert.deepEqual(f.errors(), [])
  f.write('data/monte-carlo/fixture/frozen/main.py', Buffer.from('alternate fixture'))
  assert.deepEqual(f.errors(), [['工作簿 book-1', '登记附件的哈希或大小不匹配']])
})

test('release data reports missing selected bodies, a wrong reference root and unmatched cases', t => {
  const f = fixture(t)
  fs.unlinkSync(path.join(f.root, 'sources', '182-001', '182-001-pdf原文.md'))
  f.write('data/cases/records/case-1.json', { id: 'different-case' })
  assert.deepEqual(f.errors(), [['文献书票与正文', '缺少所选正文：182-001'], ['公开案例', '案例记录身份不一致：case-1']])
  f.write('sources/182-001/182-001-pdf译文.md', Buffer.from('not a supported filename'))
  f.write('sources/182-001/182-001-pdf翻译.md', Buffer.from('valid filename'))
  f.write('sources/references-index.json', { schema_version: 1, root: 'D:/local-source' })
  assert.equal(f.errors()[0][0], '文献书票与正文')
  assert.match(f.errors()[0][1], /容器内绝对路径|根目录与 NAS 配置不一致/)
})

test('favorites verification preserves the existing writable volume identity', () => {
  const frontend = { container_name: 'weibull-frontend',
    volumes: [{ type: 'volume', source: 'library-favorites', target: '/app-state/library-favorites' }],
  }
  const compose = { name: 'weibull', volumes: { 'library-favorites': { name: 'weibull_library-favorites' } } }
  let actual = { Destination: '/app-state/library-favorites', Type: 'volume', Name: 'weibull_library-favorites', RW: true }
  let exists = true
  const calls = []
  function docker(args) {
    calls.push(args.slice(0, 2).join(' '))
    if (args[0] === 'volume') return 'weibull_library-favorites'
    if (args[1] === 'ls') return exists ? 'weibull-frontend\n' : ''
    return JSON.stringify([actual])
  }
  assert.equal(checkFavorites(compose, frontend, false, docker), 'weibull_library-favorites')
  assert.deepEqual(calls, ['container ls', 'container inspect', 'volume inspect'])
  actual = { ...actual, Name: 'other_library-favorites' }
  assert.throws(() => checkFavorites(compose, frontend, false, docker), /收藏卷或可写挂载不一致/)
  assert.throws(() => checkFavorites(compose, frontend, true, docker), /已有前端/)
  exists = false
  assert.match(checkFavorites(compose, frontend, true, docker), /待首次连接/)
})
