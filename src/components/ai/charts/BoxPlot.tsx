/**
 * 通用箱型图组件 — 展示分组数据的分布
 *
 * 用于：AI 直接估计的预测 vs 真值（按真值分组看预测分布）
 * 设计：只输出图表，外框由 ChartCard 提供
 */
"use client"

import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Cell
} from 'recharts'

export interface BoxPlotPoint {
  label: string
  true_val: number
  min: number
  q1: number
  median: number
  q3: number
  max: number
  mean: number
  count: number
  outlier_count: number
}

interface BoxPlotProps {
  data: BoxPlotPoint[]
  xLabel?: string
  yLabel?: string
  color?: string
  showDiagonal?: boolean
  yAxisDomain?: [number, number]
}

export function BoxPlot({
  data,
  xLabel = '',
  yLabel = '',
  color = '#0891b2',
  showDiagonal = true,
  yAxisDomain,
}: BoxPlotProps) {
  if (!data || data.length === 0) {
    return (
      <div className="h-[320px] flex items-center justify-center text-slate-400">
        无有效数据
      </div>
    )
  }

  const allMin = Math.min(...data.map(d => d.min))
  const allMax = Math.max(...data.map(d => d.max))
  const padding = (allMax - allMin) * 0.1 || 1
  const domain: [number, number] = yAxisDomain || [allMin - padding, allMax + padding]

  // Render box plots as custom bars — each bar is invisible, we draw the box plot in its shape
  const chartData = data.map(d => ({ ...d, placeholder: d.q3 }))

  return (
    <div className="h-[320px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 10, right: 20, bottom: 30, left: 50 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10 }}
            label={{ value: xLabel, position: 'bottom', offset: 0, fontSize: 11 }}
          />
          <YAxis
            tick={{ fontSize: 10 }}
            label={{ value: yLabel, angle: -90, position: 'insideLeft', fontSize: 11 }}
            domain={domain}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.[0]) return null
              const d = payload[0].payload as BoxPlotPoint
              return (
                <div className="bg-white border border-slate-200 rounded-lg shadow-lg p-3 text-xs space-y-1">
                  <div className="font-bold text-slate-700">{d.label}</div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
                    <span className="text-slate-500">真值</span><span className="font-mono">{d.true_val}</span>
                    <span className="text-slate-500">中位数</span><span className="font-mono">{d.median.toFixed(4)}</span>
                    <span className="text-slate-500">均值</span><span className="font-mono">{d.mean.toFixed(4)}</span>
                    <span className="text-slate-500">Q1 – Q3</span><span className="font-mono">{d.q1.toFixed(4)} – {d.q3.toFixed(4)}</span>
                    <span className="text-slate-500">须</span><span className="font-mono">{d.min.toFixed(4)} – {d.max.toFixed(4)}</span>
                    <span className="text-slate-500">样本数</span><span className="font-mono">{d.count}</span>
                    {d.outlier_count > 0 && (
                      <><span className="text-slate-500">异常值</span><span className="font-mono text-orange-500">{d.outlier_count}</span></>
                    )}
                  </div>
                </div>
              )
            }}
          />
          {showDiagonal && (
            <ReferenceLine
              segment={[
                { x: data[0]?.label, y: data[0]?.true_val },
                { x: data[data.length - 1]?.label, y: data[data.length - 1]?.true_val },
              ]}
              stroke="#94a3b8" strokeDasharray="5 5" strokeWidth={1}
            />
          )}
          <Bar
            dataKey="placeholder"
            fill="transparent"
            stroke="none"
            shape={(props: unknown) => {
              const p = props as {
                x: number; width: number;
                background: { y: number; height: number };
                payload: BoxPlotPoint;
              }
              if (!p.payload) return <g />

              const d = p.payload
              // background.y = top of chart area, background.height = chart area height
              const areaTop = p.background.y
              const areaH = p.background.height
              const [domMin, domMax] = domain
              const domRange = domMax - domMin || 1

              const yScale = (val: number) => areaTop + (1 - (val - domMin) / domRange) * areaH

              const bx = p.x
              const bw = p.width
              const cx = bx + bw / 2

              const yQ3 = yScale(d.q3)
              const yQ1 = yScale(d.q1)
              const yMed = yScale(d.median)
              const yMax = yScale(d.max)
              const yMin = yScale(d.min)

              return (
                <g>
                  {/* Box: Q1 → Q3 */}
                  <rect
                    x={bx} y={yQ3} width={bw} height={Math.max(1, yQ1 - yQ3)}
                    fill={color} fillOpacity={0.2} stroke={color} strokeWidth={1.5} rx={2}
                  />
                  {/* Median line */}
                  <line x1={bx} y1={yMed} x2={bx + bw} y2={yMed}
                    stroke={color} strokeWidth={2.5} />
                  {/* Upper whisker */}
                  <line x1={cx} y1={yQ3} x2={cx} y2={yMax}
                    stroke={color} strokeWidth={1} strokeDasharray="3 2" />
                  <line x1={bx + bw * 0.2} y1={yMax} x2={bx + bw * 0.8} y2={yMax}
                    stroke={color} strokeWidth={1.5} />
                  {/* Lower whisker */}
                  <line x1={cx} y1={yQ1} x2={cx} y2={yMin}
                    stroke={color} strokeWidth={1} strokeDasharray="3 2" />
                  <line x1={bx + bw * 0.2} y1={yMin} x2={bx + bw * 0.8} y2={yMin}
                    stroke={color} strokeWidth={1.5} />
                  {/* Mean dot */}
                  <circle cx={cx} cy={yScale(d.mean)} r={3}
                    fill={color} fillOpacity={0.5} />
                </g>
              )
            }}
          >
            {chartData.map((_, i) => (
              <Cell key={i} fill="transparent" />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
