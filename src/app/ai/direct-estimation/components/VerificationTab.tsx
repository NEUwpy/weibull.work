/**
 * 可信性验证 Tab — 直接估计
 *
 * 精度汇总表（绝对/相对切换 + 组内/插值/外推切换）+ 验证案例表
 */
"use client"

import React, { useEffect, useState } from 'react'
import { loadCSV, loadJSON, schemeMetricsPath, schemeValidationPath, generalizationMetricsPath, groupBy, DirectEstimationMetricsData, DirectEstimationValidationRow, GeneralizationMetricsData, GeneralizationMetricsByN } from '@/lib/ai-data'

const SAMPLE_SIZES = [5, 7, 10, 15]
const PARAM_NAMES = ['beta', 'eta', 'gamma'] as const
const PARAM_LABELS: Record<string, string> = { beta: 'β', eta: 'η', gamma: 'γ' }

const VALIDATION_TYPE_OPTIONS = [
  { key: 'ig', label: '组内验证' },
  { key: 'ip', label: '插值验证' },
  { key: 'ex', label: '外推验证' },
] as const

export function VerificationTab({ scheme = 'a-1' }: { scheme?: string }) {
  const [metrics, setMetrics] = useState<Map<number, DirectEstimationMetricsData>>(new Map())
  const [predictions, setPredictions] = useState<Map<number, DirectEstimationValidationRow[]>>(new Map())
  const [genMetrics, setGenMetrics] = useState<GeneralizationMetricsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [metricMode, setMetricMode] = useState<'absolute' | 'relative'>('absolute')
  const [validationType, setValidationType] = useState<string>('ig')

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

        // 加载泛化评估数据
        try {
          const gen = await loadJSON<GeneralizationMetricsData>(generalizationMetricsPath())
          setGenMetrics(gen)
        } catch {}

        setMetrics(mMap)
        setPredictions(pMap)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [scheme])

  if (loading) {
    return <div className="text-center py-12 text-slate-400">加载验证数据中...</div>
  }

  const hasMetrics = metrics.size > 0
  const hasPredictions = predictions.size > 0

  return (
    <div className="space-y-6">
      <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-3 text-sm text-cyan-700">
        可信性验证：使用已知真值的 Weibull 样本，对比 AI 预测值与真值。
        验证集从训练数据中按 20% 比例随机划分。
      </div>

      {/* 精度汇总表 */}
      {(hasMetrics || genMetrics) && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-bold text-slate-700">精度汇总</h4>
            <div className="flex items-center gap-2">
              {/* 验证类型切换 */}
              {genMetrics && (
                <div className="flex rounded-lg border border-slate-200 overflow-hidden text-xs">
                  {VALIDATION_TYPE_OPTIONS.map(opt => (
                    <button
                      key={opt.key}
                      onClick={() => setValidationType(opt.key)}
                      className={`px-3 py-1 font-medium transition-colors ${validationType === opt.key ? 'bg-cyan-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'}`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              )}
              {/* 精度类型切换 */}
              <div className="flex rounded-lg border border-slate-200 overflow-hidden text-xs">
                <button
                  onClick={() => setMetricMode('absolute')}
                  className={`px-3 py-1 font-medium transition-colors ${metricMode === 'absolute' ? 'bg-cyan-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'}`}
                >
                  绝对精度 (MAE)
                </button>
                <button
                  onClick={() => setMetricMode('relative')}
                  className={`px-3 py-1 font-medium transition-colors ${metricMode === 'relative' ? 'bg-cyan-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'}`}
                >
                  相对精度 (MRE)
                </button>
              </div>
            </div>
          </div>

          {/* 泛化精度表（有 generalization_metrics.json 时） */}
          {genMetrics && (() => {
            const schemeKey = scheme.replace('-', '')
            const typeData = genMetrics.results?.[schemeKey]?.[validationType]
            if (!typeData) return <p className="text-xs text-slate-400">该方案/验证类型暂无泛化数据</p>

            const byN = typeData.by_n || {}
            return (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="bg-slate-100">
                        <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">样本量 n</th>
                        {PARAM_NAMES.map(p => (
                          <th key={p} className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">
                            {metricMode === 'absolute' ? `MAE(${PARAM_LABELS[p]})` : `MRE(${PARAM_LABELS[p]})`}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {SAMPLE_SIZES.map(n => {
                        const m = byN[`n${n}`] as GeneralizationMetricsByN | undefined
                        if (!m) return null
                        return (
                          <tr key={n}>
                            <td className="border border-slate-200 px-3 py-2 font-mono font-bold">n={n}</td>
                            {PARAM_NAMES.map(p => (
                              <td key={p} className="border border-slate-200 px-3 py-2 text-right font-mono">
                                {metricMode === 'absolute'
                                  ? (m[`mae_${p}` as keyof GeneralizationMetricsByN] as number)?.toFixed(p === 'beta' ? 4 : 2)
                                  : `${((m[`mre_${p}` as keyof GeneralizationMetricsByN] as number) * 100)?.toFixed(1)}%`
                                }
                              </td>
                            ))}
                          </tr>
                        )
                      })}
                      {/* 汇总行 */}
                      {typeData.overall && (
                        <tr className="bg-cyan-50 font-bold">
                          <td className="border border-slate-200 px-3 py-2 font-mono">汇总</td>
                          {PARAM_NAMES.map(p => (
                            <td key={p} className="border border-slate-200 px-3 py-2 text-right font-mono">
                              {metricMode === 'absolute'
                                ? (typeData.overall[`mae_${p}` as keyof GeneralizationMetricsByN] as number)?.toFixed(p === 'beta' ? 4 : 2)
                                : `${((typeData.overall[`mre_${p}` as keyof GeneralizationMetricsByN] as number) * 100)?.toFixed(1)}%`
                              }
                            </td>
                          ))}
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
                <p className="text-xs text-slate-400 mt-2">
                  {metricMode === 'absolute'
                    ? 'MAE = 平均绝对误差（原始尺度）'
                    : 'MRE = 平均相对误差 = mean(|pred - true| / true) × 100%'
                  }
                  {' | '}
                  {VALIDATION_TYPE_OPTIONS.find(o => o.key === validationType)?.label}：
                  {validationType === 'ig' ? '训练集参数组合' : validationType === 'ip' ? '训练网格之间的新组合' : '超出训练范围的组合'}
                </p>
              </>
            )
          })()}

          {/* 回退：无泛化数据时用原有 metrics */}
          {!genMetrics && hasMetrics && (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="bg-slate-100">
                      <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">样本量 n</th>
                      {PARAM_NAMES.map(p => (
                        <th key={p} className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">
                          {metricMode === 'absolute' ? `MAE(${PARAM_LABELS[p]})` : `MRE(${PARAM_LABELS[p]})`}
                        </th>
                      ))}
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
                              {metricMode === 'absolute'
                                ? (m.metrics as unknown as Record<string, number>)[`mae_${p}`]?.toFixed(p === 'beta' ? 4 : 2)
                                : `${((m.metrics as unknown as Record<string, number>)[`mean_relative_error_${p}`] * 100)?.toFixed(1)}%`
                              }
                            </td>
                          ))}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-slate-400 mt-2">
                {metricMode === 'absolute'
                  ? 'MAE = 平均绝对误差（原始尺度）'
                  : 'MRE = 平均相对误差 = mean(|pred - true| / true) × 100%'
                }
              </p>
            </>
          )}
        </div>
      )}

      {/* 验证案例表 */}
      {hasPredictions && (() => {
        const cases: Array<{
          n: number; true_beta: number; true_eta: number; true_gamma: number
          pred_beta: number; pred_eta: number; pred_gamma: number
        }> = []

        predictions.forEach((rows, n) => {
          const groups = new Map<string, DirectEstimationValidationRow[]>()
          for (const row of rows) {
            const key = `${row.true_beta}_${row.true_eta}`
            if (!groups.has(key)) groups.set(key, [])
            groups.get(key)!.push(row)
          }
          groups.forEach((groupRows) => {
            for (const row of groupRows.slice(0, 3)) {
              cases.push({
                n, true_beta: row.true_beta, true_eta: row.true_eta, true_gamma: row.true_gamma,
                pred_beta: row.pred_beta, pred_eta: row.pred_eta, pred_gamma: row.pred_gamma,
              })
            }
          })
        })

        return (
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
            <h4 className="text-sm font-bold text-slate-700 mb-3">验证案例（部分）</h4>
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-100">
                    <th className="border border-slate-200 px-2 py-1.5 text-left font-bold text-slate-600">n</th>
                    <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">真 β</th>
                    <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">真 η</th>
                    <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">真 γ</th>
                    <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">预 β</th>
                    <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">预 η</th>
                    <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">预 γ</th>
                    <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">err β</th>
                    <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">err η</th>
                    <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">err γ</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.slice(0, 20).map((c, i) => (
                    <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                      <td className="border border-slate-200 px-2 py-1 font-mono">{c.n}</td>
                      <td className="border border-slate-200 px-2 py-1 text-right font-mono">{c.true_beta}</td>
                      <td className="border border-slate-200 px-2 py-1 text-right font-mono">{c.true_eta}</td>
                      <td className="border border-slate-200 px-2 py-1 text-right font-mono">{c.true_gamma}</td>
                      <td className="border border-slate-200 px-2 py-1 text-right font-mono">{c.pred_beta.toFixed(4)}</td>
                      <td className="border border-slate-200 px-2 py-1 text-right font-mono">{c.pred_eta.toFixed(2)}</td>
                      <td className="border border-slate-200 px-2 py-1 text-right font-mono">{c.pred_gamma.toFixed(2)}</td>
                      <td className={`border border-slate-200 px-2 py-1 text-right font-mono ${Math.abs(c.pred_beta - c.true_beta) / c.true_beta > 0.1 ? 'text-red-600' : 'text-green-600'}`}>
                        {((c.pred_beta - c.true_beta) / c.true_beta * 100).toFixed(1)}%
                      </td>
                      <td className={`border border-slate-200 px-2 py-1 text-right font-mono ${Math.abs(c.pred_eta - c.true_eta) / c.true_eta > 0.1 ? 'text-red-600' : 'text-green-600'}`}>
                        {((c.pred_eta - c.true_eta) / c.true_eta * 100).toFixed(1)}%
                      </td>
                      <td className="border border-slate-200 px-2 py-1 text-right font-mono text-slate-400">
                        {c.true_gamma === 0 ? '—' : `${((c.pred_gamma - c.true_gamma) / c.true_gamma * 100).toFixed(1)}%`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-slate-400 mt-2">
              err = (预测 - 真值) / 真值 × 100%。绿色 = 误差 &lt;10%，红色 = 误差 &gt;10%
            </p>
          </div>
        )
      })()}

      {/* 无数据提示 */}
      {!hasMetrics && !hasPredictions && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center">
          <p className="text-sm text-slate-400">验证数据未找到</p>
          <p className="text-xs text-slate-300 mt-1">请先训练模型并将结果复制到 public/ai/data/</p>
        </div>
      )}
    </div>
  )
}
