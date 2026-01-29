"use client"

import React from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ComposedChart, Area
} from 'recharts'

interface TraceItem {
  step: number
  beta: number
  eta: number
  gamma: number
  log_likelihood: number | null
}

interface Props {
  traceData: TraceItem[]
}

export default function MLEVisualizer({ traceData }: Props) {
  if (!traceData || traceData.length === 0) return null

  // Process data for display (e.g. filter out nulls if needed)
  const data = traceData
    .filter(d => typeof d.beta === 'number' && typeof d.eta === 'number') // Only keep valid steps
    .map(d => ({
      ...d,
      log_likelihood: d.log_likelihood ? parseFloat(d.log_likelihood.toFixed(4)) : null,
      beta: parseFloat(d.beta.toFixed(4)),
      eta: parseFloat(d.eta.toFixed(2))
    }))

  return (
    <div className="space-y-8">
      
      {/* Chart 1: Likelihood Maximization */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <h3 className="text-sm font-black text-slate-700 uppercase mb-1">似然函数优化轨迹 (Likelihood Maximization)</h3>
        <p className="text-xs text-slate-500 mb-4">
          横轴：迭代次数 (Step) | 纵轴：对数似然值 (Log-Likelihood)
          <br/>
          解释：曲线应呈现上升趋势并逐渐平缓。上升越快，说明收敛越快；震荡则意味着不稳。
        </p>
        <div className="h-[300px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="step" tick={{fontSize: 10}} tickLine={false} axisLine={{stroke: '#e2e8f0'}} />
              <YAxis domain={['auto', 'auto']} tick={{fontSize: 10}} tickLine={false} axisLine={false} width={40} />
              <Tooltip 
                contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}}
                itemStyle={{fontSize: '12px'}}
              />
              <Legend wrapperStyle={{fontSize: '12px'}} />
              <Line 
                type="monotone" 
                dataKey="log_likelihood" 
                stroke="#3b82f6" 
                strokeWidth={2}
                dot={{r: 2, fill: '#3b82f6'}}
                activeDot={{r: 6}} 
                name="Log-Likelihood"
                animationDuration={1500}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Chart 2: Parameter Convergence */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <h3 className="text-sm font-black text-slate-700 uppercase mb-1">参数收敛过程 (Parameter Convergence)</h3>
        <p className="text-xs text-slate-500 mb-4">
          横轴：迭代次数 | 左轴：形状参数 (Beta) | 右轴：尺度参数 (Eta)
          <br/>
          解释：观察算法如何在多维空间中搜索。Beta 和 Eta 通常是耦合的，一个变动会影响另一个。
        </p>
        <div className="h-[300px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="step" tick={{fontSize: 10}} tickLine={false} />
              <YAxis yAxisId="left" domain={['auto', 'auto']} tick={{fontSize: 10}} axisLine={false} label={{ value: 'Beta', angle: -90, position: 'insideLeft', fontSize: 10 }} />
              <YAxis yAxisId="right" orientation="right" domain={['auto', 'auto']} tick={{fontSize: 10}} axisLine={false} label={{ value: 'Eta', angle: 90, position: 'insideRight', fontSize: 10 }} />
              <Tooltip 
                contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}}
                itemStyle={{fontSize: '12px'}}
              />
              <Legend wrapperStyle={{fontSize: '12px'}} />
              <Line 
                yAxisId="left"
                type="monotone" 
                dataKey="beta" 
                stroke="#10b981" 
                strokeWidth={2}
                dot={false}
                name="Beta (Shape)"
              />
              <Line 
                yAxisId="right"
                type="monotone" 
                dataKey="eta" 
                stroke="#f59e0b" 
                strokeWidth={2}
                dot={false}
                strokeDasharray="5 5"
                name="Eta (Scale)"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

    </div>
  )
}
