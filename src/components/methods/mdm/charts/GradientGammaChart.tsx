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

import React, { useCallback, useMemo, useState } from 'react'
import {
  ComposedChart,
  Scatter,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceDot,
  Label
} from 'recharts'
import { cn } from '@/lib/utils'
import { formatCalculationNumber as number } from '@/lib/calculation-trace'
import { processPlotAxes, processPlotFrame, ProcessYAxisLabel } from '@/components/shared/charts/ProcessPlot'

// 单条曲线数据类型
export interface GradientGammaPoint {
  gamma: number
  gradient: number
  sigma_min?: number
  best_beta?: number
  best_eta?: number
  source?: string
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
interface AdoptedLocation { id: number; gamma: number; selected: boolean }

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
  showPoints?: boolean        // 是否显示曲线采样点，默认 false
  gammaReferenceLines?: GammaReferenceLine[]  // 额外的 γ 参考线
  selectedPoint?: { gamma: number; gradient: number }
  calculatedPoints?: GradientGammaPoint[]
  adoptedLocations?: AdoptedLocation[]
  onSelectLocation?: (id: number) => void
  interpolation?: 'linear' | 'monotone'

  // 样式
  height?: number
  showTitle?: boolean
  title?: string
  subtitle?: string

  // 容器样式
  className?: string
  noContainer?: boolean       // 不渲染外层容器，只渲染图表
  workspacePlot?: boolean
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
  showPoints = false,
  gammaReferenceLines = [],
  selectedPoint,
  calculatedPoints = [],
  adoptedLocations = [],
  onSelectLocation,
  interpolation = 'monotone',
  height = 300,
  showTitle = true,
  title,
  subtitle,
  className,
  noContainer = false,
  workspacePlot = false,
}: GradientGammaChartProps) {
  const [hoveredPoint, setHoveredPoint] = useState<GradientGammaPoint | null>(null)
  const drawCalculatedPoint = useCallback((props: any) => <circle className="mdm-gradient-calculated-point"
    cx={props.cx} cy={props.cy} r={2.7} fill="#ef4444" stroke="#fff" strokeWidth={0.5}
    data-gamma={props.payload.gamma} data-gradient={props.payload.gradient}
    onMouseEnter={() => setHoveredPoint(props.payload)} onMouseLeave={() => setHoveredPoint(null)} />, [])

  // 计算显示用的曲线
  const displayCurves = useMemo(() => {
    const selected = overlayMode ? curves : singleCurve
      ? [{ id: 'current', data: singleCurve, color: '#ef4444', strokeWidth: 2 }]
      : curves.length > 0 ? [curves[0]] : []
    return domain?.x ? selected.map(curve => ({ ...curve,
      data: curve.data.filter(point => point.gamma >= domain.x![0] && point.gamma <= domain.x![1]) })) : selected
  }, [curves, singleCurve, overlayMode, domain?.x])
  const visibleCalculatedPoints = domain?.x
    ? calculatedPoints.filter(point => point.gamma >= domain.x![0] && point.gamma <= domain.x![1])
    : calculatedPoints

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

  const gradientPointDot = showPoints
    ? (props: any) => {
        if (props.payload?.source && props.payload.source !== 'trace_grid') {
          return <g />
        }
        return (
          <circle
            className="mdm-gradient-sample-point"
            cx={props.cx}
            cy={props.cy}
            r={2.5}
            fill="#fff"
            stroke={props.stroke || '#ef4444'}
            strokeWidth={1.5}
          />
        )
      }
    : false

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
    <ResponsiveContainer width="100%" height={workspacePlot ? '100%' : height}>
      <ComposedChart
        data={displayCurves[0]?.data || []}
        margin={workspacePlot ? processPlotAxes.margin : { top: 20, right: 25, bottom: 45, left: 20 }}
      >
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
        <XAxis
          dataKey="gamma"
          height={workspacePlot ? processPlotAxes.xAxisHeight : undefined}
          type="number"
          domain={xDomain}
          allowDataOverflow={!!domain?.x}
          tickFormatter={(v) => v.toFixed(0)}
          tick={{ fontSize: 14 }}
          tickLine={true}
          stroke="#000"
          strokeWidth={1}
          label={{ value: '位置参数 γ', position: 'bottom', offset: 8, fontSize: 14, fill: '#64748b' }}
          axisLine={{ stroke: '#000', strokeWidth: 1 }}
        />
        <YAxis
          dataKey="gradient"
          width={workspacePlot ? processPlotAxes.yAxisWidth : 68}
          domain={yDomain}
          allowDataOverflow={!!domain?.y}
          tickFormatter={(v) => v.toFixed(3)}
          tick={{ fontSize: 14 }}
          tickLine={true}
          stroke="#000"
          strokeWidth={1}
          label={{ value: '梯度 ∇(γ)', content: workspacePlot ? <ProcessYAxisLabel /> : undefined,
            angle: -90, position: 'insideLeft', fontSize: 14, fill: '#64748b' }}
          axisLine={{ stroke: '#000', strokeWidth: 1 }}
        />
        <Tooltip content={({ active, payload, label }) => {
          const entry = payload?.find(item => item.name === '本次求解计算点') ?? payload?.find(item => item.name !== '采纳位置')
          const point = hoveredPoint ?? displayCurves[0]?.data.find(point => point.gamma === label) ?? entry?.payload
          if ((!active && !hoveredPoint) || !Number.isFinite(point?.gamma) || !Number.isFinite(point?.gradient)) return null
          const actual = !!hoveredPoint || entry?.name === '本次求解计算点' || ['trace_grid', 'solver_root', 'solver_evaluation'].includes(point.source)
          return <div className="rounded-xl border border-slate-200 bg-white/95 p-3 text-sm shadow-sm">
            <p>{actual ? '本次求解计算点' : '函数计算值'}</p>
            <p>γ = {number(point.gamma)}，g(γ) = {number(point.gradient)}</p>
            {typeof point.evaluation === 'number' && <p>求根求值序号：{point.evaluation}</p>}
          </div>
        }} />

        {/* δ 参考线 */}
        <ReferenceLine
          y={currentDelta}
          stroke="#10b981"
          strokeDasharray="3 3"
          label={{ position: 'insideTopRight', value: `δ=${currentDelta.toFixed(3)}`, fill: '#10b981', fontSize: 14 }}
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
            label={{ value: ref.label, fill: ref.color || '#f59e0b', fontSize: 14, position: ref.position || 'top' }}
          />
        ))}

        {selectedPoint && Math.abs(selectedPoint.gradient-currentDelta) > 1e-10 && <ReferenceLine y={selectedPoint.gradient}
          stroke="#b7791f" strokeDasharray="4 4" ifOverflow="extendDomain" />}
        {/* 曲线 */}
        {overlayMode ? (
          // 多条曲线叠加模式
          displayCurves.map((curve) => (
            <Line
              key={curve.id}
              data={curve.data}
              type={interpolation}
              dataKey="gradient"
              stroke={curve.color || '#ef4444'}
              strokeWidth={curve.strokeWidth || 2}
              dot={gradientPointDot}
              name={curve.name || `#${curve.id}`}
              opacity={curve.opacity ?? 1}
              activeDot={{ r: 5 }}
              isAnimationActive={false}
            />
          ))
        ) : (
          // 单曲线模式
          <Line
            type={interpolation}
            dataKey="gradient"
            stroke="#ef4444"
            strokeWidth={2}
            dot={gradientPointDot}
            activeDot={{ r: 6 }}
            isAnimationActive={false}
          />
        )}
        {!!visibleCalculatedPoints.length && <Scatter name="本次求解计算点" data={visibleCalculatedPoints} fill="#ef4444"
          shape={drawCalculatedPoint} isAnimationActive={false} />}
        {!!adoptedLocations.length && <Scatter name="采纳位置" isAnimationActive={false}
          data={adoptedLocations.map(location => ({ ...location, gradient: yDomain[0] }))}
          shape={(props: unknown) => {
            const { cx, cy, payload } = props as { cx: number; cy: number; payload: AdoptedLocation }
            return <g data-adopted-location={payload.id} onClick={() => onSelectLocation?.(payload.id)} className="cursor-pointer">
              <title>{`第 ${payload.id} 次，γ̂ = ${number(payload.gamma)}`}</title>
              <rect x={cx - 4} y={cy - 12} width={8} height={12} fill="transparent" />
              <line x1={cx} x2={cx} y1={cy} y2={cy - (payload.selected ? 12 : 7)}
                stroke={payload.selected ? '#b7791f' : '#64748b'} strokeWidth={payload.selected ? 3 : 1.5} />
            </g>
          }} />}
        {selectedPoint && <ReferenceDot x={selectedPoint.gamma} y={selectedPoint.gradient} r={5}
          fill="#b7791f" stroke="#fff" strokeWidth={2} ifOverflow="extendDomain" />}
      </ComposedChart>
    </ResponsiveContainer>
  )

  if (workspacePlot) return <div className={processPlotFrame} data-process-plot role="img" aria-label="位置参数与剖面梯度">{chartContent}</div>

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
