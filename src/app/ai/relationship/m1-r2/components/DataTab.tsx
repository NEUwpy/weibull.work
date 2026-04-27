/**
 * M1-R2 训练数据 Tab
 *
 * M1-R2 使用与 M1-R1 相同的训练数据，但输入不同：
 * M1-R1 输入样本，M1-R2 输入参数真值 (β, η, γ)
 */
"use client"

import React, { useEffect, useState } from 'react'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { ScatterPlot } from '@/components/ai/charts/ScatterPlot'
import { loadCSV, trainingDataPath, computeStats, groupBy } from '@/lib/ai-data'

interface DataRow {
  n: number
  beta: number
  eta: number
  gamma: number
  optimal_delta: number
  [key: string]: number
}

const SAMPLE_SIZES = [5, 7, 10, 15, 20]

export function DataTab() {
  const [data, setData] = useState<Map<number, DataRow[]>>(new Map())
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const map = new Map<number, DataRow[]>()
        for (const n of SAMPLE_SIZES) {
          try {
            const rows = await loadCSV<DataRow>(trainingDataPath(n))
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
    return <div className="text-center py-12 text-slate-400">加载训练数据中...</div>
  }

  if (data.size === 0) {
    return (
      <div className="text-center py-12 text-slate-400">
        <p>训练数据未找到</p>
        <p className="text-xs mt-1">请先运行 generate_training_data.py 生成训练数据</p>
      </div>
    )
  }

  const allData = Array.from(data.values()).flat()

  // M1-R2 特有：参数 → δ 的散点图
  const betaVsDelta = allData
    .filter(d => !isNaN(d.optimal_delta))
    .map(d => ({ x: d.beta, y: d.optimal_delta }))

  const etaVsDelta = allData
    .filter(d => !isNaN(d.optimal_delta))
    .map(d => ({ x: d.eta, y: d.optimal_delta }))

  return (
    <div className="space-y-6">
      {/* 说明 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-blue-700 mb-2">M1-R2 训练数据</h4>
        <p className="text-xs text-blue-600">
          M1-R2 使用与 M1-R1 相同的训练数据，但网络输入不同：
          M1-R1 输入样本值（n 个失效时间），M1-R2 输入参数真值 (β, η, γ)。
          因此 M1-R2 只需一个公共模型，不按 n 分。
        </p>
      </div>

      {/* 参数空间说明 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div className="text-xs text-blue-500">参数组合</div>
          <div className="text-lg font-black text-blue-700">45 组</div>
          <div className="text-xs text-blue-400">3×3×1×5</div>
        </div>
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
          <div className="text-xs text-purple-500">总样本数</div>
          <div className="text-lg font-black text-purple-700">{allData.length.toLocaleString()}</div>
          <div className="text-xs text-purple-400">有效记录</div>
        </div>
        <div className="bg-green-50 border border-green-200 rounded-lg p-3">
          <div className="text-xs text-green-500">β 值</div>
          <div className="text-lg font-black text-green-700">1, 2, 5</div>
          <div className="text-xs text-green-400">形状参数</div>
        </div>
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
          <div className="text-xs text-amber-500">η 值</div>
          <div className="text-lg font-black text-amber-700">100, 1000, 5000</div>
          <div className="text-xs text-amber-400">尺度参数</div>
        </div>
      </div>

      {/* M1-R2 特有散点图：参数 vs δ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="M1-R2: β vs 最优 δ">
          <ScatterPlot data={betaVsDelta} xLabel="β (形状参数)" yLabel="最优 δ" color="#3b82f6" />
        </ChartCard>
        <ChartCard title="M1-R2: η vs 最优 δ">
          <ScatterPlot data={etaVsDelta} xLabel="η (尺度参数)" yLabel="最优 δ" color="#10b981" />
        </ChartCard>
      </div>

      {/* 与 M1-R1 数据的区别 */}
      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-3">M1-R1 vs M1-R2 数据使用方式</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">维度</th>
                <th className="border border-slate-200 px-3 py-2 text-center font-bold text-purple-600">M1-R1</th>
                <th className="border border-slate-200 px-3 py-2 text-center font-bold text-blue-600">M1-R2</th>
              </tr>
            </thead>
            <tbody>
              <tr><td className="border border-slate-200 px-3 py-2 font-bold">网络输入</td><td className="border border-slate-200 px-3 py-2 text-center">样本值（n 个）</td><td className="border border-slate-200 px-3 py-2 text-center">参数真值 (β,η,γ)</td></tr>
              <tr><td className="border border-slate-200 px-3 py-2 font-bold">模型数量</td><td className="border border-slate-200 px-3 py-2 text-center">5 个（按 n）</td><td className="border border-slate-200 px-3 py-2 text-center">1 个（公共）</td></tr>
              <tr><td className="border border-slate-200 px-3 py-2 font-bold">训练目标</td><td className="border border-slate-200 px-3 py-2 text-center">样本 → δ</td><td className="border border-slate-200 px-3 py-2 text-center">(β,η,γ) → δ</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
