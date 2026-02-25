"use client"

import React, { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Legend
} from 'recharts'
import { BookOpen, ChevronDown, Table2, AlertTriangle, CheckCircle, Info, TrendingUp, LineChart as LineChartIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Case10ViewerProps {
  caseId: string
  onCaseChange?: (caseId: string) => void
}

// Trace 数据结构
interface TraceData {
  sigma_beta_curve: { beta: number; sigma: number }[]
  grad_gamma_curve: { gamma: number; gradient: number; sigma_min: number; best_beta?: number; best_eta?: number }[]
  target_offset: number
  optimal_gamma: number
  optimal_beta: number
}

// 蒙特卡洛模拟结果
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
  error?: string
}

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

interface SimulationParams {
  n_samples: number
  n_simulations: number
  true_beta: number
  true_eta: number
  true_gamma: number
  offset: number
  gamma_steps: number
  seed: number
}

interface FixedSampleResult {
  beta: number | null
  eta: number | null
  gamma: number | null
  r2: number | null
  status: string
  trace_data?: TraceData
}

interface FixedSampleAnalysis {
  data: number[]
  bernard: FixedSampleResult
  exact: FixedSampleResult
}

interface MedianRankComparison {
  i: number
  bernard: number
  exact: number
  diff: number
}

interface CaseData {
  simulation_params: SimulationParams
  median_rank_comparison?: MedianRankComparison[]
  bernard_stats: MethodStats
  exact_stats: MethodStats
  bernard_results: SimulationResult[]
  exact_results: SimulationResult[]
  fixed_sample?: FixedSampleAnalysis
}

// 核密度估计 (KDE) - 计算平滑的概率密度曲线
function computeKDE(values: number[], bandwidth?: number) {
  const n = values.length
  if (n === 0) return { points: [], bandwidth: 0 }

  // 使用 Silverman 规则自动选择带宽
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

  // 生成KDE曲线点
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min
  const numPoints = 200

  const points = Array.from({ length: numPoints }, (_, i) => {
    const x = min - range * 0.1 + (i / (numPoints - 1)) * range * 1.2
    // 高斯核密度估计
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

export default function Case10Viewer({ caseId, onCaseChange }: Case10ViewerProps) {
  const [data, setData] = useState<CaseData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [activeTab, setActiveTab] = useState<'statistics' | 'curves'>('curves')
  const [activeChart, setActiveChart] = useState<'gradient' | 'sigma_min' | 'sigma_beta'>('gradient')

  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true)
        const res = await fetch('/case-studies/mdm/case10/data.json')
        if (!res.ok) throw new Error('数据加载失败')
        const json = await res.json()
        setData(json)
      } catch (err: any) {
        setError(err.message)
      } finally {
        setIsLoading(false)
      }
    }
    loadData()
  }, [])

  // 计算有效结果
  const validBernardResults = useMemo(() => {
    if (!data) return []
    return data.bernard_results.filter(r => r.beta !== null && r.status === 'success')
  }, [data])

  const validExactResults = useMemo(() => {
    if (!data) return []
    return data.exact_results.filter(r => r.beta !== null && r.status === 'success')
  }, [data])

  // KDE 概率密度曲线数据
  const kdeData = useMemo(() => {
    if (validBernardResults.length === 0 || validExactResults.length === 0) return null

    const bernardBetas = validBernardResults.map(r => r.beta!)
    const exactBetas = validExactResults.map(r => r.beta!)
    const bernardEtas = validBernardResults.map(r => r.eta!)
    const exactEtas = validExactResults.map(r => r.eta!)
    const bernardGammas = validBernardResults.map(r => r.gamma!)
    const exactGammas = validExactResults.map(r => r.gamma!)

    return {
      beta: {
        bernard: computeKDE(bernardBetas).points,
        exact: computeKDE(exactBetas).points,
      },
      eta: {
        bernard: computeKDE(bernardEtas).points,
        exact: computeKDE(exactEtas).points,
      },
      gamma: {
        bernard: computeKDE(bernardGammas).points,
        exact: computeKDE(exactGammas).points,
      }
    }
  }, [validBernardResults, validExactResults])

  const colors = {
    beta: '#1e40af',      // 深蓝色
    eta: '#047857',       // 深绿色
    gamma: '#b45309'      // 深橙色
  }

  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-4 border-orange-200 border-t-orange-600 mb-4"></div>
          <p className="text-slate-600 font-bold">加载案例10数据中...</p>
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
  const hasTraceData = data.fixed_sample?.bernard?.trace_data && data.fixed_sample?.exact?.trace_data

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
                <option value="case-15">案例15: MDM vs WMLE 方法对比 (精细步长) ★</option>
                <option value="case-16">案例16: MDM vs WMLE 方法对比 (精细步长+多尺度) ★</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={18} />
            </div>
          </div>
        </div>
      )}

      {/* 标题 */}
      <div className="bg-gradient-to-r from-orange-50 to-amber-50 rounded-2xl p-6 border border-orange-200">
        <h2 className="text-xl font-bold text-slate-800 mb-2">案例10: 中位秩方法对比研究</h2>
        <p className="text-sm text-slate-600 mb-2">
          蒙特卡洛模拟: n={params.n_samples}, 各{params.n_simulations}次 | 真实参数: β={params.true_beta}, η={params.true_eta}, γ={params.true_gamma}
        </p>
        <div className="flex items-center gap-2 text-xs text-orange-600 bg-orange-100 px-3 py-1.5 rounded-lg w-fit">
          <Info size={14} />
          <span>对比 Bernard 近似 vs 精确中位秩(基于F分布) 对 MDM 估计的影响</span>
        </div>
      </div>

      {/* 过程量对比: 中位秩值 */}
      {data.median_rank_comparison && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <Table2 className="text-orange-600" size={20} />
            <h3 className="text-lg font-bold text-slate-800">过程量对比: 中位秩值 F(t<sub>i</sub>)</h3>
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
                  {data.median_rank_comparison.map((row) => (
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
                n = {params.n_samples} | 差异 = Exact - Bernard | 正值表示精确中位秩大于 Bernard 近似
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 主Tab选择 */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex gap-1 bg-slate-100 p-1 rounded-lg w-fit">
          {([
            { key: 'curves', label: '曲线对比', icon: LineChartIcon },
            { key: 'statistics', label: '统计分析', icon: Table2 },
          ] as const).map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 text-sm font-bold rounded-md transition-all",
                activeTab === tab.key
                  ? "bg-white text-orange-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              <tab.icon size={16} />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* 曲线对比区域 */}
      {activeTab === 'curves' && (
        <>
          {hasTraceData ? (
            <>
              {/* 固定样本信息 */}
              <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
                <h3 className="text-lg font-bold text-slate-800 mb-2">固定样本曲线分析</h3>
                <p className="text-sm text-slate-600 mb-2">
                  样本数据 (n={data.fixed_sample!.data.length}): {data.fixed_sample!.data.map(v => v.toFixed(1)).join(', ')}
                </p>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="bg-blue-50 p-3 rounded-lg">
                    <span className="font-bold text-blue-700">Bernard 近似: </span>
                    <span className="font-mono">
                      β = {data.fixed_sample!.bernard.beta?.toFixed(4) ?? 'N/A'},
                      γ = {data.fixed_sample!.bernard.gamma?.toFixed(1) ?? 'N/A'}
                    </span>
                  </div>
                  <div className="bg-emerald-50 p-3 rounded-lg">
                    <span className="font-bold text-emerald-700">精确中位秩: </span>
                    <span className="font-mono">
                      β = {data.fixed_sample!.exact.beta?.toFixed(4) ?? 'N/A'},
                      γ = {data.fixed_sample!.exact.gamma?.toFixed(1) ?? 'N/A'}
                    </span>
                  </div>
                </div>
              </div>

              {/* 曲线选择 */}
              <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
                <div className="flex gap-1 bg-slate-100 p-1 rounded-lg w-fit">
                  {([
                    { key: 'gradient', label: '梯度-γ 曲线' },
                    { key: 'sigma_min', label: 'σ_min-γ 曲线' },
                    { key: 'sigma_beta', label: 'σ-β 曲线' },
                  ] as const).map(tab => (
                    <button
                      key={tab.key}
                      onClick={() => setActiveChart(tab.key)}
                      className={cn(
                        "px-3 py-1.5 text-sm font-bold rounded-md transition-all",
                        activeChart === tab.key
                          ? "bg-white text-orange-600 shadow-sm"
                          : "text-slate-500 hover:text-slate-700"
                      )}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* 图表 */}
              <CurveComparisonCharts
                bernardTrace={data.fixed_sample!.bernard.trace_data!}
                exactTrace={data.fixed_sample!.exact.trace_data!}
                activeChart={activeChart}
              />
            </>
          ) : (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-amber-700 flex items-center gap-2">
              <AlertTriangle size={20} />
              暂无曲线数据，请重新运行数据生成脚本
            </div>
          )}
        </>
      )}

      {/* 统计分析区域 */}
      {activeTab === 'statistics' && (
        <>
          {/* 统计汇总对比表 */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <Table2 className="text-orange-600" size={20} />
              <h3 className="text-lg font-bold text-slate-800">表1: 统计汇总对比</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b-2 border-slate-300">
                    <th className="py-2 px-3 text-left font-bold text-slate-700">方法</th>
                    <th className="py-2 px-2 text-center font-bold text-slate-700">收敛率</th>
                    <th className="py-2 px-2 text-right font-bold text-slate-700">β均值</th>
                    <th className="py-2 px-2 text-right font-bold text-slate-700">β偏差</th>
                    <th className="py-2 px-2 text-right font-bold text-slate-700">β标准差</th>
                    <th className="py-2 px-2 text-right font-bold text-slate-700">γ均值</th>
                    <th className="py-2 px-2 text-right font-bold text-slate-700">γ偏差</th>
                    <th className="py-2 px-2 text-right font-bold text-slate-700">γ标准差</th>
                    <th className="py-2 px-2 text-right font-bold text-slate-700">β MSE</th>
                    <th className="py-2 px-2 text-right font-bold text-slate-700">γ MSE</th>
                  </tr>
                </thead>
                <tbody>
                  {/* Bernard */}
                  <tr className="border-b border-slate-200 bg-blue-50">
                    <td className="py-2 px-3 font-bold text-blue-700">Bernard 近似</td>
                    <td className="py-2 px-2 text-center font-mono">
                      <span className={cn(
                        "px-2 py-0.5 rounded text-xs font-bold",
                        data.bernard_stats.convergence_rate >= 0.95 ? "bg-green-100 text-green-700" :
                        data.bernard_stats.convergence_rate >= 0.8 ? "bg-yellow-100 text-yellow-700" :
                        "bg-red-100 text-red-700"
                      )}>
                        {(data.bernard_stats.convergence_rate * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-2 px-2 text-right font-mono">{data.bernard_stats.beta?.mean.toFixed(4)}</td>
                    <td className="py-2 px-2 text-right font-mono text-red-600">{data.bernard_stats.bias_beta?.mean.toFixed(6)}</td>
                    <td className="py-2 px-2 text-right font-mono">{data.bernard_stats.beta?.std.toFixed(4)}</td>
                    <td className="py-2 px-2 text-right font-mono">{data.bernard_stats.gamma?.mean.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono text-red-600">{data.bernard_stats.bias_gamma?.mean.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono">{data.bernard_stats.gamma?.std.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono">{data.bernard_stats.mse_beta?.toFixed(6)}</td>
                    <td className="py-2 px-2 text-right font-mono">{data.bernard_stats.mse_gamma?.toFixed(2)}</td>
                  </tr>
                  {/* Exact */}
                  <tr className="border-b border-slate-200 bg-emerald-50">
                    <td className="py-2 px-3 font-bold text-emerald-700">精确中位秩</td>
                    <td className="py-2 px-2 text-center font-mono">
                      <span className={cn(
                        "px-2 py-0.5 rounded text-xs font-bold",
                        data.exact_stats.convergence_rate >= 0.95 ? "bg-green-100 text-green-700" :
                        data.exact_stats.convergence_rate >= 0.8 ? "bg-yellow-100 text-yellow-700" :
                        "bg-red-100 text-red-700"
                      )}>
                        {(data.exact_stats.convergence_rate * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-2 px-2 text-right font-mono">{data.exact_stats.beta?.mean.toFixed(4)}</td>
                    <td className="py-2 px-2 text-right font-mono text-red-600">{data.exact_stats.bias_beta?.mean.toFixed(6)}</td>
                    <td className="py-2 px-2 text-right font-mono">{data.exact_stats.beta?.std.toFixed(4)}</td>
                    <td className="py-2 px-2 text-right font-mono">{data.exact_stats.gamma?.mean.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono text-red-600">{data.exact_stats.bias_gamma?.mean.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono">{data.exact_stats.gamma?.std.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono">{data.exact_stats.mse_beta?.toFixed(6)}</td>
                    <td className="py-2 px-2 text-right font-mono">{data.exact_stats.mse_gamma?.toFixed(2)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="text-xs text-slate-500 mt-2">
              偏差 = 估计均值 - 真实值 | MSE = 均方误差 | 有效样本: Bernard {data.bernard_stats.valid_count}, Exact {data.exact_stats.valid_count}
            </p>
          </div>

          {/* 三参数估计值概率密度分布 (KDE) */}
          {kdeData && (
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
              <div className="flex items-center gap-2 mb-4">
                <LineChartIcon className="text-orange-600" size={20} />
                <h3 className="text-lg font-bold text-slate-800">参数估计值概率密度分布 (核密度估计)</h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* β 分布曲线 */}
                <div>
                  <p className="text-center text-sm font-semibold mb-2" style={{ color: colors.beta }}>β 参数估计分布</p>
                  <div className="h-[280px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart margin={{ top: 10, right: 15, bottom: 30, left: 45 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                        <XAxis
                          dataKey="x"
                          tick={{ fontSize: 10 }}
                          tickLine={true}
                          stroke="#000"
                          strokeWidth={1}
                          type="number"
                          domain={['auto', 'auto']}
                          axisLine={{ stroke: '#000', strokeWidth: 1 }}
                        />
                        <YAxis
                          tick={{ fontSize: 10 }}
                          tickLine={true}
                          stroke="#000"
                          strokeWidth={1}
                          axisLine={{ stroke: '#000', strokeWidth: 1 }}
                        />
                        <Tooltip
                          contentStyle={{
                            borderRadius: '4px',
                            border: '1px solid #e5e7eb',
                            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                            fontSize: '12px'
                          }}
                          formatter={(value: number) => value.toFixed(4)}
                          labelFormatter={(label) => `β估计值: ${Number(label).toFixed(3)}`}
                        />
                        <Legend
                          verticalAlign="top"
                          align="center"
                          wrapperStyle={{ fontSize: '11px', fontWeight: 500 }}
                        />
                        <ReferenceLine x={params.true_beta} stroke="#ef4444" strokeDasharray="5 5" strokeWidth={2} />
                        <Line
                          type="monotone"
                          dataKey="y"
                          data={kdeData.beta.bernard}
                          name="Bernard"
                          stroke="#3b82f6"
                          strokeWidth={2}
                          dot={false}
                        />
                        <Line
                          type="monotone"
                          dataKey="y"
                          data={kdeData.beta.exact}
                          name="Exact"
                          stroke="#10b981"
                          strokeWidth={2}
                          dot={false}
                        />
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
                        <XAxis
                          dataKey="x"
                          tick={{ fontSize: 10 }}
                          tickLine={true}
                          stroke="#000"
                          strokeWidth={1}
                          type="number"
                          domain={['auto', 'auto']}
                          axisLine={{ stroke: '#000', strokeWidth: 1 }}
                        />
                        <YAxis
                          tick={{ fontSize: 10 }}
                          tickLine={true}
                          stroke="#000"
                          strokeWidth={1}
                          axisLine={{ stroke: '#000', strokeWidth: 1 }}
                        />
                        <Tooltip
                          contentStyle={{
                            borderRadius: '4px',
                            border: '1px solid #e5e7eb',
                            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                            fontSize: '12px'
                          }}
                          formatter={(value: number) => value.toFixed(5)}
                          labelFormatter={(label) => `η估计值: ${Number(label).toFixed(1)}`}
                        />
                        <Legend
                          verticalAlign="top"
                          align="center"
                          wrapperStyle={{ fontSize: '11px', fontWeight: 500 }}
                        />
                        <ReferenceLine x={params.true_eta} stroke="#ef4444" strokeDasharray="5 5" strokeWidth={2} />
                        <Line
                          type="monotone"
                          dataKey="y"
                          data={kdeData.eta.bernard}
                          name="Bernard"
                          stroke="#3b82f6"
                          strokeWidth={2}
                          dot={false}
                        />
                        <Line
                          type="monotone"
                          dataKey="y"
                          data={kdeData.eta.exact}
                          name="Exact"
                          stroke="#10b981"
                          strokeWidth={2}
                          dot={false}
                        />
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
                        <XAxis
                          dataKey="x"
                          tick={{ fontSize: 10 }}
                          tickLine={true}
                          stroke="#000"
                          strokeWidth={1}
                          type="number"
                          domain={['auto', 'auto']}
                          axisLine={{ stroke: '#000', strokeWidth: 1 }}
                        />
                        <YAxis
                          tick={{ fontSize: 10 }}
                          tickLine={true}
                          stroke="#000"
                          strokeWidth={1}
                          axisLine={{ stroke: '#000', strokeWidth: 1 }}
                        />
                        <Tooltip
                          contentStyle={{
                            borderRadius: '4px',
                            border: '1px solid #e5e7eb',
                            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                            fontSize: '12px'
                          }}
                          formatter={(value: number) => value.toFixed(5)}
                          labelFormatter={(label) => `γ估计值: ${Number(label).toFixed(1)}`}
                        />
                        <Legend
                          verticalAlign="top"
                          align="center"
                          wrapperStyle={{ fontSize: '11px', fontWeight: 500 }}
                        />
                        <ReferenceLine x={params.true_gamma} stroke="#ef4444" strokeDasharray="5 5" strokeWidth={2} />
                        <Line
                          type="monotone"
                          dataKey="y"
                          data={kdeData.gamma.bernard}
                          name="Bernard"
                          stroke="#3b82f6"
                          strokeWidth={2}
                          dot={false}
                        />
                        <Line
                          type="monotone"
                          dataKey="y"
                          data={kdeData.gamma.exact}
                          name="Exact"
                          stroke="#10b981"
                          strokeWidth={2}
                          dot={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
              <p className="text-center text-base font-semibold text-slate-700 mt-3">
                图: 参数估计值概率密度分布 (核密度估计)
              </p>
              <p className="text-center text-xs text-slate-500 mt-1">
                使用高斯核密度估计 (KDE) 平滑曲线，带宽采用 Silverman 规则自动选择。
                <span className="text-red-500 font-medium ml-2">红色虚线</span>为真实参数值。
              </p>
            </div>
          )}
        </>
      )}

      {/* 结论 */}
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl p-6 border border-amber-200">
        <h3 className="text-lg font-bold text-slate-800 mb-3 flex items-center gap-2">
          <TrendingUp className="text-amber-600" size={20} />
          研究结论
        </h3>
        <div className="space-y-3 text-sm text-slate-700">
          <p>
            <span className="font-bold text-blue-700">Bernard 近似</span>: 偏差 = {data.bernard_stats.bias_beta?.mean.toFixed(6)},
            标准差 = {data.bernard_stats.beta?.std.toFixed(4)}, 收敛率 = {(data.bernard_stats.convergence_rate * 100).toFixed(1)}%
          </p>
          <p>
            <span className="font-bold text-emerald-700">精确中位秩</span>: 偏差 = {data.exact_stats.bias_beta?.mean.toFixed(6)},
            标准差 = {data.exact_stats.beta?.std.toFixed(4)}, 收敛率 = {(data.exact_stats.convergence_rate * 100).toFixed(1)}%
          </p>
          <p className="pt-2 border-t border-amber-200">
            对于 n={params.n_samples} 的小样本情况，两种方法的估计精度差异
            {Math.abs((data.bernard_stats.bias_beta?.mean || 0) - (data.exact_stats.bias_beta?.mean || 0)) < 0.001 ? (
              <span className="text-green-600 font-bold"> 不显著</span>
            ) : (
              <span className="text-orange-600 font-bold"> 较为明显</span>
            )}。
          </p>
        </div>
      </div>
    </div>
  )
}

// 曲线对比图表组件
function CurveComparisonCharts({
  bernardTrace,
  exactTrace,
  activeChart
}: {
  bernardTrace: TraceData
  exactTrace: TraceData
  activeChart: 'gradient' | 'sigma_min' | 'sigma_beta'
}) {
  // γ 范围限制 (针对固定样本)
  const GAMMA_MIN = 1000
  const GAMMA_MAX = 1500

  // 过滤梯度曲线数据
  const filteredBernardCurve = useMemo(() => {
    return bernardTrace.grad_gamma_curve.filter(d => d.gamma >= GAMMA_MIN && d.gamma <= GAMMA_MAX)
  }, [bernardTrace.grad_gamma_curve])

  const filteredExactCurve = useMemo(() => {
    return exactTrace.grad_gamma_curve.filter(d => d.gamma >= GAMMA_MIN && d.gamma <= GAMMA_MAX)
  }, [exactTrace.grad_gamma_curve])

  return (
    <>
      {/* 图1: 梯度-γ 曲线 */}
      {activeChart === 'gradient' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-slate-800">图1: 梯度 vs γ 曲线对比</h3>
            <div className="flex gap-4 text-xs">
              <span className="flex items-center gap-1">
                <span className="w-4 h-0.5 bg-blue-500 inline-block"></span>
                <span className="text-slate-600">Bernard: γ*={bernardTrace.optimal_gamma?.toFixed(0)}</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-4 h-0.5 bg-emerald-500 inline-block"></span>
                <span className="text-slate-600">Exact: γ*={exactTrace.optimal_gamma?.toFixed(0)}</span>
              </span>
            </div>
          </div>
          <div className="h-[350px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart margin={{ top: 10, right: 30, bottom: 40, left: 60 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  type="number"
                  dataKey="gamma"
                  domain={[GAMMA_MIN, GAMMA_MAX]}
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v) => v.toFixed(0)}
                  label={{ value: '位置参数 γ', position: 'bottom', offset: 0, fontSize: 11, fill: '#64748b' }}
                  allowDataOverflow
                />
                <YAxis
                  width={50}
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v) => v.toFixed(2)}
                  label={{ value: '梯度 ∇(γ)', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#64748b' }}
                />
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                  formatter={(v: number) => [v.toFixed(4), '梯度']}
                  labelFormatter={(v) => `γ: ${Number(v).toFixed(1)}`}
                />
                <Legend />
                {/* 偏移值参考线 */}
                <ReferenceLine
                  y={bernardTrace.target_offset}
                  stroke="#ef4444"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  label={{ value: `δ=${bernardTrace.target_offset}`, position: 'right', fill: '#ef4444', fontSize: 10 }}
                />
                {/* Bernard 曲线 */}
                <Line
                  data={filteredBernardCurve}
                  type="monotone"
                  dataKey="gradient"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                  name="Bernard"
                />
                {/* Exact 曲线 */}
                <Line
                  data={filteredExactCurve}
                  type="monotone"
                  dataKey="gradient"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                  name="Exact"
                />
                {/* Bernard 最优点 */}
                {bernardTrace.optimal_gamma >= GAMMA_MIN && bernardTrace.optimal_gamma <= GAMMA_MAX && (
                  <ReferenceLine
                    x={bernardTrace.optimal_gamma}
                    stroke="#3b82f6"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    label={{ value: `γ_B=${bernardTrace.optimal_gamma.toFixed(0)}`, position: 'top', fill: '#3b82f6', fontSize: 9 }}
                  />
                )}
                {/* Exact 最优点 */}
                {exactTrace.optimal_gamma >= GAMMA_MIN && exactTrace.optimal_gamma <= GAMMA_MAX && (
                  <ReferenceLine
                    x={exactTrace.optimal_gamma}
                    stroke="#10b981"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    label={{ value: `γ_E=${exactTrace.optimal_gamma.toFixed(0)}`, position: 'top', fill: '#10b981', fontSize: 9 }}
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            梯度曲线与红色虚线 δ={bernardTrace.target_offset} 的交点确定最优 γ。
            两种中位秩方法产生的梯度曲线略有差异，导致估计结果不同。
          </p>
        </div>
      )}

      {/* 图2: σ_min-γ 曲线 */}
      {activeChart === 'sigma_min' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-slate-800">图2: 最小标准差 σ_min vs γ 对比</h3>
            <div className="flex gap-4 text-xs">
              <span className="flex items-center gap-1">
                <span className="w-4 h-0.5 bg-blue-500 inline-block"></span>
                <span className="text-slate-600">Bernard</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-4 h-0.5 bg-emerald-500 inline-block"></span>
                <span className="text-slate-600">Exact</span>
              </span>
            </div>
          </div>
          <div className="h-[350px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart margin={{ top: 10, right: 30, bottom: 40, left: 60 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  type="number"
                  dataKey="gamma"
                  domain={[GAMMA_MIN, GAMMA_MAX]}
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v) => v.toFixed(0)}
                  label={{ value: '位置参数 γ', position: 'bottom', offset: 0, fontSize: 11, fill: '#64748b' }}
                  allowDataOverflow
                />
                <YAxis
                  width={50}
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v) => v.toFixed(0)}
                  label={{ value: '最小标准差 σ_min', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#64748b' }}
                />
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                  formatter={(v: number) => [v.toFixed(2), 'σ_min']}
                  labelFormatter={(v) => `γ: ${Number(v).toFixed(1)}`}
                />
                <Legend />
                {/* Bernard 曲线 */}
                <Line
                  data={filteredBernardCurve}
                  type="monotone"
                  dataKey="sigma_min"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                  name="Bernard"
                />
                {/* Exact 曲线 */}
                <Line
                  data={filteredExactCurve}
                  type="monotone"
                  dataKey="sigma_min"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                  name="Exact"
                />
                {/* Bernard 最优点 */}
                {bernardTrace.optimal_gamma >= GAMMA_MIN && bernardTrace.optimal_gamma <= GAMMA_MAX && (
                  <ReferenceLine
                    x={bernardTrace.optimal_gamma}
                    stroke="#3b82f6"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                  />
                )}
                {/* Exact 最优点 */}
                {exactTrace.optimal_gamma >= GAMMA_MIN && exactTrace.optimal_gamma <= GAMMA_MAX && (
                  <ReferenceLine
                    x={exactTrace.optimal_gamma}
                    stroke="#10b981"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            每个 γ 对应的最小标准差 σ_min（通过 Brent 优化找到最优 β）。
            曲线呈 U 型，底部对应最优拟合。两种方法的曲线形状相似但位置略有偏移。
          </p>
        </div>
      )}

      {/* 图3: σ-β 曲线 */}
      {activeChart === 'sigma_beta' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-slate-800">图3: σ vs β 曲线对比 (在最优 γ 处)</h3>
            <div className="flex gap-4 text-xs">
              <span className="flex items-center gap-1">
                <span className="w-4 h-0.5 bg-blue-500 inline-block"></span>
                <span className="text-slate-600">Bernard: β*={bernardTrace.optimal_beta?.toFixed(4)}</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-4 h-0.5 bg-emerald-500 inline-block"></span>
                <span className="text-slate-600">Exact: β*={exactTrace.optimal_beta?.toFixed(4)}</span>
              </span>
            </div>
          </div>
          <div className="h-[350px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart margin={{ top: 10, right: 30, bottom: 40, left: 60 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  type="number"
                  dataKey="beta"
                  domain={[0.5, 5]}
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v) => v.toFixed(1)}
                  label={{ value: '形状参数 β', position: 'bottom', offset: 0, fontSize: 11, fill: '#64748b' }}
                />
                <YAxis
                  width={50}
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v) => v.toFixed(0)}
                  label={{ value: '标准差 σ_η', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#64748b' }}
                />
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                  formatter={(v: number) => [v.toFixed(2), 'σ']}
                  labelFormatter={(v) => `β: ${Number(v).toFixed(2)}`}
                />
                <Legend />
                {/* Bernard 曲线 */}
                <Line
                  data={bernardTrace.sigma_beta_curve}
                  type="monotone"
                  dataKey="sigma"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                  name="Bernard"
                />
                {/* Exact 曲线 */}
                <Line
                  data={exactTrace.sigma_beta_curve}
                  type="monotone"
                  dataKey="sigma"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                  name="Exact"
                />
                {/* Bernard 最优 β */}
                {bernardTrace.optimal_beta >= 0.5 && bernardTrace.optimal_beta <= 5 && (
                  <ReferenceLine
                    x={bernardTrace.optimal_beta}
                    stroke="#3b82f6"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    label={{ value: `β_B`, position: 'top', fill: '#3b82f6', fontSize: 9 }}
                  />
                )}
                {/* Exact 最优 β */}
                {exactTrace.optimal_beta >= 0.5 && exactTrace.optimal_beta <= 5 && (
                  <ReferenceLine
                    x={exactTrace.optimal_beta}
                    stroke="#10b981"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    label={{ value: `β_E`, position: 'top', fill: '#10b981', fontSize: 9 }}
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            在各自最优 γ 下的 σ-β 曲线。曲线的最低点对应 Brent 优化找到的最优 β。
            两种方法产生的曲线形状相似，但最优点的位置略有不同。
          </p>
        </div>
      )}

      {/* 参数估计对比表 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <Table2 className="text-orange-600" size={20} />
          <h3 className="text-lg font-bold text-slate-800">固定样本参数估计对比</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b-2 border-slate-300">
                <th className="py-2 px-3 text-left font-bold text-slate-700">方法</th>
                <th className="py-2 px-2 text-right font-bold text-slate-700">γ 估计</th>
                <th className="py-2 px-2 text-right font-bold text-slate-700">β 估计</th>
                <th className="py-2 px-2 text-right font-bold text-slate-700">η 估计</th>
                <th className="py-2 px-2 text-right font-bold text-slate-700">R²</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-slate-200 bg-blue-50">
                <td className="py-2 px-3 font-bold text-blue-700">Bernard 近似</td>
                <td className="py-2 px-2 text-right font-mono">{bernardTrace.optimal_gamma?.toFixed(2) ?? 'N/A'}</td>
                <td className="py-2 px-2 text-right font-mono">{bernardTrace.optimal_beta?.toFixed(4) ?? 'N/A'}</td>
                <td className="py-2 px-2 text-right font-mono">—</td>
                <td className="py-2 px-2 text-right font-mono">—</td>
              </tr>
              <tr className="border-b border-slate-200 bg-emerald-50">
                <td className="py-2 px-3 font-bold text-emerald-700">精确中位秩</td>
                <td className="py-2 px-2 text-right font-mono">{exactTrace.optimal_gamma?.toFixed(2) ?? 'N/A'}</td>
                <td className="py-2 px-2 text-right font-mono">{exactTrace.optimal_beta?.toFixed(4) ?? 'N/A'}</td>
                <td className="py-2 px-2 text-right font-mono">—</td>
                <td className="py-2 px-2 text-right font-mono">—</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-xs text-slate-500 mt-2">
          两种中位秩方法在相同样本上的估计结果对比。差异主要源于中位秩值的计算方法不同。
        </p>
      </div>
    </>
  )
}
