/**
 * 性能展示 Tab — 直接估计
 *
 * 散点图、误差分布、热力图等
 */
"use client"

import React, { useEffect, useState } from 'react'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { AIChartLine } from '@/components/ai/charts/LineChart'
import {
  loadCSV, loadJSON,
  schemeMetricsPath, schemeValidationPath,
  DirectEstimationMetricsData, DirectEstimationValidationRow,
  computeStats, groupBy,
} from '@/lib/ai-data'

const SAMPLE_SIZES = [5, 7, 10, 15]
const PARAM_NAMES = ['beta', 'eta', 'gamma'] as const
const PARAM_LABELS: Record<string, string> = { beta: 'β', eta: 'η', gamma: 'γ' }

export function PerformanceTab({ scheme = 'a-1' }: { scheme?: string }) {
  const [metrics, setMetrics] = useState<Map<number, DirectEstimationMetricsData>>(new Map())
  const [predictions, setPredictions] = useState<Map<number, DirectEstimationValidationRow[]>>(new Map())
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const mMap = new Map<number, DirectEstimationMetricsData>()
        const pMap = new Map<number, DirectEstimationValidationRow[]>()

        if (scheme === 'b-1') {
          // B-1 统一模型
          try {
            const m = await loadJSON<DirectEstimationMetricsData>(schemeMetricsPath('b-1'))
            for (const n of SAMPLE_SIZES) mMap.set(n, m)
          } catch {}
          try {
            const p = await loadCSV<Record<string, number>>(schemeValidationPath('b-1'))
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

  if (loading) {
    return <div className="text-center py-12 text-slate-400">加载性能数据中...</div>
  }

  const hasData = metrics.size > 0 || predictions.size > 0

  return (
    <div className="space-y-6">
      {/* 总体指标表 */}
      {metrics.size > 0 && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-slate-700 mb-3">总体精度指标</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">模型</th>
                  {PARAM_NAMES.map(p => (
                    <React.Fragment key={p}>
                      <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MAE({PARAM_LABELS[p]})</th>
                      <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">RMSE({PARAM_LABELS[p]})</th>
                    </React.Fragment>
                  ))}
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">相对 MSE</th>
                </tr>
              </thead>
              <tbody>
                {SAMPLE_SIZES.filter(n => metrics.has(n)).map(n => {
                  const m = metrics.get(n)!
                  return (
                    <tr key={n}>
                      <td className="border border-slate-200 px-3 py-2 font-mono font-bold">n={n}</td>
                      {PARAM_NAMES.map(p => (
                        <React.Fragment key={p}>
                          <td className="border border-slate-200 px-3 py-2 text-right font-mono">
                            {(m.metrics as unknown as Record<string, number>)[`mae_${p}`]?.toFixed(p === 'beta' ? 4 : 2)}
                          </td>
                          <td className="border border-slate-200 px-3 py-2 text-right font-mono">
                            {(m.metrics as unknown as Record<string, number>)[`rmse_${p}`]?.toFixed(p === 'beta' ? 4 : 2)}
                          </td>
                        </React.Fragment>
                      ))}
                      <td className="border border-slate-200 px-3 py-2 text-right font-mono">
                        {m.metrics.total_relative_mse?.toFixed(6)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 预测 vs 真值散点图 */}
      {predictions.size > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {PARAM_NAMES.map(param => {
            const allData: { x: number; y: number }[] = []
            predictions.forEach((rows) => {
              for (const row of rows) {
                const trueVal = (row as unknown as Record<string, number>)[`true_${param}`]
                const predVal = (row as unknown as Record<string, number>)[`pred_${param}`]
                if (!isNaN(trueVal) && !isNaN(predVal)) {
                  allData.push({ x: trueVal, y: predVal })
                }
              }
            })

            if (allData.length === 0) return null

            // 添加 y=x 参考线数据
            const allVals = allData.flatMap(d => [d.x, d.y])
            const minVal = Math.min(...allVals)
            const maxVal = Math.max(...allVals)

            return (
              <ChartCard key={param} title={`${PARAM_LABELS[param]}: 预测 vs 真值`}>
                <AIChartLine
                  lines={[
                    { id: 'pred', label: '预测值', data: allData, color: '#0891b2' },
                    { id: 'ref', label: 'y=x', data: [
                      { x: minVal, y: minVal },
                      { x: maxVal, y: maxVal },
                    ], color: '#94a3b8' },
                  ]}
                  xLabel={`真值 ${PARAM_LABELS[param]}`}
                  yLabel={`预测 ${PARAM_LABELS[param]}`}
                />
                <div className="text-center mt-2 text-xs text-slate-400">
                  点越靠近对角线越好
                </div>
              </ChartCard>
            )
          })}
        </div>
      )}

      {/* 误差分布 */}
      {predictions.size > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {PARAM_NAMES.map(param => {
            const errors: number[] = []
            predictions.forEach((rows) => {
              for (const row of rows) {
                const trueVal = (row as unknown as Record<string, number>)[`true_${param}`]
                const predVal = (row as unknown as Record<string, number>)[`pred_${param}`]
                if (!isNaN(trueVal) && !isNaN(predVal) && Math.abs(trueVal) > 1e-10) {
                  errors.push((predVal - trueVal) / trueVal * 100)
                }
              }
            })

            if (errors.length === 0) return null

            const stats = computeStats(errors)

            return (
              <ChartCard key={param} title={`${PARAM_LABELS[param]}: 相对误差分布 (%)`}>
                <div className="p-4 space-y-3">
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-slate-50 rounded p-2">
                      <div className="text-slate-400">均值</div>
                      <div className="font-mono font-bold">{stats.mean.toFixed(2)}%</div>
                    </div>
                    <div className="bg-slate-50 rounded p-2">
                      <div className="text-slate-400">标准差</div>
                      <div className="font-mono font-bold">{stats.std.toFixed(2)}%</div>
                    </div>
                    <div className="bg-slate-50 rounded p-2">
                      <div className="text-slate-400">最小</div>
                      <div className="font-mono font-bold">{stats.min.toFixed(2)}%</div>
                    </div>
                    <div className="bg-slate-50 rounded p-2">
                      <div className="text-slate-400">最大</div>
                      <div className="font-mono font-bold">{stats.max.toFixed(2)}%</div>
                    </div>
                  </div>
                  <div className="text-xs text-slate-400 text-center">
                    样本数: {errors.length}
                  </div>
                </div>
              </ChartCard>
            )
          })}
        </div>
      )}

      {/* 按 n 对比 */}
      {metrics.size > 1 && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-slate-700 mb-3">不同样本量精度对比</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">样本量</th>
                  {PARAM_NAMES.map(p => (
                    <th key={p} className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MAE({PARAM_LABELS[p]})</th>
                  ))}
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">相对 MSE</th>
                </tr>
              </thead>
              <tbody>
                {SAMPLE_SIZES.filter(n => metrics.has(n)).map(n => {
                  const m = metrics.get(n)!
                  return (
                    <tr key={n}>
                      <td className="border border-slate-200 px-3 py-2 font-mono font-bold">n={n}</td>
                      {PARAM_NAMES.map(p => (
                        <td key={p} className="border border-slate-200 px-3 py-2 text-right font-mono">
                          {(m.metrics as unknown as Record<string, number>)[`mae_${p}`]?.toFixed(p === 'beta' ? 4 : 2)}
                        </td>
                      ))}
                      <td className="border border-slate-200 px-3 py-2 text-right font-mono">
                        {m.metrics.total_relative_mse?.toFixed(6)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-slate-400 mt-2">样本量越大，精度通常越高</p>
        </div>
      )}

      {/* 无数据提示 */}
      {!hasData && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center">
          <p className="text-sm text-slate-400">性能数据未找到</p>
          <p className="text-xs text-slate-300 mt-1">请先训练模型并将结果复制到 public/ai/data/</p>
        </div>
      )}
    </div>
  )
}
