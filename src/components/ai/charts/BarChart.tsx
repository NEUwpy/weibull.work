/**
 * 通用柱状图组件 — 用于展示分类数据对比
 *
 * 复用于：D6(无解率), P4(指标对比)
 * 设计：只输出图表，外框由 ChartCard 提供
 */
"use client"

import React from 'react'
import {
  BarChart as RechartsBarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from 'recharts'

interface BarDataItem {
  label: string
  value: number
  color?: string
}

interface BarChartProps {
  data: BarDataItem[]
  xLabel?: string
  yLabel?: string
  color?: string
  showValue?: boolean    // 在柱顶显示数值
}

export function BarChart({
  data,
  xLabel = '',
  yLabel = '',
  color = '#8b5cf6',
  showValue = false,
}: BarChartProps) {
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
        <RechartsBarChart data={data} margin={{ top: 10, right: 20, bottom: 30, left: 50 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10 }}
            label={{ value: xLabel, position: 'bottom', offset: 0, fontSize: 11 }}
          />
          <YAxis
            tick={{ fontSize: 10 }}
            label={{ value: yLabel, angle: -90, position: 'insideLeft', fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{ borderRadius: '4px', border: '1px solid #e5e7eb', fontSize: '11px' }}
            formatter={(value: number) => [value.toFixed(4), yLabel]}
          />
          <Bar dataKey="value" radius={[3, 3, 0, 0]}>
            {data.map((entry, index) => (
              <Cell key={index} fill={entry.color || color} />
            ))}
          </Bar>
        </RechartsBarChart>
      </ResponsiveContainer>
    </div>
  )
}
