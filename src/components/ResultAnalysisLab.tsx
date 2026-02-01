"use client"

import React, { useState, useCallback } from 'react'
import { Play, RefreshCw, BarChart3, Loader2, TrendingUp } from 'lucide-react'
import {
  ResponsiveContainer,
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
  BarChart, Bar, Cell,
  LineChart, Line, Legend,
  Area, AreaChart
} from 'recharts'
import {
  DataPoint,
  WeibullResult,
  calculateMedianRanks,
  calculateWeibullParameters
} from '@/lib/weibull'

// Error Distribution Chart Component (Histogram + KDE Curve)
interface ErrorDistributionChartProps {
  title: string
  color: string
  errors: number[]
  trueValue: number
  estimatedMean?: number
}

function ErrorDistributionChart({ title, color, errors, trueValue, estimatedMean }: ErrorDistributionChartProps) {
  if (!errors || errors.length === 0) {
    return (
      <div className="text-center text-slate-400 py-8">
        暂无数据
      </div>
    )
  }

  // Calculate histogram bins
  const binCount = Math.min(15, Math.max(5, Math.floor(Math.sqrt(errors.length))))
  const max = Math.max(...errors)
  const binWidth = max / binCount

  const histogramData = Array.from({ length: binCount }, (_, i) => {
    const binStart = i * binWidth
    const binEnd = (i + 1) * binWidth
    const count = errors.filter(err => err >= binStart && err < binEnd).length
    return { binStart, binEnd, count }
  })

  // Calculate KDE
  const mean = errors.reduce((a, b) => a + b, 0) / errors.length
  const std = Math.sqrt(errors.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / errors.length)
  const sorted = [...errors].sort((a, b) => a - b)
  const iqr = sorted[Math.floor(sorted.length * 0.75)] - sorted[Math.floor(sorted.length * 0.25)]
  const h = 0.9 * Math.min(std, iqr / 1.34) * Math.pow(errors.length, -0.2)

  const kdePoints: { x: number; y: number }[] = []
  const xMax = Math.max(...errors) * 1.1
  const numPoints = 50

  for (let i = 0; i <= numPoints; i++) {
    const x = (i / numPoints) * xMax
    let y = 0
    for (const xi of errors) {
      const u = (x - xi) / h
      y += Math.exp(-0.5 * u * u)
    }
    y = y / (errors.length * h * Math.sqrt(2 * Math.PI))
    kdePoints.push({ x, y })
  }

  const maxCount = Math.max(...histogramData.map(d => d.count))
  const maxDensity = Math.max(...kdePoints.map(d => d.y))

  // SVG dimensions
  const width = 280
  const height = 220
  const padding = { top: 10, right: 15, bottom: 25, left: 35 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const xScale = (val: number) => padding.left + (val / xMax) * chartWidth
  const yScale = (val: number) => padding.top + chartHeight - (val / maxCount) * chartHeight

  // Statistics
  const median = sorted[Math.floor(sorted.length * 0.5)]
  const q95 = sorted[Math.floor(sorted.length * 0.95)]

  return (
    <div>
      <div className="text-center text-sm font-bold mb-2" style={{ color }}>{title}</div>
      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map(t => (
          <line
            key={`grid-${t}`}
            x1={padding.left}
            y1={padding.top + chartHeight * t}
            x2={width - padding.right}
            y2={padding.top + chartHeight * t}
            stroke="#f1f5f9"
            strokeWidth={1}
          />
        ))}

        {/* Y-axis labels */}
        {[0, 0.5, 1].map(t => {
          const val = Math.round(maxCount * t)
          return (
            <text
              key={`ylabel-${t}`}
              x={padding.left - 5}
              y={padding.top + chartHeight * t + 4}
              textAnchor="end"
              fontSize={9}
              fill="#94a3b8"
            >
              {val}
            </text>
          )
        })}

        {/* X-axis labels */}
        {[0, 0.25, 0.5, 0.75, 1].map(t => {
          const val = xMax * t
          return (
            <text
              key={`xlabel-${t}`}
              x={xScale(val)}
              y={height - 8}
              textAnchor="middle"
              fontSize={9}
              fill="#94a3b8"
            >
              {val.toFixed(2)}
            </text>
          )
        })}

        {/* Histogram bars */}
        {histogramData.map((d, i) => (
          <rect
            key={`bar-${i}`}
            x={xScale(d.binStart)}
            y={yScale(d.count)}
            width={Math.max(xScale(d.binEnd) - xScale(d.binStart) - 1, 1)}
            height={yScale(0) - yScale(d.count)}
            fill={color}
            fillOpacity={0.4}
          />
        ))}

        {/* KDE Curve - scaled to match histogram height */}
        <polyline
          points={kdePoints.map(d => `${xScale(d.x)},${yScale(d.y * (maxCount / maxDensity))}`).join(' ')}
          fill="none"
          stroke={color}
          strokeWidth={2.5}
        />

        {/* Mean line */}
        <line
          x1={xScale(mean)}
          y1={padding.top}
          x2={xScale(mean)}
          y2={padding.top + chartHeight}
          stroke={color}
          strokeWidth={1}
          strokeDasharray="4 4"
          opacity={0.6}
        />
      </svg>

      {/* Legend */}
      <div className="flex items-center justify-center gap-4 text-xs text-slate-500 mt-1">
        <span className="flex items-center gap-1">
          <div className="w-3 h-3" style={{ backgroundColor: color, opacity: 0.4 }}></div>
          <span>直方图</span>
        </span>
        <span className="flex items-center gap-1">
          <div className="w-8 h-0.5" style={{ backgroundColor: color }}></div>
          <span>密度曲线</span>
        </span>
      </div>

      {/* Statistics */}
      <div className="flex items-center justify-center gap-3 text-xs text-slate-600 mt-2">
        <span>μ: {mean.toFixed(4)}</span>
        <span>M: {median.toFixed(4)}</span>
        <span>P95: {q95.toFixed(4)}</span>
      </div>
    </div>
  )
}

interface SimulationResult {
  beta: number
  eta: number
  gamma: number
  betaError: number
  etaError: number
  gammaError: number
}

interface StatsSummary {
  betaMean: number
  betaStd: number
  betaBias: number
  betaMse: number
  etaMean: number
  etaStd: number
  etaBias: number
  etaMse: number
  gammaMean: number
  gammaStd: number
  gammaBias: number
  gammaMse: number
}

interface MultiSampleStats {
  sampleSize: number
  betaMean: number
  betaStd: number
  betaMse: number
  etaMean: number
  etaStd: number
  etaMse: number
  gammaMean: number
  gammaStd: number
  gammaMse: number
}

interface OffsetStats {
  offset: number
  betaMean: number
  betaStd: number
  betaBias: number
  betaMse: number
  etaMean: number
  etaStd: number
  etaBias: number
  etaMse: number
  gammaMean: number
  gammaStd: number
  gammaBias: number
  gammaMse: number
  absError95th: number  // 95th percentile of absolute errors
  // Raw error data for box plots
  betaErrors: number[]
  etaErrors: number[]
  gammaErrors: number[]
}

interface ResultAnalysisLabProps {
  methodId: string
  trueBeta: number
  trueEta: number
  trueGamma: number
}

type AnalysisMode = 'single' | 'range' | 'offset'

// Generate sample from Weibull distribution
function generateSample(n: number, beta: number, eta: number, gamma: number): DataPoint[] {
  return Array.from({ length: n }, (_, i) => {
    const u = Math.random()
    const t = gamma + eta * Math.pow(-Math.log(u), 1 / beta)
    return { id: i, value: t, status: 'F' as const }
  })
}

// Calculate histogram bins
function calculateHistogram(data: number[], binCount: number = 20): { bin: string, count: number, value: number }[] {
  const min = Math.min(...data)
  const max = Math.max(...data)
  const binWidth = (max - min) / binCount

  const bins = Array.from({ length: binCount }, (_, i) => ({
    bin: `${(min + i * binWidth).toFixed(2)}`,
    count: 0,
    value: min + i * binWidth + binWidth / 2
  }))

  data.forEach(value => {
    const binIndex = Math.min(Math.floor((value - min) / binWidth), binCount - 1)
    bins[binIndex].count++
  })

  return bins
}

// Calculate box plot stats
function calculateBoxPlotStats(data: number[]): { min: number, q1: number, median: number, q3: number, max: number } {
  const sorted = [...data].sort((a, b) => a - b)
  const n = sorted.length
  return {
    min: sorted[0],
    q1: sorted[Math.floor(n * 0.25)],
    median: sorted[Math.floor(n * 0.5)],
    q3: sorted[Math.floor(n * 0.75)],
    max: sorted[n - 1]
  }
}

export default function ResultAnalysisLab({
  methodId,
  trueBeta,
  trueEta,
  trueGamma
}: ResultAnalysisLabProps) {
  // Analysis mode: single sample size, sample size range, or offset (MDM only)
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>('single')
  const [singleSampleSize, setSingleSampleSize] = useState(50)
  const [sampleSizeMin, setSampleSizeMin] = useState(10)
  const [sampleSizeMax, setSampleSizeMax] = useState(200)
  const [sampleSizeStep, setSampleSizeStep] = useState(10)

  // Offset range configuration (for offset mode)
  const [offsetMin, setOffsetMin] = useState(0)
  const [offsetMax, setOffsetMax] = useState(0.5)
  const [offsetStep, setOffsetStep] = useState(0.02)

  // Simulation settings
  const [numSimulations, setNumSimulations] = useState(100)
  const [isRunning, setIsRunning] = useState(false)

  // Results
  const [results, setResults] = useState<SimulationResult[]>([])
  const [stats, setStats] = useState<StatsSummary | null>(null)
  const [multiStats, setMultiStats] = useState<MultiSampleStats[]>([])
  const [currentProgress, setCurrentProgress] = useState({ completed: 0, total: 0 })

  // Offset slider state for interactive distribution view
  const [selectedOffsetIndex, setSelectedOffsetIndex] = useState(0)

  // Estimate parameters using backend API
  const estimateParameters = async (data: DataPoint[], offset?: number): Promise<WeibullResult> => {
    try {
      const body: any = {
        method: methodId,
        data: data.map(d => d.value)
      }

      // Add offset parameter for MDM method
      if (methodId === 'mdm' && offset !== undefined) {
        body.offset = offset
      }

      const response = await fetch('http://localhost:8001/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })

      if (!response.ok) {
        throw new Error('API request failed')
      }

      const res = await response.json()
      const points = calculateMedianRanks(data, res.gamma || 0)

      return {
        beta: res.beta,
        eta: res.eta,
        gamma: res.gamma || 0,
        rSquared: res.rSquared,
        points,
        converged: res.converged
      }
    } catch (error) {
      // Fallback to RRX if API fails
      const gamma = trueGamma
      const points = calculateMedianRanks(data, gamma)
      return calculateWeibullParameters(points, gamma)
    }
  }

  const getSampleSizes = useCallback(() => {
    if (analysisMode === 'single' || analysisMode === 'offset') {
      return [singleSampleSize]
    }
    const sizes: number[] = []
    for (let n = sampleSizeMin; n <= sampleSizeMax; n += sampleSizeStep) {
      sizes.push(n)
    }
    return sizes
  }, [analysisMode, singleSampleSize, sampleSizeMin, sampleSizeMax, sampleSizeStep])

  const runSimulation = useCallback(async () => {
    setIsRunning(true)
    setResults([])
    setStats(null)
    setMultiStats([])

    if (analysisMode === 'offset') {
      // Offset mode: Test different offset values with the same sample size
      const offsets: number[] = []
      const numSteps = Math.floor((offsetMax - offsetMin) / offsetStep) + 1
      for (let i = 0; i < numSteps; i++) {
        const offset = parseFloat((offsetMin + i * offsetStep).toFixed(4))
        offsets.push(offset)
      }

      const totalSimulations = offsets.length * numSimulations
      setCurrentProgress({ completed: 0, total: totalSimulations })

      // Results grouped by offset value
      const offsetStats: OffsetStats[] = []

      for (const offset of offsets) {
        const betaEstimates: number[] = []
        const etaEstimates: number[] = []
        const gammaEstimates: number[] = []
        const betaErrors: number[] = []
        const etaErrors: number[] = []
        const gammaErrors: number[] = []

        for (let i = 0; i < numSimulations; i++) {
          const sample = generateSample(singleSampleSize, trueBeta, trueEta, trueGamma)
          const estimated = await estimateParameters(sample, offset)

          if (estimated.beta === null || estimated.eta === null) continue

          betaEstimates.push(estimated.beta)
          etaEstimates.push(estimated.eta)
          gammaEstimates.push(estimated.gamma)

          // Store absolute errors for box plots
          betaErrors.push(Math.abs(estimated.beta - trueBeta))
          etaErrors.push(Math.abs(estimated.eta - trueEta))
          gammaErrors.push(Math.abs(estimated.gamma - trueGamma))
        }

        const calcStats = (estimates: number[], trueVal: number) => {
          const n = estimates.length
          if (n === 0) return { mean: 0, std: 0, mse: 0, bias: 0 }
          const mean = estimates.reduce((a, b) => a + b, 0) / n
          const variance = estimates.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / n
          const std = Math.sqrt(variance)
          const bias = mean - trueVal
          const mse = estimates.reduce((a, b) => a + Math.pow(b - trueVal, 2), 0) / n
          return { mean, std, mse, bias }
        }

        // Calculate 95th percentile of absolute errors
        const allAbsErrors = [...betaErrors, ...etaErrors, ...gammaErrors]
        const calc95thPercentile = (data: number[]): number => {
          if (data.length === 0) return 0
          const sorted = [...data].sort((a, b) => a - b)
          const idx = Math.ceil(sorted.length * 0.95) - 1
          return sorted[Math.max(0, idx)]
        }

        offsetStats.push({
          offset,
          betaMean: calcStats(betaEstimates, trueBeta).mean,
          betaStd: calcStats(betaEstimates, trueBeta).std,
          betaBias: calcStats(betaEstimates, trueBeta).bias,
          betaMse: calcStats(betaEstimates, trueBeta).mse,
          etaMean: calcStats(etaEstimates, trueEta).mean,
          etaStd: calcStats(etaEstimates, trueEta).std,
          etaBias: calcStats(etaEstimates, trueEta).bias,
          etaMse: calcStats(etaEstimates, trueEta).mse,
          gammaMean: calcStats(gammaEstimates, trueGamma).mean,
          gammaStd: calcStats(gammaEstimates, trueGamma).std,
          gammaBias: calcStats(gammaEstimates, trueGamma).bias,
          gammaMse: calcStats(gammaEstimates, trueGamma).mse,
          absError95th: calc95thPercentile(allAbsErrors),
          betaErrors,
          etaErrors,
          gammaErrors
        })

        setCurrentProgress({ completed: (offsets.indexOf(offset) + 1) * numSimulations, total: totalSimulations })
      }

      // Store results in multiStats for display (final complete data)
      setMultiStats(offsetStats as any)

      // Set stats for first offset (for compatibility with existing display logic)
      const firstStats = offsetStats[0]
      setStats({
        betaMean: firstStats.betaMean,
        betaStd: firstStats.betaStd,
        betaBias: firstStats.betaBias,
        betaMse: firstStats.betaMse,
        etaMean: firstStats.etaMean,
        etaStd: firstStats.etaStd,
        etaBias: firstStats.etaBias,
        etaMse: firstStats.etaMse,
        gammaMean: firstStats.gammaMean,
        gammaStd: firstStats.gammaStd,
        gammaBias: firstStats.gammaBias,
        gammaMse: firstStats.gammaMse,
      })

      setCurrentProgress({ completed: totalSimulations, total: totalSimulations })
      setIsRunning(false)
      return
    }

    // Existing single/range sample size modes
    const sampleSizes = analysisMode === 'single'
      ? [singleSampleSize]
      : Array.from({ length: Math.floor((sampleSizeMax - sampleSizeMin) / sampleSizeStep) + 1 },
          (_, i) => sampleSizeMin + i * sampleSizeStep)

    const totalSimulations = sampleSizes.length * numSimulations
    setCurrentProgress({ completed: 0, total: totalSimulations })

    if (analysisMode === 'single') {
      // Single sample size mode
      const simulationResults: SimulationResult[] = []
      const betaEstimates: number[] = []
      const etaEstimates: number[] = []
      const gammaEstimates: number[] = []

      for (let i = 0; i < numSimulations; i++) {
        const sample = generateSample(singleSampleSize, trueBeta, trueEta, trueGamma)
        const estimated = await estimateParameters(sample)

        if (estimated.beta === null || estimated.eta === null) continue

        const betaError = estimated.beta - trueBeta
        const etaError = estimated.eta - trueEta
        const gammaError = estimated.gamma - trueGamma

        simulationResults.push({
          beta: estimated.beta,
          eta: estimated.eta,
          gamma: estimated.gamma,
          betaError,
          etaError,
          gammaError
        })

        betaEstimates.push(estimated.beta)
        etaEstimates.push(estimated.eta)
        gammaEstimates.push(estimated.gamma)

        if (i % 10 === 0) {
          setCurrentProgress({ completed: i, total: numSimulations })
          setResults([...simulationResults])
        }
      }

      setResults(simulationResults)

      // Calculate statistics
      const calcStats = (estimates: number[], trueVal: number) => {
        const n = estimates.length
        const mean = estimates.reduce((a, b) => a + b, 0) / n
        const variance = estimates.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / n
        const std = Math.sqrt(variance)
        const bias = mean - trueVal
        const mse = estimates.reduce((a, b) => a + Math.pow(b - trueVal, 2), 0) / n
        return { mean, std, bias, mse }
      }

      setStats({
        betaMean: calcStats(betaEstimates, trueBeta).mean,
        betaStd: calcStats(betaEstimates, trueBeta).std,
        betaBias: calcStats(betaEstimates, trueBeta).bias,
        betaMse: calcStats(betaEstimates, trueBeta).mse,
        etaMean: calcStats(etaEstimates, trueEta).mean,
        etaStd: calcStats(etaEstimates, trueEta).std,
        etaBias: calcStats(etaEstimates, trueEta).bias,
        etaMse: calcStats(etaEstimates, trueEta).mse,
        gammaMean: calcStats(gammaEstimates, trueGamma).mean,
        gammaStd: calcStats(gammaEstimates, trueGamma).std,
        gammaBias: calcStats(gammaEstimates, trueGamma).bias,
        gammaMse: calcStats(gammaEstimates, trueGamma).mse,
      })

    } else {
      // Multi sample size mode
      const allMultiStats: MultiSampleStats[] = []
      const firstSampleResults: SimulationResult[] = [] // For histogram display

      for (const sampleSize of sampleSizes) {
        const betaEstimates: number[] = []
        const etaEstimates: number[] = []
        const gammaEstimates: number[] = []

        for (let i = 0; i < numSimulations; i++) {
          const sample = generateSample(sampleSize, trueBeta, trueEta, trueGamma)
          const estimated = await estimateParameters(sample)

          if (estimated.beta === null || estimated.eta === null) continue

          betaEstimates.push(estimated.beta)
          etaEstimates.push(estimated.eta)
          gammaEstimates.push(estimated.gamma)

          // Save first sample size results for histogram
          if (sampleSize === sampleSizes[0]) {
            const betaError = estimated.beta - trueBeta
            const etaError = estimated.eta - trueEta
            const gammaError = estimated.gamma - trueGamma
            firstSampleResults.push({
              beta: estimated.beta,
              eta: estimated.eta,
              gamma: estimated.gamma,
              betaError,
              etaError,
              gammaError
            })
          }
        }

        const calcStats = (estimates: number[], trueVal: number) => {
          const n = estimates.length
          const mean = estimates.reduce((a, b) => a + b, 0) / n
          const variance = estimates.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / n
          const std = Math.sqrt(variance)
          const mse = estimates.reduce((a, b) => a + Math.pow(b - trueVal, 2), 0) / n
          return { mean, std, mse }
        }

        allMultiStats.push({
          sampleSize,
          betaMean: calcStats(betaEstimates, trueBeta).mean,
          betaStd: calcStats(betaEstimates, trueBeta).std,
          betaMse: calcStats(betaEstimates, trueBeta).mse,
          etaMean: calcStats(etaEstimates, trueEta).mean,
          etaStd: calcStats(etaEstimates, trueEta).std,
          etaMse: calcStats(etaEstimates, trueEta).mse,
          gammaMean: calcStats(gammaEstimates, trueGamma).mean,
          gammaStd: calcStats(gammaEstimates, trueGamma).std,
          gammaMse: calcStats(gammaEstimates, trueGamma).mse,
        })

        setMultiStats([...allMultiStats])
      }

      // Set results and stats for first sample size (for histogram display)
      setResults(firstSampleResults)
      const firstStats = allMultiStats[0]
      setStats({
        betaMean: firstStats.betaMean,
        betaStd: firstStats.betaStd,
        betaBias: firstStats.betaMean - trueBeta,
        betaMse: firstStats.betaMse,
        etaMean: firstStats.etaMean,
        etaStd: firstStats.etaStd,
        etaBias: firstStats.etaMean - trueEta,
        etaMse: firstStats.etaMse,
        gammaMean: firstStats.gammaMean,
        gammaStd: firstStats.gammaStd,
        gammaBias: firstStats.gammaMean - trueGamma,
        gammaMse: firstStats.gammaMse,
      })
    }

    setCurrentProgress({ completed: totalSimulations, total: totalSimulations })
    setIsRunning(false)
  }, [analysisMode, singleSampleSize, sampleSizeMin, sampleSizeMax, sampleSizeStep, offsetMin, offsetMax, offsetStep, numSimulations, trueBeta, trueEta, trueGamma, methodId])

  return (
    <div className="space-y-6">
      {/* Control Panel */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6">
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className="text-emerald-600" size={20} />
          <h3 className="font-bold text-slate-900">蒙特卡洛模拟配置</h3>
        </div>

        {/* True Parameters Display */}
        <div className="bg-slate-50 rounded-xl p-4 mb-4 border border-slate-200">
          <div className="text-xs font-black text-slate-500 uppercase mb-2">真实参数 (来自上方卡片)</div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <span className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
                <span className="text-sm font-black text-blue-600">β</span>
              </span>
              <span className="font-mono font-bold text-slate-900">{trueBeta.toFixed(3)}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center">
                <span className="text-sm font-black text-indigo-600">η</span>
              </span>
              <span className="font-mono font-bold text-slate-900">{trueEta.toFixed(1)}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-8 h-8 rounded-lg bg-purple-100 flex items-center justify-center">
                <span className="text-sm font-black text-purple-600">γ</span>
              </span>
              <span className="font-mono font-bold text-slate-900">{trueGamma.toFixed(1)}</span>
            </div>
          </div>
        </div>

        {/* Analysis Mode */}
        <div className="mb-4">
          <div className="text-xs font-black text-slate-500 uppercase mb-2">分析模式</div>
          <div className="flex gap-4 flex-wrap">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="analysisMode"
                checked={analysisMode === 'single'}
                onChange={() => setAnalysisMode('single')}
                className="w-4 h-4 text-emerald-600"
              />
              <span className="text-sm font-bold text-slate-700">固定样本量看精度</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="analysisMode"
                checked={analysisMode === 'range'}
                onChange={() => setAnalysisMode('range')}
                className="w-4 h-4 text-emerald-600"
              />
              <span className="text-sm font-bold text-slate-700">看样本量影响</span>
            </label>
            {methodId === 'mdm' && (
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="analysisMode"
                  checked={analysisMode === 'offset'}
                  onChange={() => setAnalysisMode('offset')}
                  className="w-4 h-4 text-amber-600"
                />
                <span className="text-sm font-bold text-amber-700">偏移量影响 (MDM)</span>
              </label>
            )}
          </div>
        </div>

        {/* Configuration based on mode */}
        <div className="mb-4">
          {analysisMode === 'offset' ? (
            // Offset range configuration for MDM
            <div className="flex items-center gap-4 flex-wrap">
              <div className="flex items-center gap-2">
                <label className="text-xs font-black text-slate-500 uppercase">最小偏移</label>
                <input
                  type="number"
                  min={0}
                  max={2}
                  step={0.01}
                  value={offsetMin}
                  onChange={(e) => setOffsetMin(parseFloat(e.target.value) || 0)}
                  className="w-20 px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono font-bold text-center"
                />
              </div>
              <div className="flex items-center gap-2">
                <label className="text-xs font-black text-slate-500 uppercase">最大偏移</label>
                <input
                  type="number"
                  min={0}
                  max={2}
                  step={0.01}
                  value={offsetMax}
                  onChange={(e) => setOffsetMax(parseFloat(e.target.value) || 0.5)}
                  className="w-20 px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono font-bold text-center"
                />
              </div>
              <div className="flex items-center gap-2">
                <label className="text-xs font-black text-slate-500 uppercase">步长</label>
                <input
                  type="number"
                  min={0.01}
                  max={0.5}
                  step={0.01}
                  value={offsetStep}
                  onChange={(e) => setOffsetStep(parseFloat(e.target.value) || 0.02)}
                  className="w-20 px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono font-bold text-center"
                />
              </div>
              <div className="text-xs text-slate-500">
                = ~{Math.floor((offsetMax - offsetMin) / offsetStep) + 1} 个偏移值
              </div>
            </div>
          ) : analysisMode === 'single' ? (
            // Single sample size configuration
            <div className="flex items-center gap-2">
              <label className="text-xs font-black text-slate-500 uppercase">样本量 n</label>
              <input
                type="number"
                min={5}
                max={500}
                value={singleSampleSize}
                onChange={(e) => setSingleSampleSize(parseInt(e.target.value) || 50)}
                className="w-24 px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono font-bold text-center"
              />
            </div>
          ) : (
            // Sample size range configuration
            <div className="flex items-center gap-4 flex-wrap">
              <div className="flex items-center gap-2">
                <label className="text-xs font-black text-slate-500 uppercase">最小</label>
                <input
                  type="number"
                  min={5}
                  value={sampleSizeMin}
                  onChange={(e) => setSampleSizeMin(parseInt(e.target.value) || 10)}
                  className="w-20 px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono font-bold text-center"
                />
              </div>
              <div className="flex items-center gap-2">
                <label className="text-xs font-black text-slate-500 uppercase">最大</label>
                <input
                  type="number"
                  min={10}
                  value={sampleSizeMax}
                  onChange={(e) => setSampleSizeMax(parseInt(e.target.value) || 200)}
                  className="w-20 px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono font-bold text-center"
                />
              </div>
              <div className="flex items-center gap-2">
                <label className="text-xs font-black text-slate-500 uppercase">步长</label>
                <input
                  type="number"
                  min={1}
                  value={sampleSizeStep}
                  onChange={(e) => setSampleSizeStep(parseInt(e.target.value) || 10)}
                  className="w-20 px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono font-bold text-center"
                />
              </div>
              <div className="text-xs text-slate-500">
                = {getSampleSizes().length} 个样本量: {getSampleSizes().slice(0, 5).join(', ')}{getSampleSizes().length > 5 ? '...' : ''}
              </div>
            </div>
          )}
        </div>

        {/* Number of Simulations */}
        <div className="mb-4">
          <div className="flex items-center gap-2">
            <label className="text-xs font-black text-slate-500 uppercase">重复次数</label>
            <select
              value={numSimulations}
              onChange={(e) => setNumSimulations(parseInt(e.target.value))}
              className="px-3 py-2 border border-slate-200 rounded-lg text-sm font-bold bg-white"
            >
              <option value={30}>30</option>
              <option value={100}>100</option>
              <option value={500}>500</option>
              <option value={1000}>1000</option>
              <option value={5000}>5000</option>
            </select>
            <span className="text-xs text-slate-500">次</span>
          </div>
        </div>

        {/* Run Button */}
        <button
          onClick={runSimulation}
          disabled={isRunning}
          className={`w-full flex items-center justify-center gap-2 px-6 py-3 ${analysisMode === 'offset' ? 'bg-amber-600 hover:bg-amber-700' : 'bg-emerald-600 hover:bg-emerald-700'} disabled:bg-slate-300 text-white rounded-xl text-sm font-bold transition-all shadow-sm`}
        >
          {isRunning ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} />}
          {isRunning
            ? `运行中 ${currentProgress.completed}/${currentProgress.total}`
            : analysisMode === 'offset'
            ? `开始偏移量分析 (~${Math.floor((offsetMax - offsetMin) / offsetStep) + 1} × ${numSimulations} 次)`
            : `开始模拟 (${getSampleSizes().length} × ${numSimulations} = ${getSampleSizes().length * numSimulations} 次)`
          }
        </button>
      </div>

      {/* Results */}
      {(stats || multiStats.length > 0) && (
        <div className="space-y-6">
          {/* Statistics Summary Table */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp className="text-blue-600" size={20} />
              <h3 className="font-bold text-slate-900">统计摘要</h3>
            </div>

            {stats ? (
              // Single sample size mode
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200">
                      <th className="text-left py-2 px-3 font-black text-slate-500">参数</th>
                      <th className="text-right py-2 px-3 font-black text-slate-500">真实值</th>
                      <th className="text-right py-2 px-3 font-black text-slate-500">估计均值</th>
                      <th className="text-right py-2 px-3 font-black text-slate-500">标准差</th>
                      <th className="text-right py-2 px-3 font-black text-slate-500">偏差</th>
                      <th className="text-right py-2 px-3 font-black text-slate-500">MSE</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-slate-100">
                      <td className="py-2 px-3 font-bold text-slate-900">β (形状)</td>
                      <td className="py-2 px-3 text-right font-mono text-slate-700">{trueBeta.toFixed(4)}</td>
                      <td className="py-2 px-3 text-right font-mono font-bold text-blue-600">{stats.betaMean.toFixed(4)}</td>
                      <td className="py-2 px-3 text-right font-mono text-amber-600">{stats.betaStd.toFixed(4)}</td>
                      <td className="py-2 px-3 text-right font-mono text-slate-700">{stats.betaBias >= 0 ? '+' : ''}{stats.betaBias.toFixed(4)}</td>
                      <td className="py-2 px-3 text-right font-mono text-red-600">{stats.betaMse.toFixed(4)}</td>
                    </tr>
                    <tr className="border-b border-slate-100">
                      <td className="py-2 px-3 font-bold text-slate-900">η (尺度)</td>
                      <td className="py-2 px-3 text-right font-mono text-slate-700">{trueEta.toFixed(2)}</td>
                      <td className="py-2 px-3 text-right font-mono font-bold text-indigo-600">{stats.etaMean.toFixed(2)}</td>
                      <td className="py-2 px-3 text-right font-mono text-amber-600">{stats.etaStd.toFixed(2)}</td>
                      <td className="py-2 px-3 text-right font-mono text-slate-700">{stats.etaBias >= 0 ? '+' : ''}{stats.etaBias.toFixed(2)}</td>
                      <td className="py-2 px-3 text-right font-mono text-red-600">{stats.etaMse.toFixed(2)}</td>
                    </tr>
                    <tr>
                      <td className="py-2 px-3 font-bold text-slate-900">γ (位置)</td>
                      <td className="py-2 px-3 text-right font-mono text-slate-700">{trueGamma.toFixed(2)}</td>
                      <td className="py-2 px-3 text-right font-mono font-bold text-purple-600">{stats.gammaMean.toFixed(2)}</td>
                      <td className="py-2 px-3 text-right font-mono text-amber-600">{stats.gammaStd.toFixed(2)}</td>
                      <td className="py-2 px-3 text-right font-mono text-slate-700">{stats.gammaBias >= 0 ? '+' : ''}{stats.gammaBias.toFixed(2)}</td>
                      <td className="py-2 px-3 text-right font-mono text-red-600">{stats.gammaMse.toFixed(2)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : (
              // Multi sample size mode OR offset mode
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200">
                      {analysisMode === 'offset' ? (
                        <>
                          <th className="text-left py-2 px-3 font-black text-slate-500">偏移量</th>
                          <th className="text-center py-2 px-3 font-black text-blue-500">β̂ 均值</th>
                          <th className="text-center py-2 px-3 font-black text-blue-500">β̂ MSE</th>
                          <th className="text-center py-2 px-3 font-black text-amber-500">95%分位数</th>
                          <th className="text-center py-2 px-3 font-black text-indigo-500">η̂ 均值</th>
                          <th className="text-center py-2 px-3 font-black text-indigo-500">η̂ MSE</th>
                          <th className="text-center py-2 px-3 font-black text-purple-500">γ̂ 均值</th>
                          <th className="text-center py-2 px-3 font-black text-purple-500">γ̂ MSE</th>
                        </>
                      ) : (
                        <>
                          <th className="text-left py-2 px-3 font-black text-slate-500">样本量</th>
                          <th className="text-center py-2 px-3 font-black text-blue-500">β̂ 均值</th>
                          <th className="text-center py-2 px-3 font-black text-blue-500">β̂ 标准差</th>
                          <th className="text-center py-2 px-3 font-black text-blue-500">β̂ MSE</th>
                          <th className="text-center py-2 px-3 font-black text-indigo-500">η̂ 均值</th>
                          <th className="text-center py-2 px-3 font-black text-indigo-500">η̂ 标准差</th>
                          <th className="text-center py-2 px-3 font-black text-indigo-500">η̂ MSE</th>
                          <th className="text-center py-2 px-3 font-black text-purple-500">γ̂ 均值</th>
                          <th className="text-center py-2 px-3 font-black text-purple-500">γ̂ 标准差</th>
                          <th className="text-center py-2 px-3 font-black text-purple-500">γ̂ MSE</th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {multiStats.map((s: any) => (
                      <tr key={analysisMode === 'offset' ? s.offset : s.sampleSize} className="border-b border-slate-100">
                        {analysisMode === 'offset' ? (
                          <>
                            <td className="py-2 px-3 font-bold text-slate-900">δ={s.offset.toFixed(3)}</td>
                            <td className="py-2 px-3 text-right font-mono text-blue-600">{s.betaMean.toFixed(4)}</td>
                            <td className="py-2 px-3 text-right font-mono text-red-600">{s.betaMse.toFixed(4)}</td>
                            <td className="py-2 px-3 text-right font-mono text-amber-600">{s.absError95th.toFixed(4)}</td>
                            <td className="py-2 px-3 text-right font-mono text-indigo-600">{s.etaMean.toFixed(2)}</td>
                            <td className="py-2 px-3 text-right font-mono text-red-600">{s.etaMse.toFixed(2)}</td>
                            <td className="py-2 px-3 text-right font-mono text-purple-600">{s.gammaMean.toFixed(2)}</td>
                            <td className="py-2 px-3 text-right font-mono text-red-600">{s.gammaMse.toFixed(2)}</td>
                          </>
                        ) : (
                          <>
                            <td className="py-2 px-3 font-bold text-slate-900">n={s.sampleSize}</td>
                            <td className="py-2 px-3 text-right font-mono text-blue-600">{s.betaMean.toFixed(4)}</td>
                            <td className="py-2 px-3 text-right font-mono text-amber-600">{s.betaStd.toFixed(4)}</td>
                            <td className="py-2 px-3 text-right font-mono text-red-600">{s.betaMse.toFixed(4)}</td>
                            <td className="py-2 px-3 text-right font-mono text-indigo-600">{s.etaMean.toFixed(2)}</td>
                            <td className="py-2 px-3 text-right font-mono text-amber-600">{s.etaStd.toFixed(2)}</td>
                            <td className="py-2 px-3 text-right font-mono text-red-600">{s.etaMse.toFixed(2)}</td>
                            <td className="py-2 px-3 text-right font-mono text-purple-600">{s.gammaMean.toFixed(2)}</td>
                            <td className="py-2 px-3 text-right font-mono text-amber-600">{s.gammaStd.toFixed(2)}</td>
                            <td className="py-2 px-3 text-right font-mono text-red-600">{s.gammaMse.toFixed(2)}</td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Chart 1: Histogram */}
          {stats && results.length > 0 && analysisMode !== 'offset' && (
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <div className="flex items-center gap-2 mb-4">
                <BarChart3 className="text-blue-600" size={20} />
                <h3 className="font-bold text-slate-900">图1: 参数分布直方图</h3>
                <span className="text-xs text-slate-500 ml-auto">
                  n={analysisMode === 'single' ? singleSampleSize : sampleSizeMin}, {numSimulations}次重复
                  {analysisMode === 'range' && ' (显示第一个样本量)'}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Beta Histogram */}
                <div>
                  <div className="text-center text-sm font-bold text-blue-600 mb-2">β̂ 分布</div>
                  <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={calculateHistogram(results.map(r => r.beta))}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="bin" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 10 }} />
                        <Bar dataKey="count" fill="#3b82f6" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="text-center text-xs text-slate-500 mt-1">
                    真实值: {trueBeta.toFixed(2)} | 均值: {stats.betaMean.toFixed(2)}
                  </div>
                </div>

                {/* Eta Histogram */}
                <div>
                  <div className="text-center text-sm font-bold text-indigo-600 mb-2">η̂ 分布</div>
                  <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={calculateHistogram(results.map(r => r.eta))}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="bin" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 10 }} />
                        <Bar dataKey="count" fill="#6366f1" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="text-center text-xs text-slate-500 mt-1">
                    真实值: {trueEta.toFixed(1)} | 均值: {stats.etaMean.toFixed(1)}
                  </div>
                </div>

                {/* Gamma Histogram */}
                <div>
                  <div className="text-center text-sm font-bold text-purple-600 mb-2">γ̂ 分布</div>
                  <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={calculateHistogram(results.map(r => r.gamma))}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="bin" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 10 }} />
                        <Bar dataKey="count" fill="#a855f7" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="text-center text-xs text-slate-500 mt-1">
                    真实值: {trueGamma.toFixed(1)} | 均值: {stats.gammaMean.toFixed(1)}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Chart 2: Standard Deviation vs Sample Size/Offset */}
          {multiStats.length > 0 && (analysisMode === 'range' || analysisMode === 'offset') && (
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <div className="flex items-center gap-2 mb-4">
                <BarChart3 className={analysisMode === 'offset' ? 'text-amber-600' : 'text-emerald-600'} size={20} />
                <h3 className="font-bold text-slate-900">
                  图2: {analysisMode === 'offset' ? 'MSE 随偏移量变化' : '标准差随样本量变化'}
                </h3>
              </div>

              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={multiStats}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis
                      dataKey={analysisMode === 'offset' ? 'offset' : 'sampleSize'}
                      domain={analysisMode === 'offset' ? ['dataMin', 'dataMax'] : ['auto', 'auto']}
                      label={{ value: analysisMode === 'offset' ? '偏移量 δ' : '样本量 n', position: 'insideBottom', offset: -5 }}
                      tickFormatter={analysisMode === 'offset' ? (v) => v.toFixed(3) : undefined}
                      tick={{ fontSize: 11 }}
                    />
                    <YAxis label={{ value: analysisMode === 'offset' ? 'MSE' : '标准差', angle: -90, position: 'insideLeft' }} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    {analysisMode === 'offset' ? (
                      // Offset mode: Show MSE instead of Std (more meaningful)
                      <>
                        <Line type="monotone" dataKey="betaMse" stroke="#3b82f6" name="β̂ MSE" strokeWidth={2} dot={{ r: 4 }} />
                        <Line type="monotone" dataKey="etaMse" stroke="#6366f1" name="η̂ MSE" strokeWidth={2} dot={{ r: 4 }} />
                        <Line type="monotone" dataKey="gammaMse" stroke="#a855f7" name="γ̂ MSE" strokeWidth={2} dot={{ r: 4 }} />
                      </>
                    ) : (
                      // Sample size range mode: Show Std
                      <>
                        <Line type="monotone" dataKey="betaStd" stroke="#3b82f6" name="β̂ 标准差" strokeWidth={2} dot={{ r: 4 }} />
                        <Line type="monotone" dataKey="etaStd" stroke="#6366f1" name="η̂ 标准差" strokeWidth={2} dot={{ r: 4 }} />
                        <Line type="monotone" dataKey="gammaStd" stroke="#a855f7" name="γ̂ 标准差" strokeWidth={2} dot={{ r: 4 }} />
                      </>
                    )}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Chart 3: MSE Curve / 95th Percentile Error Curve */}
          {multiStats.length > 0 && (analysisMode === 'range' || analysisMode === 'offset') && (
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp className={analysisMode === 'offset' ? 'text-amber-600' : 'text-red-600'} size={20} />
                <h3 className="font-bold text-slate-900">
                  图3: {analysisMode === 'offset' ? '偏差95%分位数随偏移量变化' : 'MSE 收敛曲线'}
                </h3>
              </div>

              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={multiStats}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis
                      dataKey={analysisMode === 'offset' ? 'offset' : 'sampleSize'}
                      domain={analysisMode === 'offset' ? ['dataMin', 'dataMax'] : ['auto', 'auto']}
                      label={{ value: analysisMode === 'offset' ? '偏移量 δ' : '样本量 n', position: 'insideBottom', offset: -5 }}
                      tickFormatter={analysisMode === 'offset' ? (v) => v.toFixed(3) : undefined}
                      tick={{ fontSize: 11 }}
                    />
                    <YAxis label={{ value: analysisMode === 'offset' ? '偏差95%分位数' : 'MSE', angle: -90, position: 'insideLeft' }} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    {analysisMode === 'offset' ? (
                      // Offset mode: Show 95th percentile error
                      <Line
                        type="monotone"
                        dataKey="absError95th"
                        stroke="#f59e0b"
                        name="95%分位数 P95(|偏差|)"
                        strokeWidth={2}
                        dot={{ r: 4 }}
                      />
                    ) : (
                      // Sample size range mode: Show MSE
                      <>
                        <Line type="monotone" dataKey="betaMse" stroke="#3b82f6" name="β̂ MSE" strokeWidth={2} dot={{ r: 4 }} />
                        <Line type="monotone" dataKey="etaMse" stroke="#6366f1" name="η̂ MSE" strokeWidth={2} dot={{ r: 4 }} />
                        <Line type="monotone" dataKey="gammaMse" stroke="#a855f7" name="γ̂ MSE" strokeWidth={2} dot={{ r: 4 }} />
                      </>
                    )}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Chart 4: Interactive Error Distribution (offset mode only) */}
          {multiStats.length > 0 && analysisMode === 'offset' && (
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <div className="flex items-center gap-2 mb-4">
                <BarChart3 className="text-purple-600" size={20} />
                <h3 className="font-bold text-slate-900">
                  图4: 偏差分布直方图
                </h3>
                <span className="text-xs text-slate-500 ml-2">滑动滑块查看不同偏移量下的误差分布</span>
              </div>

              {/* Offset Slider */}
              <div className="mb-6">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-bold text-slate-700">
                    当前偏移量 δ = {(multiStats[selectedOffsetIndex] as any)?.offset?.toFixed(3) || '0.000'}
                  </span>
                  <span className="text-xs text-slate-500">
                    {selectedOffsetIndex + 1} / {multiStats.length}
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={multiStats.length - 1}
                  step={1}
                  value={selectedOffsetIndex}
                  onChange={(e) => setSelectedOffsetIndex(parseInt(e.target.value))}
                  className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-purple-600"
                  style={{ background: `linear-gradient(to right, #c4b5fd 0%, #c4b5fd ${(selectedOffsetIndex / (multiStats.length - 1)) * 100}%, #e2e8f0 ${(selectedOffsetIndex / (multiStats.length - 1)) * 100}%, #e2e8f0 100%)` }}
                />
                <div className="flex justify-between text-xs text-slate-400 mt-1">
                  <span>δ = {offsetMin.toFixed(3)}</span>
                  <span>δ = {offsetMax.toFixed(3)}</span>
                </div>
              </div>

              {/* Statistics Summary for Selected Offset */}
              {(multiStats[selectedOffsetIndex] as any)?.offset && (
                <div className="grid grid-cols-3 gap-4 mb-6">
                  <div className="bg-blue-50 rounded-lg p-3 border border-blue-100">
                    <div className="text-xs font-bold text-blue-600 mb-1">β 偏差</div>
                    <div className="flex items-center gap-3 text-xs">
                      <span>均值: {((multiStats[selectedOffsetIndex] as any)?.betaMean - trueBeta).toFixed(4)}</span>
                      <span>95%分位: {((multiStats[selectedOffsetIndex] as any)?.absError95th).toFixed(4)}</span>
                    </div>
                  </div>
                  <div className="bg-indigo-50 rounded-lg p-3 border border-indigo-100">
                    <div className="text-xs font-bold text-indigo-600 mb-1">η 偏差</div>
                    <div className="flex items-center gap-3 text-xs">
                      <span>均值: {Math.abs((multiStats[selectedOffsetIndex] as any)?.etaMean - trueEta).toFixed(2)}</span>
                      <span>MSE: {((multiStats[selectedOffsetIndex] as any)?.etaMse).toFixed(2)}</span>
                    </div>
                  </div>
                  <div className="bg-purple-50 rounded-lg p-3 border border-purple-100">
                    <div className="text-xs font-bold text-purple-600 mb-1">γ 偏差</div>
                    <div className="flex items-center gap-3 text-xs">
                      <span>均值: {Math.abs((multiStats[selectedOffsetIndex] as any)?.gammaMean - trueGamma).toFixed(2)}</span>
                      <span>MSE: {((multiStats[selectedOffsetIndex] as any)?.gammaMse).toFixed(2)}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Distribution Histograms with KDE Curves */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Beta Error Distribution */}
                <ErrorDistributionChart
                  title="β 偏差 |β̂ - β|"
                  color="#3b82f6"
                  errors={(multiStats[selectedOffsetIndex] as any)?.betaErrors || []}
                  trueValue={trueBeta}
                  estimatedMean={(multiStats[selectedOffsetIndex] as any)?.betaMean}
                />

                {/* Eta Error Distribution */}
                <ErrorDistributionChart
                  title="η 偏差 |η̂ - η|"
                  color="#6366f1"
                  errors={(multiStats[selectedOffsetIndex] as any)?.etaErrors || []}
                  trueValue={trueEta}
                  estimatedMean={(multiStats[selectedOffsetIndex] as any)?.etaMean}
                />

                {/* Gamma Error Distribution */}
                <ErrorDistributionChart
                  title="γ 偏差 |γ̂ - γ|"
                  color="#a855f7"
                  errors={(multiStats[selectedOffsetIndex] as any)?.gammaErrors || []}
                  trueValue={trueGamma}
                  estimatedMean={(multiStats[selectedOffsetIndex] as any)?.gammaMean}
                />
              </div>
            </div>
          )}

          {/* Chart 5: Scatter Plot (single sample size mode) */}
          {stats && results.length > 0 && analysisMode === 'single' && (
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <div className="flex items-center gap-2 mb-4">
                <BarChart3 className="text-purple-600" size={20} />
                <h3 className="font-bold text-slate-900">图4: 估计值 vs 真实值偏差</h3>
              </div>

              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis type="number" dataKey="beta" name="估计值" domain={['auto', 'auto']} tick={{ fontSize: 11 }} />
                    <YAxis type="number" dataKey="betaError" name="偏差" tick={{ fontSize: 11 }} />
                    <Tooltip
                      cursor={{ strokeDasharray: '3 3' }}
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const p = payload[0].payload
                          return (
                            <div className="bg-white border border-slate-200 rounded-lg p-2 shadow-lg text-xs">
                              <p className="font-bold">β̂: {p.beta.toFixed(3)}</p>
                              <p>偏差: {p.betaError.toFixed(4)}</p>
                            </div>
                          )
                        }
                        return null
                      }}
                    />
                    <ReferenceLine y={0} stroke="#22c55e" strokeWidth={2} strokeDasharray="4 4" />
                    <Scatter name="估计结果" data={results} fill="#3b82f6" opacity={0.6} />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
              <p className="text-xs text-slate-400 mt-2 text-center">X轴: 估计值 β̂ | Y轴: 与真实值的偏差 | 绿色虚线: 无偏差（完美估计）</p>
            </div>
          )}
        </div>
      )}

      {/* Empty State */}
      {!stats && multiStats.length === 0 && !isRunning && (
        <div className="bg-slate-50 rounded-2xl border border-slate-200 p-12 text-center">
          <BarChart3 className="mx-auto text-slate-300 mb-4" size={48} />
          <p className="text-slate-400 font-bold">
            {analysisMode === 'offset' ? '点击"开始偏移量分析"运行模拟' : '点击"开始模拟"运行蒙特卡洛模拟'}
          </p>
          <p className="text-slate-300 text-sm mt-2">
            {analysisMode === 'offset'
              ? `将测试 ~${Math.floor((offsetMax - offsetMin) / offsetStep) + 1} 个偏移值，每个重复 ${numSimulations} 次`
              : analysisMode === 'single'
              ? `将生成 ${numSimulations} 次样本，每次样本量 n=${singleSampleSize}`
              : `将测试 ${getSampleSizes().length} 个样本量，每个重复 ${numSimulations} 次`
            }
          </p>
        </div>
      )}
    </div>
  )
}
