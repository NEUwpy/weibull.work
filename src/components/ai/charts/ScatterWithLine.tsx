/**
 * 散点+拟合线组件 — 用于展示数据点和拟合曲线
 *
 * 复用于：R2-4(MDM拟合线+数据点), V2(验证案例拟合图)
 * 设计：只输出图表，外框由 ChartCard 提供
 */
"use client"

import React from 'react'
import {
  ScatterChart, Scatter, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'

interface ScatterWithLineProps {
  scatterData: { x: number; y: number }[]
  lineData: { x: number; y: number }[]
  xLabel?: string
  yLabel?: string
  scatterColor?: string
  lineColor?: string
  scatterLabel?: string
  lineLabel?: string
}

export function ScatterWithLine({
  scatterData,
  lineData,
  xLabel = '',
  yLabel = '',
  scatterColor = '#3b82f6',
  lineColor = '#ef4444',
  scatterLabel = '数据点',
  lineLabel = '拟合线',
}: ScatterWithLineProps) {
  if (!scatterData || scatterData.length === 0) {
    return (
      <div className="h-[280px] flex items-center justify-center text-slate-400">
        无有效数据
      </div>
    )
  }

  const allX = [...scatterData.map(d => d.x), ...lineData.map(d => d.x)]
  const allY = [...scatterData.map(d => d.y), ...lineData.map(d => d.y)]
  const xDomain: [number, number] = [Math.min(...allX) * 0.95, Math.max(...allX) * 1.05]
  const yDomain: [number, number] = [Math.min(...allY) * 0.95, Math.max(...allY) * 1.05]

  return (
    <>
      {/* 图例 */}
      <div className="flex gap-4 mb-2 text-xs justify-center">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-full inline-block" style={{ backgroundColor: scatterColor }} />
          <span className="text-slate-600">{scatterLabel}</span>
        </span>
        <span className="flex items-center gap-1">
          <span className="w-4 h-0.5 inline-block" style={{ backgroundColor: lineColor }} />
          <span className="text-slate-600">{lineLabel}</span>
        </span>
      </div>

      <div className="h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 10, right: 20, bottom: 30, left: 50 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis
              type="number"
              dataKey="x"
              domain={xDomain}
              tick={{ fontSize: 10 }}
              label={{ value: xLabel, position: 'bottom', offset: 0, fontSize: 11 }}
            />
            <YAxis
              type="number"
              dataKey="y"
              domain={yDomain}
              tick={{ fontSize: 10 }}
              label={{ value: yLabel, angle: -90, position: 'insideLeft', fontSize: 11 }}
            />
            <Tooltip
              contentStyle={{ borderRadius: '4px', border: '1px solid #e5e7eb', fontSize: '11px' }}
              formatter={(value: number) => value.toFixed(4)}
            />
            <Scatter data={scatterData} fill={scatterColor} />
            {lineData.length > 0 && (
              <Line
                type="monotone"
                dataKey="y"
                data={lineData}
                stroke={lineColor}
                strokeWidth={2}
                dot={false}
              />
            )}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </>
  )
}
