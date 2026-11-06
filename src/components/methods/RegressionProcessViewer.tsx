"use client"

import { useState } from 'react'
import { ProcessChart, ProcessFormula } from '@/components/shared/charts/CalculationProcessChart'
import { type CalculationChart, type CalculationTrace, formatCalculationNumber as number } from '@/lib/calculation-trace'

interface RegressionView {
  gamma: number
  criterion: number
  slope: number
  intercept: number
  beta: number
  eta: number
  selected: boolean
  distance_precision_note?: boolean
  points: { x: number; y: number; fit: number; observation?: number; distance?: number; probability?: number }[]
  calculation?: { count: number; x_mean: number; y_mean: number; sxx: number; syy: number; sxy: number; residual_sum: number }
}

function isView(value: unknown): value is RegressionView {
  if (!value || typeof value !== 'object') return false
  const view = value as RegressionView
  return ['gamma', 'criterion', 'slope', 'intercept', 'beta', 'eta'].every(key =>
    Number.isFinite(view[key as keyof RegressionView]))
    && Array.isArray(view.points) && view.points.length > 0
    && view.points.every(point => [point.x, point.y, point.fit].every(Number.isFinite))
}

function regressionChart(view: RegressionView, lse: boolean, original = false, sampleIndex = 0): CalculationChart {
  const current = view.points[Math.min(sampleIndex, view.points.length - 1)]
  return {
    id: original ? 'original-probability-plot' : 'viewed-regression',
    title: original ? '2　原样本的概率图：γ = 0' : lse ? '2　这个位置下的 White 回归' : '3　平移后样本的概率图',
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

export function RegressionProcessViewer({ trace }: { trace: CalculationTrace }) {
  const details = trace.details as { regression_views?: unknown[]; original_regression?: unknown } | undefined
  const views = details?.regression_views?.filter(isView) ?? []
  const [viewIndex, setViewIndex] = useState<number | null>(null)
  const [sampleIndex, setSampleIndex] = useState(0)
  const selectedIndex = views.findIndex(view => view.selected)
  const index = Math.min(viewIndex ?? selectedIndex, views.length - 1)
  const view = views[index]
  const sample = view?.points[Math.min(sampleIndex, view.points.length - 1)]
  const sums = view?.calculation
  const lse = trace.method === 'lse'
  const criterion = trace.charts[0]
  if (!view || !criterion || selectedIndex < 0) return <div className="grid min-w-0 gap-4 xl:grid-cols-2">{trace.charts.map(chart => <ProcessChart key={chart.id} chart={chart} />)}</div>
  const original = isView(details?.original_regression) ? details.original_regression : null
  const locationChart: CalculationChart = {
    ...criterion,
    title: lse ? '1　比较 F 比，确定位置' : '1　概率图最直的位置在哪里',
    selected: [
      ...(criterion.selected ?? []).map(point => ({ ...point, label: '最终位置' })),
      ...(!view.selected ? [{ x: view.gamma, y: view.criterion, label: '正在查看' }] : []),
    ],
  }

  return <div className="min-w-0 space-y-4" data-regression-process={trace.method}>
    <p className="text-base leading-relaxed text-slate-700">{lse
      ? '换一个位置 γ，就把寿命减去 γ、重新做 White 回归并计算 F 比。F 最大的那组回归给出最终三参数。'
      : '换一个位置 γ，观察平移后的概率图是否更接近直线。相关系数最大处确定位置，再由这条直线求形状和尺度。'}</p>
    <div className="rounded-xl border border-slate-200 bg-white/70 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <label htmlFor={`location-view-${trace.method}`} className="text-base font-medium text-slate-800">查看位置 γ = {number(view.gamma)}</label>
        <button type="button" onClick={() => setViewIndex(selectedIndex)} className="rounded-lg bg-amber-50 px-3 py-2 text-base text-amber-900">回到最终位置</button>
      </div>
      <input id={`location-view-${trace.method}`} aria-label="切换位置并联动回归图" type="range" min={0} max={views.length - 1} step={1} value={index}
        onChange={event => setViewIndex(Number(event.target.value))} className="mt-4 w-full accent-emerald-700" />
      <div className="mt-1 flex flex-wrap justify-between gap-2 text-sm text-slate-500"><span>γ = {number(views[0].gamma)}</span><span>{view.selected ? '当前为最终采纳的位置' : '比较用位置；最终估计保持不变'}</span><span>γ = {number(views[views.length - 1].gamma)}</span></div>
    </div>
    {lse ? <div className="grid min-w-0 items-start gap-4 xl:grid-cols-2">
      <ProcessChart chart={locationChart} initiallyFocused={false} /><ProcessChart chart={regressionChart(view, true, false, sampleIndex)} />
    </div> : <>
      <ProcessChart chart={locationChart} initiallyFocused={false} />
      <div className="grid min-w-0 items-start gap-4 xl:grid-cols-2">{original && <ProcessChart chart={regressionChart(original, false, true, sampleIndex)} />}<ProcessChart chart={regressionChart(view, false, false, sampleIndex)} /></div>
    </>}
    {sample && sums && <section aria-label="样本变换与回归计算" className="min-w-0 space-y-3 rounded-xl border border-slate-200 px-4 py-4">
      <h3 className="text-lg font-semibold text-slate-800">样本怎样形成回归点，再算出直线和判据</h3>
      <p className="text-base leading-relaxed text-slate-700">{lse ? '横坐标 Xᵢ 是 White 标准对数 Weibull 分布第 i 个顺序统计量的期望，仅由 i 和样本量 n 确定，现行实现按期望积分计算；纵坐标是平移寿命的对数。' : '先按 Park 的绘图位置公式得到 pᵢ，再把它变成 Weibull 分数 Yᵢ；横坐标是平移寿命的对数。'}</p>
      {!lse && <ProcessFormula expression={view.points.length <= 10 ? String.raw`p_i=\frac{i-3/8}{n+1/4},\quad X_i=\ln(t_i-\gamma),\quad Y_i=\ln[-\ln(1-p_i)]` : String.raw`p_i=\frac{i-1/2}{n},\quad X_i=\ln(t_i-\gamma),\quad Y_i=\ln[-\ln(1-p_i)]`} />}
      <label htmlFor={`${trace.method}-regression-sample`} className="block text-base font-medium text-slate-800">查看第 {Math.min(sampleIndex + 1, view.points.length)} 个样本形成的点</label>
      {view.distance_precision_note && <p className="text-base text-amber-800">这个位置非常接近最小观测，显示的 γ 经过舍入；下面的距离保留计算时的精度。</p>}
      <input id={`${trace.method}-regression-sample`} aria-label="查看样本到回归点的计算" type="range" min={0} max={view.points.length - 1} value={Math.min(sampleIndex, view.points.length - 1)} onChange={event => setSampleIndex(Number(event.target.value))} className="w-full accent-blue-600" />
      <p className="rounded-lg bg-blue-50/60 px-4 py-3 text-base leading-relaxed text-slate-700">t₍ᵢ₎ = {number(sample.observation)}，t₍ᵢ₎ − γ = {number(sample.distance)}{lse ? `；Xᵢ = ${number(sample.x)}，Yᵢ = ln(${number(sample.distance)}) = ${number(sample.y)}` : `；pᵢ = ${number(sample.probability)}，Xᵢ = ln(${number(sample.distance)}) = ${number(sample.x)}，Yᵢ = ${number(sample.y)}`}。</p>
      <div className="grid min-w-0 gap-3 lg:grid-cols-2">
        <div className="min-w-0 rounded-lg bg-slate-50 px-4 py-3"><h4 className="text-base font-semibold text-slate-800">最小二乘得到斜率与截距</h4><ProcessFormula expression={String.raw`S_{XX}=\sum(X_i-\bar X)^2,\quad S_{XY}=\sum(X_i-\bar X)(Y_i-\bar Y)`} /><ProcessFormula expression={String.raw`b=S_{XY}/S_{XX},\quad a=\bar Y-b\bar X`} /><p className="text-base leading-relaxed">b = {number(sums.sxy)} ÷ {number(sums.sxx)} = <strong>{number(view.slope)}</strong><br />a = {number(sums.y_mean)} − {number(view.slope)} × {number(sums.x_mean)} = <strong>{number(view.intercept)}</strong></p></div>
        <div className="min-w-0 rounded-lg bg-amber-50/60 px-4 py-3"><h4 className="text-base font-semibold text-slate-800">由同一组点计算位置判据</h4>{lse ? <><ProcessFormula expression={String.raw`F=\frac{\sum(Y_i-\bar Y)^2/(n-1)}{\sum(Y_i-a-bX_i)^2/(n-2)}`} /><p className="text-base leading-relaxed">F = [{number(sums.syy)} / {sums.count - 1}] ÷ [{number(sums.residual_sum)} / {sums.count - 2}] = <strong>{number(view.criterion)}</strong></p></> : <><ProcessFormula expression={String.raw`\rho=S_{XY}/\sqrt{S_{XX}S_{YY}},\quad S_{YY}=\sum(Y_i-\bar Y)^2`} /><p className="text-base leading-relaxed">ρ = {number(sums.sxy)} ÷ √({number(sums.sxx)} × {number(sums.syy)}) = <strong>{number(view.criterion)}</strong></p></>}</div>
      </div>
    </section>}
    <div className="grid min-w-0 gap-3 rounded-xl bg-emerald-50/60 p-4 text-base sm:grid-cols-3">
      <p>{lse ? 'F 比' : '相关系数 ρ'} = <strong>{number(view.criterion)}</strong><span className="mt-1 block text-sm text-slate-600">{lse ? '比较各位置的 F，取最大值' : '比较各位置的 ρ，取最大值'}</span></p>
      <p>斜率 b = <strong>{number(view.slope)}</strong><span className="mt-1 block text-base text-slate-600">{lse ? `形状 β = 1/${number(view.slope)} = ` : '形状 β = b = '}{number(view.beta)}</span></p>
      <p>截距 a = <strong>{number(view.intercept)}</strong><span className="mt-1 block text-base text-slate-600">{lse ? `尺度 η = exp(${number(view.intercept)}) = ` : `尺度 η = exp[−(${number(view.intercept)})/${number(view.slope)}] = `}{number(view.eta)}</span></p>
    </div>
    <details className="rounded-xl border border-slate-200 px-4 py-3">
      <summary className="cursor-pointer text-base font-medium text-slate-700">比较不同位置的数值</summary>
      <div className="mt-3 overflow-x-auto"><table className="w-full text-right text-base tabular-nums"><thead><tr className="text-slate-500">{['位置 γ', lse ? 'F 比' : '相关系数 ρ', '形状 β', '尺度 η', ''].map((label, i) => <th key={i} className="whitespace-nowrap px-3 py-2 font-medium">{label}</th>)}</tr></thead>
        <tbody>{views.map((candidate, i) => <tr key={i} className={i === index ? 'bg-emerald-50 text-emerald-900' : 'text-slate-700'}>
          {[candidate.gamma, candidate.criterion, candidate.beta, candidate.eta].map((value, j) => <td key={j} className="whitespace-nowrap px-3 py-2">{number(value)}</td>)}
          <td className="whitespace-nowrap px-3 py-2"><button type="button" onClick={() => setViewIndex(i)} aria-pressed={i === index} className="rounded px-2 py-1 text-emerald-800 hover:bg-emerald-100">{candidate.selected ? '最终位置' : '查看图'}</button></td>
        </tr>)}</tbody></table></div>
      <p className="mt-2 text-sm text-slate-500">表内抽取本次计算已经求值的位置供比较。</p>
    </details>
  </div>
}
