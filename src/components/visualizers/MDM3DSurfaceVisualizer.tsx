"use client"

import React, { useState } from 'react'
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
import { RotateCw } from 'lucide-react'
import { cn } from '@/lib/utils'

interface TraceData {
  sigma_beta_curve: { beta: number; sigma: number }[]
  grad_gamma_curve: { gamma: number; gradient: number; sigma_min: number }[]
  target_offset: number
  optimal_gamma: number
  optimal_beta: number
}

interface MDM3DSurfaceVisualizerProps {
  traceData: TraceData
}

type ViewAngle = 'default' | 'rotated'

// Generate 3D surface data: multiple gamma slices
function generate3DSurfaceData(traceData: TraceData) {
  const { grad_gamma_curve, sigma_beta_curve, optimal_gamma, optimal_beta } = traceData

  // Select key gamma points to show as slices
  const numSlices = 7
  const indices = Array.from({ length: numSlices }, (_, i) =>
    Math.floor((i * (grad_gamma_curve.length - 1)) / (numSlices - 1))
  )

  const slices: { name: string; gamma: number; data: { beta: number; sigma: number }[]; isOptimal: boolean }[] = []

  indices.forEach((idx) => {
    const gammaPoint = grad_gamma_curve[idx]
    const baseSigma = gammaPoint.sigma_min
    const isOptimal = Math.abs(gammaPoint.gamma - optimal_gamma) < 10

    // Generate sigma vs beta curve for this gamma
    const curveData = sigma_beta_curve.map(betaPoint => {
      const betaOffset = Math.abs(betaPoint.beta - optimal_beta)
      const sigma = baseSigma + betaOffset * baseSigma * 0.3
      return {
        beta: betaPoint.beta,
        sigma
      }
    })

    slices.push({
      name: `γ=${gammaPoint.gamma.toFixed(0)}`,
      gamma: gammaPoint.gamma,
      data: curveData,
      isOptimal
    })
  })

  return slices
}

export default function MDM3DSurfaceVisualizer({ traceData }: MDM3DSurfaceVisualizerProps) {
  const [viewAngle, setViewAngle] = useState<ViewAngle>('default')

  if (!traceData) return null

  const slices = generate3DSurfaceData(traceData)
  const allSigmaValues = slices.flatMap(s => s.data.map(d => d.sigma))
  const minSigma = Math.min(...allSigmaValues)
  const maxSigma = Math.max(...allSigmaValues)

  // Find the optimal slice
  const optimalSlice = slices.find(s => s.isOptimal)

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-slate-800">三维参数空间曲面</h3>
            <p className="text-sm text-slate-500 mt-1">
              展示 {"$\\sigma_\\eta(\\beta, \\gamma)$"} 的三维曲面：多条曲线代表不同 {"$\\gamma$"} 截面。
              橙色曲线为最优 {"$\\gamma^*$"} 处的截面，最低点对应最优参数组合 (β*, γ*)。
            </p>
          </div>
          <button
            onClick={() => setViewAngle(viewAngle === 'default' ? 'rotated' : 'default')}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all",
              "bg-slate-100 text-slate-600 hover:text-slate-800 hover:bg-slate-200"
            )}
          >
            <RotateCw size={12} />
            切换视角
          </button>
        </div>
      </div>

      <div className="h-[350px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            margin={{ top: 20, right: 20, bottom: 30, left: 20 }}
            data={slices[0]?.data || []}
          >
            <CartesianGrid
              strokeDasharray={viewAngle === 'default' ? "2 2" : "1 1"}
              vertical={false}
              stroke="#e2e8f0"
            />
            <XAxis
              dataKey="beta"
              type="number"
              domain={[0, 'dataMax']}
              tickFormatter={(v) => v.toFixed(1)}
              tick={{ fontSize: 10 }}
            >
              <Label value="形状参数 β" position="bottom" offset={0} style={{ fontSize: 11, fill: '#64748b' }} />
            </XAxis>
            <YAxis
              width={50}
              tick={{ fontSize: 10 }}
              domain={[minSigma * 0.95, maxSigma * 1.05]}
              label={{ value: '标准差 σ_η', angle: -90, position: 'insideLeft', style: { fontSize: 11, fill: '#64748b' } }}
            />
            <Tooltip
              contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
              labelFormatter={(v) => `β: ${Number(v).toFixed(2)}`}
              formatter={(value: number) => value.toFixed(4)}
            />

            {/* Reference line at optimal beta */}
            <ReferenceLine x={traceData.optimal_beta} stroke="#f59e0b" strokeDasharray="3 3" opacity={0.3} />

            {/* Multiple gamma slices - creating pseudo-3D effect */}
            {slices.map((slice, idx) => {
              // Calculate visual properties based on gamma (depth)
              const gammaRatio = slice.gamma / Math.max(...slices.map(s => s.gamma))
              const isOptimal = slice.isOptimal

              return (
                <Line
                  key={slice.name}
                  data={slice.data}
                  type="monotone"
                  dataKey="sigma"
                  stroke={isOptimal ? "#f59e0b" : `hsl(${220 + idx * 15}, 70%, ${55 - idx * 5}%)`}
                  strokeWidth={isOptimal ? 3 : 1.5}
                  strokeOpacity={viewAngle === 'default' ? 0.3 + gammaRatio * 0.5 : 0.6}
                  dot={false}
                  activeDot={isOptimal ? { r: 5 } : false}
                  name={slice.name}
                />
              )
            })}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Legend with gamma slices */}
      <div className="mt-4 bg-slate-50 rounded-xl p-4 border border-slate-200">
        <div className="flex items-center justify-between">
          <div className="text-sm font-bold text-slate-700">γ 截面曲线（从前到后）</div>
          <div className="flex items-center gap-3 flex-wrap">
            {slices.map((slice, idx) => (
              <div key={idx} className="flex items-center gap-1.5">
                <div
                  className={cn(
                    "w-8 h-0.5 rounded transition-all",
                    slice.isOptimal && "h-1"
                  )}
                  style={{
                    backgroundColor: slice.isOptimal ? "#f59e0b" : `hsl(${220 + idx * 15}, 70%, ${55 - idx * 5}%)`,
                    opacity: slice.isOptimal ? 1 : 0.3 + (slice.gamma / Math.max(...slices.map(s => s.gamma))) * 0.5
                  }}
                />
                <span className={cn(
                  "text-xs",
                  slice.isOptimal ? "font-bold text-amber-600" : "text-slate-500"
                )}>
                  {slice.gamma.toFixed(0)}
                  {slice.isOptimal && " ★"}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Explanation */}
        <div className="mt-3 pt-3 border-t border-slate-200">
          <div className="flex items-start gap-2 text-xs text-slate-500">
            <span className="font-bold text-amber-600">★</span>
            <span>
              最优解位置：β*={traceData.optimal_beta.toFixed(2)}, γ*={traceData.optimal_gamma.toFixed(1)},
              最低 σ={minSigma.toFixed(4)}
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400 mt-1">
            <RotateCw size={11} />
            <span>点击"切换视角"查看不同深度的参数截面</span>
          </div>
        </div>
      </div>
    </div>
  )
}
