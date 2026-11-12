"use client"

import { useEffect, useMemo, useState } from 'react'
import { CalculationWorkspace } from '@/components/methods/CalculationWorkspace'
import { PowerScaleCalculation } from '@/components/methods/PowerScaleCalculation'
import { ProcessChart } from '@/components/shared/charts/CalculationProcessChart'
import { ProcessPlotControls } from '@/components/shared/charts/ProcessPlot'
import { ProcessValueTable } from '@/components/shared/charts/ProcessValueTable'
import { embeddedCalculationTrace, readCalculationTrace, formatCalculationNumber as number, type CalculationChart, type CalculationTrace } from '@/lib/calculation-trace'
import type { FlowChartTarget } from '@/lib/method-flow'
import { mleProcessData, type MLEFrame } from './process-data'
import { useCalculationBatch } from '../../CalculationBatch'

type Model = NonNullable<ReturnType<typeof mleProcessData>>

interface Props {
  traceData: unknown
  calculation?: unknown
  rSquared?: number | null
  isUpdating?: boolean
}

export default function MLEVisualizer({ traceData, calculation, rSquared, isUpdating = false }: Props) {
  const record = calculation ?? embeddedCalculationTrace(traceData)
  const { trace } = readCalculationTrace(record, 'mle')
  const model = useMemo(() => trace ? mleProcessData(trace) : null, [trace])
  const [index, setIndex] = useState(0)
  useEffect(() => setIndex(0), [record])
  const viewed = model?.frames[Math.min(index, model.frames.length - 1)]
  const branch = model && !model.success ? 'failed' : model?.final?.gamma === 0 ? 'zero' : 'ready'
  const values: Record<string, string> = model ? { n: String(model.samples.length), unit: number(model.unit), candidate_count: String(model.candidates.length),
    gamma: number(model.final?.gamma), beta: number(model.final?.beta), eta: number(model.final?.eta),
    log_likelihood: number(model.final?.log_likelihood), r_squared: number(rSquared),
    viewed_gamma: number(viewed?.gamma), viewed_beta: number(viewed?.beta), viewed_eta: number(viewed?.eta), viewed_ll: number(viewed?.log_likelihood) } : {}
  return <CalculationWorkspace methodId="mle" ready={!!model} updating={isUpdating} revision={model}
    values={values} workflowBranch={branch}
    workflowValues={{ count: model?.samples.length, viewedGamma: viewed?.gamma, gamma: model?.final?.gamma, beta: model?.final?.beta, eta: model?.final?.eta }}
    formulaVariant={(_, target) => target === 'trial' ? viewed?.shape_at_lower_boundary ? 'boundary' : undefined
      : target === 'location' ? branch : target === 'shape' ? model && !model.success ? 'failed' : model?.final?.shape_at_lower_boundary ? 'boundary' : undefined
        : target === 'scale' ? model && !model.success ? 'failed' : model?.scale?.use_scaled ? 'scaled' : undefined : undefined}
    notice={trace && !model ? <p role="alert" className="py-3 text-sm text-amber-800">这份记录缺少本次求解明细，请重新计算后查看。</p>
      : model && !model.success ? <p role="status" className="py-3 text-sm text-amber-800">本次未找到合格的有限局部极大候选，不返回参数估计。</p> : null}
    emptyContent={!record && <p className="py-6 text-slate-500">输入样本并计算后，即可查看过程图。源码可直接切换查看。</p>}
    renderFigure={(_, target) => trace && model ? <MLEFigure target={target} trace={trace} model={model} viewed={viewed}
      index={index} setIndex={setIndex} rSquared={rSquared} /> : null}
    renderDetails={(_, target) => trace && model ? <MLERuntimeDetails target={target} trace={trace} model={model} viewed={viewed} /> : null} />
}

function shapeReadingChart(frame: MLEFrame) {
  const actual = frame.shape_chart.series.find(series => series.id === 'solver-points')?.points
  return { ...frame.shape_chart, series: frame.shape_chart.series.filter(series => series.id === 'shape-score')
    .map(series => ({ ...series, points: actual ? [...actual].sort((a, b) => a.x - b.x) : series.points })) }
}

function ShapeFigure({ frame, final = false }: { frame: MLEFrame; final?: boolean }) {
  const batch = useCalculationBatch()
  const charts = useMemo(() => batch?.records.flatMap(({ source, trace }) => {
    const model = mleProcessData(trace)
    if (!model?.frames.length) return []
    const selected = final ? model.final : model.frames.reduce((nearest, item) =>
      Math.abs(item.normalized_gamma - frame.normalized_gamma) < Math.abs(nearest.normalized_gamma - frame.normalized_gamma) ? item : nearest)
    return selected ? [{ sourceId: source.id, label: source.name + ' · γ=' + number(selected.gamma), chart: shapeReadingChart(selected) }] : []
  }), [batch, frame, final])
  return <ProcessChart key={frame.evaluation} chart={shapeReadingChart(frame)} batchCharts={charts}
    figureOnly workspacePlot initiallyFocused={false} showYAxisLabel focusLabel="聚焦条件形状" />
}

function MLEFigure({ target, trace, model, viewed, index, setIndex, rSquared }: {
  target?: FlowChartTarget; trace: CalculationTrace; model: Model; viewed?: MLEFrame; index: number; setIndex: (index: number) => void; rSquared?: number | null
}) {
  if (target === 'samples') return <ProcessValueTable label="排序样本与归一化" minColumnWidth={340}
    columns={[{ label: '序号 i' }, { label: '排序样本 t₍ᵢ₎', align: 'right' }, { label: '归一化 zᵢ', align: 'right' }]}
    rows={model.samples.map(sample => [sample.index, number(sample.observation), number(sample.normalized)])} />
  if (target === 'trial') return viewed ? <div className="space-y-3">
    <ProcessPlotControls>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label htmlFor="mle-trial-location" className="text-slate-600">试算位置 γ = {number(viewed.gamma)}</label>
        {model.final && <button type="button" className="text-sm text-blue-700" onClick={() => setIndex(model.frames.indexOf(model.final!))}>查看采纳位置</button>}
      </div>
      <input id="mle-trial-location" aria-label="查看MLE实际试算位置" type="range" min={0} max={model.frames.length - 1}
        step={1} value={Math.min(index, model.frames.length - 1)} onChange={event => setIndex(Number(event.target.value))} className="h-4 w-full accent-emerald-600" />
    </ProcessPlotControls>
    <ShapeFigure frame={viewed} />
    <ProcessValueTable label="当前试算的条件结果" columns={[{ label: '条件量' }, { label: '取值', align: 'right' }]}
      rows={[[`条件形状 β*`, number(viewed.beta)], ['对应尺度 η*', number(viewed.eta)], ['剖面对数似然 ℓₚ', number(viewed.log_likelihood)]]} />
  </div> : <p className="text-slate-500">本次没有可显示的有限条件求值。</p>
  if (target === 'location') return <div className="space-y-6">
    {trace.charts.filter(chart => ['profile-likelihood', 'location-score'].includes(chart.id)).map(chart => {
      const shown: CalculationChart = { ...chart, references: [...chart.references ?? [],
        ...(viewed && viewed.gamma !== model.final?.gamma ? [{ axis: 'x' as const, value: viewed.gamma, label: '当前试算' }] : [])] }
      return <div key={chart.id} className="min-w-0 space-y-3">
        <ProcessPlotControls><h4 className="text-base text-slate-600">{chart.title}</h4></ProcessPlotControls>
        <ProcessChart chart={shown} initiallyFocused={false} figureOnly workspacePlot showYAxisLabel focusLabel="聚焦候选位置" /></div>
    })}
    {model.candidates.length > 0 && <ProcessValueTable label="合格有限候选" minColumnWidth={460}
      columns={[{ label: '位置 γ' }, { label: '形状 β', align: 'right' }, { label: '尺度 η', align: 'right' }, { label: '似然 ℓ', align: 'right' }]}
      rows={model.candidates.map(candidate => [number(candidate.gamma), number(candidate.beta), number(candidate.eta), number(candidate.ll)])} />}
  </div>
  if (target === 'shape') return model.final ? <div className="space-y-3"><p className="text-slate-600">固定 γ̂ = {number(model.final.gamma)}</p>
    <ShapeFigure frame={model.final} final />
    {model.final.shape_at_lower_boundary && <p className="text-sm text-slate-600">β̂ = 1，按形状下界采纳。</p>}
  </div> : <p className="text-slate-500">未采纳有限候选，本步没有形状估计。</p>
  if (target === 'scale') return model.scale ? <PowerScaleCalculation trace={trace} view="table" />
    : <p className="text-slate-500">未采纳有限候选，本步没有尺度估计。</p>
  return <ProcessValueTable label="MLE本次估计结果" columns={[{ label: '估计量' }, { label: '取值', align: 'right' }]}
    rows={[[`位置 γ̂`, number(model.final?.gamma)], ['形状 β̂', number(model.final?.beta)], ['尺度 η̂', number(model.final?.eta)],
      ['拟合优度 R²', model.success ? number(rSquared) : '—'], ['对数似然 ℓ', number(model.final?.log_likelihood)],
      ['求解状态', !model.success ? '未找到有限局部极大值' : model.final?.gamma === 0 ? '零位置边界' : '有限局部极大候选']]} />
}

function MLERuntimeDetails({ target, trace, model, viewed }: { target?: FlowChartTarget; trace: CalculationTrace; model: Model; viewed?: MLEFrame }) {
  if (target === 'samples') return <p className="text-sm text-slate-600">n = {model.samples.length}，u = {number(model.unit)}</p>
  if (target === 'trial') return viewed && <p className="text-sm leading-relaxed tabular-nums text-slate-600">
    γ = {number(viewed.gamma)}，Sβ = {number(viewed.shape_score)}{viewed.shape_at_lower_boundary ? '，形状下界。' : '。'}</p>
  if (target === 'location') return <div className="space-y-4">
    <p className="text-sm text-slate-600">合格候选 {model.candidates.length} 个{model.final ? `，采纳 γ̂ = ${number(model.final.gamma)}` : ''}。</p>
    {model.supportLimit && <details><summary className="cursor-pointer text-sm text-slate-600">支持边界诊断</summary>
      <p className="mt-2 text-sm leading-relaxed text-slate-600">γ → {number(model.supportLimit.gamma)} 的开边界极限未在支持域内取到，仅记诊断。</p>
      <p className="mt-2 text-sm tabular-nums text-slate-600">ℓlim = {number(model.supportLimit.log_likelihood)}</p>
      {model.limitExceedsSelected && <p className="mt-2 text-sm text-slate-600">该极限高于所选有限候选的似然。</p>}
    </details>}
  </div>
  if (target === 'shape') return model.final && <p className="text-sm tabular-nums text-slate-600">β̂ = {number(model.final.beta)}，Sβ = {number(model.final.shape_score)}</p>
  if (target === 'scale') return model.scale && <PowerScaleCalculation trace={trace} view="details" />
  return <p className="text-sm text-slate-600">R² 仅作拟合检查。</p>
}
