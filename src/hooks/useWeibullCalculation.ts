/**
 * 威布尔参数估计 - 后端 API 调用
 *
 * 封装 POST /calculate 的请求构建和响应解析，
 * 供 page.tsx（计算器）和 methods/[methodId]/page.tsx（方法详情）共享。
 */

import { DataPoint, WeibullResult, calculateMedianRanks } from '@/lib/weibull'
import { getApiBaseUrl } from '@/lib/config'

export interface CalculateOptions {
  methodId: string
  data: DataPoint[]
  trace?: boolean
  offset?: number
}

export interface CalculateResponse {
  result: WeibullResult
  traceData?: any
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
    requestBody.offset = offset ?? 0.1
  }

  const response = await fetch(`${getApiBaseUrl()}/calculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requestBody),
  })

  if (!response.ok) {
    const errData = await response.json()
    throw new Error(errData.detail || '计算失败')
  }

  const res = await response.json()
  const gamma = res.gamma || 0
  const points = calculateMedianRanks(data, gamma)

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
  }
}
