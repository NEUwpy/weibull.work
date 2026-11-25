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
  signal?: AbortSignal,
  request: typeof fetch = fetch
): Promise<MethodComparisonRow[]> {
  const isMDM = methodId.toLowerCase() === 'mdm'
  const response = await request('/api/studies/simulate', {
    method: 'POST',
    signal,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      methodId,
      // step identifies historical shards. The current solver does not take a step setting.
      params: { beta, eta, gamma, n, rep, seed, offset: isMDM ? offset : undefined }
    })
  })

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.error || data.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  const data = await response.json()
  const rows: MethodComparisonRow[] = data.rows
  if (!Array.isArray(rows) || rows.length === 0) throw new Error('现场模拟未返回结果。')
  if (isMDM && rows.some(row => row.offset_value !== offset)) {
    throw new Error(`MDM 现场模拟返回的偏移量与所选值 ${offset} 不一致。`)
  }
  return rows
}
