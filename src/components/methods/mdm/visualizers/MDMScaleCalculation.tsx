"use client"

import { useId, useState } from 'react'
import { ProcessEquation } from '@/components/shared/charts/ProcessEquation'
import { ProcessValueTable } from '@/components/shared/charts/ProcessValueTable'
import { formatCalculationNumber as number } from '@/lib/calculation-trace'
import type { PseudoScaleValue } from './process-data'

const mathNumber = (value: number) => number(value).replace(/e([+-]?\d+)/, String.raw`\times10^{$1}`)

export function MDMScaleValues({ values, total }: { values: PseudoScaleValue[]; total: number | null }) {
  if (!values.length) return <p className="text-slate-500">本次记录未包含逐样本伪尺度。</p>
  return <ProcessValueTable label="各样本的伪尺度值"
    columns={[{ label: '样本序号 i' }, { label: '伪尺度 ηᵢ', align: 'right' }]}
    rows={values.map((value, index) => [index + 1, number(value.eta)])}
    footer={total !== null && <><span>合计（{values.length} 个）</span><strong className="font-medium">{number(total)}</strong></>} />
}

export function MDMScaleCalculation({ values, beta, gamma, eta, total }: {
  values: PseudoScaleValue[]; beta: number; gamma: number; eta: number; total: number | null
}) {
  const [index, setIndex] = useState(0)
  const sliderId = useId()
  const currentIndex = Math.min(index, Math.max(0, values.length - 1))
  const point = values[currentIndex]
  const mean = String.raw`\hat\eta`
    + (total !== null && values.length > 0 ? String.raw`\approx\frac{${mathNumber(total)}}{${values.length}}` : '')
    + String.raw`\approx${mathNumber(eta)}`
  const substitution = point ? String.raw`\begin{aligned}&\eta_{${currentIndex + 1}}\approx\frac{${mathNumber(point.observation)}-${mathNumber(gamma)}}{[-\ln(1-${mathNumber(point.rank)})]^{1/${mathNumber(beta)}}}`
    + (point.distance !== undefined && point.denominator !== undefined
      ? String.raw`\\[10pt]&\approx\frac{${mathNumber(point.distance)}}{${mathNumber(point.denominator)}}` : '')
    + String.raw`\\[10pt]&\approx${mathNumber(point.eta)}\end{aligned}` : ''
  return <div className="min-w-0 space-y-4" aria-label="本次数值计算">
    <ProcessEquation expression={mean} />
    {point && <details>
      <summary className="cursor-pointer text-sm text-slate-600">逐样本反算</summary>
      <div className="mt-3 min-w-0 space-y-2">
        <label htmlFor={sliderId} className="text-base text-slate-700">第 {currentIndex + 1} 个样本</label>
        <input id={sliderId} aria-label="查看每个样本怎样算出伪尺度" type="range" min={0} max={values.length - 1} step={1}
          value={currentIndex} onChange={event => setIndex(Number(event.target.value))} className="w-full accent-blue-600" />
        <p className="text-sm tabular-nums text-slate-600">t = {number(point.observation)}，p = {number(point.rank)}</p>
        <ProcessEquation expression={substitution} />
      </div>
    </details>}
  </div>
}
