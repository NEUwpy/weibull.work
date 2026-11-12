import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import ts from 'typescript'

const require = createRequire(import.meta.url)
function loadBatch() {
  const cache = new Map(), stored = new Map()
  const storage = { setItem: (key, value) => stored.set(key, value), getItem: key => stored.get(key) ?? null }
  function load(filename) {
    filename = path.resolve(filename)
    if (cache.has(filename)) return cache.get(filename).exports
    const module = { exports: {} }
    cache.set(filename, module)
    const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    }).outputText
    const localRequire = name => name.startsWith('.') ? load(path.resolve(path.dirname(filename), name + '.ts')) : require(name)
    new Function('require', 'module', 'exports', 'sessionStorage', code)(localRequire, module, module.exports, storage)
    return module.exports
  }
  return { ...load('src/lib/calculator-batch.ts'), CalculationError: load('src/lib/calculation-feedback.ts').CalculationError, stored }
}
const parameters = { beta: 2, eta: 1000, gamma: 500 }
const response = { methodId: 'mdm', result: { beta: 2, eta: 950, gamma: 510, rSquared: .99, points: [], converged: true },
  calculation: { original: 'criterion' }, traceData: { original: 'solver' } }

test('batch generation preserves independent groups and exact generating parameters', () => {
  const { generateSampleSources } = loadBatch()
  const sources = generateSampleSources(50, 7, parameters)
  assert.equal(sources.length, 50)
  assert.equal(new Set(sources.map(source => source.id)).size, 50)
  assert.equal(new Set(sources.map(source => source.groupId)).size, 1)
  assert.ok(sources.every(source => source.data.length === 7 && source.data.every(point => point.value > parameters.gamma)))
  assert.ok(sources.every(source => !source.result && source.generatedFrom !== parameters))
  assert.notDeepEqual(sources[0].data, sources[1].data)
  assert.deepEqual(sources[0].generatedFrom, parameters)
  for (const invalid of [0, 1.5, 1001, NaN]) assert.throws(() => generateSampleSources(invalid, 7, parameters))
})

test('one rejected estimate keeps its actual sample and diagnostic while later groups finish', async () => {
  const { generateSampleSources, estimateSampleSources, CalculationError } = loadBatch()
  const sources = generateSampleSources(3, 7, parameters), original = JSON.stringify(sources)
  let calls = 0
  const progress = []
  const result = await estimateSampleSources(sources, async () => {
    if (++calls === 2) throw new CalculationError('no finite solution', { rejected: true }, { solver: 'failed' }, { kind: 'solver' })
    return response
  }, { isCurrent: () => true, onProgress: (rows, value) => progress.push({ rows, ...value }) })
  assert.equal(calls, 3)
  assert.equal(result.length, 3)
  assert.equal(result[1].result, undefined)
  assert.equal(result[1].calculationError, 'no finite solution')
  assert.deepEqual(result[1].calculation, { rejected: true })
  assert.deepEqual(result[1].traceData, { solver: 'failed' })
  assert.equal(result[2].result, response.result)
  assert.ok(result.every((source, index) => source.data === sources[index].data))
  assert.equal(JSON.stringify(sources), original)
  assert.deepEqual(progress.map(value => value.completed), [0, 1, 2, 3])
  assert.equal(progress[0].rows[0].result, undefined)
})

test('inherited groups retain every observation independently and require fresh estimates', () => {
  const { generateSampleSources, inheritSampleSources } = loadBatch()
  const sources = generateSampleSources(3, 7, parameters).map(source => ({ ...source, ...response,
    calculationError: 'old failure', calculationOffset: .2, mdmOptimization: { old: true },
    fixedComparison: response.result, archive: { id: 'frozen', n: 7, delta: .1, runId: 1 } }))
  sources[1].data[2].status = 'S'
  const original = JSON.stringify(sources), inherited = inheritSampleSources(sources)
  assert.equal(inherited.length, 3)
  assert.equal(new Set(inherited.map(source => source.groupId)).size, 1)
  assert.notEqual(inherited[0].groupId, sources[0].groupId)
  assert.deepEqual(inherited.map(source => source.data), sources.map(source => source.data))
  assert.deepEqual(inherited.map(source => source.name), sources.map(source => source.name))
  for (const [index, source] of inherited.entries()) {
    assert.notEqual(source.id, sources[index].id)
    assert.notEqual(source.data, sources[index].data)
    assert.notEqual(source.generatedFrom, sources[index].generatedFrom)
    for (const field of ['result', 'traceData', 'calculation', 'calculationError', 'calculationOffset',
      'mdmOptimization', 'fixedComparison', 'archive']) assert.equal(source[field], undefined)
  }
  inherited[0].data[0].value = -1
  inherited[0].generatedFrom.gamma = -1
  assert.equal(JSON.stringify(sources), original)
  const another = inheritSampleSources(sources)
  assert.notEqual(another[0].groupId, inherited[0].groupId)
})

test('unusable success payloads retain the right diagnostic fields and never stale previous results', async () => {
  const { generateSampleSources, estimateSampleSources } = loadBatch()
  const sources = generateSampleSources(2, 7, parameters).map(source => ({ ...source, ...response, archive: { id: 'old' } }))
  const result = await estimateSampleSources(sources, async () => ({ ...response, result: { ...response.result, converged: false } }),
    { isCurrent: () => true, onProgress() {} })
  assert.ok(result.every(source => !source.result && !source.archive && source.calculationError))
  assert.equal(result[0].calculation, response.calculation)
  assert.equal(result[0].traceData, response.traceData)
})

test('a changed batch discards in-flight responses and stops remaining requests', async () => {
  const { generateSampleSources, estimateSampleSources } = loadBatch()
  let current = true, calls = 0, updates = 0
  const result = await estimateSampleSources(generateSampleSources(3, 7, parameters), async () => {
    calls++; current = false; return response
  }, { isCurrent: () => current, onProgress() { updates++ } })
  assert.equal(result, null)
  assert.equal(calls, 1)
  assert.equal(updates, 1)
})

test('process handoff reuses the actual records; refresh fallback retains exact observations', () => {
  const batch = loadBatch()
  const sources = batch.generateSampleSources(3, 7, parameters).map(source => ({ ...source, ...response }))
  const id = batch.storeCalculationBatch(sources, 'mdm', 2, .1, parameters)
  assert.equal(batch.readCalculationBatch(id, 'mdm').sources, sources)
  assert.equal(batch.readCalculationBatch(id, 'mle'), null)
  const anotherMethod = batch.readCalculationBatch(id, 'mle', true)
  assert.equal(anotherMethod.sources[0].data, sources[0].data)
  assert.ok(anotherMethod.sources.every(source => !source.result && !source.calculation && !source.traceData && !source.archive))
  const fresh = loadBatch()
  fresh.stored.set('weibull-calculation-batch:' + id, batch.stored.get('weibull-calculation-batch:' + id))
  const restored = fresh.readCalculationBatch(id, 'mdm')
  assert.equal(restored.activeIndex, 2)
  assert.deepEqual(restored.sources.map(source => source.data), sources.map(source => source.data))
  assert.ok(restored.sources.every(source => !source.calculation))
  fresh.stored.set('weibull-calculation-batch:broken', '{')
  assert.equal(fresh.readCalculationBatch('broken', 'mdm'), null)
})

test('workbook import joins by run id, preserves failure rows, and never changes archived values', () => {
  const { workbookSampleSources } = loadBatch()
  const book = { id: 'frozen', truth: [2, 1000, 500], groups: { 2: {
    samples: [[23, 610, 920], [7, 620, 950], [8, 630, 980]],
    resultRows: [[7, 1.7, 910, 550], [23, 2.1, 940, 560], [8, null, null, null]],
    blocks: [{ method: 'mdm', delta: .1, column: 1 }],
  } } }
  const original = JSON.stringify(book), sources = workbookSampleSources(book, 2, 'mdm', .1)
  assert.deepEqual(sources.map(source => source.archive.runId), [23, 7, 8])
  assert.deepEqual(sources[0].data.map(point => point.value), [610, 920])
  assert.equal(sources[0].result.beta, 2.1)
  assert.equal(sources[1].result.beta, 1.7)
  assert.equal(sources[2].result, undefined)
  assert.ok(sources[2].calculationError)
  assert.equal(JSON.stringify(book), original)
  assert.throws(() => workbookSampleSources(book, 2, 'mdm', .2))
})
