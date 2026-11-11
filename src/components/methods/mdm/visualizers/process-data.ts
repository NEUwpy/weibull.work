import type { CalculationTrace } from '../../../../lib/calculation-trace'

export interface ShapePoint { beta: number; sigma: number; evaluation?: number }
export interface ShapeSlice {
  gamma: number
  beta: number
  sigma: number
  eta?: number
  points: ShapePoint[]
  evaluatedPoints?: ShapePoint[]
}
export interface GradientPoint {
  gamma: number
  gradient: number
  sigma_min?: number
  best_beta?: number
  best_eta?: number
  source?: string
  evaluation?: number
}
export interface PseudoScaleValue {
  observation: number
  rank: number
  eta: number
  distance?: number
  rank_transform?: number
  denominator?: number
}

const record = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value)
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)

/** Focus the reading window without changing or interpolating function values. */
export function mdmGradientDomain(points: GradientPoint[], gamma: number, offset: number, full = false) {
  const xs = points.map(point => point.gamma).filter(finite)
  const left = Math.min(...xs, gamma)
  const right = Math.max(...xs, gamma)
  const span = right - left || Math.max(Math.abs(gamma), 1)
  const x: [number, number] = full
    ? [left, right > left ? right : left + span]
    : [Math.max(left, gamma - span * .025), Math.min(right, gamma + span * .025)]
  if (x[0] === x[1]) x[1] = x[0] + span * .025
  const ys = points.filter(point => point.gamma >= x[0] && point.gamma <= x[1])
    .map(point => point.gradient).filter(finite)
  const bottom = Math.min(...ys, offset)
  const top = Math.max(...ys, offset)
  const padding = (top - bottom || Math.max(Math.abs(offset), .1)) * .12
  return { x, y: [bottom - padding, top + padding] as [number, number] }
}

/** Read backend function samples and conditional minima; never estimate a new result. */
export function mdmProcessData(value: unknown, calculation: CalculationTrace) {
  if (!record(value)) return null
  const { gamma, beta, eta, sigma, target_offset: offset } = calculation.selection
  if (![gamma, beta, eta, sigma, offset].every(finite)) return null
  const selectedGamma = gamma as number
  const selectedBeta = beta as number
  const selectedSigma = sigma as number
  if (value.optimal_gamma !== selectedGamma || value.optimal_beta !== selectedBeta) return null
  // A right-edge extrapolation's virtual target is not an evaluated gradient.
  const legacyGradients: GradientPoint[] = (Array.isArray(value.grad_gamma_curve) ? value.grad_gamma_curve : [])
    .filter((point): point is Record<string, unknown> => record(point) && point.virtual !== true && point.source !== 'display_sample'
      && finite(point.gamma) && finite(point.gradient))
    .map(point => ({ gamma: point.gamma as number, gradient: point.gradient as number,
      sigma_min: finite(point.sigma_min) ? point.sigma_min : undefined,
      best_beta: finite(point.best_beta) ? point.best_beta : undefined,
      best_eta: finite(point.best_eta) ? point.best_eta : undefined,
      source: typeof point.source === 'string' ? point.source : undefined,
      evaluation: finite(point.evaluation) ? point.evaluation : undefined }))
    .sort((left, right) => left.gamma - right.gamma)
  const gradientMap = new Map(legacyGradients.map(point => [point.gamma, point]))
  const locationChart = calculation.charts.find(chart => chart.id === 'location-criterion')
  for (const series of locationChart?.series ?? []) {
    if (series.role !== 'solver') continue
    for (const point of series.points) {
      if (point.virtual === true || !finite(point.x) || !finite(point.y)) continue
      gradientMap.set(point.x, { ...gradientMap.get(point.x), gamma: point.x, gradient: point.y,
        source: 'solver_evaluation', evaluation: finite(point.evaluation) ? point.evaluation : undefined })
    }
  }
  const gradients = Array.from(gradientMap.values()).sort((left, right) => left.gamma-right.gamma)
  const gradientEvaluations = gradients.filter(point => ['trace_grid', 'solver_root', 'solver_evaluation'].includes(point.source ?? ''))

  const points = (items: unknown[]): ShapePoint[] => items
    .filter((point): point is Record<string, unknown> => record(point) && finite(point.beta) && finite(point.sigma))
    .map(point => ({ beta: point.beta as number, sigma: point.sigma as number,
      ...(finite(point.evaluation) ? { evaluation: point.evaluation } : {}) }))
  const withMinimum = (items: ShapePoint[], minimum: ShapePoint) =>
    Array.from(new Map([...items, minimum].map(point => [point.beta, point])).values())
      .sort((left, right) => left.beta - right.beta)

  const slices: ShapeSlice[] = []
  for (const surface of Array.isArray(value.sigma_beta_gamma) ? value.sigma_beta_gamma : []) {
    if (!record(surface) || !finite(surface.gamma) || !Array.isArray(surface.betas) || !Array.isArray(surface.sigmas)) continue
    const minimum = gradients.find(point => point.gamma === surface.gamma)
    if (!minimum || !finite(minimum.best_beta) || !finite(minimum.sigma_min)) continue
    const evaluatedPoints = points(Array.isArray(surface.solver_points) ? surface.solver_points : [])
    if (!evaluatedPoints.length) continue
    slices.push({ gamma: surface.gamma, beta: minimum.best_beta, sigma: minimum.sigma_min,
      eta: minimum.best_eta, points: withMinimum(evaluatedPoints, { beta: minimum.best_beta, sigma: minimum.sigma_min }),
      evaluatedPoints })
  }
  const solverSamples = calculation.charts.find(chart => chart.id === 'shape-discrepancy')?.series
    .filter(series => series.role === 'solver').flatMap(series => series.points.map(point => ({ beta: point.x, sigma: point.y,
      ...(finite(point.evaluation) ? { evaluation: point.evaluation } : {}) }))) ?? []
  const finalSlice: ShapeSlice = { gamma: selectedGamma, beta: selectedBeta, sigma: selectedSigma,
    eta: eta as number, points: withMinimum(solverSamples, { beta: selectedBeta, sigma: selectedSigma }), evaluatedPoints: solverSamples }
  const byGamma = new Map(slices.map(slice => [slice.gamma, slice]))
  byGamma.set(selectedGamma, finalSlice)
  const details = record(calculation.details) ? calculation.details : null
  const bracket = details?.root_bracket
  const interpolation = calculation.selection.solver === 'linear_interpolation' && record(bracket)
    && record(bracket.left) && record(bracket.right) && finite(bracket.left.gamma) && finite(bracket.left.gradient)
    && finite(bracket.right.gamma) && finite(bracket.right.gradient)
    ? {
      left: { gamma: bracket.left.gamma, gradient: bracket.left.gradient },
      right: { gamma: bracket.right.gamma, gradient: bracket.right.gradient },
      point: locationChart?.selected?.find(point => point.source === 'linear_interpolation' && point.x === selectedGamma),
      formula: locationChart?.formula,
    } : undefined
  const rawScales = details && Array.isArray(details.pseudo_scales) ? details.pseudo_scales : []
  const pseudoScales: PseudoScaleValue[] = rawScales.every(point => record(point)
    && finite(point.observation) && finite(point.rank) && point.rank > 0 && point.rank < 1 && finite(point.eta))
    ? rawScales.map(point => ({ observation: point.observation, rank: point.rank, eta: point.eta,
      distance: finite(point.distance) ? point.distance : undefined,
      rank_transform: finite(point.rank_transform) ? point.rank_transform : undefined,
      denominator: finite(point.denominator) ? point.denominator : undefined })) : []
  const scaleSum = details && finite(details.pseudo_scale_sum) ? details.pseudo_scale_sum : null
  return { gradients, gradientEvaluations, slices: Array.from(byGamma.values()).sort((left, right) => left.gamma - right.gamma),
    finalSlice, offset: offset as number, pseudoScales, scaleSum, interpolation,
    rankMethod: typeof details?.rank_method === 'string' ? details.rank_method : null }
}
