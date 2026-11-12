'use client'

import { useMemo } from 'react'
import { ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import { processPlotAxes, processPlotFrame, ProcessYAxisLabel } from './ProcessPlot'
import { formatCalculationNumber as number } from '@/lib/calculation-trace'

interface SampleRun {
  id: number
  sample: readonly number[]
}

interface Observation {
  runId: number
  rank: number
  index: number
  time: number
}

const observationColor = '#426981'
const minimumColor = '#c27f45'
const gapColor = '#cbd5e1'
const truthColor = '#475569'

export function ProcessSampleChart({ runs, trueGamma, selectedRun, onSelect }: {
  runs: readonly SampleRun[]; trueGamma?: number; selectedRun: number | null; onSelect: (id: number) => void
}) {
  const origin = Number.isFinite(trueGamma) ? trueGamma : undefined
  const plot = useMemo(() => {
    const sorted = runs.filter(run => run.sample.length > 0)
      .map(run => ({ id: run.id, sample: [...run.sample].sort((a, b) => a - b) }))
      .sort((a, b) => a.sample[0] - b.sample[0] || a.id - b.id)
    if (!sorted.length) return null
    const observations: Observation[] = []
    const minima: Observation[] = []
    let min = origin ?? Infinity, max = origin ?? -Infinity
    sorted.forEach((run, row) => {
      run.sample.forEach((time, index) => {
        const point = { runId: run.id, rank: row + 1, index: index + 1, time }
        if (index === 0) minima.push(point)
        else observations.push(point)
        min = Math.min(min, time)
        max = Math.max(max, time)
      })
    })
    const padding = (max - min) * .025 || 1
    const timeDomain: [number, number] = [min - padding, max + padding]
    const targetStep = (max - min) / 3 || 1
    const magnitude = 10 ** Math.floor(Math.log10(targetStep))
    const step = [1, 2, 2.5, 5, 10].map(factor => factor * magnitude).reduce((best, candidate) =>
      Math.abs(candidate - targetStep) < Math.abs(best - targetStep) ? candidate : best)
    const anchor = origin ?? 0
    const firstTick = Math.ceil((timeDomain[0] - anchor) / step)
    const lastTick = Math.floor((timeDomain[1] - anchor) / step)
    const timeTicks = Array.from({ length: lastTick - firstTick + 1 }, (_, index) => anchor + (firstTick + index) * step)
    return { observations, minima, timeDomain, timeTicks }
  }, [runs, origin])
  if (!plot) return null
  const { observations, minima, timeDomain, timeTicks } = plot
  const rankTicks = Array.from(new Set([1, Math.ceil(minima.length / 2), minima.length]))

  function dot({ cx, cy, payload }: { cx?: number; cy?: number; payload?: Observation }) {
    if (!payload || cx === undefined || cy === undefined) return <g />
    const minimum = payload.index === 1
    const active = selectedRun === payload.runId
    return <circle cx={cx} cy={cy} r={minimum ? active ? 3 : 2 : active ? 2 : 1.45}
      fill={minimum ? minimumColor : observationColor}
      opacity={selectedRun === null || active ? 1 : .36}
      data-sample-observation={payload.index} data-sample-run={payload.runId}
      data-sample-rank={payload.rank} data-sample-selected={active || undefined}
      className="cursor-pointer" onClick={() => onSelect(payload.runId)} />
  }

  return <div>
    <div className={processPlotFrame} data-process-plot role="group" aria-label="按最小观测排序的样本散点图">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={processPlotAxes.margin}>
          <XAxis type="number" dataKey="time" domain={timeDomain} allowDataOverflow height={processPlotAxes.xAxisHeight}
            ticks={timeTicks} minTickGap={24} tickFormatter={number} tick={{ fontSize: 14, fill: '#64748b' }}
            axisLine={{ stroke: '#cbd5e1' }} tickLine={false}
            label={{ value: '寿命 t', position: 'bottom', offset: 8, fontSize: 14, fill: '#475569' }} />
          <YAxis type="number" dataKey="rank" domain={[.2, minima.length + .8]} reversed allowDataOverflow
            ticks={rankTicks} width={processPlotAxes.yAxisWidth} tick={{ fontSize: 14, fill: '#64748b' }}
            axisLine={{ stroke: '#cbd5e1' }} tickLine={false}
            label={{ value: '排序序号', content: <ProcessYAxisLabel /> }} />
          <Tooltip cursor={false} isAnimationActive={false} content={({ active, payload }) => {
            const point = payload?.[0]?.payload as Observation | undefined
            if (!active || !point) return null
            return <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm tabular-nums text-slate-700 shadow-sm">
              <p>第 {point.runId} 次 · 排序第 {point.rank} 行</p>
              <p>t<sub>({point.index})</sub> = {number(point.time)}</p>
              {point.index === 1 && origin !== undefined && <p>t<sub>(1)</sub> − γ = {number(point.time - origin)}</p>}
            </div>
          }} />
          {origin !== undefined && minima.map(point => <ReferenceLine key={point.runId}
            segment={[{ x: origin, y: point.rank }, { x: point.time, y: point.rank }]}
            stroke={point.runId === selectedRun ? minimumColor : gapColor} />)}
          {origin !== undefined && <ReferenceLine x={origin} stroke={truthColor} strokeDasharray="4 3" />}
          <Scatter data={observations} shape={dot} isAnimationActive={false} />
          <Scatter data={minima} shape={dot} isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-600">
      <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: observationColor }} />观测</span>
      <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: minimumColor }} />最小观测</span>
      {origin !== undefined && <>
        <span className="inline-flex items-center gap-1.5"><span className="w-4 border-t" style={{ borderColor: gapColor }} />起点至最小观测</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-4 border-t border-dashed" style={{ borderColor: truthColor }} />真实起点 γ = {number(origin)}</span>
      </>}
    </div>
  </div>
}
