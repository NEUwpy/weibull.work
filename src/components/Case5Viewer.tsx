"use client"

import React, { useState, useEffect } from 'react'
import { Table2, Table } from 'lucide-react'
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

interface Case5ViewerProps {
  caseId: string
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

// 梯度曲线点
interface GradientPoint {
  gamma: number
  gradient: number
  sigma_min?: number
  best_beta?: number
  best_eta?: number
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
const TRUE_GAMMA = 1000

export default function Case5Viewer({ caseId }: Case5ViewerProps) {
  const [results, setResults] = useState<EstimateResult[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [curvesData, setCurvesData] = useState<SampleCurve[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadData = async () => {
      try {
        // 并行加载所有数据
        const [resultsRes, summaryRes, curvesRes] = await Promise.all([
          fetch('/cases/mdm_case5_results.csv'),
          fetch('/cases/mdm_case5_summary.json'),
          fetch('/cases/mdm_case5_curves.json')
        ])

        if (!resultsRes.ok) throw new Error('结果数据加载失败')
        if (!summaryRes.ok) throw new Error('统计摘要加载失败')
        if (!curvesRes.ok) throw new Error('曲线数据加载失败')

        const resultsText = await resultsRes.text()
        const resultsData = parseCSV(resultsText)
        setResults(resultsData)

        const summaryData = await summaryRes.json()
        setSummary(summaryData)

        const curvesResJson = await curvesRes.json()

        // 对每个样本的梯度曲线进行裁剪，过滤超出[0, 0.6]范围的点
        const clippedSamples = curvesResJson.samples.map(sample => ({
          ...sample,
          grad_gamma_curve: sample.grad_gamma_curve
            .map(p => ({ ...p, gradient: Math.max(0, Math.min(0.6, p.gradient)) }))
            .filter(p => p.gradient >= 0 && p.gradient <= 0.6)  // 只保留范围内的点
        }))

        setCurvesData(clippedSamples)
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

    return lines.slice(1).map((line, lineIdx) => {
      const values = line.split(',')
      const obj: any = {}
      headers.forEach((header, idx) => {
        const val = values[idx]?.trim()
        // sample_id 保持为字符串，其他转换为数字
        if (header === 'sample_id') {
          obj[header] = val
        } else {
          obj[header] = val === '' ? null : Number(val)
        }
      })
      // 验证必要字段
      return obj as EstimateResult
    })
  }

  // 曲线颜色
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
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-200 border-t-purple-600 mb-4"></div>
          <p className="text-slate-600 font-bold">加载案例5数据中...</p>
        </div>
      </div>
    )
  }

  if (!summary || curvesData.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <p className="text-center text-slate-600">数据加载失败</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 案例标题与说明 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <h2 className="text-xl font-bold text-slate-800 mb-3">
          案例5: 30组实际样本的MDM估计分析
        </h2>
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
        <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
          <Table2 className="text-purple-600" size={20} />
          统计汇总表
        </h3>
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

      {/* 详细估计结果表 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
          <Table className="text-purple-600" size={20} />
          表1: 各样本估计结果
        </h3>
        <div className="overflow-x-auto overflow-y-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b-2 border-slate-400 bg-slate-50 sticky top-0">
                <th className="text-center py-2 px-2 font-bold text-slate-800 border border-slate-300">样本编号</th>
                <th className="text-center py-2 px-2 font-bold text-slate-800 border border-slate-300">β估计值</th>
                <th className="text-center py-2 px-2 font-bold text-slate-800 border border-slate-300">β偏差</th>
                <th className="text-center py-2 px-2 font-bold text-slate-800 border border-slate-300">η估计值</th>
                <th className="text-center py-2 px-2 font-bold text-slate-800 border border-slate-300">η偏差</th>
                <th className="text-center py-2 px-2 font-bold text-slate-800 border border-slate-300">γ估计值</th>
                <th className="text-center py-2 px-2 font-bold text-slate-800 border border-slate-300">γ偏差</th>
              </tr>
            </thead>
            <tbody>
              {results.filter(r => r && r.sample_id && r.bias_gamma !== undefined).map((r, idx) => (
                <tr key={r.sample_id} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                  <td className="text-center py-1 px-2 font-mono text-slate-700 border border-slate-200">{r.sample_id}</td>
                  <td className="text-center py-1 px-2 font-mono text-slate-700 border border-slate-200">{r.est_beta?.toFixed(3) ?? '—'}</td>
                  <td className="text-center py-1 px-2 font-mono text-slate-700 border border-slate-200">{r.bias_beta?.toFixed(3) ?? '—'}</td>
                  <td className="text-center py-1 px-2 font-mono text-slate-700 border border-slate-200">{r.est_eta?.toFixed(1) ?? '—'}</td>
                  <td className="text-center py-1 px-2 font-mono text-slate-700 border border-slate-200">{r.bias_eta?.toFixed(1) ?? '—'}</td>
                  <td className="text-center py-1 px-2 font-mono text-slate-700 border border-slate-200">{r.est_gamma?.toFixed(1) ?? '—'}</td>
                  <td className="text-center py-1 px-2 font-mono text-slate-700 border border-slate-200">{r.bias_gamma?.toFixed(1) ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 图1: 梯度曲线簇 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-lg font-bold text-slate-800">图1. 梯度曲线簇 - 位置参数梯度判据</h3>
            <p className="text-xs text-slate-500">30条样本的 ∇(γ) 与偏移值δ={OFFSET_VALUE} 比较</p>
          </div>
          <div className="w-3 h-3 bg-purple-500 rounded"></div>
        </div>
        <Legend
          verticalAlign="top"
          height={30}
          payload={
            curvesData.slice(0, 30).map((sample, idx) => ({
              value: sample.sample_id,
              type: 'line',
              id: `line-${sample.sample_id}`,
              color: curveColors[idx % curveColors.length]
            }))
          }
        />
        <div className="w-full max-w-6xl" style={{ height: '600px' }}>
          <ResponsiveContainer width="100%">
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

      {/* 关键发现 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <h3 className="text-lg font-bold text-slate-800 mb-4">关键发现</h3>
        <div className="space-y-3">
          <div className="bg-red-50 rounded-lg p-3 border border-red-200">
            <p className="text-sm text-red-800">
              <span className="font-bold">β估计系统性偏差:</span> 所有30个样本的β估计值均约为1.0，与真实值2.0相差约-1.0，表明MDM算法在小样本下对β存在系统性低估。
            </p>
          </div>
          <div className="bg-amber-50 rounded-lg p-3 border border-amber-200">
            <p className="text-sm text-amber-800">
              <span className="font-bold">η与γ估计波动较大:</span> η的偏差范围为[-572.9, +552.5]，γ的偏差范围为[-448.9, +492.5]，标准差均超过200，说明小样本下尺度参数和位置参数估计不稳定。
            </p>
          </div>
          <div className="bg-green-50 rounded-lg p-3 border border-green-200">
            <p className="text-sm text-green-800">
              <span className="font-bold">梯度收敛性:</span> 所有样本的梯度曲线在δ={OFFSET_VALUE}附近均存在交点，表明MDM算法具有良好的收敛特性。
            </p>
          </div>
        </div>
      </div>

      {/* 方法说明 */}
      <div className="bg-slate-50 p-6 rounded-2xl border border-slate-200">
        <h3 className="text-lg font-bold text-slate-800 mb-3">方法说明</h3>
        <p className="text-sm text-slate-700 mb-2">
          <span className="font-bold">MDM（最小差异法）</span>通过最小化对数项与求和项的差异来估计威布尔分布参数：
        </p>
        <div className="bg-white rounded-lg p-3 border border-slate-300 font-mono text-sm text-slate-800">
          目标函数 = |(β-1) × Σln(x-γ) - n × (mean((x-γ)/η)^β - 1)|
        </div>
        <p className="text-sm text-slate-700 mt-2">
          其中 x 为观测数据，γ 的搜索范围设为 [0.5×t_min, 0.999999×t_min]，偏移量 δ = {OFFSET_VALUE} 控制搜索下限。
        </p>
      </div>
    </div>
  )
}
