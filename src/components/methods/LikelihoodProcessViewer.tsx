"use client"

import { useState } from 'react'
import { ProcessChart, ProcessFormula } from '@/components/shared/charts/CalculationProcessChart'
import { type CalculationChart, type CalculationPoint, type CalculationTrace, readPowerScaleCalculation, formatCalculationNumber as number } from '@/lib/calculation-trace'

const math = (value: unknown) => number(value).replace(/e([+-]?\d+)/, String.raw`\times10^{$1}`)

interface ReadingFrame {
  gamma: number
  beta: number
  eta: number
  final: boolean
  log_likelihood?: number
  location_score?: number
  t1?: number
  t2?: number
  j3?: number
  shape_chart: CalculationChart
}

function ViewChoice({ staged, onChange }: { staged: boolean; onChange: (value: boolean) => void }) {
  return <div className="flex gap-1 rounded-lg bg-slate-100 p-1">
    {[false, true].map(value => <button key={String(value)} type="button" aria-pressed={staged === value}
      onClick={() => onChange(value)} className={`rounded-md px-3 py-1.5 text-base ${staged === value ? 'bg-white font-medium text-slate-800 shadow-sm' : 'text-slate-500'}`}>
      {value ? '分步阅读' : '总览'}
    </button>)}
  </div>
}

function Value({ label, value }: { label: string; value: unknown }) {
  return <div className="flex items-baseline gap-1.5"><dt className="text-slate-500">{label}</dt><dd className="font-medium tabular-nums text-slate-800">{number(value)}</dd></div>
}

function ModifiedLikelihood({ trace }: { trace: CalculationTrace }) {
  const details = trace.details as { profile_frames?: CalculationPoint[]; deleted_value?: number; deleted_observations?: number
    shape_iterations?: { iteration: number; shape_before: number; shape_after: number; log_sum: number; weighted_log_mean: number; numerator: number; denominator: number }[] } | undefined
  const scale = readPowerScaleCalculation(trace)
  const frames = details?.profile_frames ?? []
  const [index, setIndex] = useState(Math.max(0, frames.length - 1))
  const frame = frames[Math.min(index, frames.length - 1)]
  const iteration = details?.shape_iterations?.find(step => step.iteration === frame?.iteration)
  const [staged, setStaged] = useState(false)
  const [stage, setStage] = useState(0)
  const names = ['形状为什么取这个值', '迭代怎样接近峰值', '何时结束迭代']
  const charts = trace.charts.map(chart => chart.id === 'modified-profile-likelihood' && frame ? {
    ...chart,
    selected: [{ ...frame, label: Number(frame.iteration) === Number(trace.selection.iterations) ? '最终形状参数' : `第 ${frame.iteration} 次迭代` }],
    references: Number(frame.iteration) === Number(trace.selection.iterations) ? []
      : [{ axis: 'x' as const, value: Number(trace.selection.beta), label: '最终形状' }],
  } : chart)
  return <div className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-base leading-relaxed text-slate-700">先取最小观测确定位置并删除该点，再寻找保留样本修改似然的峰值。</p>
      <ViewChoice staged={staged} onChange={setStaged} />
    </div>
    {scale && <section aria-label="最小观测定位与样本平移" className="rounded-xl border border-slate-200 px-4 py-4">
      <h3 className="text-lg font-semibold text-slate-800">从原样本确定位置，形成迭代用的样本</h3>
      <div className="mt-3 grid gap-3 text-base sm:grid-cols-3">
        <p className="rounded-lg bg-slate-50 p-3">① 取原样本最小值<br /><strong>γ̂ = {number(scale.gamma)}</strong></p>
        <p className="rounded-lg bg-slate-50 p-3">② 删去该一个观测<br /><strong>q = n − 1 = {scale.count}</strong></p>
        <p className="rounded-lg bg-slate-50 p-3">③ 保留观测减去 γ̂<br /><strong>yᵢ = t₍ᵢ₎ − γ̂，i = 2,…,n</strong></p>
      </div>
      <div className="mt-3 max-h-48 overflow-auto"><table className="w-full text-right text-sm tabular-nums"><thead><tr>{['原样本序号', '保留观测 t₍ᵢ₎', '平移后 yᵢ'].map(label => <th key={label} className="whitespace-nowrap px-3 py-2 font-medium">{label}</th>)}</tr></thead><tbody>{scale.samples.map(point => <tr key={point.index}>{[point.index, point.observation, point.distance].map((value, i) => <td key={i} className="whitespace-nowrap px-3 py-1">{number(value)}</td>)}</tr>)}</tbody></table></div>
    </section>}
    <div className="rounded-xl bg-slate-100/70 px-4 py-3">
      <dl className="flex flex-wrap gap-x-6 gap-y-2 text-base"><Value label="位置 γ̂ = 最小观测 =" value={trace.selection.gamma} /><Value label="保留样本数 =" value={((trace.recovery?.[0]?.values ?? []).find(item => item.label === '保留样本数 q'))?.value} /></dl>
      {frames.length > 1 && <div className="mt-4 grid items-center gap-3 sm:grid-cols-[auto_minmax(100px,1fr)_auto]">
        <label htmlFor="mmle-iteration" className="text-base text-slate-600">查看实际迭代</label>
        <input id="mmle-iteration" aria-label="查看MMLE实际迭代" type="range" min={0} max={frames.length - 1} step={1} value={Math.min(index, frames.length - 1)} onChange={event => setIndex(Number(event.target.value))} className="w-full accent-emerald-700" />
        <button type="button" onClick={() => setIndex(frames.length - 1)} className="rounded-lg px-3 py-1.5 text-base text-emerald-700 hover:bg-white">回到最终估计</button>
      </div>}
      {frame && <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-base"><Value label="迭代次数 =" value={frame.iteration} /><Value label="β =" value={frame.x} /><Value label="ℓₚ =" value={frame.y} /><Value label="该形状对应 η =" value={frame.eta} /></dl>}
      {iteration && scale && <div className="mt-4 min-w-0 rounded-lg bg-white px-3 py-3" aria-label="本次形状迭代的数值代入">
        <p className="text-base text-slate-700">第 {iteration.iteration} 次迭代：Σ ln yᵢ = {number(iteration.log_sum)}，Σ wᵢ ln yᵢ = {number(iteration.weighted_log_mean)}。</p>
        <ProcessFormula expression={String.raw`\begin{aligned}w_i(\beta_k)&=\frac{y_i^{\beta_k}}{\sum_j y_j^{\beta_k}}\\\beta_{k+1}&=\frac{q+\beta_k\sum\ln y_i}{q\sum w_i(\beta_k)\ln y_i}\\&\approx\frac{${scale.count}+${math(iteration.shape_before)}\times${math(iteration.log_sum)}}{${scale.count}\times${math(iteration.weighted_log_mean)}}\\&\approx\frac{${math(iteration.numerator)}}{${math(iteration.denominator)}}\approx${math(iteration.shape_after)}\end{aligned}`} />
      </div>}
    </div>
    {staged && <div className="flex flex-wrap gap-2">{names.slice(0, charts.length).map((name, i) => <button key={name} type="button" aria-pressed={stage === i} onClick={() => setStage(i)} className={`rounded-lg border px-3 py-2 text-base ${stage === i ? 'border-emerald-600 bg-emerald-50 text-emerald-800' : 'border-slate-200 text-slate-600'}`}>{i + 1}　{name}</button>)}</div>}
    <div className="grid min-w-0 grid-cols-1 items-start gap-4 xl:grid-cols-2">{charts.map((chart, i) => (!staged || stage === i) && <div key={chart.id} className={i === 0 ? 'xl:col-span-2' : ''}><ProcessChart chart={chart} /></div>)}</div>
  </div>
}

function ConditionalLikelihood({ trace }: { trace: CalculationTrace }) {
  const details = trace.details as { reading_frames?: ReadingFrame[]; weight_values?: { n: number; j1: number; j2: number; j3: number; shape: number; j3_clamped: boolean } } | undefined
  const equation = (trace.details as { equation_calculation?: { mean_log: number; log_sum: number; weighted_log_mean: number; inverse_mean: number; power_ratio: number; shape_weight: number; standardized_power_sum: number } } | undefined)?.equation_calculation
  const frames = details?.reading_frames ?? []
  const finalIndex = Math.max(0, frames.findIndex(frame => frame.final))
  const [index, setIndex] = useState(finalIndex)
  const [staged, setStaged] = useState(false)
  const [stage, setStage] = useState(0)
  const frame = frames[Math.min(index, frames.length - 1)]
  const weighted = trace.method === 'wmle'
  const weights = details?.weight_values
  const shapeScore = weighted ? trace.selection.t1 : frames.find(item => item.final)?.shape_chart.selected?.[0]?.y
  const main = trace.charts.filter(chart => chart.id !== 'candidate-residuals' && chart.id !== 'conditional-shape-equation')
  const shape = frame?.shape_chart ?? trace.charts.find(chart => chart.id === 'conditional-shape-equation')
  const charts = [...main.map(chart => {
    const value = frame && (chart.id === 'profile-likelihood' ? frame.log_likelihood : chart.id === 'location-score' ? frame.location_score : frame.t2)
    return typeof value === 'number' && frame ? { ...chart, selected: [{ x: frame.gamma, y: value, label: frame.final ? '最终选择' : '当前查看位置' }] } : chart
  }), ...(shape ? [shape] : [])]
  const names = weighted ? ['位置与形状共同确定', '在该位置求形状'] : ['比较位置的似然', '峰值判据', '在该位置求形状']
  return <div className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="max-w-4xl text-base leading-relaxed text-slate-700">{weighted ? '两个加权方程共同确定形状和位置：每换一个位置，先求 T₁ = 0 对应的形状，再看 T₂ 是否也为零。' : '每换一个位置，都求出相应的形状和尺度；比较这些位置的似然，确定最终三参数。'}</p>
      <ViewChoice staged={staged} onChange={setStaged} />
    </div>
    {weighted && weights && <section aria-label="加权方程的权重来源" className="rounded-xl border border-slate-200 px-4 py-4">
      <h3 className="text-lg font-semibold text-slate-800">本次权重怎样取值</h3>
      <p className="mt-2 text-base text-slate-700">J₁、J₂按样本量 n = {weights.n} 读取作者配套表；J₃还随候选形状变化，按 n、β 查表并插值。下面列出最终 β̂ = {number(weights.shape)} 所用的值。</p>
      <div className="mt-3 grid gap-3 text-base sm:grid-cols-3">
        <p className="rounded-lg bg-slate-50 p-3"><strong>J₁ = {number(weights.j1)}</strong><span className="mt-1 block text-slate-600">用于尺度：幂次总和除以 nJ₁</span></p>
        <p className="rounded-lg bg-slate-50 p-3"><strong>J₂ = {number(weights.j2)}</strong><span className="mt-1 block text-slate-600">用于形状方程 T₁ 中的 J₂/β</span></p>
        <p className="rounded-lg bg-slate-50 p-3"><strong>J₃ = {number(weights.j3)}</strong><span className="mt-1 block text-slate-600">用于位置方程 T₂ 中的校准项</span></p>
      </div>
      {weights.j3_clamped && <p className="mt-2 text-base text-amber-800">本次形状超出 J₃ 表的 0.1–5 区间，现行实现使用该区间的端值。</p>}
    </section>}
    {frame && <section className="rounded-xl bg-slate-100/70 px-4 py-3" aria-label="位置与形状联动">
      <div className="grid items-center gap-3 sm:grid-cols-[auto_minmax(100px,1fr)_auto]">
        <label htmlFor={`${trace.method}-location`} className="text-base text-slate-600">查看位置 γ</label>
        <input id={`${trace.method}-location`} aria-label={`查看${trace.method.toUpperCase()}位置与对应形状`} type="range" min={0} max={frames.length - 1} step={1} value={Math.min(index, frames.length - 1)} onChange={event => setIndex(Number(event.target.value))} className="w-full accent-emerald-700" />
        <button type="button" onClick={() => setIndex(finalIndex)} className="rounded-lg px-3 py-1.5 text-base text-emerald-700 hover:bg-white">回到最终估计</button>
      </div>
      <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-base"><Value label="γ =" value={frame.gamma} /><Value label="对应 β =" value={frame.beta} /><Value label="对应 η =" value={frame.eta} />
        {weighted ? <><Value label="T₁ =" value={frame.t1} /><Value label="T₂ =" value={frame.t2} /><Value label="该形状的 J₃ =" value={frame.j3} /></> : <Value label="对应 ℓₚ =" value={frame.log_likelihood} />}
      </dl>
      {weighted && <ProcessFormula expression="T_1(\beta,\gamma)=0\quad\longrightarrow\quad\beta^*(\gamma),\qquad T_2\{\beta^*(\gamma),\gamma\}=0" />}
    </section>}
    {staged && <div className="flex flex-wrap gap-2">{names.slice(0, charts.length).map((name, i) => <button key={name} type="button" aria-pressed={stage === i} onClick={() => setStage(i)} className={`rounded-lg border px-3 py-2 text-base ${stage === i ? 'border-emerald-600 bg-emerald-50 text-emerald-800' : 'border-slate-200 text-slate-600'}`}>{i + 1}　{name}</button>)}</div>}
    <div className="grid min-w-0 grid-cols-1 items-start gap-4 xl:grid-cols-2">{charts.map((chart, i) => (!staged || stage === i) && <div key={chart.id} className={!weighted && i === 2 ? 'xl:col-span-2' : ''}><ProcessChart key={`${chart.id}-${frame?.gamma ?? ''}`} chart={chart} /></div>)}</div>
    {equation && <section aria-label="最终参数的方程代入" className="min-w-0 rounded-xl border border-slate-200 px-4 py-4">
      <h3 className="text-lg font-semibold text-slate-800">最终参数怎样代入这些判据</h3>
      <p className="mt-2 text-base text-slate-700">固定最终 γ̂ = {number(trace.selection.gamma)}，由样本距离 dᵢ = tᵢ − γ̂ 得到以下汇总量，代入最终 β̂ = {number(trace.selection.beta)}。</p>
      <div className="mt-3 grid min-w-0 gap-3 lg:grid-cols-2"><div className="min-w-0 rounded-lg bg-slate-50 p-3">
        <ProcessFormula expression={String.raw`\overline{\ln d}=\frac1n\sum\ln d_i,\quad L_\beta=\frac{\sum d_i^\beta\ln d_i}{\sum d_i^\beta}`} />
        <ProcessFormula expression={String.raw`${weighted ? 'T_1' : String.raw`S_\beta`}=\frac{${math(equation.shape_weight)}}{${math(trace.selection.beta)}}+${math(equation.mean_log)}-${math(equation.weighted_log_mean)}` + (typeof shapeScore === 'number' ? String.raw`\approx${math(shapeScore)}` : '')} />
        <p className="text-base text-slate-700">{weighted ? `与位置方程共同检查，最终 T₁ = ${number(trace.selection.t1)}。` : '形状曲线展示该式随 β 的变化；内点取零点，β = 1 下界按约束采纳。'}</p>
      </div><div className="min-w-0 rounded-lg bg-amber-50/60 p-3">{weighted ? <>
        <ProcessFormula expression={String.raw`T_2=\overline{1/d}\,\frac{\sum d_i^\beta}{\sum d_i^{\beta-1}}-J_3`} />
        <ProcessFormula expression={String.raw`T_2\approx${math(equation.inverse_mean)}\times${math(equation.power_ratio)}-${math(weights?.j3)}\approx${math(trace.selection.t2)}`} />
      </> : <><ProcessFormula expression={String.raw`\ell=n\ln\beta-n\beta\ln\eta+(\beta-1)\sum\ln d_i-\sum(d_i/\eta)^\beta`} /><p className="text-base leading-relaxed text-slate-700">Σ ln dᵢ = {number(equation.log_sum)}，Σ(dᵢ/η̂)^β̂ = {number(equation.standardized_power_sum)}。代入最终 β̂、η̂ 与样本量，得到 ℓ = <strong>{number(trace.selection.log_likelihood)}</strong>；比较有限极大候选的似然，采纳最大者。</p></>}</div></div>
    </section>}
  </div>
}

export function LikelihoodProcessViewer({ trace }: { trace: CalculationTrace }) {
  const key = `${trace.method}-${trace.selection.beta}-${trace.selection.eta}-${trace.selection.gamma}`
  return trace.method === 'mmle' ? <ModifiedLikelihood key={key} trace={trace} /> : <ConditionalLikelihood key={key} trace={trace} />
}
