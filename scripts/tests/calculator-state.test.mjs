import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createDefaultParameterResult,
  generateWeibullSample,
  getDefaultParameters,
  getEstimateFailure,
  toggleParameterMode,
} from '../../src/lib/calculator-state.ts'

test('3P and 2P defaults use the approved parameters', () => {
  assert.deepEqual(getDefaultParameters(true), { beta: 2, eta: 1000, gamma: 1000 })
  assert.deepEqual(getDefaultParameters(false), { beta: 2, eta: 1000, gamma: 0 })
})

test('parameter mode preserves and restores the last 3P gamma', () => {
  const twoP = toggleParameterMode({ is3P: true, currentGamma: 750, last3PGamma: 1000 })
  assert.deepEqual(twoP, { is3P: false, gamma: 0, last3PGamma: 750 })

  const threeP = toggleParameterMode(twoP)
  assert.deepEqual(threeP, { is3P: true, gamma: 750, last3PGamma: 750 })
})

test('sample generation uses the current parameters', () => {
  const sample = generateWeibullSample(2, { beta: 2, eta: 1000, gamma: 1000 }, () => 0.5)
  const expected = 1000 + 1000 * Math.sqrt(-Math.log(0.5))
  assert.equal(sample.length, 2)
  assert.equal(sample[0].value, expected)
  assert.deepEqual(sample.map(({ id, status }) => ({ id, status })), [
    { id: 0, status: 'F' },
    { id: 1, status: 'F' },
  ])
})

test('invalid and non-converged estimates return explicit failures', () => {
  assert.equal(
    getEstimateFailure({ beta: null, eta: 100, gamma: 0 }),
    '参数估计未返回完整参数',
  )
  assert.equal(
    getEstimateFailure({ beta: 2, eta: 100, gamma: 0, converged: false }),
    '参数估计未收敛',
  )
  assert.equal(
    getEstimateFailure({ beta: 2, eta: 100, gamma: 0, converged: 'unbounded' }),
    '参数估计无解',
  )
  assert.equal(getEstimateFailure({ beta: 2, eta: 100, gamma: 0, converged: true }), null)
})

test('default parameter result is 3P manual-ready and uses current data points', () => {
  const points = [{ x: 1, y: 2, rank: 0.5, t: 3 }]
  const result = createDefaultParameterResult(
    [{ id: 0, value: 1200, status: 'F' }],
    () => points,
  )
  assert.deepEqual(result, {
    beta: 2,
    eta: 1000,
    gamma: 1000,
    rSquared: null,
    points,
    converged: true,
  })
})
