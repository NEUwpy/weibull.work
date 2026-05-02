/**
 * M1-R1 方法对比 Tab
 *
 * 精度对比表 + C2(δ sweep) + C3(改善热力图)
 */
"use client"

import React, { useEffect, useState } from 'react'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { AIChartLine } from '@/components/ai/charts/LineChart'
import { loadCSV } from '@/lib/ai-data'

interface SweepRow { [key: string]: number | string }
interface ImprovementRow { [key: string]: number | string }

const SAMPLE_SIZES = [5, 7, 10, 15, 20]
const FIXED_DELTAS = [0.01, 0.05, 0.1, 0.2, 0.5]

interface PrecisionData {
  n: number
  methods: Record<string, {
    label: string
    per_param: Record<string, { mae: number; mre: number }>
    aggregate: { total_mae: number; total_mre: number }
    samples: number
  }>
}

export function CompareTab() {
  const [sweepData, setSweepData] = useState<SweepRow[]>([])
  const [improvementData, setImprovementData] = useState<ImprovementRow[]>([])
  const [precisionData, setPrecisionData] = useState<Record<string, PrecisionData>>({})
  const [viewMode, setViewMode] = useState<'aggregate' | 'per_param'>('aggregate')
  const [metricMode, setMetricMode] = useState<'absolute' | 'relative'>('absolute')
  const [loading, setLoading] = useState(true)

  const toNum = (v: number | string): number => typeof v === 'number' ? v : parseFloat(v) || 0

  useEffect(() => {
    async function load() {
      try {
        const [sweep, imp, precision] = await Promise.all([
          loadCSV<SweepRow>('/ai/data/comparison_sweep.csv').catch(() => []),
          loadCSV<ImprovementRow>('/ai/data/comparison_improvement.csv').catch(() => []),
          fetch('/ai/data/m1_mdm_precision.json').then(r => r.ok ? r.json() : {}).catch(() => ({})),
        ])
        setSweepData(sweep)
        setImprovementData(imp)
        setPrecisionData(precision)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return <div className="text-center py-12 text-slate-400">加载对比数据中...</div>

  // C2: Sweep MSE curve per (beta, n)
  const renderSweepCharts = () => {
    if (sweepData.length === 0) return null
    const betas = [1.0, 2.0, 5.0]

    return (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {betas.map(beta => (
          <ChartCard key={beta} title={`C2: β=${beta} δ Sweep MSE 曲线`}>
            <AIChartLine
              lines={SAMPLE_SIZES.map((n, i) => {
                const rows = sweepData.filter(r => toNum(r.beta) === beta && toNum(r.n) === n)
                return {
                  id: `n${n}`,
                  label: `n=${n}`,
                  data: rows.map(r => ({ x: toNum(r.delta), y: toNum(r.mean_mse) })),
                  color: ['#3b82f6', '#10b981', '#f59e0b'][i % 3],
                }
              })}
              xLabel="δ"
              yLabel="Mean MSE"
            />
          </ChartCard>
        ))}
      </div>
    )
  }

  // 精度对比表
  const renderPrecisionTable = () => {
    const ns = Object.keys(precisionData).map(k => parseInt(k.replace('n', ''))).sort((a, b) => a - b)
    if (ns.length === 0) return null

    const methods = ['mdm_fixed_0.5', 'mdm_ai_delta']
    const params = ['beta', 'eta', 'gamma'] as const
    const paramLabels: Record<string, string> = { beta: 'β', eta: 'η', gamma: 'γ' }

    const showParams = viewMode === 'per_param'
    const colSpan = showParams ? params.length + 1 : 1

    return (
      <div className="space-y-3">
        <div className="flex items-center gap-3 flex-wrap">
          <h3 className="text-base font-bold text-slate-800">精度对比：MDM(δ=0.5) vs MDM(AI最优δ)</h3>
          <div className="flex bg-slate-100 rounded-lg p-0.5">
            <button className={`px-3 py-1 text-xs rounded-md transition-colors ${viewMode === 'aggregate' ? 'bg-white text-slate-800 shadow-sm font-bold' : 'text-slate-500'}`} onClick={() => setViewMode('aggregate')}>聚合精度</button>
            <button className={`px-3 py-1 text-xs rounded-md transition-colors ${viewMode === 'per_param' ? 'bg-white text-slate-800 shadow-sm font-bold' : 'text-slate-500'}`} onClick={() => setViewMode('per_param')}>三参数精度</button>
          </div>
          <div className="flex bg-slate-100 rounded-lg p-0.5">
            <button className={`px-3 py-1 text-xs rounded-md transition-colors ${metricMode === 'absolute' ? 'bg-white text-slate-800 shadow-sm font-bold' : 'text-slate-500'}`} onClick={() => setMetricMode('absolute')}>MAE (绝对)</button>
            <button className={`px-3 py-1 text-xs rounded-md transition-colors ${metricMode === 'relative' ? 'bg-white text-slate-800 shadow-sm font-bold' : 'text-slate-500'}`} onClick={() => setMetricMode('relative')}>MRE (相对)</button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">方法</th>
                {ns.map(n => (
                  <th key={n} className="border border-slate-200 px-3 py-2 text-center font-bold text-slate-600" colSpan={colSpan}>n={n}</th>
                ))}
              </tr>
              {showParams && (
                <tr className="bg-slate-50">
                  <th className="border border-slate-200 px-3 py-2"></th>
                  {ns.map(n => (
                    <React.Fragment key={n}>
                      {params.map(p => <th key={p} className="border border-slate-200 px-2 py-1 text-right font-bold text-slate-500 text-xs">{paramLabels[p]}</th>)}
                      <th className="border border-slate-200 px-2 py-1 text-right font-bold text-slate-500 text-xs">聚合</th>
                    </React.Fragment>
                  ))}
                </tr>
              )}
            </thead>
            <tbody>
              {methods.map((method, mi) => {
                const entry = ns.map(n => precisionData[`n${n}`]?.methods?.[method]).filter(Boolean)
                if (entry.length === 0) return null
                const label = entry[0].label
                const rowClass = mi === 0 ? 'hover:bg-blue-50' : 'bg-blue-50 hover:bg-blue-100'

                return (
                  <tr key={method} className={rowClass}>
                    <td className="border border-slate-200 px-3 py-2 font-bold text-slate-700">{label}</td>
                    {ns.map(n => {
                      const m = precisionData[`n${n}`]?.methods?.[method]
                      if (!m) return <td key={n} className="border border-slate-200 px-2 py-1 text-center text-slate-400">—</td>
                      if (showParams) {
                        return (
                          <React.Fragment key={n}>
                            {params.map(p => {
                              const val = metricMode === 'absolute' ? m.per_param[p]?.mae : m.per_param[p]?.mre
                              return (
                                <td key={p} className="border border-slate-200 px-2 py-1 text-right font-mono text-xs">
                                  {val != null ? (metricMode === 'absolute' ? val.toFixed(4) : (val * 100).toFixed(1) + '%') : '—'}
                                </td>
                              )
                            })}
                            <td className="border border-slate-200 px-2 py-1 text-right font-mono text-xs font-bold">
                              {(m.aggregate.total_mre * 100).toFixed(1) + '%'}
                            </td>
                          </React.Fragment>
                        )
                      }
                      return (
                        <td key={n} className="border border-slate-200 px-3 py-2 text-right font-mono font-bold">
                          {(m.aggregate.total_mre * 100).toFixed(1) + '%'}
                        </td>
                      )
                    })}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  // C3: Improvement heatmap-style table
  const renderImprovementTable = () => {
    if (improvementData.length === 0) return null
    const betas = [1.0, 2.0, 5.0]

    return (
      <ChartCard title="C3: AI δ 相对固定 δ 的改善百分比">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-2 py-1.5 text-left font-bold text-slate-600">β</th>
                <th className="border border-slate-200 px-2 py-1.5 text-center font-bold text-slate-600">n</th>
                {FIXED_DELTAS.map(fd => (
                  <th key={fd} className="border border-slate-200 px-2 py-1.5 text-center font-bold text-slate-600">vs δ={fd}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {betas.map(beta => (
                SAMPLE_SIZES.map(n => {
                  const rows = improvementData.filter(r => toNum(r.beta) === beta && toNum(r.n) === n)
                  if (rows.length === 0) return null
                  const avg = (col: string) => {
                    const vals = rows.map(r => toNum(r[col])).filter(v => !isNaN(v))
                    return vals.length > 0 ? vals.reduce((s, v) => s + v, 0) / vals.length : 0
                  }
                  return (
                    <tr key={`${beta}-${n}`} className="hover:bg-slate-50">
                      <td className="border border-slate-200 px-2 py-1 font-mono">{beta}</td>
                      <td className="border border-slate-200 px-2 py-1 text-center font-mono">{n}</td>
                      {FIXED_DELTAS.map(fd => {
                        const val = avg(`vs_${fd}`)
                        const color = val > 0 ? 'text-green-600' : val < 0 ? 'text-red-600' : 'text-slate-500'
                        return (
                          <td key={fd} className={`border border-slate-200 px-2 py-1 text-center font-mono ${color}`}>
                            {val > 0 ? '+' : ''}{val.toFixed(1)}%
                          </td>
                        )
                      })}
                    </tr>
                  )
                })
              ))}
            </tbody>
          </table>
        </div>
      </ChartCard>
    )
  }

  return (
    <div className="space-y-6">
      {renderPrecisionTable()}

      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-xs text-slate-600 space-y-2">
        <h4 className="text-sm font-bold text-slate-700">指标说明</h4>
        <p><strong>MAE（绝对）</strong>：Mean Absolute Error = (1/N)Σ|θ̂-θ|，有量纲（β 无量纲，η/γ 与数据同量纲）</p>
        <p><strong>MRE（相对）</strong>：Mean Relative Error = (1/N)Σ|θ̂-θ|/|θ|，无量纲，可跨参数比较</p>
        <p><strong>聚合指标</strong>：三参数 MRE 之和（无量纲），与最优 δ 选择所用的相对 MSE 一致</p>
        <p><strong>最优 δ 选择</strong>：最小化 ((β̂-β)/β)² + ((η̂-η)/η)² + ((γ̂-γ)/γ)²（相对 MSE，每个参数的相对误差平方和）</p>
        <p><strong>数据来源</strong>：M1 参数空间 β∈{'{1,2,5}'}, η∈{'{100,1000,5000}'}, γ=1000，每组 9 个样本</p>
      </div>

      {renderSweepCharts()}
      {renderImprovementTable()}
    </div>
  )
}
