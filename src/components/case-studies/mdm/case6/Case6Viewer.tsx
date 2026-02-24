"use client"

import React, { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, ComposedChart, Scatter, AreaChart, Area
} from 'recharts'
import { BookOpen, ChevronDown, GitCommit, ArrowRight, Table2, AlertTriangle, CheckCircle, Eye, EyeOff } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Case6ViewerProps {
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
}

interface StrategyResult {
  strategy_id: string
  strategy_name: string
  offset: number
  beta: number | null
  eta: number | null
  gamma: number | null
  r2: number | null
  status: string | boolean
  trace_data?: TraceData
  error?: string
}

interface CaseData {
  source_case: string
  data: number[]
  true_params: { beta: number; eta: number; gamma: number }
  strategies: { id: string; name: string; description: string }[]
  offsets: number[]
  results: StrategyResult[]
}

const STRATEGY_TABS = [
  { id: 'iter60', name: '60次迭代', color: 'purple' },
  { id: 'iter30', name: '30次迭代', color: 'blue' },
  { id: 'iter15', name: '15次迭代', color: 'emerald' },
  { id: 'discrete', name: '离散搜索', color: 'amber' },
]

const OFFSET_TABS = [
  { value: 0.1, label: 'δ = 0.1' },
  { value: 0.15, label: 'δ = 0.15' },
]

export default function Case6Viewer({ caseId, onCaseChange }: Case6ViewerProps) {
  const [data, setData] = useState<CaseData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // 当前选中的策略和偏移量
  const [activeStrategy, setActiveStrategy] = useState('iter60')
  const [activeOffset, setActiveOffset] = useState(0.1)

  // 数据点显示开关
  const [showDataPoints, setShowDataPoints] = useState(true)

  // 加载数据
  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true)
        const res = await fetch('/case-studies/mdm/case6/data.json')
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

  // 获取当前结果
  const currentResult = data?.results.find(
    r => r.strategy_id === activeStrategy && r.offset === activeOffset
  )

  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-4 border-purple-200 border-t-purple-600 mb-4"></div>
          <p className="text-slate-600 font-bold">加载案例6数据中...</p>
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
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={18} />
            </div>
          </div>
        </div>
      )}

      {/* 标题 */}
      <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-2xl p-6 border border-indigo-200">
        <h2 className="text-xl font-bold text-slate-800 mb-2">案例6: 搜索步长对结果的影响</h2>
        <p className="text-sm text-slate-600">
          数据来源: c2案例 (n=7) | 真实参数: β={data.true_params.beta}, η={data.true_params.eta}, γ={data.true_params.gamma}
        </p>
      </div>

      {/* 汇总表格 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm max-w-3xl">
        <div className="flex items-center gap-2 mb-4">
          <Table2 className="text-purple-600" size={20} />
          <h3 className="text-lg font-bold text-slate-800">汇总对比表</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-base border-collapse">
            <thead>
              <tr className="border-b-2 border-slate-300">
                <th className="py-2 px-3 text-left font-bold text-slate-700">搜索策略</th>
                <th className="py-2 px-3 text-center font-bold text-slate-700">δ</th>
                <th className="py-2 px-3 text-right font-bold text-slate-700">γ估计</th>
                <th className="py-2 px-3 text-right font-bold text-slate-700">β估计</th>
                <th className="py-2 px-3 text-right font-bold text-slate-700">η估计</th>
                <th className="py-2 px-3 text-center font-bold text-slate-700">状态</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((r, idx) => (
                <tr
                  key={idx}
                  className={cn(
                    "border-b border-slate-200 cursor-pointer hover:bg-slate-50",
                    r.strategy_id === activeStrategy && r.offset === activeOffset && "bg-indigo-50"
                  )}
                  onClick={() => {
                    setActiveStrategy(r.strategy_id)
                    setActiveOffset(r.offset)
                  }}
                >
                  <td className="py-2 px-3 font-medium">{r.strategy_name}</td>
                  <td className="py-2 px-3 text-center font-mono">{r.offset}</td>
                  <td className="py-2 px-3 text-right font-mono">
                    {r.gamma !== null ? r.gamma.toFixed(1) : '—'}
                  </td>
                  <td className="py-2 px-3 text-right font-mono">
                    {r.beta !== null ? r.beta.toFixed(4) : '—'}
                  </td>
                  <td className="py-2 px-3 text-right font-mono">
                    {r.eta !== null ? r.eta.toFixed(1) : '—'}
                  </td>
                  <td className="py-2 px-3 text-center">
                    {r.status === 'no_intersection' ? (
                      <span className="inline-flex items-center gap-1 text-amber-600">
                        <AlertTriangle size={14} /> 无交点
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
        <p className="text-xs text-slate-500 mt-2">点击行可查看对应的可视化图表</p>
      </div>

      {/* Tab 选择器 */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex flex-wrap gap-2 mb-4">
          {/* 策略 Tab */}
          <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
            {STRATEGY_TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveStrategy(tab.id)}
                className={cn(
                  "px-3 py-1.5 text-sm font-bold rounded-md transition-all",
                  activeStrategy === tab.id
                    ? `bg-white text-${tab.color}-600 shadow-sm`
                    : "text-slate-500 hover:text-slate-700"
                )}
              >
                {tab.name}
              </button>
            ))}
          </div>

          {/* 偏移量 Tab */}
          <div className="flex gap-1 bg-slate-100 p-1 rounded-lg ml-auto">
            {OFFSET_TABS.map(tab => (
              <button
                key={tab.value}
                onClick={() => setActiveOffset(tab.value)}
                className={cn(
                  "px-3 py-1.5 text-sm font-bold rounded-md transition-all",
                  activeOffset === tab.value
                    ? "bg-white text-purple-600 shadow-sm"
                    : "text-slate-500 hover:text-slate-700"
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* 当前结果标题 */}
        <div className="flex items-center gap-3 mb-4">
          <div className="bg-indigo-100 p-2 rounded-lg text-indigo-600">
            <GitCommit size={20} />
          </div>
          <div>
            <h4 className="font-bold text-slate-800">
              {currentResult?.strategy_name} | δ = {currentResult?.offset}
            </h4>
            <p className="text-sm text-slate-500">
              {currentResult?.status === 'no_intersection'
                ? '该策略未找到梯度曲线与偏移值的交点'
                : `找到交点: γ = ${currentResult?.gamma?.toFixed(2)}, β = ${currentResult?.beta?.toFixed(4)}`
              }
            </p>
          </div>
        </div>

        {/* 图表区域 */}
        {currentResult?.trace_data ? (
          <ChartsDisplay traceData={currentResult.trace_data} showDataPoints={showDataPoints} setShowDataPoints={setShowDataPoints} />
        ) : (
          <div className="h-40 bg-amber-50 rounded-xl border border-amber-200 flex items-center justify-center text-amber-700">
            <AlertTriangle className="mr-2" size={20} />
            该策略未找到有效结果
          </div>
        )}
      </div>
    </div>
  )
}

// 图表显示组件（复制自 MDMIterationViewer）
function ChartsDisplay({ traceData, showDataPoints, setShowDataPoints }: { traceData: TraceData; showDataPoints: boolean; setShowDataPoints: (v: boolean) => void }) {
  const [activeIndex, setActiveIndex] = useState(0)

  useEffect(() => {
    if (traceData.grad_gamma_curve) {
      const idx = traceData.grad_gamma_curve.findIndex(
        d => Math.abs(d.gamma - traceData.optimal_gamma) < 1
      )
      setActiveIndex(idx >= 0 ? idx : Math.floor(traceData.grad_gamma_curve.length / 2))
    }
  }, [traceData.optimal_gamma, traceData.grad_gamma_curve])

  const activePoint = traceData.grad_gamma_curve[activeIndex] || traceData.grad_gamma_curve[0]
  const activeGamma = activePoint?.gamma || 0

  // 找到最近的 sigma_beta_gamma 切片
  const sliceData = useMemo(() => {
    if (!traceData.sigma_beta_gamma) return null
    let minDiff = Infinity
    let closestSlice = traceData.sigma_beta_gamma[0]
    for (const slice of traceData.sigma_beta_gamma) {
      const diff = Math.abs(slice.gamma - activeGamma)
      if (diff < minDiff) {
        minDiff = diff
        closestSlice = slice
      }
    }
    return closestSlice.betas.map((beta, i) => ({
      beta,
      sigma: closestSlice.sigmas[i]
    })).filter(d => d.sigma <= 1400)
  }, [traceData.sigma_beta_gamma, activeGamma])

  // 梯度图数据
  const gradientData = traceData.grad_gamma_curve.map((d, i) => ({
    ...d,
    index: i,
    isOptimal: Math.abs(d.gamma - traceData.optimal_gamma) < 1
  }))

  const handleMouseMove = (state: any) => {
    if (state.activeTooltipIndex !== undefined) {
      setActiveIndex(state.activeTooltipIndex)
    }
  }

  // 计算梯度范围
  const gradients = traceData.grad_gamma_curve.map(d => d.gradient)
  const gradientMin = Math.min(...gradients)
  const gradientMax = Math.max(...gradients)
  const yMin = Math.min(gradientMin * 1.1, traceData.target_offset * 0.9)
  const yMax = Math.max(gradientMax * 1.1, traceData.target_offset * 1.2)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
      {/* 数据点显示开关 */}
      <div className="col-span-full flex justify-end">
        <button
          onClick={() => setShowDataPoints(!showDataPoints)}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border",
            showDataPoints
              ? "bg-slate-100 text-slate-700 border-slate-200"
              : "bg-white text-slate-400 border-slate-200"
          )}
        >
          {showDataPoints ? <Eye size={14} /> : <EyeOff size={14} />}
          <span>数据点</span>
        </button>
      </div>
      {/* 图1: 梯度-γ 曲线 */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-bold text-slate-700">梯度 vs γ 曲线</span>
          <span className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded-md font-mono">
            δ = {traceData.target_offset}
          </span>
        </div>
        <div className="h-[280px] w-full relative">
          <ResponsiveContainer width="100%" height={280}>
            <LineChart
              data={gradientData}
              margin={{ top: 10, right: 40, bottom: 30, left: 50 }}
              onMouseMove={handleMouseMove}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
              <XAxis
                dataKey="gamma"
                type="number"
                domain={['auto', 'auto']}
                tick={{ fontSize: 10 }}
                tickFormatter={(v) => v.toFixed(0)}
                label={{ value: '位置参数 γ', position: 'bottom', offset: 0, fontSize: 11, fill: '#64748b' }}
              />
              <YAxis
                width={45}
                tick={{ fontSize: 10 }}
                domain={['auto', 'auto']}
                tickFormatter={(v) => v.toFixed(2)}
                label={{ value: '梯度', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#64748b' }}
              />
              <Tooltip
                contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                labelFormatter={(v) => `γ: ${Number(v).toFixed(1)}`}
                formatter={(v: number) => [v.toFixed(4), '梯度']}
              />
              <Line
                type="monotone"
                dataKey="gradient"
                stroke="#8b5cf6"
                strokeWidth={2}
                dot={{ r: 3, fill: '#8b5cf6', strokeWidth: 0 }}
                activeDot={{ r: 5, fill: '#8b5cf6' }}
              />
              {/* 偏移值参考线 */}
              <ReferenceLine
                y={traceData.target_offset}
                stroke="#ef4444"
                strokeWidth={2}
                strokeDasharray="5 5"
                label={{ value: `δ=${traceData.target_offset}`, position: 'right', fill: '#ef4444', fontSize: 10 }}
              />
              {/* 最优γ参考线（竖线） */}
              <ReferenceLine
                x={traceData.optimal_gamma}
                stroke="#3b82f6"
                strokeWidth={2}
                strokeDasharray="5 5"
                label={{ value: `γ*=${traceData.optimal_gamma?.toFixed(0)}`, position: 'top', fill: '#3b82f6', fontSize: 10 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="text-xs text-slate-500 mt-2">
          梯度曲线与偏移值δ的交点即为最优γ。蓝色虚线标示找到的最优位置：γ={traceData.optimal_gamma?.toFixed(2)}
        </p>
      </div>

      {/* 图2: σ vs β 曲线（当前γ下的切片） */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-bold text-slate-700">σ vs β 曲线 (γ={activeGamma.toFixed(0)})</span>
          <span className="text-xs text-emerald-600 bg-emerald-50 px-2 py-1 rounded-md font-mono">
            Best β = {activePoint?.best_beta?.toFixed(3) ?? '?'}
          </span>
        </div>
        <div className="h-[280px] w-full">
          {sliceData ? (
            <ResponsiveContainer width="100%" height={280}>
              <ComposedChart data={sliceData} margin={{ top: 10, right: 10, bottom: 30, left: 50 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="beta"
                  type="number"
                  domain={[0, 6]}
                  tick={{ fontSize: 10 }}
                  label={{ value: '形状参数 β', position: 'bottom', offset: 0, fontSize: 11, fill: '#64748b' }}
                />
                <YAxis
                  width={40}
                  tick={{ fontSize: 10 }}
                  label={{ value: '标准差 σ', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#64748b' }}
                />
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                  formatter={(v: number) => [v.toFixed(3), 'σ']}
                  labelFormatter={(v) => `β: ${Number(v).toFixed(2)}`}
                />
                <Line
                  type="monotone"
                  dataKey="sigma"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                />
                <ReferenceLine x={activePoint?.best_beta} stroke="#ef4444" strokeDasharray="3 3" />
                {showDataPoints && (
                  <Scatter
                    data={[{ beta: activePoint?.best_beta, sigma: activePoint?.sigma_min }]}
                    fill="#ef4444"
                    shape="diamond"
                  />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-300">
              暂无切片数据
            </div>
          )}
        </div>
        <p className="text-xs text-slate-500 mt-2">
          在当前γ下，通过一维搜索找到σ最小的β值。
        </p>
      </div>
    </div>
  )
}
