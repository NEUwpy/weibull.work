"use client"

import React from 'react'
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
  Area,
  AreaChart
} from 'recharts'

interface TraceData {
  sigma_beta_curve: { beta: number; sigma: number }[]
  grad_gamma_curve: { gamma: number; gradient: number; sigma_min: number }[]
  target_offset: number
  optimal_gamma: number
  optimal_beta: number
}

interface MDMHistoryVisualizerProps {
  traceData: TraceData
}

export default function MDMHistoryVisualizer({ traceData }: MDMHistoryVisualizerProps) {
  if (!traceData) return null

  // Prepare history data: each iteration is a gamma candidate
  const historyData = traceData.grad_gamma_curve.map((point, index) => ({
    iteration: index + 1,
    gamma: point.gamma,
    sigma_min: point.sigma_min,
    gradient: point.gradient
  }))

  // Find optimal iteration (where gamma is closest to optimal_gamma)
  const optimalIteration = historyData.findIndex(
    d => Math.abs(d.gamma - traceData.optimal_gamma) < 1
  )

  const minSigma = Math.min(...historyData.map(d => d.sigma_min))
  const maxSigma = Math.max(...historyData.map(d => d.sigma_min))

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
      <div className="mb-6">
        <h3 className="text-lg font-bold text-slate-800">方案 3: 优化历史曲线</h3>
        <p className="text-sm text-slate-500 mt-1">
          展示外层循环遍历 {"$\\gamma$"} 候选值时，{"$\\sigma_{\\min}(\\gamma)$"} 的变化历史。
          垂直虚线标记找到最优 {"$\\gamma^*$"} 的迭代位置，曲线最低点对应最佳参数组合。
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: σ_min vs Iteration */}
        <div>
          <div className="mb-3">
            <h4 className="text-sm font-bold text-slate-700">标准差最小值 vs 迭代次数</h4>
          </div>
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={historyData} margin={{ top: 5, right: 20, bottom: 30, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="iteration"
                  tick={{ fontSize: 10 }}
                >
                  <Label value="迭代次数 (γ 候选索引)" position="bottom" offset={0} style={{ fontSize: 10, fill: '#94a3b8' }} />
                </XAxis>
                <YAxis
                  width={45}
                  tick={{ fontSize: 10 }}
                  domain={[minSigma * 0.95, maxSigma * 1.05]}
                >
                  <Label value="σ_min" position="left" angle={-90} style={{ fontSize: 10, fill: '#94a3b8' }} />
                </YAxis>
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                  labelFormatter={(v) => `迭代: ${v}`}
                  formatter={(value: number, name: string) => [
                    name === 'sigma_min' ? value.toFixed(4) : value.toFixed(2),
                    name === 'sigma_min' ? 'σ_min' : name
                  ]}
                  cursor={{ strokeDasharray: '3 3' }}
                />
                <Area
                  type="monotone"
                  dataKey="sigma_min"
                  stroke="#6366f1"
                  fill="#6366f1"
                  fillOpacity={0.3}
                  strokeWidth={2}
                />
                <ReferenceLine
                  x={optimalIteration + 1}
                  stroke="#f59e0b"
                  strokeDasharray="3 3"
                  label={{ value: `最优 γ=${traceData.optimal_gamma.toFixed(0)}`, position: 'top', fill: '#f59e0b', fontSize: 10 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Right: Gradient vs Iteration */}
        <div>
          <div className="mb-3">
            <h4 className="text-sm font-bold text-slate-700">梯度判据 vs 迭代次数</h4>
          </div>
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={historyData} margin={{ top: 5, right: 20, bottom: 30, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="iteration"
                  tick={{ fontSize: 10 }}
                >
                  <Label value="迭代次数 (γ 候选索引)" position="bottom" offset={0} style={{ fontSize: 10, fill: '#94a3b8' }} />
                </XAxis>
                <YAxis
                  width={45}
                  tick={{ fontSize: 10 }}
                />
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                  labelFormatter={(v) => `迭代: ${v}`}
                  formatter={(value: number) => value.toFixed(4)}
                  cursor={{ strokeDasharray: '3 3' }}
                />
                <ReferenceLine
                  y={traceData.target_offset}
                  stroke="#10b981"
                  strokeDasharray="3 3"
                  label={{ value: `δ=${traceData.target_offset}`, position: 'right', fill: '#10b981', fontSize: 10 }}
                />
                <ReferenceLine y={0} stroke="#cbd5e1" />
                <Line
                  type="monotone"
                  dataKey="gradient"
                  stroke="#ef4444"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 5 }}
                />
                <ReferenceLine
                  x={optimalIteration + 1}
                  stroke="#f59e0b"
                  strokeDasharray="3 3"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Stats summary */}
      <div className="mt-4 grid grid-cols-4 gap-4">
        <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
          <div className="text-xs text-slate-500">总迭代次数</div>
          <div className="text-lg font-bold text-slate-800">{historyData.length}</div>
        </div>
        <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
          <div className="text-xs text-slate-500">最优迭代</div>
          <div className="text-lg font-bold text-amber-600">#{optimalIteration + 1}</div>
        </div>
        <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
          <div className="text-xs text-slate-500">最小 σ_min</div>
          <div className="text-lg font-bold text-emerald-600">{minSigma.toFixed(4)}</div>
        </div>
        <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
          <div className="text-xs text-slate-500">最优 γ</div>
          <div className="text-lg font-bold text-blue-600">{traceData.optimal_gamma.toFixed(1)}</div>
        </div>
      </div>
    </div>
  )
}
