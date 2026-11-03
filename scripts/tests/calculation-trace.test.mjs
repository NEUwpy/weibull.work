import test from 'node:test'
import assert from 'node:assert/strict'
import { calculationFocus, readCalculationTrace } from '../../src/lib/calculation-trace.ts'

const evidence = () => ({
  schema_version: 1, method: 'mle',
  criterion: { description: '接受候选中选择最大似然' },
  selection: { description: '选择内点候选', beta: 2, eta: 1000, gamma: 5 },
  charts: [{
    id: 'likelihood', title: '剖面对数似然', x: { key: 'x', label: 'γ' }, y: { key: 'y', label: 'ℓ' },
    series: [{ id: 'profile', label: '实际求值', kind: 'line', role: 'solver', points: [
      { x: 0, y: -10 }, { x: 3, y: -2 }, { x: 5, y: -1 }, { x: 6, y: -2 }, { x: 7, y: -4 },
      { x: 8, y: -1e15 }, { x: 9, y: -1e17 }, { x: 10, y: -1e19 },
    ] }], selected: [{ x: 5, y: -1, label: '最终选择' }],
  }],
})

test('a plot consumes the original backend evidence without rewriting values', () => {
  const source = evidence()
  const json = JSON.stringify(source)
  const result = readCalculationTrace(source, 'mle')
  assert.equal(result.trace, source)
  assert.equal(JSON.stringify(source), json)
  assert.equal(result.trace.charts[0].series[0].points.at(-1).y, -1e19)
})

test('wrong-method and incomplete records are not drawn as another run', () => {
  assert.equal(readCalculationTrace(evidence(), 'wmle').error, 'method_mismatch')
  const source = evidence()
  source.charts[0].series[0].points[0].y = NaN
  assert.equal(readCalculationTrace(source, 'mle').error, 'invalid')
  assert.equal(readCalculationTrace(null, 'mle').error, 'missing')
})

test('axis focus retains selected coordinates and never mutates complete observations', () => {
  const chart = evidence().charts[0]
  const json = JSON.stringify(chart)
  const focus = calculationFocus(chart)
  assert.ok(focus)
  assert.ok(focus.x[0] <= 5 && focus.x[1] >= 5)
  assert.ok(focus.y[0] <= -1 && focus.y[1] >= -1)
  assert.equal(JSON.stringify(chart), json)
})

test('parameter recovery rejects nonfinite evidence and keeps empirical step interpolation', () => {
  const source = evidence()
  source.recovery = [{ title: '尺度恢复', formula: '\\hat\\eta=e^a', values: [{ label: 'η̂', value: 1000 }] }]
  source.charts[0].series[0].interpolation = 'stepAfter'
  assert.equal(readCalculationTrace(source).trace, source)
  source.recovery[0].values[0].value = Infinity
  assert.equal(readCalculationTrace(source).error, 'invalid')
})
