/**
 * M1-R1 偏移量估计精度 Tab
 *
 * 展示：① 真值与最优 δ 的对应关系 ② 模型预测精度
 * 图表：P1(预测vs真实散点图), P2(误差分布直方图), P5(预测vs真实分布)
 */
"use client"

import React, { useEffect, useState } from 'react'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { ScatterPlot } from '@/components/ai/charts/ScatterPlot'
import { Histogram } from '@/components/ai/charts/Histogram'
import { loadCSV, validationPredictionsPath } from '@/lib/ai-data'

interface PredRow {
  [key: string]: number | string
}

const SAMPLE_SIZES = [5, 7, 10, 15, 20]

export function DeltaAccuracyTab() {
  const [data, setData] = useState<Map<number, PredRow[]>>(new Map())
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const map = new Map<number, PredRow[]>()
        for (const n of SAMPLE_SIZES) {
          try {
            const rows = await loadCSV<PredRow>(validationPredictionsPath(n))
            map.set(n, rows)
          } catch {}
        }
        setData(map)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) {
    return <div className="text-center py-12 text-slate-400">加载验证预测数据中...</div>
  }

  if (data.size === 0) {
    return (
      <div className="text-center py-12 text-slate-400">
        <p>验证预测数据未找到</p>
        <p className="text-xs mt-1">请先运行 train_model.py 生成验证预测</p>
      </div>
    )
  }

  const toNum = (v: number | string): number => typeof v === 'number' ? v : parseFloat(v) || 0

  // 汇总统计
  const allErrors: number[] = []
  for (const rows of Array.from(data.values())) {
    for (const r of rows) {
      const e = toNum(r.error)
      if (!isNaN(e)) allErrors.push(e)
    }
  }
  const mse = allErrors.reduce((s, e) => s + e * e, 0) / allErrors.length
  const mae = allErrors.reduce((s, e) => s + Math.abs(e), 0) / allErrors.length
  const bias = allErrors.reduce((s, e) => s + e, 0) / allErrors.length
  const std = Math.sqrt(allErrors.reduce((s, e) => s + (e - bias) ** 2, 0) / allErrors.length)

  return (
    <div className="space-y-6">
      {/* 说明 */}
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-purple-700 mb-2">偏移量估计精度</h4>
        <p className="text-xs text-purple-600">
          展示 M1-R1 模型预测 δ 与真实最优 δ 的对比。验证集来自蒙特卡洛模拟，已知真值参数和最优 δ。
        </p>
      </div>

      {/* 汇总指标卡片 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
          <div className="text-xs text-purple-500">总验证样本</div>
          <div className="text-lg font-black text-purple-700 font-mono">{allErrors.length}</div>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div className="text-xs text-blue-500">MSE</div>
          <div className="text-lg font-black text-blue-700 font-mono">{mse.toFixed(6)}</div>
        </div>
        <div className="bg-green-50 border border-green-200 rounded-lg p-3">
          <div className="text-xs text-green-500">MAE</div>
          <div className="text-lg font-black text-green-700 font-mono">{mae.toFixed(4)}</div>
        </div>
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
          <div className="text-xs text-amber-500">偏差 (Bias)</div>
          <div className="text-lg font-black text-amber-700 font-mono">{bias.toFixed(4)}</div>
        </div>
      </div>

      {/* 各 n 指标卡片 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {SAMPLE_SIZES.filter(n => data.has(n)).map(n => {
          const rows = data.get(n)!
          const errors = rows.map(r => toNum(r.error)).filter(e => !isNaN(e))
          const nMse = errors.reduce((s, e) => s + e * e, 0) / errors.length
          const nMae = errors.reduce((s, e) => s + Math.abs(e), 0) / errors.length
          return (
            <React.Fragment key={n}>
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
                <div className="text-xs text-purple-500">n={n} MSE</div>
                <div className="text-lg font-black text-purple-700 font-mono">{nMse.toFixed(6)}</div>
              </div>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                <div className="text-xs text-blue-500">n={n} MAE</div>
                <div className="text-lg font-black text-blue-700 font-mono">{nMae.toFixed(6)}</div>
              </div>
            </React.Fragment>
          )
        })}
      </div>

      {/* P1: 预测 vs 真实散点图 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {SAMPLE_SIZES.filter(n => data.has(n)).map(n => {
          const rows = data.get(n)!
          const scatterData = rows
            .map(r => ({ x: toNum(r.true_delta), y: toNum(r.predicted_delta) }))
            .filter(p => !isNaN(p.x) && !isNaN(p.y))

          return (
            <ChartCard key={n} title={`P1: n=${n} 预测 vs 真实 δ`}>
              <ScatterPlot
                data={scatterData}
                xLabel="真实 δ"
                yLabel="预测 δ"
                color="#8b5cf6"
                showDiagonal={true}
              />
            </ChartCard>
          )
        })}
      </div>

      {/* P2: 误差分布直方图 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {SAMPLE_SIZES.filter(n => data.has(n)).map(n => {
          const rows = data.get(n)!
          const errors = rows.map(r => toNum(r.error)).filter(e => !isNaN(e))

          return (
            <ChartCard key={n} title={`P2: n=${n} 预测误差分布`}>
              <Histogram
                values={errors}
                xLabel="预测误差 (预测δ - 真实δ)"
                yLabel="频次"
                color="#3b82f6"
              />
            </ChartCard>
          )
        })}
      </div>

      {/* P5: 预测 δ 分布 vs 真实 δ 分布 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {SAMPLE_SIZES.filter(n => data.has(n)).map(n => {
          const rows = data.get(n)!
          const trueDeltas = rows.map(r => toNum(r.true_delta)).filter(v => !isNaN(v))
          const predDeltas = rows.map(r => toNum(r.predicted_delta)).filter(v => !isNaN(v))

          return (
            <ChartCard key={n} title={`P5: n=${n} 预测 vs 真实 δ 分布`}>
              <Histogram
                values={trueDeltas}
                secondValues={predDeltas}
                xLabel="δ 值"
                yLabel="频次"
                color="#3b82f6"
                secondColor="#f59e0b"
              />
              <div className="flex justify-center gap-4 mt-2 text-xs">
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded" style={{ backgroundColor: '#3b82f6' }} />
                  <span className="text-slate-500">真实 δ</span>
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded" style={{ backgroundColor: '#f59e0b' }} />
                  <span className="text-slate-500">预测 δ</span>
                </span>
              </div>
            </ChartCard>
          )
        })}
      </div>

      {/* 验证集详情表 */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-3">验证集预测详情（前 20 条）</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-2 py-1.5 text-left font-bold text-slate-600">n</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">β</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">η</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">真实 δ</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">预测 δ</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">误差</th>
              </tr>
            </thead>
            <tbody>
              {Array.from(data.entries())
                .flatMap(([n, rows]) => rows.slice(0, 7).map(r => ({ row: r, n })))
                .slice(0, 20)
                .map(({ row: r, n }, i) => (
                  <tr key={i} className="hover:bg-slate-100/50">
                    <td className="border border-slate-200 px-2 py-1 font-mono">{n}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{r.beta}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{r.eta}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{toNum(r.true_delta).toFixed(4)}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{toNum(r.predicted_delta).toFixed(4)}</td>
                    <td className={`border border-slate-200 px-2 py-1 text-right font-mono ${
                      Math.abs(toNum(r.error)) < 0.02 ? 'text-green-600' : Math.abs(toNum(r.error)) < 0.05 ? 'text-yellow-600' : 'text-red-600'
                    }`}>
                      {toNum(r.error).toFixed(4)}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
