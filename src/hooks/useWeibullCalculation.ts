/**
 * 威布尔参数估计 - 后端 API 调用
 *
 * 封装 POST /calculate 的请求构建和响应解析，
 * 供 page.tsx（计算器）和 methods/[methodId]/page.tsx（方法详情）共享。
 */

import { DataPoint, WeibullResult, calculateMedianRanks } from '@/lib/weibull'
import { getApiBaseUrl } from '@/lib/config'
import { MDM_DEFAULT_OFFSET, isMdmOffsetOption } from '@/lib/calculator-state'
import { CalculationError, requestCalculationJson } from '@/lib/calculation-feedback'
import { optimizeMdmOffset, type MdmOffsetMode } from '@/lib/mdm-process-optimization'

export { CalculationError } from '@/lib/calculation-feedback'

export interface CalculateOptions {
  methodId: string
  data: DataPoint[]
  trace?: boolean
  offset?: number
}

export interface CalculateResponse {
  result: WeibullResult
  traceData?: any
  calculation?: unknown
  methodId: string
}

export async function calculateSampleEstimate(options: CalculateOptions, offsetMode: MdmOffsetMode = 'fixed') {
  const mdm = options.methodId.toLowerCase() === 'mdm'
  const optimization = mdm && offsetMode === 'ai'
    ? await optimizeMdmOffset(options.data.filter(point => point.status === 'F').map(point => point.value))
    : undefined
  const offset = optimization?.selected_delta ?? options.offset
  const response = await calculateWeibull({ ...options, offset: mdm ? offset : undefined })
  return { ...response, calculationOffset: offset, mdmOptimization: optimization }
}

/**
 * 调用后端 /calculate，返回 WeibullResult + traceData。
 *
 * 用法：
 *   const { result, traceData } = await calculateWeibull({ methodId: 'mle', data })
 */
export async function calculateWeibull(options: CalculateOptions): Promise<CalculateResponse> {
  const { methodId, data, trace = false, offset } = options

  const failureData = data.filter(d => d.status === 'F').map(d => d.value)

  const requestBody: any = {
    method: methodId,
    data: failureData,
    trace,
  }

  // MDM 方法添加 offset
  if (methodId.toLowerCase() === 'mdm') {
    const selectedOffset = offset ?? MDM_DEFAULT_OFFSET
    if (!isMdmOffsetOption(selectedOffset)) {
      throw new CalculationError('MDM 偏移量必须使用 0.00–0.50、步长 0.02 的可选值', undefined, undefined, { kind: 'input' })
    }
    requestBody.offset = selectedOffset
  }

  const res = await requestCalculationJson(`${getApiBaseUrl()}/calculate`, requestBody, true)

  const backendMethod = (res.method || '').toLowerCase()
  const requestedMethod = methodId.toLowerCase()
  if (backendMethod !== requestedMethod) {
    throw new CalculationError(
      `方法身份不一致：请求 ${methodId}，返回 ${res.method}`,
      undefined, undefined, { kind: 'response' },
    )
  }

  const gamma = res.gamma || 0
  const points = Array.isArray(res.plot_points)
    ? res.plot_points
    : calculateMedianRanks(data, gamma, requestedMethod)

  return {
    result: {
      beta: res.beta,
      eta: res.eta,
      gamma,
      rSquared: res.rSquared,
      points,
      converged: res.converged,
    },
    traceData: res.trace_data,
    calculation: res.calculation,
    methodId: backendMethod,
  }
}
