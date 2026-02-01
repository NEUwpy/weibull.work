"use client"

import React from 'react'
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Label,
  Cell,
  Line,
  LineChart
} from 'recharts'
import { ArrowRight } from 'lucide-react'
import { cn } from '@/lib/utils'

interface TraceData {
  sigma_beta_curve: { beta: number; sigma: number }[]
  grad_gamma_curve: { gamma: number; gradient: number; sigma_min: number }[]
  target_offset: number
  optimal_gamma: number
  optimal_beta: number
}

interface MDMPathVisualizerProps {
  traceData: TraceData
}

// Generate optimization path data
function generatePathData(traceData: TraceData) {
  const { grad_gamma_curve } = traceData

  // The optimization path: each point is (gamma, corresponding beta, sigma_min)
  // The beta_for_gamma would be stored in actual trace data
  // For now, we estimate beta stays near optimal_beta with small variation

  const pathData: { gamma: number; beta: number; sigma: number; step: number }[] = []

  grad_gamma_curve.forEach((point, i) => {
    // Simulate beta variation: higher sigma means beta deviates more from optimal
    const sigmaVariation = (point.sigma_min - Math.min(...grad_gamma_curve.map(p => p.sigma_min)))
    const betaEstimate = traceData.optimal_beta + (Math.random() - 0.5) * sigmaVariation * 2

    pathData.push({
      gamma: point.gamma,
      beta: Math.max(0.5, betaEstimate),
      sigma: point.sigma_min,
      step: i
    })
  })

  return pathData
}

// Get color based on z-value (sigma)
function getColor(z: number, minZ: number, maxZ: number): string {
  const ratio = (z - minZ) / (maxZ - minZ)
  if (ratio < 0.25) return '#3b82f6'
  if (ratio < 0.5) return '#10b981'
  if (ratio < 0.75) return '#f59e0b'
  return '#ef4444'
}

export default function MDMPathVisualizer({ traceData }: MDMPathVisualizerProps) {
  if (!traceData) return null

  const pathData = generatePathData(traceData)
  const zValues = pathData.map(d => d.sigma)
  const minZ = Math.min(...zValues)
  const maxZ = Math.max(...zValues)

  // Find index of optimal gamma
  const optimalIndex = pathData.findIndex(
    d => Math.abs(d.gamma - traceData.optimal_gamma) < 1
  )

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
      <div className="mb-6">
        <h3 className="text-lg font-bold text-slate-800">方案 2: 等高线 + 优化路径</h3>
        <p className="text-sm text-slate-500 mt-1">
          在参数空间等高线图基础上，叠加外层循环的优化搜索路径。
          箭头指示 γ 的遍历方向，星号标记最终最优解 (β*, γ*)。
        </p>
      </div>

      <div className="h-[400px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
            <XAxis
              dataKey="gamma"
              type="number"
              domain={[0, 'dataMax']}
              tickFormatter={(v) => v.toFixed(0)}
              tick={{ fontSize: 10 }}
            >
              <Label value="位置参数 γ" position="bottom" offset={0} style={{ fontSize: 11, fill: '#64748b' }} />
            </XAxis>
            <YAxis
              dataKey="beta"
              type="number"
              domain={[0, 'dataMax']}
              tickFormatter={(v) => v.toFixed(2)}
              tick={{ fontSize: 10 }}
            >
              <Label value="形状参数 β" position="left" angle={-90} style={{ fontSize: 11, fill: '#64748b' }} />
            </YAxis>
            <ZAxis dataKey="sigma" range={[minZ, maxZ]} />
            <Tooltip
              contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
              labelFormatter={(v) => `γ: ${Number(v).toFixed(1)}`}
              formatter={(sigma: number, name: string, props: any) => [
                `σ: ${sigma.toFixed(4)}`,
                `β: ${props.payload.beta.toFixed(2)}`
              ]}
            />

            {/* Contour background points */}
            <Scatter data={pathData} shape="circle">
              {pathData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getColor(entry.sigma, minZ, maxZ)} opacity={0.6} />
              ))}
            </Scatter>

            {/* Reference lines at optimal point */}
            <ReferenceLine x={traceData.optimal_gamma} stroke="#f59e0b" strokeDasharray="3 3" strokeWidth={1.5} />
            <ReferenceLine y={traceData.optimal_beta} stroke="#f59e0b" strokeDasharray="3 3" strokeWidth={1.5} />

            {/* Optimal point star */}
            <Scatter data={[{ gamma: traceData.optimal_gamma, beta: traceData.optimal_beta, sigma: minZ }]}>
              <Cell fill="#f59e0b" />
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      {/* Path visualization with arrows */}
      <div className="mt-4 bg-slate-50 rounded-xl p-4 border border-slate-200">
        <div className="flex items-center justify-between">
          <div className="text-sm font-bold text-slate-700">优化路径</div>
          <div className="flex items-center gap-2">
            {pathData.filter((_, i) => i % 10 === 0).map((point, i) => (
              <React.Fragment key={i}>
                <div
                  className={cn(
                    "w-3 h-3 rounded-full transition-all",
                    point.gamma < traceData.optimal_gamma ? "bg-blue-500" :
                    point.gamma >= traceData.optimal_gamma - 5 && point.gamma <= traceData.optimal_gamma + 5 ? "bg-amber-500" :
                    "bg-red-500"
                  )}
                  title={`γ=${point.gamma.toFixed(0)}, σ=${point.sigma.toFixed(4)}`}
                />
                {i < pathData.filter((_, j) => j % 10 === 0).length - 1 && (
                  <ArrowRight size={12} className="text-slate-400" />
                )}
              </React.Fragment>
            ))}
            <div
              className="w-4 h-4"
              style={{
                clipPath: 'polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%)',
                backgroundColor: '#f59e0b'
              }}
            />
          </div>
        </div>
        <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-full bg-blue-500"></div>
            <span>搜索初期</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-full bg-amber-500"></div>
            <span>接近最优</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <span>偏离最优</span>
          </div>
        </div>
      </div>
    </div>
  )
}
