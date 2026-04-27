/**
 * 通用直方图组件 — 用于展示数据分布
 *
 * 复用于：D1(δ分布), P2(误差分布), P5(预测vs真实分布), R2-3(收敛步数分布)
 * 设计：只输出图表，外框由 ChartCard 提供
 */
"use client"

import React, { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'

interface PrecomputedBin {
  x0: number
  x1: number
  count: number
}

interface HistogramProps {
  values?: number[]
  precomputedBins?: PrecomputedBin[]  // 预计算的 bin 数据，传入时跳过 values 解析
  precomputedMean?: number            // 预计算的均值
  bins?: number          // 分箱数，默认 auto
  xLabel?: string
  yLabel?: string
  color?: string
  showMean?: boolean     // 显示均值参考线
  secondValues?: number[] // 叠加第二组数据
  secondColor?: string
  secondLabel?: string
}

function computeBins(values: number[], binCount?: number) {
  if (values.length === 0) return { bins: [], binWidth: 0, min: 0, max: 0 }
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const n = binCount ?? Math.min(Math.ceil(Math.sqrt(values.length)), 30)
  const binWidth = range / n

  const bins = Array.from({ length: n }, (_, i) => ({
    x0: min + i * binWidth,
    x1: min + (i + 1) * binWidth,
    count: 0,
    count2: 0,
  }))

  for (const v of values) {
    let idx = Math.floor((v - min) / binWidth)
    if (idx >= n) idx = n - 1
    if (idx < 0) idx = 0
    bins[idx].count++
  }

  return { bins, binWidth, min, max }
}

export function Histogram({
  values,
  precomputedBins,
  precomputedMean,
  bins: binCount,
  xLabel = '',
  yLabel = '频次',
  color = '#8b5cf6',
  showMean = false,
  secondValues,
  secondColor = '#10b981',
  secondLabel,
}: HistogramProps) {
  const result = useMemo(() => {
    // 使用预计算的 bin 数据
    if (precomputedBins && precomputedBins.length > 0) {
      const avgWidth = precomputedBins.length > 1
        ? (precomputedBins[precomputedBins.length - 1].x1 - precomputedBins[0].x0) / precomputedBins.length
        : 1
      const data = precomputedBins.map(b => ({
        label: ((b.x0 + b.x1) / 2).toFixed(avgWidth < 0.01 ? 3 : avgWidth < 0.1 ? 2 : 1),
        count: b.count,
        count2: undefined,
      }))
      return { data, mean: precomputedMean ?? 0 }
    }

    // 从原始 values 计算
    const allValues = secondValues ? [...values!, ...secondValues] : values!
    const { bins, binWidth } = computeBins(allValues, binCount)

    for (const b of bins) { b.count = 0; b.count2 = 0 }
    for (const v of values!) {
      let idx = Math.floor((v - bins[0].x0) / binWidth)
      if (idx >= bins.length) idx = bins.length - 1
      if (idx < 0) idx = 0
      bins[idx].count++
    }
    if (secondValues) {
      for (const v of secondValues) {
        let idx = Math.floor((v - bins[0].x0) / binWidth)
        if (idx >= bins.length) idx = bins.length - 1
        if (idx < 0) idx = 0
        bins[idx].count2++
      }
    }

    const data = bins.map(b => ({
      label: ((b.x0 + b.x1) / 2).toFixed(binWidth < 0.01 ? 3 : binWidth < 0.1 ? 2 : 1),
      count: b.count,
      count2: secondValues ? b.count2 : undefined,
    }))

    const mean = values!.reduce((a, b) => a + b, 0) / values!.length
    return { data, mean }
  }, [values, precomputedBins, precomputedMean, binCount, secondValues])

  if ((!values || values.length === 0) && (!precomputedBins || precomputedBins.length === 0)) {
    return (
      <div className="h-[280px] flex items-center justify-center text-slate-400">
        无有效数据
      </div>
    )
  }

  return (
    <div className="h-[280px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={result.data} margin={{ top: 10, right: 20, bottom: 30, left: 50 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 9 }}
            label={{ value: xLabel, position: 'bottom', offset: 0, fontSize: 11 }}
            interval={Math.max(0, Math.floor(result.data.length / 8))}
          />
          <YAxis
            tick={{ fontSize: 10 }}
            label={{ value: yLabel, angle: -90, position: 'insideLeft', fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{ borderRadius: '4px', border: '1px solid #e5e7eb', fontSize: '11px' }}
          />
          {showMean && (
            <ReferenceLine
              x={result.data.find(d => {
                const v = parseFloat(d.label)
                return Math.abs(v - result.mean) < (result.data.length > 0 ? 0.01 : 1)
              })?.label}
              stroke="#ef4444"
              strokeDasharray="5 5"
              strokeWidth={2}
            />
          )}
          <Bar dataKey="count" fill={color} radius={[2, 2, 0, 0]} />
          {secondValues && (
            <Bar dataKey="count2" fill={secondColor} radius={[2, 2, 0, 0]} opacity={0.7} />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
