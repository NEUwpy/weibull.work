"use client"

import { useState } from 'react'
import { ProcessChart } from '@/components/shared/charts/CalculationProcessChart'
import { ProcessEquation } from '@/components/shared/charts/ProcessEquation'
import { ProcessValueTable } from '@/components/shared/charts/ProcessValueTable'
import { type CalculationChart, type CalculationTrace, readPowerScaleCalculation, formatCalculationNumber as number } from '@/lib/calculation-trace'
import { ProcessDetails } from './ProcessDetails'

const math = (value: unknown) => number(value).replace(/e([+-]?\d+)/, String.raw`\times10^{$1}`)

export function PowerScaleCalculation({ trace, view }: { trace: CalculationTrace; view: 'chart' | 'table' | 'details' }) {
  const data = readPowerScaleCalculation(trace)
  const [index, setIndex] = useState<number | null>(null)
  if (!data) return trace.selection.status === 'ok' ? <p className="text-base text-amber-800">这份记录缺少逐样本的尺度计算，请重新计算后查看。</p> : null
  const current = Math.min(index ?? 0, data.samples.length - 1)
  const sample = data.samples[current]
  const weighted = trace.method === 'wmle'
  const retained = trace.method === 'mmle'
  const displayIndex = sample.index - (retained ? 1 : 0)
  const distanceSymbol = retained ? 'y' : 'd'
  const scaled = data.use_scaled
  const total = scaled ? data.scaled_sum : data.power_sum
  const mean = scaled ? data.scaled_mean : data.power_mean
  const power = scaled ? sample.scaled_power : sample.power
  const chart: CalculationChart = {
    id: 'scale-sample-contributions', title: '每个样本对幂次总和的贡献',
    x: { key: 'x', label: '样本顺序 i' }, y: { key: 'y', label: scaled ? `(${distanceSymbol}ᵢ/${distanceSymbol}max)^β̂` : `${distanceSymbol}ᵢ^β̂` },
    series: [{ id: 'powers', label: '逐样本幂次贡献', kind: 'scatter', role: 'diagnostic',
      points: data.samples.map(point => ({ x: point.index - (retained ? 1 : 0), y: (scaled ? point.scaled_power : point.power)! })) }],
    references: [{ axis: 'y', value: mean!, label: `A = ${number(mean)}` }],
  }
  const substitution = String.raw`\begin{aligned}${distanceSymbol}_{${displayIndex}}&=${math(sample.observation)}-${math(data.gamma)}\approx${math(sample.distance)}\\c_{${displayIndex}}&`
    + (scaled ? String.raw`=\left(\frac{${math(sample.distance)}}{${math(data.reference_distance)}}\right)^{${math(data.beta)}}` : String.raw`=${math(sample.distance)}^{${math(data.beta)}}`)
    + String.raw`\approx${math(power)}\end{aligned}`
  if (view === 'chart') return <div className="space-y-4">
    <ProcessChart chart={chart} initiallyFocused={false} figureOnly workspacePlot showYAxisLabel />
    <ProcessDetails title="查看全部样本的尺度计算数值"><PowerScaleCalculation trace={trace} view="table" /></ProcessDetails>
  </div>
  if (view === 'table') return <ProcessValueTable label="逐样本尺度贡献" minColumnWidth={440}
    columns={[{ label: '序号', math: 'i' }, { label: retained ? '保留观测' : '排序样本', math: retained ? 't_{(i+1)}' : 't_{(i)}', align: 'right' }, { label: '平移距离', math: retained ? 'y_i' : 'd_i', align: 'right' },
      { label: scaled ? '归一化幂次' : '幂次贡献', math: 'c_i', align: 'right' }]}
    rows={data.samples.map(point => [point.index - (retained ? 1 : 0), number(point.observation), number(point.distance), number(scaled ? point.scaled_power : point.power)])}
    footer={<><span>Σcᵢ = {number(total)}</span><span>{retained ? 'q' : 'n'} = {data.count}</span></>} />
  if (view === 'details') return <div className="min-w-0 space-y-4" aria-label="尺度数值代入">
    <ProcessEquation expression={String.raw`\begin{aligned}&A\approx\frac{${math(total)}}{${data.count}${weighted ? String.raw`\times${math(data.normalizer)}` : ''}}\approx${math(mean)}\\[10pt]&\hat\eta\approx${scaled ? String.raw`${math(data.reference_distance)}\times` : ''}${math(mean)}^{1/${math(data.beta)}}\\[10pt]&\approx${math(data.eta)}\end{aligned}`} />
    <details><summary className="cursor-pointer text-sm text-slate-600">逐样本计算</summary>
      <div className="mt-3 space-y-2">
        <p className="text-sm text-slate-600">第 {displayIndex} 个样本</p>
        <input aria-label="查看每个样本的尺度贡献" type="range" min={0} max={data.samples.length - 1} step={1}
          value={current} onChange={event => setIndex(Number(event.target.value))} className="w-full accent-emerald-600" />
        <ProcessEquation expression={substitution} />
      </div>
    </details>
  </div>
}
