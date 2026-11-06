import test from 'node:test'
import assert from 'node:assert/strict'
import { mdmGradientDomain, mdmProcessData } from '../../src/components/methods/mdm/visualizers/process-data.ts'

function fixture(strategy = 'brent_root', approximate = false) {
  const calculation = {
    charts: [{ id: 'shape-discrepancy', series: [{ role: 'solver', points: [{ x: 2.1, y: 7 }] }] }],
    selection: { gamma: 10, beta: 2.1, eta: 100, sigma: 7, target_offset: .1, strategy, approximate },
  }
  const trace = {
    optimal_gamma: 10, optimal_beta: 2.1,
    sigma_beta_curve: [{ beta: 2, sigma: 9 }, { beta: 3, sigma: 12 }],
    sigma_beta_gamma: [{ gamma: 0, betas: [1, 2, 3], sigmas: [15, 10, 18],
      solver_points: [{ beta: 1, sigma: 15 }, { beta: 2, sigma: 10 }, { beta: 3, sigma: 18 }] }],
    grad_gamma_curve: [
      { gamma: 10, gradient: .1, best_beta: 2.1, sigma_min: 7, best_eta: 100, virtual: approximate },
      { gamma: 0, gradient: -.2, best_beta: 1.8, sigma_min: 8, best_eta: 110 },
    ],
  }
  return { trace, calculation }
}

test('MDM linked slices use exact backend conditional minima and final position', () => {
  const { trace, calculation } = fixture()
  const before = JSON.stringify({ trace, calculation })
  const model = mdmProcessData(trace, calculation)
  assert.equal(model.finalSlice.gamma, 10)
  assert.deepEqual(model.finalSlice.points.find(point => point.beta === 2.1), { beta: 2.1, sigma: 7 })
  assert.deepEqual(model.slices[0], { gamma: 0, beta: 1.8, sigma: 8, eta: 110,
    points: [{ beta: 1, sigma: 15 }, { beta: 1.8, sigma: 8 }, { beta: 2, sigma: 10 }, { beta: 3, sigma: 18 }],
    evaluatedPoints: trace.sigma_beta_gamma[0].solver_points })
  assert.deepEqual(model.gradients.map(point => point.gamma), [0, 10])
  assert.equal(JSON.stringify({ trace, calculation }), before)
})

test('MDM extrapolated target never becomes a gradient value or crossing', () => {
  const { trace, calculation } = fixture('brent_root', true)
  const model = mdmProcessData(trace, calculation)
  assert.equal(model.finalSlice.gamma, 10)
  assert.deepEqual(model.gradients.map(point => point.gamma), [0])
})

test('MDM zero location remains the exact final slice', () => {
  const { trace, calculation } = fixture('truncated_at_zero')
  calculation.selection.gamma = trace.optimal_gamma = 0
  const model = mdmProcessData(trace, calculation)
  assert.equal(model.slices.filter(slice => slice.gamma === 0).length, 1)
  assert.equal(model.finalSlice.beta, calculation.selection.beta)
  assert.equal(model.finalSlice.eta, calculation.selection.eta)
})

test('MDM does not combine samples from a different calculation', () => {
  const { trace, calculation } = fixture()
  trace.optimal_gamma = 9
  assert.equal(mdmProcessData(trace, calculation), null)
})

test('MDM scale display preserves each sample, probability and backend calculation operands', () => {
  const { trace, calculation } = fixture()
  calculation.details = { pseudo_scales: [
    { observation: 20, rank: .25, distance: 10, rank_transform: .287682, denominator: .5, eta: 20 },
    { observation: 50, rank: .75, distance: 40, rank_transform: 1.386294, denominator: 2, eta: 20 },
  ], pseudo_scale_sum: 40 }
  const before = JSON.stringify(calculation)
  const model = mdmProcessData(trace, calculation)
  assert.deepEqual(model.pseudoScales, calculation.details.pseudo_scales)
  assert.equal(model.scaleSum, 40)
  assert.equal(JSON.stringify(calculation), before)
})

test('MDM old scale records still display sample values without inventing missing operands', () => {
  const { trace, calculation } = fixture()
  calculation.details = { pseudo_scales: [{ observation: 20, rank: .25, eta: 100 }] }
  const model = mdmProcessData(trace, calculation)
  assert.equal(model.pseudoScales[0].observation, 20)
  assert.equal(model.pseudoScales[0].eta, 100)
  assert.equal(model.pseudoScales[0].denominator, undefined)
  assert.equal(model.scaleSum, null)
})

test('MDM draws actual solver points and excludes old supplementary drawing samples', () => {
  const { trace, calculation } = fixture()
  trace.grad_gamma_curve[0].source = 'solver_root'
  trace.grad_gamma_curve[1].source = 'trace_grid'
  trace.grad_gamma_curve.push({ gamma: 5, gradient: -.1, source: 'display_sample' })
  calculation.charts.push({ id: 'location-criterion', series: [
    { role: 'solver', points: [{ x: 8, y: .05, evaluation: 3 }, { x: 10, y: .1, evaluation: 4 }] },
    { role: 'virtual', points: [{ x: 12, y: .1, virtual: true }] },
  ] })
  trace.sigma_beta_gamma[0].solver_points = [{ beta: 1.8, sigma: 8 }]
  const before = JSON.stringify({ trace, calculation })
  const model = mdmProcessData(trace, calculation)
  assert.deepEqual(model.gradientEvaluations.map(point => point.gamma), [0, 8, 10])
  assert.deepEqual(model.gradients.map(point => point.gamma), [0, 8, 10])
  assert.equal(model.gradientEvaluations.find(point => point.gamma === 8).evaluation, 3)
  assert.deepEqual(model.finalSlice.evaluatedPoints, [{ beta: 2.1, sigma: 7 }])
  assert.deepEqual(model.finalSlice.points, [{ beta: 2.1, sigma: 7 }])
  assert.deepEqual(model.slices[0].points, [{ beta: 1.8, sigma: 8 }])
  assert.deepEqual(model.slices[0].evaluatedPoints, [{ beta: 1.8, sigma: 8 }])
  assert.equal(JSON.stringify({ trace, calculation }), before)
})

test('MDM reading window reveals the crossing without a distant peak stretching its axes', () => {
  const points = [
    { gamma: 0, gradient: -.02 }, { gamma: 990, gradient: -.18 },
    { gamma: 1002, gradient: .006 }, { gamma: 1006, gradient: .14 },
    { gamma: 1020, gradient: .22 }, { gamma: 1290, gradient: 2 },
    { gamma: 1314, gradient: 1.76 },
  ]
  const before = JSON.stringify(points)
  const focused = mdmGradientDomain(points, 1006, .14)
  assert.ok(focused.x[0] < 990 && focused.x[1] > 1020)
  assert.ok(focused.x[0] > 0 && focused.x[1] < 1290)
  assert.ok(focused.y[0] < -.18 && focused.y[1] > .22 && focused.y[1] < 2)
  const full = mdmGradientDomain(points, 1006, .14, true)
  assert.deepEqual(full.x, [0, 1314])
  assert.ok(full.y[1] > 2)
  assert.equal(JSON.stringify(points), before)
})

test('MDM reading windows stay finite at the nonnegative boundary and for a single function point', () => {
  for (const [points, gamma] of [
    [[{ gamma: 0, gradient: .2 }, { gamma: 100, gradient: .5 }], 0],
    [[{ gamma: 10, gradient: .2 }], 10],
  ]) {
    for (const full of [true, false]) {
      const domain = mdmGradientDomain(points, gamma, .2, full)
      assert.ok(domain.x.every(Number.isFinite) && domain.y.every(Number.isFinite))
      assert.ok(domain.x[0] <= gamma && gamma <= domain.x[1])
      assert.ok(domain.x[0] >= 0 && domain.x[0] < domain.x[1])
      assert.ok(domain.y[0] < .2 && .2 < domain.y[1])
    }
  }
})
