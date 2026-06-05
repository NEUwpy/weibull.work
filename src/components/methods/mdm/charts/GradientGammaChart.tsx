/**
 * ∇(γ) 梯度曲线图 - 位置参数梯度判据
 *
 * 复用场景：
 * - 计算过程 (interactive=true): 单曲线 + δ 滑动条调整
 * - 案例展示 (interactive=false, overlayMode=true): 多曲线叠加 + 固定 δ 参考线
 * - 纯渲染模式 (noContainer=true): 只渲染图表，不包含外框和滑动条
 *
 * 设计原则：交互组件 + 功能开关
 */
"use client"

import React, { useMemo } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Label
} from 'recharts'
import { cn } from '@/lib/utils'

// 单条曲线数据类型
export interface GradientGammaPoint {
  gamma: number
  gradient: number
  sigma_min?: number
  best_beta?: number
  best_eta?: number
}

// 曲线数据类型
export interface GradientCurveData {
  id: string | number
  data: GradientGammaPoint[]
  color?: string
  strokeWidth?: number
  name?: string
  opacity?: number
}

// γ 参考线类型
export interface GammaReferenceLine {
  gamma: number
  label: string
  color?: string
  strokeDasharray?: string
  position?: 'top' | 'bottom'
}

interface GradientGammaChartProps {
  // 数据
  curves: GradientCurveData[]
  singleCurve?: GradientGammaPoint[]  // 单曲线模式数据（兼容旧接口）

  // 功能开关
  interactive?: boolean       // 总开关，默认 false
  showDeltaSlider?: boolean   // δ 滑动条，默认 false
  overlayMode?: boolean       // 多条曲线叠加显示，默认 false

  // δ 滑动条相关（仅 interactive 模式）
  deltaOffset?: number        // 当前 δ 值
  onDeltaChange?: (delta: number) => void
  deltaRange?: [number, number]  // δ 范围，默认 [0, 0.5]
  deltaStep?: number          // δ 步进，默认 0.001

  // 最优 γ 相关（交互模式）
  optimalGamma?: number
  gammaMode?: 'optimal' | 'manual'
  currentGamma?: number       // 当前选中的 γ（手动模式）

  // 展示配置
  domain?: {
    x?: [number, number]
    y?: [number, number]
  }
  offsetReference?: number    // δ 参考线值（非交互模式）
  showZeroLine?: boolean      // 是否显示 y=0 参考线，默认 true
  gammaReferenceLines?: GammaReferenceLine[]  // 额外的 γ 参考线

  // 样式
  height?: number
  showTitle?: boolean
  title?: string
  subtitle?: string

  // 容器样式
  className?: string
  noContainer?: boolean       // 不渲染外层容器，只渲染图表
}

export function GradientGammaChart({
  curves,
  singleCurve,
  interactive = false,
  showDeltaSlider = false,
  overlayMode = false,
  deltaOffset = 0.1,
  onDeltaChange,
  deltaRange = [0, 0.5],
  deltaStep = 0.001,
  optimalGamma,
  gammaMode = 'optimal',
  currentGamma,
  domain,
  offsetReference,
  showZeroLine = true,
  gammaReferenceLines = [],
  height = 300,
  showTitle = true,
  title,
  subtitle,
  className,
  noContainer = false
}: GradientGammaChartProps) {

  // 计算显示用的曲线
  const displayCurves = useMemo(() => {
    if (overlayMode) {
      return curves
    }
    // 单曲线模式
    if (singleCurve) {
      return [{ id: 'current', data: singleCurve, color: '#ef4444', strokeWidth: 2 }]
    }
    return curves.length > 0 ? [curves[0]] : []
  }, [curves, singleCurve, overlayMode])

  // 计算坐标轴范围
  const allGammas = useMemo(() => {
    const gammas: number[] = []
    displayCurves.forEach(curve => {
      curve.data.forEach(d => {
        if (d.gamma !== null && d.gamma !== undefined) {
          gammas.push(d.gamma)
        }
      })
    })
    return gammas
  }, [displayCurves])

  const allGradients = useMemo(() => {
    const gradients: number[] = []
    displayCurves.forEach(curve => {
      curve.data.forEach(d => {
        if (d.gradient !== null && d.gradient !== undefined) {
          gradients.push(d.gradient)
        }
      })
    })
    return gradients
  }, [displayCurves])

  // 当前使用的 δ 值
  const currentDelta = interactive ? deltaOffset : (offsetReference ?? 0.2)

  // 默认域名
  const xDomain = domain?.x || (allGammas.length > 0 ? [
    Math.min(...allGammas, optimalGamma ?? Infinity) - 5,
    Math.max(...allGammas, optimalGamma ?? -Infinity) + 5
  ] : [0, 100])
  const yDomain = domain?.y || (allGradients.length > 0 ? [
    Math.min(...allGradients, currentDelta) - 0.1,
    Math.max(...allGradients, currentDelta) + 0.1
  ] : [-0.5, 1])

  // 图表渲染部分
  const chartContent = (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart
        data={displayCurves[0]?.data || []}
        margin={{ top: 20, right: 25, bottom: 45, left: 20 }}
      >
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
        <XAxis
          dataKey="gamma"
          type="number"
          domain={xDomain}
          tickFormatter={(v) => v.toFixed(0)}
          tick={{ fontSize: 10 }}
          tickLine={true}
          stroke="#000"
          strokeWidth={1}
          label={{ value: '位置参数 γ', position: 'bottom', offset: 0, fontSize: 11, fill: '#64748b' }}
          axisLine={{ stroke: '#000', strokeWidth: 1 }}
        />
        <YAxis
          width={45}
          domain={yDomain}
          tickFormatter={(v) => v.toFixed(3)}
          tick={{ fontSize: 10 }}
          tickLine={true}
          stroke="#000"
          strokeWidth={1}
          label={{ value: '梯度 ∇(γ)', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#64748b' }}
          axisLine={{ stroke: '#000', strokeWidth: 1 }}
        />
        <Tooltip
          contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
          labelFormatter={(v) => `γ: ${Number(v).toFixed(1)}`}
          formatter={(v: number, name: string) => [v.toFixed(4), name === 'gradient' ? '∇(γ)' : name]}
        />

        {/* δ 参考线 */}
        <ReferenceLine
          y={currentDelta}
          stroke="#10b981"
          strokeDasharray="3 3"
          label={{ position: 'right', value: `δ=${currentDelta.toFixed(3)}`, fill: '#10b981', fontSize: 10 }}
        />

        {/* y=0 参考线 */}
        {showZeroLine && (
          <ReferenceLine y={0} stroke="#cbd5e1" />
        )}

        {/* 最优 γ 参考线（交互模式） */}
        {interactive && optimalGamma !== undefined && Number.isFinite(optimalGamma) && (
          <ReferenceLine
            x={gammaMode === 'optimal' ? optimalGamma : (currentGamma ?? optimalGamma)}
            stroke={gammaMode === 'optimal' ? '#f59e0b' : '#3b82f6'}
            strokeDasharray="3 3"
            strokeWidth={2}
          >
            <Label
              value={gammaMode === 'optimal' ? '最优γ' : '当前'}
              position={gammaMode === 'optimal' ? 'bottom' : 'top'}
              fill={gammaMode === 'optimal' ? '#f59e0b' : '#3b82f6'}
              fontSize={9}
            />
          </ReferenceLine>
        )}

        {/* 手动模式下也显示最优 γ */}
        {interactive && gammaMode === 'manual' && optimalGamma !== undefined && currentGamma !== undefined && Math.abs(currentGamma - optimalGamma) > 1 && (
          <ReferenceLine x={optimalGamma} stroke="#f59e0b" strokeDasharray="3 3">
            <Label value="最优" position="bottom" fill="#f59e0b" fontSize={9} />
          </ReferenceLine>
        )}

        {/* 额外的 γ 参考线 */}
        {gammaReferenceLines.map((ref, idx) => (
          <ReferenceLine
            key={idx}
            x={ref.gamma}
            stroke={ref.color || '#f59e0b'}
            strokeDasharray={ref.strokeDasharray || '3 3'}
            label={{ value: ref.label, fill: ref.color || '#f59e0b', fontSize: 10, position: ref.position || 'top' }}
          />
        ))}

        {/* 曲线 */}
        {overlayMode ? (
          // 多条曲线叠加模式
          displayCurves.map((curve) => (
            <Line
              key={curve.id}
              data={curve.data}
              type="monotone"
              dataKey="gradient"
              stroke={curve.color || '#ef4444'}
              strokeWidth={curve.strokeWidth || 2}
              dot={false}
              name={curve.name || `#${curve.id}`}
              opacity={curve.opacity ?? 1}
              activeDot={{ r: 5 }}
            />
          ))
        ) : (
          // 单曲线模式
          <Line
            type="monotone"
            dataKey="gradient"
            stroke="#ef4444"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 6 }}
          />
        )}
      </LineChart>
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
              {title || '位置参数梯度判据'}
            </h4>
            {interactive && (
              <span className="text-sm font-bold text-emerald-600">
                δ = {currentDelta.toFixed(3)}
              </span>
            )}
          </div>
          {subtitle && (
            <p className="text-xs text-slate-500">{subtitle}</p>
          )}
        </div>
      )}

      {/* δ 滑动条（仅交互模式） */}
      {interactive && showDeltaSlider && (
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-slate-500">补偿阈值 δ</span>
            <span className="text-xs text-slate-400">
              范围: {deltaRange[0].toFixed(3)} - {deltaRange[1].toFixed(3)}
            </span>
          </div>
          <input
            type="range"
            min={deltaRange[0]}
            max={deltaRange[1]}
            step={deltaStep}
            value={deltaOffset}
            onChange={(e) => onDeltaChange?.(parseFloat(e.target.value))}
            className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-emerald-600"
            style={{
              background: `linear-gradient(to right, #6ee7b7 0%, #6ee7b7 ${((deltaOffset - deltaRange[0]) / (deltaRange[1] - deltaRange[0])) * 100}%, #e2e8f0 ${((deltaOffset - deltaRange[0]) / (deltaRange[1] - deltaRange[0])) * 100}%, #e2e8f0 100%)`
            }}
          />
          <div className="flex justify-between text-xs text-slate-400 mt-1">
            <span>{deltaRange[0].toFixed(3)}</span>
            <span>{deltaRange[1].toFixed(3)}</span>
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
