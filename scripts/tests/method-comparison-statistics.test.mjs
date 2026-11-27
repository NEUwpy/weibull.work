import test from 'node:test'
import assert from 'node:assert/strict'
import { loadServerModule } from './helpers/load-server-module.mjs'

const { summarizeMethodComparison } = loadServerModule('src/lib/method-comparison-statistics.ts')
const { parseSimulationBatch } = loadServerModule('src/lib/simulation-analysis.ts')
const input = { methodId: 'mdm', beta: 2, eta: 100, gamma: 5, n: 7, rep: 2, seed: 42, offset: 0.1 }
const good = { method_id: 'mdm', beta_true: 2, eta_true: 100, gamma: 5, sample_size: 7,
  offset_value: 0.1, sim_id: 1, est_beta: 2.5, est_eta: 100, est_gamma: 4, status: 'success' }
const failed = { ...good, sim_id: 2, est_beta: 40, est_gamma: 50, status: 'failure' }
const metrics = {
  n_total: 2, n_valid: 1, n_failure: 1,
  param_standard: Object.fromEntries(Object.entries({ beta: 0.5, eta: 0, gamma: -1 }).map(([key, bias]) =>
    [key, { absolute: { n: 1, bias, sd: 0, rmse: Math.abs(bias), mae: Math.abs(bias) } }])),
}

test('live failure with finite estimates stays in the denominator and out of the table and density', () => {
  const batch = parseSimulationBatch({ rows: [good, failed], metrics }, input)
  const stats = summarizeMethodComparison({ status: 'ready', source: 'simulation', ...batch })
  assert.equal(batch.rows[1].est_beta, 40)
  assert.equal(stats.count, 2)
  assert.equal(stats.includedCount, 1)
  assert.equal(stats.failures, 1)
  assert.equal(stats.parameters.beta.mean, 2.5)
  assert.equal(stats.parameters.gamma.bias, -1)
  assert.deepEqual(Array.from(stats.parameters.beta.values), [2.5])
})

test('all-failed live batch still reports its attempts and leaves estimate summaries empty', () => {
  const batch = parseSimulationBatch({ rows: [{ ...failed, sim_id: 1 }, failed],
    metrics: { n_total: 2, n_valid: 0, n_failure: 2 } }, input)
  const stats = summarizeMethodComparison({ status: 'ready', source: 'simulation', ...batch })
  assert.equal(stats.count, 2)
  assert.equal(stats.failures, 2)
  assert.equal(stats.parameters.beta.mean, null)
  assert.equal(stats.parameters.beta.sd, null)
  assert.equal(stats.parameters.beta.values.length, 0)
})

test('historical estimates support descriptive statistics without inventing a failure rate or truth', () => {
  const legacy = { ...good, status: undefined, gamma: undefined }
  const stats = summarizeMethodComparison({ status: 'ready', source: 'archive', filename: 'fixture.csv',
    rows: [legacy, { ...legacy, sim_id: 2, est_gamma: null }, { ...legacy, sim_id: 3, est_beta: 3.5 }] })
  assert.equal(stats.count, 3)
  assert.equal(stats.includedCount, 2)
  assert.equal(stats.failures, null)
  assert.equal(stats.parameters.beta.mean, 3)
  assert.equal(stats.parameters.beta.sd, Math.sqrt(0.5))
  assert.equal(stats.parameters.gamma.truth, null)
  assert.equal(stats.parameters.gamma.bias, null)
  assert.deepEqual(Array.from(stats.parameters.gamma.values), [4, 4])
})
