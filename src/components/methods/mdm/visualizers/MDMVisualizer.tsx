"use client"

import { useEffect, useMemo, useState } from 'react'
import { CalculationProcessViewer } from '@/components/shared/charts/CalculationProcessViewer'
import { embeddedCalculationTrace, formatCalculationNumber as number, readCalculationTrace, type CalculationTrace } from '@/lib/calculation-trace'
import type { FlowChartTarget } from '@/lib/method-flow'
import { MDM_OFFSET_MAX, MDM_OFFSET_MIN, MDM_OFFSET_STEP } from '@/lib/calculator-state'
import { CalculationWorkspace } from '@/components/methods/CalculationWorkspace'
import { ProcessPointLegend } from '@/components/shared/charts/CalculationProcessChart'
import { ProcessEquation } from '@/components/shared/charts/ProcessEquation'
import { ProcessPlotControls } from '@/components/shared/charts/ProcessPlot'
import { ProcessValueTable } from '@/components/shared/charts/ProcessValueTable'
import { SigmaBetaChart, GradientGammaChart } from '../charts'
import { mdmGradientDomain, mdmProcessData, type ShapeSlice } from './process-data'
import { MDMScaleCalculation, MDMScaleValues } from './MDMScaleCalculation'
import { useCalculationBatch } from '../../CalculationBatch'
import { MDMBatchWorkspace } from '../MDMBatchWorkspace'
import { liveMDMBatch } from './batch-process-data'

type ProcessData = NonNullable<ReturnType<typeof mdmProcessData>>
interface MDMVisualizerProps {
  traceData: unknown
  calculation?: unknown
  rSquared?: number | null
  mdmOffset: number
  onMdmOffsetChange: (offset: number) => void
  offsetStale?: boolean
  isOffsetUpdating?: boolean
}

export default function MDMVisualizer({ traceData, calculation, rSquared, mdmOffset, onMdmOffsetChange,
  offsetStale = false, isOffsetUpdating = false }: MDMVisualizerProps) {
  const record = calculation ?? embeddedCalculationTrace(traceData)
  const batch = useCalculationBatch()
  const batchProcess = useMemo(() => batch ? liveMDMBatch(batch.sources, batch.origin, mdmOffset) : null, [batch, mdmOffset])
  const { trace } = readCalculationTrace(record, 'mdm')
  const model = useMemo(() => trace ? mdmProcessData(traceData, trace) : null, [traceData, trace])
  const [manualIndex, setManualIndex] = useState<number | null>(null)
  const [fullShape, setFullShape] = useState(true)
  const [fullGradient, setFullGradient] = useState(true)
  useEffect(() => { setManualIndex(null); setFullShape(true); setFullGradient(true) }, [traceData, calculation])
  const finalIndex = model?.slices.indexOf(model.finalSlice) ?? -1
  const selected = model ? model.slices[manualIndex ?? (finalIndex > 0 ? finalIndex - 1 : 1)] ?? model.finalSlice : undefined
  const shownOffset = model && !isOffsetUpdating ? model.offset : mdmOffset
  const branch = trace?.selection.approximate === true ? 'extrapolated' : trace?.selection.strategy === 'truncated_at_zero' ? 'zero' : 'ready'
  if (batch && batchProcess?.runs.length) return <MDMBatchWorkspace process={batchProcess}
    selectedRun={batch.activeIndex + 1} onSelect={id => { if (id !== null) batch.onSelect(id - 1) }} />
  return <CalculationWorkspace methodId="mdm" ready={!!model} updating={isOffsetUpdating} revision={model}
    values={model ? { n: String(model.pseudoScales.length), offset: number(shownOffset), found_gamma: number(model.finalSlice.gamma),
      found_beta: number(model.finalSlice.beta), found_eta: number(model.finalSlice.eta) } : {}}
    workflowValues={{ count: model?.pseudoScales.length || undefined, offset: shownOffset }}
    workflowBranch={branch}
    formulaVariant={(_, target) => target === 'samples' ? model?.rankMethod ?? undefined : target === 'location' ? branch : undefined}
    notice={offsetStale && !isOffsetUpdating && <p role="status" className="py-3 text-sm text-amber-800">偏移量已改变，请重新计算。</p>}
    emptyContent={record ? <CalculationProcessViewer calculation={record} methodId="mdm" showOverview={false} />
      : <p className="py-6 text-slate-500">输入样本并计算后，即可查看过程图。</p>}
    renderFigure={(_, target) => trace && model && selected && <MDMStepImage target={target} model={model} selected={selected} trace={trace}
      rSquared={rSquared} fullShape={fullShape} setFullShape={setFullShape} fullGradient={fullGradient} setFullGradient={setFullGradient}
      setManualIndex={setManualIndex} shownOffset={shownOffset} mdmOffset={mdmOffset} onMdmOffsetChange={onMdmOffsetChange} />}
    renderDetails={(_, target) => trace && model && selected && <MDMRuntimeDetails target={target} trace={trace} model={model} selected={selected}
      rSquared={rSquared} shownOffset={shownOffset} />} />
}

function MDMStepImage({ target, model, selected, trace, rSquared, fullShape, setFullShape, fullGradient,
  setFullGradient, setManualIndex, shownOffset, mdmOffset, onMdmOffsetChange }: {
  target?: FlowChartTarget; model: ProcessData; selected: ShapeSlice; trace: CalculationTrace; rSquared?: number | null
  fullShape: boolean; setFullShape: (value: boolean) => void; fullGradient: boolean; setFullGradient: (value: boolean) => void
  setManualIndex: (index: number) => void; shownOffset: number; mdmOffset: number; onMdmOffsetChange: (value: number) => void
}) {
  if (target === 'samples') return <ProcessValueTable label="样本与经验概率" minColumnWidth={460}
    columns={['序号 i', '排序样本 t₍ᵢ₎', '经验概率 pᵢ', '概率变换 xᵢ'].map((label, index) => ({ label, align: index ? 'right' : 'left' }))}
    rows={model.pseudoScales.map((point, index) =>
      [index + 1, number(point.observation), number(point.rank), number(point.rank_transform)])} />
  if (target === 'trial') return <div className="space-y-3">
    <ProcessPlotControls>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label htmlFor="mdm-process-gamma" className="text-slate-600">查看 γ = <span className="tabular-nums">{number(selected.gamma)}</span></label>
        <button type="button" onClick={() => setManualIndex(model.slices.indexOf(model.finalSlice))}
          className="text-sm text-blue-700">查看采纳位置</button>
      </div>
      <input id="mdm-process-gamma" aria-label="查看不同位置下的形状寻优" type="range" min={0} max={model.slices.length - 1}
        step={1} value={model.slices.indexOf(selected)} onChange={event => setManualIndex(Number(event.target.value))}
        className="h-4 w-full accent-blue-600" />
    </ProcessPlotControls>
    <MDMShapePlot slice={selected} full={fullShape} />
    <div className="flex flex-wrap items-center justify-between gap-2">
      <ProcessPointLegend color="#2563eb" selectedLabel="条件最小点" />
      <button type="button" onClick={() => setFullShape(!fullShape)} className="text-sm text-blue-700">
        {fullShape ? '聚焦条件最小点' : '显示全部范围'}</button>
    </div>
  </div>
  if (target === 'location') {
    const intersection = model.interpolation?.point
    const chosen = intersection ? { gamma: intersection.x, gradient: intersection.y }
      : model.gradients.find(point => point.gamma === model.finalSlice.gamma)
    return <div className="space-y-3">
      <ProcessPlotControls>
        <label htmlFor="mdm-process-offset" className="text-slate-600">偏移量 δ = {number(shownOffset)}</label>
        <input id="mdm-process-offset" aria-label="MDM偏移量" type="range" min={MDM_OFFSET_MIN} max={MDM_OFFSET_MAX}
          step={MDM_OFFSET_STEP} value={mdmOffset} onChange={event => onMdmOffsetChange(Number(event.target.value))}
          className="h-4 w-full accent-emerald-600" />
      </ProcessPlotControls>
      <GradientGammaChart curves={[{ id: 'gradient', data: model.gradients }]} workspacePlot
        calculatedPoints={model.gradientEvaluations}
        domain={mdmGradientDomain(model.gradients, model.finalSlice.gamma, shownOffset, fullGradient)}
        offsetReference={shownOffset} interpolation="linear" selectedPoint={chosen}
        gammaReferenceLines={[{ gamma: model.finalSlice.gamma, label: `γ̂ = ${number(model.finalSlice.gamma)}`, color: '#b7791f', position: 'top' },
          ...(selected.gamma !== model.finalSlice.gamma ? [{ gamma: selected.gamma, label: '当前试算', color: '#2563eb', position: 'bottom' as const }] : [])]} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <ProcessPointLegend color="#ef4444" selectedLabel={intersection ? '插值交点' : undefined} />
        <button type="button" onClick={() => setFullGradient(!fullGradient)} className="text-sm text-blue-700">
          {fullGradient ? '聚焦选中位置' : '显示全部范围'}</button>
      </div>
    </div>
  }
  if (target === 'shape') return <div className="space-y-3">
    <p className="text-slate-600">固定 γ̂ = {number(model.finalSlice.gamma)}</p>
    <MDMShapePlot slice={model.finalSlice} full />
    <ProcessPointLegend color="#2563eb" selectedLabel="采纳形状" />
  </div>
  if (target === 'scale') return <MDMScaleValues values={model.pseudoScales} total={model.scaleSum} />
  return <ProcessValueTable label="本次估计结果" columns={[{ label: '估计量' }, { label: '取值', align: 'right' }]}
    rows={resultValues(model, trace, rSquared)} />
}

function MDMRuntimeDetails({ target, model, selected, trace, rSquared, shownOffset }: {
  target?: FlowChartTarget; model: ProcessData; selected: ShapeSlice; trace: CalculationTrace; rSquared?: number | null; shownOffset: number
}) {
  if (target === 'scale') return <MDMScaleCalculation values={model.pseudoScales} total={model.scaleSum}
    eta={model.finalSlice.eta!} beta={model.finalSlice.beta} gamma={model.finalSlice.gamma} />
  if (target === 'trial') return <p className="text-sm leading-relaxed tabular-nums text-slate-600">
    当前试算 γ = {number(selected.gamma)}，s(γ) = {number(selected.sigma)}。</p>
  if (target === 'location') return <div className="space-y-3">
    <p className="text-base tabular-nums">δ = {number(shownOffset)}，γ̂ = {number(model.finalSlice.gamma)}</p>
    {trace.selection.approximate === true && <p role="status" className="text-sm text-amber-800">{trace.selection.description}</p>}
    {model.interpolation && <details>
      <summary className="cursor-pointer text-sm text-slate-600">插值计算</summary>
      {model.interpolation.formula && <ProcessEquation expression={model.interpolation.formula} />}
      <p className="text-sm leading-relaxed tabular-nums text-slate-600">
        左点 ({number(model.interpolation.left.gamma)}, {number(model.interpolation.left.gradient)})，
        右点 ({number(model.interpolation.right.gamma)}, {number(model.interpolation.right.gradient)})。
      </p>
    </details>}
  </div>
  if (target === 'samples') return <p className="text-sm text-slate-600">
    n = {model.pseudoScales.length}，{model.rankMethod === 'exact' ? '精确中位秩' : 'Bernard 近似秩'}。</p>
  if (target === 'shape') return <p className="text-base tabular-nums">β̂ = {number(model.finalSlice.beta)}</p>
  return <p className="text-sm text-slate-600">{resultValues(model, trace, rSquared).at(-1)?.[1]}</p>
}

function resultValues(model: ProcessData, trace: CalculationTrace, rSquared?: number | null): [string, string][] {
  return [
    ['位置 γ̂', number(model.finalSlice.gamma)], ['形状 β̂', number(model.finalSlice.beta)], ['尺度 η̂', number(model.finalSlice.eta)],
    ['拟合优度 R²', rSquared == null ? '—' : number(rSquared)],
    ['求解状态', trace.selection.approximate ? '右端回退'
      : trace.selection.strategy === 'truncated_at_zero' ? '零位置'
        : trace.selection.solver === 'linear_interpolation' ? '线性插值' : '已采纳'],
  ]
}

function MDMShapePlot({ slice, full }: { slice: ShapeSlice; full: boolean }) {
  const points = full ? slice.points : slice.points.filter(point =>
    point.beta >= slice.beta * .45 && point.beta <= slice.beta * 1.8)
  const x = points.map(point => point.beta)
  const y = points.map(point => point.sigma)
  return <SigmaBetaChart curves={[{ id: 'current', data: points }]} workspacePlot
    calculatedPoints={slice.evaluatedPoints}
    domain={{ x: [Math.min(...x), Math.max(...x)], y: [0, Math.max(...y) * 1.08 || 1] }}
    xTicks={[]} interpolation="linear" selectedPoint={{ beta: slice.beta, sigma: slice.sigma }} />
}
