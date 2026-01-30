"use client"

import React, { useState, useCallback } from 'react'
import { Play, RefreshCw, BarChart3, Loader2, TrendingUp } from 'lucide-react'
import {
  ResponsiveContainer,
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
  BarChart, Bar, Cell,
  LineChart, Line, Legend
} from 'recharts'
import {
  DataPoint,
  WeibullResult,
  calculateMedianRanks,
  calculateWeibullParameters
} from '@/lib/weibull'

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

interface ResultAnalysisLabProps {
  methodId: string
  trueBeta: number
  trueEta: number
  trueGamma: number
}

type SampleSizeMode = 'single' | 'range'

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
  // Sample size mode
  const [sampleSizeMode, setSampleSizeMode] = useState<SampleSizeMode>('single')
  const [singleSampleSize, setSingleSampleSize] = useState(50)
  const [sampleSizeMin, setSampleSizeMin] = useState(10)
  const [sampleSizeMax, setSampleSizeMax] = useState(200)
  const [sampleSizeStep, setSampleSizeStep] = useState(10)

  // Simulation settings
  const [numSimulations, setNumSimulations] = useState(1000)
  const [isRunning, setIsRunning] = useState(false)

  // Results
  const [results, setResults] = useState<SimulationResult[]>([])
  const [stats, setStats] = useState<StatsSummary | null>(null)
  const [multiStats, setMultiStats] = useState<MultiSampleStats[]>([])
  const [currentProgress, setCurrentProgress] = useState({ completed: 0, total: 0 })

  const getSampleSizes = useCallback(() => {
    if (sampleSizeMode === 'single') {
      return [singleSampleSize]
    }
    const sizes: number[] = []
    for (let n = sampleSizeMin; n <= sampleSizeMax; n += sampleSizeStep) {
      sizes.push(n)
    }
    return sizes
  }, [sampleSizeMode, singleSampleSize, sampleSizeMin, sampleSizeMax, sampleSizeStep])

  // Estimate parameters using backend API
  const estimateParameters = async (data: DataPoint[]): Promise<WeibullResult> => {
    try {
      const response = await fetch('http://localhost:8001/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          method: methodId,
          data: data.map(d => d.value)
        })
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

  const runSimulation = useCallback(async () => {
    setIsRunning(true)
    setResults([])
    setStats(null)
    setMultiStats([])

    // Get sample sizes
    const sampleSizes = sampleSizeMode === 'single'
      ? [singleSampleSize]
      : Array.from({ length: Math.floor((sampleSizeMax - sampleSizeMin) / sampleSizeStep) + 1 },
          (_, i) => sampleSizeMin + i * sampleSizeStep)

    const totalSimulations = sampleSizes.length * numSimulations
    setCurrentProgress({ completed: 0, total: totalSimulations })

    if (sampleSizeMode === 'single') {
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
  }, [sampleSizeMode, singleSampleSize, sampleSizeMin, sampleSizeMax, sampleSizeStep, numSimulations, trueBeta, trueEta, trueGamma, methodId])

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

        {/* Sample Size Mode */}
        <div className="mb-4">
          <div className="text-xs font-black text-slate-500 uppercase mb-2">样本量模式</div>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="sampleSizeMode"
                checked={sampleSizeMode === 'single'}
                onChange={() => setSampleSizeMode('single')}
                className="w-4 h-4 text-emerald-600"
              />
              <span className="text-sm font-bold text-slate-700">单一样本量</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="sampleSizeMode"
                checked={sampleSizeMode === 'range'}
                onChange={() => setSampleSizeMode('range')}
                className="w-4 h-4 text-emerald-600"
              />
              <span className="text-sm font-bold text-slate-700">不同样本量范围</span>
            </label>
          </div>
        </div>

        {/* Sample Size Configuration */}
        <div className="mb-4">
          {sampleSizeMode === 'single' ? (
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
          className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white rounded-xl text-sm font-bold transition-all shadow-sm"
        >
          {isRunning ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} />}
          {isRunning ? `运行中 ${currentProgress.completed}/${currentProgress.total}` : `开始模拟 (${getSampleSizes().length} × ${numSimulations} = ${getSampleSizes().length * numSimulations} 次)`}
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
              // Multi sample size mode
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200">
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
                    </tr>
                  </thead>
                  <tbody>
                    {multiStats.map((s) => (
                      <tr key={s.sampleSize} className="border-b border-slate-100">
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
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Chart 1: Histogram */}
          {stats && results.length > 0 && (
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <div className="flex items-center gap-2 mb-4">
                <BarChart3 className="text-blue-600" size={20} />
                <h3 className="font-bold text-slate-900">图1: 参数分布直方图</h3>
                <span className="text-xs text-slate-500 ml-auto">
                  n={sampleSizeMode === 'single' ? singleSampleSize : sampleSizeMin}, {numSimulations}次重复
                  {sampleSizeMode === 'range' && ' (显示第一个样本量)'}
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

          {/* Chart 2: Standard Deviation vs Sample Size (multi sample size mode) */}
          {multiStats.length > 0 && sampleSizeMode === 'range' && (
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <div className="flex items-center gap-2 mb-4">
                <BarChart3 className="text-emerald-600" size={20} />
                <h3 className="font-bold text-slate-900">图2: 标准差随样本量变化</h3>
              </div>

              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={multiStats}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis dataKey="sampleSize" label={{ value: '样本量 n', position: 'insideBottom', offset: -5 }} tick={{ fontSize: 11 }} />
                    <YAxis label={{ value: '标准差', angle: -90, position: 'insideLeft' }} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="betaStd" stroke="#3b82f6" name="β̂ 标准差" strokeWidth={2} dot={{ r: 4 }} />
                    <Line type="monotone" dataKey="etaStd" stroke="#6366f1" name="η̂ 标准差" strokeWidth={2} dot={{ r: 4 }} />
                    <Line type="monotone" dataKey="gammaStd" stroke="#a855f7" name="γ̂ 标准差" strokeWidth={2} dot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Chart 3: MSE Curve (multi sample size mode) */}
          {multiStats.length > 0 && sampleSizeMode === 'range' && (
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp className="text-red-600" size={20} />
                <h3 className="font-bold text-slate-900">图3: MSE 收敛曲线</h3>
              </div>

              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={multiStats}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis dataKey="sampleSize" label={{ value: '样本量 n', position: 'insideBottom', offset: -5 }} tick={{ fontSize: 11 }} />
                    <YAxis label={{ value: 'MSE', angle: -90, position: 'insideLeft' }} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="betaMse" stroke="#3b82f6" name="β̂ MSE" strokeWidth={2} dot={{ r: 4 }} />
                    <Line type="monotone" dataKey="etaMse" stroke="#6366f1" name="η̂ MSE" strokeWidth={2} dot={{ r: 4 }} />
                    <Line type="monotone" dataKey="gammaMse" stroke="#a855f7" name="γ̂ MSE" strokeWidth={2} dot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Chart 4: Scatter Plot (single sample size mode) */}
          {stats && results.length > 0 && sampleSizeMode === 'single' && (
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
          <p className="text-slate-400 font-bold">点击"开始模拟"运行蒙特卡洛模拟</p>
          <p className="text-slate-300 text-sm mt-2">
            {sampleSizeMode === 'single'
              ? `将生成 ${numSimulations} 次样本，每次样本量 n=${singleSampleSize}`
              : `将测试 ${getSampleSizes().length} 个样本量，每个重复 ${numSimulations} 次`
            }
          </p>
        </div>
      )}
    </div>
  )
}
