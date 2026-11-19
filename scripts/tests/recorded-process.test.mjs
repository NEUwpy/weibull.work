import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { loadServerModule } from './helpers/load-server-module.mjs'

const { recordedStepValues, readRegressionProcess, readWeightedProcess, readModifiedProcess } =
  loadServerModule('src/components/methods/recorded-process-data.ts')

test('looking at another regression changes conditional operands while the final regression stays selected', () => {
  const views = [
    { gamma: 0, slope: .25, intercept: 2, criterion: 10, selected: false, points: [{ x: 1, y: 2 }] },
    { gamma: 8, slope: .5, intercept: 3, criterion: 20, selected: true, points: [{ x: 1, y: 4 }] },
  ]
  const trace = { method: 'lse', selection: { gamma: 8, beta: 2, eta: 20 }, details: { regression_views: views } }
  const process = readRegressionProcess(trace, 0)
  assert.equal(process.view.gamma, 0)
  assert.equal(process.final.gamma, 8)
  const trial = recordedStepValues(trace, 'location', .9, process.view)
  const final = recordedStepValues(trace, 'regression', .9, process.view)
  assert.equal(trial.mu, '0')
  assert.equal(trial.slope, '0.25')
  assert.equal(trial.best_mu, '8')
  assert.equal(final.slope, '0.5')
  assert.equal(final.intercept, '3')
  assert.equal(final.shape, '2')
  assert.equal(final.scale, '20')
})

test('position correction shows the raw input and corrected output separately', () => {
  const trace = { method: 'mm', selection: { beta: 2, gamma: 0, eta: 8 },
    details: { raw_estimate: { beta: 2, gamma: -2, eta: 10 }, m1: 7, m2: 5, m4: 4 } }
  const values = recordedStepValues(trace, 'adjustment')
  assert.equal(values.location, '-2')
  assert.equal(values['output.location'], '0')
  assert.equal(values.scale, '10')
  assert.equal(values['output.scale'], '8')
})

test('weighted conditional shape uses the viewed position rather than the final candidate', () => {
  const trace = { method: 'wmle', selection: { beta: 2, gamma: 8, eta: 20 },
    details: { reading_frames: [
      { gamma: 0, beta: 3, t1: 1e-12, t2: .5, j3: 4, final: false },
      { gamma: 8, beta: 2, t1: 0, t2: 0, j3: 5, final: true },
    ] } }
  const viewed = readWeightedProcess(trace, 0)
  const values = recordedStepValues(trace, 'trial', undefined, undefined, viewed.frame)
  assert.equal(values.gamma, '0')
  assert.equal(values.beta, '3')
  assert.equal(values.j3, '4')
  assert.equal(readWeightedProcess(trace).frame.gamma, 8)
})

test('MMLE initial frame has no fabricated next iterate; stopping comparison follows the actual iterate', () => {
  const trace = JSON.parse(fs.readFileSync('src/data/method-process-examples/mmle.json', 'utf8')).calculation
  const initial = readModifiedProcess(trace, 0)
  assert.equal(initial.iteration, undefined)
  const initialValues = recordedStepValues(trace, 'shape', undefined, undefined, undefined, initial.iteration)
  assert.equal(initialValues.next_beta, '—')
  assert.match(initialValues.converged, /尚未执行/)
  const first = readModifiedProcess(trace, 1)
  const firstValues = recordedStepValues(trace, 'shape', undefined, undefined, undefined, first.iteration)
  assert.match(firstValues.converged, / > /)
  const last = readModifiedProcess(trace)
  const finalValues = recordedStepValues(trace, 'shape', undefined, undefined, undefined, last.iteration)
  assert.match(finalValues.converged, / ≤ /)
  assert.equal(Number(finalValues.next_beta), Number(trace.selection.beta.toPrecision(7)))
})

test('MMLE phase input and final output stay stable while inspecting internal iterations', () => {
  const trace = JSON.parse(fs.readFileSync('src/data/method-process-examples/mmle.json', 'utf8')).calculation
  const initial = readModifiedProcess(trace, 0)
  const final = readModifiedProcess(trace)
  const firstValues = recordedStepValues(trace, 'shape', undefined, undefined, undefined, initial.iteration)
  const finalValues = recordedStepValues(trace, 'shape', undefined, undefined, undefined, final.iteration)
  assert.equal(firstValues.final_beta, finalValues.final_beta)
  assert.equal(firstValues.iteration_settings, finalValues.iteration_settings)
  assert.equal(firstValues.process_status, finalValues.process_status)
  assert.notEqual(firstValues.beta, finalValues.beta)
})
