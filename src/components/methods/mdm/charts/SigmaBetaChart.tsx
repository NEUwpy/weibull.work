/**
 * σ_η(β) 曲线图 - 形状参数寻优
 *
 * 复用场景：
 * - 计算过程 (interactive=true): 单曲线 + γ 滑动条切换
 * - 案例展示 (interactive=false, overlayMode=true): 多曲线叠加
 * - 纯渲染模式 (noContainer=true): 只渲染图表，不包含外框和滑动条
 *
 * 设计原则：交互组件 + 功能开关
 */
"use client"

import React, { useState, useMemo } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Label,
  ComposedChart
} from 'recharts'
import { RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'

// 单条曲线数据类型
export interface SigmaBetaCurvePoint {
  beta: number
  sigma: number
  source?: string
}

// 曲线数据类型
export interface CurveData {
  id: string | number
  data: SigmaBetaCurvePoint[]
  color?: string
  strokeWidth?: number
  name?: string
  opacity?: number
}

// 参考线类型
export interface ReferenceLineConfig {
  value: number
  label: string
  color?: string
  strokeDasharray?: string
}

interface SigmaBetaChartProps {
  // 数据
  curves: CurveData[]

  // 功能开关
  interactive?: boolean       // 总开关，默认 false
  showGammaSlider?: boolean   // γ 滑动条（需要 gammaData），默认 false
  showControls?: boolean      // 显示模式切换和刷新按钮，默认 true
  overlayMode?: boolean       // 多条曲线叠加显示，默认 false
  showPoints?: boolean        // 是否显示 β 网格采样点，默认 false

  // γ 滑动条相关（仅 interactive + showGammaSlider 模式）
  gammaData?: Array<{
    gamma: number
    betas: number[]
    sigmas: number[]
  }>
  optimalGamma?: number
  optimalBeta?: number
  currentGamma?: number
  currentGammaIndex?: number  // 当前 γ 索引（外部控制时使用）
  gammaDataCount?: number     // γ 数据总数（外部控制时使用）
  onGammaChange?: (gammaIndex: number) => void
  onRefresh?: () => void
  gammaMode?: 'optimal' | 'manual'
  onGammaModeChange?: (mode: 'optimal' | 'manual') => void

  // 展示配置
  yScale?: 'linear' | 'log'
  domain?: {
    x?: [number, number]
    y?: [number, number]
  }
  xTicks?: number[]
  yTicks?: number[]
  referenceLines?: ReferenceLineConfig[]

  // 样式
  height?: number
  showTitle?: boolean
  title?: string
  subtitle?: string

  // 容器样式
  className?: string
  noContainer?: boolean       // 不渲染外层容器，只渲染图表
}

export function SigmaBetaChart({
  curves,
  interactive = false,
  showGammaSlider = false,
  showControls = true,
  overlayMode = false,
  showPoints = false,
  gammaData,
  optimalGamma = 0,
  optimalBeta = 0,
  currentGamma,
  currentGammaIndex,
  gammaDataCount,
  onGammaChange,
  onRefresh,
  gammaMode = 'optimal',
  onGammaModeChange,
  yScale = 'linear',
  domain,
  xTicks = [1, 2, 3, 4, 5, 6],
  yTicks,
  referenceLines = [],
  height = 300,
  showTitle = true,
  title,
  subtitle,
  className,
  noContainer = false
}: SigmaBetaChartProps) {

  // 内部 γ 滑动条状态（仅在没有外部控制时使用）
  const [internalGammaIndex, setInternalGammaIndex] = useState(() => {
    if (gammaData && optimalGamma) {
      const idx = gammaData.findIndex(d => Math.abs(d.gamma - optimalGamma) < 5)
      return idx >= 0 ? idx : Math.floor(gammaData.length / 2)
    }
    return 0
  })

  // 使用外部或内部的 gammaIndex
  const gammaIndex = currentGammaIndex ?? internalGammaIndex
  const setGammaIndex = (idx: number) => {
    setInternalGammaIndex(idx)
    onGammaChange?.(idx)
  }

  // 使用外部或内部的 gammaDataCount
  const actualGammaDataCount = gammaDataCount ?? gammaData?.length ?? 0

  // 获取当前选中 γ 的曲线数据
  const currentCurveData = useMemo(() => {
    if (!showGammaSlider || !gammaData || gammaData.length === 0) {
      return curves[0]?.data || []
    }
    const selected = gammaData[gammaIndex]
    if (selected && selected.betas && selected.sigmas) {
      return selected.betas.map((beta: number, i: number) => ({
        beta,
        sigma: selected.sigmas[i]
      }))
    }
    return curves[0]?.data || []
  }, [showGammaSlider, gammaData, gammaIndex, curves])

  // 计算选中的 γ 值
  const selectedGamma = gammaData?.[gammaIndex]?.gamma ?? currentGamma ?? optimalGamma

  // 默认域名
  const xDomain = domain?.x || [0.5, 6]
  const yDomain = domain?.y || (yScale === 'log' ? [1, 2000] : [0, 1400])

  // 决定显示哪些曲线
  const displayCurves: CurveData[] = overlayMode
    ? curves
    : [{ id: 'current', data: currentCurveData, color: '#3b82f6', strokeWidth: 3 }]

  const shapePointDot = showPoints
    ? (props: any) => {
        if (props.payload?.source && props.payload.source !== 'trace_grid') {
          return <g />
        }
        return (
          <circle
            className="mdm-shape-sample-point"
            cx={props.cx}
            cy={props.cy}
            r={2.5}
            fill="#fff"
            stroke={props.stroke || '#3b82f6'}
            strokeWidth={1.5}
          />
        )
      }
    : false

  // 过滤有效数据点
  const filterData = (data: SigmaBetaCurvePoint[]) => {
    return data.filter(d => {
      if (d.sigma === null || d.sigma === undefined) return false
      if (yScale === 'log' && d.sigma <= 0) return false
      if (yDomain && (d.sigma < yDomain[0] || d.sigma > yDomain[1])) return false
      return true
    })
  }

  // 图表渲染部分
  const chartContent = (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart
        data={filterData(displayCurves[0]?.data || [])}
        margin={{ top: 20, right: 25, bottom: 45, left: yScale === 'log' ? 60 : 55 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis
          dataKey="beta"
          type="number"
          domain={xDomain}
          ticks={xTicks}
          tickFormatter={(v) => v.toFixed(0)}
          tick={{ fontSize: 10 }}
          tickLine={true}
          stroke="#000"
          strokeWidth={1}
          label={{ value: '形状参数 β', position: 'bottom', offset: 0, fontSize: 11, fill: '#64748b' }}
          axisLine={{ stroke: '#000', strokeWidth: 1 }}
        />
        <YAxis
          scale={yScale}
          domain={yDomain}
          ticks={yTicks || (yScale === 'log' ? [1, 10, 100, 1000] : undefined)}
          tickFormatter={(v) => yScale === 'log' ? v.toString() : v.toFixed(0)}
          tick={{ fontSize: 10 }}
          tickLine={true}
          stroke="#000"
          strokeWidth={1}
          label={{
            value: yScale === 'log' ? '标准差 σ_η (对数)' : '标准差 σ_η',
            angle: -90,
            position: 'insideLeft',
            fontSize: 11,
            fill: '#64748b'
          }}
          axisLine={{ stroke: '#000', strokeWidth: 1 }}
        />
        <Tooltip
          contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
          labelFormatter={(v) => `β: ${Number(v).toFixed(2)}`}
          formatter={(v: number, name: string) => [v.toFixed(2), name]}
        />

        {/* 参考线 */}
        {referenceLines.map((ref, idx) => (
          <ReferenceLine
            key={idx}
            x={ref.value}
            stroke={ref.color || '#94a3b8'}
            strokeDasharray={ref.strokeDasharray || '3 3'}
            label={{ value: ref.label, fill: ref.color || '#94a3b8', fontSize: 10 }}
          />
        ))}

        {/* 最优 β 参考线（交互模式） */}
        {interactive && optimalBeta > 0 && (
          <ReferenceLine
            x={optimalBeta}
            stroke="#f59e0b"
            strokeWidth={2}
            strokeDasharray="5 5"
            label={{ value: `最优 β: ${optimalBeta.toFixed(2)}`, position: 'top', fill: '#f59e0b', fontSize: 10 }}
          />
        )}

        {/* 曲线 */}
        {overlayMode ? (
          // 多条曲线叠加模式
          displayCurves.map((curve) => (
            <Line
              key={curve.id}
              data={filterData(curve.data)}
              type="monotone"
              dataKey="sigma"
              stroke={curve.color || '#3b82f6'}
              strokeWidth={curve.strokeWidth || 2}
              dot={shapePointDot}
              name={curve.name || `#${curve.id}`}
              opacity={curve.opacity ?? 1}
              activeDot={{ r: 5 }}
            />
          ))
        ) : (
          // 单曲线模式
          <Line
            type="monotone"
            dataKey="sigma"
            stroke="#3b82f6"
            strokeWidth={3}
            dot={shapePointDot}
            activeDot={{ r: 6 }}
          />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  )

  // noContainer 模式：只返回图表
  if (noContainer) {
    return (
      <div className={className} style={{ height: `${height}px` }}>
        {chartContent}
      </div>
    )
  }

  // 完整模式：包含容器、标题、滑动条、图表
  return (
    <div className={cn("bg-white rounded-2xl border border-slate-200 p-6", className)}>
      {/* 标题区 */}
      {showTitle && (
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-base font-bold text-slate-800">
              {title || '形状参数寻优'}
            </h4>
            {interactive && (
              <div className="flex items-center gap-2">
                {/* Gamma Mode Switch */}
                {showControls && onGammaModeChange && (
                  <div className="flex bg-slate-100 p-0.5 rounded-full border border-slate-200">
                    <button
                      onClick={() => onGammaModeChange('optimal')}
                      className={cn(
                        "px-2.5 py-0.5 rounded-full text-xs font-black",
                        gammaMode === 'optimal'
                          ? "bg-white text-blue-600 shadow-sm"
                          : "text-slate-400 hover:text-slate-600"
                      )}
                    >
                      最优γ
                    </button>
                    <button
                      onClick={() => onGammaModeChange('manual')}
                      className={cn(
                        "px-2.5 py-0.5 rounded-full text-xs font-black",
                        gammaMode === 'manual'
                          ? "bg-white text-emerald-600 shadow-sm"
                          : "text-slate-400 hover:text-slate-600"
                      )}
                    >
                      更改γ
                    </button>
                  </div>
                )}
                {/* Refresh button */}
                {showControls && gammaMode === 'optimal' && onRefresh && (
                  <button
                    onClick={(e) => { e.preventDefault(); onRefresh(); }}
                    className="p-1.5 rounded-lg text-blue-600 hover:bg-blue-50"
                    title="刷新曲线"
                  >
                    <RefreshCw size={16} />
                  </button>
                )}
                <span className="text-sm font-bold text-blue-600">
                  γ = {selectedGamma.toFixed(2)}
                </span>
              </div>
            )}
          </div>
          {subtitle && (
            <p className="text-xs text-slate-500">{subtitle}</p>
          )}
        </div>
      )}

      {/* γ 滑动条（仅交互模式） */}
      {interactive && showGammaSlider && gammaData && gammaData.length > 0 && (
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-slate-500">位置参数 γ</span>
            <span className="text-xs text-slate-400">
              {gammaIndex + 1} / {actualGammaDataCount}
              {gammaMode === 'optimal' && <span className="text-blue-600 ml-1">(自动)</span>}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={actualGammaDataCount - 1}
            step={1}
            value={gammaIndex}
            onChange={(e) => setGammaIndex(parseInt(e.target.value))}
            disabled={gammaMode === 'optimal'}
            className={cn(
              "w-full h-2 rounded-lg appearance-none cursor-pointer transition-all",
              gammaMode === 'optimal'
                ? "bg-slate-100 cursor-not-allowed"
                : "bg-slate-200 accent-blue-600"
            )}
            style={{
              background: gammaMode === 'optimal'
                ? '#e2e8f0'
                : `linear-gradient(to right, #93c5fd 0%, #93c5fd ${(gammaIndex / (actualGammaDataCount - 1)) * 100}%, #e2e8f0 ${(gammaIndex / (actualGammaDataCount - 1)) * 100}%, #e2e8f0 100%)`
            }}
          />
          <div className="flex justify-between text-xs text-slate-400 mt-1">
            <span>{gammaData[0]?.gamma.toFixed(1) ?? '-'}</span>
            <span>{gammaData[gammaData.length - 1]?.gamma.toFixed(1) ?? '-'}</span>
          </div>
        </div>
      )}

      {/* 图表区域 */}
      <div style={{ height: `${height}px` }}>
        {chartContent}
      </div>
    </div>
  )
}
