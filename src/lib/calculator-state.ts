export type CalculatorParameters = {
  beta: number
  eta: number
  gamma: number
}

export type EstimateCandidate = {
  beta: number | null
  eta: number | null
  gamma: number
  converged?: boolean | string
}

export type ParameterModeState = {
  is3P: boolean
  gamma: number
  last3PGamma: number
}

export const DEFAULT_3P_PARAMETERS: CalculatorParameters = {
  beta: 2,
  eta: 1000,
  gamma: 1000,
}

export const MDM_DEFAULT_OFFSET = 0.1
export const MDM_OFFSET_MIN = 0
export const MDM_OFFSET_MAX = 0.5
export const MDM_OFFSET_STEP = 0.02
export const MDM_OFFSET_GRID = Object.freeze(
  Array.from(
    { length: Math.round((MDM_OFFSET_MAX - MDM_OFFSET_MIN) / MDM_OFFSET_STEP) + 1 },
    (_, index) => Number((MDM_OFFSET_MIN + index * MDM_OFFSET_STEP).toFixed(2)),
  ),
)

export function isMdmOffsetOption(value: number): boolean {
  return Number.isFinite(value) && MDM_OFFSET_GRID.some(option => option === value)
}

export function parseMdmOffsetOption(value: string | number | null | undefined): number {
  if (value === null || value === undefined || value === '') return MDM_DEFAULT_OFFSET
  const parsed = typeof value === 'number' ? value : Number(value)
  return isMdmOffsetOption(parsed) ? parsed : MDM_DEFAULT_OFFSET
}

export function getDefaultParameters(is3P: boolean): CalculatorParameters {
  return { ...DEFAULT_3P_PARAMETERS, gamma: is3P ? DEFAULT_3P_PARAMETERS.gamma : 0 }
}

export function createDefaultParameterResult<TData, TPoint>(
  data: TData[],
  calculatePoints: (data: TData[], gamma: number) => TPoint[],
) {
  return createManualParameterResult(data, true, calculatePoints)
}

export function createManualParameterResult<TData, TPoint>(
  data: TData[],
  is3P: boolean,
  calculatePoints: (data: TData[], gamma: number) => TPoint[],
) {
  const parameters = getDefaultParameters(is3P)
  return {
    ...parameters,
    rSquared: null,
    points: calculatePoints(data, parameters.gamma),
    converged: true,
  }
}

export function toggleParameterMode(state: {
  is3P: boolean
  currentGamma?: number
  gamma?: number
  last3PGamma: number
}): ParameterModeState {
  if (state.is3P) {
    const savedGamma = state.currentGamma ?? state.gamma ?? DEFAULT_3P_PARAMETERS.gamma
    return { is3P: false, gamma: 0, last3PGamma: savedGamma }
  }
  const restoredGamma = Number.isFinite(state.last3PGamma)
    ? state.last3PGamma
    : DEFAULT_3P_PARAMETERS.gamma
  return { is3P: true, gamma: restoredGamma, last3PGamma: restoredGamma }
}

export function generateWeibullSample(
  n: number,
  parameters: CalculatorParameters,
  random: () => number = Math.random,
) {
  if (!Number.isInteger(n) || n <= 0) throw new Error('样本数必须为正整数')
  if (!(parameters.beta > 0) || !(parameters.eta > 0)) {
    throw new Error('beta 和 eta 必须大于 0')
  }

  return Array.from({ length: n }, (_, id) => {
    const u = Math.min(Math.max(random(), Number.EPSILON), 1 - Number.EPSILON)
    return {
      id,
      value: parameters.gamma + parameters.eta * Math.pow(-Math.log(u), 1 / parameters.beta),
      status: 'F' as const,
    }
  })
}

export function getEstimateFailure(result: EstimateCandidate): string | null {
  if (result.converged === 'unbounded') return '参数估计无解'
  if (result.converged === false) return '参数估计未收敛'
  if (result.beta === null || result.eta === null) return '参数估计未返回完整参数'
  return null
}

export function getEstimationModeFailure(is3P: boolean): string | null {
  return is3P ? null : '当前方法仅支持 3P 估计，请切换到 3P'
}
