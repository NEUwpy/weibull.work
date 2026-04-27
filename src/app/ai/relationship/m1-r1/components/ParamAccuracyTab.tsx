/**
 * M1-R1 三参数估计精度 Tab
 *
 * 对比三种 δ 来源下的参数估计误差：
 * ① δ=0.5（固定值） ② δ=AI 预测值 ③ δ=最优值
 *
 * 数据来源：param_accuracy_comparison.csv
 */
"use client"

import React, { useEffect, useState } from 'react'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { ScatterPlot } from '@/components/ai/charts/ScatterPlot'
import { Histogram } from '@/components/ai/charts/Histogram'
import { loadCSV } from '@/lib/ai-data'

interface ParamRow {
  [key: string]: number | string
  beta: number
  eta: number
  gamma: number
  n: number
  fixed_delta: number
  fixed_est_beta: number | string
  fixed_est_eta: number | string
  fixed_est_gamma: number | string
  fixed_mse: number | string
  ai_delta: number | string
  ai_est_beta: number | string
  ai_est_eta: number | string
  ai_est_gamma: number | string
  ai_mse: number | string
  optimal_delta: number | string
  opt_est_beta: number | string
  opt_est_eta: number | string
  opt_est_gamma: number | string
  optimal_mse: number | string
}

export function ParamAccuracyTab() {
  const [data, setData] = useState<ParamRow[]>([])
  const [loading, setLoading] = useState(true)

  const toNum = (v: number | string): number => typeof v === 'number' ? v : parseFloat(v) || 0

  useEffect(() => {
    async function load() {
      try {
        const rows = await loadCSV<ParamRow>('/ai/data/param_accuracy_comparison.csv').catch(() => [])
        setData(rows)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) {
    return <div className="text-center py-12 text-slate-400">加载对比数据中...</div>
  }

  if (data.length === 0) {
    return (
      <div className="space-y-4">
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-purple-700 mb-2">三参数估计精度</h4>
          <p className="text-xs text-purple-600">
            对比三种 δ 来源下的参数估计误差：δ=0.5（固定值）、δ=AI 预测值、δ=最优值。
          </p>
        </div>
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-12 text-center">
          <div className="text-4xl mb-4">📊</div>
          <h3 className="text-lg font-bold text-slate-700 mb-2">数据待生成</h3>
          <p className="text-sm text-slate-500 max-w-lg mx-auto">
            需要运行数据生成脚本：
          </p>
          <div className="mt-4 bg-slate-100 border border-slate-200 rounded-lg p-3 max-w-md mx-auto">
            <p className="text-xs font-mono text-slate-600">
              python generate_param_accuracy.py
            </p>
          </div>
        </div>
      </div>
    )
  }

  const toNumSafe = (v: number | string | null | undefined): number | null => {
    if (v === null || v === undefined || v === '') return null
    const n = typeof v === 'number' ? v : parseFloat(String(v))
    return isNaN(n) ? null : n
  }

  // Compute averages for each source
  const fixedMSEs = data.map(r => toNumSafe(r.fixed_mse)).filter((v): v is number => v !== null)
  const aiMSEs = data.map(r => toNumSafe(r.ai_mse)).filter((v): v is number => v !== null)
  const optMSEs = data.map(r => toNumSafe(r.optimal_mse)).filter((v): v is number => v !== null)

  const avgFixed = fixedMSEs.reduce((s, v) => s + v, 0) / fixedMSEs.length
  const avgAI = aiMSEs.reduce((s, v) => s + v, 0) / aiMSEs.length
  const avgOpt = optMSEs.reduce((s, v) => s + v, 0) / optMSEs.length

  // Improvement
  const aiVsFixed = avgFixed > 0 ? ((avgFixed - avgAI) / avgFixed * 100) : 0
  const optVsFixed = avgFixed > 0 ? ((avgFixed - avgOpt) / avgFixed * 100) : 0

  // Group by n
  const nValues = Array.from(new Set(data.map(r => r.n as number))).sort((a, b) => a - b)

  // Scatter: AI δ vs optimal δ
  const aiDeltaScatter = data
    .map(r => {
      const ai = toNumSafe(r.ai_delta)
      const opt = toNumSafe(r.optimal_delta)
      return ai !== null && opt !== null ? { x: opt, y: ai } : null
    })
    .filter((p): p is { x: number; y: number } => p !== null)

  // Scatter: β̂ vs β for each source
  const betaFixedScatter = data.map(r => ({ x: r.beta, y: toNum(r.fixed_est_beta) })).filter(p => !isNaN(p.y))
  const betaAIScatter = data.map(r => ({ x: r.beta, y: toNum(r.ai_est_beta) })).filter(p => !isNaN(p.y))
  const betaOptScatter = data.map(r => ({ x: r.beta, y: toNum(r.opt_est_beta) })).filter(p => !isNaN(p.y))

  // Grouped bar data by n
  const groupedBarData = nValues.map(n => {
    const rows = data.filter(r => r.n === n)
    const fMSE = rows.map(r => toNumSafe(r.fixed_mse)).filter((v): v is number => v !== null)
    const aMSE = rows.map(r => toNumSafe(r.ai_mse)).filter((v): v is number => v !== null)
    const oMSE = rows.map(r => toNumSafe(r.optimal_mse)).filter((v): v is number => v !== null)
    return {
      label: `n=${n}`,
      'δ=0.5': fMSE.length > 0 ? +(fMSE.reduce((s, v) => s + v, 0) / fMSE.length).toFixed(4) : 0,
      'δ=AI': aMSE.length > 0 ? +(aMSE.reduce((s, v) => s + v, 0) / aMSE.length).toFixed(4) : 0,
      'δ=最优': oMSE.length > 0 ? +(oMSE.reduce((s, v) => s + v, 0) / oMSE.length).toFixed(4) : 0,
    }
  })

  return (
    <div className="space-y-6">
      {/* 说明 */}
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-purple-700 mb-2">三参数估计精度</h4>
        <p className="text-xs text-purple-600">
          对同一批验证样本（45 个组合，每组合 1 个样本），分别用 δ=0.5、δ=AI 预测值、δ=网格搜索最优值运行 MDM，
          对比 (β̂, η̂, γ̂) 的估计精度。δ=最优 是理论上界。
        </p>
      </div>

      {/* 汇总指标 */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <div className="text-xs text-slate-500">验证样本数</div>
          <div className="text-lg font-black text-slate-700 font-mono">{data.length}</div>
        </div>
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
          <div className="text-xs text-amber-500">δ=0.5 平均 MSE</div>
          <div className="text-lg font-black text-amber-700 font-mono">{avgFixed.toFixed(4)}</div>
        </div>
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
          <div className="text-xs text-purple-500">δ=AI 平均 MSE</div>
          <div className="text-lg font-black text-purple-700 font-mono">{avgAI.toFixed(4)}</div>
        </div>
        <div className="bg-green-50 border border-green-200 rounded-lg p-3">
          <div className="text-xs text-green-500">δ=最优 平均 MSE</div>
          <div className="text-lg font-black text-green-700 font-mono">{avgOpt.toFixed(4)}</div>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div className="text-xs text-blue-500">AI vs 0.5 改善</div>
          <div className={`text-lg font-black font-mono ${aiVsFixed > 0 ? 'text-green-700' : 'text-red-700'}`}>
            {aiVsFixed > 0 ? '+' : ''}{aiVsFixed.toFixed(1)}%
          </div>
        </div>
      </div>

      {/* 按 n 的分组柱状图 */}
      <ChartCard title="各 n 下三种 δ 的平均 MSE 对比">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">n</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-amber-600">δ=0.5 MSE</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-purple-600">δ=AI MSE</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-green-600">δ=最优 MSE</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-blue-600">AI vs 0.5</th>
              </tr>
            </thead>
            <tbody>
              {groupedBarData.map((row, i) => {
                const fixed = row['δ=0.5']
                const ai = row['δ=AI']
                const improvement = fixed > 0 ? ((fixed - ai) / fixed * 100) : 0
                return (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="border border-slate-200 px-3 py-2 font-mono font-bold">{row.label}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{fixed.toFixed(4)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{ai.toFixed(4)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{row['δ=最优'].toFixed(4)}</td>
                    <td className={`border border-slate-200 px-3 py-2 text-right font-mono font-bold ${
                      improvement > 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {improvement > 0 ? '+' : ''}{improvement.toFixed(1)}%
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </ChartCard>

      {/* AI δ vs 最优 δ 散点图 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="AI δ vs 最优 δ">
          <ScatterPlot
            data={aiDeltaScatter}
            xLabel="最优 δ"
            yLabel="AI 预测 δ"
            color="#8b5cf6"
            showDiagonal={true}
          />
        </ChartCard>
        <ChartCard title="各 n 三种 δ 的 MSE 对比">
          <div className="space-y-2">
            {groupedBarData.map((row, i) => {
              const maxVal = Math.max(row['δ=0.5'], row['δ=AI'], row['δ=最优'])
              return (
                <div key={i} className="space-y-1">
                  <div className="text-xs font-bold text-slate-600">{row.label}</div>
                  <div className="space-y-0.5">
                    {[
                      { key: 'δ=0.5', val: row['δ=0.5'], color: 'bg-amber-400' },
                      { key: 'δ=AI', val: row['δ=AI'], color: 'bg-purple-500' },
                      { key: 'δ=最优', val: row['δ=最优'], color: 'bg-green-500' },
                    ].map(bar => (
                      <div key={bar.key} className="flex items-center gap-2">
                        <span className="text-xs text-slate-500 w-12 text-right">{bar.key}</span>
                        <div className="flex-1 bg-slate-100 rounded h-4 relative">
                          <div
                            className={`${bar.color} h-4 rounded`}
                            style={{ width: `${maxVal > 0 ? (bar.val / maxVal * 100) : 0}%` }}
                          />
                        </div>
                        <span className="text-xs font-mono text-slate-600 w-16 text-right">{bar.val.toFixed(4)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        </ChartCard>
      </div>

      {/* β̂ vs β 散点图（三种来源） */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ChartCard title="β̂ vs β — δ=0.5">
          <ScatterPlot data={betaFixedScatter} xLabel="真实 β" yLabel="估计 β" color="#f59e0b" showDiagonal={true} />
        </ChartCard>
        <ChartCard title="β̂ vs β — δ=AI">
          <ScatterPlot data={betaAIScatter} xLabel="真实 β" yLabel="估计 β" color="#8b5cf6" showDiagonal={true} />
        </ChartCard>
        <ChartCard title="β̂ vs β — δ=最优">
          <ScatterPlot data={betaOptScatter} xLabel="真实 β" yLabel="估计 β" color="#10b981" showDiagonal={true} />
        </ChartCard>
      </div>

      {/* 逐案例对比表 */}
      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-3">逐案例对比（45 个组合）</h4>
        <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
          <table className="w-full text-sm border-collapse">
            <thead className="sticky top-0 bg-slate-100">
              <tr>
                <th className="border border-slate-200 px-2 py-1.5 text-left font-bold text-slate-600">β</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">η</th>
                <th className="border border-slate-200 px-2 py-1.5 text-center font-bold text-slate-600">n</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-amber-600">δ=0.5</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-amber-600">MSE</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-purple-600">δ=AI</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-purple-600">MSE</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-green-600">δ=最优</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-green-600">MSE</th>
              </tr>
            </thead>
            <tbody>
              {data.map((r, i) => {
                const fixedMSE = toNumSafe(r.fixed_mse)
                const aiMSE = toNumSafe(r.ai_mse)
                const optMSE = toNumSafe(r.optimal_mse)
                const bestMSE = Math.min(
                  fixedMSE ?? Infinity,
                  aiMSE ?? Infinity,
                  optMSE ?? Infinity
                )
                return (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="border border-slate-200 px-2 py-1 font-mono">{r.beta}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{r.eta}</td>
                    <td className="border border-slate-200 px-2 py-1 text-center font-mono">{r.n}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{r.fixed_delta}</td>
                    <td className={`border border-slate-200 px-2 py-1 text-right font-mono ${fixedMSE !== null && fixedMSE === bestMSE ? 'text-green-600 font-bold' : ''}`}>
                      {fixedMSE !== null ? fixedMSE.toFixed(4) : '—'}
                    </td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{toNumSafe(r.ai_delta) !== null ? toNumSafe(r.ai_delta)!.toFixed(4) : '—'}</td>
                    <td className={`border border-slate-200 px-2 py-1 text-right font-mono ${aiMSE !== null && aiMSE === bestMSE ? 'text-green-600 font-bold' : ''}`}>
                      {aiMSE !== null ? aiMSE.toFixed(4) : '—'}
                    </td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{toNumSafe(r.optimal_delta) !== null ? toNumSafe(r.optimal_delta)!.toFixed(4) : '—'}</td>
                    <td className={`border border-slate-200 px-2 py-1 text-right font-mono ${optMSE !== null && optMSE === bestMSE ? 'text-green-600 font-bold' : ''}`}>
                      {optMSE !== null ? optMSE.toFixed(4) : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
