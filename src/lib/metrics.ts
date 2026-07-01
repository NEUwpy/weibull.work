/**
 * 统一评价指标模块
 *
 * 维护约定：
 * - 本模块是指标规范源 `src/app/help/metrics/metrics-spec.ts` 的可执行实现。
 * - `/help/metrics` 是该规范源的渲染视图。
 * - 修改本模块任一公式、字段名或判定口径时，必须同步修改
 *   `src/app/help/metrics/metrics-spec.ts`；反过来，规范源变更也必须同步本模块。
 *
 * 当前默认主口径：
 * - 参数视角：Bias、SD、RMSE、MAE；beta/eta 可附相对 Bias/RMSE，gamma 不输出相对指标。
 * - 工程寿命视角：x_R 的 Bias、SD、RMSE、MAE 与相对 Bias/RMSE。
 * - S2R 中位数族与尾部指标保留为 diagnostics，不再作为唯一主口径。
 */

export const DEFAULT_R_LEVELS = [0.50, 0.90, 0.95, 0.99, 0.999] as const
export const DEFAULT_STANDARD_R_LEVELS = [0.95, 0.99] as const

export interface StandardSummary {
  n: number
  bias: number | null
  sd: number | null
  mse: number | null
  rmse: number | null
  mae: number | null
}

export type SampleStatus = 'success' | 'failure'

export interface ParamRelativeErrors {
  beta: number
  eta: number
  gamma: number
}

export interface DistributionSummary {
  mdape: number | null
  medRel: number | null
  p25Rel: number | null
  p75Rel: number | null
  relIqr: number | null
  p5Rel: number | null
  p95Rel: number | null
  p95Abs: number | null
  p99Abs: number | null
}

export function quantileTrue(beta: number, eta: number, gamma: number, R: number): number {
  return gamma + eta * (-Math.log(R)) ** (1 / beta)
}

export function quantileEst(betaHat: number, etaHat: number, gammaHat: number, R: number): number {
  return gammaHat + etaHat * (-Math.log(R)) ** (1 / betaHat)
}

export function paramRelativeErrors(
  betaHat: number,
  etaHat: number,
  gammaHat: number,
  beta: number,
  eta: number,
  gamma: number,
): ParamRelativeErrors {
  return {
    beta: (betaHat - beta) / beta,
    eta: (etaHat - eta) / eta,
    gamma: (gammaHat - gamma) / eta,
  }
}

export function paramAbsoluteErrors(
  betaHat: number,
  etaHat: number,
  gammaHat: number,
  beta: number,
  eta: number,
  gamma: number,
): ParamRelativeErrors {
  return {
    beta: betaHat - beta,
    eta: etaHat - eta,
    gamma: gammaHat - gamma,
  }
}

export function quantileRelativeError(
  betaHat: number,
  etaHat: number,
  gammaHat: number,
  beta: number,
  eta: number,
  gamma: number,
  R: number,
): number {
  const xR = quantileTrue(beta, eta, gamma, R)
  const xHatR = quantileEst(betaHat, etaHat, gammaHat, R)
  return (xHatR - xR) / xR
}

function emptySummary(): DistributionSummary {
  return {
    mdape: null,
    medRel: null,
    p25Rel: null,
    p75Rel: null,
    relIqr: null,
    p5Rel: null,
    p95Rel: null,
    p95Abs: null,
    p99Abs: null,
  }
}

function percentile(sortedValues: number[], p: number): number {
  if (sortedValues.length === 1) return sortedValues[0]
  const pos = (p / 100) * (sortedValues.length - 1)
  const lo = Math.floor(pos)
  const hi = Math.ceil(pos)
  if (lo === hi) return sortedValues[lo]
  const weight = pos - lo
  return sortedValues[lo] * (1 - weight) + sortedValues[hi] * weight
}

export function summarizeRelativeErrors(errors: number[]): DistributionSummary {
  const values = errors.filter(Number.isFinite).sort((a, b) => a - b)
  if (values.length === 0) return emptySummary()

  const absValues = values.map(Math.abs).sort((a, b) => a - b)
  const p25Rel = percentile(values, 25)
  const p75Rel = percentile(values, 75)

  return {
    mdape: percentile(absValues, 50),
    medRel: percentile(values, 50),
    p25Rel,
    p75Rel,
    relIqr: p75Rel - p25Rel,
    p5Rel: percentile(values, 5),
    p95Rel: percentile(values, 95),
    p95Abs: percentile(absValues, 95),
    p99Abs: percentile(absValues, 99),
  }
}

function emptyStandardSummary(): StandardSummary {
  return {
    n: 0,
    bias: null,
    sd: null,
    mse: null,
    rmse: null,
    mae: null,
  }
}

export function summarizeStandardErrors(errors: number[]): StandardSummary {
  const values = errors.filter(Number.isFinite)
  if (values.length === 0) return emptyStandardSummary()

  const n = values.length
  const bias = values.reduce((sum, value) => sum + value, 0) / n
  const mse = values.reduce((sum, value) => sum + value * value, 0) / n
  const mae = values.reduce((sum, value) => sum + Math.abs(value), 0) / n
  const sd = n > 1
    ? Math.sqrt(values.reduce((sum, value) => sum + (value - bias) ** 2, 0) / (n - 1))
    : 0

  return {
    n,
    bias,
    sd,
    mse,
    rmse: Math.sqrt(mse),
    mae,
  }
}

export function checkStatus(
  betaHat: number,
  etaHat: number,
  gammaHat: number,
  _beta: number,
  eta: number,
  _gamma: number,
  converged = true,
  sampleMin?: number,
  boundaryTol = 1e-10,
): SampleStatus {
  if (!converged) return 'failure'
  if (!Number.isFinite(betaHat) || betaHat <= 0) return 'failure'
  if (!Number.isFinite(etaHat) || etaHat <= 0) return 'failure'
  if (!Number.isFinite(gammaHat)) return 'failure'

  if (sampleMin !== undefined && Number.isFinite(sampleMin)) {
    const tol = boundaryTol * Math.max(Math.abs(sampleMin), Math.abs(eta), 1)
    if (gammaHat >= sampleMin - tol) return 'failure'
  }

  return 'success'
}
