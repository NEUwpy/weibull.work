"use client"

import React, { useState, useCallback } from 'react'
import { Play, RefreshCw, BarChart3, Loader2 } from 'lucide-react'
import { ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine } from 'recharts'
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
  betaRelError: number
  etaRelError: number
  gammaRelError: number
}

interface StatsSummary {
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

// Generate sample from Weibull distribution
function generateSample(n: number, beta: number, eta: number, gamma: number): DataPoint[] {
  return Array.from({ length: n }, (_, i) => {
    const u = Math.random()
    const t = gamma + eta * Math.pow(-Math.log(u), 1 / beta)
    return { id: i, value: t, status: 'F' as const }
  })
}

// Simple RRX estimation (for demonstration - in production use the actual method)
function estimateParameters(data: DataPoint[], is3P: boolean): WeibullResult {
  const gamma = is3P ? Math.min(...data.map(d => d.value)) * 0.9 : 0
  const points = calculateMedianRanks(data, gamma)
  return calculateWeibullParameters(points, gamma)
}

export default function ResultAnalysisLab({
  methodId,
  trueBeta,
  trueEta,
  trueGamma
}: ResultAnalysisLabProps) {
  const [sampleSize, setSampleSize] = useState(15)
  const [numSimulations, setNumSimulations] = useState(100)
  const [isRunning, setIsRunning] = useState(false)
  const [results, setResults] = useState<SimulationResult[]>([])
  const [stats, setStats] = useState<StatsSummary | null>(null)
  const [is3P, setIs3P] = useState(trueGamma !== 0)

  const runSimulation = useCallback(async () => {
    setIsRunning(true)
    setResults([])
    setStats(null)

    // Small delay to allow UI to update
    await new Promise(resolve => setTimeout(resolve, 50))

    const simulationResults: SimulationResult[] = []
    const betaEstimates: number[] = []
    const etaEstimates: number[] = []
    const gammaEstimates: number[] = []

    for (let i = 0; i < numSimulations; i++) {
      // Generate sample from true parameters
      const sample = generateSample(sampleSize, trueBeta, trueEta, trueGamma)

      // Estimate parameters using RRX (simplified - should use actual method)
      const estimated = estimateParameters(sample, is3P)

      // Calculate errors
      const betaError = estimated.beta - trueBeta
      const etaError = estimated.eta - trueEta
      const gammaError = estimated.gamma - trueGamma

      const betaRelError = Math.abs(betaError / trueBeta) * 100
      const etaRelError = Math.abs(etaError / trueEta) * 100
      const gammaRelError = trueGamma !== 0 ? Math.abs(gammaError / trueGamma) * 100 : 0

      simulationResults.push({
        beta: estimated.beta,
        eta: estimated.eta,
        gamma: estimated.gamma,
        betaError,
        etaError,
        gammaError,
        betaRelError,
        etaRelError,
        gammaRelError
      })

      betaEstimates.push(estimated.beta)
      etaEstimates.push(estimated.eta)
      gammaEstimates.push(estimated.gamma)

      // Update progress every 10 iterations
      if (i % 10 === 0) {
        setResults([...simulationResults])
      }
    }

    setResults(simulationResults)

    // Calculate statistics
    const calculateStats = (estimates: number[], trueValue: number) => {
      const n = estimates.length
      const mean = estimates.reduce((a, b) => a + b, 0) / n
      const variance = estimates.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / n
      const std = Math.sqrt(variance)
      const mse = estimates.reduce((a, b) => a + Math.pow(b - trueValue, 2), 0) / n
      return { mean, std, mse }
    }

    setStats({
      betaMean: calculateStats(betaEstimates, trueBeta).mean,
      betaStd: calculateStats(betaEstimates, trueBeta).std,
      betaMse: calculateStats(betaEstimates, trueBeta).mse,
      etaMean: calculateStats(etaEstimates, trueEta).mean,
      etaStd: calculateStats(etaEstimates, trueEta).std,
      etaMse: calculateStats(etaEstimates, trueEta).mse,
      gammaMean: calculateStats(gammaEstimates, trueGamma).mean,
      gammaStd: calculateStats(gammaEstimates, trueGamma).std,
      gammaMse: calculateStats(gammaEstimates, trueGamma).mse,
    })

    setIsRunning(false)
  }, [sampleSize, numSimulations, trueBeta, trueEta, trueGamma, is3P])

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6">
        <div className="flex items-center gap-4 flex-wrap">
          {/* Sample Size */}
          <div className="flex items-center gap-2">
            <label className="text-xs font-black text-slate-500 uppercase">样本量 n</label>
            <input
              type="number"
              min={5}
              max={100}
              value={sampleSize}
              onChange={(e) => setSampleSize(parseInt(e.target.value) || 15)}
              className="w-20 px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono font-bold text-center"
            />
          </div>

          {/* Number of Simulations */}
          <div className="flex items-center gap-2">
            <label className="text-xs font-black text-slate-500 uppercase">模拟次数 N</label>
            <select
              value={numSimulations}
              onChange={(e) => setNumSimulations(parseInt(e.target.value))}
              className="px-3 py-2 border border-slate-200 rounded-lg text-sm font-bold bg-white"
            >
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={500}>500</option>
              <option value={1000}>1000</option>
            </select>
          </div>

          {/* 3P Toggle */}
          {trueGamma !== 0 && (
            <div className="flex items-center gap-2">
              <label className="text-xs font-black text-slate-500 uppercase">模式</label>
              <div className="flex bg-slate-100 p-0.5 rounded-full border border-slate-200">
                <button
                  onClick={() => setIs3P(false)}
                  className={`px-3 py-1.5 text-xs font-black rounded-full transition-all ${!is3P ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500'}`}
                >
                  2P
                </button>
                <button
                  onClick={() => setIs3P(true)}
                  className={`px-3 py-1.5 text-xs font-black rounded-full transition-all ${is3P ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500'}`}
                >
                  3P
                </button>
              </div>
            </div>
          )}

          {/* Run Button */}
          <button
            onClick={runSimulation}
            disabled={isRunning}
            className="ml-auto flex items-center gap-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white rounded-xl text-sm font-bold transition-all shadow-sm"
          >
            {isRunning ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            {isRunning ? `运行中 ${results.length}/${numSimulations}` : '开始模拟'}
          </button>
        </div>
      </div>

      {/* Results */}
      {stats && (
        <>
          {/* Statistics Summary */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Beta Stats */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
                  <span className="text-sm font-black text-blue-600">β</span>
                </div>
                <span className="font-bold text-slate-900">形状参数</span>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">真实值</span>
                  <span className="font-mono font-bold text-slate-900">{trueBeta.toFixed(3)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">均值</span>
                  <span className="font-mono font-bold text-blue-600">{stats.betaMean.toFixed(3)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">标准差</span>
                  <span className="font-mono font-bold text-amber-600">{stats.betaStd.toFixed(4)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">MSE</span>
                  <span className="font-mono font-bold text-red-600">{stats.betaMse.toFixed(4)}</span>
                </div>
                <div className="flex justify-between text-sm pt-2 border-t border-slate-100">
                  <span className="text-slate-500">相对误差</span>
                  <span className="font-mono font-bold text-slate-700">{(Math.abs(stats.betaMean - trueBeta) / trueBeta * 100).toFixed(2)}%</span>
                </div>
              </div>
            </div>

            {/* Eta Stats */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center">
                  <span className="text-sm font-black text-indigo-600">η</span>
                </div>
                <span className="font-bold text-slate-900">尺度参数</span>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">真实值</span>
                  <span className="font-mono font-bold text-slate-900">{trueEta.toFixed(1)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">均值</span>
                  <span className="font-mono font-bold text-indigo-600">{stats.etaMean.toFixed(1)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">标准差</span>
                  <span className="font-mono font-bold text-amber-600">{stats.etaStd.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">MSE</span>
                  <span className="font-mono font-bold text-red-600">{stats.etaMse.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-sm pt-2 border-t border-slate-100">
                  <span className="text-slate-500">相对误差</span>
                  <span className="font-mono font-bold text-slate-700">{(Math.abs(stats.etaMean - trueEta) / trueEta * 100).toFixed(2)}%</span>
                </div>
              </div>
            </div>

            {/* Gamma Stats */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-lg bg-purple-100 flex items-center justify-center">
                  <span className="text-sm font-black text-purple-600">γ</span>
                </div>
                <span className="font-bold text-slate-900">位置参数</span>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">真实值</span>
                  <span className="font-mono font-bold text-slate-900">{trueGamma.toFixed(1)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">均值</span>
                  <span className="font-mono font-bold text-purple-600">{stats.gammaMean.toFixed(1)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">标准差</span>
                  <span className="font-mono font-bold text-amber-600">{stats.gammaStd.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">MSE</span>
                  <span className="font-mono font-bold text-red-600">{stats.gammaMse.toFixed(2)}</span>
                </div>
                {trueGamma !== 0 && (
                  <div className="flex justify-between text-sm pt-2 border-t border-slate-100">
                    <span className="text-slate-500">相对误差</span>
                    <span className="font-mono font-bold text-slate-700">{(Math.abs(stats.gammaMean - trueGamma) / trueGamma * 100).toFixed(2)}%</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Scatter Plot: Estimated vs True */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <div className="flex items-center gap-2 mb-4">
              <BarChart3 className="text-emerald-600" size={20} />
              <h3 className="font-bold text-slate-900">估计值 vs 真实值散点图</h3>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis
                    type="number"
                    dataKey="beta"
                    name="估计 β"
                    domain={['auto', 'auto']}
                    tick={{ fontSize: 11, fill: '#94a3b8' }}
                  />
                  <YAxis
                    type="number"
                    dataKey="betaError"
                    name="偏差"
                    tick={{ fontSize: 11, fill: '#94a3b8' }}
                  />
                  <Tooltip
                    cursor={{ strokeDasharray: '3 3' }}
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const p = payload[0].payload
                        return (
                          <div className="bg-white border border-slate-200 rounded-lg p-2 shadow-lg text-xs">
                            <p className="font-bold">β: {p.beta.toFixed(3)}</p>
                            <p>偏差: {p.betaError.toFixed(4)}</p>
                            <p>相对误差: {p.betaRelError.toFixed(2)}%</p>
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
            <p className="text-xs text-slate-400 mt-2 text-center">X轴: 估计值 | Y轴: 与真实值的偏差 | 绿色虚线: 真实值（无偏差）</p>
          </div>
        </>
      )}

      {/* Empty State */}
      {!stats && !isRunning && (
        <div className="bg-slate-50 rounded-2xl border border-slate-200 p-12 text-center">
          <BarChart3 className="mx-auto text-slate-300 mb-4" size={48} />
          <p className="text-slate-400 font-bold">点击"开始模拟"运行蒙特卡洛模拟</p>
          <p className="text-slate-300 text-sm mt-2">将生成 {numSimulations} 次样本，每次样本量 n={sampleSize}</p>
        </div>
      )}
    </div>
  )
}
