/**
 * 通用折线图组件 — 用于展示趋势和收敛
 *
 * 复用于：T1(损失曲线), T2(学习率曲线), R2-1(δ收敛轨迹), C2(δ sweep MSE)
 * 设计：只输出图表，外框由 ChartCard 提供
 */
"use client"

import React from 'react'
import {
  LineChart as RechartsLineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'

interface LineData {
  x: number
  y: number
}

interface MultiLineData {
  id: string
  label: string
  data: LineData[]
  color: string
}

interface AIChartLineProps {
  data?: LineData[]
  lines?: MultiLineData[]
  xLabel?: string
  yLabel?: string
  color?: string
  yReference?: number       // 水平参考线
  yReferenceLabel?: string
  xDomain?: [number, number]
  yDomain?: [number, number]
}

export function AIChartLine({
  data,
  lines,
  xLabel = '',
  yLabel = '',
  color = '#8b5cf6',
  yReference,
  yReferenceLabel,
  xDomain,
  yDomain,
}: AIChartLineProps) {
  const allData = data || (lines ? lines.flatMap(l => l.data) : [])
  if (allData.length === 0) {
    return (
      <div className="h-[280px] flex items-center justify-center text-slate-400">
        无有效数据
      </div>
    )
  }

  const allX = allData.map(d => d.x)
  const allY = allData.map(d => d.y)
  const autoXDomain = xDomain || [Math.min(...allX), Math.max(...allX)]
  const autoYDomain = yDomain || [Math.min(...allY) * 0.95, Math.max(...allY) * 1.05]

  return (
    <div className="h-[280px]">
      <ResponsiveContainer width="100%" height="100%">
        <RechartsLineChart margin={{ top: 10, right: 20, bottom: 30, left: 50 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
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
            formatter={(value: number) => [value.toFixed(6), yLabel]}
            labelFormatter={(label: number) => `Epoch: ${label}`}
          />
          {yReference !== undefined && (
            <ReferenceLine
              y={yReference}
              stroke="#ef4444"
              strokeDasharray="5 5"
              strokeWidth={1.5}
              label={yReferenceLabel ? { value: yReferenceLabel, position: 'right', fontSize: 10 } : undefined}
            />
          )}
          {data && (
            <Line type="monotone" dataKey="y" data={data} stroke={color} strokeWidth={2} dot={false} />
          )}
          {lines && lines.map(line => (
            <Line
              key={line.id}
              type="monotone"
              dataKey="y"
              data={line.data}
              stroke={line.color}
              strokeWidth={2}
              dot={false}
              name={line.label}
            />
          ))}
        </RechartsLineChart>
      </ResponsiveContainer>
    </div>
  )
}
