/**
 * M1-R2 方法对比 Tab
 *
 * 图表：C4(路线2迭代统计), C5(路线2 vs 固定δ对比)
 */
"use client"

import React, { useEffect, useState } from 'react'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { loadCSV } from '@/lib/ai-data'

interface IterationRow { [key: string]: number | string }
interface Route2ComparisonRow { [key: string]: number | string }

export function CompareTab() {
  const [iterationData, setIterationData] = useState<IterationRow[]>([])
  const [route2Data, setRoute2Data] = useState<Route2ComparisonRow[]>([])
  const [loading, setLoading] = useState(true)

  const toNum = (v: number | string): number => typeof v === 'number' ? v : parseFloat(v) || 0

  useEffect(() => {
    async function load() {
      try {
        const [iter, route2] = await Promise.all([
          loadCSV<IterationRow>('/ai/data/iteration_stats.csv').catch(() => []),
          loadCSV<Route2ComparisonRow>('/ai/data/route2_comparison.csv').catch(() => []),
        ])
        setIterationData(iter)
        setRoute2Data(route2)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) {
    return <div className="text-center py-12 text-slate-400">加载对比数据中...</div>
  }

  const hasData = iterationData.length > 0 || route2Data.length > 0

  if (!hasData) {
    return (
      <div className="space-y-4">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-blue-700 mb-2">M1-R2 方法对比</h4>
          <p className="text-xs text-blue-600">
            对比 M1-R2 迭代逼近与固定 δ 基准的精度。
          </p>
        </div>
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-12 text-center">
          <p className="text-sm text-slate-400">对比数据未找到</p>
          <p className="text-xs mt-1 text-slate-300">请先运行 evaluate_route2.py</p>
        </div>
      </div>
    )
  }

  // C4: Iteration stats
  const renderIterationStats = () => {
    if (iterationData.length === 0) return null

    const totalCases = iterationData.length
    const convergedCases = iterationData.filter(r => String(r.converged) === 'True').length
    const convergenceRate = (convergedCases / totalCases * 100).toFixed(1)
    const avgSteps = iterationData.reduce((s, r) => s + toNum(r.steps), 0) / totalCases

    return (
      <div className="space-y-4">
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
            <div className="text-xs text-purple-500">测试样本数</div>
            <div className="text-lg font-black text-purple-700 font-mono">{totalCases}</div>
          </div>
          <div className="bg-green-50 border border-green-200 rounded-lg p-3">
            <div className="text-xs text-green-500">收敛率</div>
            <div className="text-lg font-black text-green-700 font-mono">{convergenceRate}%</div>
          </div>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <div className="text-xs text-blue-500">平均迭代步数</div>
            <div className="text-lg font-black text-blue-700 font-mono">{avgSteps.toFixed(1)}</div>
          </div>
        </div>

        <ChartCard title="C4: M1-R2 迭代收敛统计">
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border border-slate-200 px-2 py-1.5 text-left font-bold text-slate-600">β</th>
                  <th className="border border-slate-200 px-2 py-1.5 text-center font-bold text-slate-600">η</th>
                  <th className="border border-slate-200 px-2 py-1.5 text-center font-bold text-slate-600">n</th>
                  <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">最终 δ</th>
                  <th className="border border-slate-200 px-2 py-1.5 text-center font-bold text-slate-600">步数</th>
                  <th className="border border-slate-200 px-2 py-1.5 text-center font-bold text-slate-600">收敛</th>
                </tr>
              </thead>
              <tbody>
                {iterationData.slice(0, 30).map((r, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="border border-slate-200 px-2 py-1 font-mono">{r.beta}</td>
                    <td className="border border-slate-200 px-2 py-1 text-center font-mono">{r.eta}</td>
                    <td className="border border-slate-200 px-2 py-1 text-center font-mono">{r.n}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{toNum(r.final_delta).toFixed(6)}</td>
                    <td className="border border-slate-200 px-2 py-1 text-center font-mono">{r.steps}</td>
                    <td className={`border border-slate-200 px-2 py-1 text-center font-mono ${
                      String(r.converged) === 'True' ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {String(r.converged) === 'True' ? 'Yes' : 'No'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ChartCard>
      </div>
    )
  }

  // C5: Route 2 vs Fixed Delta comparison
  const renderRoute2Comparison = () => {
    if (route2Data.length === 0) return null

    return (
      <ChartCard title="C5: M1-R2 vs 固定 δ 对比">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
          <p className="text-xs text-blue-700 font-medium">
            M1-R2（迭代逼近）与固定 δ 基准的 MSE 对比。
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-3 py-2 text-center font-bold text-slate-600">n</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">M1-R2 MSE</th>
                <th className="border border-slate-200 px-3 py-2 text-center font-bold text-slate-600">收敛率</th>
                <th className="border border-slate-200 px-3 py-2 text-center font-bold text-slate-600">平均步数</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">δ=0.1 MSE</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">δ=0.2 MSE</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">δ=0.5 MSE</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">vs δ=0.2</th>
              </tr>
            </thead>
            <tbody>
              {route2Data.map((r, i) => {
                const improv = toNum(r.improvement_vs_0_2 ?? 0)
                return (
                  <tr key={i} className={i === route2Data.length - 1 ? 'bg-blue-50 font-bold' : 'hover:bg-slate-50'}>
                    <td className="border border-slate-200 px-3 py-2 text-center font-mono">{r.n}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{toNum(r.route2_mse).toFixed(4)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-center font-mono">{toNum(r.route2_convergence_rate).toFixed(1)}%</td>
                    <td className="border border-slate-200 px-3 py-2 text-center font-mono">{toNum(r.route2_avg_steps).toFixed(1)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{toNum(r.fixed_delta_0_1_mse ?? 0).toFixed(4)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{toNum(r.fixed_delta_0_2_mse ?? 0).toFixed(4)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{toNum(r.fixed_delta_0_5_mse ?? 0).toFixed(4)}</td>
                    <td className={`border border-slate-200 px-3 py-2 text-right font-mono ${
                      improv > 0 ? 'text-green-600' : improv < 0 ? 'text-red-600' : 'text-slate-500'
                    }`}>
                      {improv > 0 ? '+' : ''}{improv.toFixed(1)}%
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </ChartCard>
    )
  }

  return (
    <div className="space-y-6">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-blue-700 mb-2">M1-R2 对比维度</h4>
        <ul className="text-xs text-blue-600 space-y-1">
          <li>• M1-R2 迭代收敛统计（收敛率、平均步数）</li>
          <li>• M1-R2 vs 固定 δ 基准对比</li>
        </ul>
      </div>

      {renderIterationStats()}
      {renderRoute2Comparison()}
    </div>
  )
}
