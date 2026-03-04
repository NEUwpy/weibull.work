/**
 * 箱型图组件 - 用于展示参数估计值的分布
 *
 * 显示：最小值、最大值、P1、P99、中位数、真实值参考线
 * 用途：单变量分析时，展示各分组下参数估计的分布情况
 *
 * 设计：只输出 SVG 图表，外框由 ChartCard 提供
 */
import React from 'react'

// 通用数据类型
export interface BoxPlotDataRow {
  keyLabel: string
  [key: string]: number | string | null | undefined
}

interface BoxPlotChartProps {
  data: BoxPlotDataRow[]
  dataKeyMin: string
  dataKeyMax: string
  dataKeyP01: string
  dataKeyP99: string
  dataKeyMedian: string
  color: string
  yLabel: string
  xLabel: string
  trueValue: number
}

export function BoxPlotChart({
  data,
  dataKeyMin,
  dataKeyMax,
  dataKeyP01,
  dataKeyP99,
  dataKeyMedian,
  color,
  yLabel,
  xLabel,
  trueValue
}: BoxPlotChartProps) {
  const allYValues = data.flatMap(d =>
    [d[dataKeyMin], d[dataKeyMax], d[dataKeyP01], d[dataKeyP99]]
      .filter((v): v is number => v !== null && typeof v === 'number')
  )
  if (allYValues.length === 0) return null

  const yMin = Math.min(...allYValues, trueValue) * 0.95
  const yMax = Math.max(...allYValues, trueValue) * 1.05
  const yRange = yMax - yMin

  const svgHeight = 240
  const svgWidth = 400
  const margin = { top: 30, right: 30, bottom: 50, left: 60 }
  const plotWidth = svgWidth - margin.left - margin.right
  const plotHeight = svgHeight - margin.top - margin.bottom

  const yToPixel = (y: number) => margin.top + plotHeight - ((y - yMin) / yRange) * plotHeight
  const xToPixel = (index: number) => margin.left + (index + 0.5) * (plotWidth / data.length)

  return (
    <div style={{ height: `${svgHeight}px` }}>
      <svg width="100%" height="100%" viewBox={`0 0 ${svgWidth} ${svgHeight}`} style={{ overflow: 'visible' }}>
        {/* 网格线 */}
        {Array.from({ length: 5 }, (_, i) => yMin + (yRange * i) / 4).map(tick => (
          <line key={`grid-${tick}`} x1={margin.left} y1={yToPixel(tick)} x2={svgWidth - margin.right} y2={yToPixel(tick)} stroke="#e5e7eb" strokeDasharray="3 3" />
        ))}

        {/* 真实值参考线 */}
        <line x1={margin.left} y1={yToPixel(trueValue)} x2={svgWidth - margin.right} y2={yToPixel(trueValue)} stroke={color} strokeDasharray="5 5" strokeWidth={1.5} />
        <text x={svgWidth - margin.right + 5} y={yToPixel(trueValue)} fontSize={10} fill={color} dominantBaseline="middle">真实值</text>

        {/* Y轴 */}
        <line x1={margin.left} y1={margin.top} x2={margin.left} y2={svgHeight - margin.bottom} stroke={color} strokeWidth={1.5} />

        {/* X轴 */}
        <line x1={margin.left} y1={svgHeight - margin.bottom} x2={svgWidth - margin.right} y2={svgHeight - margin.bottom} stroke="#000" strokeWidth={1} />

        {/* Y轴刻度 */}
        {Array.from({ length: 5 }, (_, i) => yMin + (yRange * i) / 4).map(tick => (
          <g key={`tick-${tick}`}>
            <line x1={margin.left - 5} y1={yToPixel(tick)} x2={margin.left} y2={yToPixel(tick)} stroke={color} strokeWidth={1} />
            <text x={margin.left - 8} y={yToPixel(tick)} textAnchor="end" dominantBaseline="middle" fontSize={10} fill="#374151">{tick.toFixed(tick < 10 ? 2 : 0)}</text>
          </g>
        ))}

        {/* X轴标签 */}
        {data.map((d, i) => (
          <text key={`x-${i}`} x={xToPixel(i)} y={svgHeight - margin.bottom + 18} textAnchor="middle" fontSize={11} fill="#374151">{d.keyLabel}</text>
        ))}

        {/* 箱型图 */}
        {data.map((d, i) => {
          const min = d[dataKeyMin] as number | null
          const max = d[dataKeyMax] as number | null
          const p01 = d[dataKeyP01] as number | null
          const p99 = d[dataKeyP99] as number | null
          const median = d[dataKeyMedian] as number | null

          if (min === null || max === null) return null

          const x = xToPixel(i)
          const boxWidth = Math.min(35, (plotWidth / data.length) * 0.7)

          return (
            <g key={`boxplot-${i}`}>
              <line x1={x} y1={yToPixel(min)} x2={x} y2={yToPixel(p01 ?? min)} stroke={color} strokeWidth={2} strokeDasharray="4 2" />
              <line x1={x} y1={yToPixel(p99 ?? max)} x2={x} y2={yToPixel(max)} stroke={color} strokeWidth={2} strokeDasharray="4 2" />
              <line x1={x - boxWidth / 3} y1={yToPixel(min)} x2={x + boxWidth / 3} y2={yToPixel(min)} stroke={color} strokeWidth={2} />
              <line x1={x - boxWidth / 3} y1={yToPixel(max)} x2={x + boxWidth / 3} y2={yToPixel(max)} stroke={color} strokeWidth={2} />
              {p01 !== null && p99 !== null && <rect x={x - boxWidth / 2} y={yToPixel(p99)} width={boxWidth} height={yToPixel(p01) - yToPixel(p99)} fill={color} fillOpacity={0.25} stroke={color} strokeWidth={2} />}
              {median !== null && <circle cx={x} cy={yToPixel(median)} r={4} fill={color} />}
            </g>
          )
        })}
      </svg>
    </div>
  )
}
