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

export const MDM_AI_SUPPORTED_SAMPLE_SIZES = Object.freeze([7, 10, 15, 20])

export function isMdmAiSampleSizeSupported(n: number): boolean {
  return MDM_AI_SUPPORTED_SAMPLE_SIZES.includes(n)
}

export function parseMdmOffsetMode(value: string | null | undefined): MdmOffsetMode {
  return value === 'ai' ? 'ai' : 'fixed'
}

export function buildMdmOptimizationDetailsHref(values: number[]): string {
  const params = new URLSearchParams({ data: values.join(',') })
  return `/ai/process-optimization/mdm?${params.toString()}`
}
