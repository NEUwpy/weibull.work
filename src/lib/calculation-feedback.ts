export type CalculationFailureKind = 'connection' | 'solver' | 'input' | 'service' | 'response'

export class CalculationError extends Error {
  readonly kind: CalculationFailureKind
  readonly status?: number

  constructor(
    message: string,
    public calculation?: unknown,
    public traceData?: unknown,
    options: { kind?: CalculationFailureKind; status?: number } = {},
  ) {
    super(message)
    this.name = 'CalculationError'
    this.kind = options.kind ?? 'service'
    this.status = options.status
  }
}

/** Keep transport failures separate from responses that reached the solver. */
export async function requestCalculationJson(url: string, body: unknown, solverResponse = false): Promise<any> {
  const requestBody = JSON.stringify(body)
  let response: Response
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: requestBody,
    })
  } catch {
    throw new CalculationError('未能连接计算服务', undefined, undefined, { kind: 'connection' })
  }

  const result = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = result?.detail
    const message = typeof detail === 'string' ? detail : detail?.message
    // FastAPI request validation and runner sample validation both use 422 too.
    const invalidSample = typeof message === 'string' && message.includes('invalid sample:')
    const solverFailure = solverResponse && response.status === 422 && !invalidSample
      && ((typeof message === 'string' && /^Method '[^']+' failed:/.test(message)) || Boolean(detail?.calculation))
    const kind = invalidSample || response.status === 400 || response.status === 422 && Array.isArray(detail)
      ? 'input' : solverFailure ? 'solver' : 'service'
    throw new CalculationError(
      kind === 'input' ? '请检查样本与计算参数后重试。'
        : message || `计算服务暂时无法完成请求（HTTP ${response.status}）`,
      detail?.calculation, detail?.trace_data, { kind, status: response.status },
    )
  }
  if (!result || typeof result !== 'object') {
    throw new CalculationError('计算服务未返回可读取的结果', undefined, undefined, { kind: 'response' })
  }
  return result
}

export interface CalculationNotice {
  kind: CalculationFailureKind
  title: string
  description: string
  sourceName?: string
}

export function getCalculationNotice(error: unknown, methodId?: string, sourceName?: string): CalculationNotice {
  const failure = error instanceof CalculationError ? error : null
  const kind = failure?.kind ?? 'service'
  const base = { kind, sourceName }
  if (kind === 'connection') return {
    ...base,
    title: '连接未完成',
    description: '暂时无法连接计算服务，请稍后重试。',
  }
  if (kind === 'solver') return {
    ...base,
    title: '未得到估计结果',
    description: methodId?.toLowerCase() === 'mle' && (failure?.message.includes('no_finite_local_maximum')
      || JSON.stringify(failure?.calculation ?? {}).includes('no_finite_local_maximum'))
      ? 'MLE 未找到有限极大值，可尝试其他方法。'
      : '当前方法未得到可用结果，可尝试其他方法。',
  }
  if (kind === 'input') return {
    ...base, title: '请检查计算条件', description: failure!.message,
  }
  if (failure?.status === 429) return {
    ...base, title: '计算服务正忙', description: '计算服务正忙，请稍后重试。',
  }
  return {
    ...base,
    title: kind === 'response' ? '结果暂不可用' : '暂时无法计算',
    description: kind === 'response' ? '暂时无法读取计算结果，请稍后重试。' : '计算服务暂时不可用，请稍后重试。',
  }
}
