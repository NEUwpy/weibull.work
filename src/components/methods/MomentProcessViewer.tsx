"use client"

import { useState } from 'react'
import { Area, AreaChart, CartesianGrid, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ProcessChart, ProcessFormula } from '@/components/shared/charts/CalculationProcessChart'
import { type CalculationTrace, formatCalculationNumber as number } from '@/lib/calculation-trace'
import { CalculationStepContent, ProcessDetails } from './CalculationSteps'

interface MomentInterval { left: number; right: number; survival: number; contributions: Record<string, number> }
interface MomentDetails {
  m1: number; m2: number; m4: number
  moment_intervals: MomentInterval[]
  formula_values: { d12: number; d24: number; minimum: number }
  raw_estimate: { beta: number; eta: number; gamma: number }
  location_adjustment: string | null
  location_calculation?: { alternative: number | null }
}

export function MomentProcessViewer({ trace, step }: { trace: CalculationTrace; step: number }) {
  const [power, setPower] = useState(1)
  const [selectedInterval, setSelectedInterval] = useState<number | null>(null)
  const details = trace.details as MomentDetails | undefined
  const intervals = details?.moment_intervals
  if (!details || !Array.isArray(intervals) || !intervals.length || !details.formula_values) return <div className="grid min-w-0 gap-4 xl:grid-cols-2">{trace.charts.map(chart => <ProcessChart key={chart.id} chart={chart} />)}</div>
  const intervalIndex = Math.min(selectedInterval ?? 0, intervals.length - 1)
  const interval = intervals[intervalIndex]
  const curve = trace.charts.find(chart => chart.id === 'weibull-moments')?.series.find(series => series.id === `survival-${power}`)?.points ?? []
  const moment = power === 1 ? details.m1 : power === 2 ? details.m2 : details.m4
  const values = details.formula_values
  const raw = details.raw_estimate
  if (step === 0) return <div className="min-w-0 space-y-4" data-moment-process>
    <CalculationStepContent title="由阶梯面积得到三个矩"
      axes={{ x: '失效时间 t', y: `经验生存函数的 ${power} 次幂 Ŝf(t)ᵏ` }}
      calculation={<ProcessFormula expression={String.raw`\widehat S_f(t)^k=(1-r/n)^k\quad (t_{(r)}\le t<t_{(r+1)})`} />}
      criterion={<>
        <ProcessFormula expression={String.raw`\bar m_k=\sum_{r=0}^{n-1}(1-r/n)^k(t_{(r+1)}-t_{(r)}),\qquad t_{(0)}=0`} />
        <p className="text-base text-slate-700">累加图中阶梯下面积，当前 m̄{power} = {number(moment)}。</p>
      </>}
      symbols={[
        ['t₍ᵣ₎', '排序后的第 r 个失效时间，圆点标记样本位置'], ['n', '样本量'], ['r', '当前间隔左端累计失效数'],
        ['Ŝf(t)', '样本中失效时间大于 t 的比例'], ['k', '生存函数的幂次，取 1、2 或 4'], ['m̄ₖ', '相应阶梯面积给出的样本矩'],
      ]}
      figure={<>
      <div className="grid gap-3 sm:grid-cols-3">{[1, 2, 4].map(k => <button key={k} type="button" onClick={() => setPower(k)} aria-pressed={power === k}
        className={`rounded-xl border px-4 py-3 text-left text-base ${power === k ? 'border-emerald-600 bg-emerald-50 text-emerald-900' : 'border-slate-200 text-slate-600'}`}>
        <span>生存函数{k === 1 ? '' : `的 ${k} 次幂`}曲线下面积</span><strong className="mt-1 block text-xl">m̄{k} = {number(k === 1 ? details.m1 : k === 2 ? details.m2 : details.m4)}</strong>
      </button>)}</div>
      <div className="h-[300px] min-w-0" role="img" aria-label={`经验生存函数${power}次幂的阶梯面积为${number(moment)}`}>
        <ResponsiveContainer width="100%" height="100%"><AreaChart data={curve} margin={{ top: 20, right: 16, bottom: 30, left: 0 }}>
          <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 4" vertical={false} />
          <XAxis type="number" dataKey="x" domain={['dataMin', 'dataMax']} tick={{ fontSize: 14 }} minTickGap={40} tickFormatter={value => number(value)} label={{ value: '失效时间 t', position: 'bottom', offset: 10, fontSize: 14 }} />
          <YAxis type="number" dataKey="y" domain={[0, 1]} width={48} tick={{ fontSize: 14 }} />
          <Tooltip formatter={value => number(value)} labelFormatter={value => `t = ${number(value)}`} />
          <Area type="stepAfter" dataKey="y" name={`Ŝf(t)^${power}`} stroke="#047857" fill="#6ee7b7" fillOpacity={0.32}
            dot={(props: any) => props.index === 0 ? <g key={props.index} /> : <circle key={props.index} className="moment-sample-node" cx={props.cx} cy={props.cy} r={2.5} fill="#047857" stroke="#fff" strokeWidth={0.5} />}
            isAnimationActive={false} />
          {selectedInterval !== null && <ReferenceArea x1={interval.left} x2={interval.right} y1={0} y2={interval.survival ** power} fill="#d97706" fillOpacity={0.35} stroke="#b45309" />}
        </AreaChart></ResponsiveContainer>
      </div>
      </>} />
    <ProcessDetails title="查看各间隔的面积贡献">
      <label className="block text-base text-slate-700" htmlFor="moment-interval">查看第 {intervalIndex + 1} 个样本间隔</label>
      <input id="moment-interval" aria-label="选择样本间隔并查看面积贡献" type="range" min={0} max={intervals.length - 1} value={intervalIndex} onChange={event => setSelectedInterval(Number(event.target.value))} className="w-full accent-amber-700" />
      <p className="text-base leading-relaxed text-slate-700">高 {number(interval.survival ** power)} × 宽（{number(interval.right)} − {number(interval.left)}）= <strong>{number(interval.contributions[String(power)])}</strong>。</p>
    </ProcessDetails>
  </div>
  if (step === 1) return <CalculationStepContent title="把三个矩代入显式解"
    calculation={<ProcessFormula expression={String.raw`\begin{aligned}\beta^*&=\frac{\ln2}{\ln(\bar m_1-\bar m_2)-\ln(\bar m_2-\bar m_4)}\\\gamma^*&=\frac{\bar m_1\bar m_4-\bar m_2^2}{\bar m_1+\bar m_4-2\bar m_2}\\\eta^*&=\frac{\bar m_1-\gamma^*}{\Gamma(1+1/\beta^*)}\end{aligned}`} />}
    criterion={<>
      <ProcessFormula expression={String.raw`\bar m_1-\bar m_2>\bar m_2-\bar m_4>0`} />
      <p className="text-base text-slate-700">本次矩差分别为 {number(values.d12)} 和 {number(values.d24)}。显式解为 β* = {number(raw.beta)}、γ* = {number(raw.gamma)}、η* = {number(raw.eta)}。</p>
    </>}
    symbols={[
      ['m̄₁、m̄₂、m̄₄', '上一步由阶梯面积计算的三个样本矩'], ['β*、γ*、η*', '检查位置范围前的形状、位置和尺度'], ['Γ', '伽马函数'],
    ]} />

  const alternative = details.location_adjustment === 'alternative_a_star_star'
  return <CalculationStepContent title="检查位置范围，确定返回参数"
    calculation={details.location_adjustment ? <>
      {alternative && <ProcessFormula expression={String.raw`\gamma^{**}=t_{(1)}-\frac{\eta^*\Gamma(1+1/\beta^*)}{n^{1/\beta^*}}`} />}
      <ProcessFormula expression={String.raw`\hat\eta=\frac{\bar m_1-\hat\gamma}{\Gamma(1+1/\beta^*)}`} />
    </> : undefined}
    criterion={<>
      <ProcessFormula expression={alternative ? String.raw`\gamma^*\ge t_{(1)}\ \Longrightarrow\ \hat\gamma=\max(0,\gamma^{**})`
        : details.location_adjustment === 'clamped_to_zero' ? String.raw`\gamma^*<0\ \Longrightarrow\ \hat\gamma=0`
          : String.raw`0\le\gamma^*<t_{(1)}\ \Longrightarrow\ \hat\gamma=\gamma^*,\quad\hat\eta=\eta^*`} />
      <p className="text-base text-slate-700">最小观测 t₍₁₎ = {number(values.minimum)}，显式位置 γ* = {number(raw.gamma)}{alternative ? `，替代位置 γ** = ${number(details.location_calculation?.alternative)}` : ''}。本次返回 β̂ = {number(trace.selection.beta)}、γ̂ = {number(trace.selection.gamma)}、η̂ = {number(trace.selection.eta)}。</p>
    </>}
    symbols={[
      ['t₍₁₎', '最小观测值'], ['β*、γ*、η*', '上一步的显式解'], ['β̂、γ̂、η̂', '检查位置后返回的三个参数'],
      ...(details.location_adjustment ? [['m̄₁', '前一步得到的第一个样本矩'], ['Γ', '伽马函数']] as const : []),
      ...(alternative ? [['γ**', '由最小观测和显式参数求出的替代位置'], ['n', '样本量']] as const : []),
    ]} />
}
