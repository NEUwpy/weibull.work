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
  Label,
  Legend,
  ComposedChart
} from 'recharts'
import { cn } from '@/lib/utils'

interface TraceData {
  sigma_beta_curve: { beta: number; sigma: number }[]
  grad_gamma_curve: { gamma: number; gradient: number; sigma_min: number; best_beta?: number; best_eta?: number }[]
  target_offset: number
  optimal_gamma: number
  optimal_beta: number
}

interface MDMOffsetAnalyzerProps {
  traceData: TraceData
}

/**
 * Offset Analysis Visualizer
 *
 * Shows how different offset values affect the estimated parameters (β, γ)
 *
 * Uses the actual best_beta values from the gradient curve data.
 */
export default function MDMOffsetAnalyzer({ traceData }: MDMOffsetAnalyzerProps) {
  const [showBeta, setShowBeta] = React.useState(true)
  const [showGamma, setShowGamma] = React.useState(true)
  const [showEta, setShowEta] = React.useState(true)
  const [showSigma, setShowSigma] = React.useState(false)

  // Check if backend is returning best_beta and best_eta
  const hasBestBeta = traceData.grad_gamma_curve.length > 0 && 'best_beta' in traceData.grad_gamma_curve[0]
  const hasBestEta = traceData.grad_gamma_curve.length > 0 && 'best_eta' in traceData.grad_gamma_curve[0]

  // Generate offset analysis data
  const offsetAnalysis = useMemo(() => {
    const { grad_gamma_curve } = traceData

    // Sort by gradient to ensure proper interpolation
    const sortedCurve = [...grad_gamma_curve].sort((a, b) => a.gradient - b.gradient)

    const gammas = sortedCurve.map(d => d.gamma)
    const grads = sortedCurve.map(d => d.gradient)
    const sigma_mins = sortedCurve.map(d => d.sigma_min)
    const best_betas = sortedCurve.map(d => d.best_beta ?? traceData.optimal_beta)

    // Find min/max gradient for offset range
    const minGrad = Math.min(...grads)
    const maxGrad = Math.max(...grads)

    // Generate offset values to test
    const offsetRange: number[] = []
    const step = (maxGrad - minGrad) / 100
    for (let o = minGrad; o <= maxGrad * 1.05; o += step) {
      offsetRange.push(o)
    }

    // For each offset, find the corresponding gamma via interpolation
    const results: {
      offset: number
      gamma: number
      beta: number
      eta: number
      sigma: number
    }[] = []

    for (const offset of offsetRange) {
      // Find where gradient = offset (or closest point)
      let foundGamma: number
      let foundBeta: number
      let foundEta: number
      let foundSigma: number

      // Binary search or linear interpolation
      if (offset <= grads[0]) {
        foundGamma = gammas[0]
        foundBeta = best_betas[0]
        foundEta = sortedCurve[0].best_eta ?? 100
        foundSigma = sigma_mins[0]
      } else if (offset >= grads[grads.length - 1]) {
        foundGamma = gammas[grads.length - 1]
        foundBeta = best_betas[grads.length - 1]
        foundEta = sortedCurve[grads.length - 1].best_eta ?? 100
        foundSigma = sigma_mins[grads.length - 1]
      } else {
        // Find the interval and interpolate
        let idx = 0
        for (let i = 0; i < grads.length - 1; i++) {
          if (grads[i] <= offset && grads[i + 1] >= offset) {
            idx = i
            break
          }
        }

        // Linear interpolation
        const t_param = (offset - grads[idx]) / (grads[idx + 1] - grads[idx])
        foundGamma = gammas[idx] + t_param * (gammas[idx + 1] - gammas[idx])
        foundBeta = best_betas[idx] + t_param * (best_betas[idx + 1] - best_betas[idx])
        foundSigma = sigma_mins[idx] + t_param * (sigma_mins[idx + 1] - sigma_mins[idx])

        // Interpolate eta if available
        const eta1 = sortedCurve[idx].best_eta
        const eta2 = sortedCurve[idx + 1].best_eta
        if (eta1 !== undefined && eta2 !== undefined) {
          foundEta = eta1 + t_param * (eta2 - eta1)
        } else {
          foundEta = 100
        }
      }

      results.push({
        offset,
        gamma: foundGamma,
        beta: foundBeta,
        eta: foundEta,
        sigma: foundSigma
      })
    }

    return results
  }, [traceData])

  // Find the data point corresponding to current offset
  const currentOffsetData = useMemo(() => {
    const idx = offsetAnalysis.findIndex(
      d => Math.abs(d.offset - traceData.target_offset) <= (offsetAnalysis[1]?.offset - offsetAnalysis[0]?.offset) / 2
    )
    return idx >= 0 ? offsetAnalysis[idx] : null
  }, [offsetAnalysis, traceData.target_offset])

  // Calculate stability (rate of change)
  const stabilityData = useMemo(() => {
    return offsetAnalysis.map((d, i) => ({
      ...d,
      gammaChange: i > 0 ? Math.abs(d.gamma - offsetAnalysis[i - 1].gamma) : 0,
      betaChange: i > 0 ? Math.abs(d.beta - offsetAnalysis[i - 1].beta) : 0
    }))
  }, [offsetAnalysis])

  if (!hasBestBeta || !hasBestEta) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-2xl p-8 text-center">
        <p className="text-yellow-800 font-bold mb-2">数据不完整</p>
        <p className="text-yellow-700 text-sm">
          后端未返回 best_beta 或 best_eta 数据。请更新 Python 后端代码后重新计算。
        </p>
        <p className="text-yellow-600 text-xs mt-2 font-mono">
          在 python/methods/mdm.py 的 grad_gamma_curve 中添加 "best_beta" 和 "best_eta" 字段
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <h3 className="text-lg font-bold text-slate-800 mb-2">偏移量敏感性分析</h3>
        <p className="text-sm text-slate-500">
          展示不同梯度偏移值 {"$\\delta$"} 对估计参数的影响。
          橙色虚线标示当前使用的偏移值 ({traceData.target_offset})。
        </p>
      </div>

      {/* Parameter Controls */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-6 flex-wrap">
          <span className="text-sm font-bold text-slate-700">显示参数：</span>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={showGamma}
              onChange={(e) => setShowGamma(e.target.checked)}
              className="w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm text-slate-600">γ (位置参数)</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={showBeta}
              onChange={(e) => setShowBeta(e.target.checked)}
              className="w-4 h-4 rounded border-slate-300 text-red-600 focus:ring-red-500"
            />
            <span className="text-sm text-slate-600">β (形状参数)</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={showEta}
              onChange={(e) => setShowEta(e.target.checked)}
              className="w-4 h-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
            />
            <span className="text-sm text-slate-600">η (尺度参数)</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={showSigma}
              onChange={(e) => setShowSigma(e.target.checked)}
              className="w-4 h-4 rounded border-slate-300 text-purple-600 focus:ring-purple-500"
            />
            <span className="text-sm text-slate-600">σ_η (标准差)</span>
          </label>
        </div>
      </div>

      {/* Main Chart: Parameters vs Offset */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-base font-bold text-slate-800">参数随偏移量变化</h4>
          {currentOffsetData && (
            <div className="text-xs text-slate-600">
              δ={traceData.target_offset} 时:
              <span className="ml-2 font-bold text-blue-600">γ={currentOffsetData.gamma.toFixed(2)}</span>
              <span className="ml-2 font-bold text-red-600">β={currentOffsetData.beta.toFixed(2)}</span>
              <span className="ml-2 font-bold text-emerald-600">η={currentOffsetData.eta.toFixed(2)}</span>
            </div>
          )}
        </div>

        <div className="h-[400px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={offsetAnalysis} margin={{ top: 20, right: 30, bottom: 20, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
              <XAxis
                dataKey="offset"
                type="number"
                domain={['dataMin', 'dataMax']}
                tickFormatter={(v) => v.toFixed(3)}
                tick={{ fontSize: 11 }}
              >
                <Label value="偏移量 δ" position="bottom" offset={0} style={{ fontSize: 11, fill: '#94a3b8' }} />
              </XAxis>
              <YAxis
                yAxisId="params"
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => v.toFixed(2)}
              >
                <Label value="参数值" position="left" angle={-90} style={{ fontSize: 11, fill: '#94a3b8' }} />
              </YAxis>
              <YAxis
                yAxisId="sigma"
                orientation="right"
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => v.toFixed(4)}
              />
              <Tooltip
                contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                labelFormatter={(v) => `δ = ${Number(v).toFixed(4)}`}
                formatter={(v: number, name: string) => {
                  const labels: Record<string, string> = {
                    beta: 'β',
                    gamma: 'γ',
                    eta: 'η',
                    sigma: 'σ_η'
                  }
                  const colors: Record<string, string> = {
                    beta: '#ef4444',
                    gamma: '#3b82f6',
                    eta: '#10b981',
                    sigma: '#8b5cf6'
                  }
                  return [<span key={name} style={{ color: colors[name] }}>{v.toFixed(4)}</span>, labels[name] || name]
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />

              {/* Current offset reference */}
              <ReferenceLine
                x={traceData.target_offset}
                stroke="#f59e0b"
                strokeDasharray="4 4"
                yAxisId="params"
                label={{
                  position: 'topLeft',
                  value: `当前 δ=${traceData.target_offset}`,
                  fill: '#f59e0b',
                  fontSize: 11,
                  fontWeight: 'bold'
                }}
              />

              {showGamma && (
                <Line
                  yAxisId="params"
                  type="monotone"
                  dataKey="gamma"
                  stroke="#3b82f6"
                  strokeWidth={2.5}
                  dot={false}
                  name="γ (位置参数)"
                  activeDot={{ r: 6 }}
                />
              )}
              {showBeta && (
                <Line
                  yAxisId="params"
                  type="monotone"
                  dataKey="beta"
                  stroke="#ef4444"
                  strokeWidth={2.5}
                  dot={false}
                  name="β (形状参数)"
                  activeDot={{ r: 6 }}
                />
              )}
              {showEta && (
                <Line
                  yAxisId="params"
                  type="monotone"
                  dataKey="eta"
                  stroke="#10b981"
                  strokeWidth={2.5}
                  dot={false}
                  name="η (尺度参数)"
                  activeDot={{ r: 6 }}
                />
              )}
              {showSigma && (
                <Line
                  yAxisId="sigma"
                  type="monotone"
                  dataKey="sigma"
                  stroke="#8b5cf6"
                  strokeWidth={2}
                  dot={false}
                  name="σ_η (标准差)"
                  activeDot={{ r: 6 }}
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Stability Analysis */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <h4 className="text-base font-bold text-slate-800 mb-4">参数稳定性分析 (变化率)</h4>
        <div className="h-[250px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={stabilityData} margin={{ top: 5, right: 30, bottom: 20, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
              <XAxis
                dataKey="offset"
                type="number"
                domain={['dataMin', 'dataMax']}
                tickFormatter={(v) => v.toFixed(3)}
                tick={{ fontSize: 11 }}
              >
                <Label value="偏移量 δ" position="bottom" offset={0} style={{ fontSize: 11, fill: '#94a3b8' }} />
              </XAxis>
              <YAxis
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => v.toFixed(4)}
              >
                <Label value="变化率 |d(param)/dδ|" position="left" angle={-90} style={{ fontSize: 10, fill: '#94a3b8' }} />
              </YAxis>
              <Tooltip
                contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                labelFormatter={(v) => `δ = ${Number(v).toFixed(4)}`}
                formatter={(v: number, name: string) => [v.toFixed(5), name === 'gammaChange' ? '|dγ/dδ|' : '|dβ/dδ|']}
              />
              <ReferenceLine
                x={traceData.target_offset}
                stroke="#f59e0b"
                strokeDasharray="3 3"
                label={{ position: 'top', value: `当前`, fill: '#f59e0b', fontSize: 10 }}
              />
              <Legend wrapperStyle={{ fontSize: 10 }} />

              <Line
                type="monotone"
                dataKey="gammaChange"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={false}
                name="|dγ/dδ|"
              />
              <Line
                type="monotone"
                dataKey="betaChange"
                stroke="#ef4444"
                strokeWidth={2}
                dot={false}
                name="|dβ/dδ|"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="text-xs text-slate-500 mt-3">
          曲线越低表示参数越稳定。选择 {"$|d\\gamma/d\\delta|$"} 和 {"$|d\\beta/d\\delta|$"} 都较小的偏移范围。
        </p>
      </div>

      {/* Current vs Recommended */}
      <div className="bg-slate-50 p-6 rounded-2xl border border-slate-200">
        <h4 className="text-base font-bold text-slate-800 mb-4">当前偏移值结果</h4>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-white p-4 rounded-xl border border-slate-200">
            <div className="text-xs font-bold text-slate-400 uppercase">当前偏移 δ</div>
            <div className="text-xl font-black text-slate-800 mt-1">{traceData.target_offset.toFixed(3)}</div>
          </div>
          <div className="bg-white p-4 rounded-xl border border-slate-200">
            <div className="text-xs font-bold text-slate-400 uppercase">估计 γ</div>
            <div className="text-xl font-black text-blue-600 mt-1">{currentOffsetData?.gamma.toFixed(2) ?? traceData.optimal_gamma.toFixed(2)}</div>
          </div>
          <div className="bg-white p-4 rounded-xl border border-slate-200">
            <div className="text-xs font-bold text-slate-400 uppercase">估计 β</div>
            <div className="text-xl font-black text-red-600 mt-1">{currentOffsetData?.beta.toFixed(2) ?? traceData.optimal_beta.toFixed(2)}</div>
          </div>
          <div className="bg-white p-4 rounded-xl border border-slate-200">
            <div className="text-xs font-bold text-slate-400 uppercase">估计 η</div>
            <div className="text-xl font-black text-emerald-600 mt-1">{currentOffsetData?.eta.toFixed(2) ?? '--'}</div>
          </div>
          <div className="bg-white p-4 rounded-xl border border-slate-200">
            <div className="text-xs font-bold text-slate-400 uppercase">最小 σ_η</div>
            <div className="text-xl font-black text-purple-600 mt-1">{currentOffsetData?.sigma.toFixed(4) ?? Math.min(...traceData.grad_gamma_curve.map(d => d.sigma_min)).toFixed(4)}</div>
          </div>
        </div>

        {/* Interpretation */}
        <div className="mt-4 p-4 bg-white rounded-xl border border-slate-200">
          <div className="text-sm text-slate-700">
            <strong>当前结果解释：</strong>
            当 δ = {traceData.target_offset} 时，梯度判据选择 γ = {currentOffsetData?.gamma.toFixed(2) ?? 'N/A'}，
            对应 β = {currentOffsetData?.beta.toFixed(2) ?? 'N/A'}，
            η = {currentOffsetData?.eta.toFixed(2) ?? 'N/A'}。
            {currentOffsetData && currentOffsetData.gamma < 0.1
              ? " ⚠️ γ 接近 0，此时退化为两参数威布尔分布。"
              : currentOffsetData && currentOffsetData.gamma > 0
              ? ` γ = ${currentOffsetData.gamma.toFixed(2)} > 0，三参数拟合有效。`
              : ''}
          </div>
        </div>
      </div>
    </div>
  )
}
