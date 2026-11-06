"use client"

import { useState } from 'react'
import { ProcessChart, ProcessFormula } from '@/components/shared/charts/CalculationProcessChart'
import { CalculationStepContent, ProcessDetails } from './CalculationSteps'
import { type CalculationChart, type CalculationTrace, readPowerScaleCalculation, formatCalculationNumber as number } from '@/lib/calculation-trace'

const math = (value: unknown) => number(value).replace(/e([+-]?\d+)/, String.raw`\times10^{$1}`)

export function PowerScaleCalculation({ trace }: { trace: CalculationTrace }) {
  const data = readPowerScaleCalculation(trace)
  const [index, setIndex] = useState<number | null>(null)
  if (!data) return trace.selection.status === 'ok' ? <p className="text-base text-amber-800">这份记录缺少逐样本的尺度计算，请重新计算后查看。</p> : null
  const current = Math.min(index ?? 0, data.samples.length - 1)
  const sample = data.samples[current]
  const weighted = trace.method === 'wmle'
  const retained = trace.method === 'mmle'
  const scaled = data.use_scaled
  const total = scaled ? data.scaled_sum : data.power_sum
  const mean = scaled ? data.scaled_mean : data.power_mean
  const power = scaled ? sample.scaled_power : sample.power
  const symbol = scaled ? String.raw`(d_i/d_{\max})^{\hat\beta}` : String.raw`d_i^{\hat\beta}`
  const count = retained ? 'q' : 'n'
  const divisor = `${count}${weighted ? 'J_1' : ''}`
  const chart: CalculationChart = {
    id: 'scale-sample-contributions', title: '每个样本对幂次总和的贡献',
    x: { key: 'x', label: '样本顺序 i' }, y: { key: 'y', label: scaled ? '归一化幂次 (dᵢ/dmax)^β̂' : '距离的幂次 dᵢ^β̂' },
    series: [{ id: 'powers', label: '逐样本幂次贡献', kind: 'scatter', role: 'diagnostic',
      points: data.samples.map(point => ({ x: point.index, y: (scaled ? point.scaled_power : point.power)! })) }],
    references: [{ axis: 'y', value: mean!, label: `汇总值 A = ${number(mean)}` }],
  }
  if (index !== null) chart.series.push({
    id: 'current', label: `当前查看的样本 ${sample.index}`, kind: 'scatter', role: 'diagnostic',
    points: [{ x: sample.index, y: power! }],
  })
  const substitution = String.raw`\begin{aligned}d_{${sample.index}}&=${math(sample.observation)}-${math(data.gamma)}\approx${math(sample.distance)}\\c_{${sample.index}}&`
    + (scaled ? String.raw`=\left(\frac{${math(sample.distance)}}{${math(data.reference_distance)}}\right)^{${math(data.beta)}}` : String.raw`=${math(sample.distance)}^{${math(data.beta)}}`)
    + String.raw`\approx${math(power)}\end{aligned}`
  const sum = String.raw`\begin{aligned}A&=\frac{\sum_i c_i}{${divisor}}\\&\approx\frac{${math(total)}}{${data.count}${weighted ? String.raw`\times${math(data.normalizer)}` : ''}}\approx${math(mean)}\\\hat\eta&`
    + (scaled ? String.raw`=d_{\max}A^{1/\hat\beta}\\&\approx${math(data.reference_distance)}\times${math(data.scale_factor)}` : String.raw`=A^{1/\hat\beta}\\&\approx${math(mean)}^{1/${math(data.beta)}}`)
    + String.raw`\approx${math(data.eta)}\end{aligned}`

  return <CalculationStepContent title="由样本的幂次贡献求尺度 η"
      figure={<ProcessChart chart={chart} initiallyFocused={false} figureOnly />}
      axes={{ x: '参与尺度计算的样本序号 i', y: scaled ? '归一化后的幂次贡献 cᵢ' : '平移距离的幂次 cᵢ' }}
      calculation={<>
        <ProcessFormula expression={String.raw`d_i=t_i-\hat\gamma,\qquad c_i=${symbol}`} />
        <p className="text-base text-slate-700">代入 β̂ = {number(data.beta)}、γ̂ = {number(data.gamma)}。</p>
      </>}
      criterion={<ProcessFormula expression={sum} />}
      symbols={[
        ['tᵢ', '第 i 个观测值'], ['dᵢ', '观测值减去选定位置后的距离'],
        ['β̂、γ̂', '本次选定的形状和位置'], [count, retained ? '删去最小观测后的样本量' : '样本量'],
        ['A', weighted ? '幂次贡献总和除以 nJ₁，图中为水平虚线' : '幂次贡献的平均值，图中为水平虚线'],
        ...(weighted ? [['J₁', `尺度修正权重，本次取 ${number(data.normalizer)}`] as const] : []),
        ...(scaled ? [['dmax', `最大平移距离，本次为 ${number(data.reference_distance)}`] as const] : []),
        ['η̂', '由幂次汇总值回代得到的尺度'],
      ]}
      details={<ProcessDetails title="查看逐样本的回代计算">
        <div className="rounded-xl bg-blue-50/60 px-4 py-3">
          <label htmlFor={`${trace.method}-scale-sample`} className="text-base font-medium text-slate-800">查看样本 {sample.index} 怎样形成幂次贡献</label>
          <input id={`${trace.method}-scale-sample`} aria-label="逐个查看尺度计算的样本贡献" type="range" min={0} max={data.samples.length - 1} step={1} value={current} onChange={event => setIndex(Number(event.target.value))} className="mt-3 w-full accent-blue-600" />
          <ProcessFormula expression={substitution} />
        </div>
    <details className="text-base text-slate-600"><summary className="cursor-pointer">查看全部样本的尺度计算数值</summary>
      <div className="mt-3 max-h-80 overflow-auto"><table className="w-full text-right text-sm tabular-nums"><thead><tr>{['样本 i', '观测 tᵢ', '距离 dᵢ', scaled ? '归一化幂次 cᵢ' : '幂次 cᵢ'].map(label => <th key={label} className="whitespace-nowrap px-3 py-2 font-medium">{label}</th>)}</tr></thead>
        <tbody>{data.samples.map((point, i) => <tr key={point.index} className={i === current ? 'bg-blue-50 text-blue-900' : ''}>{[point.index, point.observation, point.distance, scaled ? point.scaled_power : point.power].map((value, j) => <td key={j} className="whitespace-nowrap px-3 py-2">{number(value)}</td>)}</tr>)}</tbody>
      </table></div>
    </details>
      </ProcessDetails>} />
}
