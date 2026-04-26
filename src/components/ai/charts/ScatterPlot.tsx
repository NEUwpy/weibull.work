/**
 * 通用散点图组件 — 用于展示两个变量之间的关系
 *
 * 复用于：D3(δ vs 均值), D4(δ vs 标准差), D5(δ vs 变异系数), P1(预测vs真实)
 * 设计：只输出图表，外框由 ChartCard 提供
 */
"use client"

import React from 'react'
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'

interface ScatterPlotProps {
  data: { x: number; y: number }[]
  xLabel?: string
  yLabel?: string
  color?: string
  showDiagonal?: boolean  // 显示 y=x 对角线参考线
  xDomain?: [number, number]
  yDomain?: [number, number]
}

export function ScatterPlot({
  data,
  xLabel = '',
  yLabel = '',
  color = '#8b5cf6',
  showDiagonal = false,
  xDomain,
  yDomain,
}: ScatterPlotProps) {
  if (!data || data.length === 0) {
    return (
      <div className="h-[280px] flex items-center justify-center text-slate-400">
        无有效数据
      </div>
    )
  }

  const allX = data.map(d => d.x)
  const allY = data.map(d => d.y)
  const autoXDomain = xDomain || [Math.min(...allX) * 0.95, Math.max(...allX) * 1.05]
  const autoYDomain = yDomain || [Math.min(...allY) * 0.95, Math.max(...allY) * 1.05]
  const diagMin = Math.min(autoXDomain[0], autoYDomain[0])
  const diagMax = Math.max(autoXDomain[1], autoYDomain[1])

  return (
    <div className="h-[280px]">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 10, right: 20, bottom: 30, left: 50 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis
            type="number"
            dataKey="x"
            domain={autoXDomain}
            tick={{ fontSize: 10 }}
            label={{ value: xLabel, position: 'bottom', offset: 0, fontSize: 11 }}
          />
          <YAxis
            type="number"
            dataKey="y"
            domain={autoYDomain}
            tick={{ fontSize: 10 }}
            label={{ value: yLabel, angle: -90, position: 'insideLeft', fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{ borderRadius: '4px', border: '1px solid #e5e7eb', fontSize: '11px' }}
            formatter={(value: number) => value.toFixed(4)}
          />
          {showDiagonal && (
            <ReferenceLine
              segment={[{ x: diagMin, y: diagMin }, { x: diagMax, y: diagMax }]}
              stroke="#ef4444"
              strokeDasharray="5 5"
              strokeWidth={1.5}
            />
          )}
          <Scatter data={data} fill={color} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}
