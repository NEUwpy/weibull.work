/**
 * M1-R2 偏移量估计精度 Tab
 *
 * 展示 M1-R2 迭代逼近后的最终 δ 分布与收敛情况。
 * 数据来源：route2_convergence.csv
 */
"use client"

import React, { useEffect, useState } from 'react'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { ScatterPlot } from '@/components/ai/charts/ScatterPlot'
import { Histogram } from '@/components/ai/charts/Histogram'
import { loadCSV } from '@/lib/ai-data'

interface ConvRow {
  [key: string]: number | string
  n: number
  beta: number
  eta: number
  gamma: number
  seed: number
  route2_delta: number | string
  route2_mse: number | string
  est_beta: number | string
  est_eta: number | string
  est_gamma: number | string
  steps: number
  converged: string | number
  reason: string
}

export function DeltaAccuracyTab() {
  const [data, setData] = useState<ConvRow[]>([])
  const [loading, setLoading] = useState(true)

  const toNum = (v: number | string): number => typeof v === 'number' ? v : parseFloat(v) || 0

  useEffect(() => {
    async function load() {
      try {
        const rows = await loadCSV<ConvRow>('/ai/data/route2_convergence.csv').catch(() => [])
        setData(rows)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) {
    return <div className="text-center py-12 text-slate-400">加载评估数据中...</div>
  }

  if (data.length === 0) {
    return (
      <div className="text-center py-12 text-slate-400">
        <p>评估数据未找到</p>
        <p className="text-xs mt-1">请先运行 evaluate_route2.py 生成评估数据</p>
      </div>
    )
  }

  // Filter converged non-MDM-failure rows with valid delta
  const validRows = data.filter(r => {
    const d = toNum(r.route2_delta)
    return !isNaN(d) && d > 0 && r.reason !== 'mdm_failed'
  })
  const convergedRows = validRows.filter(r => {
    const conv = String(r.converged).toLowerCase()
    return conv === 'true' || conv === '1'
  })

  // Stats
  const allDeltas = convergedRows.map(r => toNum(r.route2_delta))
  const allMSE = convergedRows.map(r => toNum(r.route2_mse))
  const avgDelta = allDeltas.reduce((s, v) => s + v, 0) / allDeltas.length
  const avgMSE = allMSE.reduce((s, v) => s + v, 0) / allMSE.length
  const medianDelta = [...allDeltas].sort((a, b) => a - b)[Math.floor(allDeltas.length / 2)]

  // Group by n
  const nValues = Array.from(new Set(convergedRows.map(r => r.n as number))).sort((a, b) => a - b)
  const byN = new Map<number, ConvRow[]>()
  for (const r of convergedRows) {
    if (!byN.has(r.n as number)) byN.set(r.n as number, [])
    byN.get(r.n as number)!.push(r)
  }

  // Group by beta
  const betaValues = Array.from(new Set(convergedRows.map(r => r.beta as number))).sort((a, b) => a - b)
  const byBeta = new Map<number, ConvRow[]>()
  for (const r of convergedRows) {
    if (!byBeta.has(r.beta as number)) byBeta.set(r.beta as number, [])
    byBeta.get(r.beta as number)!.push(r)
  }

  // δ vs MSE scatter data
  const deltaVsMSE = convergedRows
    .map(r => ({ x: toNum(r.route2_delta), y: toNum(r.route2_mse) }))
    .filter(p => !isNaN(p.x) && !isNaN(p.y) && p.y < 20)

  // δ by (beta, n) grouped stats
  const groupStats: { label: string; mean: number; median: number; std: number; count: number }[] = []
  for (const beta of betaValues) {
    for (const n of nValues) {
      const rows = convergedRows.filter(r => r.beta === beta && r.n === n)
      if (rows.length === 0) continue
      const deltas = rows.map(r => toNum(r.route2_delta))
      const mean = deltas.reduce((s, v) => s + v, 0) / deltas.length
      const sorted = [...deltas].sort((a, b) => a - b)
      const median = sorted[Math.floor(sorted.length / 2)]
      const std = Math.sqrt(deltas.reduce((s, v) => s + (v - mean) ** 2, 0) / deltas.length)
      groupStats.push({ label: `β=${beta},n=${n}`, mean, median, std, count: rows.length })
    }
  }

  return (
    <div className="space-y-6">
      {/* 说明 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-blue-700 mb-2">M1-R2 偏移量估计精度</h4>
        <p className="text-xs text-blue-600">
          展示 M1-R2 迭代逼近收敛后的最终 δ 分布。M1-R2 不直接预测 δ，而是通过迭代收敛到一个稳定值。
          以下仅统计收敛成功且未到达边界的样本。
        </p>
      </div>

      {/* 汇总指标 */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div className="text-xs text-blue-500">收敛样本数</div>
          <div className="text-lg font-black text-blue-700 font-mono">{convergedRows.length}</div>
        </div>
        <div className="bg-green-50 border border-green-200 rounded-lg p-3">
          <div className="text-xs text-green-500">平均 δ</div>
          <div className="text-lg font-black text-green-700 font-mono">{avgDelta.toFixed(4)}</div>
        </div>
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
          <div className="text-xs text-purple-500">中位数 δ</div>
          <div className="text-lg font-black text-purple-700 font-mono">{medianDelta.toFixed(4)}</div>
        </div>
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
          <div className="text-xs text-amber-500">平均 MSE</div>
          <div className="text-lg font-black text-amber-700 font-mono">{avgMSE.toFixed(4)}</div>
        </div>
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <div className="text-xs text-slate-500">总评估样本</div>
          <div className="text-lg font-black text-slate-700 font-mono">{data.length}</div>
        </div>
      </div>

      {/* δ 分布直方图 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="最终 δ 分布（收敛样本）">
          <Histogram
            values={allDeltas}
            xLabel="最终 δ 值"
            yLabel="频次"
            color="#3b82f6"
          />
        </ChartCard>
        <ChartCard title="最终 δ vs 参数估计 MSE">
          <ScatterPlot
            data={deltaVsMSE}
            xLabel="最终 δ"
            yLabel="相对 MSE"
            color="#8b5cf6"
          />
        </ChartCard>
      </div>

      {/* 按 n 分组的 δ 统计 */}
      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-3">按样本量 n 分组的 δ 统计</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">n</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">样本数</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">平均 δ</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">中位数 δ</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">标准差</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">平均 MSE</th>
              </tr>
            </thead>
            <tbody>
              {nValues.map(n => {
                const rows = byN.get(n) || []
                const deltas = rows.map(r => toNum(r.route2_delta))
                const mses = rows.map(r => toNum(r.route2_mse))
                const mean = deltas.reduce((s, v) => s + v, 0) / deltas.length
                const sorted = [...deltas].sort((a, b) => a - b)
                const median = sorted[Math.floor(sorted.length / 2)]
                const std = Math.sqrt(deltas.reduce((s, v) => s + (v - mean) ** 2, 0) / deltas.length)
                const avgMse = mses.reduce((s, v) => s + v, 0) / mses.length
                return (
                  <tr key={n} className="hover:bg-slate-50">
                    <td className="border border-slate-200 px-3 py-2 font-mono font-bold">{n}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{rows.length}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{mean.toFixed(4)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{median.toFixed(4)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{std.toFixed(4)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{avgMse.toFixed(4)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 按 (β, n) 分组的 δ 统计 */}
      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-3">按 (β, n) 分组的 δ 统计</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">组合</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">样本数</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">平均 δ</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">中位数 δ</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">标准差</th>
              </tr>
            </thead>
            <tbody>
              {groupStats.map((gs, i) => (
                <tr key={i} className="hover:bg-slate-50">
                  <td className="border border-slate-200 px-3 py-2 font-mono font-bold">{gs.label}</td>
                  <td className="border border-slate-200 px-3 py-2 text-right font-mono">{gs.count}</td>
                  <td className="border border-slate-200 px-3 py-2 text-right font-mono">{gs.mean.toFixed(4)}</td>
                  <td className="border border-slate-200 px-3 py-2 text-right font-mono">{gs.median.toFixed(4)}</td>
                  <td className="border border-slate-200 px-3 py-2 text-right font-mono">{gs.std.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 各 n 的 δ 分布直方图 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {nValues.map(n => {
          const rows = byN.get(n) || []
          const deltas = rows.map(r => toNum(r.route2_delta))
          return (
            <ChartCard key={n} title={`n=${n} 最终 δ 分布`}>
              <Histogram
                values={deltas}
                xLabel="最终 δ"
                yLabel="频次"
                color="#3b82f6"
              />
            </ChartCard>
          )
        })}
      </div>

      {/* 收敛原因统计 */}
      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-3">收敛原因统计</h4>
        <p className="text-xs text-amber-600 mb-3 font-medium">
          ⚠ 注：mdm_failed 数据基于 S4.9 前历史旧口径，S4.9 后默认 MDM 已重写，待重算更新。
        </p>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {Array.from(new Set(data.map(r => r.reason as string))).map(reason => {
            const count = data.filter(r => r.reason === reason).length
            const pct = (count / data.length * 100).toFixed(1)
            const color = reason === 'delta_stable' ? 'green' : reason === 'mdm_failed' ? 'red' : 'amber'
            return (
              <div key={reason} className={`bg-${color}-50 border border-${color}-200 rounded-lg p-3`}>
                <div className={`text-xs text-${color}-500`}>{reason}</div>
                <div className={`text-lg font-black text-${color}-700 font-mono`}>{count} ({pct}%)</div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
