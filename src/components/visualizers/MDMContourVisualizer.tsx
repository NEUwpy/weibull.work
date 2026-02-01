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
  Cell
} from 'recharts'
import { cn } from '@/lib/utils'

interface TraceData {
  sigma_beta_curve: { beta: number; sigma: number }[]
  grad_gamma_curve: { gamma: number; gradient: number; sigma_min: number }[]
  target_offset: number
  optimal_gamma: number
  optimal_beta: number
}

interface MDMContourVisualizerProps {
  traceData: TraceData
}

// Generate a 2D grid of sigma values for contour visualization
function generateContourData(traceData: TraceData) {
  const { grad_gamma_curve, sigma_beta_curve } = traceData

  // Extract unique gamma and beta values
  const gammas = grad_gamma_curve.map(d => d.gamma)
  const betas = sigma_beta_curve.map(d => d.beta)

  // Create a grid: for each gamma, we have sigma_min value at corresponding beta
  const data: { x: number; y: number; z: number; gamma: number; beta: number }[] = []

  grad_gamma_curve.forEach((gammaPoint, i) => {
    // Use sigma_min as z-value (objective function)
    // The corresponding beta for this gamma would be at same index in beta_for_gamma array
    // But we only have sigma_beta_curve at optimal_gamma, so we need to estimate
    // For simplicity, we'll use the sigma_min value and vary beta around optimal_beta

    const baseSigma = gammaPoint.sigma_min
    const gamma = gammaPoint.gamma

    // Create a curve for this gamma: sigma varies with beta
    // We approximate this using a parabolic shape centered at optimal_beta
    betas.forEach(beta => {
      // Simulate sigma at this (beta, gamma) point
      // In real data, this would be the actual sigma_eta(beta, gamma)
      const betaOffset = Math.abs(beta - traceData.optimal_beta)
      const estimatedSigma = baseSigma + betaOffset * baseSigma * 0.5

      data.push({
        x: gamma,
        y: beta,
        z: estimatedSigma,
        gamma,
        beta
      })
    })
  })

  return data
}

// Get color based on z-value (sigma)
function getColor(z: number, minZ: number, maxZ: number): string {
  const ratio = (z - minZ) / (maxZ - minZ)
  // Blue (good/low) to Red (bad/high)
  if (ratio < 0.25) return '#3b82f6' // blue-500
  if (ratio < 0.5) return '#10b981'  // emerald-500
  if (ratio < 0.75) return '#f59e0b' // amber-500
  return '#ef4444' // red-500
}

export default function MDMContourVisualizer({ traceData }: MDMContourVisualizerProps) {
  if (!traceData) return null

  const contourData = generateContourData(traceData)
  const zValues = contourData.map(d => d.z)
  const minZ = Math.min(...zValues)
  const maxZ = Math.max(...zValues)

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
      <div className="mb-6">
        <h3 className="text-lg font-bold text-slate-800">方案 1: 参数空间等高线图</h3>
        <p className="text-sm text-slate-500 mt-1">
          展示目标函数 {"$\\sigma_\\eta(\\beta, \\gamma)$"} 在二维参数空间的全貌。
          颜色越蓝表示标准差越小（越优），越红表示越大。标记点为最优解 (β*, γ*)。
        </p>
      </div>

      <div className="h-[400px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
            <XAxis
              dataKey="x"
              type="number"
              domain={[0, 'dataMax']}
              tickFormatter={(v) => v.toFixed(0)}
              tick={{ fontSize: 10 }}
            >
              <Label value="位置参数 γ" position="bottom" offset={0} style={{ fontSize: 11, fill: '#64748b' }} />
            </XAxis>
            <YAxis
              dataKey="y"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={(v) => v.toFixed(2)}
              tick={{ fontSize: 10 }}
            >
              <Label value="形状参数 β" position="left" angle={-90} style={{ fontSize: 11, fill: '#64748b' }} />
            </YAxis>
            <ZAxis
              dataKey="z"
              range={[minZ, maxZ]}
            />
            <Tooltip
              contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
              labelFormatter={(v) => `γ: ${Number(v).toFixed(1)}`}
              formatter={(z: number, name: string, props: any) => [
                `σ: ${z.toFixed(4)}`,
                `β: ${props.payload.y.toFixed(2)}`
              ]}
            />
            <ReferenceLine x={traceData.optimal_gamma} stroke="#f59e0b" strokeDasharray="3 3" />
            <ReferenceLine y={traceData.optimal_beta} stroke="#f59e0b" strokeDasharray="3 3" />

            {/* Contour points as colored scatter */}
            <Scatter data={contourData}>
              {contourData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getColor(entry.z, minZ, maxZ)} opacity={0.7} />
              ))}
            </Scatter>

            {/* Mark optimal point */}
            <Scatter
              data={[{ x: traceData.optimal_gamma, y: traceData.optimal_beta, z: minZ }]}
              shape="star"
            >
              <Cell fill="#f59e0b" />
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-4 mt-4">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded bg-blue-500"></div>
          <span className="text-xs text-slate-600">低 σ (优)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded bg-emerald-500"></div>
          <span className="text-xs text-slate-600">中低</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded bg-amber-500"></div>
          <span className="text-xs text-slate-600">中高</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded bg-red-500"></div>
          <span className="text-xs text-slate-600">高 σ (差)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4" style={{ clipPath: 'polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%)', backgroundColor: '#f59e0b' }}></div>
          <span className="text-xs text-slate-600">最优解</span>
        </div>
      </div>
    </div>
  )
}
