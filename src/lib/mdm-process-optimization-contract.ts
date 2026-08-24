export type MdmOffsetMode = 'fixed' | 'ai'

export interface MdmProcessOptimizationResult {
  model_n: number
  delta_grid: number[]
  predicted_loss_curve: number[]
  selected_index: number
  selected_delta: number
  selected_predicted_loss: number
  default_delta: number
  default_index: number
  default_predicted_loss: number
  model_source_commit: string
  model_sha256: string
  representation: string
}

export interface MdmOptimizationComparison {
  lossDifference: number
  predictedAccuracyChangePercent: number | null
}

export const MDM_AI_SUPPORTED_SAMPLE_SIZES = Object.freeze([7, 10, 15, 20])

export function isMdmAiSampleSizeSupported(n: number): boolean {
  return MDM_AI_SUPPORTED_SAMPLE_SIZES.includes(n)
}

export function parseMdmOffsetMode(value: string | null | undefined): MdmOffsetMode {
  return value === 'ai' ? 'ai' : 'fixed'
}

export function compareMdmOptimization(
  result: Pick<
    MdmProcessOptimizationResult,
    'selected_predicted_loss' | 'default_predicted_loss'
  >,
): MdmOptimizationComparison {
  const lossDifference = result.selected_predicted_loss - result.default_predicted_loss
  const predictedAccuracyChangePercent = result.default_predicted_loss > 0
    ? -lossDifference / result.default_predicted_loss * 100
    : null

  return { lossDifference, predictedAccuracyChangePercent }
}

export function formatSigned(value: number, digits: number, suffix = ''): string {
  const roundingThreshold = 0.5 * 10 ** -digits
  const roundedValue = Math.abs(value) < roundingThreshold ? 0 : value
  const sign = roundedValue < 0 ? '-' : '+'
  return `${sign}${Math.abs(roundedValue).toFixed(digits)}${suffix}`
}

export function buildMdmOptimizationDetailsHref(values: number[]): string {
  const params = new URLSearchParams({ data: values.join(',') })
  return `/ai/process-optimization/mdm?${params.toString()}`
}
