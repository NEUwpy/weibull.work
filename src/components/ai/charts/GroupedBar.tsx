/**
 * 分组柱状图组件 — 用于多组数据对比
 *
 * 复用于：C4(路线1 vs 路线2效果对比)
 * 设计：只输出图表，外框由 ChartCard 提供
 */
"use client"

import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'

interface GroupedBarProps {
  data: Record<string, string | number>[]
  groups: { key: string; label: string; color: string }[]
  xKey: string
  xLabel?: string
  yLabel?: string
}

export function GroupedBar({
  data,
  groups,
  xKey,
  xLabel = '',
  yLabel = '',
}: GroupedBarProps) {
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
        <BarChart data={data} margin={{ top: 10, right: 20, bottom: 30, left: 50 }}>
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
            iconType="square"
            iconSize={10}
          />
          {groups.map(group => (
            <Bar
              key={group.key}
              dataKey={group.key}
              name={group.label}
              fill={group.color}
              radius={[2, 2, 0, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
