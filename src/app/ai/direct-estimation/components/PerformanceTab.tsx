/**
 * 性能展示 Tab — 直接估计
 *
 * 散点图、误差直方图、按维度切换的精度表
 */
"use client"

import React, { useEffect, useState, useMemo } from 'react'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { ScatterPlot } from '@/components/ai/charts/ScatterPlot'
import { Histogram } from '@/components/ai/charts/Histogram'
import {
  loadCSV, loadJSON,
  schemeMetricsPath, schemeValidationPath,
  DirectEstimationMetricsData, DirectEstimationValidationRow,
  groupBy,
} from '@/lib/ai-data'

const SAMPLE_SIZES = [5, 7, 10, 15]
const PARAM_NAMES = ['beta', 'eta', 'gamma'] as const
const PARAM_LABELS: Record<string, string> = { beta: 'β', eta: 'η', gamma: 'γ' }

type DimensionKey = 'n' | 'beta' | 'eta'
const DIM_OPTIONS: { key: DimensionKey; label: string }[] = [
  { key: 'n', label: '按样本量 n' },
  { key: 'beta', label: '按 β 真值' },
  { key: 'eta', label: '按 η 真值' },
]

export function PerformanceTab({ scheme = 'a-1' }: { scheme?: string }) {
  const [metrics, setMetrics] = useState<Map<number, DirectEstimationMetricsData>>(new Map())
  const [predictions, setPredictions] = useState<Map<number, DirectEstimationValidationRow[]>>(new Map())
  const [loading, setLoading] = useState(true)
  const [dim, setDim] = useState<DimensionKey>('n')

  useEffect(() => {
    async function load() {
      try {
        const mMap = new Map<number, DirectEstimationMetricsData>()
        const pMap = new Map<number, DirectEstimationValidationRow[]>()

        if (scheme === 'b-1' || scheme === 'b-2') {
          try {
            const m = await loadJSON<DirectEstimationMetricsData>(schemeMetricsPath(scheme))
            for (const n of SAMPLE_SIZES) mMap.set(n, m)
          } catch {}
          try {
            const p = await loadCSV<Record<string, number>>(schemeValidationPath(scheme))
            const groups = groupBy(p, (row) => String(row.n))
            groups.forEach((rows, nStr) => {
              pMap.set(Number(nStr), rows as unknown as DirectEstimationValidationRow[])
            })
          } catch {}
        } else {
          for (const n of SAMPLE_SIZES) {
            try {
              const m = await loadJSON<DirectEstimationMetricsData>(schemeMetricsPath(scheme, n))
              mMap.set(n, m)
            } catch {}
            try {
              const p = await loadCSV<Record<string, number>>(schemeValidationPath(scheme, n))
              pMap.set(n, p as unknown as DirectEstimationValidationRow[])
            } catch {}
          }
        }

        setMetrics(mMap)
        setPredictions(pMap)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [scheme])

  // 所有预测合并
  const allPredictions = useMemo(() => {
    const all: DirectEstimationValidationRow[] = []
    predictions.forEach(rows => all.push(...rows))
    return all
  }, [predictions])

  // 按维度分组计算精度
  const dimensionRows = useMemo(() => {
    if (allPredictions.length === 0) return []

    if (dim === 'n') {
      // 按 n 分组 — 直接用 metrics
      return SAMPLE_SIZES.filter(n => metrics.has(n)).map(n => {
        const m = metrics.get(n)!
        return {
          label: `n=${n}`,
          mae_beta: m.metrics.mae_beta,
          mae_eta: m.metrics.mae_eta,
          mae_gamma: m.metrics.mae_gamma,
          mre_beta: m.metrics.mean_relative_error_beta,
          mre_eta: m.metrics.mean_relative_error_eta,
          mre_gamma: m.metrics.mean_relative_error_gamma,
          count: m.metrics.val_samples,
        }
      })
    }

    // 按 β 或 η 分组 — 从 predictions 计算
    const groupKey = dim === 'beta' ? 'true_beta' : 'true_eta'
    const groups = new Map<string, DirectEstimationValidationRow[]>()
    for (const row of allPredictions) {
      const key = String((row as unknown as Record<string, number>)[groupKey])
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key)!.push(row)
    }

    const rows: Array<{
      label: string; sortVal: number
      mae_beta: number; mae_eta: number; mae_gamma: number
      mre_beta: number; mre_eta: number; mre_gamma: number
      count: number
    }> = []

    groups.forEach((gRows, key) => {
      const n = gRows.length
      let sumAbsBeta = 0, sumAbsEta = 0, sumAbsGamma = 0
      let sumRelBeta = 0, sumRelEta = 0, sumRelGamma = 0

      for (const r of gRows) {
        sumAbsBeta += Math.abs(r.pred_beta - r.true_beta)
        sumAbsEta += Math.abs(r.pred_eta - r.true_eta)
        sumAbsGamma += Math.abs(r.pred_gamma - r.true_gamma)
        if (Math.abs(r.true_beta) > 1e-10) sumRelBeta += Math.abs(r.pred_beta - r.true_beta) / Math.abs(r.true_beta)
        if (Math.abs(r.true_eta) > 1e-10) sumRelEta += Math.abs(r.pred_eta - r.true_eta) / Math.abs(r.true_eta)
        if (Math.abs(r.true_gamma) > 1e-10) sumRelGamma += Math.abs(r.pred_gamma - r.true_gamma) / Math.abs(r.true_gamma)
      }

      const numKey = Number(key)
      rows.push({
        label: dim === 'beta' ? `β=${numKey}` : `η=${numKey}`,
        sortVal: numKey,
        mae_beta: sumAbsBeta / n,
        mae_eta: sumAbsEta / n,
        mae_gamma: sumAbsGamma / n,
        mre_beta: sumRelBeta / n,
        mre_eta: sumRelEta / n,
        mre_gamma: sumRelGamma / n,
        count: n,
      })
    })

    rows.sort((a, b) => a.sortVal - b.sortVal)
    return rows
  }, [dim, allPredictions, metrics])

  if (loading) {
    return <div className="text-center py-12 text-slate-400">加载性能数据中...</div>
  }

  const hasMetrics = metrics.size > 0
  const hasPredictions = allPredictions.length > 0

  return (
    <div className="space-y-6">
      {/* 预测 vs 真值散点图 */}
      {hasPredictions && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {(PARAM_NAMES as readonly string[]).map(param => {
            const scatterData = allPredictions
              .filter(r => {
                const t = (r as unknown as Record<string, number>)[`true_${param}`]
                const p = (r as unknown as Record<string, number>)[`pred_${param}`]
                return !isNaN(t) && !isNaN(p)
              })
              .map(r => ({
                x: (r as unknown as Record<string, number>)[`true_${param}`],
                y: (r as unknown as Record<string, number>)[`pred_${param}`],
              }))

            if (scatterData.length === 0) return null

            return (
              <ChartCard key={param} title={`${PARAM_LABELS[param]}: 预测 vs 真值`}>
                <ScatterPlot
                  data={scatterData}
                  xLabel={`真值 ${PARAM_LABELS[param]}`}
                  yLabel={`预测 ${PARAM_LABELS[param]}`}
                  showDiagonal
                  color="#0891b2"
                />
                <div className="text-center mt-1 text-xs text-slate-400">
                  点越靠近对角线越好（共 {scatterData.length} 个验证点）
                </div>
              </ChartCard>
            )
          })}
        </div>
      )}

      {/* 误差分布直方图 */}
      {hasPredictions && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {(PARAM_NAMES as readonly string[]).map(param => {
            const errors: number[] = []
            for (const r of allPredictions) {
              const trueVal = (r as unknown as Record<string, number>)[`true_${param}`]
              const predVal = (r as unknown as Record<string, number>)[`pred_${param}`]
              if (!isNaN(trueVal) && !isNaN(predVal) && Math.abs(trueVal) > 1e-10) {
                errors.push((predVal - trueVal) / trueVal * 100)
              }
            }

            if (errors.length === 0) return null

            const mean = errors.reduce((a, b) => a + b, 0) / errors.length
            const std = Math.sqrt(errors.reduce((s, v) => s + (v - mean) ** 2, 0) / errors.length)

            return (
              <ChartCard key={param} title={`${PARAM_LABELS[param]}: 相对误差分布 (%)`}>
                <Histogram
                  values={errors}
                  xLabel="相对误差 (%)"
                  yLabel="频次"
                  color="#0891b2"
                  showMean
                />
                <div className="flex justify-center gap-4 mt-1 text-xs text-slate-400">
                  <span>均值: {mean.toFixed(2)}%</span>
                  <span>标准差: {std.toFixed(2)}%</span>
                  <span>样本数: {errors.length}</span>
                </div>
              </ChartCard>
            )
          })}
        </div>
      )}

      {/* 按维度切换的精度表 */}
      {dimensionRows.length > 0 && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-bold text-slate-700">精度分解</h4>
            <div className="flex rounded-lg border border-slate-200 overflow-hidden text-xs">
              {DIM_OPTIONS.map(opt => (
                <button
                  key={opt.key}
                  onClick={() => setDim(opt.key)}
                  className={`px-3 py-1 font-medium transition-colors ${dim === opt.key ? 'bg-cyan-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'}`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">
                    {dim === 'n' ? '样本量' : dim === 'beta' ? 'β 真值' : 'η 真值'}
                  </th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MAE(β)</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MAE(η)</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MRE(β)</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MRE(η)</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">样本数</th>
                </tr>
              </thead>
              <tbody>
                {dimensionRows.map((row, i) => (
                  <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                    <td className="border border-slate-200 px-3 py-2 font-mono font-bold">{row.label}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{row.mae_beta.toFixed(4)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{row.mae_eta.toFixed(1)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{(row.mre_beta * 100).toFixed(1)}%</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{(row.mre_eta * 100).toFixed(1)}%</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono text-slate-400">{row.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-slate-400 mt-2">
            MRE = 平均相对误差 = mean(|pred - true| / true) × 100%
          </p>
        </div>
      )}

      {/* 无数据提示 */}
      {!hasMetrics && !hasPredictions && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center">
          <p className="text-sm text-slate-400">性能数据未找到</p>
          <p className="text-xs text-slate-300 mt-1">请先训练模型并将结果复制到 public/ai/data/</p>
        </div>
      )}
    </div>
  )
}
