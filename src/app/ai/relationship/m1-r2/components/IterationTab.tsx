/**
 * M1-R2 迭代过程 Tab
 *
 * 展示 M1-R2 的迭代收敛过程
 * 数据来源：evaluate_route2.py 输出
 */
"use client"

import React, { useEffect, useState } from 'react'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { AIChartLine } from '@/components/ai/charts/LineChart'
import { Histogram } from '@/components/ai/charts/Histogram'
import { loadCSV } from '@/lib/ai-data'

interface IterationRow {
  [key: string]: number | string
}

export function IterationTab() {
  const [iterationData, setIterationData] = useState<IterationRow[]>([])
  const [loading, setLoading] = useState(true)

  const toNum = (v: number | string): number => typeof v === 'number' ? v : parseFloat(v) || 0

  useEffect(() => {
    async function load() {
      try {
        const data = await loadCSV<IterationRow>('/ai/data/iteration_stats.csv').catch(() => [])
        setIterationData(data)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) {
    return <div className="text-center py-12 text-slate-400">加载迭代数据中...</div>
  }

  if (iterationData.length === 0) {
    return (
      <div className="space-y-4">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-blue-700 mb-2">迭代过程可视化</h4>
          <p className="text-xs text-blue-600">
            展示 M1-R2 的 δ 收敛轨迹、参数收敛过程、收敛步数统计。
          </p>
        </div>
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-12 text-center">
          <div className="text-4xl mb-4">🔄</div>
          <h3 className="text-lg font-bold text-slate-700 mb-2">迭代数据待生成</h3>
          <p className="text-sm text-slate-500 max-w-lg mx-auto">
            需要运行 evaluate_route2.py 生成迭代过程数据：
          </p>
          <div className="mt-4 bg-slate-100 border border-slate-200 rounded-lg p-3 max-w-md mx-auto">
            <p className="text-xs font-mono text-slate-600">
              python evaluate_route2.py --test-samples 100 --betas 1,2,5
            </p>
          </div>
        </div>
      </div>
    )
  }

  // 统计
  const totalCases = iterationData.length
  const convergedCases = iterationData.filter(r => String(r.converged) === 'True').length
  const convergenceRate = (convergedCases / totalCases * 100).toFixed(1)
  const avgSteps = iterationData.reduce((s, r) => s + toNum(r.steps), 0) / totalCases
  const stepsDistribution = iterationData.map(r => toNum(r.steps))

  return (
    <div className="space-y-6">
      {/* 说明 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-blue-700 mb-2">迭代收敛过程</h4>
        <p className="text-xs text-blue-600">
          展示 M1-R2 迭代逼近的收敛情况。从 δ₀=0.5 开始，每步用 MDM 估计参数，再用网络预测新 δ。
        </p>
      </div>

      {/* 指标卡片 */}
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

      {/* 收敛步数分布 */}
      <ChartCard title="收敛步数分布">
        <Histogram
          values={stepsDistribution}
          xLabel="迭代步数"
          yLabel="频次"
          color="#3b82f6"
        />
      </ChartCard>

      {/* 迭代详情表 */}
      <ChartCard title="迭代收敛统计">
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
        {iterationData.length > 30 && (
          <div className="text-xs text-slate-400 mt-2 text-center">
            显示前 30 条，共 {iterationData.length} 条
          </div>
        )}
      </ChartCard>
    </div>
  )
}
