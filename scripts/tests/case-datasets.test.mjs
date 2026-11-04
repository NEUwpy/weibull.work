import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { loadServerModule as load } from './helpers/load-server-module.mjs'

function sample(id = 'sample') {
  return { id, name: '原始样本', data: [12.5, 10.2, 18.4],
    nature: { kind: 'observed', observation: 'complete', unit: 'h' },
    sources: [{ paper_id: '182-105', location: 'Table 1, Case 2', relation: 'secondary', original_reference: '[8] Original study' }] }
}

async function fixture(run) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'weibull-case-datasets-'))
  const previous = process.env.WEIBULL_DATA_ROOT
  process.env.WEIBULL_DATA_ROOT = root
  function write(relative, value) {
    const file = path.join(root, relative)
    fs.mkdirSync(path.dirname(file), { recursive: true })
    fs.writeFileSync(file, typeof value === 'string' ? value : JSON.stringify(value))
  }
  try { await run({ root, write }) }
  finally {
    if (previous === undefined) delete process.env.WEIBULL_DATA_ROOT
    else process.env.WEIBULL_DATA_ROOT = previous
    fs.rmSync(root, { recursive: true, force: true })
  }
}

test('only complete positive observed or simulated samples enter calculation', () => {
  const { canCalculateDataset } = load('src/lib/case-datasets.ts')
  const original = sample()
  assert.equal(canCalculateDataset(original), true)
  for (const record of [
    { ...original, data: [1, 2] },
    { ...original, data: [1, 0, 3] },
    { ...original, data: [1, Infinity, 3] },
    { ...original, nature: { kind: 'result', observation: 'complete' } },
    { ...original, nature: { kind: 'observed', observation: 'right_censored' } },
    { ...original, data: { kind: 'table', rows: [[1, 2, 3]] } },
  ]) assert.equal(canCalculateDataset(record), false)
})

test('independent files update on reread and invalid records do not hide valid neighbours', () => fixture(({ write }) => {
  const { readCaseDatasetIndex, datasetFigureUrl } = load('src/lib/server/case-datasets.ts')
  write('cases/records/one.json', sample())
  write('cases/records/broken.json', '{broken')
  let result = readCaseDatasetIndex()
  assert.equal(result.records.length, 1)
  assert.equal(result.issues.length, 1)
  write('cases/records/one.json', { ...sample(), name: '已修改的样本名称' })
  result = readCaseDatasetIndex()
  assert.equal(result.records[0].name, '已修改的样本名称')
  const figure = { ...sample('figure'), data: { kind: 'figure', asset: '182-105-图片/one.png' } }
  assert.equal(datasetFigureUrl(figure), '/api/library/assets/182-105-%E5%9B%BE%E7%89%87/one.png')
  assert.equal(datasetFigureUrl({ ...figure, data: { kind: 'figure', asset: '182-999-图片/private.png' } }), undefined)
  assert.equal(datasetFigureUrl({ ...figure, data: { kind: 'figure', asset: '182-105-图片/../private.png' } }), undefined)
}))

test('catalog pages stay light, full records load individually, and secondary references remain explicit', () => fixture(async ({ write }) => {
  const full = { ...sample('table'), name: '结果汇总表', data: { kind: 'table', rows: [['n', 'Bias'], [10, '0.2']], html: '<table><tr><td>10</td><td>0.2</td></tr></table>' }, nature: { kind: 'result', observation: 'summary' } }
  write('cases/records/table.json', full)
  write('cases/records/sample.json', sample())
  write('cases/coverage/scan.json', { paper_id: '182-105', status: 'extracted' })
  const route = load('src/app/api/cases/catalog/route.ts', {
    '@/lib/server/literature': { listPapers: () => [{ slug: '182-105', title: '论文题名', author: 'Author', year: 1996 }] },
  })
  const page = await (await route.GET(new Request('http://localhost/api/cases/catalog?q=结果汇总表&limit=1'))).json()
  assert.equal(page.matched, 1)
  assert.equal(page.items.length, 1)
  assert.equal(Object.hasOwn(page.items[0], 'data'), false)
  assert.equal(page.items[0].scale, '2 行表格')
  assert.equal(page.items[0].sources[0].title, '论文题名')
  assert.equal(page.items[0].sources[0].relation, 'secondary')
  assert.equal(page.coverage.scanned, 1)
  assert.equal(page.coverage.reviewed, 0)
  const detail = await (await route.GET(new Request('http://localhost/api/cases/catalog?id=table'))).json()
  assert.equal(detail.item.data.html, full.data.html)
  assert.equal(detail.item.sources[0].original_reference, '[8] Original study')
  assert.equal(detail.item.can_calculate, false)
  assert.equal((await route.GET(new Request('http://localhost/api/cases/catalog?id=absent'))).status, 404)
  write('cases/coverage/review.json', { papers: [{ paper_id: '182-105', status: 'reviewed' }] })
  assert.equal((await (await route.GET(new Request('http://localhost/api/cases/catalog'))).json()).coverage.reviewed, 1)
}))

test('legacy cases and grouped samples remain available while non-sample tables stay out of calculator choices', () => fixture(async ({ write }) => {
  write('cases/records/sample.json', { ...sample(), _import: { source_file: 'private/source/path' } })
  write('cases/records/table.json', { ...sample('table'), data: { kind: 'table', rows: [[1, 2, 3]] }, nature: { kind: 'result', observation: 'summary' } })
  const storage = load('src/lib/cases_md.ts')
  assert.equal(storage.getCaseById('c1').id, 'c1')
  assert.equal(storage.getGroupById('g1').subCases.length, 30)
  assert.equal(storage.getCaseById('sample').data_raw, '12.5\n10.2\n18.4')
  assert.equal(storage.getCaseById('sample').type, '真实样本')
  assert.equal(Object.hasOwn(storage.getCaseById('sample').dataset, '_import'), false)
  const tree = storage.getCasesTree()
  assert.ok(tree.some(item => item.id === 'sample'))
  assert.ok(!tree.some(item => item.id === 'table'))
  const cases = await (await load('src/app/api/cases/route.ts').GET()).json()
  assert.ok(cases.some(item => item.id === 'sample'))
  assert.ok(!cases.some(item => item.id === 'table'))
  const catalog = await (await load('src/app/api/cases/catalog/route.ts').GET(new Request('http://localhost/api/cases/catalog?q=g1-2'))).json()
  assert.equal(catalog.items.find(item => item.id === 'g1-2').nature.kind, 'simulated')
}))

test('indexed directories avoid opening unchanged data files and calculator eligibility is rechecked from data', () => fixture(({ root, write }) => {
  const table = { ...sample('table'), data: { kind: 'table', rows: [[1, 2, 3]] }, nature: { kind: 'result', observation: 'summary' } }
  write('cases/records/table.json', table)
  const file = path.join(root, 'cases/records/table.json')
  const stat = fs.statSync(file)
  write('cases/index.json', { schema_version: 1, records: [{ id: table.id, name: table.name, nature: table.nature, sources: table.sources,
    file: 'records/table.json', scale: '1 行表格', data_kind: 'table', can_calculate: true, size: stat.size, mtime_ms: stat.mtimeMs }] })
  const storage = load('src/lib/server/case-datasets.ts')
  const originalRead = fs.readFileSync
  let openedData = 0
  fs.readFileSync = function(candidate, ...args) {
    if (candidate === file) openedData++
    return originalRead.call(this, candidate, ...args)
  }
  try {
    assert.equal(storage.readCaseDatasetIndex().records.length, 1)
    assert.equal(openedData, 0)
    assert.equal(storage.readCalculableCaseDatasets().length, 0)
    assert.equal(openedData, 1)
  } finally { fs.readFileSync = originalRead }
  write('cases/records/table.json', { ...table, name: '实际文件已更新' })
  assert.equal(storage.readCaseDatasetIndex().records[0].name, '实际文件已更新')
  write('cases/records/new.json', sample('new'))
  assert.equal(storage.readCaseDatasetIndex().records.length, 2)
  fs.unlinkSync(file)
  assert.equal(storage.readCaseDatasetIndex().records.length, 1)
}))
