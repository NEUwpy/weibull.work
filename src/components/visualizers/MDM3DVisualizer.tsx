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
  ReferenceLine
} from 'recharts'
import { RotateCw, Maximize2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Label } from 'recharts'

interface TraceData {
  sigma_beta_curve: { beta: number; sigma: number }[]
  grad_gamma_curve: { gamma: number; gradient: number; sigma_min: number }[]
  target_offset: number
  optimal_gamma: number
  optimal_beta: number
}

interface MDM3DVisualizerProps {
  traceData: TraceData
}

type ViewAngle = 'perspective' | 'top' | 'side' | 'front'

export default function MDM3DVisualizer({ traceData }: MDM3DVisualizerProps) {
  const [viewAngle, setViewAngle] = useState<ViewAngle>('perspective')

  if (!traceData) return null

  // Generate multiple cross-section curves for 3D effect
  // Each curve represents sigma vs beta at a different gamma
  const generate3DCurves = () => {
    const curves: { name: string; data: { beta: number; sigma: number }[]; color: string; gamma: number }[] = []

    // Select key gamma points to show
    const keyGammaIndices = [0, Math.floor(traceData.grad_gamma_curve.length * 0.25), Math.floor(traceData.grad_gamma_curve.length * 0.5), Math.floor(traceData.grad_gamma_curve.length * 0.75), traceData.grad_gamma_curve.length - 1]

    keyGammaIndices.forEach((idx, i) => {
      const gammaPoint = traceData.grad_gamma_curve[idx]
      const baseSigma = gammaPoint.sigma_min

      // Generate sigma vs beta curve for this gamma
      const curveData = traceData.sigma_beta_curve.map(betaPoint => {
        // Offset sigma based on gamma (simulating 3D surface)
        const gammaOffset = (idx / traceData.grad_gamma_curve.length) * baseSigma * 0.5
        return {
          beta: betaPoint.beta,
          sigma: betaPoint.sigma + gammaOffset
        }
      })

      const isOptimal = Math.abs(gammaPoint.gamma - traceData.optimal_gamma) < 10
      curves.push({
        name: `γ=${gammaPoint.gamma.toFixed(0)}`,
        data: curveData,
        color: isOptimal ? '#f59e0b' : `hsl(${220 + i * 30}, 70%, ${50 + i * 8}%)`,
        gamma: gammaPoint.gamma
      })
    })

    return curves
  }

  const curves = generate3DCurves()

  // Get all sigma values for Y-axis domain
  const allSigmaValues = curves.flatMap(c => c.data.map(d => d.sigma))
  const minSigma = Math.min(...allSigmaValues)
  const maxSigma = Math.max(...allSigmaValues)

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-slate-800">方案 4: 三维立体视角 (伪3D)</h3>
            <p className="text-sm text-slate-500 mt-1">
              展示 {"$\\sigma_\\eta(\\beta, \\gamma)$"} 三维曲面：多条曲线代表不同 {"$\\gamma$"} 截面下的 {"$\\sigma$"} vs {"$\\beta$"} 关系。
              橙色曲线为最优 {"$\\gamma^*$"} 处的截面。
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setViewAngle('perspective')}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-bold transition-all",
                viewAngle === 'perspective' ? "bg-indigo-100 text-indigo-700" : "bg-slate-100 text-slate-500 hover:text-slate-700"
              )}
            >
              透视
            </button>
            <button
              onClick={() => setViewAngle('top')}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-bold transition-all",
                viewAngle === 'top' ? "bg-indigo-100 text-indigo-700" : "bg-slate-100 text-slate-500 hover:text-slate-700"
              )}
            >
              俯视
            </button>
            <button
              onClick={() => setViewAngle('side')}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-bold transition-all",
                viewAngle === 'side' ? "bg-indigo-100 text-indigo-700" : "bg-slate-100 text-slate-500 hover:text-slate-700"
              )}
            >
              侧视
            </button>
          </div>
        </div>
      </div>

      <div className="h-[350px] w-full relative">
        {/* 3D perspective hints */}
        {viewAngle === 'perspective' && (
          <div className="absolute inset-0 pointer-events-none">
            {/* Grid floor */}
            <svg className="w-full h-full opacity-20">
              <defs>
                <pattern id="grid3d" width="40" height="40" patternUnits="userSpaceOnUse">
                  <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#64748b" strokeWidth="0.5"/>
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#grid3d)" />
            </svg>
          </div>
        )}

        <ResponsiveContainer width="100%" height="100%">
          <LineChart margin={{ top: 20, right: 30, bottom: 30, left: 20 }}>
            <CartesianGrid
              strokeDasharray={viewAngle === 'perspective' ? "2 2" : "3 3"}
              vertical={false}
              stroke="#e2e8f0"
              opacity={viewAngle === 'perspective' ? 0.5 : 1}
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
              label={{ value: '标准差 σ_η', angle: -90, position: 'center' }}
            />
            <Tooltip
              contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
              labelFormatter={(v) => `β: ${Number(v).toFixed(2)}`}
              formatter={(value: number) => value.toFixed(4)}
            />

            {/* Reference line at optimal beta */}
            <ReferenceLine x={traceData.optimal_beta} stroke="#f59e0b" strokeDasharray="3 3" opacity={0.5} />

            {/* Multiple curves representing different gamma slices */}
            {curves.map((curve, idx) => (
              <Line
                key={curve.name}
                data={curve.data}
                type="monotone"
                dataKey="sigma"
                stroke={curve.color}
                strokeWidth={curve.gamma === traceData.optimal_gamma ? 3 : 1.5}
                strokeOpacity={viewAngle === 'top' ? 0.4 : 0.8}
                dot={false}
                activeDot={curve.gamma === traceData.optimal_gamma ? { r: 6 } : false}
                name={curve.name}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="mt-4 bg-slate-50 rounded-xl p-4 border border-slate-200">
        <div className="flex items-center justify-between">
          <div className="text-sm font-bold text-slate-700">截面曲线 (不同 γ 值)</div>
          <div className="flex items-center gap-3 flex-wrap">
            {curves.map((curve, idx) => (
              <div key={idx} className="flex items-center gap-1.5">
                <div
                  className={cn(
                    "w-8 h-0.5 rounded",
                    curve.gamma === traceData.optimal_gamma && "h-1"
                  )}
                  style={{ backgroundColor: curve.color }}
                />
                <span className={cn(
                  "text-xs",
                  curve.gamma === traceData.optimal_gamma ? "font-bold text-amber-600" : "text-slate-500"
                )}>
                  γ={curve.gamma.toFixed(0)}
                  {curve.gamma === traceData.optimal_gamma && " (最优)"}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Perspective indicator */}
        {viewAngle === 'perspective' && (
          <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
            <Maximize2 size={14} />
            <span>深度轴: γ (从小到大，从后到前)</span>
          </div>
        )}
      </div>

      {/* View mode description */}
      <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
        <RotateCw size={12} />
        <span>
          {viewAngle === 'perspective' && "透视视图: 模拟3D曲面效果"}
          {viewAngle === 'top' && "俯视图: 投影到β-σ平面，所有曲线重叠"}
          {viewAngle === 'side' && "侧视图: 强调曲线变化趋势"}
        </span>
      </div>
    </div>
  )
}
