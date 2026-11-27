import { requestSimulation, type SimulationBatch } from './simulation-analysis'

export type MethodComparisonParams = {
  beta: number
  eta: number
  gamma: number
  n: number
  rep: number
  seed: number
  offset: number
  step: number
}

export interface MethodComparisonRow {
  beta_true: number
  eta_true: number
  gamma?: number
  sample_size: number
  offset_value?: number | null
  sim_id: number
  est_beta: number | null
  est_eta: number | null
  est_gamma: number | null
  bias_beta: number | null
  bias_eta: number | null
  bias_gamma: number | null
  r_squared: number | null
}

export async function requestMethodComparisonSimulation(
  methodId: string,
  { beta, eta, gamma, n, rep, seed, offset }: MethodComparisonParams,
  signal: AbortSignal,
  request: typeof fetch = fetch
): Promise<SimulationBatch> {
  return requestSimulation({
    methodId, beta, eta, gamma, n, rep, seed,
    offset: methodId.toLowerCase() === 'mdm' ? offset : undefined,
  }, signal, request)
}
