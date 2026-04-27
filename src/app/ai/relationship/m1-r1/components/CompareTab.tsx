/**
 * M1-R1 方法对比 Tab
 *
 * 图表：C0(固定δ精度), C1(AI vs 固定δ), C2(δ sweep), C3(改善热力图)
 */
"use client"

import React, { useEffect, useState } from 'react'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { AIChartLine } from '@/components/ai/charts/LineChart'
import { BarChart } from '@/components/ai/charts/BarChart'
import { loadCSV } from '@/lib/ai-data'

interface ComparisonRow { [key: string]: number | string }
interface SweepRow { [key: string]: number | string }
interface ImprovementRow { [key: string]: number | string }
interface FixedDeltaRow { [key: string]: number | string }

const SAMPLE_SIZES = [5, 7, 10, 15, 20]
const FIXED_DELTAS = [0.01, 0.05, 0.1, 0.2, 0.5]

export function CompareTab() {
  const [comparisonData, setComparisonData] = useState<ComparisonRow[]>([])
  const [sweepData, setSweepData] = useState<SweepRow[]>([])
  const [improvementData, setImprovementData] = useState<ImprovementRow[]>([])
  const [fixedDeltaData, setFixedDeltaData] = useState<FixedDeltaRow[]>([])
  const [loading, setLoading] = useState(true)

  const toNum = (v: number | string): number => typeof v === 'number' ? v : parseFloat(v) || 0

  useEffect(() => {
    async function load() {
      try {
        const [comp, sweep, imp, fixedDelta] = await Promise.all([
          loadCSV<ComparisonRow>('/ai/data/comparison_ai_vs_fixed.csv').catch(() => []),
          loadCSV<SweepRow>('/ai/data/comparison_sweep.csv').catch(() => []),
          loadCSV<ImprovementRow>('/ai/data/comparison_improvement.csv').catch(() => []),
          loadCSV<FixedDeltaRow>('/ai/data/fixed_delta_comparison.csv').catch(() => []),
        ])
        setComparisonData(comp)
        setSweepData(sweep)
        setImprovementData(imp)
        setFixedDeltaData(fixedDelta)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) {
    return <div className="text-center py-12 text-slate-400">加载对比数据中...</div>
  }

  const hasData = comparisonData.length > 0 || sweepData.length > 0

  if (!hasData) {
    return (
      <div className="text-center py-12 text-slate-400">
        <p>对比数据未找到</p>
        <p className="text-xs mt-1">请先运行 generate_comparison_data.py</p>
      </div>
    )
  }

  // C0: Fixed delta MSE comparison
  const renderFixedDeltaChart = () => {
    if (fixedDeltaData.length === 0) return null

    const ns = [5, 7, 10, 15, 20]
    const deltas = [0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.7, 1.0]
    const colors = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#3b82f6']

    const lines = ns.map((n, i) => ({
      id: `n${n}`,
      label: `n=${n}`,
      data: deltas
        .map(d => {
          const row = fixedDeltaData.find(r => toNum(r.n) === n && toNum(r.delta) === d)
          return row ? { x: d, y: toNum(row.mean_mse) } : null
        })
        .filter((p): p is { x: number; y: number } => p !== null && !isNaN(p.y)),
      color: colors[i],
    }))

    const summaryRows = ns.map(n => {
      const rows = fixedDeltaData.filter(r => toNum(r.n) === n)
      const avgMse = rows.reduce((s, r) => s + toNum(r.mean_mse), 0) / rows.length
      const bestDelta = rows.reduce((best, r) => toNum(r.mean_mse) < toNum(best.mean_mse) ? r : best, rows[0])
      return { n, avgMse, bestDelta: toNum(bestDelta.delta), bestMse: toNum(bestDelta.mean_mse) }
    })

    return (
      <div className="space-y-4">
        <ChartCard title="C0: 固定 δ 下 MDM 估计精度（证明 MDM 本身正常）">
          <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-4">
            <p className="text-xs text-green-700 font-medium">
              核心结论：在相同 δ 下，n 越大 MSE 越低，完全符合统计规律。
              MDM 方法本身没有问题，&quot;n=5 优于 n=15&quot;是 δ 搜索过程的统计假象。
            </p>
          </div>
          <AIChartLine lines={lines} xLabel="δ" yLabel="Mean Relative MSE" />
        </ChartCard>

        <ChartCard title="C0: 各 n 的平均 MSE 对比">
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border border-slate-200 px-3 py-2 text-center font-bold text-slate-600">n</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">平均 MSE</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">最优 δ</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">最优 δ 处 MSE</th>
                </tr>
              </thead>
              <tbody>
                {summaryRows.map((r, i) => (
                  <tr key={r.n} className={i === summaryRows.length - 1 ? 'bg-green-50 font-bold' : 'hover:bg-slate-50'}>
                    <td className="border border-slate-200 px-3 py-2 text-center font-mono">{r.n}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{r.avgMse.toFixed(4)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{r.bestDelta.toFixed(2)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{r.bestMse.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ChartCard>
      </div>
    )
  }

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

  // C1: AI vs fixed delta MSE comparison bar chart
  const renderComparisonBars = () => {
    if (comparisonData.length === 0) return null

    const betas = [1.0, 2.0, 5.0]
    const summaryData: { name: string; ai: number }[] = []

    for (const beta of betas) {
      for (const n of SAMPLE_SIZES) {
        const rows = comparisonData.filter(r => toNum(r.beta) === beta && toNum(r.n) === n)
        if (rows.length === 0) continue
        const avg = (col: string) => {
          const vals = rows.map(r => toNum(r[col])).filter(v => v > 0 && v < 1e10)
          return vals.length > 0 ? vals.reduce((s, v) => s + v, 0) / vals.length : 0
        }
        summaryData.push({ name: `β=${beta},n=${n}`, ai: avg('ai_mse') })
      }
    }

    return (
      <ChartCard title="C1: AI δ vs 固定 δ 平均 MSE 对比 (各组合)">
        <BarChart data={summaryData.map(d => ({ label: d.name, value: d.ai, color: '#8b5cf6' }))} yLabel="AI Mean MSE" />
      </ChartCard>
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
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-blue-700 mb-2">对比维度</h4>
        <ul className="text-xs text-blue-600 space-y-1">
          <li>• 固定 δ 下的 MDM 精度（证明 MDM 本身 n 越大越好）</li>
          <li>• AI 预测 δ vs 多个固定 δ 值（0.01, 0.05, 0.10, 0.20, 0.50）</li>
          <li>• 不同 (β, n) 组合下的改善程度</li>
        </ul>
      </div>

      {renderFixedDeltaChart()}
      {renderSweepCharts()}
      {renderComparisonBars()}
      {renderImprovementTable()}
    </div>
  )
}
