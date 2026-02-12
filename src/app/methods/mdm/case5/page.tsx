"use client"

import React, { useState, useEffect } from 'react'
import { Table, ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend
} from 'recharts'

// 样本原始数据
interface SampleData {
  id: string
  values: number[]
}

// 估计结果
interface EstimateResult {
  sample_id: string
  est_beta: number
  est_eta: number
  est_gamma: number
  bias_beta: number
  bias_eta: number
  bias_gamma: number
}

// 梯度曲线点
interface GradientPoint {
  gamma: number
  gradient: number
}

// 样本曲线数据
interface SampleCurve {
  sample_id: string
  grad_gamma_curve: GradientPoint[]
}

// 统计摘要
interface Summary {
  n_samples: number
  true_params: {
    beta: number
    eta: number
    gamma: number
  }
  estimates: {
    beta_mean: number
    beta_std: number
    beta_min: number
    beta_max: number
    eta_mean: number
    eta_std: number
    eta_min: number
    eta_max: number
    gamma_mean: number
    gamma_std: number
    gamma_min: number
    gamma_max: number
  }
  bias: {
    beta_mean: number
    beta_std: number
    beta_min: number
    beta_max: number
    eta_mean: number
    eta_std: number
    eta_min: number
    eta_max: number
    gamma_mean: number
    gamma_std: number
    gamma_min: number
    gamma_max: number
  }
}

const OFFSET_VALUE = 0.1

export default function MDMCase5Page() {
  const [results, setResults] = useState<EstimateResult[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [curvesData, setCurvesData] = useState<SampleCurve[]>([])
  const [samples, setSamples] = useState<SampleData[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadData = async () => {
      try {
        const [resultsRes, summaryRes, curvesRes, samplesRes] = await Promise.all([
          fetch('/cases/mdm_case5_results.csv'),
          fetch('/cases/mdm_case5_summary.json'),
          fetch('/cases/mdm_case5_curves.json'),
          fetch('/cases/mdm_case5.csv')
        ])

        if (!resultsRes.ok) throw new Error('结果数据加载失败')
        if (!summaryRes.ok) throw new Error('统计摘要加载失败')
        if (!curvesRes.ok) throw new Error('曲线数据加载失败')
        if (!samplesRes.ok) throw new Error('样本数据加载失败')

        const resultsText = await resultsRes.text()
        const resultsData = parseCSV(resultsText)
        setResults(resultsData)

        const summaryData = await summaryRes.json()
        setSummary(summaryData)

        const curvesResJson = await curvesRes.json()
        const clippedSamples = curvesResJson.samples.map((sample: SampleCurve) => ({
          ...sample,
          grad_gamma_curve: sample.grad_gamma_curve
            .map(p => ({ ...p, gradient: Math.max(0, Math.min(0.6, p.gradient)) }))
            .filter(p => p.gradient >= 0 && p.gradient <= 0.6)
        }))
        setCurvesData(clippedSamples)

        const samplesText = await samplesRes.text()
        const samplesData = parseSamplesCSV(samplesText)
        setSamples(samplesData)
      } catch (err) {
        console.error('Failed to load case 5 data:', err)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  const parseCSV = (csvText: string): EstimateResult[] => {
    const lines = csvText.trim().split('\n')
    const headers = lines[0].split(',')

    return lines.slice(1).map(line => {
      const values = line.split(',')
      const obj: any = {}
      headers.forEach((header, idx) => {
        const val = values[idx]?.trim()
        if (header === 'sample_id') {
          obj[header] = val
        } else {
          obj[header] = val === '' ? null : Number(val)
        }
      })
      return obj as EstimateResult
    })
  }

  const parseSamplesCSV = (csvText: string): SampleData[] => {
    const lines = csvText.trim().split('\n')
    return lines.slice(1).map(line => {
      const parts = line.split(',')
      return {
        id: parts[0],
        values: parts.slice(1).map(v => parseFloat(v))
      }
    })
  }

  const curveColors = [
    '#ef4444', '#10b981', '#3b82f6', '#f59e0b', '#8b5cf6',
    '#06b6d4', '#ec4899', '#84cc16', '#6366f1', '#14b8a6',
    '#f97316', '#065f46', '#2563eb', '#7c3aed', '#00b894',
    '#e63946', '#fb8500', '#4ea8de', '#6c5ce7', '#a29bfe',
    '#ff006e', '#008000', '#008080', '#800080', '#800000',
    '#808000', '#808000', '#ff8040', '#ff80ff', '#80ffff'
  ]

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-white rounded-2xl border border-slate-200 p-12">
            <div className="flex flex-col items-center justify-center">
              <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-200 border-t-purple-600 mb-4"></div>
              <p className="text-slate-600 font-bold">加载案例5数据中...</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!summary || curvesData.length === 0) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-white rounded-2xl border border-slate-200 p-12">
            <p className="text-center text-slate-600">数据加载失败</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-md border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-8 py-4">
          <div className="flex items-center gap-4">
            <Link
              href="/methods/mdm"
              className="flex items-center gap-2 text-slate-600 hover:text-purple-600 transition-colors"
            >
              <ArrowLeft size={20} />
              <span className="font-bold">返回MDM方法</span>
            </Link>
            <div className="h-6 w-px bg-slate-300"></div>
            <h1 className="text-2xl font-bold text-slate-800">案例5: 30组实际样本的MDM估计分析</h1>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-8 py-8 space-y-6">
        {/* 案例说明 */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="bg-blue-50 rounded-xl p-4 border border-blue-200">
            <p className="text-sm text-blue-800 mb-2">
              <span className="font-bold">数据来源:</span> 30组真实失效数据，每组7个观测值，来自威布尔分布
            </p>
            <p className="text-sm text-blue-800">
              <span className="font-bold">真实参数:</span> β={summary.true_params.beta}, η={summary.true_params.eta}, γ={summary.true_params.gamma}
              <span className="ml-4 font-bold">样本量:</span> n=7
              <span className="ml-4 font-bold">偏移量:</span> δ={OFFSET_VALUE}
            </p>
          </div>
        </div>

        {/* 统计汇总表 */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <h3 className="text-lg font-bold text-slate-800 mb-4">统计汇总</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-base border-collapse">
              <thead>
                <tr className="border-b-2 border-slate-400">
                  <th className="text-left py-2 px-3 font-bold text-slate-800">参数</th>
                  <th className="text-center py-2 px-3 font-bold text-slate-800">真实值</th>
                  <th className="text-center py-2 px-3 font-bold text-slate-800">估计均值</th>
                  <th className="text-center py-2 px-3 font-bold text-slate-800">估计范围</th>
                  <th className="text-center py-2 px-3 font-bold text-slate-800">偏差均值</th>
                  <th className="text-center py-2 px-3 font-bold text-slate-800">偏差范围</th>
                  <th className="text-center py-2 px-3 font-bold text-slate-800">偏差标准差</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-slate-200">
                  <td className="py-2 px-3 font-bold text-slate-800">β</td>
                  <td className="text-center py-2 px-3 font-mono text-slate-700">{summary.true_params.beta.toFixed(1)}</td>
                  <td className="text-center py-2 px-3 font-mono text-slate-700">{summary.estimates.beta_mean.toFixed(3)}</td>
                  <td className="text-center py-2 px-3 font-mono text-slate-700 text-sm">
                    [{summary.estimates.beta_min.toFixed(2)}, {summary.estimates.beta_max.toFixed(2)}]
                  </td>
                  <td className="text-center py-2 px-3 font-mono text-slate-700">{summary.bias.beta_mean.toFixed(3)}</td>
                  <td className="text-center py-2 px-3 font-mono text-slate-700 text-sm">
                    [{summary.bias.beta_min.toFixed(2)}, {summary.bias.beta_max.toFixed(2)}]
                  </td>
                  <td className="text-center py-2 px-3 font-mono text-slate-700">{summary.bias.beta_std.toFixed(3)}</td>
                </tr>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <td className="py-2 px-3 font-bold text-slate-800">η</td>
                  <td className="text-center py-2 px-3 font-mono text-slate-700">{summary.true_params.eta.toFixed(0)}</td>
                  <td className="text-center py-2 px-3 font-mono text-slate-700">{summary.estimates.eta_mean.toFixed(1)}</td>
                  <td className="text-center py-2 px-3 font-mono text-slate-700 text-sm">
                    [{summary.estimates.eta_min.toFixed(1)}, {summary.estimates.eta_max.toFixed(1)}]
                  </td>
                  <td className="text-center py-2 px-3 font-mono text-slate-700">{summary.bias.eta_mean.toFixed(1)}</td>
                  <td className="text-center py-2 px-3 font-mono text-slate-700 text-sm">
                    [{summary.bias.eta_min.toFixed(1)}, {summary.bias.eta_max.toFixed(1)}]
                  </td>
                  <td className="text-center py-2 px-3 font-mono text-slate-700">{summary.bias.eta_std.toFixed(1)}</td>
                </tr>
                <tr className="border-b border-slate-200">
                  <td className="py-2 px-3 font-bold text-slate-800">γ</td>
                  <td className="text-center py-2 px-3 font-mono text-slate-700">{summary.true_params.gamma.toFixed(0)}</td>
                  <td className="text-center py-2 px-3 font-mono text-slate-700">{summary.estimates.gamma_mean.toFixed(1)}</td>
                  <td className="text-center py-2 px-3 font-mono text-slate-700 text-sm">
                    [{summary.estimates.gamma_min.toFixed(1)}, {summary.estimates.gamma_max.toFixed(1)}]
                  </td>
                  <td className="text-center py-2 px-3 font-mono text-slate-700">{summary.bias.gamma_mean.toFixed(1)}</td>
                  <td className="text-center py-2 px-3 font-mono text-slate-700 text-sm">
                    [{summary.bias.gamma_min.toFixed(1)}, {summary.bias.gamma_max.toFixed(1)}]
                  </td>
                  <td className="text-center py-2 px-3 font-mono text-slate-700">{summary.bias.gamma_std.toFixed(1)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* 详细数据表 */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
            <Table className="text-purple-600" size={20} />
            表1: 样本原始数据与估计结果
          </h3>
          <div className="overflow-x-auto overflow-y-auto max-h-[600px]">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b-2 border-slate-400 bg-slate-50 sticky top-0">
                  <th className="text-center py-2 px-2 font-bold text-slate-800 border border-slate-300">样本编号</th>
                  <th className="text-center py-2 px-2 font-bold text-slate-800 border border-slate-300">t₁</th>
                  <th className="text-center py-2 px-2 font-bold text-slate-800 border border-slate-300">t₂</th>
                  <th className="text-center py-2 px-2 font-bold text-slate-800 border border-slate-300">t₃</th>
                  <th className="text-center py-2 px-2 font-bold text-slate-800 border border-slate-300">t₄</th>
                  <th className="text-center py-2 px-2 font-bold text-slate-800 border border-slate-300">t₅</th>
                  <th className="text-center py-2 px-2 font-bold text-slate-800 border border-slate-300">t₆</th>
                  <th className="text-center py-2 px-2 font-bold text-slate-800 border border-slate-300">t₇</th>
                  <th className="text-center py-2 px-2 font-bold text-blue-700 border border-slate-300">β̂</th>
                  <th className="text-center py-2 px-2 font-bold text-blue-700 border border-slate-300">η̂</th>
                  <th className="text-center py-2 px-2 font-bold text-blue-700 border border-slate-300">γ̂</th>
                  <th className="text-center py-2 px-2 font-bold text-red-700 border border-slate-300">偏差(β)</th>
                  <th className="text-center py-2 px-2 font-bold text-red-700 border border-slate-300">偏差(η)</th>
                  <th className="text-center py-2 px-2 font-bold text-red-700 border border-slate-300">偏差(γ)</th>
                </tr>
              </thead>
              <tbody>
                {results.filter(r => r && r.sample_id && r.bias_gamma !== undefined).map((r, idx) => {
                  const sample = samples.find(s => s.id === r.sample_id)
                  return (
                    <tr key={r.sample_id} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                      <td className="text-center py-1 px-2 font-mono text-slate-700 border border-slate-200">{r.sample_id}</td>
                      {sample ? sample.values.map((val, i) => (
                        <td key={i} className="text-center py-1 px-2 font-mono text-slate-600 border border-slate-200 text-xs">
                          {val.toFixed(1)}
                        </td>
                      )) : (
                        Array(7).fill(0).map((_, i) => (
                          <td key={i} className="text-center py-1 px-2 border border-slate-200 text-red-500">—</td>
                        ))
                      )}
                      <td className="text-center py-1 px-2 font-mono text-blue-700 border border-slate-200">{r.est_beta?.toFixed(3) ?? '—'}</td>
                      <td className="text-center py-1 px-2 font-mono text-blue-700 border border-slate-200">{r.est_eta?.toFixed(1) ?? '—'}</td>
                      <td className="text-center py-1 px-2 font-mono text-blue-700 border border-slate-200">{r.est_gamma?.toFixed(1) ?? '—'}</td>
                      <td className={`text-center py-1 px-2 font-mono border border-slate-200 ${
                        r.bias_beta > 0 ? 'text-red-600' : 'text-green-600'
                      }`}>{r.bias_beta > 0 ? '+' : ''}{r.bias_beta?.toFixed(3) ?? '—'}</td>
                      <td className={`text-center py-1 px-2 font-mono border border-slate-200 ${
                        r.bias_eta > 0 ? 'text-red-600' : 'text-green-600'
                      }`}>{r.bias_eta > 0 ? '+' : ''}{r.bias_eta?.toFixed(1) ?? '—'}</td>
                      <td className={`text-center py-1 px-2 font-mono border border-slate-200 ${
                        r.bias_gamma > 0 ? 'text-red-600' : 'text-green-600'
                      }`}>{r.bias_gamma > 0 ? '+' : ''}{r.bias_gamma?.toFixed(1) ?? '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* 图1: 梯度曲线簇 */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="mb-4">
            <h3 className="text-lg font-bold text-slate-800">图1. 梯度曲线簇 - 位置参数梯度判据</h3>
            <p className="text-xs text-slate-500 mt-1">30条样本的 ∇(γ) 与偏移值δ={OFFSET_VALUE} 比较</p>
          </div>
          <div className="w-full" style={{ height: '600px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart margin={{ top: 20, right: 25, bottom: 40, left: 60 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="gamma"
                  type="number"
                  domain={[200, 1800]}
                  tickFormatter={(v) => v.toFixed(0)}
                  tick={{ fontSize: 10 }}
                  tickLine={true}
                  stroke="#000"
                  strokeWidth={1}
                  label={{ value: '位置参数 γ', position: 'bottom', fontSize: 12, fill: '#64748b' }}
                  axisLine={{ stroke: '#000', strokeWidth: 1 }}
                />
                <YAxis
                  width={50}
                  domain={[0, 0.6]}
                  tick={{ fontSize: 10 }}
                  tickLine={true}
                  stroke="#000"
                  strokeWidth={1}
                  label={{ value: '梯度 ∇(γ)', angle: -90, position: 'insideLeft', fontSize: 12, fill: '#64748b' }}
                  axisLine={{ stroke: '#000', strokeWidth: 1 }}
                />
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                  labelFormatter={(v) => `γ: ${Number(v).toFixed(0)}`}
                  formatter={(v: number, name: string) => [v.toFixed(4), name]}
                />
                <ReferenceLine y={OFFSET_VALUE} stroke="#10b981" strokeDasharray="3 3" label={{ position: 'right', value: `δ=${OFFSET_VALUE}`, fill: '#10b981', fontSize: 10 }} />
                <ReferenceLine y={0} stroke="#cbd5e1" />
                {curvesData.slice(0, 30).map((sample, idx) => (
                  <Line
                    key={sample.sample_id}
                    data={sample.grad_gamma_curve}
                    type="monotone"
                    dataKey="gradient"
                    stroke={curveColors[idx % curveColors.length]}
                    strokeWidth={1.5}
                    dot={false}
                    name={sample.sample_id}
                    opacity={0.8}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </main>
    </div>
  )
}
