"use client"

import { useState } from 'react'
import { Area, AreaChart, CartesianGrid, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ProcessYAxisLabel, processPlotAxes, processPlotFrame } from '@/components/shared/charts/ProcessPlot'
import { type CalculationTrace, formatCalculationNumber as number } from '@/lib/calculation-trace'
import { ProcessDetails } from './ProcessDetails'
import { useProcessAxisLabel } from './ProcessDefinitionContext'

interface MomentInterval { left: number; right: number; survival: number; contributions: Record<string, number> }
interface MomentDetails {
  m1: number; m2: number; m4: number
  moment_intervals: MomentInterval[]
}

export function MomentProcessViewer({ trace }: { trace: CalculationTrace }) {
  const xLabel = useProcessAxisLabel('weibull-moments', 'x', '失效时间 t')
  const yLabel = useProcessAxisLabel('weibull-moments', 'y', '经验生存函数 Ŝf(t)')
  const [power, setPower] = useState(1)
  const [selectedInterval, setSelectedInterval] = useState<number | null>(null)
  const details = trace.details as MomentDetails | undefined
  const intervals = details?.moment_intervals
  if (!details || !Array.isArray(intervals) || !intervals.length) return null
  const intervalIndex = Math.min(selectedInterval ?? 0, intervals.length - 1)
  const interval = intervals[intervalIndex]
  const curve = trace.charts.find(chart => chart.id === 'weibull-moments')?.series.find(series => series.id === `survival-${power}`)?.points ?? []
  const moment = power === 1 ? details.m1 : power === 2 ? details.m2 : details.m4
  return <div className="min-w-0 space-y-4" data-moment-process>
  <div className="grid gap-3 sm:grid-cols-3">{[1, 2, 4].map(k => <button key={k} type="button" onClick={() => setPower(k)} aria-pressed={power === k}
    className={`rounded-xl border px-4 py-3 text-left text-base ${power === k ? 'border-emerald-600 bg-emerald-50 text-emerald-900' : 'border-slate-200 text-slate-600'}`}>
    <span>生存函数{k === 1 ? '' : `的 ${k} 次幂`}曲线下面积</span><strong className="mt-1 block text-xl">m̄{k} = {number(k === 1 ? details.m1 : k === 2 ? details.m2 : details.m4)}</strong>
  </button>)}</div>
  <div className={processPlotFrame} data-process-plot role="img" aria-label={`经验生存函数${power}次幂的阶梯面积为${number(moment)}`}>
    <ResponsiveContainer width="100%" height="100%"><AreaChart data={curve} margin={processPlotAxes.margin}>
      <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 4" vertical={false} />
      <XAxis type="number" dataKey="x" domain={['dataMin', 'dataMax']} height={processPlotAxes.xAxisHeight} tick={{ fontSize: 14 }} minTickGap={40} tickFormatter={value => number(value)} label={{ value: xLabel, position: 'bottom', offset: 8, fontSize: 14 }} />
      <YAxis type="number" dataKey="y" domain={[0, 1]} width={processPlotAxes.yAxisWidth} tick={{ fontSize: 14 }}
        label={{ value: `${yLabel}^${power}`, content: <ProcessYAxisLabel /> }} />
      <Tooltip formatter={value => number(value)} labelFormatter={value => `t = ${number(value)}`} />
      <Area type="stepAfter" dataKey="y" name={`Ŝf(t)^${power}`} stroke="#047857" fill="#6ee7b7" fillOpacity={0.32}
        dot={(props: any) => props.index === 0 ? <g key={props.index} /> : <circle key={props.index} className="moment-sample-node" cx={props.cx} cy={props.cy} r={2.5} fill="#047857" stroke="#fff" strokeWidth={0.5} />}
        isAnimationActive={false} />
      {selectedInterval !== null && <ReferenceArea x1={interval.left} x2={interval.right} y1={0} y2={interval.survival ** power} fill="#d97706" fillOpacity={0.35} stroke="#b45309" />}
    </AreaChart></ResponsiveContainer>
  </div>
    <ProcessDetails title="查看各间隔的面积贡献">
      <label className="block text-base text-slate-700" htmlFor="moment-interval">查看第 {intervalIndex + 1} 个样本间隔</label>
      <input id="moment-interval" aria-label="选择样本间隔并查看面积贡献" type="range" min={0} max={intervals.length - 1} value={intervalIndex} onChange={event => setSelectedInterval(Number(event.target.value))} className="w-full accent-amber-700" />
      <p className="text-base leading-relaxed text-slate-700">高 {number(interval.survival ** power)} × 宽（{number(interval.right)} − {number(interval.left)}）= <strong>{number(interval.contributions[String(power)])}</strong>。</p>
    </ProcessDetails>
  </div>
}
