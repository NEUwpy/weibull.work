"use client"

import React from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ComposedChart, Area
} from 'recharts'

interface TraceItem {
  phase: string // 'init', 'iter', 'final'
  step?: number
  gamma?: number
  alpha?: number
  beta?: number // In final step
  eta?: number // In final step
  w1?: number
  w2?: number
  w3?: number
  obj_val?: number
}

interface Props {
  traceData: TraceItem[]
}

export default function WMLEVisualizer({ traceData }: Props) {
  if (!traceData || traceData.length === 0) return null

  // Filter only iteration steps for charts
  const iterData = traceData
    .filter(d => d.phase === 'iter')
    .map((d, i) => ({
      ...d,
      step: i + 1,
      obj_val: typeof d.obj_val === 'number' ? parseFloat(d.obj_val.toFixed(6)) : null,
      gamma: typeof d.gamma === 'number' ? parseFloat(d.gamma.toFixed(4)) : null,
      w3: typeof d.w3 === 'number' ? parseFloat(d.w3.toFixed(4)) : null
    }))

  // Get static weights from init step
  const initData = traceData.find(d => d.phase === 'init')
  const w1 = initData?.w1?.toFixed(4) || 'N/A'
  const w2 = initData?.w2?.toFixed(4) || 'N/A'

  return (
    <div className="space-y-8">
      
      {/* Info Cards */}
      <div className="grid grid-cols-2 gap-4">
         <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
            <span className="text-[10px] uppercase font-bold text-slate-400">静态权重 W1</span>
            <div className="text-2xl font-black text-slate-700">{w1}</div>
         </div>
         <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
            <span className="text-[10px] uppercase font-bold text-slate-400">静态权重 W2</span>
            <div className="text-2xl font-black text-slate-700">{w2}</div>
         </div>
      </div>

      {/* Chart 1: Objective Minimization */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <h3 className="text-sm font-black text-slate-700 uppercase mb-1">加权目标函数优化 (Objective Minimization)</h3>
        <p className="text-xs text-slate-500 mb-4">
          横轴：迭代次数 | 纵轴：残差平方和 (Objective Value)
          <br/>
          解释：WMLE 寻找加权方程组的根，即使得残差平方和趋近于 0。
        </p>
        <div className="h-[250px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={iterData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="step" tick={{fontSize: 10}} tickLine={false} />
              <YAxis domain={[0, 'auto']} tick={{fontSize: 10}} axisLine={false} width={40} />
              <Tooltip 
                contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}}
                itemStyle={{fontSize: '12px'}}
              />
              <Line 
                type="monotone" 
                dataKey="obj_val" 
                stroke="#ef4444" 
                strokeWidth={2}
                dot={false}
                name="Error"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Chart 2: Dynamic Weight W3 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <h3 className="text-sm font-black text-slate-700 uppercase mb-1">动态权重 W3 监测 (Dynamic Weight)</h3>
        <p className="text-xs text-slate-500 mb-4">
          横轴：迭代次数 | 左轴：形状参数 (Gamma/Beta) | 右轴：权重 W3
          <br/>
          解释：W3 不是常数，它随当前估计的形状参数动态调整，这是 WMLE 修正偏差的核心机制。
        </p>
        <div className="h-[250px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={iterData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="step" tick={{fontSize: 10}} tickLine={false} />
              <YAxis yAxisId="left" domain={['auto', 'auto']} tick={{fontSize: 10}} axisLine={false} label={{ value: 'Gamma', angle: -90, position: 'insideLeft', fontSize: 10 }} />
              <YAxis yAxisId="right" orientation="right" domain={['auto', 'auto']} tick={{fontSize: 10}} axisLine={false} label={{ value: 'W3', angle: 90, position: 'insideRight', fontSize: 10 }} />
              <Tooltip 
                contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}}
                itemStyle={{fontSize: '12px'}}
              />
              <Legend wrapperStyle={{fontSize: '12px'}} />
              <Area 
                yAxisId="right"
                type="monotone" 
                dataKey="w3" 
                fill="#dbeafe" 
                stroke="#3b82f6" 
                name="Weight W3"
              />
              <Line 
                yAxisId="left"
                type="monotone" 
                dataKey="gamma" 
                stroke="#10b981" 
                strokeWidth={2}
                dot={false}
                name="Est. Shape"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

    </div>
  )
}
