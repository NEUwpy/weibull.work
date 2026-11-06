/** Backend-owned numerical evidence for one method execution. */
export interface CalculationPoint {
  x: number
  y: number
  label?: string
  [key: string]: unknown
}

export interface CalculationSeries {
  id: string
  label: string
  kind: 'line' | 'scatter'
  role: 'solver' | 'diagnostic' | 'candidate' | 'virtual'
  points: CalculationPoint[]
  interpolation?: 'linear' | 'stepAfter'
}

export interface CalculationChart {
  id: string
  title: string
  description?: string
  formula?: string
  x: { key: string; label: string }
  y: { key: string; label: string }
  series: CalculationSeries[]
  references?: { axis: 'x' | 'y'; value: number; label: string }[]
  selected?: CalculationPoint[]
}

export interface CalculationTrace {
  schema_version: 1
  method: string
  title?: string
  criterion: { description: string; [key: string]: unknown }
  charts: CalculationChart[]
  selection: {
    description: string
    beta?: number | null
    eta?: number | null
    gamma?: number | null
    [key: string]: unknown
  }
  details?: unknown
  recovery?: { title: string; formula: string; values: { label: string; value: number }[] }[]
  [key: string]: unknown
}

export interface CalculationFocus {
  x: [number, number]
  y: [number, number]
}

export interface PowerScaleCalculation {
  beta: number; gamma: number; eta: number; count: number; normalizer: number; divisor: number
  power_sum: number | null; power_mean: number | null
  reference_distance: number; scaled_sum: number; scaled_mean: number; scale_factor: number
  use_scaled: boolean
  samples: { index: number; observation: number; distance: number; power: number | null; scaled_power: number }[]
}

/** An older or partial record must not silently omit sample contributions. */
export function readPowerScaleCalculation(trace: CalculationTrace): PowerScaleCalculation | null {
  if (!isRecord(trace.details) || !isRecord(trace.details.scale_calculation)) return null
  const value = trace.details.scale_calculation
  const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
  if (!['beta', 'gamma', 'eta', 'count', 'normalizer', 'divisor', 'reference_distance',
    'scaled_sum', 'scaled_mean', 'scale_factor'].every(key => finite(value[key]))
    || !['power_sum', 'power_mean'].every(key => value[key] === null || finite(value[key]))
    || typeof value.use_scaled !== 'boolean' || !Array.isArray(value.samples)
    || value.samples.length !== value.count || !value.samples.length
    || (!value.use_scaled && (value.power_sum === null || value.power_mean === null
      || value.samples.some(point => !isRecord(point) || point.power === null)))
    || !['beta', 'gamma', 'eta'].every(key => value[key] === trace.selection[key])
    || !value.samples.every(point => isRecord(point)
      && ['index', 'observation', 'distance', 'scaled_power'].every(key => finite(point[key]))
      && (point.power === null || finite(point.power)))) return null
  return value as unknown as PowerScaleCalculation
}

/** Viewport-only zoom: all original points remain in the backend trace. */
export function calculationFocus(chart: CalculationChart): CalculationFocus | null {
  const selected = chart.selected?.[0]
  if (!selected) return null
  const points = [...chart.series.flatMap(series => series.points), ...chart.selected!]
  const xValues = Array.from(new Set(points.map(point => point.x))).sort((left, right) => left - right)
  if (xValues.length < 3) return null
  const selectedIndex = xValues.indexOf(selected.x)
  const radius = Math.max(2, Math.ceil(xValues.length * 0.1))
  const left = xValues[Math.max(0, selectedIndex - radius)]
  const right = xValues[Math.min(xValues.length - 1, selectedIndex + radius)]
  if (left === right) return null
  const visibleY = points.filter(point => point.x >= left && point.x <= right).map(point => point.y)
  for (const reference of chart.references ?? []) {
    if (reference.axis === 'y') visibleY.push(reference.value)
  }
  const lower = Math.min(...visibleY)
  const upper = Math.max(...visibleY)
  const padding = (upper - lower) * 0.08 || Math.max(Math.abs(lower) * 0.08, 1e-12)
  return { x: [left, right], y: [lower - padding, upper + padding] }
}

type TraceReadResult =
  | { trace: CalculationTrace; error: null }
  | { trace: null; error: 'missing' | 'invalid' | 'method_mismatch' }

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function isPoint(value: unknown): value is CalculationPoint {
  return isRecord(value) && typeof value.x === 'number' && Number.isFinite(value.x)
    && typeof value.y === 'number' && Number.isFinite(value.y)
}

function isChart(value: unknown): value is CalculationChart {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.title !== 'string'
    || !isRecord(value.x) || typeof value.x.label !== 'string'
    || !isRecord(value.y) || typeof value.y.label !== 'string'
    || !Array.isArray(value.series)) return false

  if (!value.series.every(series => isRecord(series)
    && typeof series.id === 'string' && typeof series.label === 'string'
    && (series.kind === 'line' || series.kind === 'scatter')
    && ['solver', 'diagnostic', 'candidate', 'virtual'].includes(String(series.role))
    && (series.interpolation === undefined || ['linear', 'stepAfter'].includes(String(series.interpolation)))
    && Array.isArray(series.points) && series.points.every(isPoint))) return false

  if (value.selected !== undefined
    && (!Array.isArray(value.selected) || !value.selected.every(isPoint))) return false

  return value.references === undefined || (Array.isArray(value.references)
    && value.references.every(reference => isRecord(reference)
      && (reference.axis === 'x' || reference.axis === 'y')
      && typeof reference.value === 'number' && Number.isFinite(reference.value)
      && typeof reference.label === 'string'))
}

/** Validate evidence without inventing, rounding, sorting, or dropping points. */
export function readCalculationTrace(value: unknown, expectedMethod?: string): TraceReadResult {
  if (value === null || value === undefined) return { trace: null, error: 'missing' }
  if (!isRecord(value) || value.schema_version !== 1 || typeof value.method !== 'string'
    || !isRecord(value.criterion) || typeof value.criterion.description !== 'string'
    || !isRecord(value.selection) || typeof value.selection.description !== 'string'
    || !Array.isArray(value.charts) || !value.charts.every(isChart)) {
    return { trace: null, error: 'invalid' }
  }
  if (expectedMethod && value.method.toLowerCase() !== expectedMethod.toLowerCase()) {
    return { trace: null, error: 'method_mismatch' }
  }
  if (value.recovery !== undefined && (!Array.isArray(value.recovery) || !value.recovery.every(step =>
    isRecord(step) && typeof step.title === 'string' && typeof step.formula === 'string'
    && Array.isArray(step.values) && step.values.every(item => isRecord(item)
      && typeof item.label === 'string' && typeof item.value === 'number' && Number.isFinite(item.value))))) {
    return { trace: null, error: 'invalid' }
  }
  for (const key of ['beta', 'eta', 'gamma']) {
    const parameter = value.selection[key]
    if (parameter !== undefined && parameter !== null
      && (typeof parameter !== 'number' || !Number.isFinite(parameter))) {
      return { trace: null, error: 'invalid' }
    }
  }
  return { trace: value as unknown as CalculationTrace, error: null }
}

/** Old traces remain available as records, but are never promoted to a new run. */
export function embeddedCalculationTrace(trace: unknown): unknown {
  if (isRecord(trace)) return trace.calculation
  if (Array.isArray(trace)) {
    const record = trace.findLast(item => isRecord(item) && item.phase === 'calculation')
    return isRecord(record) ? record.calculation : undefined
  }
  return undefined
}

export function formatCalculationNumber(value: unknown): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
  if (value !== 0 && (Math.abs(value) >= 1e7 || Math.abs(value) < 1e-5)) {
    return value.toExponential(4)
  }
  return value.toLocaleString('zh-CN', { maximumSignificantDigits: 7, useGrouping: false })
}
