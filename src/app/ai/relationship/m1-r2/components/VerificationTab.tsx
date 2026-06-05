/**
 * M1-R2 可信性验证 Tab
 *
 * 展示 M1-R2 迭代逼近的验证案例。
 * 数据来源：route2_convergence.csv
 */
"use client"

import React, { useEffect, useState } from 'react'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { ScatterPlot } from '@/components/ai/charts/ScatterPlot'
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

export function VerificationTab() {
  const [data, setData] = useState<ConvRow[]>([])
  const [loading, setLoading] = useState(true)
  const [filterN, setFilterN] = useState<number | null>(null)
  const [filterBeta, setFilterBeta] = useState<number | null>(null)
  const [sortBy, setSortBy] = useState<'mse' | 'n' | 'beta'>('mse')

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
    return <div className="text-center py-12 text-slate-400">加载验证数据中...</div>
  }

  if (data.length === 0) {
    return (
      <div className="text-center py-12 text-slate-400">
        <p>验证数据未找到</p>
        <p className="text-xs mt-1">请先运行 evaluate_route2.py 生成评估数据</p>
      </div>
    )
  }

  // Filter valid rows (has estimates)
  const validRows = data.filter(r => {
    const eb = toNum(r.est_beta)
    return !isNaN(eb) && eb > 0 && r.reason !== 'mdm_failed'
  })

  // Apply filters
  let filtered = validRows
  if (filterN !== null) filtered = filtered.filter(r => r.n === filterN)
  if (filterBeta !== null) filtered = filtered.filter(r => r.beta === filterBeta)

  // Sort
  const sorted = [...filtered].sort((a, b) => {
    if (sortBy === 'mse') return toNum(a.route2_mse) - toNum(b.route2_mse)
    if (sortBy === 'n') return (a.n as number) - (b.n as number)
    return (a.beta as number) - (b.beta as number)
  })

  // Unique filter values
  const nValues = Array.from(new Set(validRows.map(r => r.n as number))).sort((a, b) => a - b)
  const betaValues = Array.from(new Set(validRows.map(r => r.beta as number))).sort((a, b) => a - b)

  // Convergence stats
  const totalConv = data.filter(r => {
    const conv = String(r.converged).toLowerCase()
    return conv === 'true' || conv === '1'
  }).length
  const totalMDMFail = data.filter(r => r.reason === 'mdm_failed').length
  const convRate = (totalConv / data.length * 100).toFixed(1)

  // Scatter data for good cases (bottom 50% MSE)
  const sortedByMSE = [...validRows].sort((a, b) => toNum(a.route2_mse) - toNum(b.route2_mse))
  const goodCases = sortedByMSE.slice(0, Math.floor(sortedByMSE.length / 2))
  const betaScatter = goodCases.map(r => ({ x: r.beta, y: toNum(r.est_beta) }))
  const etaScatter = goodCases.map(r => ({ x: r.eta, y: toNum(r.est_eta) }))
  const gammaScatter = goodCases.map(r => ({ x: r.gamma, y: toNum(r.est_gamma) }))

  return (
    <div className="space-y-6">
      {/* 说明 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-blue-700 mb-2">M1-R2 可信性验证</h4>
        <p className="text-xs text-blue-600">
          展示 M1-R2 迭代逼近的验证案例。每个案例使用已知参数的蒙特卡洛样本，
          通过迭代收敛后的 δ 运行 MDM 得到参数估计。
          表格默认按 MSE 升序排列（最好的案例在前）。
        </p>
        <p className="text-xs text-amber-600 mt-2 font-medium">
          ⚠ 注：本页 MDM 失败数据基于 S4.9 前历史旧口径（旧版 MDM 的 no_intersection 机制），S4.9 后默认 MDM 已重写，待重算更新。
        </p>
      </div>

      {/* 收敛统计 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div className="text-xs text-blue-500">总评估样本</div>
          <div className="text-lg font-black text-blue-700 font-mono">{data.length}</div>
        </div>
        <div className="bg-green-50 border border-green-200 rounded-lg p-3">
          <div className="text-xs text-green-500">收敛成功</div>
          <div className="text-lg font-black text-green-700 font-mono">{totalConv} ({convRate}%)</div>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
          <div className="text-xs text-red-500">MDM 失败</div>
          <div className="text-lg font-black text-red-700 font-mono">{totalMDMFail}</div>
        </div>
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
          <div className="text-xs text-purple-500">有效估计</div>
          <div className="text-lg font-black text-purple-700 font-mono">{validRows.length}</div>
        </div>
      </div>

      {/* 参数估计散点图（优秀案例） */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ChartCard title="β̂ vs β（MSE 前 50% 案例）">
          <ScatterPlot
            data={betaScatter}
            xLabel="真实 β"
            yLabel="估计 β"
            color="#8b5cf6"
            showDiagonal={true}
          />
        </ChartCard>
        <ChartCard title="η̂ vs η（MSE 前 50% 案例）">
          <ScatterPlot
            data={etaScatter}
            xLabel="真实 η"
            yLabel="估计 η"
            color="#10b981"
            showDiagonal={true}
          />
        </ChartCard>
        <ChartCard title="γ̂ vs γ（MSE 前 50% 案例）">
          <ScatterPlot
            data={gammaScatter}
            xLabel="真实 γ"
            yLabel="估计 γ"
            color="#f59e0b"
            showDiagonal={true}
          />
        </ChartCard>
      </div>

      {/* 筛选器 */}
      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-3">验证案例表</h4>
        <div className="flex flex-wrap gap-3 mb-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">n:</span>
            <button
              onClick={() => setFilterN(null)}
              className={`px-2 py-1 text-xs rounded ${filterN === null ? 'bg-blue-100 text-blue-700 font-bold' : 'bg-slate-100 text-slate-600'}`}
            >全部</button>
            {nValues.map(n => (
              <button
                key={n}
                onClick={() => setFilterN(filterN === n ? null : n)}
                className={`px-2 py-1 text-xs rounded ${filterN === n ? 'bg-blue-100 text-blue-700 font-bold' : 'bg-slate-100 text-slate-600'}`}
              >{n}</button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">β:</span>
            <button
              onClick={() => setFilterBeta(null)}
              className={`px-2 py-1 text-xs rounded ${filterBeta === null ? 'bg-purple-100 text-purple-700 font-bold' : 'bg-slate-100 text-slate-600'}`}
            >全部</button>
            {betaValues.map(b => (
              <button
                key={b}
                onClick={() => setFilterBeta(filterBeta === b ? null : b)}
                className={`px-2 py-1 text-xs rounded ${filterBeta === b ? 'bg-purple-100 text-purple-700 font-bold' : 'bg-slate-100 text-slate-600'}`}
              >{b}</button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">排序:</span>
            <button
              onClick={() => setSortBy('mse')}
              className={`px-2 py-1 text-xs rounded ${sortBy === 'mse' ? 'bg-green-100 text-green-700 font-bold' : 'bg-slate-100 text-slate-600'}`}
            >MSE</button>
            <button
              onClick={() => setSortBy('n')}
              className={`px-2 py-1 text-xs rounded ${sortBy === 'n' ? 'bg-green-100 text-green-700 font-bold' : 'bg-slate-100 text-slate-600'}`}
            >n</button>
            <button
              onClick={() => setSortBy('beta')}
              className={`px-2 py-1 text-xs rounded ${sortBy === 'beta' ? 'bg-green-100 text-green-700 font-bold' : 'bg-slate-100 text-slate-600'}`}
            >β</button>
          </div>
        </div>
        <p className="text-xs text-slate-400 mb-2">显示 {sorted.length} / {validRows.length} 条</p>
        <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
          <table className="w-full text-sm border-collapse">
            <thead className="sticky top-0 bg-slate-100">
              <tr>
                <th className="border border-slate-200 px-2 py-1.5 text-left font-bold text-slate-600">n</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">β</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">η</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">最终 δ</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">β̂</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">η̂</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">γ̂</th>
                <th className="border border-slate-200 px-2 py-1.5 text-center font-bold text-slate-600">步数</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">MSE</th>
              </tr>
            </thead>
            <tbody>
              {sorted.slice(0, 200).map((r, i) => {
                const mse = toNum(r.route2_mse)
                const mseColor = mse < 0.5 ? 'text-green-600' : mse < 2 ? 'text-yellow-600' : 'text-red-600'
                return (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="border border-slate-200 px-2 py-1 font-mono">{r.n}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{r.beta}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{r.eta}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{toNum(r.route2_delta).toFixed(4)}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{toNum(r.est_beta).toFixed(4)}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{toNum(r.est_eta).toFixed(1)}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{toNum(r.est_gamma).toFixed(1)}</td>
                    <td className="border border-slate-200 px-2 py-1 text-center font-mono">{r.steps}</td>
                    <td className={`border border-slate-200 px-2 py-1 text-right font-mono font-bold ${mseColor}`}>
                      {mse.toFixed(4)}
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
