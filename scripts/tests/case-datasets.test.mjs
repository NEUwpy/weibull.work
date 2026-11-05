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
  function publish(...records) {
    write('cases/catalog.json', { schema_version: 1, groups: records.map(record => ({
      id: 'group-' + record.id, name: record.name, kind: record.nature.kind,
      members: [{ id: record.id, name: record.name }],
    })) })
  }
  try { await run({ root, write, publish }) }
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

test('copy text preserves sample precision and tabular cells without adding metadata', () => {
  const { datasetText } = load('src/lib/case-datasets.ts')
  assert.equal(datasetText({ ...sample(), data: [24.54, 28, 25.69] }), '24.54\n28\n25.69')
  assert.equal(datasetText({ ...sample(), data: { kind: 'table', rows: [['方法', '估计值'], ['MLE', 1.2345], ['LSE', null]] } }), '方法\t估计值\nMLE\t1.2345\nLSE\t')
  assert.equal(datasetText({ ...sample(), data: { kind: 'figure', asset: 'plot.png', caption: '原图说明' } }), '原图说明')
  assert.equal(datasetText({ ...sample(), data: { kind: 'external', description: '外部数据', url: 'https://example.com/data' } }), '外部数据\nhttps://example.com/data')
})

test('independent files update on reread and invalid records do not hide valid neighbours', () => fixture(({ write, publish }) => {
  const { readCaseDatasetIndex, readCaseDatasetById, datasetFigureUrl } = load('src/lib/server/case-datasets.ts')
  write('cases/records/one.json', sample())
  publish(sample())
  write('cases/records/broken.json', '{broken')
  let result = readCaseDatasetIndex()
  assert.equal(result.records.length, 1)
  assert.equal(result.issues.length, 1)
  write('cases/records/one.json', { ...sample(), name: '原记录的标题', data: [1, 2, 3] })
  result = readCaseDatasetIndex()
  assert.equal(result.records[0].name, '原始样本')
  assert.deepEqual(Array.from(readCaseDatasetById('sample').data), [1, 2, 3])
  const figure = { ...sample('figure'), data: { kind: 'figure', asset: '182-105-图片/one.png' } }
  assert.equal(datasetFigureUrl(figure), '/api/library/assets/182-105-%E5%9B%BE%E7%89%87/one.png')
  assert.equal(datasetFigureUrl({ ...figure, data: { kind: 'figure', asset: '182-999-图片/private.png' } }), undefined)
  assert.equal(datasetFigureUrl({ ...figure, data: { kind: 'figure', asset: '182-105-图片/../private.png' } }), undefined)
}))

test('catalog pages stay light, full records load individually, and secondary references remain explicit', () => fixture(async ({ write, publish }) => {
  const full = { ...sample('table'), name: '结果汇总表', data: { kind: 'table', rows: [['n', 'Bias'], [10, '0.2']], html: '<table><tr><td>10</td><td>0.2</td></tr></table>' }, nature: { kind: 'result', observation: 'summary' } }
  write('cases/records/table.json', full)
  write('cases/records/sample.json', sample())
  publish(full, sample())
  write('cases/coverage/scan.json', { paper_id: '182-105', status: 'extracted' })
  const route = load('src/app/api/cases/catalog/route.ts', {
    '@/lib/server/literature': { listPapers: () => [{ slug: '182-105', title: '论文题名', author: 'Author', year: 1996 }] },
  })
  const page = await (await route.GET(new Request('http://localhost/api/cases/catalog?q=结果汇总表&limit=1'))).json()
  assert.equal(page.matched, 1)
  assert.equal(page.items.length, 1)
  assert.equal(Object.hasOwn(page.items[0], 'data'), false)
  assert.equal(page.items[0].scale, '1 份结果材料')
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

test('legacy cases and grouped samples remain available while non-sample tables stay out of calculator choices', () => fixture(async ({ write, publish }) => {
  write('cases/records/sample.json', { ...sample(), _import: { source_file: 'private/source/path' } })
  write('cases/records/table.json', { ...sample('table'), data: { kind: 'table', rows: [[1, 2, 3]] }, nature: { kind: 'result', observation: 'summary' } })
  publish(sample())
  const storage = load('src/lib/cases_md.ts')
  assert.equal(storage.getCaseById('c1').id, 'c1')
  assert.equal(storage.getGroupById('g1').subCases.length, 30)
  assert.equal(storage.getCaseById('sample').data_raw, '12.5\n10.2\n18.4')
  assert.equal(storage.getCaseById('sample').type, '真实样本')
  assert.equal(Object.hasOwn(storage.getCaseById('sample').dataset, '_import'), false)
  const tree = storage.getCasesTree()
  assert.ok(tree.some(item => item.id === 'group-sample' && item.children[0].id === 'sample'))
  assert.ok(!tree.some(item => item.id === 'table'))
  const cases = await (await load('src/app/api/cases/route.ts').GET()).json()
  assert.ok(cases.some(item => item.id === 'sample'))
  assert.ok(!cases.some(item => item.id === 'table'))
  const catalog = await (await load('src/app/api/cases/catalog/route.ts').GET(new Request('http://localhost/api/cases/catalog?q=g1-2'))).json()
  assert.equal(catalog.items.find(item => item.id === 'g1').nature.kind, 'simulated')
  assert.ok(!catalog.items.some(item => item.id === 'g1-2'))
  const route = load('src/app/api/cases/catalog/route.ts')
  const group = await (await route.GET(new Request('http://localhost/api/cases/catalog?id=g1'))).json()
  assert.equal(group.group.members.length, 30)
  assert.equal(group.group.members[1].name, '第2次抽样')
  assert.ok(group.group.members.every(item => item.nature.kind === 'simulated'))
  assert.equal(storage.getSubCaseById('g1', 'g1-2').type, '抽样样本')
}))

test('indexed directories avoid opening unchanged data files and calculator eligibility is rechecked from data', () => fixture(({ root, write, publish }) => {
  const table = { ...sample('table'), data: { kind: 'table', rows: [[1, 2, 3]] }, nature: { kind: 'result', observation: 'summary' } }
  write('cases/records/table.json', table)
  publish(table)
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
  assert.equal(storage.readCaseDatasetIndex().records[0].name, table.name)
  write('cases/records/new.json', sample('new'))
  assert.equal(storage.readCaseDatasetIndex().records.length, 1)
  assert.equal(storage.readCaseDatasetIndex().pending_records, 1)
  publish(table, sample('new'))
  assert.equal(storage.readCaseDatasetIndex().records.length, 2)
  fs.unlinkSync(file)
  assert.equal(storage.readCaseDatasetIndex().records.length, 1)
}))

test('a missing grouping manifest keeps scanned materials out of the catalog and calculator', () => fixture(async ({ write }) => {
  write('cases/records/sample.json', sample())
  const storage = load('src/lib/server/case-datasets.ts')
  const index = storage.readCaseDatasetIndex()
  assert.equal(index.records.length, 0)
  assert.equal(index.pending_records, 1)
  assert.match(index.issues.join(' '), /分组目录暂缺/)
  assert.equal(storage.readCaseDatasetById('sample'), null)
  assert.equal(storage.readCalculableCaseDatasets().length, 0)
}))

test('curated groups separate experiments and simulations, keep derived views inside, and exclude unselected material everywhere', () => fixture(async ({ write }) => {
  write('cases/records/batch.json', sample('batch'))
  write('cases/records/combined.json', sample('combined'))
  write('cases/records/simulation.json', { ...sample('simulation'), nature: { kind: 'simulated', observation: 'complete' } })
  write('cases/records/deep-learning.json', { ...sample('deep-learning'), sources: [{ paper_id: '184-001', location: '表1', relation: 'direct' }] })
  write('cases/catalog.json', { schema_version: 1, groups: [
    { id: 'experiment', name: '环氧树脂击穿试验样本组', kind: 'observed', members: [
      { id: 'batch', name: '第一批试件', role: 'sample' }, { id: 'combined', name: '各批合并数据', role: 'derived' }] },
    { id: 'monte-carlo', name: '参数恢复样本组', kind: 'simulated', tags: ['平台生成'], members: [{ id: 'simulation', name: '数值算例一', role: 'sample' }] },
  ] })
  const route = load('src/app/api/cases/catalog/route.ts', { '@/lib/server/literature': { listPapers: () => [] } })
  const get = async query => (await route.GET(new Request('http://localhost/api/cases/catalog?' + query))).json()
  const page = await get('kind=observed')
  assert.equal(page.items.length, 1)
  assert.equal(page.items[0].id, 'experiment')
  assert.equal(page.items[0].scale, '1 组样本 · 1 份合并视图')
  assert.equal(page.items[0].member_count, 2)
  assert.equal(Object.hasOwn(page.items[0], 'members'), false)
  assert.equal(page.pending_records, 1)
  assert.equal((await get('q=第一批试件')).items[0].id, 'experiment')
  const group = (await get('id=experiment')).group
  assert.deepEqual(Array.from(group.members, item => item.name), ['第一批试件', '各批合并数据'])
  assert.ok(group.members.every(item => !Object.hasOwn(item, 'data')))
  assert.equal((await get('id=batch')).item.name, '第一批试件')
  assert.equal((await get('id=combined')).item.role, 'derived')
  assert.ok((await get('kind=simulated')).items.some(item => item.id === 'monte-carlo'))
  assert.deepEqual(Array.from((await get('id=monte-carlo')).group.nature.tags), ['平台生成'])
  assert.equal((await get('q=平台生成')).items.filter(item => item.id === 'monte-carlo').length, 1)
  assert.ok(!(await get('kind=simulated')).items.some(item => item.id === 'experiment'))
  assert.equal((await route.GET(new Request('http://localhost/api/cases/catalog?id=deep-learning'))).status, 404)
  const storage = load('src/lib/cases_md.ts')
  assert.equal(storage.getCaseById('deep-learning'), null)
  assert.ok(!storage.getAllCases().some(item => item.id === 'deep-learning'))
  const tree = storage.getCasesTree()
  assert.ok(!tree.some(item => item.id === 'batch' || item.id === 'deep-learning'))
  assert.equal(tree.find(item => item.id === 'experiment').children.length, 1)
  assert.ok(!tree.some(item => item.id === 'combined'))
  assert.equal(tree.find(item => item.id === 'experiment').sample_count, 1)
}))

test('an invalid grouping manifest reports the problem without publishing the raw scanning inventory', () => fixture(({ write }) => {
  write('cases/records/batch.json', sample('batch'))
  write('cases/catalog.json', { schema_version: 1, groups: [
    { id: 'experiment', name: '重复分组', kind: 'observed', members: [
      { id: 'batch', name: '第一批' }, { id: 'batch', name: '重复的第一批' }] },
  ] })
  const index = load('src/lib/server/case-datasets.ts').readCaseDatasetIndex()
  assert.equal(index.records.length, 0)
  assert.equal(index.pending_records, 1)
  assert.match(index.issues.join(' '), /重复/)
}))
