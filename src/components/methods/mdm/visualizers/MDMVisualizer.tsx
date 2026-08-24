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
  Legend,
  Brush,
  ComposedChart,
  Area
} from 'recharts'
import { RefreshCw } from 'lucide-react'
import MDM3DSurfaceVisualizer from './MDM3DSurfaceVisualizer'
import { getApiBaseUrl } from '@/lib/config'
import MDMOffsetAnalyzer from './MDMOffsetAnalyzer'
import MDMIterationViewer from './MDMIterationViewer'
import { cn } from '@/lib/utils'
import { DataSource, MULTI_CURVE_COLORS } from '@/lib/weibull'
import { MDM_OFFSET_GRID, MDM_OFFSET_MAX, MDM_OFFSET_MIN, MDM_OFFSET_STEP } from '@/lib/calculator-state'

// 导入MDM图表组件
import { SigmaBetaChart, GradientGammaChart } from '../charts'

// 开关：使用新组件（true）或旧代码（false）
const USE_NEW_CHART_COMPONENTS = true

interface TraceData {
  sigma_beta_curve: { beta: number; sigma: number; source?: string }[]
  grad_gamma_curve: { gamma: number; gradient: number; sigma_min: number; best_beta?: number; best_eta?: number; source?: string }[]
  sigma_beta_gamma?: { gamma: number; betas: number[]; sigmas: number[] }[]
  target_offset: number
  optimal_gamma: number
  optimal_beta: number
  solution_strategy?: string
  constraint?: string
  probe_gradient_at_zero?: number
  root_bracket?: {
    left: { gamma: number; gradient: number; diff?: number }
    right: { gamma: number; gradient: number; diff?: number; virtual?: boolean }
  } | null
  root_solver?: string | null
  right_edge_extrapolation?: {
    gamma: number
    anchor_gradient: number
    virtual_gradient: number
    model: string
  } | null
  data?: number[]  // Original data for 3D surface calculation
}

interface MDMVisualizerProps {
  traceData: TraceData
  methodId?: string  // For API calls
  dataSources?: DataSource[]  // 多选数据源，用于叠加显示
  mdmOffset: number
  onMdmOffsetChange: (offset: number) => void
  offsetStale?: boolean
  isOffsetUpdating?: boolean
}

function previewGammaForOffset(traceData: TraceData, offset: number): number {
  const points = traceData.grad_gamma_curve.filter(point => (
    Number.isFinite(point.gamma) && Number.isFinite(point.gradient)
  ))
  if (points.length === 0) return traceData.optimal_gamma ?? 0

  const zeroPoint = points.reduce((closest, point) => (
    Math.abs(point.gamma) < Math.abs(closest.gamma) ? point : closest
  ), points[0])
  if (zeroPoint.gradient >= offset) return 0

  const byGradient = [...points].sort((a, b) => a.gradient - b.gradient)
  if (offset <= byGradient[0].gradient) return byGradient[0].gamma
  if (offset >= byGradient[byGradient.length - 1].gradient) return byGradient[byGradient.length - 1].gamma

  for (let index = 0; index < byGradient.length - 1; index++) {
    const left = byGradient[index]
    const right = byGradient[index + 1]
    if (left.gradient <= offset && right.gradient >= offset) {
      const gradientSpan = right.gradient - left.gradient
      if (Math.abs(gradientSpan) < Number.EPSILON) return left.gamma
      const ratio = (offset - left.gradient) / gradientSpan
      return left.gamma + ratio * (right.gamma - left.gamma)
    }
  }

  return traceData.optimal_gamma ?? 0
}

export default function MDMVisualizer({
  traceData,
  methodId = 'mdm',
  dataSources,
  mdmOffset,
  onMdmOffsetChange,
  offsetStale = false,
  isOffsetUpdating = false,
}: MDMVisualizerProps) {
  const [activeScheme, setActiveScheme] = useState<'original' | '3d' | 'offset'>('original')
  const [surfaceData, setSurfaceData] = useState<TraceData | null>(null)
  const [isLoadingSurface, setIsLoadingSurface] = useState(false)
  const [loadingProgress, setLoadingProgress] = useState(0)
  const [showShapePoints, setShowShapePoints] = useState(false)
  const [showGradientPoints, setShowGradientPoints] = useState(false)

  // Gamma mode: 'optimal' (auto from delta) or 'manual' (user controlled)
  const [gammaMode, setGammaMode] = useState<'optimal' | 'manual'>('optimal')

  // The calculator card and criterion chart share this single page-level value.
  const deltaOffset = mdmOffset
  const gradientSamplePointCount = traceData.grad_gamma_curve?.filter(
    point => !point.source || point.source === 'trace_grid'
  ).length ?? 0

  // Gamma used for the left chart curve. In optimal mode it follows the linked delta.
  const [chartGamma, setChartGamma] = useState(() => {
    return traceData.optimal_gamma ?? 0
  })

  // Gamma slider state for original view (shape parameter optimization)
  const [gammaIndex, setGammaIndex] = useState(() => {
    // Prefer sigma_beta_gamma (20 points) if available, otherwise use grad_gamma_curve (60 points)
    if (traceData.sigma_beta_gamma && traceData.sigma_beta_gamma.length > 0) {
      const optimalIdx = traceData.sigma_beta_gamma.findIndex(
        d => Math.abs(d.gamma - traceData.optimal_gamma) < 5
      )
      return optimalIdx >= 0 ? optimalIdx : Math.floor(traceData.sigma_beta_gamma.length / 2)
    } else if (traceData.grad_gamma_curve && traceData.grad_gamma_curve.length > 0) {
      const optimalIdx = traceData.grad_gamma_curve.findIndex(
        d => Math.abs(d.gamma - traceData.optimal_gamma) < 1
      )
      return optimalIdx >= 0 ? optimalIdx : Math.floor(traceData.grad_gamma_curve.length / 2)
    }
    return 0
  })

  if (!traceData) return null

  // Determine which data source to use for the slider
  const useSigmaBetaGamma = traceData.sigma_beta_gamma && traceData.sigma_beta_gamma.length > 0
  const gammaDataCount = useSigmaBetaGamma 
    ? traceData.sigma_beta_gamma!.length 
    : (traceData.grad_gamma_curve?.length || 0)

  // Reuse the offset-independent g(gamma) trace for an immediate crossing preview.
  // The backend then replaces it with the exact constrained/Brent result.
  const optimalGammaFromDelta = useMemo(() => {
    return offsetStale
      ? previewGammaForOffset(traceData, deltaOffset)
      : (traceData.optimal_gamma ?? 0)
  }, [deltaOffset, offsetStale, traceData])

  // Get the currently selected gamma data for left chart
  // In optimal mode: use chartGamma (kept in sync with the linked delta)
  // In manual mode: use gammaIndex (follows slider)
  const getClosestGammaIndex = (targetGamma: number) => {
    if (useSigmaBetaGamma) {
      // 找到差值最小的索引
      if (!traceData.sigma_beta_gamma) return 0
      let minDiff = Infinity
      let minIdx = 0
      for (let i = 0; i < traceData.sigma_beta_gamma.length; i++) {
        const diff = Math.abs(traceData.sigma_beta_gamma[i].gamma - targetGamma)
        if (diff < minDiff) {
          minDiff = diff
          minIdx = i
        }
      }
      return minIdx
    } else {
      // 同理处理 grad_gamma_curve
      if (!traceData.grad_gamma_curve) return 0
      let minDiff = Infinity
      let minIdx = 0
      for (let i = 0; i < traceData.grad_gamma_curve.length; i++) {
        const diff = Math.abs(traceData.grad_gamma_curve[i].gamma - targetGamma)
        if (diff < minDiff) {
          minDiff = diff
          minIdx = i
        }
      }
      return minIdx
    }
  }

  // Determine which gamma index to use for left chart
  const effectiveGammaIndex = gammaMode === 'optimal'
    ? getClosestGammaIndex(chartGamma)
    : gammaIndex

  const selectedGammaData = useSigmaBetaGamma
    ? traceData.sigma_beta_gamma?.[effectiveGammaIndex]
    : traceData.grad_gamma_curve?.[effectiveGammaIndex]
  const selectedGamma = selectedGammaData?.gamma ?? traceData.optimal_gamma ?? 0

  // Handle refresh button click - update chartGamma to current optimalGammaFromDelta
  const handleRefreshChart = () => {
    setChartGamma(optimalGammaFromDelta)
  }

  // Changing delta should move both the criterion marker and the shape-profile
  // chart immediately; the exact backend result will replace this preview.
  React.useEffect(() => {
    if (gammaMode === 'optimal') {
      setChartGamma(optimalGammaFromDelta)
    }
  }, [gammaMode, optimalGammaFromDelta])

  // When switching to manual mode, sync chartGamma with current slider position
  React.useEffect(() => {
    if (gammaMode === 'manual') {
      const currentGamma = useSigmaBetaGamma
        ? traceData.sigma_beta_gamma![gammaIndex]?.gamma
        : traceData.grad_gamma_curve[gammaIndex]?.gamma
      if (currentGamma !== undefined) {
        setChartGamma(currentGamma)
      }
    }
  }, [gammaMode])

  // Generate sigma(beta) curve for the selected gamma
  const currentSigmaBetaCurve = useSigmaBetaGamma && selectedGammaData && 'betas' in selectedGammaData
    ? selectedGammaData.betas.map((beta: number, i: number) => ({
        beta,
        sigma: selectedGammaData.sigmas[i],
        source: 'trace_grid'
      }))
    : (traceData.sigma_beta_curve || []).map(point => ({ ...point, source: point.source || 'trace_grid' }))

  // Extend data to cover beta=1 to 6 if not already covered
  const extendedSigmaBetaCurve = useMemo(() => {
    if (!currentSigmaBetaCurve || currentSigmaBetaCurve.length === 0) return []
    const existingBetas = new Set(currentSigmaBetaCurve.map(d => d.beta))
    const extended = [...currentSigmaBetaCurve]

    // Add missing beta values (1-6) with extrapolated sigma values
    for (let beta = 1; beta <= 6; beta++) {
      if (!existingBetas.has(beta)) {
        // Find nearest existing data point to extrapolate
        const nearest = currentSigmaBetaCurve.reduce((prev, curr) =>
          Math.abs(curr.beta - beta) < Math.abs(prev.beta - beta) ? curr : prev
        )
        // Simple extrapolation: use nearest value (could be improved with linear interpolation)
        extended.push({ beta, sigma: nearest.sigma * 1.05, source: 'display_extension' }) // slight increase for extrapolation
        // Sort by beta
        extended.sort((a, b) => a.beta - b.beta)
      }
    }

    return extended
  }, [currentSigmaBetaCurve])

  // Filter data to only show sigma values within 0-1400 range
  const filteredSigmaBetaCurve = extendedSigmaBetaCurve
    .filter(d => d.sigma >= 0 && d.sigma <= 1400)
  const shapeSamplePointCount = currentSigmaBetaCurve
    .filter(d => d.sigma >= 0 && d.sigma <= 1400 && (!d.source || d.source === 'trace_grid'))
    .length

  // 准备多曲线数据（用于叠加显示多组样本的寻优过程）
  const allSigmaBetaCurves = useMemo(() => {
    // 如果有多数据源，直接使用 dataSources 中的数据
    if (dataSources && dataSources.length > 0) {
      return dataSources
        .filter(ds => ds.traceData?.sigma_beta_curve)
        .map((ds, index) => ({
          id: ds.id,
          data: ds.traceData.sigma_beta_curve.filter((d: { sigma: number }) => d.sigma >= 0 && d.sigma <= 1400),
          color: ds.color || MULTI_CURVE_COLORS[index % MULTI_CURVE_COLORS.length]
        }))
    }

    // 单数据源模式：使用当前 traceData
    return [{ id: 'current', data: filteredSigmaBetaCurve, color: '#3b82f6' }]
  }, [filteredSigmaBetaCurve, dataSources])

  // 准备多曲线梯度数据
  const allGradientGammaCurves = useMemo(() => {
    // 如果有多数据源，直接使用 dataSources 中的数据
    if (dataSources && dataSources.length > 0) {
      return dataSources
        .filter(ds => ds.traceData?.grad_gamma_curve)
        .map((ds, index) => ({
          id: ds.id,
          data: ds.traceData.grad_gamma_curve,
          color: ds.color || MULTI_CURVE_COLORS[index % MULTI_CURVE_COLORS.length]
        }))
    }

    // 单数据源模式：使用当前 traceData
    return [{ id: 'current', data: traceData.grad_gamma_curve || [], color: '#ef4444' }]
  }, [traceData.grad_gamma_curve, dataSources])

  // Handle loading 3D surface data
  const handleLoad3DSurface = async () => {
    setIsLoadingSurface(true)
    setLoadingProgress(0)

    // Simulate progress while loading
    const progressInterval = setInterval(() => {
      setLoadingProgress(prev => {
        if (prev >= 90) {
          clearInterval(progressInterval)
          return 90
        }
        return prev + Math.random() * 15
      })
    }, 200)

    try {
      // Call backend to calculate sigma_beta_gamma
      const response = await fetch(`${getApiBaseUrl()}/calculate_3d_surface`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          method: methodId,
          data: traceData.data || [],
          trace_data: traceData
        })
      })

      if (!response.ok) {
        throw new Error('Failed to load 3D surface data')
      }

      const result = await response.json()

      clearInterval(progressInterval)
      setLoadingProgress(100)

      // Update trace data with sigma_beta_gamma from backend result
      const newTraceData = result.trace_data || result
      setSurfaceData({
        ...traceData,
        sigma_beta_gamma: newTraceData.sigma_beta_gamma || traceData.sigma_beta_gamma
      })

      setTimeout(() => {
        setIsLoadingSurface(false)
        setLoadingProgress(0)
      }, 300)
    } catch (error) {
      clearInterval(progressInterval)
      console.error('Failed to load 3D surface:', error)
      setIsLoadingSurface(false)
      setLoadingProgress(0)
      alert('加载三维曲面数据失败，请确保后端服务已启动。')
    }
  }

  // Reset 3D data when switching away from 3D view
  const handleSchemeChange = (scheme: 'original' | '3d' | 'offset') => {
    setActiveScheme(scheme)
    if (scheme !== '3d') {
      setSurfaceData(null)
    }
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Scheme Selector */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-sm font-bold text-slate-700">寻优过程可视化：</span>
          <div className="flex bg-slate-100 p-1 rounded-lg border border-slate-200">
            <button
              onClick={() => handleSchemeChange('original')}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-bold transition-all",
                activeScheme === 'original'
                  ? "bg-white text-blue-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              原始视图
            </button>
            <button
              onClick={() => handleSchemeChange('offset')}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-bold transition-all",
                activeScheme === 'offset'
                  ? "bg-white text-emerald-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              偏移量分析
            </button>
            <button
              onClick={() => handleSchemeChange('3d')}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-bold transition-all",
                activeScheme === '3d'
                  ? "bg-white text-purple-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              三维曲面
            </button>
          </div>
          <span className="text-xs text-slate-400 ml-auto">点击切换不同可视化方案</span>
        </div>
      </div>

      {/* Original View */}
      {activeScheme === 'original' && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

        {/* ========== Chart 1: Sigma vs Beta (with Gamma Slider) ========== */}
        {USE_NEW_CHART_COMPONENTS ? (
          /* ===== 新组件模式 ===== */
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-bold text-slate-800">形状参数寻优</h3>
                <div className="flex flex-wrap items-center justify-end gap-2">
                  <button
                    type="button"
                    role="switch"
                    aria-checked={showShapePoints}
                    aria-label="显示形状参数寻优采样点"
                    onClick={() => setShowShapePoints(current => !current)}
                    className={cn(
                      "h-7 rounded-full border px-2.5 text-xs font-bold transition-colors",
                      showShapePoints
                        ? "border-blue-200 bg-blue-50 text-blue-600"
                        : "border-slate-200 bg-white text-slate-500 hover:border-slate-300"
                    )}
                  >
                    {showShapePoints
                      ? '隐藏采样点'
                      : `显示采样点（${shapeSamplePointCount}）`}
                  </button>
                  {/* Gamma Mode Switch */}
                  <div className="flex bg-slate-100 p-0.5 rounded-full border border-slate-200">
                    <button
                      onClick={() => setGammaMode('optimal')}
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
                      onClick={() => setGammaMode('manual')}
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
                  {/* Refresh button - only in optimal mode */}
                  {gammaMode === 'optimal' && (
                    <button
                      onClick={(e) => { e.preventDefault(); handleRefreshChart(); }}
                      className="p-1.5 rounded-lg text-blue-600 hover:bg-blue-50"
                      title="刷新左图曲线"
                    >
                      <RefreshCw size={16} />
                    </button>
                  )}
                  <span className="text-sm font-bold text-blue-600">
                    γ {offsetStale ? '≈' : '='} {gammaMode === 'optimal'
                      ? optimalGammaFromDelta.toFixed(2)
                      : selectedGamma.toFixed(2)}
                  </span>
                </div>
              </div>
              <p className="text-sm text-slate-500">
                展示在选定的位置参数下，尺度参数标准差 σ_η 随形状参数 β 的变化。
                <span className="text-blue-600 font-medium">
                  {offsetStale
                    ? ' 当前 γ 为曲线交点预览，后端会自动替换为精确结果。'
                    : ' 当前最优 γ 来自本次后端计算结果。'}
                </span>
              </p>
            </div>

            {/* Gamma Slider */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-500">位置参数 γ</span>
                <span className="text-xs text-slate-400">
                  {gammaIndex + 1} / {gammaDataCount}
                  {gammaMode === 'optimal' && <span className="text-blue-600 ml-1">(自动)</span>}
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={gammaDataCount - 1}
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
                    : `linear-gradient(to right, #93c5fd 0%, #93c5fd ${(gammaIndex / (gammaDataCount - 1)) * 100}%, #e2e8f0 ${(gammaIndex / (gammaDataCount - 1)) * 100}%, #e2e8f0 100%)`
                }}
              />
              <div className="flex justify-between text-xs text-slate-400 mt-1">
                <span>{useSigmaBetaGamma && traceData.sigma_beta_gamma?.[0]
                  ? traceData.sigma_beta_gamma[0].gamma.toFixed(1)
                  : traceData.grad_gamma_curve?.[0]?.gamma?.toFixed(1) ?? '-'}
                </span>
                <span>{useSigmaBetaGamma && traceData.sigma_beta_gamma?.length
                  ? traceData.sigma_beta_gamma[traceData.sigma_beta_gamma.length - 1].gamma.toFixed(1)
                  : traceData.grad_gamma_curve?.[traceData.grad_gamma_curve.length - 1]?.gamma?.toFixed(1) ?? '-'}
                </span>
              </div>
            </div>

            {/* 使用新的 SigmaBetaChart 组件 */}
            <SigmaBetaChart
              curves={allSigmaBetaCurves}
              interactive={false}
              overlayMode={dataSources && dataSources.length > 0}
              showPoints={showShapePoints}
              noContainer={true}
              height={280}
              domain={{ x: [1, 6], y: [0, 1400] }}
              referenceLines={
                Math.abs(selectedGamma - traceData.optimal_gamma) < 5
                  ? [{ value: traceData.optimal_beta, label: `最优 β: ${traceData.optimal_beta.toFixed(2)}`, color: '#f59e0b', strokeDasharray: '5 5' }]
                  : []
              }
            />
            {/* 多曲线图例 */}
            {dataSources && dataSources.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-slate-100">
                {allSigmaBetaCurves.map((curve, idx) => (
                  <div key={curve.id} className="flex items-center gap-1.5 text-xs">
                    <div
                      className="w-3 h-0.5 rounded"
                      style={{ backgroundColor: curve.color || MULTI_CURVE_COLORS[idx % MULTI_CURVE_COLORS.length] }}
                    />
                    <span className="text-slate-600">{curve.id === 'current' ? '当前' : curve.id}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          /* ===== 旧代码模式（保留以便对比） ===== */
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-bold text-slate-800">形状参数寻优</h3>
                <div className="flex flex-wrap items-center justify-end gap-2">
                  <button
                    type="button"
                    role="switch"
                    aria-checked={showShapePoints}
                    aria-label="显示形状参数寻优采样点"
                    onClick={() => setShowShapePoints(current => !current)}
                    className={cn(
                      "h-7 rounded-full border px-2.5 text-xs font-bold transition-colors",
                      showShapePoints
                        ? "border-blue-200 bg-blue-50 text-blue-600"
                        : "border-slate-200 bg-white text-slate-500 hover:border-slate-300"
                    )}
                  >
                    {showShapePoints
                      ? '隐藏采样点'
                      : `显示采样点（${shapeSamplePointCount}）`}
                  </button>
                  {/* Gamma Mode Switch */}
                  <div className="flex bg-slate-100 p-0.5 rounded-full border border-slate-200">
                    <button
                      onClick={() => setGammaMode('optimal')}
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
                      onClick={() => setGammaMode('manual')}
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
                  {/* Refresh button - only in optimal mode */}
                  {gammaMode === 'optimal' && (
                    <button
                      onClick={(e) => { e.preventDefault(); handleRefreshChart(); }}
                      className="p-1.5 rounded-lg text-blue-600 hover:bg-blue-50"
                      title="刷新左图曲线"
                    >
                      <RefreshCw size={16} />
                    </button>
                  )}
                  <span className="text-sm font-bold text-blue-600">
                    γ = {gammaMode === 'optimal' ? optimalGammaFromDelta.toFixed(2) : selectedGamma.toFixed(2)}
                  </span>
                </div>
              </div>
              <p className="text-sm text-slate-500">
                展示在选定的位置参数下，尺度参数标准差 σ_η 随形状参数 β 的变化。
                <span className="text-blue-600 font-medium">
                  {" "}最优γ随右边δ实时变化，点击刷新图标重绘曲线
                </span>
              </p>
            </div>

            {/* Gamma Slider */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-500">位置参数 γ</span>
                <span className="text-xs text-slate-400">
                  {gammaIndex + 1} / {gammaDataCount}
                  {gammaMode === 'optimal' && <span className="text-blue-600 ml-1">(自动)</span>}
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={gammaDataCount - 1}
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
                    : `linear-gradient(to right, #93c5fd 0%, #93c5fd ${(gammaIndex / (gammaDataCount - 1)) * 100}%, #e2e8f0 ${(gammaIndex / (gammaDataCount - 1)) * 100}%, #e2e8f0 100%)`
                }}
              />
              <div className="flex justify-between text-xs text-slate-400 mt-1">
                <span>{useSigmaBetaGamma && traceData.sigma_beta_gamma?.[0]
                  ? traceData.sigma_beta_gamma[0].gamma.toFixed(1)
                  : traceData.grad_gamma_curve?.[0]?.gamma?.toFixed(1) ?? '-'}
                </span>
                <span>{useSigmaBetaGamma && traceData.sigma_beta_gamma?.length
                  ? traceData.sigma_beta_gamma[traceData.sigma_beta_gamma.length - 1].gamma.toFixed(1)
                  : traceData.grad_gamma_curve?.[traceData.grad_gamma_curve.length - 1]?.gamma?.toFixed(1) ?? '-'}
                </span>
              </div>
            </div>

            <div className="h-[280px] w-full">
              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={filteredSigmaBetaCurve} margin={{ top: 20, right: 25, bottom: 45, left: 55 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis
                    dataKey="beta"
                    type="number"
                    domain={[1, 6]}
                    ticks={[1, 2, 3, 4, 5, 6]}
                    tickFormatter={(v) => v.toFixed(0)}
                    tick={{ fontSize: 10 }}
                    label={{ value: '形状参数 β', position: 'bottom', offset: 0, fontSize: 11, fill: '#64748b' }}
                  />
                  <YAxis
                    domain={[0, 1400]}
                    tickCount={5}
                    width={45}
                    tick={{ fontSize: 10 }}
                    label={{ value: '标准差 σ_η', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#64748b' }}
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                    formatter={(value: number, name: string) => [value.toFixed(2), name]}
                    labelFormatter={(v) => `β: ${Number(v).toFixed(2)}`}
                  />
                  <Line
                    type="monotone"
                    dataKey="sigma"
                    stroke="#3b82f6"
                    strokeWidth={3}
                    dot={showShapePoints ? { r: 2.5, strokeWidth: 1 } : false}
                    activeDot={{ r: 6 }}
                  />
                  {Math.abs(selectedGamma - traceData.optimal_gamma) < 5 && (
                    <ReferenceLine
                      x={traceData.optimal_beta}
                      stroke="#f59e0b"
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      label={{ value: `最优 β: ${traceData.optimal_beta.toFixed(2)}`, position: 'top', fill: '#f59e0b', fontSize: 10 }}
                    />
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* ========== Chart 2: Gradient vs Gamma ========== */}
        {USE_NEW_CHART_COMPONENTS ? (
          /* ===== 新组件模式 ===== */
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-bold text-slate-800">位置参数梯度判据</h3>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    role="switch"
                    aria-checked={showGradientPoints}
                    aria-label="显示位置参数梯度采样点"
                    onClick={() => setShowGradientPoints(current => !current)}
                    className={cn(
                      "h-8 rounded-full border px-3 text-xs font-bold transition-colors",
                      showGradientPoints
                        ? "border-red-200 bg-red-50 text-red-600"
                        : "border-slate-200 bg-white text-slate-500 hover:border-slate-300"
                    )}
                  >
                    {showGradientPoints
                      ? '隐藏采样点'
                      : `显示采样点（${gradientSamplePointCount}）`}
                  </button>
                  <span className="text-sm font-bold text-emerald-600">δ =</span>
                  <select
                    value={deltaOffset}
                    onChange={(event) => onMdmOffsetChange(Number(event.target.value))}
                    aria-label="MDM 位置参数判据偏移量选择"
                    className="h-8 rounded-md border border-emerald-200 bg-emerald-50 px-2 text-sm font-bold text-emerald-700 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
                  >
                    {MDM_OFFSET_GRID.map(offset => (
                      <option key={offset} value={offset}>{offset.toFixed(2)}</option>
                    ))}
                  </select>
                </div>
              </div>
              <p className="text-sm text-slate-500">
                {offsetStale ? (
                  `阈值已与计算卡片同步；根据当前曲线即时得到 γ≈${optimalGammaFromDelta.toFixed(2)}，${isOffsetUpdating ? '后端正在自动更新精确 γ 与参数。' : '可点击参数估计重试精确计算。'}`
                ) : (
                  <>
                    <span className="text-blue-600 font-medium">竖线</span>标示当前选择的 γ 值，
                    <span className="text-emerald-600 font-medium">绿色虚线</span>为 δ 阈值。
                  </>
                )}
              </p>
            </div>

            {/* Delta Offset Slider */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-500">固定偏移量 δ（与计算卡片联动）</span>
                <span className="text-xs text-slate-400">
                  范围: {MDM_OFFSET_MIN.toFixed(2)} - {MDM_OFFSET_MAX.toFixed(2)}
                </span>
              </div>
              <input
                type="range"
                min={MDM_OFFSET_MIN}
                max={MDM_OFFSET_MAX}
                step={MDM_OFFSET_STEP}
                value={deltaOffset}
                onChange={(e) => onMdmOffsetChange(parseFloat(e.target.value))}
                aria-label="MDM 位置参数判据偏移量"
                className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-emerald-600"
                style={{
                  background: `linear-gradient(to right, #6ee7b7 0%, #6ee7b7 ${(deltaOffset / MDM_OFFSET_MAX) * 100}%, #e2e8f0 ${(deltaOffset / MDM_OFFSET_MAX) * 100}%, #e2e8f0 100%)`
                }}
              />
              <div className="flex justify-between text-xs text-slate-400 mt-1">
                <span>{MDM_OFFSET_MIN.toFixed(2)}</span>
                <span>{MDM_OFFSET_MAX.toFixed(2)}</span>
              </div>
            </div>

            {/* 使用新的 GradientGammaChart 组件 */}
            <GradientGammaChart
              curves={allGradientGammaCurves}
              singleCurve={traceData.grad_gamma_curve}
              interactive={false}
              overlayMode={dataSources && dataSources.length > 0}
              noContainer={true}
              height={280}
              offsetReference={deltaOffset}
              showPoints={showGradientPoints}
              domain={{
                x: [
                  Math.min(...(traceData.grad_gamma_curve?.map(d => d.gamma) || [0]), optimalGammaFromDelta) - 5,
                  Math.max(...(traceData.grad_gamma_curve?.map(d => d.gamma) || [0]), optimalGammaFromDelta) + 5
                ]
              }}
              gammaReferenceLines={
                offsetStale
                  ? [{ gamma: optimalGammaFromDelta, label: 'γ预览', color: '#f59e0b', position: 'bottom' as const }]
                  : gammaMode === 'optimal'
                  ? [{ gamma: optimalGammaFromDelta, label: '最优γ', color: '#f59e0b', position: 'bottom' as const }]
                  : [
                      { gamma: selectedGamma, label: '当前', color: '#3b82f6', position: 'top' as const },
                      ...(Math.abs(selectedGamma - optimalGammaFromDelta) > 1
                        ? [{ gamma: optimalGammaFromDelta, label: '最优', color: '#f59e0b', position: 'bottom' as const }]
                        : [])
                    ]
              }
            />
            {/* 多曲线图例 */}
            {dataSources && dataSources.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-slate-100">
                {allGradientGammaCurves.map((curve, idx) => (
                  <div key={curve.id} className="flex items-center gap-1.5 text-xs">
                    <div
                      className="w-3 h-0.5 rounded"
                      style={{ backgroundColor: curve.color || MULTI_CURVE_COLORS[idx % MULTI_CURVE_COLORS.length] }}
                    />
                    <span className="text-slate-600">{curve.id === 'current' ? '当前' : curve.id}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          /* ===== 旧代码模式（保留以便对比） ===== */
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-bold text-slate-800">位置参数梯度判据</h3>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    role="switch"
                    aria-checked={showGradientPoints}
                    aria-label="显示位置参数梯度采样点"
                    onClick={() => setShowGradientPoints(current => !current)}
                    className={cn(
                      "h-8 rounded-full border px-3 text-xs font-bold transition-colors",
                      showGradientPoints
                        ? "border-red-200 bg-red-50 text-red-600"
                        : "border-slate-200 bg-white text-slate-500 hover:border-slate-300"
                    )}
                  >
                    {showGradientPoints
                      ? '隐藏采样点'
                      : `显示采样点（${gradientSamplePointCount}）`}
                  </button>
                  <span className="text-sm font-bold text-emerald-600">δ =</span>
                  <select
                    value={deltaOffset}
                    onChange={(event) => onMdmOffsetChange(Number(event.target.value))}
                    aria-label="MDM 位置参数判据偏移量选择"
                    className="h-8 rounded-md border border-emerald-200 bg-emerald-50 px-2 text-sm font-bold text-emerald-700 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
                  >
                    {MDM_OFFSET_GRID.map(offset => (
                      <option key={offset} value={offset}>{offset.toFixed(2)}</option>
                    ))}
                  </select>
                </div>
              </div>
              <p className="text-sm text-slate-500">
                {offsetStale ? (
                  `阈值已与计算卡片同步；根据当前曲线即时得到 γ≈${optimalGammaFromDelta.toFixed(2)}，${isOffsetUpdating ? '后端正在自动更新精确 γ 与参数。' : '可点击参数估计重试精确计算。'}`
                ) : (
                  <>
                    <span className="text-blue-600 font-medium">竖线</span>标示当前选择的 γ 值，
                    <span className="text-emerald-600 font-medium">绿色虚线</span>为 δ 阈值。
                  </>
                )}
              </p>
            </div>

            {/* Delta Offset Slider */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-500">固定偏移量 δ（与计算卡片联动）</span>
                <span className="text-xs text-slate-400">
                  范围: {MDM_OFFSET_MIN.toFixed(2)} - {MDM_OFFSET_MAX.toFixed(2)}
                </span>
              </div>
              <input
                type="range"
                min={MDM_OFFSET_MIN}
                max={MDM_OFFSET_MAX}
                step={MDM_OFFSET_STEP}
                value={deltaOffset}
                onChange={(e) => onMdmOffsetChange(parseFloat(e.target.value))}
                aria-label="MDM 位置参数判据偏移量"
                className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-emerald-600"
                style={{
                  background: `linear-gradient(to right, #6ee7b7 0%, #6ee7b7 ${(deltaOffset / MDM_OFFSET_MAX) * 100}%, #e2e8f0 ${(deltaOffset / MDM_OFFSET_MAX) * 100}%, #e2e8f0 100%)`
                }}
              />
              <div className="flex justify-between text-xs text-slate-400 mt-1">
                <span>{MDM_OFFSET_MIN.toFixed(2)}</span>
                <span>{MDM_OFFSET_MAX.toFixed(2)}</span>
              </div>
            </div>

            <div className="h-[280px] w-full">
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={traceData.grad_gamma_curve || []} margin={{ top: 20, right: 25, bottom: 45, left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis
                    dataKey="gamma"
                    type="number"
                    domain={[
                      Math.min(...(traceData.grad_gamma_curve?.map(d => d.gamma) || [0]), optimalGammaFromDelta) - 5,
                      Math.max(...(traceData.grad_gamma_curve?.map(d => d.gamma) || [0]), optimalGammaFromDelta) + 5
                    ]}
                    tickFormatter={(v) => v.toFixed(0)}
                    tick={{ fontSize: 10 }}
                    label={{ value: '位置参数 γ', position: 'bottom', offset: 0, fontSize: 11, fill: '#64748b' }}
                  />
                  <YAxis
                    width={45}
                    tick={{ fontSize: 10 }}
                    label={{ value: '梯度 ∇(γ)', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#64748b' }}
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                    labelFormatter={(v) => `γ: ${Number(v).toFixed(1)}`}
                    formatter={(v: number) => [v.toFixed(4), '∇(γ)']}
                  />
                  <ReferenceLine y={deltaOffset} stroke="#10b981" strokeDasharray="3 3" label={{ position: 'right', value: `δ=${deltaOffset.toFixed(3)}`, fill: '#10b981', fontSize: 10 }} />
                  <ReferenceLine y={0} stroke="#cbd5e1" />
                  <Line
                    type="monotone"
                    dataKey="gradient"
                    stroke="#ef4444"
                    strokeWidth={2}
                    dot={showGradientPoints ? { r: 2.5, strokeWidth: 1 } : false}
                    activeDot={{ r: 6 }}
                  />
                  {/* Markers based on mode */}
                  {!offsetStale && (
                    gammaMode === 'optimal' ? (
                      // Optimal mode: only show orange line at optimal gamma (based on current delta)
                      <ReferenceLine x={optimalGammaFromDelta} stroke="#f59e0b" strokeDasharray="3 3" strokeWidth={2}>
                        <Label value="最优γ" position="bottom" fill="#f59e0b" fontSize={9} />
                      </ReferenceLine>
                    ) : (
                      // Manual mode: show blue line for current gamma
                      <ReferenceLine x={selectedGamma} stroke="#3b82f6" strokeDasharray="2 2" strokeWidth={2}>
                        <Label value="当前" position="top" fill="#3b82f6" fontSize={9} />
                      </ReferenceLine>
                    )
                  )}
                  {/* In manual mode, also show optimal gamma marker if different from current */}
                  {!offsetStale && gammaMode === 'manual' && Math.abs(selectedGamma - optimalGammaFromDelta) > 1 && (
                    <ReferenceLine x={optimalGammaFromDelta} stroke="#f59e0b" strokeDasharray="3 3">
                      <Label value="最优" position="bottom" fill="#f59e0b" fontSize={9} />
                    </ReferenceLine>
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

      </div>
          <MDMIterationViewer 
            traceData={surfaceData || traceData}
            isLoading={isLoadingSurface}
            onLoadData={handleLoad3DSurface}
            hasData={surfaceData !== null}
          />
        </>
      )}

      {/* Offset Analysis */}
      {activeScheme === 'offset' && (
        <MDMOffsetAnalyzer traceData={{ ...traceData, target_offset: deltaOffset }} />
      )}

      {/* 3D Surface Plot */}
      {activeScheme === '3d' && (
        <MDM3DSurfaceVisualizer
          traceData={surfaceData || traceData}
          isLoading={isLoadingSurface}
          loadingProgress={loadingProgress}
          onLoadData={handleLoad3DSurface}
          hasLoadedData={surfaceData !== null}
        />
      )}
    </div>
  )
}
