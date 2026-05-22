/**
 * 统一评价指标 — 前端共享函数
 *
 * 与 python/studies/common/metrics.py 公式对等。
 * 前端组件计算指标时必须调用本模块，禁止内联重复实现。
 *
 * 命名：camelCase（前端规范），注释标注对应 Python 函数名。
 */

// ============================================================
// 常量
// ============================================================

/** 默认可靠度水平 */
export const DEFAULT_R_LEVELS = [0.995, 0.990, 0.950, 0.900] as const

/** 默认 outlier 判定阈值 */
export const DEFAULT_NE_THRESHOLD = 1.0

// ============================================================
// 层 1：单样本基础指标
// ============================================================

/**
 * 归一化综合误差 NE（对应 Python: ne()）
 *
 * NE = sqrt(
 *   ((betaHat - beta) / beta)^2
 *   + ((etaHat - eta) / eta)^2
 *   + ((gammaHat - gamma) / eta)^2
 * )
 *
 * gamma 使用 eta 归一化，避免 gamma=0 时的分母问题。
 */
export function ne(
  betaHat: number, etaHat: number, gammaHat: number,
  beta: number, eta: number, gamma: number,
): number {
  return Math.sqrt(
    ((betaHat - beta) / beta) ** 2
    + ((etaHat - eta) / eta) ** 2
    + ((gammaHat - gamma) / eta) ** 2,
  )
}

/**
 * 真实分位点 x_R = gamma + eta * (-ln(R))^(1/beta)（对应 Python: quantile_true()）
 */
export function quantileTrue(beta: number, eta: number, gamma: number, R: number): number {
  return gamma + eta * (-Math.log(R)) ** (1 / beta)
}

/**
 * 估计分位点 x̂_R = gammaHat + etaHat * (-ln(R))^(1/betaHat)（对应 Python: quantile_est()）
 */
export function quantileEst(betaHat: number, etaHat: number, gammaHat: number, R: number): number {
  return gammaHat + etaHat * (-Math.log(R)) ** (1 / betaHat)
}

/**
 * 归一化分位点误差 |x̂_R - x_R| / eta（对应 Python: nqe_R()）
 *
 * 用 eta 归一化，比 reR（用 x_R 归一化）更稳健。
 */
export function nqeR(
  betaHat: number, etaHat: number, gammaHat: number,
  beta: number, eta: number, gamma: number,
  R: number,
): number {
  const xR = quantileTrue(beta, eta, gamma, R)
  const xHatR = quantileEst(betaHat, etaHat, gammaHat, R)
  return Math.abs(xHatR - xR) / eta
}

/**
 * 相对分位点误差 |x̂_R - x_R| / x_R（对应 Python: re_R()）
 */
export function reR(
  betaHat: number, etaHat: number, gammaHat: number,
  beta: number, eta: number, gamma: number,
  R: number,
): number {
  const xR = quantileTrue(beta, eta, gamma, R)
  const xHatR = quantileEst(betaHat, etaHat, gammaHat, R)
  return Math.abs(xHatR - xR) / xR
}

// ============================================================
// 层 2：状态判定
// ============================================================

export type SampleStatus = 'success' | 'failure' | 'outlier'

/**
 * 判定单样本状态（对应 Python: check_status()）
 *
 * 判定顺序：
 * 1. betaHat 或 etaHat 非有限或 <= 0 → failure
 * 2. gammaHat 非有限 → failure（不要求 >0，但必须 finite）
 * 3. converged 为 false → failure
 * 4. NE > neThreshold → outlier
 * 5. 其余 → success
 */
export function checkStatus(
  betaHat: number, etaHat: number, gammaHat: number,
  beta: number, eta: number, gamma: number,
  converged = true,
  neThreshold = DEFAULT_NE_THRESHOLD,
): SampleStatus {
  if (!Number.isFinite(betaHat) || betaHat <= 0) return 'failure'
  if (!Number.isFinite(etaHat) || etaHat <= 0) return 'failure'
  if (!Number.isFinite(gammaHat)) return 'failure'
  if (!converged) return 'failure'

  const neValue = ne(betaHat, etaHat, gammaHat, beta, eta, gamma)
  if (neValue > neThreshold) return 'outlier'

  return 'success'
}
