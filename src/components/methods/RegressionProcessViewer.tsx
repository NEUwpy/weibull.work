"use client"

import { useId, useState } from 'react'
import { ProcessValueTable } from '@/components/shared/charts/ProcessValueTable'
import { readRegressionProcess, type RegressionView } from './recorded-process-data'
import styles from './CalculationWorkspace.module.css'
import { ProcessEquation } from '@/components/shared/charts/ProcessEquation'
const math = (value: unknown) => number(value).replace(/e([+-]?\d+)/, String.raw`\times10^{$1}`)
import { ProcessChart, ProcessFormula } from '@/components/shared/charts/CalculationProcessChart'
import { type CalculationChart, type CalculationTrace, formatCalculationNumber as number } from '@/lib/calculation-trace'

function regressionChart(view: RegressionView, lse: boolean, original = false, sampleIndex = 0): CalculationChart {
  const current = view.points[Math.min(sampleIndex, view.points.length - 1)]
  return {
    id: original ? 'original-probability-plot' : lse ? 'white-regression' : 'park-probability-regression',
    title: original ? '原样本概率图（γ = 0）' : lse ? 'White 回归' : '平移后的概率图',
    x: { key: 'x', label: lse ? 'White 顺序统计量期望 E[W₍ᵢ:ₙ₎]' : original ? 'ln(tᵢ)' : 'ln(tᵢ − γ)' },
    y: { key: 'y', label: lse ? 'ln(tᵢ − γ)' : 'Weibull 分数 ln[−ln(1−pᵢ)]' },
    series: [
      { id: 'sample', label: '样本变换点', kind: 'scatter', role: 'diagnostic', points: view.points.map(point => ({ x: point.x, y: point.y })) },
      { id: 'fit', label: '该位置的回归直线', kind: 'line', role: 'diagnostic', points: view.points.map(point => ({ x: point.x, y: point.fit })) },
      { id: 'current', label: `当前样本 ${Math.min(sampleIndex + 1, view.points.length)}`, kind: 'scatter', role: 'diagnostic', points: current ? [{ x: current.x, y: current.y }] : [] },
    ],
    formula: lse ? String.raw`Y=a+bX,\quad\beta=1/b,\quad\eta=e^a` : String.raw`Y=a+b\ln(t-\gamma),\quad\beta=b,\quad\eta=e^{-a/b}`,
  }
}

export function RegressionProcessViewer({ trace, mode, viewIndex, onViewIndexChange }: {
  trace: CalculationTrace; mode: 'transformation' | 'location' | 'regression'
  viewIndex?: number | null; onViewIndexChange?: (index: number) => void
}) {
  const id = useId()
  const process = readRegressionProcess(trace, viewIndex)
  const { views, finalIndex, original } = process
  const [sampleIndex, setSampleIndex] = useState(0)
  const index = mode === 'location' ? process.index : finalIndex
  const view = views[index]
  const setViewIndex = (value: number) => onViewIndexChange?.(value)
  const sample = view?.points[Math.min(sampleIndex, view.points.length - 1)]
  const sums = view?.calculation
  const lse = trace.method === 'lse'
  const criterion = trace.charts[0]
  if (!view || !criterion || finalIndex < 0) return <p role="status" className="text-slate-600">这份记录缺少本步的回归明细，请重新计算后查看。</p>
  const locationChart: CalculationChart = {
    ...criterion,
    title: lse ? '位置判据：F(γ)' : '位置判据：ρ(γ)',
    selected: [
      ...(criterion.selected ?? []).map(point => ({ ...point, label: '最终位置' })),
      ...(!view.selected ? [{ x: view.gamma, y: view.criterion, label: '正在查看' }] : []),
    ],
  }

  if (mode === 'transformation') return <div className="space-y-4">
    <ProcessValueTable label={lse ? '样本与 White 顺序统计量期望' : '样本到 Park 绘图位置和概率分数'} minColumnWidth={440}
      columns={(lse ? ['序号', '排序样本', '顺序统计量期望'] : ['序号', '排序样本', '绘图位置', 'Weibull 分数']).map((label, i) => ({ label, math: (lse ? ['i', 't_{(i)}', 'X_i'] : ['i', 't_{(i)}', 'p_i', 'Y_i'])[i], align: 'right' }))}
      rows={view.points.map((p, i) => lse ? [i+1, number(p.observation), number(p.x)] : [i+1, number(p.observation), number(p.probability), number(p.y)])} />
  </div>

  return <div className="min-w-0 space-y-4" data-regression-process={trace.method}>
    {mode === 'location' && <div className="rounded-xl border border-slate-200 bg-white/70 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <label htmlFor={`${id}-location`} className="text-base font-medium text-slate-800">查看位置 γ = {number(view.gamma)}</label>
        <button type="button" onClick={() => setViewIndex(finalIndex)} className="rounded-lg bg-amber-50 px-3 py-2 text-base text-amber-900">回到最终位置</button>
      </div>
      <input id={`${id}-location`} aria-label="切换位置并联动回归图" type="range" min={0} max={views.length - 1} step={1} value={index}
        onChange={event => setViewIndex(Number(event.target.value))} className="mt-4 w-full accent-emerald-700" />
      <div className="mt-1 flex flex-wrap justify-between gap-2 text-sm text-slate-500"><span>γ = {number(views[0].gamma)}</span><span>{view.selected ? '当前为最终采纳的位置' : '比较用位置；最终估计保持不变'}</span><span>γ = {number(views[views.length - 1].gamma)}</span></div>
    </div>}
    {mode === 'regression' ? <div className="space-y-3"><ProcessChart chart={regressionChart(view, lse, false, sampleIndex)} figureOnly workspacePlot showYAxisLabel initiallyFocused={false} /></div> : lse ? <div className={styles.figureGrid}>
      <ProcessChart chart={locationChart} initiallyFocused={false} workspacePlot showYAxisLabel /><ProcessChart chart={regressionChart(view, true, false, sampleIndex)} batchCharts={!view.selected ? [] : undefined} workspacePlot showYAxisLabel initiallyFocused={false} />
    </div> : <>
      <ProcessChart chart={locationChart} initiallyFocused={false} workspacePlot showYAxisLabel />
      <div className={styles.figureGrid}>{original && <ProcessChart chart={regressionChart(original, false, true, sampleIndex)} workspacePlot showYAxisLabel initiallyFocused={false} />}<ProcessChart chart={regressionChart(view, false, false, sampleIndex)} batchCharts={!view.selected ? [] : undefined} workspacePlot showYAxisLabel initiallyFocused={false} /></div>
    </>}
    {sample && sums && <section aria-label="样本变换与回归计算" className="min-w-0 space-y-3 rounded-xl border border-slate-200 px-4 py-4">
      <h3 className="text-lg font-semibold text-slate-800">{mode === 'location' ? '样本变换怎样形成位置判据' : '从样本变换点求回归系数'}</h3>
      <label htmlFor={`${id}-sample`} className="block text-base font-medium text-slate-800">查看第 {Math.min(sampleIndex + 1, view.points.length)} 个样本形成的点</label>
      {view.distance_precision_note && <p className="text-base text-amber-800">这个位置非常接近最小观测，显示的 γ 经过舍入；下面的距离保留计算时的精度。</p>}
      <input id={`${id}-sample`} aria-label="查看样本到回归点的计算" type="range" min={0} max={view.points.length - 1} value={Math.min(sampleIndex, view.points.length - 1)} onChange={event => setSampleIndex(Number(event.target.value))} className="w-full accent-blue-600" />
      <p className="rounded-lg bg-blue-50/60 px-4 py-3 text-base leading-relaxed text-slate-700">t₍ᵢ₎ = {number(sample.observation)}，t₍ᵢ₎ − γ = {number(sample.distance)}{lse ? `；Xᵢ = ${number(sample.x)}，Yᵢ = ln(${number(sample.distance)}) = ${number(sample.y)}` : `；pᵢ = ${number(sample.probability)}，Xᵢ = ln(${number(sample.distance)}) = ${number(sample.x)}，Yᵢ = ${number(sample.y)}`}。</p>
      <div className="grid min-w-0 gap-3 lg:grid-cols-2">
        {mode === 'regression' && <div className="min-w-0 rounded-lg bg-slate-50 px-4 py-3"><h4 className="text-base font-semibold text-slate-800">最小二乘得到斜率与截距</h4><ProcessFormula expression={String.raw`S_{XX}=\sum(X_i-\bar X)^2,\quad S_{XY}=\sum(X_i-\bar X)(Y_i-\bar Y)`} /><ProcessFormula expression={String.raw`b=S_{XY}/S_{XX},\quad a=\bar Y-b\bar X`} /><p className="text-base leading-relaxed">b = {number(sums.sxy)} ÷ {number(sums.sxx)} = <strong>{number(view.slope)}</strong><br />a = {number(sums.y_mean)} − {number(view.slope)} × {number(sums.x_mean)} = <strong>{number(view.intercept)}</strong></p></div>}
        {mode === 'location' && <div className="min-w-0 rounded-lg bg-amber-50/60 px-4 py-3"><h4 className="text-base font-semibold text-slate-800">由同一组点计算位置判据</h4>{lse ? <><ProcessFormula expression={String.raw`F=\frac{\sum(Y_i-\bar Y)^2/(n-1)}{\sum(Y_i-a-bX_i)^2/(n-2)}`} /><p className="text-base leading-relaxed">F = [{number(sums.syy)} / {sums.count - 1}] ÷ [{number(sums.residual_sum)} / {sums.count - 2}] = <strong>{number(view.criterion)}</strong></p></> : <><ProcessFormula expression={String.raw`\rho=S_{XY}/\sqrt{S_{XX}S_{YY}},\quad S_{YY}=\sum(Y_i-\bar Y)^2`} /><p className="text-base leading-relaxed">ρ = {number(sums.sxy)} ÷ √({number(sums.sxx)} × {number(sums.syy)}) = <strong>{number(view.criterion)}</strong></p></>}</div>}
      </div>
    </section>}
    {mode === 'regression' && <div className="space-y-3" aria-label="回归系数恢复参数">
      <ProcessEquation expression={lse ? String.raw`\hat\beta=1/${math(view.slope)}\approx${math(view.beta)}` : String.raw`\hat\beta=b\approx${math(view.beta)}`} />
      <ProcessEquation expression={lse ? String.raw`\hat\eta=e^{${math(view.intercept)}}\approx${math(view.eta)}` : String.raw`\hat\eta=e^{-(${math(view.intercept)})/${math(view.slope)}}\approx${math(view.eta)}`} />
    </div>}
    {mode === 'location' && <details className="rounded-xl border border-slate-200 px-4 py-3">
      <summary className="cursor-pointer text-base font-medium text-slate-700">比较不同位置的数值</summary>
      <div className="mt-3 overflow-x-auto"><table className="w-full text-right text-base tabular-nums"><thead><tr className="text-slate-500">{['γ', lse ? 'F' : 'ρ', 'β', 'η', ''].map((label, i) => <th key={i} className="whitespace-nowrap px-3 py-2 font-medium">{label}</th>)}</tr></thead>
        <tbody>{views.map((candidate, i) => <tr key={i} className={i === index ? 'bg-emerald-50 text-emerald-900' : 'text-slate-700'}>
          {[candidate.gamma, candidate.criterion, candidate.beta, candidate.eta].map((value, j) => <td key={j} className="whitespace-nowrap px-3 py-2">{number(value)}</td>)}
          <td className="whitespace-nowrap px-3 py-2"><button type="button" onClick={() => setViewIndex(i)} aria-pressed={i === index} className="rounded px-2 py-1 text-emerald-800 hover:bg-emerald-100">{candidate.selected ? '最终位置' : '查看图'}</button></td>
        </tr>)}</tbody></table></div>
    </details>}
  </div>
}
