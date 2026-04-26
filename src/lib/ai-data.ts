/**
 * AI 模块数据加载工具
 *
 * 负责从 public/ai/data/ 加载 CSV 和 JSON 数据，
 * 并解析为前端图表组件可用的格式。
 */

// ============================================================
// CSV 解析
// ============================================================

export function parseCSV<T extends Record<string, number | string>>(text: string): T[] {
  const lines = text.trim().split('\n')
  if (lines.length < 2) return []

  const headers = lines[0].split(',').map(h => h.trim())
  const rows: T[] = []

  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',').map(v => v.trim())
    if (values.length !== headers.length) continue

    const row: Record<string, number | string> = {}
    for (let j = 0; j < headers.length; j++) {
      const val = values[j]
      if (val === '' || val === 'None' || val === 'null') {
        row[headers[j]] = NaN
      } else {
        const num = Number(val)
        row[headers[j]] = isNaN(num) ? val : num
      }
    }
    rows.push(row as T)
  }

  return rows
}

export async function loadCSV<T extends Record<string, number | string>>(path: string): Promise<T[]> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`)
  const text = await res.text()
  return parseCSV<T>(text)
}

// ============================================================
// JSON 加载
// ============================================================

export async function loadJSON<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`)
  return res.json()
}

// ============================================================
// 数据路径常量
// ============================================================

export const AI_DATA_BASE = '/ai/data'

export function trainingDataPath(n: number) {
  return `${AI_DATA_BASE}/training_data_n${n}.csv`
}

export function trainingDataAllPath() {
  return `${AI_DATA_BASE}/training_data_all.csv`
}

export function metricsPath(n: number | 'n1') {
  if (n === 'n1') return `${AI_DATA_BASE}/delta_from_params_metrics.json`
  return `${AI_DATA_BASE}/n${n}_metrics.json`
}

export function validationPredictionsPath(n: number) {
  return `${AI_DATA_BASE}/validation_predictions_n${n}.csv`
}

// ============================================================
// 直接估计数据路径
// ============================================================

export function directEstimationTrainingDataPath(n: number) {
  return `${AI_DATA_BASE}/direct_estimation_training_data_n${n}.csv`
}

export function directEstimationMetricsPath(n: number) {
  return `${AI_DATA_BASE}/direct_estimation_n${n}_metrics.json`
}

export function directEstimationValidationPath(n: number) {
  return `${AI_DATA_BASE}/direct_estimation_validation_predictions_n${n}.csv`
}

export function directEstimationHistoryPath(n: number) {
  return `${AI_DATA_BASE}/direct_estimation_training_history_n${n}.csv`
}

// Scheme-aware 路径函数
export function schemeMetricsPath(scheme: string, n?: number) {
  if (scheme === 'b-1') return `${AI_DATA_BASE}/direct_estimation_b1_metrics.json`
  const suffix = scheme === 'a-1' ? '' : `_${scheme.replace('-', '')}`
  return `${AI_DATA_BASE}/direct_estimation_n${n}${suffix}_metrics.json`
}

export function schemeValidationPath(scheme: string, n?: number) {
  if (scheme === 'b-1') return `${AI_DATA_BASE}/direct_estimation_validation_predictions_b1.csv`
  const suffix = scheme === 'a-1' ? '' : `_${scheme.replace('-', '')}`
  return `${AI_DATA_BASE}/direct_estimation_validation_predictions_n${n}${suffix}.csv`
}

export function schemeHistoryPath(scheme: string, n?: number) {
  if (scheme === 'b-1') return `${AI_DATA_BASE}/direct_estimation_training_history_b1.csv`
  const suffix = scheme === 'a-1' ? '' : `_${scheme.replace('-', '')}`
  return `${AI_DATA_BASE}/direct_estimation_training_history_n${n}${suffix}.csv`
}

export interface DirectEstimationMetricsData {
  metrics: {
    mse_beta: number
    mse_eta: number
    mse_gamma: number
    mae_beta: number
    mae_eta: number
    mae_gamma: number
    rmse_beta: number
    rmse_eta: number
    rmse_gamma: number
    mean_relative_error_beta: number
    mean_relative_error_eta: number
    mean_relative_error_gamma: number
    total_relative_mse: number
    best_epoch: number
    best_val_loss: number
    input_dim: number
    train_samples: number
    val_samples: number
    architecture: string
  }
  history: {
    train_loss: number[]
    val_loss: number[]
    lr: number[]
  }
  config: Record<string, number>
  trained_at: string
}

export interface DirectEstimationValidationRow {
  n: number
  true_beta: number
  true_eta: number
  true_gamma: number
  pred_beta: number
  pred_eta: number
  pred_gamma: number
}

export interface DirectEstimationHistoryRow {
  epoch: number
  train_loss: number
  val_loss: number
  lr: number
}

// ============================================================
// 统计工具
// ============================================================

export function computeHistogramBins(values: number[], binCount?: number) {
  const validValues = values.filter(v => !isNaN(v))
  if (validValues.length === 0) return []

  const min = Math.min(...validValues)
  const max = Math.max(...validValues)
  const range = max - min || 1
  const n = binCount ?? Math.min(Math.ceil(Math.sqrt(validValues.length)), 30)
  const binWidth = range / n

  const bins = Array.from({ length: n }, (_, i) => ({
    x0: min + i * binWidth,
    x1: min + (i + 1) * binWidth,
    midpoint: min + (i + 0.5) * binWidth,
    count: 0,
  }))

  for (const v of validValues) {
    let idx = Math.floor((v - min) / binWidth)
    if (idx >= n) idx = n - 1
    if (idx < 0) idx = 0
    bins[idx].count++
  }

  return bins
}

export function computeStats(values: number[]) {
  const valid = values.filter(v => !isNaN(v))
  if (valid.length === 0) return { mean: 0, std: 0, min: 0, max: 0, median: 0, count: 0 }

  const sorted = [...valid].sort((a, b) => a - b)
  const mean = valid.reduce((a, b) => a + b, 0) / valid.length
  const variance = valid.reduce((sum, v) => sum + (v - mean) ** 2, 0) / valid.length

  return {
    mean,
    std: Math.sqrt(variance),
    min: sorted[0],
    max: sorted[sorted.length - 1],
    median: sorted[Math.floor(sorted.length / 2)],
    count: valid.length,
  }
}

export function groupBy<T>(data: T[], keyFn: (item: T) => string): Map<string, T[]> {
  const groups = new Map<string, T[]>()
  for (const item of data) {
    const key = keyFn(item)
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(item)
  }
  return groups
}
