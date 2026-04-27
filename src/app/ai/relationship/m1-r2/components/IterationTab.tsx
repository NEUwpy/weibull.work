/**
 * M1-R2 迭代过程 Tab
 *
 * 展示 M1-R2 的迭代收敛过程：
 * - 按 (β, η, n) 分组，每组一条 δ 收敛轨迹
 * - 下方表格显示迭代详情
 */
"use client"

import React, { useEffect, useState } from 'react'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { AIChartLine } from '@/components/ai/charts/LineChart'
import { loadCSV } from '@/lib/ai-data'

interface TraceRow {
  [key: string]: number | string
  n: number
  beta: number
  eta: number
  gamma: number
  seed: number
  mse: number
  step: number
  delta: number
  est_beta: number
  est_eta: number
  est_gamma: number
}

interface GroupKey {
  n: number
  beta: number
  eta: number
}

export function IterationTab() {
  const [traces, setTraces] = useState<TraceRow[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null)

  const toNum = (v: number | string): number => typeof v === 'number' ? v : parseFloat(v) || 0

  useEffect(() => {
    async function load() {
      try {
        const data = await loadCSV<TraceRow>('/ai/data/route2_iteration_traces.csv').catch(() => [])
        setTraces(data)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) {
    return <div className="text-center py-12 text-slate-400">加载迭代数据中...</div>
  }

  if (traces.length === 0) {
    return (
      <div className="space-y-4">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-blue-700 mb-2">迭代过程可视化</h4>
          <p className="text-xs text-blue-600">
            展示 M1-R2 的 δ 收敛轨迹。每个 (β, η, n) 组合显示一条收敛成功的案例。
          </p>
        </div>
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-12 text-center">
          <div className="text-4xl mb-4">🔄</div>
          <h3 className="text-lg font-bold text-slate-700 mb-2">迭代轨迹数据待生成</h3>
          <p className="text-sm text-slate-500 max-w-lg mx-auto">
            需要运行 evaluate_route2.py 生成逐步迭代数据：
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

  // Group by (beta, eta, n), then pick first seed per group
  const groups = new Map<string, TraceRow[]>()
  for (const row of traces) {
    const key = `${row.beta}_${row.eta}_${row.n}`
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(row)
  }

  // Pick one seed per group (first one)
  const representativeTraces = new Map<string, TraceRow[]>()
  for (const [key, rows] of Array.from(groups.entries())) {
    const seedSet = new Set(rows.map((r: TraceRow) => r.seed as number))
    const seeds = Array.from(seedSet)
    const firstSeed = seeds[0]
    const seedRows = rows.filter((r: TraceRow) => r.seed === firstSeed).sort((a: TraceRow, b: TraceRow) => (a.step as number) - (b.step as number))
    representativeTraces.set(key, seedRows)
  }

  // Group by n for chart panels
  const nValues = Array.from(new Set(traces.map((r: TraceRow) => r.n as number))).sort((a: number, b: number) => a - b)
  const betaValues = Array.from(new Set(traces.map((r: TraceRow) => r.beta as number))).sort((a: number, b: number) => a - b)
  const etaValues = Array.from(new Set(traces.map((r: TraceRow) => r.eta as number))).sort((a: number, b: number) => a - b)

  const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1']

  // Stats
  const totalGroups = representativeTraces.size
  const avgSteps = Array.from(representativeTraces.values())
    .reduce((s, rows) => s + rows.length, 0) / totalGroups

  // Build line data for a chart panel (one n value, lines by beta*eta)
  const buildLines = (n: number) => {
    const lines: { id: string; label: string; data: { x: number; y: number }[]; color: string }[] = []
    let colorIdx = 0
    for (const beta of betaValues) {
      for (const eta of etaValues) {
        const key = `${beta}_${eta}_${n}`
        const rows = representativeTraces.get(key)
        if (!rows || rows.length === 0) continue
        lines.push({
          id: key,
          label: `β=${beta}, η=${eta}`,
          data: rows.map(r => ({ x: r.step, y: toNum(r.delta) })),
          color: colors[colorIdx % colors.length],
        })
        colorIdx++
      }
    }
    return lines
  }

  // Build detail table for selected group
  const buildTable = (key: string) => {
    const rows = representativeTraces.get(key)
    if (!rows) return null
    return rows
  }

  return (
    <div className="space-y-6">
      {/* 说明 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-blue-700 mb-2">迭代收敛轨迹</h4>
        <p className="text-xs text-blue-600">
          每个 (β, η, n) 组合显示一条收敛成功的案例（已排除收敛到边界 δ 的案例）。
          横轴 = 迭代步数，纵轴 = δ 值。从 δ₀=0.5 开始，逐步收敛到最优 δ。
        </p>
      </div>

      {/* 指标卡片 */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
          <div className="text-xs text-purple-500">展示组合数</div>
          <div className="text-lg font-black text-purple-700 font-mono">{totalGroups}</div>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div className="text-xs text-blue-500">平均迭代步数</div>
          <div className="text-lg font-black text-blue-700 font-mono">{avgSteps.toFixed(1)}</div>
        </div>
        <div className="bg-green-50 border border-green-200 rounded-lg p-3">
          <div className="text-xs text-green-500">总轨迹点数</div>
          <div className="text-lg font-black text-green-700 font-mono">{traces.length}</div>
        </div>
      </div>

      {/* 分面折线图：按 n 分面板 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {nValues.map(n => {
          const lines = buildLines(n)
          if (lines.length === 0) return null
          return (
            <ChartCard key={n} title={`n=${n} δ 收敛轨迹`}>
              <AIChartLine
                lines={lines}
                xLabel="迭代步数"
                yLabel="δ 值"
              />
            </ChartCard>
          )
        })}
      </div>

      {/* 组合选择表格 */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-3">迭代详情（点击组合查看）</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">β</th>
                <th className="border border-slate-200 px-3 py-2 text-center font-bold text-slate-600">η</th>
                <th className="border border-slate-200 px-3 py-2 text-center font-bold text-slate-600">n</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">初始 δ₀</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">最终 δ</th>
                <th className="border border-slate-200 px-3 py-2 text-center font-bold text-slate-600">步数</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MSE</th>
              </tr>
            </thead>
            <tbody>
              {Array.from(representativeTraces.entries()).map(([key, rows]) => {
                const first = rows[0]
                const last = rows[rows.length - 1]
                const isSelected = selectedGroup === key
                return (
                  <tr
                    key={key}
                    onClick={() => setSelectedGroup(isSelected ? null : key)}
                    className={`cursor-pointer transition-colors ${
                      isSelected ? 'bg-blue-50 border-blue-300' : 'hover:bg-slate-100'
                    }`}
                  >
                    <td className="border border-slate-200 px-3 py-2 font-mono">{first.beta}</td>
                    <td className="border border-slate-200 px-3 py-2 text-center font-mono">{first.eta}</td>
                    <td className="border border-slate-200 px-3 py-2 text-center font-mono">{first.n}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{toNum(first.delta).toFixed(4)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{toNum(last.delta).toFixed(4)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-center font-mono">{rows.length}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{toNum(first.mse).toFixed(4)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 选中组合的逐步详情 */}
      {selectedGroup && buildTable(selectedGroup) && (
        <ChartCard title={`逐步迭代详情: β=${selectedGroup.split('_')[0]}, η=${selectedGroup.split('_')[1]}, n=${selectedGroup.split('_')[2]}`}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border border-slate-200 px-3 py-2 text-center font-bold text-slate-600">步骤</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">δ</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">β̂</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">η̂</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">γ̂</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">Δδ</th>
                </tr>
              </thead>
              <tbody>
                {buildTable(selectedGroup)!.map((row, i, arr) => {
                  const prevDelta = i > 0 ? toNum(arr[i - 1].delta) : null
                  const currDelta = toNum(row.delta)
                  const diff = prevDelta !== null ? currDelta - prevDelta : null
                  return (
                    <tr key={i} className="hover:bg-slate-50">
                      <td className="border border-slate-200 px-3 py-2 text-center font-mono font-bold">{row.step}</td>
                      <td className="border border-slate-200 px-3 py-2 text-right font-mono">{currDelta.toFixed(6)}</td>
                      <td className="border border-slate-200 px-3 py-2 text-right font-mono">{!isNaN(toNum(row.est_beta)) ? toNum(row.est_beta).toFixed(4) : '—'}</td>
                      <td className="border border-slate-200 px-3 py-2 text-right font-mono">{!isNaN(toNum(row.est_eta)) ? toNum(row.est_eta).toFixed(2) : '—'}</td>
                      <td className="border border-slate-200 px-3 py-2 text-right font-mono">{!isNaN(toNum(row.est_gamma)) ? toNum(row.est_gamma).toFixed(2) : '—'}</td>
                      <td className={`border border-slate-200 px-3 py-2 text-right font-mono ${
                        diff === null ? 'text-slate-400' : Math.abs(diff) < 0.001 ? 'text-green-600' : 'text-slate-600'
                      }`}>
                        {diff !== null ? diff.toFixed(6) : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </ChartCard>
      )}
    </div>
  )
}
