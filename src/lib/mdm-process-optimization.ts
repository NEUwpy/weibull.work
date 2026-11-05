import { getApiBaseUrl, API_ENDPOINTS } from '@/lib/config'
import { MdmProcessOptimizationResult } from '@/lib/mdm-process-optimization-contract'
import { CalculationError, requestCalculationJson } from '@/lib/calculation-feedback'

export * from '@/lib/mdm-process-optimization-contract'

export async function optimizeMdmOffset(values: number[]): Promise<MdmProcessOptimizationResult> {
  const result = await requestCalculationJson(
    `${getApiBaseUrl()}${API_ENDPOINTS.aiOptimizeMdmOffset}`, { data: values },
  ) as MdmProcessOptimizationResult
  if (
    !Array.isArray(result.delta_grid) || result.delta_grid.length !== 26
    || !Array.isArray(result.predicted_loss_curve) || result.predicted_loss_curve.length !== 26
    || result.selected_delta !== result.delta_grid[result.selected_index]
  ) {
    throw new CalculationError('AI 偏移量优化接口返回了无效的候选曲线', undefined, undefined, { kind: 'response' })
  }
  return result
}
