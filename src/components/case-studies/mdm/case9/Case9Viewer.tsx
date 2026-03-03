"use client"

import React, { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, ComposedChart, Scatter, BarChart, Bar, Legend
} from 'recharts'
import { BookOpen, ChevronDown, Table2, AlertTriangle, CheckCircle, Info, TrendingUp, Eye, EyeOff } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useCaseList } from '@/hooks/useCaseList'

interface Case9ViewerProps {
  caseId: string
  onCaseChange?: (caseId: string) => void
}

// 数据结构
interface TraceData {
  sigma_beta_curve: { beta: number; sigma: number }[]
  grad_gamma_curve: { gamma: number; gradient: number; sigma_min: number; best_beta?: number }[]
  sigma_beta_gamma?: { gamma: number; betas: number[]; sigmas: number[] }[]
  target_offset: number
  optimal_gamma: number
  optimal_beta: number
  gamma_steps?: number
  discrete_gamma?: boolean
  beta_step?: number
  poly_fit?: {
    degree: number
    coefficients: number[]
    formula: string
    fit_gammas: number[]
    fit_grads: number[]
    fit_gamma: number | null
    r_squared: number
  }
}

interface StepResult {
  beta_step: number
  offset: number
  beta: number | null
  eta: number | null
  gamma: number | null
  r2: number | null
  status: string | boolean
  beta_error?: number
  gamma_error?: number
  eta_error?: number
  trace_data?: TraceData
  error?: string
}

interface BrentResult {
  method: string
  offset: number
  beta: number | null
  eta: number | null
  gamma: number | null
  r2: number | null
  status: string | boolean
  trace_data?: TraceData
}

interface CaseData {
  source_case: string
  data: number[]
  true_params: { beta: number; eta: number; gamma: number }
  beta_steps: number[]
  offsets: number[]
  gamma_steps: number
  brent_results: BrentResult[]
  results: StepResult[]
  discrete_results: StepResult[]
}

const OFFSET_TABS = [
  { value: 0.1, label: 'δ = 0.1' },
  { value: 0.15, label: 'δ = 0.15' },
]

// 颜色方案：从深蓝(小步长)到红色(大步长)
const getStepColor = (step: number, steps: number[]) => {
  const idx = steps.indexOf(step)
  const ratio = idx / (steps.length - 1)
  // 从蓝色渐变到红色
  const h = 240 - ratio * 240  // 240 (蓝) -> 0 (红)
  return `hsl(${h}, 70%, 50%)`
}

export default function Case9Viewer({ caseId, onCaseChange }: Case9ViewerProps) {
  const [data, setData] = useState<CaseData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [activeOffset, setActiveOffset] = useState(0.1)
  const [activeBetaStep, setActiveBetaStep] = useState(0.01)
  const [activeChart, setActiveChart] = useState<'error' | 'sigmaBeta' | 'sigmaMin' | 'sigmaMinDiscrete' | 'gradient' | 'gradientDiscrete'>('error')

  // 曲线显示/隐藏状态
  const [visibleSigmaBeta, setVisibleSigmaBeta] = useState<Set<number>>(new Set([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1]))
  const [visibleSigmaMin, setVisibleSigmaMin] = useState<Set<number>>(new Set([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1]))
  const [showBrentCurve, setShowBrentCurve] = useState(true)  // Brent曲线默认显示

  // 数据点显示开关
  const [showDataPoints, setShowDataPoints] = useState(true)  // 默认显示数据点

  // 切换曲线显示
  const toggleSigmaBetaVisibility = (step: number) => {
    setVisibleSigmaBeta(prev => {
      const newSet = new Set(prev)
      if (newSet.has(step)) {
        newSet.delete(step)
      } else {
        newSet.add(step)
      }
      return newSet
    })
  }

  const toggleSigmaMinVisibility = (step: number) => {
    setVisibleSigmaMin(prev => {
      const newSet = new Set(prev)
      if (newSet.has(step)) {
        newSet.delete(step)
      } else {
        newSet.add(step)
      }
      return newSet
    })
  }

  // 全选/全不选
  const toggleAllSigmaBeta = () => {
    if (visibleSigmaBeta.size === 10) {
      setVisibleSigmaBeta(new Set())
    } else {
      setVisibleSigmaBeta(new Set([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1]))
    }
  }

  const toggleAllSigmaMin = () => {
    if (visibleSigmaMin.size === 10) {
      setVisibleSigmaMin(new Set())
    } else {
      setVisibleSigmaMin(new Set([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1]))
    }
  }

  // 离散γ搜索的σ_min曲线显示/隐藏状态
  const [visibleSigmaMinDiscrete, setVisibleSigmaMinDiscrete] = useState<Set<number>>(new Set([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1]))

  const toggleSigmaMinDiscreteVisibility = (step: number) => {
    setVisibleSigmaMinDiscrete(prev => {
      const newSet = new Set(prev)
      if (newSet.has(step)) {
        newSet.delete(step)
      } else {
        newSet.add(step)
      }
      return newSet
    })
  }

  const toggleAllSigmaMinDiscrete = () => {
    if (visibleSigmaMinDiscrete.size === 10) {
      setVisibleSigmaMinDiscrete(new Set())
    } else {
      setVisibleSigmaMinDiscrete(new Set([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1]))
    }
  }

  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true)
        const res = await fetch('/case-studies/mdm/case9/data.json')
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

  // 获取案例列表 - 必须在所有条件返回之前调用
  const { cases: caseList } = useCaseList()

  // 当前偏移量下的所有结果
  const currentResults = useMemo(() => {
    if (!data) return []
    return data.results.filter(r => r.offset === activeOffset && !r.error)
  }, [data, activeOffset])

  // 当前偏移量下的离散γ搜索结果
  const currentDiscreteResults = useMemo(() => {
    if (!data?.discrete_results) return []
    return data.discrete_results.filter(r => r.offset === activeOffset && !r.error)
  }, [data, activeOffset])

  // 当前选中的结果
  const currentResult = currentResults.find(r => r.beta_step === activeBetaStep)

  // β步长 vs 估计误差数据
  const errorChartData = useMemo(() => {
    return currentResults
      .filter(r => r.beta_error !== undefined)
      .map(r => ({
        beta_step: r.beta_step,
        beta: r.beta,
        gamma: r.gamma,
        beta_error: r.beta_error,
        gamma_error: r.gamma_error,
      }))
      .sort((a, b) => a.beta_step - b.beta_step)
  }, [currentResults])

  // β步长 vs γ估计值数据
  const gammaChartData = useMemo(() => {
    return currentResults
      .filter(r => r.gamma !== null)
      .map(r => ({
        beta_step: r.beta_step,
        gamma: r.gamma,
        beta: r.beta,
      }))
      .sort((a, b) => a.beta_step - b.beta_step)
  }, [currentResults])

  // 多β步长的σ-β曲线叠加数据（选择最优γ附近的数据）
  const sigmaBetaOverlayData = useMemo(() => {
    if (!data) return []

    return currentResults
      .filter(r => r.trace_data?.sigma_beta_gamma)
      .map(r => {
        const sigmaBetaGamma = r.trace_data!.sigma_beta_gamma!
        // 找到最接近最优γ的切片
        let closestSlice = sigmaBetaGamma[0]
        let minDiff = Infinity
        for (const slice of sigmaBetaGamma) {
          const diff = Math.abs(slice.gamma - (r.gamma || 0))
          if (diff < minDiff) {
            minDiff = diff
            closestSlice = slice
          }
        }

        const betaStep = r.beta_step!
        return {
          beta_step: betaStep,
          color: getStepColor(betaStep, data.beta_steps),
          data: closestSlice.betas.map((beta, i) => ({
            beta,
            sigma: closestSlice.sigmas[i]
          })).filter(d => d.beta >= 0 && d.beta <= 3 && d.sigma !== null && d.sigma !== undefined && d.sigma <= 3000),
          optimal_beta: r.beta,
          optimal_gamma: r.gamma
        }
      })
      .sort((a, b) => a.beta_step - b.beta_step)
  }, [currentResults, data])

  // Brent优化的σ-β曲线数据
  const brentSigmaBetaData = useMemo(() => {
    if (!data?.brent_results) return null

    const brentResult = data.brent_results.find(r => r.offset === activeOffset)
    if (!brentResult?.trace_data?.sigma_beta_gamma) return null

    const sigmaBetaGamma = brentResult.trace_data.sigma_beta_gamma
    // 找到最接近最优γ的切片
    let closestSlice = sigmaBetaGamma[0]
    let minDiff = Infinity
    for (const slice of sigmaBetaGamma) {
      const diff = Math.abs(slice.gamma - (brentResult.gamma || 0))
      if (diff < minDiff) {
        minDiff = diff
        closestSlice = slice
      }
    }

    return {
      beta: brentResult.beta,
      gamma: brentResult.gamma,
      eta: brentResult.eta,
      data: closestSlice.betas.map((beta, i) => ({
        beta,
        sigma: closestSlice.sigmas[i]
      })).filter((d: { beta: number; sigma: number | null }) => d.beta >= 0 && d.beta <= 3 && d.sigma !== null && d.sigma !== undefined && d.sigma <= 3000)
    }
  }, [data, activeOffset])

  // 多β步长的σ_min-γ曲线叠加数据
  const sigmaMinOverlayData = useMemo(() => {
    if (!data) return []

    return currentResults
      .filter(r => r.trace_data?.grad_gamma_curve)
      .map(r => {
        const betaStep = r.beta_step!
        const curve = r.trace_data!.grad_gamma_curve

        return {
          beta_step: betaStep,
          color: getStepColor(betaStep, data.beta_steps),
          data: curve
            .filter(d => d.gamma >= 1000 && d.gamma <= 1500)
            .map(d => ({
              gamma: d.gamma,
              sigma_min: d.sigma_min,
              best_beta: d.best_beta
            })),
          optimal_gamma: r.gamma
        }
      })
      .sort((a, b) => a.beta_step - b.beta_step)
  }, [currentResults, data])

  // 离散γ搜索的σ_min-γ曲线叠加数据（用于图6）
  const sigmaMinDiscreteOverlayData = useMemo(() => {
    if (!data) return []

    return currentDiscreteResults
      .filter(r => r.trace_data?.grad_gamma_curve)
      .map(r => {
        const betaStep = r.beta_step!
        const curve = r.trace_data!.grad_gamma_curve

        return {
          beta_step: betaStep,
          color: getStepColor(betaStep, data.beta_steps),
          data: curve
            .filter(d => d.gamma >= 1000 && d.gamma <= 1500)
            .map(d => ({
              gamma: d.gamma,
              sigma_min: d.sigma_min,
              best_beta: d.best_beta
            })),
          optimal_gamma: r.gamma
        }
      })
      .sort((a, b) => a.beta_step - b.beta_step)
  }, [currentDiscreteResults, data])

  // 多β步长的梯度-γ曲线叠加数据（原始点 + 拟合曲线）
  const gradientOverlayData = useMemo(() => {
    if (!data) return []

    return currentResults
      .filter(r => r.trace_data?.grad_gamma_curve)
      .map(r => {
        const betaStep = r.beta_step!
        const curve = r.trace_data!.grad_gamma_curve
        const polyFit = r.trace_data?.poly_fit

        return {
          beta_step: betaStep,
          color: getStepColor(betaStep, data.beta_steps),
          // 原始数据点
          rawData: curve
            .filter(d => d.gamma >= 1000 && d.gamma <= 1500)
            .map(d => ({
              gamma: d.gamma,
              gradient: d.gradient
            })),
          // 拟合曲线数据
          fitData: polyFit?.fit_gammas ? polyFit.fit_gammas
            .map((g: number, i: number) => ({
              gamma: g,
              gradient: polyFit.fit_grads[i]
            }))
            .filter((d: { gamma: number; gradient: number }) => d.gamma >= 1000 && d.gamma <= 1500) : [],
          optimal_gamma: r.gamma,
          fit_gamma: polyFit?.fit_gamma
        }
      })
      .sort((a, b) => a.beta_step - b.beta_step)
  }, [currentResults, data])

  // Brent优化的梯度-γ曲线数据
  const brentGradientData = useMemo(() => {
    if (!data?.brent_results) return null

    const brentResult = data.brent_results.find(r => r.offset === activeOffset)
    if (!brentResult?.trace_data?.grad_gamma_curve) return null

    const curve = brentResult.trace_data.grad_gamma_curve
    return {
      beta: brentResult.beta,
      gamma: brentResult.gamma,
      data: curve
        .filter((d: { gamma: number; gradient: number }) => d.gamma >= 1000 && d.gamma <= 1500)
        .map((d: { gamma: number; gradient: number }) => ({
          gamma: d.gamma,
          gradient: d.gradient
        }))
    }
  }, [data, activeOffset])

  // 离散γ搜索的梯度-γ曲线叠加数据
  const gradientDiscreteOverlayData = useMemo(() => {
    if (!data) return []

    return currentDiscreteResults
      .filter(r => r.trace_data?.grad_gamma_curve)
      .map(r => {
        const betaStep = r.beta_step!
        const curve = r.trace_data!.grad_gamma_curve
        const polyFit = r.trace_data?.poly_fit

        return {
          beta_step: betaStep,
          color: getStepColor(betaStep, data.beta_steps),
          // 原始数据点
          rawData: curve
            .filter(d => d.gamma >= 1000 && d.gamma <= 1500)
            .map(d => ({
              gamma: d.gamma,
              gradient: d.gradient
            })),
          // 拟合曲线数据
          fitData: polyFit?.fit_gammas ? polyFit.fit_gammas
            .map((g: number, i: number) => ({
              gamma: g,
              gradient: polyFit.fit_grads[i]
            }))
            .filter((d: { gamma: number; gradient: number }) => d.gamma >= 1000 && d.gamma <= 1500) : [],
          optimal_gamma: r.gamma,
          fit_gamma: polyFit?.fit_gamma
        }
      })
      .sort((a, b) => a.beta_step - b.beta_step)
  }, [currentDiscreteResults, data])

  // 梯度曲线显示/隐藏状态
  const [visibleGradient, setVisibleGradient] = useState<Set<number>>(new Set([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1]))
  const [showBrentGradient, setShowBrentGradient] = useState(true)

  // 离散γ搜索梯度曲线显示/隐藏状态
  const [visibleGradientDiscrete, setVisibleGradientDiscrete] = useState<Set<number>>(new Set([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1]))
  const [showBrentGradientDiscrete, setShowBrentGradientDiscrete] = useState(true)

  const toggleGradientVisibility = (step: number) => {
    setVisibleGradient(prev => {
      const newSet = new Set(prev)
      if (newSet.has(step)) {
        newSet.delete(step)
      } else {
        newSet.add(step)
      }
      return newSet
    })
  }

  const toggleAllGradient = () => {
    if (visibleGradient.size === 10) {
      setVisibleGradient(new Set())
    } else {
      setVisibleGradient(new Set([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1]))
    }
  }

  const toggleGradientDiscreteVisibility = (step: number) => {
    setVisibleGradientDiscrete(prev => {
      const newSet = new Set(prev)
      if (newSet.has(step)) {
        newSet.delete(step)
      } else {
        newSet.add(step)
      }
      return newSet
    })
  }

  const toggleAllGradientDiscrete = () => {
    if (visibleGradientDiscrete.size === 10) {
      setVisibleGradientDiscrete(new Set())
    } else {
      setVisibleGradientDiscrete(new Set([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1]))
    }
  }

  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-4 border-purple-200 border-t-purple-600 mb-4"></div>
          <p className="text-slate-600 font-bold">加载案例9数据中...</p>
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

  return (
    <div className="space-y-6">
      {/* 案例选择下拉框 */}
      {onCaseChange && caseList.length > 0 && (
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
                {caseList.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={18} />
            </div>
          </div>
        </div>
      )}

      {/* 标题 */}
      <div className="bg-gradient-to-r from-cyan-50 to-blue-50 rounded-2xl p-6 border border-cyan-200">
        <h2 className="text-xl font-bold text-slate-800 mb-2">案例9: β步长对估计结果的影响</h2>
        <p className="text-sm text-slate-600 mb-2">
          数据来源: 实际样本 (n={data.data.length}) | β步长: {data.beta_steps.join(', ')}
        </p>
        <div className="flex items-center gap-2 text-xs text-cyan-600 bg-cyan-100 px-3 py-1.5 rounded-lg w-fit">
          <Info size={14} />
          <span>研究β步长从0.01到0.1对最优β、σ-β曲线、σ_min-γ曲线和γ估计的影响</span>
        </div>
      </div>

      {/* 偏移量选择 */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex gap-1 bg-slate-100 p-1 rounded-lg w-fit">
          {OFFSET_TABS.map(tab => (
            <button
              key={tab.value}
              onClick={() => setActiveOffset(tab.value)}
              className={cn(
                "px-4 py-2 text-sm font-bold rounded-md transition-all",
                activeOffset === tab.value
                  ? "bg-white text-cyan-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* 汇总表格 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <Table2 className="text-cyan-600" size={20} />
          <h3 className="text-lg font-bold text-slate-800">汇总对比表 (δ = {activeOffset})</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b-2 border-slate-300">
                <th className="py-2 px-3 text-left font-bold text-slate-700">β步长</th>
                <th className="py-2 px-2 text-right font-bold text-slate-700">γ估计</th>
                <th className="py-2 px-2 text-right font-bold text-slate-700">β估计</th>
                <th className="py-2 px-2 text-right font-bold text-slate-700">η估计</th>
                <th className="py-2 px-2 text-right font-bold text-slate-700 text-red-500">γ误差</th>
                <th className="py-2 px-2 text-right font-bold text-slate-700 text-red-500">β误差</th>
                <th className="py-2 px-2 text-center font-bold text-slate-700">状态</th>
              </tr>
            </thead>
            <tbody>
              {currentResults.map((r, idx) => (
                <tr
                  key={idx}
                  className={cn(
                    "border-b border-slate-200 cursor-pointer hover:bg-slate-50",
                    r.beta_step === activeBetaStep && "bg-cyan-50"
                  )}
                  onClick={() => setActiveBetaStep(r.beta_step!)}
                >
                  <td className="py-2 px-3 font-medium">
                    <span
                      className="inline-block w-3 h-3 rounded-full mr-2"
                      style={{ backgroundColor: getStepColor(r.beta_step!, data.beta_steps) }}
                    />
                    {r.beta_step?.toFixed(2)}
                  </td>
                  <td className="py-2 px-2 text-right font-mono">
                    {r.gamma !== null ? r.gamma.toFixed(2) : '—'}
                  </td>
                  <td className="py-2 px-2 text-right font-mono">
                    {r.beta !== null ? r.beta.toFixed(4) : '—'}
                  </td>
                  <td className="py-2 px-2 text-right font-mono">
                    {r.eta !== null ? r.eta.toFixed(1) : '—'}
                  </td>
                  <td className="py-2 px-2 text-right font-mono text-red-500">
                    {r.gamma_error !== undefined ? r.gamma_error.toFixed(4) : '—'}
                  </td>
                  <td className="py-2 px-2 text-right font-mono text-red-500">
                    {r.beta_error !== undefined ? r.beta_error.toFixed(6) : '—'}
                  </td>
                  <td className="py-2 px-2 text-center">
                    {r.error ? (
                      <span className="inline-flex items-center gap-1 text-red-600">
                        <AlertTriangle size={14} /> 错误
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-emerald-600">
                        <CheckCircle size={14} /> 成功
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-slate-500 mt-2">误差相对于β步长=0.01的结果计算。点击行可查看对应的可视化图表。</p>
      </div>

      {/* 图表类型选择 */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex flex-wrap gap-2 mb-4">
          <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
            <button
              onClick={() => setActiveChart('error')}
              className={cn(
                "px-3 py-1.5 text-sm font-bold rounded-md transition-all",
                activeChart === 'error'
                  ? "bg-white text-red-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              误差分析
            </button>
            <button
              onClick={() => setActiveChart('sigmaBeta')}
              className={cn(
                "px-3 py-1.5 text-sm font-bold rounded-md transition-all",
                activeChart === 'sigmaBeta'
                  ? "bg-white text-blue-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              σ-β曲线
            </button>
            <button
              onClick={() => setActiveChart('sigmaMin')}
              className={cn(
                "px-3 py-1.5 text-sm font-bold rounded-md transition-all",
                activeChart === 'sigmaMin'
                  ? "bg-white text-emerald-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              σ_min(密)
            </button>
            <button
              onClick={() => setActiveChart('sigmaMinDiscrete')}
              className={cn(
                "px-3 py-1.5 text-sm font-bold rounded-md transition-all",
                activeChart === 'sigmaMinDiscrete'
                  ? "bg-white text-teal-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              σ_min(疏)
            </button>
            <button
              onClick={() => setActiveChart('gradient')}
              className={cn(
                "px-3 py-1.5 text-sm font-bold rounded-md transition-all",
                activeChart === 'gradient'
                  ? "bg-white text-purple-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              梯度曲线(密)
            </button>
            <button
              onClick={() => setActiveChart('gradientDiscrete')}
              className={cn(
                "px-3 py-1.5 text-sm font-bold rounded-md transition-all",
                activeChart === 'gradientDiscrete'
                  ? "bg-white text-orange-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              梯度曲线(疏)
            </button>
          </div>
          {/* 数据点显示开关 */}
          {activeChart !== 'error' && (
            <button
              onClick={() => setShowDataPoints(!showDataPoints)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border ml-2",
                showDataPoints
                  ? "bg-slate-100 text-slate-700 border-slate-200"
                  : "bg-white text-slate-400 border-slate-200"
              )}
            >
              {showDataPoints ? <Eye size={14} /> : <EyeOff size={14} />}
              <span>数据点</span>
            </button>
          )}
        </div>

        {/* 图1: β步长 vs 估计误差 */}
        {activeChart === 'error' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-bold text-slate-700">图1: β步长 vs 估计误差</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">
                  误差相对于β步长=0.01的结果
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-6">
              {/* β误差 */}
              <div>
                <div className="text-xs text-slate-500 mb-2 text-center">β估计误差</div>
                <div className="h-[280px]">
                  <ResponsiveContainer width="100%" height={280}>
                    <ComposedChart data={errorChartData} margin={{ top: 10, right: 20, bottom: 30, left: 50 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                      <XAxis
                        dataKey="beta_step"
                        type="number"
                        domain={[0, 0.1]}
                        tick={{ fontSize: 10 }}
                        tickFormatter={(v) => v.toFixed(2)}
                        label={{ value: 'β步长', position: 'bottom', offset: 0, fontSize: 11, fill: '#64748b' }}
                      />
                      <YAxis
                        width={45}
                        tick={{ fontSize: 10 }}
                        tickFormatter={(v) => v.toFixed(4)}
                        label={{ value: 'β误差', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#64748b' }}
                      />
                      <Tooltip
                        contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                        formatter={(v: number) => [v.toFixed(6), 'β误差']}
                        labelFormatter={(v) => `β步长: ${Number(v).toFixed(2)}`}
                      />
                      <Line
                        type="monotone"
                        dataKey="beta_error"
                        stroke="#ef4444"
                        strokeWidth={2}
                        dot={{ r: 4, fill: '#ef4444', strokeWidth: 0 }}
                        activeDot={{ r: 6, fill: '#ef4444' }}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* γ误差 */}
              <div>
                <div className="text-xs text-slate-500 mb-2 text-center">γ估计误差</div>
                <div className="h-[280px]">
                  <ResponsiveContainer width="100%" height={280}>
                    <ComposedChart data={errorChartData} margin={{ top: 10, right: 20, bottom: 30, left: 50 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                      <XAxis
                        dataKey="beta_step"
                        type="number"
                        domain={[0, 0.1]}
                        tick={{ fontSize: 10 }}
                        tickFormatter={(v) => v.toFixed(2)}
                        label={{ value: 'β步长', position: 'bottom', offset: 0, fontSize: 11, fill: '#64748b' }}
                      />
                      <YAxis
                        width={45}
                        tick={{ fontSize: 10 }}
                        tickFormatter={(v) => v.toFixed(2)}
                        label={{ value: 'γ误差', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#64748b' }}
                      />
                      <Tooltip
                        contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                        formatter={(v: number) => [v.toFixed(4), 'γ误差']}
                        labelFormatter={(v) => `β步长: ${Number(v).toFixed(2)}`}
                      />
                      <Line
                        type="monotone"
                        dataKey="gamma_error"
                        stroke="#f59e0b"
                        strokeWidth={2}
                        dot={{ r: 4, fill: '#f59e0b', strokeWidth: 0 }}
                        activeDot={{ r: 6, fill: '#f59e0b' }}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            <p className="text-xs text-slate-500">
              左图: β步长增大时，β估计误差的变化趋势。右图: β步长对γ估计误差的影响。
              <span className="text-red-500 ml-1">误差随步长增大而增大</span>，但增长速率可能非线性。
            </p>
          </div>
        )}

        {/* 图2: 多β步长的σ-β曲线叠加 */}
        {activeChart === 'sigmaBeta' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-bold text-slate-700">图2: 多 β 步长下的 σ-β 曲线叠加</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">
                  显示 {visibleSigmaBeta.size}/{sigmaBetaOverlayData.length} 条曲线
                </span>
                <button
                  onClick={toggleAllSigmaBeta}
                  className="text-xs px-2 py-1 bg-slate-100 hover:bg-slate-200 rounded-md text-slate-600 font-medium transition-colors"
                >
                  {visibleSigmaBeta.size === 10 ? '全不选' : '全选'}
                </button>
              </div>
            </div>

            {/* 曲线选择按钮 */}
            <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
              <div className="text-xs text-slate-500 mb-2">点击切换曲线显示/隐藏：</div>
              <div className="flex flex-wrap gap-2">
                {/* Brent优化曲线 */}
                {brentSigmaBetaData && (
                  <button
                    onClick={() => setShowBrentCurve(!showBrentCurve)}
                    className={cn(
                      "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all border",
                      showBrentCurve
                        ? "border-transparent shadow-sm bg-emerald-100 text-emerald-700 border-emerald-200"
                        : "border-slate-200 bg-white text-slate-400"
                    )}
                  >
                    {showBrentCurve ? <Eye size={12} /> : <EyeOff size={12} />}
                    <span>Brent优化</span>
                    <span className="w-3 h-0.5 bg-emerald-500 rounded" style={{ borderStyle: 'dashed' }} />
                  </button>
                )}
                {/* 离散搜索曲线 */}
                {sigmaBetaOverlayData.map((series) => {
                  const isVisible = visibleSigmaBeta.has(series.beta_step)
                  return (
                    <button
                      key={series.beta_step}
                      onClick={() => toggleSigmaBetaVisibility(series.beta_step)}
                      className={cn(
                        "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all border",
                        isVisible
                          ? "border-transparent shadow-sm"
                          : "border-slate-200 bg-white text-slate-400"
                      )}
                      style={isVisible ? {
                        backgroundColor: series.color + '20',
                        color: series.color,
                        borderColor: series.color + '40'
                      } : {}}
                    >
                      {isVisible ? <Eye size={12} /> : <EyeOff size={12} />}
                      <span>β步长={series.beta_step.toFixed(2)}</span>
                      <span
                        className="w-3 h-0.5 rounded"
                        style={{ backgroundColor: isVisible ? series.color : '#cbd5e1' }}
                      />
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="h-[400px] w-full">
              <ResponsiveContainer width="100%" height={400}>
                <ComposedChart margin={{ top: 10, right: 20, bottom: 40, left: 55 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis
                    type="number"
                    dataKey="beta"
                    domain={[0, 3]}
                    ticks={[0, 0.5, 1, 1.5, 2, 2.5, 3]}
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
                    formatter={(v: number, name: string) => [v?.toFixed(2) ?? 'null', name]}
                    labelFormatter={(v) => `β: ${Number(v).toFixed(2)}`}
                  />
                  {/* Brent优化曲线（黑色虚线） */}
                  {showBrentCurve && brentSigmaBetaData && (
                    <React.Fragment>
                      <Line
                        data={brentSigmaBetaData.data}
                        type="monotone"
                        dataKey="sigma"
                        stroke="#10b981"
                        strokeWidth={2.5}
                        strokeDasharray="6 3"
                        dot={false}
                        name="Brent优化"
                        isAnimationActive={false}
                      />
                      {/* 标记最优β点 */}
                      {brentSigmaBetaData.beta != null && (
                        <ReferenceLine
                          x={brentSigmaBetaData.beta}
                          stroke="#10b981"
                          strokeDasharray="3 3"
                          strokeWidth={1.5}
                          label={{ value: `β=${brentSigmaBetaData.beta.toFixed(4)}`, position: 'top', fill: '#10b981', fontSize: 10 }}
                        />
                      )}
                    </React.Fragment>
                  )}
                  {/* 离散搜索曲线 */}
                  {sigmaBetaOverlayData
                    .filter((series) => visibleSigmaBeta.has(series.beta_step))
                    .map((series, idx) => (
                    <React.Fragment key={series.beta_step}>
                      {/* 连接线 */}
                      <Line
                        data={series.data}
                        type="monotone"
                        dataKey="sigma"
                        stroke={series.color}
                        strokeWidth={2}
                        dot={false}
                        name={`β步长=${series.beta_step.toFixed(2)}`}
                        isAnimationActive={false}
                      />
                      {/* 数据点标记 */}
                      {showDataPoints && (
                        <Scatter
                          data={series.data}
                          dataKey="sigma"
                          fill={series.color}
                          stroke="#fff"
                          strokeWidth={1}
                          r={3}
                          name={`β步长=${series.beta_step.toFixed(2)} (点)`}
                          isAnimationActive={false}
                        />
                      )}
                    </React.Fragment>
                  ))}
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            {/* Brent优化结果信息 */}
            {brentSigmaBetaData && (
              <div className="bg-emerald-50 rounded-lg p-3 border border-emerald-200">
                <div className="text-xs font-bold text-emerald-700 mb-1">Brent优化结果（参考基准）：</div>
                <div className="text-xs text-emerald-600">
                  β = <span className="font-mono font-bold">{brentSigmaBetaData.beta?.toFixed(6)}</span>，
                  γ = <span className="font-mono font-bold">{brentSigmaBetaData.gamma?.toFixed(2)}</span>，
                  η = <span className="font-mono font-bold">{brentSigmaBetaData.eta?.toFixed(1)}</span>
                </div>
              </div>
            )}

            <p className="text-xs text-slate-500">
              <span className="text-emerald-500 font-medium">绿色虚线</span>为Brent优化结果（连续搜索），
              <span className="font-medium">圆点</span>标记离散搜索的β取值点。
              β步长越大，数据点越稀疏，可能偏离Brent最优解。
              β步长越大，数据点越稀疏，最低点位置可能偏移。
            </p>
          </div>
        )}

        {/* 图3: σ_min-γ曲线（密集采样） */}
        {activeChart === 'sigmaMin' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-bold text-slate-700">图3: σ_min-γ曲线（密集采样，120点）</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">
                  显示 {visibleSigmaMin.size}/{sigmaMinOverlayData.length} 条曲线
                </span>
                <button
                  onClick={toggleAllSigmaMin}
                  className="text-xs px-2 py-1 bg-slate-100 hover:bg-slate-200 rounded-md text-slate-600 font-medium transition-colors"
                >
                  {visibleSigmaMin.size === 10 ? '全不选' : '全选'}
                </button>
              </div>
            </div>

            {/* 曲线选择按钮 */}
            <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
              <div className="text-xs text-slate-500 mb-2">点击切换曲线显示/隐藏：</div>
              <div className="flex flex-wrap gap-2">
                {sigmaMinOverlayData.map((series) => {
                  const isVisible = visibleSigmaMin.has(series.beta_step)
                  return (
                    <button
                      key={series.beta_step}
                      onClick={() => toggleSigmaMinVisibility(series.beta_step)}
                      className={cn(
                        "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all border",
                        isVisible
                          ? "border-transparent shadow-sm"
                          : "border-slate-200 bg-white text-slate-400"
                      )}
                      style={isVisible ? {
                        backgroundColor: series.color + '20',
                        color: series.color,
                        borderColor: series.color + '40'
                      } : {}}
                    >
                      {isVisible ? <Eye size={12} /> : <EyeOff size={12} />}
                      <span>β步长={series.beta_step.toFixed(2)}</span>
                      <span
                        className="w-3 h-0.5 rounded"
                        style={{ backgroundColor: isVisible ? series.color : '#cbd5e1' }}
                      />
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="h-[400px] w-full">
              <ResponsiveContainer width="100%" height={400}>
                <ComposedChart margin={{ top: 10, right: 20, bottom: 40, left: 55 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis
                    type="number"
                    dataKey="gamma"
                    domain={[1000, 1500]}
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v) => v.toFixed(0)}
                    label={{ value: '位置参数 γ', position: 'bottom', offset: 0, fontSize: 11, fill: '#64748b' }}
                  />
                  <YAxis
                    width={50}
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v) => v.toFixed(0)}
                    label={{ value: '最小标准差 σ_min', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#64748b' }}
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                    formatter={(v: number, name: string) => [v?.toFixed(2) ?? 'null', name]}
                    labelFormatter={(v) => `γ: ${Number(v).toFixed(0)}`}
                  />
                  {sigmaMinOverlayData
                    .filter((series) => visibleSigmaMin.has(series.beta_step))
                    .map((series, idx) => (
                    <React.Fragment key={series.beta_step}>
                      <Line
                        data={series.data}
                        type="monotone"
                        dataKey="sigma_min"
                        stroke={series.color}
                        strokeWidth={2}
                        dot={false}
                        name={`β步长=${series.beta_step.toFixed(2)}`}
                        isAnimationActive={false}
                      />
                      {showDataPoints && (
                        <Scatter
                          data={series.data}
                          dataKey="sigma_min"
                          fill={series.color}
                          stroke="#fff"
                          strokeWidth={1}
                          r={3}
                          name={`β步长=${series.beta_step.toFixed(2)} (点)`}
                          isAnimationActive={false}
                        />
                      )}
                    </React.Fragment>
                  ))}
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            <p className="text-xs text-slate-500">
              β步长影响σ_min-γ曲线的平滑度和最低点位置。
              <span className="font-medium">圆点</span>为原始数据点（密集采样）。
            </p>
          </div>
        )}

        {/* 图6: 离散γ搜索的σ_min-γ曲线叠加 */}
        {activeChart === 'sigmaMinDiscrete' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-bold text-slate-700">图6: σ_min-γ曲线（稀疏采样，步长50）</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">
                  显示 {visibleSigmaMinDiscrete.size}/{sigmaMinDiscreteOverlayData.length} 条曲线
                </span>
                <button
                  onClick={toggleAllSigmaMinDiscrete}
                  className="text-xs px-2 py-1 bg-slate-100 hover:bg-slate-200 rounded-md text-slate-600 font-medium transition-colors"
                >
                  {visibleSigmaMinDiscrete.size === 10 ? '全不选' : '全选'}
                </button>
              </div>
            </div>

            {/* 曲线选择按钮 */}
            <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
              <div className="text-xs text-slate-500 mb-2">点击切换曲线显示/隐藏（稀疏采样：γ=1430, 1400, 1350...，步长50）：</div>
              <div className="flex flex-wrap gap-2">
                {sigmaMinDiscreteOverlayData.map((series) => {
                  const isVisible = visibleSigmaMinDiscrete.has(series.beta_step)
                  return (
                    <button
                      key={series.beta_step}
                      onClick={() => toggleSigmaMinDiscreteVisibility(series.beta_step)}
                      className={cn(
                        "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all border",
                        isVisible
                          ? "border-transparent shadow-sm"
                          : "border-slate-200 bg-white text-slate-400"
                      )}
                      style={isVisible ? {
                        backgroundColor: series.color + '20',
                        color: series.color,
                        borderColor: series.color + '40'
                      } : {}}
                    >
                      {isVisible ? <Eye size={12} /> : <EyeOff size={12} />}
                      <span>β步长={series.beta_step.toFixed(2)}</span>
                      <span
                        className="w-3 h-0.5 rounded"
                        style={{ backgroundColor: isVisible ? series.color : '#cbd5e1' }}
                      />
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="h-[400px] w-full">
              <ResponsiveContainer width="100%" height={400}>
                <ComposedChart margin={{ top: 10, right: 20, bottom: 40, left: 55 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis
                    type="number"
                    dataKey="gamma"
                    domain={[1000, 1500]}
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v) => v.toFixed(0)}
                    label={{ value: '位置参数 γ', position: 'bottom', offset: 0, fontSize: 11, fill: '#64748b' }}
                  />
                  <YAxis
                    width={50}
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v) => v.toFixed(0)}
                    label={{ value: '最小标准差 σ_min', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#64748b' }}
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                    formatter={(v: number, name: string) => [v?.toFixed(2) ?? 'null', name]}
                    labelFormatter={(v) => `γ: ${Number(v).toFixed(0)}`}
                  />
                  {sigmaMinDiscreteOverlayData
                    .filter((series) => visibleSigmaMinDiscrete.has(series.beta_step))
                    .map((series, idx) => (
                    <React.Fragment key={series.beta_step}>
                      <Line
                        data={series.data}
                        type="monotone"
                        dataKey="sigma_min"
                        stroke={series.color}
                        strokeWidth={2}
                        dot={false}
                        name={`β步长=${series.beta_step.toFixed(2)}`}
                        isAnimationActive={false}
                      />
                      {showDataPoints && (
                        <Scatter
                          data={series.data}
                          dataKey="sigma_min"
                          fill={series.color}
                          stroke="#fff"
                          strokeWidth={1}
                          r={4}
                          name={`β步长=${series.beta_step.toFixed(2)} (点)`}
                          isAnimationActive={false}
                        />
                      )}
                    </React.Fragment>
                  ))}
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            <p className="text-xs text-slate-500">
              与图3对比，采样密度降低（步长50）后，σ_min-γ曲线的细节变化可能被遗漏。
              <span className="font-medium">圆点</span>为原始数据点（稀疏采样）。
            </p>
          </div>
        )}

        {/* 图4: 梯度-γ曲线叠加 */}
        {activeChart === 'gradient' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-bold text-slate-700">图4: 梯度-γ曲线（密集采样，120点）</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">
                  显示 {visibleGradient.size}/{gradientOverlayData.length} 条曲线
                </span>
                <button
                  onClick={toggleAllGradient}
                  className="text-xs px-2 py-1 bg-slate-100 hover:bg-slate-200 rounded-md text-slate-600 font-medium transition-colors"
                >
                  {visibleGradient.size === 10 ? '全不选' : '全选'}
                </button>
              </div>
            </div>

            {/* 曲线选择按钮 */}
            <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
              <div className="text-xs text-slate-500 mb-2">点击切换曲线显示/隐藏：</div>
              <div className="flex flex-wrap gap-2">
                {/* Brent优化曲线 */}
                {brentGradientData && (
                  <button
                    onClick={() => setShowBrentGradient(!showBrentGradient)}
                    className={cn(
                      "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all border",
                      showBrentGradient
                        ? "border-transparent shadow-sm bg-emerald-100 text-emerald-700 border-emerald-200"
                        : "border-slate-200 bg-white text-slate-400"
                    )}
                  >
                    {showBrentGradient ? <Eye size={12} /> : <EyeOff size={12} />}
                    <span>Brent优化</span>
                    <span className="w-3 h-0.5 bg-emerald-500 rounded" style={{ borderStyle: 'dashed' }} />
                  </button>
                )}
                {/* 离散搜索曲线 */}
                {gradientOverlayData.map((series) => {
                  const isVisible = visibleGradient.has(series.beta_step)
                  return (
                    <button
                      key={series.beta_step}
                      onClick={() => toggleGradientVisibility(series.beta_step)}
                      className={cn(
                        "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all border",
                        isVisible
                          ? "border-transparent shadow-sm"
                          : "border-slate-200 bg-white text-slate-400"
                      )}
                      style={isVisible ? {
                        backgroundColor: series.color + '20',
                        color: series.color,
                        borderColor: series.color + '40'
                      } : {}}
                    >
                      {isVisible ? <Eye size={12} /> : <EyeOff size={12} />}
                      <span>β步长={series.beta_step.toFixed(2)}</span>
                      <span
                        className="w-3 h-0.5 rounded"
                        style={{ backgroundColor: isVisible ? series.color : '#cbd5e1' }}
                      />
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="h-[400px] w-full">
              <ResponsiveContainer width="100%" height={400}>
                <ComposedChart margin={{ top: 10, right: 20, bottom: 40, left: 55 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis
                    type="number"
                    dataKey="gamma"
                    domain={[1000, 1500]}
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v) => v.toFixed(0)}
                    label={{ value: '位置参数 γ', position: 'bottom', offset: 0, fontSize: 11, fill: '#64748b' }}
                  />
                  <YAxis
                    width={50}
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v) => v.toFixed(2)}
                    label={{ value: '梯度 ∇(γ)', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#64748b' }}
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                    formatter={(v: number, name: string) => [v?.toFixed(4) ?? 'null', name]}
                    labelFormatter={(v) => `γ: ${Number(v).toFixed(0)}`}
                  />
                  {/* 偏移量参考线 */}
                  <ReferenceLine
                    y={activeOffset}
                    stroke="#ef4444"
                    strokeDasharray="5 5"
                    strokeWidth={2}
                    label={{ value: `δ=${activeOffset}`, position: 'right', fill: '#ef4444', fontSize: 10 }}
                  />
                  {/* Brent优化曲线（绿色虚线） */}
                  {showBrentGradient && brentGradientData && (
                    <Line
                      data={brentGradientData.data}
                      type="monotone"
                      dataKey="gradient"
                      stroke="#10b981"
                      strokeWidth={2.5}
                      strokeDasharray="6 3"
                      dot={false}
                      name="Brent优化"
                      isAnimationActive={false}
                    />
                  )}
                  {/* 离散搜索：拟合曲线 + 原始散点 */}
                  {gradientOverlayData
                    .filter((series) => visibleGradient.has(series.beta_step))
                    .map((series, idx) => (
                    <React.Fragment key={series.beta_step}>
                      {/* 拟合曲线（实线） */}
                      <Line
                        data={series.fitData}
                        type="monotone"
                        dataKey="gradient"
                        stroke={series.color}
                        strokeWidth={2}
                        dot={false}
                        name={`β步长=${series.beta_step.toFixed(2)}`}
                        isAnimationActive={false}
                      />
                      {/* 原始数据点（散点） */}
                      {showDataPoints && (
                        <Scatter
                          data={series.rawData}
                          dataKey="gradient"
                          fill={series.color}
                          stroke="#fff"
                          strokeWidth={1}
                          r={3}
                          name={`β步长=${series.beta_step.toFixed(2)} (原始)`}
                          isAnimationActive={false}
                        />
                      )}
                    </React.Fragment>
                  ))}
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            <p className="text-xs text-slate-500">
              <span className="text-red-500 font-medium">红色虚线</span>为偏移量δ={activeOffset}，
              <span className="font-medium">实线</span>为三次插值拟合曲线，
              <span className="font-medium">圆点</span>为原始数据点（密集采样）。
              <span className="text-emerald-500 font-medium">绿色虚线</span>为Brent优化结果。
            </p>
          </div>
        )}

        {/* 图5: 离散γ搜索的梯度-γ曲线叠加 */}
        {activeChart === 'gradientDiscrete' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-bold text-slate-700">图5: 梯度-γ曲线（稀疏采样，步长50）</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">
                  显示 {visibleGradientDiscrete.size}/{gradientDiscreteOverlayData.length} 条曲线
                </span>
                <button
                  onClick={toggleAllGradientDiscrete}
                  className="text-xs px-2 py-1 bg-slate-100 hover:bg-slate-200 rounded-md text-slate-600 font-medium transition-colors"
                >
                  {visibleGradientDiscrete.size === 10 ? '全不选' : '全选'}
                </button>
              </div>
            </div>

            {/* 曲线选择按钮 */}
            <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
              <div className="text-xs text-slate-500 mb-2">点击切换曲线显示/隐藏（稀疏采样：γ=1430, 1400, 1350...，步长50）：</div>
              <div className="flex flex-wrap gap-2">
                {/* Brent优化曲线 */}
                {brentGradientData && (
                  <button
                    onClick={() => setShowBrentGradientDiscrete(!showBrentGradientDiscrete)}
                    className={cn(
                      "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all border",
                      showBrentGradientDiscrete
                        ? "border-transparent shadow-sm bg-emerald-100 text-emerald-700 border-emerald-200"
                        : "border-slate-200 bg-white text-slate-400"
                    )}
                  >
                    {showBrentGradientDiscrete ? <Eye size={12} /> : <EyeOff size={12} />}
                    <span>Brent优化</span>
                    <span className="w-3 h-0.5 bg-emerald-500 rounded" style={{ borderStyle: 'dashed' }} />
                  </button>
                )}
                {/* 离散搜索曲线 */}
                {gradientDiscreteOverlayData.map((series) => {
                  const isVisible = visibleGradientDiscrete.has(series.beta_step)
                  return (
                    <button
                      key={series.beta_step}
                      onClick={() => toggleGradientDiscreteVisibility(series.beta_step)}
                      className={cn(
                        "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all border",
                        isVisible
                          ? "border-transparent shadow-sm"
                          : "border-slate-200 bg-white text-slate-400"
                      )}
                      style={isVisible ? {
                        backgroundColor: series.color + '20',
                        color: series.color,
                        borderColor: series.color + '40'
                      } : {}}
                    >
                      {isVisible ? <Eye size={12} /> : <EyeOff size={12} />}
                      <span>β步长={series.beta_step.toFixed(2)}</span>
                      <span
                        className="w-3 h-0.5 rounded"
                        style={{ backgroundColor: isVisible ? series.color : '#cbd5e1' }}
                      />
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="h-[400px] w-full">
              <ResponsiveContainer width="100%" height={400}>
                <ComposedChart margin={{ top: 10, right: 20, bottom: 40, left: 55 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis
                    type="number"
                    dataKey="gamma"
                    domain={[1000, 1500]}
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v) => v.toFixed(0)}
                    label={{ value: '位置参数 γ', position: 'bottom', offset: 0, fontSize: 11, fill: '#64748b' }}
                  />
                  <YAxis
                    width={50}
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v) => v.toFixed(2)}
                    label={{ value: '梯度 ∇(γ)', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#64748b' }}
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                    formatter={(v: number, name: string) => [v?.toFixed(4) ?? 'null', name]}
                    labelFormatter={(v) => `γ: ${Number(v).toFixed(0)}`}
                  />
                  {/* 偏移量参考线 */}
                  <ReferenceLine
                    y={activeOffset}
                    stroke="#ef4444"
                    strokeDasharray="5 5"
                    strokeWidth={2}
                    label={{ value: `δ=${activeOffset}`, position: 'right', fill: '#ef4444', fontSize: 10 }}
                  />
                  {/* Brent优化曲线（绿色虚线） */}
                  {showBrentGradientDiscrete && brentGradientData && (
                    <Line
                      data={brentGradientData.data}
                      type="monotone"
                      dataKey="gradient"
                      stroke="#10b981"
                      strokeWidth={2.5}
                      strokeDasharray="6 3"
                      dot={false}
                      name="Brent优化"
                      isAnimationActive={false}
                    />
                  )}
                  {/* 离散γ搜索：拟合曲线 + 原始散点 */}
                  {gradientDiscreteOverlayData
                    .filter((series) => visibleGradientDiscrete.has(series.beta_step))
                    .map((series, idx) => (
                    <React.Fragment key={series.beta_step}>
                      {/* 拟合曲线（实线） */}
                      <Line
                        data={series.fitData}
                        type="monotone"
                        dataKey="gradient"
                        stroke={series.color}
                        strokeWidth={2}
                        dot={false}
                        name={`β步长=${series.beta_step.toFixed(2)}`}
                        isAnimationActive={false}
                      />
                      {/* 原始数据点（散点） */}
                      {showDataPoints && (
                        <Scatter
                          data={series.rawData}
                          dataKey="gradient"
                          fill={series.color}
                          stroke="#fff"
                          strokeWidth={1}
                          r={4}
                          name={`β步长=${series.beta_step.toFixed(2)} (原始)`}
                          isAnimationActive={false}
                        />
                      )}
                    </React.Fragment>
                  ))}
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            <p className="text-xs text-slate-500">
              <span className="text-red-500 font-medium">红色虚线</span>为偏移量δ={activeOffset}，
              <span className="font-medium">实线</span>为三次插值拟合曲线，
              <span className="font-medium">圆点</span>为原始数据点（稀疏采样，步长50）。
              <span className="text-emerald-500 font-medium">绿色虚线</span>为Brent优化结果。
              与图4对比可见采样密度对梯度曲线的影响。
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
