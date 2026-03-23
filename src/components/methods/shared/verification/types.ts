/**
 * 可信性验证系统 - 类型定义
 */

// 样本数据
export interface SampleData {
  id: string
  values: number[]
}

// 估计结果
export interface EstimateResult {
  sample_id: string
  est_beta: number
  est_eta: number
  est_gamma: number
  bias_beta: number
  bias_eta: number
  bias_gamma: number
}

// 梯度曲线点
export interface GradientPoint {
  gamma: number
  gradient: number
}

// 样本曲线数据
export interface SampleCurve {
  sample_id: string
  grad_gamma_curve: GradientPoint[]
}

// 统计摘要
export interface SummaryData {
  n_samples: number
  true_params: {
    beta: number
    eta: number
    gamma: number
  }
  estimates: {
    beta_mean: number
    beta_std: number
    beta_min: number
    beta_max: number
    eta_mean: number
    eta_std: number
    eta_min: number
    eta_max: number
    gamma_mean: number
    gamma_std: number
    gamma_min: number
    gamma_max: number
  }
  bias: {
    beta_mean: number
    beta_std: number
    beta_min: number
    beta_max: number
    eta_mean: number
    eta_std: number
    eta_min: number
    eta_max: number
    gamma_mean: number
    gamma_std: number
    gamma_min: number
    gamma_max: number
  }
}

// 验证配置（从 config.md 解析）
export interface VerificationConfig {
  id: string
  name: string
  description?: string
  paper?: {
    id: string
    title: string
    authors: string
    journal?: string
    year?: number
    figure?: string
  }
  verification?: {
    trueParams: { beta: number; eta: number; gamma: number }
    sampleSize: number
    offset: number
    nSamples: number
    paperImage: string
    curvesData: string
    samplesData: string
    resultsData: string
    summaryData: string
  }
}
