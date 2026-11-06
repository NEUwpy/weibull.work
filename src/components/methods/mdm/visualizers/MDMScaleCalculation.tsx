"use client"

import { useState } from 'react'
import { ProcessChart, ProcessFormula } from '@/components/shared/charts/CalculationProcessChart'
import { type CalculationChart, formatCalculationNumber as number } from '@/lib/calculation-trace'
import type { PseudoScaleValue } from './process-data'
import { CalculationStepContent, ProcessDetails } from '@/components/methods/CalculationSteps'

const mathNumber = (value: number) => number(value).replace(/e([+-]?\d+)/, String.raw`\times10^{$1}`)

export function MDMScaleCalculation({ values, beta, gamma, eta, total, rankMethod }: {
  values: PseudoScaleValue[]; beta: number; gamma: number; eta: number; total: number | null; rankMethod: string | null
}) {
  const [index, setIndex] = useState<number | null>(null)
  const currentIndex = Math.min(index ?? 0, Math.max(0, values.length - 1))
  const point = values[currentIndex]
  const mean = String.raw`\begin{aligned}\hat\eta&=\frac{1}{n}\sum_{i=1}^n\eta_i\\&`
    + (total !== null ? String.raw`\approx\frac{${mathNumber(total)}}{${values.length}}` : '')
    + String.raw`\approx${mathNumber(eta)}\end{aligned}`
  const substitution = point ? String.raw`\begin{aligned}\eta_{${currentIndex + 1}}&\approx\frac{${mathNumber(point.observation)}-${mathNumber(gamma)}}{[-\ln(1-${mathNumber(point.rank)})]^{1/${mathNumber(beta)}}}\\&`
    + (point.distance !== undefined && point.denominator !== undefined
      ? String.raw`\approx\frac{${mathNumber(point.distance)}}{${mathNumber(point.denominator)}}` : '')
    + String.raw`\approx${mathNumber(point.eta)}\end{aligned}` : ''
  const chart: CalculationChart = {
    id: 'pseudo-scale-values', title: '各样本反算的伪尺度值与最终均值',
    x: { key: 'x', label: '样本值 t₍ᵢ₎' }, y: { key: 'y', label: '伪尺度值 ηᵢ' },
    series: [{ id: 'pseudo-scales', label: '每个样本对应的 ηᵢ', kind: 'scatter', role: 'diagnostic',
      points: values.map((value, i) => ({ x: value.observation, y: value.eta, index: i + 1 })) }],
    references: [{ axis: 'y', value: eta, label: `平均值 η̂ = ${number(eta)}` }],
  }
  if (index !== null && point) chart.series.push({
    id: 'current-sample', label: `当前查看的第 ${currentIndex + 1} 个样本`, kind: 'scatter', role: 'diagnostic',
    points: [{ x: point.observation, y: point.eta }],
  })
  return <CalculationStepContent title="伪尺度取平均，得到尺度 η"
      figure={values.length > 0 && <ProcessChart chart={chart} initiallyFocused={false} figureOnly />}
      axes={values.length > 0 ? { x: '排序后的样本值 t₍ᵢ₎', y: '该样本反算的伪尺度 ηᵢ' } : undefined}
      calculation={<>
        <ProcessFormula expression={String.raw`\eta_i=\frac{t_{(i)}-\hat\gamma}{[-\ln(1-p_i)]^{1/\hat\beta}}`} />
        {rankMethod === 'bernard' && <ProcessFormula expression={String.raw`p_i=\frac{i-0.3}{n+0.4}`} />}
        {rankMethod === 'exact' && <ProcessFormula expression={String.raw`p_i=Q_{\mathrm{Beta}(i,n+1-i)}(0.5)`} />}
        <p className="text-base text-slate-700">代入 β̂ = {number(beta)}、γ̂ = {number(gamma)}。</p>
      </>}
      criterion={<ProcessFormula expression={mean} />}
      symbols={[
        ['i', '按样本值从小到大的序号'], ['n', '样本量'],
        ['pᵢ', rankMethod === 'exact' ? 'Beta(i, n+1−i) 分布的中位数' : rankMethod === 'bernard' ? '按 Bernard 中位秩估计的累计概率' : '第 i 个样本的经验累计概率'],
        ...(rankMethod === 'exact' ? [['Q', '所标分布的分位数函数']] as const : []),
        ['β̂、γ̂', '上方采纳的形状和位置'], ['η̂', '所有伪尺度的算术平均值，图中为水平虚线'],
      ]}
      details={point && <ProcessDetails title="查看各样本的代入计算">
      <div className="rounded-xl bg-blue-50/60 px-4 py-3">
        <label htmlFor="mdm-scale-observation" className="text-base font-medium text-slate-800">查看第 {currentIndex + 1} 个样本的代入计算</label>
        <input id="mdm-scale-observation" aria-label="查看每个样本怎样算出伪尺度" type="range" min={0} max={values.length - 1} step={1}
          value={currentIndex} onChange={event => setIndex(Number(event.target.value))} className="mt-3 w-full accent-blue-600" />
        <p className="mt-2 text-base tabular-nums text-slate-700">t₍{currentIndex + 1}₎ = {number(point.observation)}，p{currentIndex + 1} = {number(point.rank)}</p>
        <ProcessFormula expression={substitution} />
      </div>
      <details className="text-base text-slate-600">
        <summary className="cursor-pointer">查看全部样本与伪尺度值</summary>
        <div className="mt-3 max-h-80 overflow-auto"><table className="w-full text-right text-sm tabular-nums">
          <thead><tr>{['样本序号 i', '样本 t₍ᵢ₎', '经验概率 pᵢ', '伪尺度 ηᵢ'].map(label => <th key={label} className="whitespace-nowrap px-3 py-2 font-medium">{label}</th>)}</tr></thead>
          <tbody>{values.map((value, i) => <tr key={i} className={i === currentIndex ? 'bg-blue-50 text-blue-900' : ''}>
            {[i + 1, value.observation, value.rank, value.eta].map((value, j) => <td key={j} className="whitespace-nowrap px-3 py-2">{number(value)}</td>)}
          </tr>)}</tbody>
        </table></div>
      </details>
      </ProcessDetails>} />
}
