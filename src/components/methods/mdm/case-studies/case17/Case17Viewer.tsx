/**
 * 案例17: 小样本估计的统计陷阱
 *
 * 研究 MDM 方法在 n=3 时估计偏差反而小于大样本的现象。
 *
 * 核心问题:
 * 1. 增加模拟次数是否会消除偶然性?
 * 2. 无解率是否导致幸存者偏差?
 * 3. 为什么会无解?
 */

'use client'

import React, { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, BarChart, Bar, ComposedChart,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Legend, ReferenceLine, Cell, ScatterChart, Scatter, AreaChart, Area
} from 'recharts'
import { AlertTriangle, TrendingDown, TrendingUp, HelpCircle, CheckCircle, XCircle } from 'lucide-react'
import { SigmaBetaChart, type CurveData as SigmaCurveData } from '../../charts/SigmaBetaChart'
import { GradientGammaChart, type GradientCurveData } from '../../charts/GradientGammaChart'

// 类型定义
interface Stats {
  total_runs: number
  valid_count: number
  no_solution_count: number
  no_solution_rate: number
  est_beta_mean: number | null
  est_beta_std: number | null
  est_beta_median: number | null
  est_eta_mean: number | null
  est_eta_std: number | null
  est_gamma_mean: number | null
  est_gamma_std: number | null
  bias_beta_mean: number | null
  bias_beta_std: number | null
  abs_bias_beta_mean: number | null
}

interface NoSolutionSample {
  sim_id: number
  seed: number
  sample: number[]
  sample_min: number
  sample_max: number
  chart_data: {
    sigma_beta_curves: Array<{ gamma: number; betas: number[]; sigmas: number[] }>
    gradient_gamma_curve: Array<{ gamma: number; gradient: number }>
  } | null
}

interface SampleSizeData {
  stats: Stats
  all_estimates: {
    beta: number[]
    eta: number[]
    gamma: number[]
  }
  no_solution_samples: NoSolutionSample[]
}

interface McRunsData {
  mc_runs: number
  by_sample_size: Record<string, SampleSizeData>
}

interface Case17Data {
  config: {
    true_beta: number
    true_eta: number
    true_gamma: number
    offset: number
    sample_sizes: number[]
    mc_runs_list: number[]
  }
  combinations: Array<{
    beta: number
    eta: number
    gamma: number
    offset: number
    by_mc_runs: Record<string, McRunsData>
  }>
}

interface Case17ViewerProps {
  caseId: string
  onCaseChange?: (caseId: string) => void
}

// 颜色配置
const SAMPLE_SIZE_COLORS: Record<number, string> = {
  3: '#ef4444',
  5: '#f97316',
  7: '#eab308',
  10: '#22c55e',
  20: '#3b82f6',
  30: '#8b5cf6',
}

export default function Case17Viewer({ caseId, onCaseChange }: Case17ViewerProps) {
  const [data, setData] = useState<Case17Data | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedMcRuns, setSelectedMcRuns] = useState(5000)
  const [selectedSampleSize, setSelectedSampleSize] = useState(3)
  const [selectedNoSolutionIndex, setSelectedNoSolutionIndex] = useState(0)

  // 加载数据
  useEffect(() => {
    const loadData = async () => {
      try {
        const res = await fetch('/case-studies/mdm/case17/data.json')
        if (!res.ok) throw new Error('数据加载失败')
        const json = await res.json()
        setData(json)
      } catch (err) {
        setError(err instanceof Error ? err.message : '未知错误')
      } finally {
        setIsLoading(false)
      }
    }
    loadData()
  }, [])

  // 当前选中的数据
  const currentData = useMemo(() => {
    if (!data || !data.combinations[0]) return null
    return data.combinations[0].by_mc_runs[selectedMcRuns]
  }, [data, selectedMcRuns])

  // 构建偏差对比图表数据
  const biasChartData = useMemo(() => {
    if (!currentData || !data) return []

    return data.config.sample_sizes.map(n => {
      const nData = currentData.by_sample_size[String(n)]
      const stats = nData?.stats

      return {
        n,
        bias_mean: stats?.bias_beta_mean ?? null,
        abs_bias_mean: stats?.abs_bias_beta_mean ?? null,
        std: stats?.est_beta_std ?? null,
        no_solution_rate: stats?.no_solution_rate ?? 0,
        color: SAMPLE_SIZE_COLORS[n]
      }
    })
  }, [currentData, data])

  // 构建模拟次数对比数据
  const mcRunsChartData = useMemo(() => {
    if (!data || !data.combinations[0]) return []

    return data.config.mc_runs_list.map(mc => {
      const item: any = { mc_runs: mc }

      data.config.sample_sizes.forEach(n => {
        const nData = data.combinations[0].by_mc_runs[String(mc)]?.by_sample_size[String(n)]
        item[`n${n}`] = nData?.stats?.abs_bias_beta_mean ?? null
      })

      return item
    })
  }, [data])

  // 当前选中的样本量数据
  const currentSampleData = useMemo(() => {
    if (!currentData) return null
    return currentData.by_sample_size[String(selectedSampleSize)]
  }, [currentData, selectedSampleSize])

  // 估计值分布数据
  const estimateDistributionData = useMemo(() => {
    if (!currentSampleData || !data) return null

    const trueBeta = data.config.true_beta
    const trueEta = data.config.true_eta
    const trueGamma = data.config.true_gamma

    // 创建直方图数据
    const createHistogram = (values: number[], bins: number = 30) => {
      if (!values.length) return []
      const min = Math.min(...values)
      const max = Math.max(...values)
      const binWidth = (max - min) / bins

      const histogram = Array(bins).fill(0)
      values.forEach(v => {
        const idx = Math.min(Math.floor((v - min) / binWidth), bins - 1)
        histogram[idx]++
      })

      return histogram.map((count, idx) => ({
        bin: min + idx * binWidth + binWidth / 2,
        count,
        density: count / values.length
      }))
    }

    return {
      beta: {
        histogram: createHistogram(currentSampleData.all_estimates.beta),
        trueValue: trueBeta,
        mean: currentSampleData.stats.est_beta_mean,
        values: currentSampleData.all_estimates.beta
      },
      eta: {
        histogram: createHistogram(currentSampleData.all_estimates.eta),
        trueValue: trueEta,
        mean: currentSampleData.stats.est_eta_mean,
        values: currentSampleData.all_estimates.eta
      },
      gamma: {
        histogram: createHistogram(currentSampleData.all_estimates.gamma),
        trueValue: trueGamma,
        mean: currentSampleData.stats.est_gamma_mean,
        values: currentSampleData.all_estimates.gamma
      }
    }
  }, [currentSampleData, data])

  // 无解样本数据
  const noSolutionSamples = useMemo(() => {
    return currentSampleData?.no_solution_samples ?? []
  }, [currentSampleData])

  // 当前选中的无解样本
  const currentNoSolutionSample = useMemo(() => {
    return noSolutionSamples[selectedNoSolutionIndex]
  }, [noSolutionSamples, selectedNoSolutionIndex])

  // 为 SigmaBetaChart 准备数据
  const sigmaBetaChartData = useMemo((): SigmaCurveData[] => {
    if (!currentNoSolutionSample?.chart_data?.sigma_beta_curves) return []

    // 只选择几个代表性的 gamma 曲线
    const curves = currentNoSolutionSample.chart_data.sigma_beta_curves
    const step = Math.max(1, Math.floor(curves.length / 5))
    const selectedCurves = curves.filter((_, idx) => idx % step === 0 || idx === curves.length - 1)

    return selectedCurves.map(curve => ({
      id: curve.gamma,
      data: curve.betas.map((beta, i) => ({ beta, sigma: curve.sigmas[i] })),
      color: `hsl(${(curve.gamma / 1500) * 240}, 70%, 50%)`,
      name: `γ=${curve.gamma.toFixed(0)}`
    }))
  }, [currentNoSolutionSample])

  // 为 GradientGammaChart 准备数据
  const gradientGammaChartData = useMemo((): GradientCurveData[] => {
    if (!currentNoSolutionSample?.chart_data?.gradient_gamma_curve) return []

    return [{
      id: 'gradient',
      data: currentNoSolutionSample.chart_data.gradient_gamma_curve.map(p => ({
        gamma: p.gamma,
        gradient: p.gradient
      })),
      color: '#ef4444'
    }]
  }, [currentNoSolutionSample])

  // 加载状态
  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-rose-200 border-t-rose-600 mb-4"></div>
          <p className="text-slate-600 font-bold">加载案例17数据中...</p>
        </div>
      </div>
    )
  }

  // 错误状态
  if (error || !data) {
    return (
      <div className="bg-white rounded-2xl border border-red-200 p-8">
        <div className="flex items-center gap-3 text-red-600">
          <AlertTriangle size={24} />
          <p>数据加载失败: {error}</p>
        </div>
      </div>
    )
  }

  const trueParams = data.config

  return (
    <div className="space-y-6">
      {/* 研究说明 */}
      <div className="bg-gradient-to-r from-rose-50 to-amber-50 rounded-2xl border border-rose-200 p-6">
        <h3 className="text-lg font-bold text-slate-800 mb-3 flex items-center gap-2">
          <AlertTriangle className="text-rose-600" size={22} />
          研究背景
        </h3>
        <p className="text-slate-700 leading-relaxed">
          在 MDM 方法的数据分析中，发现了一个反直觉的现象：
          <span className="font-bold text-rose-600">在某些参数组合下，n=3（样本量最小）的估计偏差反而比大样本更小</span>。
          本案例通过增加模拟次数、分析无解率等方式，揭示这一现象背后的统计陷阱。
        </p>
        <div className="mt-3 p-3 bg-white/50 rounded-lg">
          <span className="text-sm text-slate-600">研究参数：</span>
          <span className="ml-2 font-mono font-bold">
            β={trueParams.true_beta}, η={trueParams.true_eta}, γ={trueParams.true_gamma}, δ={trueParams.offset}
          </span>
        </div>
      </div>

      {/* MC 次数选择器 */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6">
        <div className="flex items-center gap-4">
          <span className="text-sm font-medium text-slate-600">模拟次数:</span>
          <div className="flex gap-2">
            {data.config.mc_runs_list.map(mc => (
              <button
                key={mc}
                onClick={() => setSelectedMcRuns(mc)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  selectedMcRuns === mc
                    ? 'bg-slate-800 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {mc.toLocaleString()}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 核心发现 */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6">
        <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
          <HelpCircle className="text-blue-600" size={22} />
          核心发现
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* 偏差对比柱状图 */}
          <div>
            <h4 className="text-sm font-bold text-slate-700 mb-3">β 绝对偏差 vs 样本量</h4>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={biasChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="n" label={{ value: '样本量 n', position: 'bottom', offset: -5 }} />
                <YAxis label={{ value: '绝对偏差', angle: -90, position: 'insideLeft' }} />
                <Tooltip
                  formatter={(value: any) => value?.toFixed(4)}
                  labelFormatter={(label) => `n=${label}`}
                />
                <Bar dataKey="abs_bias_mean" name="β 绝对偏差">
                  {biasChartData.map((entry, index) => (
                    <Cell key={index} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* 无解率对比 */}
          <div>
            <h4 className="text-sm font-bold text-slate-700 mb-3">无解率 vs 样本量</h4>
            <ResponsiveContainer width="100%" height={250}>
              <ComposedChart data={biasChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="n" />
                <YAxis label={{ value: '百分比 (%)', angle: -90, position: 'insideLeft' }} />
                <Tooltip formatter={(value: any) => `${value?.toFixed(1)}%`} />
                <Bar dataKey="no_solution_rate" name="无解率" fill="#ef4444" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* 模拟次数对比 */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6">
        <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
          <TrendingUp className="text-green-600" size={22} />
          问题1: 增加模拟次数是否消除偶然性?
        </h3>

        <div className="mb-4 p-4 bg-slate-50 rounded-xl">
          <p className="text-sm text-slate-600">
            如果 n=3 的"小偏差"是偶然，随着模拟次数增加，偏差应该趋近于真实值。
          </p>
        </div>

        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={mcRunsChartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="mc_runs"
              label={{ value: '模拟次数', position: 'bottom', offset: -5 }}
            />
            <YAxis label={{ value: '绝对偏差', angle: -90, position: 'insideLeft' }} />
            <Tooltip formatter={(value: any) => value?.toFixed(4)} />
            <Legend />
            {data.config.sample_sizes.map(n => (
              <Line
                key={n}
                type="monotone"
                dataKey={`n${n}`}
                name={`n=${n}`}
                stroke={SAMPLE_SIZE_COLORS[n]}
                strokeWidth={n === 3 ? 3 : 2}
                dot={{ r: n === 3 ? 6 : 4 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 详细统计表格 */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6">
        <h3 className="text-lg font-bold text-slate-800 mb-4">详细统计 ({selectedMcRuns.toLocaleString()} 次模拟)</h3>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50">
                <th className="px-4 py-3 text-left font-bold">样本量</th>
                <th className="px-4 py-3 text-right font-bold">β 估计均值</th>
                <th className="px-4 py-3 text-right font-bold">β 偏差均值</th>
                <th className="px-4 py-3 text-right font-bold">β 绝对偏差</th>
                <th className="px-4 py-3 text-right font-bold">标准差</th>
                <th className="px-4 py-3 text-right font-bold">无解率</th>
              </tr>
            </thead>
            <tbody>
              {biasChartData.map((row, idx) => {
                const nData = currentData?.by_sample_size[String(row.n)]
                const stats = nData?.stats

                return (
                  <tr
                    key={idx}
                    className={`border-t border-slate-100 ${row.n === selectedSampleSize ? 'bg-blue-50' : ''}`}
                    onClick={() => setSelectedSampleSize(row.n)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td className="px-4 py-3 font-bold" style={{ color: row.color }}>
                      n={row.n}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {stats?.est_beta_mean?.toFixed(4) ?? 'N/A'}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {stats?.bias_beta_mean?.toFixed(4) ?? 'N/A'}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-bold">
                      {row.abs_bias_mean?.toFixed(4) ?? 'N/A'}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {stats?.est_beta_std?.toFixed(4) ?? 'N/A'}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      <span className={row.no_solution_rate > 10 ? 'text-red-600 font-bold' : ''}>
                        {row.no_solution_rate.toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-slate-500">点击行可查看该样本量的估计值分布</p>
      </div>

      {/* 估计值分布图 */}
      {estimateDistributionData && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
            <TrendingDown className="text-purple-600" size={22} />
            估计值分布 (n={selectedSampleSize})
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* β 分布 */}
            <div>
              <h4 className="text-sm font-bold text-slate-700 mb-2 text-center">
                β 分布 (真实值: {trueParams.true_beta})
              </h4>
              <ResponsiveContainer width="100%" height={200}>
                <ComposedChart data={estimateDistributionData.beta.histogram}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="bin" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip formatter={(v: any) => v?.toFixed(0)} />
                  <Bar dataKey="count" fill="#3b82f6" opacity={0.7} />
                  <ReferenceLine
                    x={trueParams.true_beta}
                    stroke="#ef4444"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                  />
                  {estimateDistributionData.beta.mean && (
                    <ReferenceLine
                      x={estimateDistributionData.beta.mean}
                      stroke="#10b981"
                      strokeWidth={2}
                    />
                  )}
                </ComposedChart>
              </ResponsiveContainer>
              <div className="flex justify-center gap-4 mt-1 text-xs">
                <span className="text-red-500">— 真实值</span>
                <span className="text-green-500">— 估计均值</span>
              </div>
            </div>

            {/* η 分布 */}
            <div>
              <h4 className="text-sm font-bold text-slate-700 mb-2 text-center">
                η 分布 (真实值: {trueParams.true_eta})
              </h4>
              <ResponsiveContainer width="100%" height={200}>
                <ComposedChart data={estimateDistributionData.eta.histogram}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="bin" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip formatter={(v: any) => v?.toFixed(0)} />
                  <Bar dataKey="count" fill="#f59e0b" opacity={0.7} />
                  <ReferenceLine
                    x={trueParams.true_eta}
                    stroke="#ef4444"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                  />
                  {estimateDistributionData.eta.mean && (
                    <ReferenceLine
                      x={estimateDistributionData.eta.mean}
                      stroke="#10b981"
                      strokeWidth={2}
                    />
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            {/* γ 分布 */}
            <div>
              <h4 className="text-sm font-bold text-slate-700 mb-2 text-center">
                γ 分布 (真实值: {trueParams.true_gamma})
              </h4>
              <ResponsiveContainer width="100%" height={200}>
                <ComposedChart data={estimateDistributionData.gamma.histogram}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="bin" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip formatter={(v: any) => v?.toFixed(0)} />
                  <Bar dataKey="count" fill="#8b5cf6" opacity={0.7} />
                  <ReferenceLine
                    x={trueParams.true_gamma}
                    stroke="#ef4444"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                  />
                  {estimateDistributionData.gamma.mean && (
                    <ReferenceLine
                      x={estimateDistributionData.gamma.mean}
                      stroke="#10b981"
                      strokeWidth={2}
                    />
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* 无解样本分析 */}
      {noSolutionSamples.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
            <XCircle className="text-red-600" size={22} />
            无解样本分析 (n={selectedSampleSize})
          </h3>

          <div className="mb-4">
            <span className="text-sm text-slate-600">共 {noSolutionSamples.length} 个无解样本，选择：</span>
            <div className="flex gap-2 mt-2">
              {noSolutionSamples.map((sample, idx) => (
                <button
                  key={idx}
                  onClick={() => setSelectedNoSolutionIndex(idx)}
                  className={`px-3 py-1 rounded text-sm ${
                    selectedNoSolutionIndex === idx
                      ? 'bg-red-600 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  样本 {idx + 1}
                </button>
              ))}
            </div>
          </div>

          {currentNoSolutionSample && (
            <>
              {/* 样本信息 */}
              <div className="mb-4 p-4 bg-red-50 rounded-xl border border-red-200">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <span className="text-slate-500">样本 ID:</span>
                    <span className="ml-2 font-mono">{currentNoSolutionSample.sim_id}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">样本值范围:</span>
                    <span className="ml-2 font-mono">
                      [{currentNoSolutionSample.sample_min.toFixed(1)}, {currentNoSolutionSample.sample_max.toFixed(1)}]
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500">样本数据:</span>
                    <span className="ml-2 font-mono text-xs">
                      {currentNoSolutionSample.sample.map(v => v.toFixed(0)).join(', ')}
                    </span>
                  </div>
                </div>
              </div>

              {/* 图表 */}
              {currentNoSolutionSample.chart_data && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* σ_η(β) 曲线 */}
                  <div>
                    <h4 className="text-sm font-bold text-slate-700 mb-3">σ_η(β) 曲线 - 无最小值点</h4>
                    {sigmaBetaChartData.length > 0 ? (
                      <SigmaBetaChart
                        curves={sigmaBetaChartData}
                        interactive={false}
                        showControls={false}
                        overlayMode={true}
                        height={280}
                        noContainer={false}
                      />
                    ) : (
                      <div className="text-slate-500 p-4 bg-slate-50 rounded">无数据</div>
                    )}
                  </div>

                  {/* ∇(γ) 曲线 */}
                  <div>
                    <h4 className="text-sm font-bold text-slate-700 mb-3">∇(γ) 曲线 - 无交点</h4>
                    {gradientGammaChartData.length > 0 ? (
                      <GradientGammaChart
                        curves={gradientGammaChartData}
                        interactive={false}
                        overlayMode={false}
                        offsetReference={trueParams.offset}
                        height={280}
                        noContainer={false}
                      />
                    ) : (
                      <div className="text-slate-500 p-4 bg-slate-50 rounded">无数据</div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* 结论 */}
      <div className="bg-gradient-to-r from-green-50 to-blue-50 rounded-2xl border border-green-200 p-6">
        <h3 className="text-lg font-bold text-slate-800 mb-3 flex items-center gap-2">
          <CheckCircle className="text-green-600" size={22} />
          研究结论
        </h3>

        <div className="space-y-4 text-slate-700">
          <div className="flex items-start gap-3">
            <div className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-sm font-bold flex-shrink-0">1</div>
            <div>
              <p className="font-bold">偶然性验证</p>
              <p className="text-sm">观察增加模拟次数后，n=3 的偏差是否趋近于真实值。如果趋于稳定，说明偶然性不是主要原因。</p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-sm font-bold flex-shrink-0">2</div>
            <div>
              <p className="font-bold">幸存者偏差</p>
              <p className="text-sm">n=3 的高无解率（10%+）可能导致只有"幸运"的样本被保留，人为降低了均值偏差。</p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-sm font-bold flex-shrink-0">3</div>
            <div>
              <p className="font-bold">高方差陷阱</p>
              <p className="text-sm">n=3 的标准差远大于大样本，均值不稳定。即使均值接近真实值，中位数可能相差甚远。</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
