"use client"

import React, { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Legend
} from 'recharts'
import { BookOpen, ChevronDown, Table2, AlertTriangle, Info, TrendingUp, LineChart as LineChartIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Case11ViewerProps {
  caseId: string
  onCaseChange?: (caseId: string) => void
}

// 统计数据结构
interface ParameterStats {
  mean: number
  std: number
  min: number
  max: number
  median: number
  q1: number
  q3: number
  p01: number
  p99: number
}

interface MethodStats {
  count: number
  valid_count: number
  convergence_rate: number
  beta?: ParameterStats
  eta?: ParameterStats
  gamma?: ParameterStats
  bias_beta?: { mean: number; std: number }
  bias_eta?: { mean: number; std: number }
  bias_gamma?: { mean: number; std: number }
  mse_beta?: number
  mse_eta?: number
  mse_gamma?: number
}

interface SimulationResult {
  sim_id: number
  rank_method: 'bernard' | 'exact'
  beta: number | null
  eta: number | null
  gamma: number | null
  r2: number | null
  status: string
  bias_beta?: number
  bias_eta?: number
  bias_gamma?: number
}

interface MedianRankComparison {
  i: number
  bernard: number
  exact: number
  diff: number
}

interface SampleResult {
  n: number
  median_rank_comparison: MedianRankComparison[]
  bernard_stats: MethodStats
  exact_stats: MethodStats
  bernard_results: SimulationResult[]
  exact_results: SimulationResult[]
}

interface SimulationParams {
  sample_sizes: number[]
  n_simulations: number
  true_beta: number
  true_eta: number
  true_gamma: number
  offset: number
  gamma_steps: number
  seed: number
}

interface CaseData {
  simulation_params: SimulationParams
  sample_results: SampleResult[]
}

// 核密度估计 (KDE)
function computeKDE(values: number[], bandwidth?: number) {
  const n = values.length
  if (n === 0) return { points: [], bandwidth: 0 }

  const mean = values.reduce((a, b) => a + b, 0) / n
  const std = Math.sqrt(values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / n)
  const iqr = (() => {
    const sorted = [...values].sort((a, b) => a - b)
    const q1 = sorted[Math.floor(n * 0.25)]
    const q3 = sorted[Math.floor(n * 0.75)]
    return q3 - q1
  })()
  const defaultBandwidth = 0.9 * Math.min(std, iqr / 1.34) / Math.pow(n, 0.2)
  const h = bandwidth ?? defaultBandwidth

  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min
  const numPoints = 200

  const points = Array.from({ length: numPoints }, (_, i) => {
    const x = min - range * 0.1 + (i / (numPoints - 1)) * range * 1.2
    let density = 0
    for (const v of values) {
      const u = (x - v) / h
      density += Math.exp(-0.5 * u * u)
    }
    density /= (n * h * Math.sqrt(2 * Math.PI))
    return { x, y: density }
  })

  return { points, bandwidth: h }
}

const colors = {
  beta: '#1e40af',
  eta: '#047857',
  gamma: '#b45309'
}

// 样本量颜色
const sampleColors: Record<number, { bernard: string; exact: string }> = {
  7: { bernard: '#3b82f6', exact: '#10b981' },    // blue / emerald
  10: { bernard: '#8b5cf6', exact: '#f59e0b' },   // violet / amber
  15: { bernard: '#ec4899', exact: '#06b6d4' },   // pink / cyan
}

export default function Case11Viewer({ caseId, onCaseChange }: Case11ViewerProps) {
  const [data, setData] = useState<CaseData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedN, setSelectedN] = useState<number>(7)

  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true)
        const res = await fetch('/case-studies/mdm/case11/data.json')
        if (!res.ok) throw new Error('数据加载失败')
        const json = await res.json()
        setData(json)
        if (json.sample_results?.length > 0) {
          setSelectedN(json.sample_results[0].n)
        }
      } catch (err: any) {
        setError(err.message)
      } finally {
        setIsLoading(false)
      }
    }
    loadData()
  }, [])

  // 获取当前选中样本量的数据
  const currentSampleData = useMemo(() => {
    if (!data) return null
    return data.sample_results.find(sr => sr.n === selectedN)
  }, [data, selectedN])

  // 计算所有样本量的 KDE 数据
  const allKDEData = useMemo(() => {
    if (!data) return null

    const result: Record<number, { beta: { bernard: any[]; exact: any[] }; eta: { bernard: any[]; exact: any[] }; gamma: { bernard: any[]; exact: any[] } }> = {}

    for (const sr of data.sample_results) {
      const validBernard = sr.bernard_results.filter(r => r.beta !== null && r.status === 'success')
      const validExact = sr.exact_results.filter(r => r.beta !== null && r.status === 'success')

      result[sr.n] = {
        beta: {
          bernard: computeKDE(validBernard.map(r => r.beta!)).points,
          exact: computeKDE(validExact.map(r => r.beta!)).points,
        },
        eta: {
          bernard: computeKDE(validBernard.map(r => r.eta!)).points,
          exact: computeKDE(validExact.map(r => r.eta!)).points,
        },
        gamma: {
          bernard: computeKDE(validBernard.map(r => r.gamma!)).points,
          exact: computeKDE(validExact.map(r => r.gamma!)).points,
        }
      }
    }

    return result
  }, [data])

  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-4 border-orange-200 border-t-orange-600 mb-4"></div>
          <p className="text-slate-600 font-bold">加载案例11数据中...</p>
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700">
        数据加载失败: {error}
      </div>
    )
  }

  const params = data.simulation_params

  return (
    <div className="space-y-6">
      {/* 案例选择下拉框 */}
      {onCaseChange && (
        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-4">
            <BookOpen className="text-purple-600" size={20} />
            <label className="text-sm font-bold text-slate-600 whitespace-nowrap">切换案例：</label>
            <div className="relative flex-1 max-w-md">
              <select
                value={caseId}
                onChange={(e) => onCaseChange(e.target.value)}
                className="w-full appearance-none bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-purple-500 cursor-pointer hover:bg-slate-100 transition-colors"
              >
                <option value="case-1">案例1: 多维度参数影响研究</option>
                <option value="case-2">案例2: 样本量与偏移量影响</option>
                <option value="case-3">案例3: 无交点梯度曲线研究 ★</option>
                <option value="case-4">案例4: 大样本性能验证</option>
                <option value="case-5">案例5: 30组实际样本分析 ★</option>
                <option value="case-6">案例6: 搜索步长对结果的影响 (c2数据)</option>
                <option value="case-7">案例7: 搜索步长对结果的影响 (实际样本) ★</option>
                <option value="case-8">案例8: β搜索方式对比 (β步长0.05) ★</option>
                <option value="case-9">案例9: β步长对估计结果的影响 ★</option>
                <option value="case-10">案例10: 中位秩方法对比研究 ★</option>
                <option value="case-11">案例11: 中位秩方法对比 (多样本量) ★</option>
                <option value="case-12">案例12: MDM vs WMLE 方法对比 ★</option>
                <option value="case-13">案例13: 中位秩方法对比 (多尺度参数) ★</option>
                <option value="case-14">案例14: MDM vs WMLE 方法对比 (多尺度参数) ★</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={18} />
            </div>
          </div>
        </div>
      )}

      {/* 标题 */}
      <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-2xl p-6 border border-indigo-200">
        <h2 className="text-xl font-bold text-slate-800 mb-2">案例11: 中位秩方法对比研究 (多样本量扩展)</h2>
        <p className="text-sm text-slate-600 mb-2">
          蒙特卡洛模拟: n ∈ {'{' + params.sample_sizes.join(', ') + '}'}, 各{params.n_simulations}次 | 真实参数: β={params.true_beta}, η={params.true_eta}, γ={params.true_gamma}
        </p>
        <div className="flex items-center gap-2 text-xs text-indigo-600 bg-indigo-100 px-3 py-1.5 rounded-lg w-fit">
          <Info size={14} />
          <span>对比不同样本量下 Bernard 近似 vs 精确中位秩 的估计差异</span>
        </div>
      </div>

      {/* 样本量选择器 */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-4">
          <label className="text-sm font-bold text-slate-600 whitespace-nowrap">选择样本量：</label>
          <div className="flex gap-2">
            {params.sample_sizes.map(n => (
              <button
                key={n}
                onClick={() => setSelectedN(n)}
                className={cn(
                  "px-4 py-2 rounded-xl text-sm font-bold transition-all",
                  selectedN === n
                    ? "bg-indigo-600 text-white shadow-md"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                )}
              >
                n = {n}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 过程量对比: 中位秩值 */}
      {currentSampleData && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <Table2 className="text-indigo-600" size={20} />
            <h3 className="text-lg font-bold text-slate-800">过程量对比: 中位秩值 F(t<sub>i</sub>) (n={selectedN})</h3>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 公式说明 */}
            <div className="space-y-3">
              <div className="bg-blue-50 p-4 rounded-xl border border-blue-200">
                <p className="text-sm font-bold text-blue-700 mb-2">Bernard 近似公式</p>
                <p className="font-mono text-sm text-slate-700 bg-white px-3 py-2 rounded-lg">
                  F(t<sub>i</sub>) = (i - 0.3) / (n + 0.4)
                </p>
              </div>
              <div className="bg-emerald-50 p-4 rounded-xl border border-emerald-200">
                <p className="text-sm font-bold text-emerald-700 mb-2">精确中位秩公式 (基于F分布)</p>
                <p className="font-mono text-sm text-slate-700 bg-white px-3 py-2 rounded-lg">
                  F(t<sub>i</sub>) = i / [i + (n+1-i) · F<sub>2(n+1-i),2i</sub>(0.5)]
                </p>
              </div>
            </div>
            {/* 数值对比表 */}
            <div>
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b-2 border-slate-300">
                    <th className="py-2 px-3 text-center font-bold text-slate-700">秩 i</th>
                    <th className="py-2 px-3 text-right font-bold text-blue-700">Bernard</th>
                    <th className="py-2 px-3 text-right font-bold text-emerald-700">Exact</th>
                    <th className="py-2 px-3 text-right font-bold text-slate-700">差异</th>
                  </tr>
                </thead>
                <tbody>
                  {currentSampleData.median_rank_comparison.map((row) => (
                    <tr key={row.i} className="border-b border-slate-100 hover:bg-slate-50">
                      <td className="py-2 px-3 text-center font-mono font-bold">{row.i}</td>
                      <td className="py-2 px-3 text-right font-mono text-blue-700">{row.bernard.toFixed(6)}</td>
                      <td className="py-2 px-3 text-right font-mono text-emerald-700">{row.exact.toFixed(6)}</td>
                      <td className={cn(
                        "py-2 px-3 text-right font-mono font-bold",
                        row.diff > 0 ? "text-red-600" : row.diff < 0 ? "text-green-600" : "text-slate-500"
                      )}>
                        {row.diff > 0 ? '+' : ''}{row.diff.toFixed(6)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-slate-500 mt-2">
                n = {selectedN} | 差异 = Exact - Bernard
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 统计汇总对比表 (所有样本量) */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <Table2 className="text-indigo-600" size={20} />
          <h3 className="text-lg font-bold text-slate-800">统计汇总对比 (所有样本量)</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b-2 border-slate-300">
                <th className="py-2 px-3 text-left font-bold text-slate-700">n</th>
                <th className="py-2 px-3 text-left font-bold text-slate-700">方法</th>
                <th className="py-2 px-2 text-right font-bold text-slate-700">β偏差</th>
                <th className="py-2 px-2 text-right font-bold text-slate-700">β标准差</th>
                <th className="py-2 px-2 text-right font-bold text-slate-700">β MSE</th>
                <th className="py-2 px-2 text-right font-bold text-slate-700">γ偏差</th>
                <th className="py-2 px-2 text-right font-bold text-slate-700">γ标准差</th>
                <th className="py-2 px-2 text-right font-bold text-slate-700">γ MSE</th>
              </tr>
            </thead>
            <tbody>
              {data.sample_results.map((sr) => (
                <React.Fragment key={sr.n}>
                  {/* Bernard 行 */}
                  <tr className="border-b border-slate-200 bg-blue-50">
                    <td rowSpan={2} className="py-2 px-3 font-bold text-slate-700 text-center align-middle border-r border-slate-200">
                      {sr.n}
                    </td>
                    <td className="py-2 px-3 font-bold text-blue-700">Bernard</td>
                    <td className="py-2 px-2 text-right font-mono text-red-600">{sr.bernard_stats.bias_beta?.mean.toFixed(6)}</td>
                    <td className="py-2 px-2 text-right font-mono">{sr.bernard_stats.beta?.std.toFixed(4)}</td>
                    <td className="py-2 px-2 text-right font-mono">{sr.bernard_stats.mse_beta?.toFixed(6)}</td>
                    <td className="py-2 px-2 text-right font-mono text-red-600">{sr.bernard_stats.bias_gamma?.mean.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono">{sr.bernard_stats.gamma?.std.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono">{sr.bernard_stats.mse_gamma?.toFixed(2)}</td>
                  </tr>
                  {/* Exact 行 */}
                  <tr className="border-b border-slate-200 bg-emerald-50">
                    <td className="py-2 px-3 font-bold text-emerald-700">Exact</td>
                    <td className="py-2 px-2 text-right font-mono text-red-600">{sr.exact_stats.bias_beta?.mean.toFixed(6)}</td>
                    <td className="py-2 px-2 text-right font-mono">{sr.exact_stats.beta?.std.toFixed(4)}</td>
                    <td className="py-2 px-2 text-right font-mono">{sr.exact_stats.mse_beta?.toFixed(6)}</td>
                    <td className="py-2 px-2 text-right font-mono text-red-600">{sr.exact_stats.bias_gamma?.mean.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono">{sr.exact_stats.gamma?.std.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono">{sr.exact_stats.mse_gamma?.toFixed(2)}</td>
                  </tr>
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-slate-500 mt-2">
          偏差 = 估计均值 - 真实值 | MSE = 均方误差
        </p>
      </div>

      {/* 概率密度分布对比 (所有样本量) */}
      {allKDEData && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <LineChartIcon className="text-indigo-600" size={20} />
            <h3 className="text-lg font-bold text-slate-800">参数估计值概率密度分布 (所有样本量对比)</h3>
          </div>

          {/* 图例说明 */}
          <div className="flex flex-wrap gap-4 mb-4 text-xs">
            {params.sample_sizes.map(n => (
              <React.Fragment key={n}>
                <span className="flex items-center gap-1">
                  <span className="w-4 h-0.5 inline-block" style={{ backgroundColor: sampleColors[n].bernard }}></span>
                  <span className="text-slate-600">n={n} Bernard</span>
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-4 h-0.5 inline-block" style={{ backgroundColor: sampleColors[n].exact }}></span>
                  <span className="text-slate-600">n={n} Exact</span>
                </span>
              </React.Fragment>
            ))}
            <span className="flex items-center gap-1 ml-4">
              <span className="w-4 h-0.5 bg-red-500 inline-block" style={{ borderStyle: 'dashed' }}></span>
              <span className="text-slate-600">真实值</span>
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* β 分布曲线 */}
            <div>
              <p className="text-center text-sm font-semibold mb-2" style={{ color: colors.beta }}>β 参数估计分布</p>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart margin={{ top: 10, right: 15, bottom: 30, left: 45 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis dataKey="x" tick={{ fontSize: 10 }} type="number" domain={['auto', 'auto']} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ borderRadius: '4px', border: '1px solid #e5e7eb', fontSize: '11px' }}
                      formatter={(v: number) => v.toFixed(4)}
                      labelFormatter={(l) => `β: ${Number(l).toFixed(3)}`}
                    />
                    <ReferenceLine x={params.true_beta} stroke="#ef4444" strokeDasharray="5 5" strokeWidth={2} />
                    {params.sample_sizes.map(n => (
                      <React.Fragment key={n}>
                        <Line type="monotone" dataKey="y" data={allKDEData[n].beta.bernard} stroke={sampleColors[n].bernard} strokeWidth={2} dot={false} name={`n=${n} Bernard`} />
                        <Line type="monotone" dataKey="y" data={allKDEData[n].beta.exact} stroke={sampleColors[n].exact} strokeWidth={2} dot={false} strokeDasharray="4 2" name={`n=${n} Exact`} />
                      </React.Fragment>
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            {/* η 分布曲线 */}
            <div>
              <p className="text-center text-sm font-semibold mb-2" style={{ color: colors.eta }}>η 参数估计分布</p>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart margin={{ top: 10, right: 15, bottom: 30, left: 45 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis dataKey="x" tick={{ fontSize: 10 }} type="number" domain={['auto', 'auto']} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ borderRadius: '4px', border: '1px solid #e5e7eb', fontSize: '11px' }}
                      formatter={(v: number) => v.toFixed(5)}
                      labelFormatter={(l) => `η: ${Number(l).toFixed(1)}`}
                    />
                    <ReferenceLine x={params.true_eta} stroke="#ef4444" strokeDasharray="5 5" strokeWidth={2} />
                    {params.sample_sizes.map(n => (
                      <React.Fragment key={n}>
                        <Line type="monotone" dataKey="y" data={allKDEData[n].eta.bernard} stroke={sampleColors[n].bernard} strokeWidth={2} dot={false} />
                        <Line type="monotone" dataKey="y" data={allKDEData[n].eta.exact} stroke={sampleColors[n].exact} strokeWidth={2} dot={false} strokeDasharray="4 2" />
                      </React.Fragment>
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            {/* γ 分布曲线 */}
            <div>
              <p className="text-center text-sm font-semibold mb-2" style={{ color: colors.gamma }}>γ 参数估计分布</p>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart margin={{ top: 10, right: 15, bottom: 30, left: 45 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis dataKey="x" tick={{ fontSize: 10 }} type="number" domain={['auto', 'auto']} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ borderRadius: '4px', border: '1px solid #e5e7eb', fontSize: '11px' }}
                      formatter={(v: number) => v.toFixed(5)}
                      labelFormatter={(l) => `γ: ${Number(l).toFixed(1)}`}
                    />
                    <ReferenceLine x={params.true_gamma} stroke="#ef4444" strokeDasharray="5 5" strokeWidth={2} />
                    {params.sample_sizes.map(n => (
                      <React.Fragment key={n}>
                        <Line type="monotone" dataKey="y" data={allKDEData[n].gamma.bernard} stroke={sampleColors[n].bernard} strokeWidth={2} dot={false} />
                        <Line type="monotone" dataKey="y" data={allKDEData[n].gamma.exact} stroke={sampleColors[n].exact} strokeWidth={2} dot={false} strokeDasharray="4 2" />
                      </React.Fragment>
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
          <p className="text-center text-xs text-slate-500 mt-3">
            使用高斯核密度估计 (KDE)。实线 = Bernard近似，虚线 = 精确中位秩。
            <span className="text-red-500 font-medium ml-2">红色虚线</span>为真实参数值。
          </p>
        </div>
      )}

      {/* 结论 */}
      <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-2xl p-6 border border-indigo-200">
        <h3 className="text-lg font-bold text-slate-800 mb-3 flex items-center gap-2">
          <TrendingUp className="text-indigo-600" size={20} />
          研究结论
        </h3>
        <div className="space-y-3 text-sm text-slate-700">
          {data.sample_results.map(sr => (
            <p key={sr.n}>
              <span className="font-bold text-slate-800">n={sr.n}:</span>{' '}
              Bernard β偏差 = {sr.bernard_stats.bias_beta?.mean.toFixed(6)},
              Exact β偏差 = {sr.exact_stats.bias_beta?.mean.toFixed(6)},
              差异 = {((sr.exact_stats.bias_beta?.mean || 0) - (sr.bernard_stats.bias_beta?.mean || 0)).toFixed(6)}
            </p>
          ))}
          <p className="pt-2 border-t border-indigo-200">
            随着样本量增加，两种方法的估计精度都有提升，差异逐渐缩小。
            对于小样本 (n=7)，精确中位秩可能略有优势。
          </p>
        </div>
      </div>
    </div>
  )
}
