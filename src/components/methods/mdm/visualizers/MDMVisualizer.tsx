"use client"

import { useEffect, useMemo, useState } from 'react'
import { CalculationProcessViewer } from '@/components/shared/charts/CalculationProcessViewer'
import { embeddedCalculationTrace, formatCalculationNumber, readCalculationTrace } from '@/lib/calculation-trace'
import { calculationSteps } from '@/lib/calculation-steps'
import { MDM_OFFSET_MAX, MDM_OFFSET_MIN, MDM_OFFSET_STEP } from '@/lib/calculator-state'
import type { DataSource } from '@/lib/weibull'
import { SigmaBetaChart, GradientGammaChart } from '../charts'
import { mdmGradientDomain, mdmProcessData } from './process-data'
import { MDMScaleCalculation } from './MDMScaleCalculation'
import { CalculationProgramLink, CalculationStepContent } from '@/components/methods/CalculationSteps'
import { ProcessFormula, ProcessPointLegend } from '@/components/shared/charts/CalculationProcessChart'

interface MDMVisualizerProps {
  traceData: unknown
  calculation?: unknown
  methodId?: string
  dataSources?: DataSource[]
  mdmOffset: number
  onMdmOffsetChange: (offset: number) => void
  offsetStale?: boolean
  isOffsetUpdating?: boolean
}

export default function MDMVisualizer({ traceData, calculation, mdmOffset, onMdmOffsetChange,
  offsetStale = false, isOffsetUpdating = false }: MDMVisualizerProps) {
  const record = calculation ?? embeddedCalculationTrace(traceData)
  const { trace } = readCalculationTrace(record, 'mdm')
  const model = useMemo(() => trace ? mdmProcessData(traceData, trace) : null, [traceData, trace])
  const [manualIndex, setManualIndex] = useState<number | null>(null)
  const [showFullShape, setShowFullShape] = useState(true)
  const [showFullGradient, setShowFullGradient] = useState(true)
  useEffect(() => { setManualIndex(null); setShowFullShape(true); setShowFullGradient(true) }, [traceData, calculation])
  if (!trace || !model) return <CalculationProcessViewer calculation={record} methodId="mdm" stale={offsetStale} isUpdating={isOffsetUpdating} />

  const selected = manualIndex === null ? model.finalSlice : model.slices[manualIndex] ?? model.finalSlice
  const finalIndex = model.slices.findIndex(slice => slice.gamma === model.finalSlice.gamma)
  const points = showFullShape ? selected.points : selected.points.filter(point =>
    point.beta >= selected.beta * 0.45 && point.beta <= selected.beta * 1.8)
  const xValues = points.map(point => point.beta)
  const yValues = points.map(point => point.sigma)
  const shapeDomain = { x: [Math.min(...xValues), Math.max(...xValues)] as [number, number],
    y: [0, Math.max(...yValues) * 1.08 || 1] as [number, number] }
  const updatingOffset = isOffsetUpdating && mdmOffset !== model.offset
  const shownOffset = updatingOffset ? mdmOffset : model.offset
  const approximate = trace.selection.approximate === true
  const selectionLabel = updatingOffset ? '上次选中位置' : approximate ? '外推位置' : trace.selection.strategy === 'truncated_at_zero' ? '零位置处理' : '选中位置'
  const chosenGradient = model.gradients.find(point => point.gamma === model.finalSlice.gamma)
  const atZero = trace.selection.strategy === 'truncated_at_zero'
  const [shapeStep, positionStep, scaleStep] = calculationSteps.mdm

  return <div className="min-w-0 space-y-4" data-calculation-method="mdm" aria-busy={isOffsetUpdating}>
    {offsetStale && !isOffsetUpdating && <p role="status" className="rounded-xl bg-amber-50 px-4 py-3 text-base text-amber-800">偏移量已改变，请重新计算。</p>}
    {(approximate || trace.selection.strategy === 'truncated_at_zero') && <p className="rounded-xl bg-amber-50 px-4 py-3 text-base leading-relaxed text-amber-900">{trace.selection.description}</p>}
    <CalculationProgramLink method="mdm" programSteps={[...shapeStep.programSteps, ...positionStep.programSteps]} />
    <CalculationStepContent title="位置 γ 与形状 β 的联动" stacked
      figure={
        <div className="grid min-w-0 items-start gap-6 min-[900px]:grid-cols-2">
          <div className="min-w-0 space-y-2" aria-label="位置梯度图">
            <h5 className="font-semibold text-slate-800">位置梯度 g(γ)</h5>
            <label htmlFor="mdm-process-offset" className="flex min-h-9 items-center text-base text-slate-600">
              偏移量 δ = {formatCalculationNumber(shownOffset)}
            </label>
            <input id="mdm-process-offset" aria-label="MDM偏移量" type="range" min={MDM_OFFSET_MIN} max={MDM_OFFSET_MAX} step={MDM_OFFSET_STEP}
              value={mdmOffset} onChange={event => onMdmOffsetChange(Number(event.target.value))} className="block w-full accent-emerald-600" />
            <GradientGammaChart curves={[{ id: 'gradient', data: model.gradients }]} noContainer height={320}
              calculatedPoints={model.gradientEvaluations}
              domain={mdmGradientDomain(model.gradients, model.finalSlice.gamma, shownOffset, showFullGradient)}
              offsetReference={shownOffset} interpolation="linear"
              selectedPoint={chosenGradient ? { gamma: chosenGradient.gamma, gradient: chosenGradient.gradient } : undefined}
              gammaReferenceLines={[{ gamma: model.finalSlice.gamma, label: `${approximate ? '外推 ' : ''}γ̂ = ${formatCalculationNumber(model.finalSlice.gamma)}`, color: '#b7791f', position: 'top' },
                ...(manualIndex !== null && selected.gamma !== model.finalSlice.gamma ? [{ gamma: selected.gamma, label: '当前查看', color: '#2563eb' }] : [])]} />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <ProcessPointLegend color="#ef4444" />
              <button type="button" onClick={() => setShowFullGradient(value => !value)} className="rounded-lg px-2 py-1 text-blue-700 hover:bg-blue-50">{showFullGradient ? '聚焦选中位置' : '显示全部范围'}</button>
            </div>
          </div>
          <div className="min-w-0 space-y-2" aria-label="条件形状图">
            <h5 className="font-semibold text-slate-800">固定 γ 的形状寻优</h5>
            <div className="flex min-h-9 flex-wrap items-center justify-between gap-x-2 gap-y-1">
              <label htmlFor="mdm-process-gamma" className="text-slate-600">查看 γ = <span className="tabular-nums text-blue-700">{formatCalculationNumber(selected.gamma)}</span> <span className="text-sm">（{manualIndex === null ? selectionLabel : '试算'}）</span></label>
              <button type="button" onClick={() => { setManualIndex(null); setShowFullShape(true) }} aria-pressed={manualIndex === null}
                className="rounded-lg bg-blue-50 px-2 py-1.5 text-sm text-blue-700">回到选中位置</button>
            </div>
            <input id="mdm-process-gamma" aria-label="查看不同位置下的形状寻优" type="range" min={0} max={model.slices.length - 1} step={1}
              value={manualIndex ?? finalIndex} onChange={event => {
                setManualIndex(Number(event.target.value))
                setShowFullShape(true)
                setShowFullGradient(true)
              }} className="block w-full accent-blue-600" />
            <SigmaBetaChart curves={[{ id: 'current', data: points }]} noContainer height={320}
              calculatedPoints={selected.evaluatedPoints}
              domain={shapeDomain} xTicks={[]} interpolation="linear"
              selectedPoint={{ beta: selected.beta, sigma: selected.sigma }} />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <ProcessPointLegend color="#2563eb" selectedLabel="条件最小点" />
              <button type="button" onClick={() => setShowFullShape(value => !value)} className="rounded-lg px-2 py-1 text-blue-700 hover:bg-blue-50">{showFullShape ? '聚焦条件最小点' : '显示全部范围'}</button>
            </div>
            {selected.gamma !== model.finalSlice.gamma && <p className="text-sm text-slate-600">试算 β = {formatCalculationNumber(selected.beta)}，σ₍η₎ = {formatCalculationNumber(selected.sigma)}。</p>}
          </div>
        </div>
      }
      criterion={<div className="grid min-w-0 gap-5 sm:grid-cols-2">
        <div className="min-w-0">
          <ProcessFormula expression={approximate ? String.raw`g(\gamma_R)<\delta,\qquad\hat\gamma<t_{(1)}` : atZero
            ? String.raw`g(0)\ge\delta\ \Longrightarrow\ \hat\gamma=0` : String.raw`g(\hat\gamma)-\delta=0`} />
          <p className="text-base text-slate-700">γ̂ = {formatCalculationNumber(model.finalSlice.gamma)}{approximate ? '（右端外推）' : ''}{updatingOffset ? `（上次 δ = ${formatCalculationNumber(model.offset)} 的结果）` : ''}。</p>
        </div>
        <div className="min-w-0">
          <ProcessFormula expression={String.raw`\hat\beta=\beta^*(\hat\gamma)`} />
          <p className="text-base text-slate-700">β̂ = {formatCalculationNumber(model.finalSlice.beta)}。</p>
        </div>
      </div>}
      calculation={<>
          <p className="mt-2 text-base text-slate-700">拖动查看位置 γ，梯度图标出同一位置，形状图显示该位置的试算结果。</p>
          <ProcessFormula expression={String.raw`\begin{aligned}s(\gamma)&=\min_\beta\sigma_\eta(\beta,\gamma)\\g(\gamma)&=\frac{ds(\gamma)}{d\gamma}\approx\frac{s(\gamma+h)-s(\gamma-h)}{2h}\end{aligned}`} />
          <p className="text-base text-slate-700">图中内点用中心差分，靠近搜索端点时用单侧差分。</p>
          <ProcessFormula expression={String.raw`\begin{aligned}\eta_i(\beta,\gamma)&=\frac{t_{(i)}-\gamma}{[-\ln(1-p_i)]^{1/\beta}}\\\sigma_\eta(\beta,\gamma)&=\sqrt{\frac{\sum_i(\eta_i-\bar\eta)^2}{n-1}}\\\beta^*(\gamma)&=\arg\min_{0.1\le\beta\le15}\sigma_\eta(\beta,\gamma)\end{aligned}`} />
          {approximate && <p className="text-base text-amber-800">右端梯度低于目标值，采用贴近最小观测值左侧的外推位置。</p>}
      </>}
      symbols={[
        ['位置图横轴', '试算位置 γ'], ['位置图纵轴', '最小标准差对 γ 的梯度 g(γ)'],
        ['形状图横轴', '固定查看位置下试算的 β'], ['形状图纵轴', '伪尺度的样本标准差 σ₍η₎'],
        ['s(γ)', '在该 γ 下对 β 寻优后得到的最小标准差'], ['β*(γ)', '该 γ 下使标准差最小的形状'],
        ['δ', '水平虚线所示的目标梯度'], ['h', '数值差分步长'], ['γ̂、β̂', '最终采纳的位置和形状'],
        ['t₍ᵢ₎、pᵢ', '排序后的第 i 个观测值及其经验累计概率'],
        ['ηᵢ、η̄', '单个观测反算的伪尺度及当前 β、γ 下的伪尺度平均值'], ['n', '样本量'],
        ...(approximate ? [['γR', '右端探测位置'], ['t₍₁₎', '最小观测值']] as const : []),
      ]} />
    <CalculationProgramLink method="mdm" programSteps={scaleStep.programSteps} />
    <MDMScaleCalculation values={model.pseudoScales} beta={model.finalSlice.beta} gamma={model.finalSlice.gamma}
      eta={model.finalSlice.eta!} total={model.scaleSum} rankMethod={model.rankMethod} />
  </div>
}
