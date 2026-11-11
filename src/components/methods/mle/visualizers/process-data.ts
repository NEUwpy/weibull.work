import { type CalculationChart, type CalculationTrace, readPowerScaleCalculation, readCalculationTrace } from '@/lib/calculation-trace'

export interface MLEFrame {
  gamma: number; normalized_gamma: number; beta: number; eta: number; log_likelihood: number; location_score: number
  shape_score: number; shape_at_lower_boundary: boolean; evaluation: number; final: boolean; shape_chart: CalculationChart
}
export interface MLECandidate { gamma: number; beta: number; eta: number; ll: number; kind: string; location_score: number }
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)

/** Old supplementary plotting records cannot pass as actual solver views. */
export function mleProcessData(trace: CalculationTrace) {
  const details = trace.details
  if (!record(details) || details.actual_solver_views !== true || !Array.isArray(details.reading_frames)
    || !Array.isArray(details.candidates) || !Array.isArray(details.prepared_samples) || !finite(details.normalization_unit)) return null
  if (!details.reading_frames.every(frame => record(frame)
    && ['gamma', 'normalized_gamma', 'beta', 'eta', 'log_likelihood', 'location_score', 'shape_score', 'evaluation'].every(key => finite(frame[key]))
    && typeof frame.final === 'boolean' && typeof frame.shape_at_lower_boundary === 'boolean'
    && readCalculationTrace({ schema_version: 1, method: 'mle', criterion: trace.criterion, selection: trace.selection, charts: [frame.shape_chart] }, 'mle').trace)) return null
  if (!details.candidates.every(candidate => record(candidate) && ['gamma', 'beta', 'eta', 'll'].every(key => finite(candidate[key])))) return null
  if (!details.prepared_samples.every(sample => record(sample) && ['index', 'observation', 'normalized'].every(key => finite(sample[key])))) return null
  const frames = [...details.reading_frames as MLEFrame[]].sort((a, b) => a.gamma - b.gamma)
  const final = frames.find(frame => frame.final)
  const success = trace.selection.status === 'ok'
  if (success && (!final || frames.filter(frame => frame.final).length !== 1
    || !['gamma', 'beta', 'eta'].every(key => final[key as 'gamma' | 'beta' | 'eta'] === trace.selection[key]))) return null
  const scale = readPowerScaleCalculation(trace)
  if (success && !scale) return null
  return { frames, final, success, scale, unit: details.normalization_unit,
    samples: details.prepared_samples as { index: number; observation: number; normalized: number }[],
    candidates: details.candidates as MLECandidate[],
    supportLimit: details.support_boundary_limit as { beta: number; eta: number; gamma: number; log_likelihood: number } | null,
    limitExceedsSelected: details.boundary_limit_exceeds_selected === true }
}
