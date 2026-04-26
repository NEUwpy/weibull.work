/**
 * 多线折线图组件 — 用于展示多条趋势线
 *
 * 复用于：R2-2(参数收敛轨迹 β̂,η̂,ŷ)
 * 设计：只输出图表，外框由 ChartCard 提供
 */
"use client"

import React from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'

interface MultiLineChartProps {
  data: Record<string, number>[]
  lines: { key: string; label: string; color: string }[]
  xKey: string
  xLabel?: string
  yLabel?: string
}

export function MultiLineChart({
  data,
  lines,
  xKey,
  xLabel = '',
  yLabel = '',
}: MultiLineChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="h-[280px] flex items-center justify-center text-slate-400">
        无有效数据
      </div>
    )
  }

  return (
    <div className="h-[280px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 20, bottom: 30, left: 50 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
          <XAxis
            dataKey={xKey}
            tick={{ fontSize: 10 }}
            label={{ value: xLabel, position: 'bottom', offset: 0, fontSize: 11 }}
          />
          <YAxis
            tick={{ fontSize: 10 }}
            label={{ value: yLabel, angle: -90, position: 'insideLeft', fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{ borderRadius: '4px', border: '1px solid #e5e7eb', fontSize: '11px' }}
          />
          <Legend
            wrapperStyle={{ fontSize: '11px' }}
            iconType="line"
            iconSize={16}
          />
          {lines.map(line => (
            <Line
              key={line.key}
              type="monotone"
              dataKey={line.key}
              name={line.label}
              stroke={line.color}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
