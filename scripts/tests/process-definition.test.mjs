import test from 'node:test'
import assert from 'node:assert/strict'
import { loadServerModule } from './helpers/load-server-module.mjs'

const { bindProcessChart } = loadServerModule('src/components/methods/ProcessDefinitionContext.tsx')

test('chart axes use the shared quantity definitions while keeping numerical evidence untouched', () => {
  const chart = { id: 'profile', x: { key: 'x', label: 'old x' }, y: { key: 'y', label: 'old y' },
    series: [{ points: [{ x: 1, y: 2 }] }], selected: [{ x: 1, y: 2 }] }
  const definition = { variables: { gamma: { axisLabel: '位置参数 γ' }, profile: { axisLabel: '剖面似然' } },
    chartBindings: { profile: { x: 'gamma', y: 'profile' } } }
  const bound = bindProcessChart(chart, definition)
  assert.equal(bound.x.label, '位置参数 γ')
  assert.equal(bound.y.label, '剖面似然')
  assert.equal(bound.series, chart.series)
  assert.equal(bound.selected, chart.selected)
  assert.equal(chart.x.label, 'old x')
})
