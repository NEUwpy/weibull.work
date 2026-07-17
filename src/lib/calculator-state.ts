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

export function getDefaultParameters(is3P: boolean): CalculatorParameters {
  return { ...DEFAULT_3P_PARAMETERS, gamma: is3P ? DEFAULT_3P_PARAMETERS.gamma : 0 }
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
  if (result.beta === null || result.eta === null) return '参数估计未返回完整参数'
  if (result.converged === 'unbounded') return '参数估计无解'
  if (result.converged === false) return '参数估计未收敛'
  return null
}
