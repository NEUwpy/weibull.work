"use client"

import React, { useState, useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, AreaChart, Area, ComposedChart, Scatter } from 'recharts'
import { Loader2, Play, GitCommit, ArrowRight, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'

interface TraceData {
  sigma_beta_curve: { beta: number; sigma: number }[]
  grad_gamma_curve: { gamma: number; gradient: number; sigma_min: number; best_beta?: number }[]
  sigma_beta_gamma?: { gamma: number; betas: number[]; sigmas: number[] }[]
  target_offset: number
  optimal_gamma: number
  optimal_beta: number
  data?: number[]
}

interface MDMIterationViewerProps {
  traceData: TraceData
  isLoading?: boolean
  onLoadData: () => void
  hasData?: boolean
}

export default function MDMIterationViewer({
  traceData,
  isLoading = false,
  onLoadData,
  hasData = false
}: MDMIterationViewerProps) {
  // State for the currently hovered gamma index
  const [activeIndex, setActiveIndex] = useState<number>(0)

  // Update index when traceData changes or initially
  React.useEffect(() => {
    if (traceData.grad_gamma_curve) {
      const idx = traceData.grad_gamma_curve.findIndex(d => Math.abs(d.gamma - traceData.optimal_gamma) < 1)
      setActiveIndex(idx >= 0 ? idx : Math.floor(traceData.grad_gamma_curve.length / 2))
    }
  }, [traceData.optimal_gamma, traceData.grad_gamma_curve])

  // Determine active gamma from index
  const activeGammaPoint = traceData.grad_gamma_curve[activeIndex] || traceData.grad_gamma_curve[0]
  const activeGamma = activeGammaPoint.gamma

  // Find the closest slice data in sigma_beta_gamma (20 points)
  const sliceData = useMemo(() => {
    if (!hasData || !traceData.sigma_beta_gamma) return null

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
  }, [hasData, traceData.sigma_beta_gamma, activeGamma])

  // Chart 1 Data
  const pathData = traceData.grad_gamma_curve.map((d, i) => ({
    ...d,
    index: i,
    isOptimal: Math.abs(d.gamma - traceData.optimal_gamma) < 1
  }))

  const handleMouseMove = (state: any) => {
    if (state.activeTooltipIndex !== undefined) {
      setActiveIndex(state.activeTooltipIndex)
    }
  }

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm mt-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="flex items-center gap-3 mb-6">
        <div className="bg-purple-100 p-2 rounded-lg text-purple-600">
          {isLoading ? <Loader2 size={24} className="animate-spin" /> : <GitCommit size={24} />}
        </div>
        <div>
          <h3 className="text-lg font-bold text-slate-800">
            {isLoading ? "正在计算迭代数据..." : "算法迭代与收敛路径"}
          </h3>
          <p className="text-sm text-slate-500">
            {isLoading 
              ? "正在还原算法的内层优化路径" 
              : "双层嵌套循环可视化：外层遍历 γ (左图)，内层寻找最优 β (右图)。"}
          </p>
        </div>
        {!isLoading && (
          <button
            onClick={onLoadData}
            className={cn(
              "ml-auto flex items-center gap-2 px-4 py-2 rounded-lg font-bold transition-all text-sm shadow-md",
              hasData 
                ? "bg-slate-100 text-slate-600 hover:bg-slate-200 shadow-slate-200" 
                : "bg-purple-600 hover:bg-purple-700 text-white shadow-purple-200"
            )}
          >
            {hasData ? <RefreshCw size={16} /> : <Play size={16} />}
            {hasData ? "刷新数据" : "加载迭代数据"}
          </button>
        )}
      </div>

      {!hasData && !isLoading ? (
        <div className="h-40 bg-slate-50 rounded-xl border border-dashed border-slate-200 flex items-center justify-center text-slate-400 text-sm">
          点击右上方按钮加载数据以启用可视化
        </div>
      ) : isLoading ? (
        <div className="h-40 flex items-center justify-center">
          <div className="flex flex-col items-center gap-2">
            <Loader2 size={32} className="text-purple-600 animate-spin" />
            <span className="text-xs text-slate-400 font-medium">正在处理采样点数据...</span>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Chart 1: The Path (Gamma vs Sigma_min) */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-bold text-slate-700">1. 外层循环：遍历 γ</span>
              <span className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded-md font-mono">
                Current γ = {activeGamma.toFixed(1)}
              </span>
            </div>
            <div className="h-[240px] w-full relative">
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart 
                  data={pathData} 
                  margin={{ top: 10, right: 10, bottom: 20, left: 40 }}
                  onMouseMove={handleMouseMove}
                >
                  <defs>
                    <linearGradient id="colorSigma" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis 
                    dataKey="gamma" 
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v) => v.toFixed(0)}
                    label={{ value: '位置参数 γ (迭代步)', position: 'bottom', offset: 0, fontSize: 11, fill: '#64748b' }}
                  />
                  <YAxis 
                    width={35}
                    tick={{ fontSize: 10 }}
                    label={{ value: '最小标准差 σ_min', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#64748b' }}
                  />
                  <Tooltip 
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                    labelFormatter={(v) => `γ: ${Number(v).toFixed(1)}`}
                    formatter={(v: number) => [v.toFixed(3), 'σ_min']}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="sigma_min" 
                    stroke="#8b5cf6" 
                    fillOpacity={1} 
                    fill="url(#colorSigma)" 
                  />
                  <ReferenceLine x={activeGamma} stroke="#3b82f6" strokeDasharray="3 3" />
                  <Scatter data={[{ x: activeGamma, y: activeGammaPoint.sigma_min }]} fill="#3b82f6" />
                </AreaChart>
              </ResponsiveContainer>
              <div className="absolute top-2 right-2 text-[10px] text-slate-400 bg-white/80 px-2 py-1 rounded backdrop-blur-sm pointer-events-none">
                移动鼠标查看不同阶段
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-2">
              算法在搜索空间中移动，对于每一个 γ，都记录下能达到的最小标准差（沟底高度）。
            </p>
          </div>

          {/* Arrow between charts */}
          <div className="hidden lg:flex flex-col items-center justify-center pt-8 -mx-4 text-slate-300">
            <ArrowRight size={24} />
          </div>

          {/* Chart 2: The Slice (Beta vs Sigma at current Gamma) */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-bold text-slate-700">2. 内层优化：寻找 β</span>
              <span className="text-xs text-emerald-600 bg-emerald-50 px-2 py-1 rounded-md font-mono">
                Best β = {activeGammaPoint.best_beta?.toFixed(3) ?? '?'}
              </span>
            </div>
            <div className="h-[240px] w-full">
              {sliceData ? (
                <ResponsiveContainer width="100%" height={240}>
                  <ComposedChart data={sliceData} margin={{ top: 10, right: 10, bottom: 20, left: 40 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis 
                      dataKey="beta" 
                      type="number" 
                      domain={[0, 6]}
                      tick={{ fontSize: 10 }}
                      label={{ value: '形状参数 β', position: 'bottom', offset: 0, fontSize: 11, fill: '#64748b' }}
                    />
                    <YAxis 
                      width={35}
                      tick={{ fontSize: 10 }}
                      domain={[0, 'auto']}
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
                    <ReferenceLine x={activeGammaPoint.best_beta} stroke="#ef4444" strokeDasharray="3 3" />
                    <Scatter 
                      data={[{ beta: activeGammaPoint.best_beta, sigma: activeGammaPoint.sigma_min }]} 
                      fill="#ef4444" 
                      shape="diamond"
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-slate-300">
                  暂无该点切片数据
                </div>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-2">
              在当前 γ 固定时，算法通过一维搜索找到抛物线的最低点（最优 β）。
              这个最低点的高度被记录到左图中。
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
