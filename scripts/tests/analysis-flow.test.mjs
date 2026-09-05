import test from 'node:test'
import assert from 'node:assert/strict'
import { createLatestRequestTracker } from '../../src/lib/latest-request.ts'
import { expandChunkParameters } from '../../src/lib/study-chunks.ts'
import { parseSimulationBatch, requestSimulation, simulationRange } from '../../src/lib/simulation-analysis.ts'

const input = { methodId: 'mdm', beta: 2, eta: 100, gamma: 5, n: 7, rep: 2, seed: 42, offset: 0.1 }
const goodRow = { method_id: 'mdm', beta_true: 2, eta_true: 100, gamma: 5, sample_size: 7, offset_value: 0.1,
  sim_id: 1, est_beta: 2, est_eta: 100, est_gamma: 5, status: 'success' }
const badRow = { ...goodRow, sim_id: 2, est_beta: null, est_eta: null, est_gamma: null, status: 'failure', error: 'solver failed' }
const payload = () => ({ rows: [{ ...goodRow }, { ...badRow }], metrics: {
  n_total: 2, n_valid: 1, n_failure: 1,
  param_standard: Object.fromEntries(['beta', 'eta', 'gamma'].map(key => [key, { absolute: { n: 1, bias: 0, sd: 0, rmse: 0, mae: 0 } }])),
} })

test('an old completion cannot overwrite edited input or a newer batch', async () => {
  const tracker = createLatestRequestTracker()
  let release
  let displayed = 'new input'
  const old = tracker.begin('card')
  const pending = new Promise(resolve => { release = resolve }).then(() => {
    if (tracker.isCurrent('card', old)) displayed = 'old estimate'
  })
  tracker.invalidate('card')
  const current = tracker.begin('card')
  release()
  await pending
  assert.equal(displayed, 'new input')
  assert.equal(tracker.isCurrent('card', current), true)
  tracker.clear()
  assert.equal(tracker.isCurrent('card', current), false)
})

test('multi-offset selection expands every selected combination once', () => {
  const combinations = expandChunkParameters({ beta: [2], n: [7, 10], d: [0.1, 0.2, 0.2] })
  assert.deepEqual(combinations, [
    { beta: 2, n: 7, d: 0.1 }, { beta: 2, n: 7, d: 0.2 },
    { beta: 2, n: 10, d: 0.1 }, { beta: 2, n: 10, d: 0.2 },
  ])
  assert.deepEqual(expandChunkParameters({ n: [7], d: [] }), [])
})

test('simulation keeps failed rows and the backend metric denominator', () => {
  const batch = parseSimulationBatch(payload(), input)
  assert.equal(batch.rows[1].status, 'failure')
  assert.equal(batch.rows[1].est_gamma, null)
  assert.equal(batch.metrics.n_valid, 1)
  const allFailed = payload()
  allFailed.rows = [{ ...badRow, sim_id: 1 }, { ...badRow }]
  allFailed.metrics = { n_total: 2, n_valid: 0, n_failure: 2 }
  assert.equal(parseSimulationBatch(allFailed, input).metrics.param_standard, undefined)
})

test('simulation rejects silently replaced methods, missing metrics and mismatched row identities', () => {
  for (const edit of [
    value => { value.rows[0].method_id = 'lre' },
    value => { delete value.metrics },
    value => { value.metrics.n_valid = 2 },
    value => { value.rows[0].sample_size = 10 },
    value => { value.rows[1].sim_id = 1 },
  ]) {
    const value = payload(); edit(value)
    assert.throws(() => parseSimulationBatch(value, input))
  }
})

test('network and backend failures never produce fallback estimates', async () => {
  const signal = new AbortController().signal
  await assert.rejects(() => requestSimulation(input, signal, async () => { throw new Error('network failed') }), /network failed/)
  await assert.rejects(() => requestSimulation(input, signal, async () => ({ ok: false, status: 429, json: async () => ({}) })), /繁忙/)
  await assert.rejects(() => requestSimulation({ ...input, rep: 1001 }, signal, async () => { throw new Error('must not fetch') }), /有效参数/)
})

test('ranges include the intended endpoint and reject unbounded or inverted scans', () => {
  assert.deepEqual(simulationRange(0, 0.3, 0.1), [0, 0.1, 0.2, 0.3])
  assert.throws(() => simulationRange(0, 1, 0))
  assert.throws(() => simulationRange(1, 0, 0.1))
  assert.throws(() => simulationRange(0, 0.5, 0.00001, 50))
})
