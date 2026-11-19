"use client"

import type { FlowChartTarget } from '@/lib/method-flow'
import { recordedDetails, readModifiedProcess, readWeightedProcess } from './recorded-process-data'
import styles from './CalculationWorkspace.module.css'
import { ProcessDetails } from './ProcessDetails'
import { ProcessValueTable } from '@/components/shared/charts/ProcessValueTable'
import { ProcessEquation } from '@/components/shared/charts/ProcessEquation'
import { MathText } from '@/components/shared/MathText'
import { ProcessChart, ProcessFormula } from '@/components/shared/charts/CalculationProcessChart'
import { type CalculationTrace, readPowerScaleCalculation, formatCalculationNumber as number } from '@/lib/calculation-trace'

const math = (value: unknown) => number(value).replace(/e([+-]?\d+)/, String.raw`\times10^{$1}`)

function Value({ label, value }: { label: string; value: unknown }) {
  return <div className="flex items-baseline gap-1.5"><dt className="text-slate-500">{label}</dt><dd className="font-medium tabular-nums text-slate-800">{number(value)}</dd></div>
}

export function ModifiedLikelihoodSample({ trace }: { trace: CalculationTrace }) {
  const scale = readPowerScaleCalculation(trace)
  if (!scale) return null
  return <section aria-label="最小观测定位与样本平移" className="min-w-0 space-y-4">
    <ProcessEquation expression={String.raw`\hat\gamma=t_{(1)}=${math(scale.gamma)},\quad q=n-1=${scale.count}`} />
    <ProcessValueTable label="保留样本与平移距离" minColumnWidth={360}
      columns={[
        { label: '保留样本序号', math: 'i' },
        { label: '保留观测', math: 't_{(i+1)}', align: 'right' },
        { label: '平移距离', math: 'y_i', align: 'right' },
      ]}
      rows={scale.samples.map(point => [point.index - 1, number(point.observation), number(point.distance)])} />
  </section>
}

function ModifiedLikelihood({ trace, index: requested, onIndexChange }: ReaderProps) {
  const scale = readPowerScaleCalculation(trace)
  const { frames, frame, iteration, index } = readModifiedProcess(trace, requested)
  const setIndex = onIndexChange
  const charts = trace.charts.map(chart => chart.id === 'modified-profile-likelihood' && frame ? {
    ...chart,
    selected: [{ ...frame, label: Number(frame.iteration) === Number(trace.selection.iterations) ? '最终形状参数' : `第 ${frame.iteration} 次迭代` }],
    references: Number(frame.iteration) === Number(trace.selection.iterations) ? []
      : [{ axis: 'x' as const, value: Number(trace.selection.beta), label: '最终形状' }],
  } : chart)
  return <div className="space-y-4">
    <div className="rounded-xl bg-slate-100/70 px-4 py-3">
      <dl className="flex flex-wrap gap-x-6 gap-y-2 text-base"><Value label="γ̂ =" value={trace.selection.gamma} /><Value label="q =" value={((trace.recovery?.[0]?.values ?? []).find(item => item.label === '保留样本数 q'))?.value} /></dl>
      {frames.length > 1 && <div className="mt-4 grid items-center gap-3 sm:grid-cols-[auto_minmax(100px,1fr)_auto]">
        <label htmlFor="mmle-iteration" className="text-base text-slate-600">查看实际迭代</label>
        <input id="mmle-iteration" aria-label="查看MMLE实际迭代" type="range" min={0} max={frames.length - 1} step={1} value={Math.min(index, frames.length - 1)} onChange={event => setIndex(Number(event.target.value))} className="w-full accent-emerald-700" />
        <button type="button" onClick={() => setIndex(frames.length - 1)} className="rounded-lg px-3 py-1.5 text-base text-emerald-700 hover:bg-white">回到最终估计</button>
      </div>}
      {frame && <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-base"><Value label="迭代次数 =" value={frame.iteration} /><Value label="β =" value={frame.x} /><Value label="ℓₚ =" value={frame.y} /><Value label="η(β) =" value={frame.eta} /></dl>}
      {iteration && scale && <ProcessDetails title="本次形状迭代的数值代入"><div className="min-w-0 space-y-3" aria-label="本次形状迭代的数值代入">
        <p className="text-base text-slate-700">第 {iteration.iteration} 次迭代：Σ ln yᵢ = {number(iteration.log_sum)}，Σ wᵢ ln yᵢ = {number(iteration.weighted_log_mean)}。</p>
        <ProcessFormula expression={String.raw`\begin{aligned}w_i(\beta_k)&=\frac{y_i^{\beta_k}}{\sum_j y_j^{\beta_k}}\\\beta_{k+1}&=\frac{q+\beta_k\sum\ln y_i}{q\sum w_i(\beta_k)\ln y_i}\\&\approx\frac{${scale.count}+${math(iteration.shape_before)}\times${math(iteration.log_sum)}}{${scale.count}\times${math(iteration.weighted_log_mean)}}\\&\approx\frac{${math(iteration.numerator)}}{${math(iteration.denominator)}}\approx${math(iteration.shape_after)}\end{aligned}`} />
      </div></ProcessDetails>}
    </div>
    <div className={styles.figureGrid}>{charts.map((chart, i) => <div key={chart.id} className={i === 0 ? styles.fullFigure : undefined}><div className="mb-3 flex flex-wrap items-baseline gap-x-2 text-base text-slate-700"><span>{chart.id === 'modified-profile-likelihood' ? '修改剖面似然' : chart.id === 'shape-fixed-point' ? '形状迭代' : '迭代步长'}</span><MathText math={chart.id === 'modified-profile-likelihood' ? String.raw`\ell_p(\beta)` : chart.id === 'shape-fixed-point' ? String.raw`\beta_k` : String.raw`|\Delta\beta_k|`} /></div><ProcessChart chart={chart} figureOnly workspacePlot showYAxisLabel initiallyFocused={false} /></div>)}</div>
  </div>
}

interface ReaderProps { trace: CalculationTrace; target?: FlowChartTarget; index?: number | null; onIndexChange: (index: number) => void }

export function WeightedLikelihoodWeights({ trace }: { trace: CalculationTrace }) {
  const weights = recordedDetails(trace).weight_values
  return weights && <section aria-label="加权方程的权重来源" className="space-y-3">
    <p className="text-sm leading-relaxed text-slate-600">J₁、J₂由样本量 n = {weights.n} 查表；J₃还随候选形状变化。下列为最终 β̂ = {number(weights.shape)} 对应的权重。</p>
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 tabular-nums">
      <dt><MathText math="J_1(n)" /></dt><dd>{number(weights.j1)}</dd>
      <dt><MathText math="J_2(n)" /></dt><dd>{number(weights.j2)}</dd>
      <dt><MathText math={String.raw`J_3(n,\hat\beta)`} /></dt><dd>{number(weights.j3)}</dd>
    </dl>
    {weights.j3_clamped && <p className="text-sm text-amber-800">β̂ 超出 J₃ 表的 0.1–5 区间，本次取该区间端值。</p>}
  </section>
}

function WeightedLikelihoodEquations({ trace }: { trace: CalculationTrace }) {
  const { equation_calculation: equation, weight_values: weights } = recordedDetails(trace)
  const shapeScore = trace.selection.t1
  return <>{equation && <section aria-label="最终参数的方程代入" className="min-w-0 rounded-xl border border-slate-200 px-4 py-4">
      <h3 className="text-lg font-semibold text-slate-800">最终参数怎样代入这些判据</h3>
      <p className="mt-2 text-base text-slate-700">固定最终 γ̂ = {number(trace.selection.gamma)}，由样本距离 dᵢ = tᵢ − γ̂ 得到以下汇总量，代入最终 β̂ = {number(trace.selection.beta)}。</p>
      <div className="mt-3 grid min-w-0 gap-3 lg:grid-cols-2"><div className="min-w-0 rounded-lg bg-slate-50 p-3">
        <ProcessFormula expression={String.raw`\overline{\ln d}=\frac1n\sum\ln d_i,\quad L_\beta=\frac{\sum d_i^\beta\ln d_i}{\sum d_i^\beta}`} />
        <ProcessFormula expression={String.raw`T_1=\frac{${math(equation.shape_weight)}}{${math(trace.selection.beta)}}+${math(equation.mean_log)}-${math(equation.weighted_log_mean)}` + (typeof shapeScore === 'number' ? String.raw`\approx${math(shapeScore)}` : '')} />
        <p className="text-base text-slate-700">与位置方程共同检查，最终 T₁ = {number(trace.selection.t1)}。</p>
      </div><div className="min-w-0 rounded-lg bg-amber-50/60 p-3">
        <ProcessFormula expression={String.raw`T_2=\overline{1/d}\,\frac{\sum d_i^\beta}{\sum d_i^{\beta-1}}-J_3`} />
        <ProcessFormula expression={String.raw`T_2\approx${math(equation.inverse_mean)}\times${math(equation.power_ratio)}-${math(weights?.j3)}\approx${math(trace.selection.t2)}`} />
      </div></div>
    </section>}</>
}

function WeightedLikelihood({ trace, target, index: requested, onIndexChange }: ReaderProps) {
  const { frames, frame, finalIndex, index } = readWeightedProcess(trace, requested)
  const setIndex = onIndexChange
  const main = trace.charts.filter(chart => chart.id === 'weighted-location-equation')
  const shape = frame?.shape_chart ?? trace.charts.find(chart => chart.id === 'conditional-shape-equation')
  const charts = target === 'trial' ? shape ? [shape] : [] : main.map(chart => {
    const value = frame?.t2
    return typeof value === 'number' && frame ? { ...chart, selected: [
      ...(chart.selected ?? []), ...(!frame.final ? [{ x: frame.gamma, y: value, label: '当前试算' }] : []),
    ] } : chart
  })
  if (target === 'comparison') return <WeightedLikelihoodEquations trace={trace} />
  if (target === 'trial' && !shape) return <p role="status" className="text-slate-600">{trace.selection.approximate === true
    ? '本次按边界残差容差接受候选，没有可显示的条件形状求根记录；不将该候选标为形状方程零点。'
    : '这份记录缺少条件形状求值，请重新计算后查看。'}</p>
  return <div className="space-y-4">
    {frame && <section className="rounded-xl bg-slate-100/70 px-4 py-3" aria-label="位置与形状联动">
      {target === 'trial' && <div className="grid items-center gap-3 sm:grid-cols-[auto_minmax(100px,1fr)_auto]">
        <label htmlFor={`${trace.method}-location`} className="text-base text-slate-600">查看位置 γ</label>
        <input id={`${trace.method}-location`} aria-label={`查看${trace.method.toUpperCase()}位置与对应形状`} type="range" min={0} max={frames.length - 1} step={1} value={Math.min(index, frames.length - 1)} onChange={event => setIndex(Number(event.target.value))} className="w-full accent-emerald-700" />
        <button type="button" onClick={() => setIndex(finalIndex)} className="rounded-lg px-3 py-1.5 text-base text-emerald-700 hover:bg-white">回到最终估计</button>
      </div>}
      <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-base"><Value label="γ =" value={frame.gamma} /><Value label="对应 β =" value={frame.beta} />{target === 'location' && <Value label="条件尺度 η*(γ) =" value={frame.eta} />}
        {target === 'trial' ? <Value label="T₁ =" value={frame.t1} /> : <><Value label="T₂ =" value={frame.t2} /><Value label="该形状的 J₃ =" value={frame.j3} /></>}
      </dl>
      <ProcessFormula expression={String.raw`T_1(\beta,\gamma)=0\quad\longrightarrow\quad\beta^*(\gamma),\qquad T_2\{\beta^*(\gamma),\gamma\}=0`} />
    </section>}
    <div className={styles.figureGrid}>{charts.map(chart => <div key={chart.id}><ProcessChart key={`${chart.id}-${frame?.gamma ?? ''}`} chart={chart} figureOnly batchCharts={target === 'trial' && !frame?.final ? [] : undefined} workspacePlot showYAxisLabel initiallyFocused={false} /></div>)}</div>

  </div>
}

export function LikelihoodProcessViewer(props: ReaderProps) {
  return props.trace.method === 'mmle' ? <ModifiedLikelihood {...props} /> : <WeightedLikelihood {...props} />
}
