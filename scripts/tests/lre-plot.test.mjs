import test from 'node:test'
import assert from 'node:assert/strict'
import { calculateMedianRanks } from '../../src/lib/weibull.ts'

const observations = values => values.map((value, id) => ({ id, value, status: 'F' }))

test('LRE chart switches Park plotting positions at n=10/11', () => {
  for (const n of [10, 11]) {
    const data = observations(Array.from({ length: n }, (_, i) => n - i + 3))
    const points = calculateMedianRanks(data, 3, 'lre')
    const expectedFirst = n === 10 ? 0.625 / 10.25 : 0.5 / 11
    assert.equal(points[0].medianRank, expectedFirst)
    assert.equal(points[0].x, 0)
    assert.equal(points.at(-1).medianRank, 1 - expectedFirst)
    assert.equal(points[0].y, Math.log(-Math.log1p(-expectedFirst)))
  }
})

test('LRE probability plot agrees with the Park paper estimate and backend R squared', () => {
  const data = observations([
    30.94, 18.51, 16.62, 51.56, 22.85, 22.38, 19.08, 49.56,
    17.12, 10.67, 25.43, 10.24, 27.47, 14.70, 14.10, 29.93,
    27.98, 36.02, 19.40, 14.97, 22.57, 12.26, 18.14, 18.84,
  ])
  const beta = 1.3637606268, eta = 15.1160268653, gamma = 9.1976834666
  const points = calculateMedianRanks(data, gamma, 'lre')
  const mean = points.reduce((sum, p) => sum + p.y, 0) / points.length
  const residual = points.reduce((sum, p) => sum + (p.y - beta * (p.x - Math.log(eta))) ** 2, 0)
  const total = points.reduce((sum, p) => sum + (p.y - mean) ** 2, 0)
  assert.ok(Math.abs(1 - residual / total - 0.980557226558) < 1e-10)
})

test('Park sample size matches API failure filtering and other methods retain Bernard', () => {
  const data = [...observations([1, 2, 3]), { id: 3, value: 4, status: 'S' }]
  assert.equal(calculateMedianRanks(data, 0, 'lre')[0].medianRank, 0.625 / 3.25)
  assert.equal(calculateMedianRanks(data, 0, 'mle')[0].medianRank, 0.7 / 4.4)
  assert.deepEqual(calculateMedianRanks(data), calculateMedianRanks(data, 0, 'mle'))
})
