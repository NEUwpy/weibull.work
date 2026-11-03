"use client"

import React, { useState } from 'react'
import {
  CartesianGrid, ComposedChart, Line, ReferenceDot, ReferenceLine,
  ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Check, ChevronDown, Info } from 'lucide-react'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import {
  type CalculationChart, type CalculationTrace,
  calculationFocus, formatCalculationNumber, readCalculationTrace,
} from '@/lib/calculation-trace'

interface CalculationProcessViewerProps {
  calculation: unknown
  methodId?: string
  stale?: boolean
  isUpdating?: boolean
}

const SERIES_COLORS = ['#2563eb', '#7c3aed', '#059669', '#475569', '#db2777']
const axisNumber = (value: number) => value !== 0 && (Math.abs(value) >= 1e5 || Math.abs(value) < 1e-3)
  ? value.toExponential(2) : value.toLocaleString('zh-CN', { maximumSignificantDigits: 4, useGrouping: false })

function ProcessFormula({ expression }: { expression: string }) {
  return <div className="max-w-full overflow-x-auto py-2 text-base text-slate-700"
    dangerouslySetInnerHTML={{ __html: katex.renderToString(expression, { throwOnError: false, strict: false, trust: false }) }} />
}

function ProcessChart({ chart }: { chart: CalculationChart }) {
  const focus = calculationFocus(chart)
  const values = chart.series.flatMap(series => series.points.map(point => point.y))
  const fullSpan = values.length ? Math.max(...values) - Math.min(...values) : 0
  const [focused, setFocused] = useState(!!focus && (chart.id === 'location-score'
    || fullSpan > (focus.y[1] - focus.y[0]) * 100))
  const domains = focused ? focus : null
  // Restrict only SVG rendering to the chosen x viewport. Passing enormous
  // offscreen coordinates to SVG can make the entire path disappear.
  // These are references to the original points; the backend record stays complete.
  const viewSeries = domains ? chart.series.map(series => ({ ...series,
    points: series.points.filter(point => point.x >= domains.x[0] && point.x <= domains.x[1]),
  })) : chart.series
  const plottedPoints = [...viewSeries.flatMap(series => series.points), ...(chart.selected ?? [])]
  const hasPoints = plottedPoints.length > 0
  return (
    <section className="min-w-0 rounded-2xl border border-slate-200/80 bg-white/70 px-3 py-4 sm:px-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 title={chart.description} className="text-lg font-semibold leading-snug text-slate-800">{chart.title}</h3>
        {focus && <button type="button" onClick={() => setFocused(value => !value)} aria-pressed={focused}
          className="rounded-lg px-2 py-1 text-sm font-medium text-blue-700 hover:bg-blue-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500">
          {focused ? '显示全部范围' : '聚焦最终选择'}
        </button>}
      </div>
      {chart.formula && <ProcessFormula expression={chart.formula} />}
      <p className="mt-3 text-sm leading-relaxed text-slate-600">{chart.y.label}</p>
      {hasPoints ? (
        <div className="mt-1 h-[300px] w-full min-w-0" role="img" aria-label={`${chart.title}；横轴${chart.x.label}，纵轴${chart.y.label}`}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={plottedPoints} margin={{ top: 26, right: 18, bottom: 30, left: 2 }}>
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 4" vertical={false} />
              <XAxis type="number" dataKey="x" domain={domains?.x ?? ['auto', 'auto']} allowDataOverflow={!!domains}
                allowDuplicatedCategory={false}
                tickFormatter={axisNumber} tick={{ fontSize: 14, fill: '#64748b' }}
                axisLine={{ stroke: '#cbd5e1' }} tickLine={false} minTickGap={32}
                label={{ value: chart.x.label, position: 'bottom', offset: 12, fontSize: 14, fill: '#475569' }} />
              <YAxis type="number" dataKey="y" domain={domains?.y ?? ['auto', 'auto']} allowDataOverflow={!!domains} width={76}
                tickFormatter={axisNumber} tick={{ fontSize: 14, fill: '#64748b' }}
                axisLine={false} tickLine={false} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null
                  const entries = payload.filter(entry => Number.isFinite(entry.payload?.x) && Number.isFinite(entry.payload?.y))
                  return <div className="max-w-[280px] rounded-xl border border-slate-200 bg-white/95 p-3 text-sm leading-relaxed shadow-sm">
                    {entries.map((entry, index) => <div key={index} className={index > 0 ? 'mt-2 border-t border-slate-100 pt-2' : ''}>
                      <p className="font-medium text-slate-700">{entry.name}</p>
                      <p className="text-slate-500">{chart.x.label} = {formatCalculationNumber(entry.payload.x)}</p>
                      <p className="text-slate-500">{chart.y.label} = {formatCalculationNumber(entry.payload.y)}</p>
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
              {viewSeries.map((series, index) => {
                const color = series.role === 'virtual' ? '#94a3b8' : SERIES_COLORS[index % SERIES_COLORS.length]
                return series.kind === 'line' ? (
                  <Line key={series.id} data={series.points} type={series.interpolation ?? 'linear'} dataKey="y" name={series.label}
                    stroke={color} strokeWidth={2} dot={series.points.length < 80 ? { r: 2, fill: color, strokeWidth: 0 } : false}
                    strokeDasharray={series.role === 'virtual' ? '5 4' : undefined}
                    activeDot={{ r: 4 }} isAnimationActive={false} connectNulls={false} />
                ) : (
                  <Scatter key={series.id} name={series.label} data={series.points} fill={color}
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
        {chart.series.map((series, index) => (
          <span key={series.id} className="inline-flex items-center gap-1.5">
            <span className={`inline-block h-2 w-2 shrink-0 ${series.kind === 'line' ? 'rounded-sm' : 'rounded-full'}`}
              style={{ backgroundColor: series.role === 'virtual' ? '#94a3b8' : SERIES_COLORS[index % SERIES_COLORS.length] }} />
            {series.label}
          </span>
        ))}
        {!!chart.selected?.length && Array.from(new Set(chart.selected.map(point => point.label ?? '最终选择'))).map(label => (
          <span key={label} className="inline-flex items-center gap-1.5 text-amber-800"><span className="h-2 w-2 rounded-full bg-[#b7791f]" />{label}</span>
        ))}
      </div>
    </section>
  )
}

function RunRecords({ trace }: { trace: CalculationTrace }) {
  const [open, setOpen] = useState(false)
  return (
    <details className="group mt-4 rounded-xl border border-slate-200/80 bg-slate-50/60"
      onToggle={event => setOpen(event.currentTarget.open)}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-3 text-base font-medium text-slate-600 hover:text-slate-900">
        本次计算记录
        <ChevronDown size={18} className="shrink-0 transition-transform group-open:rotate-180" />
      </summary>
      {open && <div className="border-t border-slate-200 px-4 py-3">
        <pre className="max-h-[440px] overflow-auto whitespace-pre text-sm leading-relaxed text-slate-700" tabIndex={0}>{JSON.stringify(trace, null, 2)}</pre>
      </div>}
    </details>
  )
}

function RootComparison({ chart }: { chart: CalculationChart }) {
  const points = chart.series.flatMap(series => series.points)
  return <section className="min-w-0 rounded-xl border border-slate-200/70 px-4 py-3">
    <h3 title={chart.description} className="text-base font-semibold text-slate-800">{chart.title}</h3>
    {chart.formula && <ProcessFormula expression={chart.formula} />}
    <div className="mt-2 overflow-x-auto"><table className="w-full text-right text-base tabular-nums">
      <thead className="text-slate-500"><tr>{['候选','β','γ','T₁','T₂','T₁²+T₂²'].map(label=><th key={label} className="whitespace-nowrap px-2 py-2 font-medium">{label}</th>)}</tr></thead>
      <tbody>{points.map((point,index)=><tr key={index} className={chart.selected?.some(p=>p.x===point.x && p.y===point.y) ? 'bg-amber-50/70 text-amber-900' : 'text-slate-700'}>
        <td className="whitespace-nowrap px-2 py-2">{chart.selected?.some(p=>p.x===point.x && p.y===point.y) ? '最终选择' : index+1}{point.candidate_kind==='boundary_residual_tolerance' ? '（边界近似）' : ''}</td>
        {[point.beta,point.gamma,point.t1,point.t2,point.y].map((value,i)=><td key={i} className="px-2 py-2">{formatCalculationNumber(value)}</td>)}
      </tr>)}</tbody>
    </table></div>
  </section>
}

export function CalculationProcessViewer({ calculation, methodId, stale = false, isUpdating = false }: CalculationProcessViewerProps) {
  const { trace, error } = readCalculationTrace(calculation, methodId)
  if (!trace) {
    const message = error === 'method_mismatch'
      ? '这份运行记录属于其他方法，请重新计算。'
      : error === 'invalid'
        ? '本次计算记录不完整，暂时无法展示过程图。请重新计算。'
        : '这份结果尚无真实计算过程记录，请重新计算后查看。'
    return <div role="status" className="flex items-start gap-2 rounded-xl bg-slate-100/70 px-4 py-4 text-base leading-relaxed text-slate-600"><Info size={19} className="mt-0.5 shrink-0" />{message}</div>
  }

  const runId = trace.run && typeof trace.run === 'object' && 'id' in trace.run ? String(trace.run.id) : undefined
  const failed = typeof trace.selection.status === 'string' && trace.selection.status !== 'ok'
  const showSelection = failed || trace.selection.approximate === true || !trace.recovery?.length
  const mainCharts = trace.charts.filter(chart => chart.id !== 'candidate-residuals')

  return (
    <div className="min-w-0 space-y-4" data-calculation-method={trace.method}>
      {stale && <p role="status" className="rounded-xl bg-amber-50 px-4 py-3 text-base text-amber-800">{isUpdating ? '正在按新设置重新计算；下方为上一次计算的记录。' : '设置已改变；下方仍是上一次计算的记录，请重新计算。'}</p>}
      {showSelection && <div className={`flex items-start gap-3 rounded-xl px-4 py-4 ${failed || trace.selection.approximate === true ? 'bg-amber-50' : 'bg-slate-100/70'}`}>
        {failed ? <Info size={20} className="mt-0.5 shrink-0 text-amber-700" /> : <Check size={20} className="mt-0.5 shrink-0 text-amber-700" />}
        <div className="min-w-0">
          <h2 className={`text-lg font-semibold leading-snug ${failed ? 'text-amber-900' : 'text-slate-800'}`}>{failed ? '未得到可采纳结果' : trace.selection.approximate === true ? '近似结果' : '本次估计'}</h2>
          {(failed || trace.selection.approximate === true) && <p className="mt-1 text-base leading-relaxed text-slate-700">{trace.selection.description}</p>}
          <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-base tabular-nums text-slate-800">
            {(['beta', 'eta', 'gamma'] as const).map((key, index) => trace.selection[key] !== undefined && trace.selection[key] !== null && (
              <div key={key} className="flex items-baseline gap-1"><dt className="text-slate-500">{['β̂', 'η̂', 'γ̂'][index]} =</dt><dd className="font-semibold">{formatCalculationNumber(trace.selection[key])}</dd></div>
            ))}
          </dl>
        </div>
      </div>}
      <div className={`grid min-w-0 grid-cols-1 items-start gap-4 ${mainCharts.length === 3 ? 'xl:grid-cols-3' : 'xl:grid-cols-2'}`}>
        {mainCharts.map(chart => <ProcessChart key={`${runId ?? ''}-${chart.id}`} chart={chart} />)}
      </div>
      {!!trace.recovery?.length && <section aria-label="由判据确定参数" className="grid min-w-0 grid-cols-1 gap-0 rounded-2xl bg-slate-100/60 sm:grid-cols-3">
        {trace.recovery.map((step, index) => <div key={step.title} className="min-w-0 px-4 py-4 sm:px-5">
          <h3 className="text-base font-semibold text-slate-800"><span className="mr-2 text-slate-400">{index + 1}</span>{step.title}</h3>
          <ProcessFormula expression={step.formula} />
          <dl className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-base tabular-nums">
            {step.values.map(item => <div key={item.label} className="flex gap-1"><dt className="text-slate-500">{item.label} =</dt><dd className="font-medium text-slate-800">{formatCalculationNumber(item.value)}</dd></div>)}
          </dl>
        </div>)}
      </section>}
      {trace.charts.filter(chart=>chart.id==='candidate-residuals').map(chart=><RootComparison key={chart.id} chart={chart} />)}
      <RunRecords key={runId ?? `${trace.method}-${trace.selection.beta}-${trace.selection.gamma}`} trace={trace} />
    </div>
  )
}
