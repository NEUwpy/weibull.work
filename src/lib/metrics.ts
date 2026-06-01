/**
 * S2R 唯一评价指标模块
 *
 * 维护约定：
 * - 本模块是指标规范页面 `/help/metrics` 的可执行实现。
 * - `/help/metrics` 是本模块的可读规范说明。
 * - 修改本模块任一公式、字段名或判定口径时，必须同步修改
 *   `src/app/help/metrics/page.tsx`；反过来，页面规范变更也必须同步本模块。
 *
 * 当前唯一指标体系：
 * - 参数视角和工程分位点视角都先形成带符号相对误差分布。
 * - 主指标为 MdAPE；并列报告方向、稳定性、尾部和有效估计率。
 * - beta/eta 用自身归一化，gamma 用 eta 归一化。
 * - NE、NQE_R、RE_R、Outlier Rate 等旧体系指标已废止，不再导出。
 */

export const DEFAULT_R_LEVELS = [0.50, 0.90, 0.95, 0.99, 0.999] as const

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
