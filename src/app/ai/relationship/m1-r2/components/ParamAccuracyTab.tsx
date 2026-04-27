/**
 * M1-R2 三参数估计精度 Tab
 *
 * 展示 M1-R2 迭代逼近后的参数估计精度。
 * 数据来源：route2_convergence.csv（含 est_beta, est_eta, est_gamma）
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
  route2_delta: number | string
  route2_mse: number | string
  est_beta: number | string
  est_eta: number | string
  est_gamma: number | string
  steps: number
  converged: string | number
  reason: string
}

export function ParamAccuracyTab() {
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

  // Filter rows with valid estimates
  const validRows = data.filter(r => {
    const eb = toNum(r.est_beta)
    return !isNaN(eb) && eb > 0 && r.reason !== 'mdm_failed'
  })

  // Compute errors
  const betaErrors = validRows.map(r => toNum(r.est_beta) - r.beta)
  const etaErrors = validRows.map(r => toNum(r.est_eta) - r.eta)
  const gammaErrors = validRows.map(r => toNum(r.est_gamma) - r.gamma)

  const betaRelErrors = validRows.map(r => (toNum(r.est_beta) - r.beta) / r.beta)
  const etaRelErrors = validRows.map(r => (toNum(r.est_eta) - r.eta) / r.eta)
  const gammaRelErrors = validRows.map(r => (toNum(r.est_gamma) - r.gamma) / r.gamma)

  // MSE per parameter
  const betaMSE = betaErrors.reduce((s, e) => s + e * e, 0) / betaErrors.length
  const etaMSE = etaErrors.reduce((s, e) => s + e * e, 0) / etaErrors.length
  const gammaMSE = gammaErrors.reduce((s, e) => s + e * e, 0) / gammaErrors.length

  // Relative MSE per parameter
  const betaRelMSE = betaRelErrors.reduce((s, e) => s + e * e, 0) / betaRelErrors.length
  const etaRelMSE = etaRelErrors.reduce((s, e) => s + e * e, 0) / etaRelErrors.length
  const gammaRelMSE = gammaRelErrors.reduce((s, e) => s + e * e, 0) / gammaRelErrors.length

  // Group by n
  const nValues = Array.from(new Set(validRows.map(r => r.n as number))).sort((a, b) => a - b)

  // Scatter data: predicted vs true
  const betaScatter = validRows.map(r => ({ x: r.beta, y: toNum(r.est_beta) }))
  const etaScatter = validRows.map(r => ({ x: r.eta, y: toNum(r.est_eta) }))
  const gammaScatter = validRows.map(r => ({ x: r.gamma, y: toNum(r.est_gamma) }))

  // Grouped MSE by (n, beta)
  const betaValues = Array.from(new Set(validRows.map(r => r.beta as number))).sort((a, b) => a - b)
  const groupedMSE: { label: string; betaMSE: number; etaMSE: number; gammaMSE: number; totalMSE: number; count: number }[] = []
  for (const n of nValues) {
    for (const beta of betaValues) {
      const rows = validRows.filter(r => r.n === n && r.beta === beta)
      if (rows.length === 0) continue
      const bMSE = rows.reduce((s, r) => s + ((toNum(r.est_beta) - r.beta) / r.beta) ** 2, 0) / rows.length
      const eMSE = rows.reduce((s, r) => s + ((toNum(r.est_eta) - r.eta) / r.eta) ** 2, 0) / rows.length
      const gMSE = rows.reduce((s, r) => s + ((toNum(r.est_gamma) - r.gamma) / r.gamma) ** 2, 0) / rows.length
      groupedMSE.push({
        label: `n=${n},β=${beta}`,
        betaMSE: bMSE,
        etaMSE: eMSE,
        gammaMSE: gMSE,
        totalMSE: bMSE + eMSE + gMSE,
        count: rows.length,
      })
    }
  }

  return (
    <div className="space-y-6">
      {/* 说明 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-blue-700 mb-2">M1-R2 三参数估计精度</h4>
        <p className="text-xs text-blue-600">
          展示 M1-R2 迭代逼近后 (β̂, η̂, γ̂) 与真值的对比。仅统计 MDM 成功返回结果的样本。
        </p>
      </div>

      {/* 汇总指标 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div className="text-xs text-blue-500">有效样本数</div>
          <div className="text-lg font-black text-blue-700 font-mono">{validRows.length}</div>
        </div>
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
          <div className="text-xs text-purple-500">β 相对 MSE</div>
          <div className="text-lg font-black text-purple-700 font-mono">{betaRelMSE.toFixed(4)}</div>
        </div>
        <div className="bg-green-50 border border-green-200 rounded-lg p-3">
          <div className="text-xs text-green-500">η 相对 MSE</div>
          <div className="text-lg font-black text-green-700 font-mono">{etaRelMSE.toFixed(4)}</div>
        </div>
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
          <div className="text-xs text-amber-500">γ 相对 MSE</div>
          <div className="text-lg font-black text-amber-700 font-mono">{gammaRelMSE.toFixed(4)}</div>
        </div>
      </div>

      {/* 预测 vs 真实散点图 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ChartCard title="β̂ vs β（真实）">
          <ScatterPlot
            data={betaScatter}
            xLabel="真实 β"
            yLabel="估计 β"
            color="#8b5cf6"
            showDiagonal={true}
          />
        </ChartCard>
        <ChartCard title="η̂ vs η（真实）">
          <ScatterPlot
            data={etaScatter}
            xLabel="真实 η"
            yLabel="估计 η"
            color="#10b981"
            showDiagonal={true}
          />
        </ChartCard>
        <ChartCard title="γ̂ vs γ（真实）">
          <ScatterPlot
            data={gammaScatter}
            xLabel="真实 γ"
            yLabel="估计 γ"
            color="#f59e0b"
            showDiagonal={true}
          />
        </ChartCard>
      </div>

      {/* 相对误差分布直方图 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ChartCard title="β 相对误差分布">
          <Histogram
            values={betaRelErrors.filter(e => !isNaN(e) && Math.abs(e) < 5)}
            xLabel="(β̂ - β) / β"
            yLabel="频次"
            color="#8b5cf6"
          />
        </ChartCard>
        <ChartCard title="η 相对误差分布">
          <Histogram
            values={etaRelErrors.filter(e => !isNaN(e) && Math.abs(e) < 5)}
            xLabel="(η̂ - η) / η"
            yLabel="频次"
            color="#10b981"
          />
        </ChartCard>
        <ChartCard title="γ 相对误差分布">
          <Histogram
            values={gammaRelErrors.filter(e => !isNaN(e) && Math.abs(e) < 5)}
            xLabel="(γ̂ - γ) / γ"
            yLabel="频次"
            color="#f59e0b"
          />
        </ChartCard>
      </div>

      {/* 按 (n, β) 分组的相对 MSE */}
      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-3">按 (n, β) 分组的相对 MSE</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">组合</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">样本数</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">β 相对MSE</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">η 相对MSE</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">γ 相对MSE</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">总相对MSE</th>
              </tr>
            </thead>
            <tbody>
              {groupedMSE.map((row, i) => (
                <tr key={i} className="hover:bg-slate-50">
                  <td className="border border-slate-200 px-3 py-2 font-mono font-bold">{row.label}</td>
                  <td className="border border-slate-200 px-3 py-2 text-right font-mono">{row.count}</td>
                  <td className="border border-slate-200 px-3 py-2 text-right font-mono">{row.betaMSE.toFixed(4)}</td>
                  <td className="border border-slate-200 px-3 py-2 text-right font-mono">{row.etaMSE.toFixed(4)}</td>
                  <td className="border border-slate-200 px-3 py-2 text-right font-mono">{row.gammaMSE.toFixed(4)}</td>
                  <td className="border border-slate-200 px-3 py-2 text-right font-mono font-bold">{row.totalMSE.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 按 n 汇总 */}
      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-3">按样本量 n 汇总</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">n</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">样本数</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">β 相对MSE</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">η 相对MSE</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">γ 相对MSE</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">总相对MSE</th>
              </tr>
            </thead>
            <tbody>
              {nValues.map(n => {
                const rows = validRows.filter(r => r.n === n)
                const bMSE = rows.reduce((s, r) => s + ((toNum(r.est_beta) - r.beta) / r.beta) ** 2, 0) / rows.length
                const eMSE = rows.reduce((s, r) => s + ((toNum(r.est_eta) - r.eta) / r.eta) ** 2, 0) / rows.length
                const gMSE = rows.reduce((s, r) => s + ((toNum(r.est_gamma) - r.gamma) / r.gamma) ** 2, 0) / rows.length
                return (
                  <tr key={n} className="hover:bg-slate-50">
                    <td className="border border-slate-200 px-3 py-2 font-mono font-bold">{n}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{rows.length}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{bMSE.toFixed(4)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{eMSE.toFixed(4)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{gMSE.toFixed(4)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono font-bold">{(bMSE + eMSE + gMSE).toFixed(4)}</td>
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
