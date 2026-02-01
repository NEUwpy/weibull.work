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
import MDM3DSurfaceVisualizer from './MDM3DSurfaceVisualizer'
import { cn } from '@/lib/utils'

interface TraceData {
  sigma_beta_curve: { beta: number; sigma: number }[]
  grad_gamma_curve: { gamma: number; gradient: number; sigma_min: number }[]
  target_offset: number
  optimal_gamma: number
  optimal_beta: number
}

interface MDMVisualizerProps {
  traceData: TraceData
}

export default function MDMVisualizer({ traceData }: MDMVisualizerProps) {
  const [activeScheme, setActiveScheme] = useState<'original' | '3d'>('original')

  if (!traceData) return null

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Scheme Selector */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-sm font-bold text-slate-700">寻优过程可视化：</span>
          <div className="flex bg-slate-100 p-1 rounded-lg border border-slate-200">
            <button
              onClick={() => setActiveScheme('original')}
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
              onClick={() => setActiveScheme('3d')}
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
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

        {/* Chart 1: Sigma vs Beta (at optimal Gamma) */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="mb-6">
            <h3 className="text-lg font-bold text-slate-800">形状参数寻优 (固定 γ={traceData.optimal_gamma.toFixed(2)})</h3>
            <p className="text-sm text-slate-500 mt-1">
              展示在最佳置参数下，尺度参数标准差 {"$\\sigma_{\\eta}$"} 随形状参数 {"$\\beta$"} 的变化。
              最低点对应最佳 {"$\\beta$"}。
            </p>
          </div>
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={traceData.sigma_beta_curve} margin={{ top: 5, right: 20, bottom: 20, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="beta"
                  type="number"
                  domain={['auto', 'auto']}
                  tickFormatter={(v) => v.toFixed(2)}
                  tick={{ fontSize: 10 }}
                >
                  <Label value="形状参数 β" position="bottom" offset={0} style={{ fontSize: 10, fill: '#94a3b8' }} />
                </XAxis>
                <YAxis
                  width={40}
                  tick={{ fontSize: 10 }}
                  domain={['auto', 'auto']}
                />
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                  labelFormatter={(v) => `β: ${Number(v).toFixed(3)}`}
                  formatter={(v: number) => [v.toFixed(4), 'σ_η']}
                />
                <Line
                  type="monotone"
                  dataKey="sigma"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 6 }}
                />
                <ReferenceLine x={traceData.optimal_beta} stroke="#f59e0b" strokeDasharray="3 3">
                   <Label value="最优 β" position="top" fill="#f59e0b" fontSize={10} />
                </ReferenceLine>
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Gradient vs Gamma */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="mb-6">
            <h3 className="text-lg font-bold text-slate-800">位置参数梯度判据</h3>
            <p className="text-sm text-slate-500 mt-1">
              {"$\\nabla(\\gamma)$"} 曲线与补偿阈值 {"$\\delta$"}={traceData.target_offset} 的交点即为最佳位置参数。
              偏移值的引入提高了小样本估计的稳健性。
            </p>
          </div>
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={traceData.grad_gamma_curve} margin={{ top: 5, right: 20, bottom: 20, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="gamma"
                  type="number"
                  domain={['auto', 'auto']}
                  tickFormatter={(v) => v.toFixed(0)}
                  tick={{ fontSize: 10 }}
                >
                  <Label value="位置参数 γ" position="bottom" offset={0} style={{ fontSize: 10, fill: '#94a3b8' }} />
                </XAxis>
                <YAxis
                  width={40}
                  tick={{ fontSize: 10 }}
                />
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                  labelFormatter={(v) => `γ: ${Number(v).toFixed(1)}`}
                  formatter={(v: number) => [v.toFixed(4), '∇(γ)']}
                />
                <ReferenceLine y={traceData.target_offset} stroke="#10b981" strokeDasharray="3 3" label={{ position: 'right', value: `δ=${traceData.target_offset}`, fill: '#10b981', fontSize: 10 }} />
                <ReferenceLine y={0} stroke="#cbd5e1" />
                <Line
                  type="monotone"
                  dataKey="gradient"
                  stroke="#ef4444"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 6 }}
                />
                <ReferenceLine x={traceData.optimal_gamma} stroke="#f59e0b" strokeDasharray="3 3">
                </ReferenceLine>
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>
      )}

      {/* 3D Surface Plot */}
      {activeScheme === '3d' && (
        <MDM3DSurfaceVisualizer traceData={traceData} />
      )}
    </div>
  )
}
