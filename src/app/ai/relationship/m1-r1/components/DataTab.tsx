/**
 * M1-R1 训练数据可视化 Tab
 *
 * 图表：D1(δ分布直方图), D2(按β,n分组箱型图), D3-D5(散点图), D6(无解率), D7(参数空间)
 */
"use client"

import React, { useEffect, useState } from 'react'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { Histogram } from '@/components/ai/charts/Histogram'
import { ScatterPlot } from '@/components/ai/charts/ScatterPlot'
import { BarChart } from '@/components/ai/charts/BarChart'
import { loadCSV, trainingDataPath, computeStats, groupBy } from '@/lib/ai-data'

interface DataRow {
  n: number
  beta: number
  eta: number
  gamma: number
  [key: string]: number
}

const SAMPLE_SIZES = [5, 7, 10, 15, 20]

export function DataTab() {
  const [data, setData] = useState<Map<number, DataRow[]>>(new Map())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      try {
        const map = new Map<number, DataRow[]>()
        for (const n of SAMPLE_SIZES) {
          try {
            const rows = await loadCSV<DataRow>(trainingDataPath(n))
            map.set(n, rows)
          } catch {
            // 文件可能不存在（训练数据未生成）
          }
        }
        setData(map)
      } catch (e) {
        setError('加载训练数据失败')
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

  // 合并所有数据
  const allData = Array.from(data.values()).flat()

  // D1: 最优 δ 分布直方图（按 n 分组）
  const deltaByN = SAMPLE_SIZES.filter(n => data.has(n)).map(n => ({
    n,
    values: data.get(n)!.map(d => d.optimal_delta).filter(v => !isNaN(v)),
  }))

  // D3: δ vs 样本均值散点图
  const scatterMeanData = allData
    .filter(d => !isNaN(d.optimal_delta))
    .map(d => {
      const sampleKeys = Object.keys(d).filter(k => k.startsWith('t') && k !== 'optimal_delta' && k !== 'best_mse')
      const sampleValues = sampleKeys.map(k => d[k]).filter(v => !isNaN(v))
      const mean = sampleValues.reduce((a, b) => a + b, 0) / sampleValues.length
      return { x: mean, y: d.optimal_delta }
    })

  // D4: δ vs 样本标准差散点图
  const scatterStdData = allData
    .filter(d => !isNaN(d.optimal_delta))
    .map(d => {
      const sampleKeys = Object.keys(d).filter(k => k.startsWith('t') && k !== 'optimal_delta' && k !== 'best_mse')
      const sampleValues = sampleKeys.map(k => d[k]).filter(v => !isNaN(v))
      const mean = sampleValues.reduce((a, b) => a + b, 0) / sampleValues.length
      const variance = sampleValues.reduce((sum, v) => sum + (v - mean) ** 2, 0) / sampleValues.length
      return { x: Math.sqrt(variance), y: d.optimal_delta }
    })

  // D5: δ vs 变异系数散点图
  const scatterCVData = allData
    .filter(d => !isNaN(d.optimal_delta))
    .map(d => {
      const sampleKeys = Object.keys(d).filter(k => k.startsWith('t') && k !== 'optimal_delta' && k !== 'best_mse')
      const sampleValues = sampleKeys.map(k => d[k]).filter(v => !isNaN(v))
      const mean = sampleValues.reduce((a, b) => a + b, 0) / sampleValues.length
      const variance = sampleValues.reduce((sum, v) => sum + (v - mean) ** 2, 0) / sampleValues.length
      const cv = mean > 0 ? Math.sqrt(variance) / mean : 0
      return { x: cv, y: d.optimal_delta }
    })

  // D2: 按 β、n 分组的统计
  const groupStats = Array.from(
    groupBy(allData.filter(d => !isNaN(d.optimal_delta)), d => `β=${d.beta},n=${d.n}`)
  ).map(([key, rows]) => {
    const deltas = rows.map(d => d.optimal_delta)
    const stats = computeStats(deltas)
    return { keyLabel: key, ...stats }
  }).sort((a, b) => a.keyLabel.localeCompare(b.keyLabel))

  // D6: 按参数组合的成功率
  const successRates = Array.from(
    groupBy(allData, d => `β=${d.beta},η=${d.eta}`)
  ).map(([key, rows]) => ({
    label: key,
    value: rows.length,
    color: '#8b5cf6',
  })).sort((a, b) => a.label.localeCompare(b.label))

  return (
    <div className="space-y-6">
      {/* 参数空间说明 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
          <div className="text-xs text-purple-500">参数组合</div>
          <div className="text-lg font-black text-purple-700">45 组</div>
          <div className="text-xs text-purple-400">3×3×1×5</div>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div className="text-xs text-blue-500">总样本数</div>
          <div className="text-lg font-black text-blue-700">{allData.length.toLocaleString()}</div>
          <div className="text-xs text-blue-400">有效记录</div>
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

      {/* D1: δ 分布直方图 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {deltaByN.map(({ n, values }) => (
          <ChartCard key={n} title={`D1: n=${n} 最优 δ 分布 (N=${values.length})`}>
            <Histogram values={values} xLabel="最优 δ" yLabel="频次" color="#8b5cf6" />
          </ChartCard>
        ))}
      </div>

      {/* D3-D5: 散点图 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ChartCard title="D3: δ vs 样本均值">
          <ScatterPlot data={scatterMeanData} xLabel="样本均值" yLabel="最优 δ" color="#3b82f6" />
        </ChartCard>
        <ChartCard title="D4: δ vs 样本标准差">
          <ScatterPlot data={scatterStdData} xLabel="样本标准差" yLabel="最优 δ" color="#10b981" />
        </ChartCard>
        <ChartCard title="D5: δ vs 变异系数">
          <ScatterPlot data={scatterCVData} xLabel="变异系数 (CV)" yLabel="最优 δ" color="#f59e0b" />
        </ChartCard>
      </div>

      {/* D6: 样本数量柱状图 */}
      <ChartCard title="D6: 各参数组合的有效样本数">
        <BarChart data={successRates} xLabel="参数组合" yLabel="样本数" color="#8b5cf6" />
      </ChartCard>

      {/* 参数空间表格 */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-3">参数空间定义</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">参数</th>
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">值</th>
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">说明</th>
              </tr>
            </thead>
            <tbody>
              <tr><td className="border border-slate-200 px-3 py-2 font-mono">β</td><td className="border border-slate-200 px-3 py-2">1, 2, 5</td><td className="border border-slate-200 px-3 py-2 text-slate-500">形状参数</td></tr>
              <tr><td className="border border-slate-200 px-3 py-2 font-mono">η</td><td className="border border-slate-200 px-3 py-2">100, 1000, 5000</td><td className="border border-slate-200 px-3 py-2 text-slate-500">尺度参数</td></tr>
              <tr><td className="border border-slate-200 px-3 py-2 font-mono">γ</td><td className="border border-slate-200 px-3 py-2">1000</td><td className="border border-slate-200 px-3 py-2 text-slate-500">位置参数（固定）</td></tr>
              <tr><td className="border border-slate-200 px-3 py-2 font-mono">n</td><td className="border border-slate-200 px-3 py-2">5, 7, 10, 15, 20</td><td className="border border-slate-200 px-3 py-2 text-slate-500">样本量</td></tr>
              <tr><td className="border border-slate-200 px-3 py-2 font-mono">δ</td><td className="border border-slate-200 px-3 py-2">[0.001, 1.00] 粗搜 0.1 + 细搜 0.01</td><td className="border border-slate-200 px-3 py-2 text-slate-500">搜索范围</td></tr>
              <tr><td className="border border-slate-200 px-3 py-2 font-mono">MC</td><td className="border border-slate-200 px-3 py-2">500</td><td className="border border-slate-200 px-3 py-2 text-slate-500">每组参数模拟次数</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
