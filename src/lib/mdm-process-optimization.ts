import { getApiBaseUrl, API_ENDPOINTS } from '@/lib/config'
import { MdmProcessOptimizationResult } from '@/lib/mdm-process-optimization-contract'

export * from '@/lib/mdm-process-optimization-contract'

export async function optimizeMdmOffset(values: number[]): Promise<MdmProcessOptimizationResult> {
  const response = await fetch(`${getApiBaseUrl()}${API_ENDPOINTS.aiOptimizeMdmOffset}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data: values }),
  })

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(errorBody.detail || `AI 偏移量优化失败（HTTP ${response.status}）`)
  }

  const result = await response.json() as MdmProcessOptimizationResult
  if (
    result.delta_grid.length !== 26
    || result.predicted_loss_curve.length !== 26
    || result.selected_delta !== result.delta_grid[result.selected_index]
  ) {
    throw new Error('AI 偏移量优化接口返回了无效的候选曲线')
  }
  return result
}
