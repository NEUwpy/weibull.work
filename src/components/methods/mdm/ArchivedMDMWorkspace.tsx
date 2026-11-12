'use client'

import { useEffect, useMemo, useState } from 'react'
import { CalculationWorkspace } from '../CalculationWorkspace'
import { GradientGammaChart } from './charts/GradientGammaChart'
import { MDMScaleCalculation, MDMScaleValues } from './visualizers/MDMScaleCalculation'
import { ProcessChart } from '@/components/shared/charts/CalculationProcessChart'
import { ProcessSampleChart } from '@/components/shared/charts/ProcessSampleChart'
import { ProcessValueTable } from '@/components/shared/charts/ProcessValueTable'
import { formatCalculationNumber as number, type CalculationPoint, type CalculationSeries } from '@/lib/calculation-trace'
import type { FlowChartTarget } from '@/lib/method-flow'
import type { ArchivedMDMProcess, ArchivedMDMRun, ArchivedMDMTrace, WorkbookProcessSelection } from '@/lib/monte-carlo'
import type { MethodFlow } from '@/lib/method-flow'
import { useCalculationBatch } from '../CalculationBatch'

function adoptedShape(run: ArchivedMDMRun) {
  return { x: run.beta, y: run.trace.shape.find(([beta]) => beta === run.beta)![1] }
}

function batchSeries(runs: ArchivedMDMRun[], points: (run: ArchivedMDMRun) => CalculationPoint[]): CalculationSeries[] {
  return runs.map(run => ({ id: String(run.id), label: '第 ' + run.id + ' 次', kind: 'line', role: 'solver', points: points(run) }))
}

const runColumn = { label: '重复' }
const numeric = (label: string) => ({ label, align: 'right' as const })

function ConditionalShape({ selection, run, index }: {
  selection: WorkbookProcessSelection; run: ArchivedMDMRun; index: number
}) {
  const [open, setOpen] = useState(false)
  const [curves, setCurves] = useState<ArchivedMDMTrace['shape'][]>()
  const [error, setError] = useState('')
  const { id, n, delta } = selection
  useEffect(() => {
    if (!open || curves || run.trace.trialShapes) return
    const controller = new AbortController()
    const query = new URLSearchParams({ n: String(n), delta: String(delta), trialRun: String(run.id) })
    setError('')
    fetch('/api/monte-carlo/' + encodeURIComponent(id) + '/process?' + query, { signal: controller.signal })
      .then(async response => {
        const result = await response.json()
        if (!response.ok) throw new Error(result.error || '形状试算点读取失败')
        if (!controller.signal.aborted) setCurves(result)
      })
      .catch(cause => {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : '形状试算点读取失败')
      })
    return () => controller.abort()
  }, [open, curves, id, n, delta, run.id, run.trace.trialShapes])

  const [gamma, sigma, beta] = run.trace.profile[index]
  const points = run.trace.trialShapes?.[index] ?? curves?.[index]
  return <details onToggle={event => setOpen(event.currentTarget.open)}>
    <summary className="cursor-pointer text-sm text-slate-600">查看该位置的形状试算</summary>
    {open && (points ? <ProcessChart workspacePlot figureOnly initiallyFocused={false} showYAxisLabel
      chart={{ id: 'archived-conditional-shape', title: '试算位置 γ = ' + number(gamma),
        x: { key: 'x', label: '形状 β' }, y: { key: 'y', label: '标准差 σ_η' },
        series: [{ id: 'evaluations', kind: 'line', role: 'solver', label: '有界优化计算点', points: points.map(([x, y]) => ({ x, y })) }],
        selected: [{ x: beta, y: sigma, label: '条件最小点' }] }} />
      : <p className="mt-2 text-sm text-slate-600" role={error ? 'alert' : 'status'}>{error || '正在读取试算点…'}</p>)}
  </details>
}

export function ArchivedMDMWorkspace({ process, selectedRun, onSelect }: {
  process: Omit<ArchivedMDMProcess, 'flow'> & { flow?: MethodFlow }; selectedRun: number | null; onSelect: (id: number | null) => void
}) {
  const batch = useCalculationBatch()
  const { runs } = process
  const { delta } = process.selection
  const [trueBeta, trueEta, trueGamma] = process.truth
  const selected = runs.find(run => run.id === selectedRun)
  const n = selected?.sample.length ?? process.selection.n
  const mixedSampleSizes = runs.some(run => run.sample.length !== n)
  const shownDelta = selected?.offset ?? delta
  const knownTruth = process.truth.length === 3
  const solverLabel = (run?: ArchivedMDMRun) => !run && batch ? '位置判据' : run?.branch === 'zero' ? '零位置'
    : run?.branch === 'extrapolated' ? '右端回退' : run?.solver === 'linear_interpolation' ? '线性插值' : 'Brent 求根'
  const activeId = selected && String(selected.id)
  const [trial, setTrial] = useState<{ id: number; index: number }>()
  const trialIndex = !selected ? 0 : trial?.id === selected.id ? trial.index
    : Math.max(0, selected.trace.profile.findLastIndex(([gamma]) => gamma <= selected.gamma))
  const trialPoint = selected?.trace.profile[trialIndex]
  const pseudoScales = selected?.trace.pseudoScales.map(([denominator, eta], index) => {
    const observation = selected.sample[index]
    const rank = selected.sampleRanks?.[index] ?? (index + 1 - .3) / (n + .4)
    return { observation, rank, rank_transform: -Math.log(1 - rank), distance: observation - selected.gamma, denominator, eta }
  }) ?? []
  const plots = useMemo(() => ({
    profile: batchSeries(runs, run => run.trace.profile.map(([x, y]) => ({ x, y }))),
    shape: batchSeries(runs, run => run.trace.shape.map(([x, y]) => ({ x, y }))),
    adopted: runs.map(adoptedShape),
  }), [runs])
  const domain = useMemo(() => {
    let maxGamma = knownTruth ? trueGamma : 0, minGradient = delta, maxGradient = delta
    for (const run of runs) {
      maxGamma = Math.max(maxGamma, run.gamma)
      for (const point of run.curve) {
        maxGamma = Math.max(maxGamma, point.gamma)
        minGradient = Math.min(minGradient, point.gradient)
        maxGradient = Math.max(maxGradient, point.gradient)
      }
    }
    const padding = (maxGradient - minGradient) * .05
    return { x: [0, maxGamma] as [number, number], y: [minGradient - padding, maxGradient + padding] as [number, number] }
  }, [runs, trueGamma, delta])

  // Draw the active trace after the background repetitions.
  const orderedRuns = selected ? [...runs.filter(run => run !== selected), selected] : runs
  function plot(id: string, title: string, x: string, y: string, series: CalculationSeries[], label: string,
    point?: CalculationPoint, showAdopted = false) {
    const active = series.find(item => item.id === activeId)
    const ordered = active ? [...series.filter(item => item !== active), active] : series
    return <ProcessChart workspacePlot figureOnly showYAxisLabel
      overlay={{ activeId, label, adoptedLabel: showAdopted ? '采纳形状' : point ? '查看的试算点' : undefined }}
      chart={{ id, title, x: { key: 'x', label: x }, y: { key: 'y', label: y }, selected: point ? [point] : undefined,
        series: showAdopted ? [...ordered, { id: 'adopted', label: '采纳形状', kind: 'scatter',
          role: 'candidate', points: plots.adopted }] : ordered }} />
  }

  function runButton(run: ArchivedMDMRun) {
    return <button type="button" aria-pressed={selected === run} aria-label={'查看第 ' + run.id + ' 次计算'}
      className={selected === run ? 'font-semibold text-blue-700' : 'text-slate-700 hover:text-blue-700'}
      onClick={() => onSelect(selected === run && !batch ? null : run.id)}>{run.id}</button>
  }

  function figure(target?: FlowChartTarget) {
    switch (target) {
      case 'samples':
        return <div className="space-y-3">
          {!batch && <ProcessSampleChart runs={runs} trueGamma={knownTruth ? trueGamma : undefined} selectedRun={selectedRun} onSelect={onSelect} />}
          {selected && <details open>
            <summary className="cursor-pointer text-sm text-slate-600">第 {selected.id} 次样本和经验概率</summary>
            <div className="mt-2 max-h-80 overflow-y-auto">
              <ProcessValueTable label="排序样本与经验概率" columns={[{ label: 'i' }, numeric('tᵢ'), numeric('F(tᵢ)'), numeric('xᵢ')]}
                rows={pseudoScales.map((value, index) => [index + 1, number(value.observation), number(value.rank), number(value.rank_transform)])} />
            </div>
          </details>}
        </div>
      case 'trial':
        return <div className="space-y-3">
          {plot('archive-profile', '各次位置试算', '位置 γ', '最小标准差 σₘᵢₙ', plots.profile, '各次最小标准差',
            trialPoint && { x: trialPoint[0], y: trialPoint[1], label: ' ' })}
          {selected && trialPoint && <>
            <label className="block text-sm text-slate-600">
              试算位置 γ = {number(trialPoint[0])}
              <input type="range" min={0} max={selected.trace.profile.length - 1} step={1} value={trialIndex}
                aria-label="查看本次实际试算位置" onChange={event => setTrial({ id: selected.id, index: Number(event.target.value) })}
                className="block w-full accent-blue-600" />
            </label>
            <ConditionalShape key={process.selection.id + '-' + selected.id} selection={process.selection} run={selected} index={trialIndex} />
          </>}
        </div>
      case 'location':
        return <div className="space-y-3">
          <GradientGammaChart curves={orderedRuns.map(run => ({ id: run.id, data: run.curve, name: '第 ' + run.id + ' 次',
            color: run === selected ? '#2563eb' : '#64748b', opacity: run === selected ? 1 : .22, strokeWidth: run === selected ? 2.5 : 1 }))}
            domain={domain} overlayMode workspacePlot interpolation="linear" offsetReference={shownDelta} calculatedPoints={selected?.curve}
            adoptedLocations={runs.map(run => ({ id: run.id, gamma: run.gamma, selected: run === selected }))} onSelectLocation={onSelect}
            gammaReferenceLines={knownTruth ? [{ gamma: trueGamma, label: 'γ 真值 = ' + number(trueGamma), color: '#398362' }] : []} />
          <p className="text-sm text-slate-600">各组实际梯度曲线 · 图底短线为采纳位置</p>
        </div>
      case 'shape':
        return plot('archive-shape', '固定各次采纳位置后的形状寻优', '形状 β', '标准差 σ_η', plots.shape,
          '各次回代的实际求值', selected && { ...adoptedShape(selected), label: ' ' }, true)
      case 'scale':
        return selected && !batch ? <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-600">
            <span>第 {selected.id} 次 · η̂ = {number(selected.eta)}</span>
            <button type="button" onClick={() => onSelect(null)} className="text-blue-700 hover:underline">查看整组</button>
          </div>
          <MDMScaleValues values={pseudoScales} total={selected.trace.scaleSum} />
        </div> : <div className="space-y-3"><div className="max-h-80 overflow-y-auto">
          <ProcessValueTable label="各次伪尺度的合计与均值" minColumnWidth={300}
            columns={[runColumn, numeric('Σηᵢ'), numeric('n'), numeric('均值 η̂')]}
            rows={runs.map(run => [runButton(run), number(run.trace.scaleSum), run.sample.length, number(run.eta)])} />
        </div>{selected && <details><summary className="cursor-pointer text-sm text-slate-600">第 {selected.id} 组伪尺度</summary>
          <MDMScaleValues values={pseudoScales} total={selected.trace.scaleSum} /></details>}</div>
      case 'result':
        return <div className="max-h-96 overflow-y-auto">
          <ProcessValueTable label="各次估计结果" minColumnWidth={465}
            columns={[runColumn, numeric('位置 γ̂'), numeric('形状 β̂'), numeric('尺度 η̂'), numeric('R²')]}
            rows={runs.map(run => [runButton(run), number(run.gamma), number(run.beta), number(run.eta), number(run.rSquared)])} />
        </div>
    }
  }

  function details(target?: FlowChartTarget) {
    if (target === 'samples') return <p>{runs.length} 次 · {mixedSampleSizes ? '各组样本量不同' : '每次 ' + n + ' 个样本'} · {selected?.rankMethod === 'exact' ? '精确中位秩' : 'Bernard 近似秩'}</p>
    if (target === 'trial') return trialPoint
      ? <p className="tabular-nums">γ = {number(trialPoint[0])}，σₘᵢₙ = {number(trialPoint[1])}，β* = {number(trialPoint[2])}</p>
      : <p>每条曲线用该次实际位置网格的最小标准差连线。</p>
    if (target === 'location') return <div className="space-y-2 tabular-nums">
      <p>{solverLabel(selected)} · δ = {number(shownDelta)}</p>
      {selected && <>
        {selected.branch !== 'zero' && selected.branch !== 'extrapolated' && <p data-archived-run={selected.id}>搜索区间 [{number(selected.bracket[0])}, {number(selected.bracket[1])}]</p>}
        <p>γ̂ = {number(selected.gamma)}</p>
      </>}
    </div>
    if (target === 'shape' && selected) return <p className="tabular-nums">固定 γ̂ = {number(selected.gamma)}，采纳 β̂ = {number(selected.beta)}</p>
    if (target === 'scale' && selected) return <MDMScaleCalculation values={pseudoScales}
      beta={selected.beta} gamma={selected.gamma} eta={selected.eta} total={selected.trace.scaleSum} />
    if (target === 'result') return knownTruth ? <p>真值 γ = {number(trueGamma)}，β = {number(trueBeta)}，η = {number(trueEta)}。</p> : null
  }

  return <div data-archived-process={process.selection.id}>
    <CalculationWorkspace methodId="mdm" recordedFlow={process.flow} ready
      workflowBranch={selected?.branch ?? 'ready'}
      formulaVariant={(_, target) => target === 'samples' ? selected?.rankMethod : target === 'location' ? selected?.branch ?? 'ready' : undefined}
      workflowValues={{ count: n, offset: shownDelta }} values={{ offset: number(shownDelta), n: number(n),
        found_gamma: number(selected?.gamma), found_beta: number(selected?.beta), found_eta: number(selected?.eta) }}
      notice={<div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm text-slate-600">
        <span>{process.title} · {mixedSampleSizes ? '多种样本量' : 'n=' + n} · δ={shownDelta.toFixed(2)} · {runs.length} 次</span>
        <label className="flex items-center gap-2">查看
          <select aria-label={batch ? '查看当前组' : '查看归档重复'} className="rounded-md border border-slate-200 bg-white px-2 py-1"
            value={selectedRun ?? ''} onChange={event => onSelect(event.target.value ? Number(event.target.value) : null)}>
            {!batch && <option value="">整组</option>}
            {runs.map(run => <option key={run.id} value={run.id}>第 {run.id} 次</option>)}
          </select>
        </label>
      </div>}
      renderFigure={(_, target) => figure(target)}
      renderDetails={(_, target) => <div className="text-sm text-slate-600">{details(target)}</div>} />
  </div>
}
