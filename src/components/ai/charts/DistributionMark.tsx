/**
 * 分布+标记点组件 — 用于展示预测值在训练数据分布中的位置
 *
 * 复用于：R1-2(预测δ在分布中的位置)
 * 设计：直方图 + 垂直标记线
 */
"use client"

import React, { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'

interface DistributionMarkProps {
  distributionValues: number[]  // 训练数据的 δ 分布
  markValue: number             // 预测的 δ 值
  bins?: number
  color?: string
  markColor?: string
}

export function DistributionMark({
  distributionValues,
  markValue,
  bins: binCount,
  color = '#8b5cf6',
  markColor = '#ef4444',
}: DistributionMarkProps) {
  const data = useMemo(() => {
    if (!distributionValues || distributionValues.length === 0) return []
    const allValues = [...distributionValues, markValue]
    const min = Math.min(...allValues) - 0.01
    const max = Math.max(...allValues) + 0.01
    const range = max - min
    const n = binCount ?? Math.min(Math.ceil(Math.sqrt(distributionValues.length)), 25)
    const binWidth = range / n

    const bins = Array.from({ length: n }, (_, i) => ({
      label: (min + (i + 0.5) * binWidth).toFixed(3),
      count: 0,
      midpoint: min + (i + 0.5) * binWidth,
    }))

    for (const v of distributionValues) {
      let idx = Math.floor((v - min) / binWidth)
      if (idx >= n) idx = n - 1
      if (idx < 0) idx = 0
      bins[idx].count++
    }

    return bins
  }, [distributionValues, markValue, binCount])

  if (!distributionValues || distributionValues.length === 0) {
    return (
      <div className="h-[280px] flex items-center justify-center text-slate-400">
        无分布数据
      </div>
    )
  }

  return (
    <div className="h-[280px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 20, bottom: 30, left: 50 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 9 }}
            label={{ value: 'δ', position: 'bottom', offset: 0, fontSize: 11 }}
            interval={Math.max(0, Math.floor(data.length / 6))}
          />
          <YAxis
            tick={{ fontSize: 10 }}
            label={{ value: '频次', angle: -90, position: 'insideLeft', fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{ borderRadius: '4px', border: '1px solid #e5e7eb', fontSize: '11px' }}
          />
          <Bar dataKey="count" fill={color} radius={[2, 2, 0, 0]} />
          <ReferenceLine
            x={data.reduce((closest, d) =>
              Math.abs(d.midpoint - markValue) < Math.abs(closest.midpoint - markValue) ? d : closest
            ).label}
            stroke={markColor}
            strokeWidth={2.5}
            label={{ value: `δ=${markValue.toFixed(4)}`, position: 'top', fontSize: 11, fill: markColor }}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
