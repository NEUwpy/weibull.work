"use client"

import { useState } from 'react'
import {
  CartesianGrid, ComposedChart, Line, ReferenceDot, ReferenceLine,
  ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis,
} from 'recharts'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { type CalculationChart, type CalculationPoint, calculationFocus, formatCalculationNumber } from '@/lib/calculation-trace'
import { processPlotAxes, processPlotFrame, ProcessYAxisLabel } from './ProcessPlot'
import { useCalculationBatch } from '@/components/methods/CalculationBatch'

const SERIES_COLORS = ['#2563eb', '#7c3aed', '#059669', '#475569', '#db2777']
const axisNumber = (value: number) => value !== 0 && (Math.abs(value) >= 1e5 || Math.abs(value) < 1e-3)
  ? value.toExponential(2) : value.toLocaleString('zh-CN', { maximumSignificantDigits: 4, useGrouping: false })

type HoverPoint = { point: CalculationPoint; name: string }
function CalculatedPoint({ cx, cy, payload, color, label, onHover }: {
  cx?: number; cy?: number; payload?: CalculationPoint; color: string; label: string
  onHover: (value: HoverPoint | null) => void
}) {
  if (!payload) return <g />
  return <circle className="process-calculated-point" cx={cx} cy={cy} r={2.7} fill={color} stroke="#fff" strokeWidth={0.5}
    data-x={payload.x} data-y={payload.y}
    onMouseEnter={() => onHover({ point: payload, name: label })} onMouseLeave={() => onHover(null)} />
}

export function ProcessFormula({ expression }: { expression: string }) {
  return <div className="max-w-full overflow-x-auto py-2 text-base text-slate-700"
    dangerouslySetInnerHTML={{ __html: katex.renderToString(expression, { throwOnError: false, strict: false, trust: false }) }} />
}

export function ProcessPointLegend({ color, selectedLabel = '采纳值' }: { color: string; selectedLabel?: string }) {
  return <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-500">
    <span className="inline-flex items-center gap-1.5" title="按横坐标连接本次实际计算点"><span className="inline-block w-4 border-t-2" style={{ borderColor: color }} />计算点连线</span>
    <span className="inline-flex items-center gap-1.5" title="本次求解实际计算的点"><span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />计算点</span>
    <span className="inline-flex items-center gap-1.5 text-amber-800"><span className="h-2 w-2 rounded-full bg-[#b7791f]" />{selectedLabel}</span>
  </div>
}

export function ProcessChart({ chart: givenChart, initiallyFocused, figureOnly = false, showYAxisLabel = false, focusLabel = '聚焦最终选择', workspacePlot = false, overlay: givenOverlay, batchCharts }: {
  chart: CalculationChart; initiallyFocused?: boolean; figureOnly?: boolean; showYAxisLabel?: boolean; focusLabel?: string; workspacePlot?: boolean
  overlay?: { activeId?: string; activeLabel?: string; label: string; adoptedLabel?: string }
  batchCharts?: { sourceId: string; label: string; chart: CalculationChart }[]
}) {
  const batch = useCalculationBatch()
  let chart = givenChart
  let overlay = givenOverlay
  const rows = batchCharts ?? batch?.records.flatMap(({ source, trace }) => {
    const item = source.id === batch.sources[batch.activeIndex]?.id ? givenChart : trace.charts.find(item => item.id === givenChart.id)
    return item ? [{ sourceId: source.id, label: source.name, chart: item }] : []
  })
  if (batch && !overlay && rows && rows.length > 1) {
    chart = { ...givenChart, series: rows.flatMap(row => row.chart.series.map(series => ({
      ...series, id: row.sourceId + '/' + series.id, label: row.label + ' · ' + series.label,
    }))) }
    overlay = { activeId: batch.sources[batch.activeIndex]?.id, activeLabel: batch.sources[batch.activeIndex]?.name, label: '各组实际计算' }
  }
  const activeSeries = (id: string) => id === overlay?.activeId || !!overlay?.activeId && id.startsWith(overlay.activeId + '/')
  const [hoveredPoint, setHoveredPoint] = useState<HoverPoint | null>(null)
  const focus = overlay ? null : calculationFocus(chart)
  const values = chart.series.flatMap(series => series.points.map(point => point.y))
  const extent = values.reduce(([min, max], value) => [Math.min(min, value), Math.max(max, value)], [Infinity, -Infinity])
  const fullSpan = values.length ? extent[1] - extent[0] : 0
  const [focused, setFocused] = useState(initiallyFocused ?? (!!focus && (chart.id === 'location-score'
    || fullSpan > (focus.y[1] - focus.y[0]) * 100)))
  const domains = focused ? focus : null
  // Restrict only SVG rendering to the chosen x viewport. Passing enormous
  // offscreen coordinates to SVG can make the entire path disappear.
  // These are references to the original points; the backend record stays complete.
  const viewSeries = domains ? chart.series.map(series => ({ ...series,
    points: series.points.filter(point => point.x >= domains.x[0] && point.x <= domains.x[1]),
  })) : chart.series
  const plottedPoints = [...viewSeries.flatMap(series => series.points), ...(chart.selected ?? [])]
  const hasPoints = plottedPoints.length > 0
  const focusButton = focus && <button type="button" onClick={() => setFocused(value => !value)} aria-pressed={focused}
    className="rounded-lg px-2 py-1 text-sm font-medium text-blue-700 hover:bg-blue-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500">
    {focused ? '显示全部范围' : focusLabel}
  </button>
  return (
    <section className={figureOnly ? 'min-w-0' : 'min-w-0 rounded-2xl border border-slate-200/80 bg-white/70 px-3 py-4 sm:px-5'}>
      {(!figureOnly || (focus && !workspacePlot)) && <div className={`flex flex-wrap items-start gap-2 ${figureOnly ? 'justify-end' : 'justify-between'}`}>
        {!figureOnly && <h3 title={chart.description} className="text-lg font-semibold leading-snug text-slate-800">{chart.title}</h3>}
        {!workspacePlot && focusButton}
      </div>}
      {!figureOnly && <p className="mt-3 text-base leading-relaxed text-slate-600">横轴：{chart.x.label}；纵轴：{chart.y.label}。{chart.description}</p>}
      {!figureOnly && chart.formula && <ProcessFormula expression={chart.formula} />}
      {hasPoints ? (
        <div className={workspacePlot ? processPlotFrame : 'mt-1 h-[300px] w-full min-w-0'} data-process-plot={workspacePlot || undefined}
          role="img" aria-label={`${chart.title}；横轴${chart.x.label}，纵轴${chart.y.label}`}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={plottedPoints} margin={workspacePlot ? processPlotAxes.margin : { top: 26, right: 18, bottom: 30, left: 2 }}>
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 4" vertical={false} />
              <XAxis type="number" dataKey="x" domain={domains?.x ?? ['auto', 'auto']} allowDataOverflow={!!domains}
                allowDuplicatedCategory={false}
                height={workspacePlot ? processPlotAxes.xAxisHeight : undefined}
                tickFormatter={axisNumber} tick={{ fontSize: 14, fill: '#64748b' }}
                axisLine={{ stroke: '#cbd5e1' }} tickLine={false} minTickGap={32}
                label={{ value: chart.x.label, position: 'bottom', offset: workspacePlot ? 8 : 12, fontSize: 14, fill: '#475569' }} />
              <YAxis type="number" dataKey="y" domain={domains?.y ?? ['auto', 'auto']} allowDataOverflow={!!domains} width={workspacePlot ? processPlotAxes.yAxisWidth : 76}
                tickFormatter={axisNumber} tick={{ fontSize: 14, fill: '#64748b' }}
                axisLine={workspacePlot ? { stroke: '#cbd5e1' } : false} tickLine={false}
                label={showYAxisLabel ? { value: chart.y.label, content: workspacePlot ? <ProcessYAxisLabel /> : undefined,
                  angle: -90, position: 'insideLeft', fontSize: 14, fill: '#64748b' } : undefined} />
              <Tooltip
                content={({ active, payload }) => {
                  if ((!active || !payload?.length) && !hoveredPoint) return null
                  const entries = hoveredPoint ? [{ name: hoveredPoint.name, payload: hoveredPoint.point }]
                    : (payload ?? []).filter(entry => Number.isFinite(entry.payload?.x) && Number.isFinite(entry.payload?.y))
                      .filter(entry => !overlay || chart.series.some(series => activeSeries(series.id) && series.label === entry.name))
                  if (!entries.length) return null
                  return <div className="max-w-[280px] rounded-xl border border-slate-200 bg-white/95 p-3 text-sm leading-relaxed shadow-sm">
                    {entries.map((entry, index) => <div key={index} className={index > 0 ? 'mt-2 border-t border-slate-100 pt-2' : ''}>
                      <p className="font-medium text-slate-700">{entry.name}</p>
                      <p className="text-slate-500">{chart.x.label} = {formatCalculationNumber(entry.payload.x)}</p>
                      <p className="text-slate-500">{chart.y.label} = {formatCalculationNumber(entry.payload.y)}</p>
                      {typeof entry.payload.evaluation === 'number' && <p className="text-slate-500">求值序号：{entry.payload.evaluation}</p>}
                      {typeof entry.payload.iteration === 'number' && <p className="text-slate-500">{entry.payload.iteration === 0 ? '初始形状' : `实际迭代：第 ${entry.payload.iteration} 步`}</p>}
                    </div>)}
                  </div>
                }}
                cursor={{ stroke: '#cbd5e1', strokeDasharray: '4 4' }}
              />
              {chart.references?.map((reference, index) => (
                <ReferenceLine key={`${reference.axis}-${index}`}
                  {...(reference.axis === 'x' ? { x: reference.value } : { y: reference.value })}
                  stroke="#94a3b8" strokeDasharray="5 4" ifOverflow={domains ? 'hidden' : 'extendDomain'}
                  label={{ value: reference.label, position: reference.axis === 'x' ? 'insideTopRight' : 'insideTopLeft', fill: '#64748b', fontSize: 14 }} />
              ))}
              {chart.selected?.flatMap((point, index) => [
                <ReferenceLine key={`projection-x-${index}`} x={point.x} stroke="#b7791f" strokeDasharray="4 4" ifOverflow="extendDomain"
                  label={{ value: formatCalculationNumber(point.x), position: 'insideBottomRight', fill: '#9a670f', fontSize: 14 }} />,
                ...(!chart.references?.some(reference => reference.axis === 'y' && Math.abs(reference.value-point.y) <= 1e-10) ? [<ReferenceLine key={`projection-y-${index}`} y={point.y} stroke="#b7791f" strokeDasharray="4 4" ifOverflow="extendDomain"
                  label={{ value: formatCalculationNumber(point.y), position: 'insideTopLeft', fill: '#9a670f', fontSize: 14 }} />] : []),
              ])}
              {viewSeries.map((series, index) => {
                const highlighted = !overlay || activeSeries(series.id)
                const color = overlay ? series.role === 'candidate' ? '#b7791f' : highlighted ? '#2563eb' : '#64748b'
                  : series.role === 'virtual' ? '#94a3b8' : SERIES_COLORS[index % SERIES_COLORS.length]
                return series.kind === 'line' ? (
                  <Line key={series.id} data={series.points} type={series.interpolation ?? 'linear'} dataKey="y" name={series.label}
                    stroke={color} strokeWidth={highlighted ? 2 : 1} strokeOpacity={highlighted ? 1 : .22}
                    dot={series.role === 'solver' && highlighted ? <CalculatedPoint color={color} label={series.label} onHover={setHoveredPoint} /> : false}
                    strokeDasharray={series.role === 'virtual' ? '5 4' : undefined}
                    activeDot={highlighted ? { r: 4 } : false} isAnimationActive={false} connectNulls={false} />
                ) : (
                  <Scatter key={series.id} name={series.label} data={series.points} fill={color}
                    shape={series.role === 'solver' ? <CalculatedPoint color={color} label={series.label} onHover={setHoveredPoint} /> : undefined}
                    fillOpacity={0.75} isAnimationActive={false} />
                )
              })}
              {chart.selected?.map((point, index) => (
                <ReferenceDot key={`selected-${index}`} x={point.x} y={point.y} r={6}
                  fill="#b7791f" stroke="#fff" strokeWidth={2} ifOverflow="extendDomain"
                  label={{ value: point.label ?? '最终选择', position: 'top', offset: 10, fill: '#9a670f', fontSize: 14 }} />
              ))}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      ) : <p className="py-8 text-center text-base text-slate-500">本次运行未得到可绘制的有限数值。</p>}
      <div className="mt-2 flex flex-wrap items-start gap-x-4 gap-y-1 text-sm text-slate-500">
        {overlay ? <>
          <span className="inline-flex items-center gap-1.5"><span className="h-px w-4 bg-slate-400" />{overlay.label}</span>
          {overlay.activeId && <span className="inline-flex items-center gap-1.5"><span className="h-0.5 w-4 bg-blue-600" />
            {overlay.activeLabel ?? chart.series.find(series => activeSeries(series.id))?.label}</span>}
          {overlay.adoptedLabel && <span className="inline-flex items-center gap-1.5 text-amber-800">
            <span className="h-2 w-2 rounded-full bg-[#b7791f]" />{overlay.adoptedLabel}</span>}
        </> : chart.series.map((series, index) => (
          <span key={series.id} title={series.label} className="inline-flex items-center gap-1.5">
            <span className={`inline-block h-2 w-2 shrink-0 ${series.kind === 'line' && series.role !== 'solver' ? 'rounded-sm' : 'rounded-full'}`}
              style={{ backgroundColor: series.role === 'virtual' ? '#94a3b8' : SERIES_COLORS[index % SERIES_COLORS.length] }} />
            {series.role === 'solver' ? series.id === 'iterations' ? '迭代点' : '计算点'
              : series.role === 'candidate' ? '候选点'
              : series.label.includes('补充采样') || series.label.includes('辅助采样') ? '函数曲线' : series.label}
          </span>
        ))}
        {!overlay && !!chart.selected?.length && Array.from(new Set(chart.selected.map(point => point.label ?? '最终选择'))).map(label => (
          <span key={label} title={label} className="inline-flex items-center gap-1.5 text-amber-800"><span className="h-2 w-2 rounded-full bg-[#b7791f]" />采纳值</span>
        ))}
      </div>
      {workspacePlot && !overlay && <div className="flex min-h-7 justify-end">{focusButton}</div>}
    </section>
  )
}

