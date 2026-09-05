export type AnalysisMode = 'single' | 'range' | 'offset'
export type AnalysisParameter = 'beta' | 'eta' | 'gamma'

export interface SimulationRow {
  sim_id: number
  method_id: string
  beta_true: number
  eta_true: number
  gamma: number
  sample_size: number
  offset_value?: number | null
  est_beta: number | null
  est_eta: number | null
  est_gamma: number | null
  status: 'success' | 'failure'
  error?: string | null
}

export interface ParameterMetrics {
  n: number
  bias: number
  sd: number
  rmse: number
  mae: number
}

export interface SimulationMetrics {
  n_total: number
  n_valid: number
  n_failure: number
  param_standard?: Record<AnalysisParameter, { absolute: ParameterMetrics }>
}

export interface SimulationBatch {
  sampleSize: number
  offset?: number
  rows: SimulationRow[]
  metrics: SimulationMetrics
}

export interface SimulationInput {
  methodId: string
  beta: number
  eta: number
  gamma: number
  n: number
  rep: number
  seed: number
  offset?: number
}

export function simulationRange(min: number, max: number, step: number, limit = 500): number[] {
  if (![min, max, step].every(Number.isFinite) || step <= 0 || max < min) {
    throw new Error('范围必须从小到大，且步长必须大于 0')
  }
  const count = Math.floor((max - min) / step + 1e-9) + 1
  if (count > limit) throw new Error(`一次最多选择 ${limit} 个设计单元`)
  return Array.from({ length: count }, (_, i) => Number((min + i * step).toFixed(8)))
}

/** Keep every row; the backend is the authority for validity and aggregation. */
export function parseSimulationBatch(payload: unknown, input: SimulationInput): SimulationBatch {
  const value = payload as { rows?: SimulationRow[]; metrics?: SimulationMetrics } | null
  const rows = value?.rows
  const metrics = value?.metrics
  if (!Array.isArray(rows) || !metrics ||
      ![metrics.n_total, metrics.n_valid, metrics.n_failure].every(n => Number.isInteger(n) && n >= 0) ||
      metrics.n_total !== input.rep || rows.length !== metrics.n_total ||
      metrics.n_valid + metrics.n_failure !== metrics.n_total) {
    throw new Error('模拟响应缺少完整的行记录或有效性统计')
  }
  const ids = new Set<number>()
  for (const row of rows) {
    if (!row || !['success', 'failure'].includes(row.status) ||
        row.method_id?.toLowerCase() !== input.methodId.toLowerCase() ||
        row.beta_true !== input.beta || row.eta_true !== input.eta || row.gamma !== input.gamma ||
        row.sample_size !== input.n ||
        (input.offset !== undefined && row.offset_value !== input.offset) ||
        !Number.isInteger(row.sim_id) || ids.has(row.sim_id)) {
      throw new Error('模拟响应的方法、参数或行身份与请求不一致')
    }
    ids.add(row.sim_id)
    if (row.status === 'success' && ![row.est_beta, row.est_eta, row.est_gamma].every(
      estimate => typeof estimate === 'number' && Number.isFinite(estimate),
    )) throw new Error('模拟响应包含无效的成功估计')
  }
  if (rows.filter(row => row.status === 'success').length !== metrics.n_valid) {
    throw new Error('模拟行状态与汇总有效数不一致')
  }
  if (metrics.n_valid > 0) {
    for (const parameter of ['beta', 'eta', 'gamma'] as const) {
      const summary = metrics.param_standard?.[parameter]?.absolute
      if (!summary || summary.n !== metrics.n_valid ||
          ![summary.bias, summary.sd, summary.rmse, summary.mae].every(Number.isFinite)) {
        throw new Error('模拟响应缺少共享标准指标')
      }
    }
  }
  return { sampleSize: input.n, offset: input.offset, rows, metrics }
}

export async function requestSimulation(
  input: SimulationInput,
  signal: AbortSignal,
  fetcher: typeof fetch = fetch,
): Promise<SimulationBatch> {
  if (![input.beta, input.eta, input.gamma].every(Number.isFinite) || input.beta <= 0 || input.eta <= 0 || input.gamma < 0 ||
      !Number.isInteger(input.n) || input.n < 3 || input.n > 500 ||
      !Number.isInteger(input.rep) || input.rep < 1 || input.rep > 1000 ||
      (input.offset !== undefined && (!Number.isFinite(input.offset) || input.offset < 0 || input.offset > 0.5))) {
    throw new Error('请输入有效参数：β、η > 0，γ ≥ 0，样本量 3–500，重复次数 1–1000，偏移量 0–0.5')
  }
  const { methodId, ...params } = input
  const response = await fetcher('/api/studies/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ methodId, params }),
    signal,
  })
  const payload = await response.json()
  if (!response.ok) {
    if (response.status === 429) throw new Error('计算服务繁忙，请稍后重新运行')
    throw new Error(typeof payload.error === 'string' ? payload.error : '模拟请求失败，请重新运行')
  }
  return parseSimulationBatch(payload, input)
}
