import { formatCalculationNumber as number, readPowerScaleCalculation, type CalculationChart, type CalculationPoint, type CalculationTrace } from '@/lib/calculation-trace'
import type { FlowChartTarget } from '@/lib/method-flow'

export interface RegressionView {
  gamma: number; criterion: number; slope: number; intercept: number; beta: number; eta: number; selected: boolean
  distance_precision_note?: boolean
  points: { x: number; y: number; fit: number; observation?: number; distance?: number; probability?: number }[]
  calculation?: { count: number; x_mean: number; y_mean: number; sxx: number; syy: number; sxy: number; residual_sum: number }
}
export interface WeightedFrame {
  gamma: number; beta: number; eta: number; final: boolean; t1?: number; t2?: number; j3?: number; shape_chart: CalculationChart
}
export interface ShapeIteration {
  iteration: number; shape_before: number; shape_after: number; log_sum: number; weighted_log_mean: number
  numerator: number; denominator: number; shape_step: number
}
export interface RecordedDetails {
  normalization_unit?: number
  prepared_samples?: { index: number; observation: number; normalized: number }[]
  weight_values?: { n: number; j1: number; j2: number; j3: number; shape: number; j3_clamped: boolean }
  reading_frames?: WeightedFrame[]
  equation_calculation?: { mean_log: number; log_sum: number; weighted_log_mean: number; inverse_mean: number; power_ratio: number; shape_weight: number }
  candidates?: { beta: number; gamma: number; eta: number; objective: number; t1: number; t2: number; kind: string }[]
  regression_views?: RegressionView[]
  original_regression?: RegressionView
  order_statistic_means?: number[]
  evaluations?: CalculationPoint[]
  slope?: number; intercept?: number
  m1?: number; m2?: number; m4?: number
  raw_estimate?: { beta: number; eta: number; gamma: number }
  formula_values?: { d12: number; d24: number; shape_denominator: number; location_numerator: number; location_denominator: number; gamma_function: number; minimum: number }
  location_adjustment?: string | null
  location_calculation?: { alternative: number | null; sample_size: number; sample_size_root: number; final_scale_numerator: number }
  two_param_shape?: number | null; two_param_scale?: number | null
  initial_shape?: number; max_iterations?: number; shape_absolute_step_tolerance?: number; final_shape_step?: number
  profile_frames?: CalculationPoint[]; shape_iterations?: ShapeIteration[]; shifted_observations?: number[]
}
export const recordedDetails = (trace: CalculationTrace) => (trace.details ?? {}) as RecordedDetails
export const recordedRun = (trace: CalculationTrace) => trace.run as { id: string; observations: number[]; parameters: Record<string, unknown> } | undefined
export const vectorSummary = (values?: number[]) => !values?.length ? '—'
  : values.slice(0, 3).map(number).join('，') + (values.length > 3 ? '，…' : '') + '（' + values.length + ' 项）'

export function readRegressionProcess(trace: CalculationTrace, requested?: number | null) {
  const details = recordedDetails(trace)
  const views = details.regression_views ?? []
  const finalIndex = views.findIndex(view => view.selected)
  const index = Math.max(0, Math.min(requested ?? finalIndex, views.length - 1))
  return { views, final: views[finalIndex], view: views[index], index, finalIndex, original: details.original_regression }
}
export function readWeightedProcess(trace: CalculationTrace, requested?: number | null) {
  const frames = recordedDetails(trace).reading_frames ?? []
  const finalIndex = Math.max(0, frames.findIndex(frame => frame.final))
  const index = Math.max(0, Math.min(requested ?? finalIndex, frames.length - 1))
  return { frames, frame: frames[index], index, finalIndex }
}
export function readModifiedProcess(trace: CalculationTrace, requested?: number | null) {
  const details = recordedDetails(trace)
  const frames = details.profile_frames ?? []
  const index = Math.max(0, Math.min(requested ?? frames.length - 1, frames.length - 1))
  const frame = frames[index]
  return { frames, frame, index, iteration: details.shape_iterations?.find(item => item.iteration === frame?.iteration) }
}

/** Format the operands already owned by this run; input/output namespaces keep corrections distinct. */
export function recordedStepValues(trace: CalculationTrace, target: FlowChartTarget | undefined, rSquared?: number | null,
  viewedRegression?: RegressionView, viewedWeighted?: WeightedFrame, iteration?: ShapeIteration): Record<string, string> {
  const d = recordedDetails(trace), s = trace.selection, run = recordedRun(trace), samples = run?.observations ?? []
  const scale = readPowerScaleCalculation(trace)
  const finalRegression = readRegressionProcess(trace).final
  const regression = target === 'location' ? viewedRegression ?? finalRegression : finalRegression
  const frame = viewedWeighted ?? readWeightedProcess(trace).frame
  const raw = d.raw_estimate
  const values: Record<string, string> = {
    data: vectorSummary(samples), t: vectorSummary(samples), x: vectorSummary(samples), 'self.data': vectorSummary(samples),
    n: String(samples.length), unit: number(d.normalization_unit), z: vectorSummary(d.prepared_samples?.map(p => p.normalized)),
    beta: number(s.beta), eta: number(s.eta), gamma: number(s.gamma), gamma_val: number(s.gamma), gamma_hat: number(s.gamma),
    shape: number(s.beta), scale: number(s.eta), location: number(s.gamma),
    beta_hat: number(s.beta), eta_hat: number(s.eta), best_mu: number(s.gamma),
    r2: number(rSquared), return: number(rSquared),
    final_beta: number(s.beta), final_eta: number(s.eta), final_gamma: number(s.gamma), r_squared: number(rSquared),
    process_status: s.status === 'ok' ? '已采纳' : String(s.description ?? s.status ?? '未获得结果'),
    raw_beta: number(raw?.beta), raw_gamma: number(raw?.gamma), raw_eta: number(raw?.eta), minimum: number(d.formula_values?.minimum ?? samples[0]),
    final_slope: number(finalRegression?.slope), final_intercept: number(finalRegression?.intercept),
    m1: number(d.m1), m2: number(d.m2), m4: number(d.m4),
  }
  if (trace.method === 'wmle') Object.assign(values, {
    weight: number(d.weight_values?.j2), j1: number(d.weight_values?.j1), j2: number(d.weight_values?.j2),
    j3: number(target === 'trial' || target === 'location' ? frame?.j3 : d.weight_values?.j3),
    candidates: String(d.candidates?.length ?? 0) + ' 个接受候选',
    best: 'β̂ = ' + number(s.beta) + '，γ̂ = ' + number(s.gamma),
    t1: number(s.t1), t2: number(s.t2), objective: number(s.objective),
    trial_gamma: number(frame?.gamma), trial_beta: number(frame?.beta), trial_eta: number(frame?.eta),
  })
  if (trace.method === 'wmle' && (target === 'trial' || target === 'location')) Object.assign(values, {
    gamma: number(frame?.gamma), beta: number(frame?.beta), eta: number(frame?.eta),
    t1: number(frame?.t1), t2: number(frame?.t2), 'score(beta)': number(frame?.t1),
    'output.gamma': target === 'location' ? number(s.gamma) : number(frame?.gamma),
  })
  if (trace.method === 'lse' || trace.method === 'lre') Object.assign(values, {
    X: vectorSummary(finalRegression?.points.map(p => p.x)),
    y: vectorSummary(finalRegression?.points.map(p => p.y)),
    F: vectorSummary(finalRegression?.points.map(p => p.probability!).filter(Number.isFinite)),
    value: vectorSummary(d.order_statistic_means),
    slope: number(regression?.slope), intercept: number(regression?.intercept),
    's_y2 / s_res2': number(regression?.criterion), criterion: number(regression?.criterion),
    mu: number(regression?.gamma), x_vals: vectorSummary(finalRegression?.points.map(p => p.x)),
  })
  if (trace.method === 'mm') Object.assign(values, {
    shape: number(raw?.beta), location: number(raw?.gamma), scale: number(raw?.eta),
    'output.location': target === 'adjustment' ? number(s.gamma) : number(raw?.gamma),
    'output.scale': target === 'adjustment' ? number(s.eta) : number(raw?.eta),
    two_param_shape: number(d.two_param_shape), two_param_scale: number(d.two_param_scale),
  })
  if (trace.method === 'mmle') Object.assign(values, {
    initial_shape: number(d.initial_shape), tolerance: number(d.shape_absolute_step_tolerance), max_iterations: number(d.max_iterations),
    iteration_settings: '初值 ' + number(d.initial_shape) + '；容差 ' + number(d.shape_absolute_step_tolerance) + '；上限 ' + number(d.max_iterations),
    y: vectorSummary(d.shifted_observations), q: String(scale?.count ?? Math.max(0, samples.length - 1)),
    beta: number(target === 'shape' ? iteration?.shape_before ?? d.initial_shape : s.beta),
    next_beta: number(iteration?.shape_after), converged: iteration
      ? number(iteration.shape_step) + (iteration.shape_step <= (d.shape_absolute_step_tolerance ?? 0) ? ' ≤ ' : ' > ') + number(d.shape_absolute_step_tolerance)
      : '初始值，尚未执行更新',
    logs: 'Σ ln yᵢ = ' + number(d.shape_iterations?.at(-1)?.log_sum),
    last_solution_info: String(s.status), return: 'β̂ = ' + number(s.beta) + '，η̂ = ' + number(s.eta) + '，γ̂ = ' + number(s.gamma),
    'beta, eta, gamma': 'β̂ = ' + number(s.beta) + '，η̂ = ' + number(s.eta) + '，γ̂ = ' + number(s.gamma),
  })
  return values
}
