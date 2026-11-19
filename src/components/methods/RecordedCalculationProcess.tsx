"use client"

import { useEffect, useState } from 'react'
import { ProcessEquation } from '@/components/shared/charts/ProcessEquation'
import { ProcessChart } from '@/components/shared/charts/CalculationProcessChart'
import { ProcessValueTable } from '@/components/shared/charts/ProcessValueTable'
import { formatCalculationNumber as number, readCalculationTrace, readPowerScaleCalculation, type CalculationChart, type CalculationTrace } from '@/lib/calculation-trace'
import type { FlowChartTarget } from '@/lib/method-flow'
import { CalculationWorkspace } from './CalculationWorkspace'
import { LikelihoodProcessViewer, ModifiedLikelihoodSample, WeightedLikelihoodWeights } from './LikelihoodProcessViewer'
import { MomentProcessViewer } from './MomentProcessViewer'
import { PowerScaleCalculation } from './PowerScaleCalculation'
import { ProcessDetails } from './ProcessDetails'
import { RegressionProcessViewer } from './RegressionProcessViewer'
import { recordedDetails, recordedRun, recordedStepValues, readRegressionProcess, readWeightedProcess, readModifiedProcess } from './recorded-process-data'

export default function RecordedCalculationProcess({ methodId, calculation, rSquared, updating }: {
  methodId: string
  calculation: unknown
  rSquared?: number | null
  updating?: boolean
}) {
  const { trace, error } = readCalculationTrace(calculation, methodId)
  const [regressionIndex, setRegressionIndex] = useState<number | null>(null)
  const [weightedIndex, setWeightedIndex] = useState<number | null>(null)
  const [iterationIndex, setIterationIndex] = useState<number | null>(null)
  useEffect(() => { setRegressionIndex(null); setWeightedIndex(null); setIterationIndex(null) }, [calculation])
  const readers = { regressionIndex, setRegressionIndex, weightedIndex, setWeightedIndex, iterationIndex, setIterationIndex }
  const selection = trace?.selection
  const branch = selection?.approximate === true ? 'extrapolated' : selection && selection.status !== 'ok' ? 'failed' : 'ready'
  const details = trace ? recordedDetails(trace) : undefined
  const run = trace ? recordedRun(trace) : undefined
  const samples = run?.observations ?? []

  return <CalculationWorkspace methodId={methodId} ready={!!trace} updating={updating} revision={trace} workflowBranch={branch}
    values={(_, target) => trace ? recordedStepValues(trace, target, rSquared,
      readRegressionProcess(trace, regressionIndex).view, readWeightedProcess(trace, weightedIndex).frame,
      readModifiedProcess(trace, iterationIndex).iteration) : {}}
    formulaVariant={(_, target) => {
      if (methodId === 'mm' && target === 'adjustment' && selection?.status === 'ok') return String(details?.location_adjustment ?? 'unchanged')
      if (methodId === 'wmle' && target === 'location') return branch
    }}
    notice={trace && branch !== 'ready'
      ? <p role="status" className="py-3 text-sm text-amber-800">{branch === 'extrapolated' ? '边界近似。' : '未得到可采纳结果。'}{selection?.description}</p>
      : calculation && error ? <p role="alert" className="py-3 text-sm text-amber-800">
        {error === 'method_mismatch' ? '这份计算记录属于其他方法。' : '这份记录缺少本次求解明细，请重新计算后查看。'}
      </p> : null}
    emptyContent={!calculation && <p className="py-6 text-slate-500">输入样本并计算后，即可查看过程图。源码可直接切换查看。</p>}
    renderFigure={(_, target) => trace ? recordedStepFigure(trace, samples, readers, rSquared, target) : null}
    renderDetails={(_, target) => trace && <RecordedStepDetails key={run?.id} trace={trace} rSquared={rSquared} target={target} readers={readers} />} />
}

type Readers = {
  regressionIndex: number | null; setRegressionIndex: (index: number | null) => void
  weightedIndex: number | null; setWeightedIndex: (index: number | null) => void
  iterationIndex: number | null; setIterationIndex: (index: number | null) => void
}

function recordedStepFigure(trace: CalculationTrace, samples: number[], readers: Readers, rSquared?: number | null, target?: FlowChartTarget) {
  const runId = (trace.run as { id?: string } | undefined)?.id
  const chart = (id: string) => trace.charts.find(item => item.id === id)
  const plot = (id: string) => {
    const value = chart(id)
    return value && <div>
      <ProcessChart chart={value} figureOnly workspacePlot showYAxisLabel initiallyFocused={false} />
    </div>
  }
  const { selection } = trace
  if (target === 'samples') return samples.length > 0 && <div className="space-y-4">
    <ProcessValueTable label="排序样本" minColumnWidth={260}
      columns={[{ label: '序号', math: 'i' }, { label: '观测值', math: 't_{(i)}', align: 'right' }, ...(trace.method === 'wmle' ? [{ label: '归一化样本', math: 'z_i', align: 'right' as const }] : [])]}
      rows={samples.map((observation, index) => [index + 1, number(observation), ...(trace.method === 'wmle'
        ? [number(recordedDetails(trace).prepared_samples?.[index]?.normalized)] : [])])} />
  </div>
  if (target === 'result') return <ProcessValueTable label="估计结果" minColumnWidth={260}
    columns={[{ label: '计算量' }, { label: '本次结果', align: 'right' }]}
    rows={[
      ['β̂', number(selection.beta)], ['η̂', number(selection.eta)], ['γ̂', number(selection.gamma)],
      ...(trace.method === 'mmle' ? [] : [['R²', number(rSquared)]]),
      ['求解状态', selection.approximate === true ? '边界近似' : selection.status === 'ok' ? '成功' : '未得到可采纳结果'],
    ]} />

  if (selection.status !== 'ok') {
    const d = recordedDetails(trace)
    if (trace.method === 'mm' && [d.m1, d.m2, d.m4].every(value => typeof value === 'number' && Number.isFinite(value))) {
      if (target === 'moments') return <ProcessValueTable label="本次已计算的样本矩"
        columns={[{ label: '样本矩' }, { label: '实际值', align: 'right' }]}
        rows={[[1, d.m1], [2, d.m2], [4, d.m4]].map(([k, value]) => ['m̄' + k, number(value)])} />
      if (target === 'estimate') return <div className="space-y-3">
        <p className="text-slate-600">本次已得到三个样本矩，但它们不满足显式解的可采纳条件，参数求解在此停止。</p>
        <ProcessEquation expression={String.raw`(${math(d.m1)}-${math(d.m2)})>(${math(d.m2)}-${math(d.m4)})>0\quad\text{不成立}`} />
      </div>
    }
    return <p className="text-slate-600">本步没有可显示的后续求解记录，未返回可采纳参数。</p>
  }

  switch (trace.method) {
    case 'wmle':
      if (target === 'trial' || target === 'location') return <LikelihoodProcessViewer trace={trace} target={target}
        index={readers.weightedIndex} onIndexChange={readers.setWeightedIndex} />
      if (target === 'comparison') {
        const candidates = chart('candidate-residuals')
        return <div className="space-y-4">{candidates && <RootComparison chart={candidates} />}
          <ProcessDetails title="核对最终共同解的方程代入"><LikelihoodProcessViewer trace={trace} target="comparison"
            onIndexChange={readers.setWeightedIndex} /></ProcessDetails>
        </div>
      }
      if (target === 'scale') return <PowerScaleCalculation trace={trace} view="chart" />
      break
    case 'mmle':
      if (target === 'location') return <ModifiedLikelihoodSample trace={trace} />
      if (target === 'shape') return <LikelihoodProcessViewer trace={trace} index={readers.iterationIndex} onIndexChange={readers.setIterationIndex} />
      if (target === 'scale') return <PowerScaleCalculation trace={trace} view="chart" />
      break
    case 'lse':
    case 'lre':
      if (target === 'location' || target === 'regression' || target === 'transformation') return <RegressionProcessViewer
        key={runId + target} trace={trace} mode={target} viewIndex={readers.regressionIndex} onViewIndexChange={readers.setRegressionIndex} />
      break
    case 'mm':
      if (target === 'moments') return <MomentProcessViewer key={runId} trace={trace} />
      if (target === 'estimate') return <div className="space-y-4">{plot('moment-admissibility')}<MomentSubstitution trace={trace} target={target} /></div>
      if (target === 'comparison') return <MomentSubstitution trace={trace} target={target} />
      if (target === 'adjustment' && typeof selection.gamma === 'number') return <div className="space-y-4"><ProcessValueTable
        label="位置处理前后的参数" minColumnWidth={290}
        columns={['参数', '原值', '处理值'].map(label => ({ label, align: 'right' }))}
        rows={([['γ', 'gamma'], ['η', 'eta']] as const).map(([label, key]) => {
          const raw = selection.raw_estimate as Partial<Record<'gamma' | 'eta', number>> | undefined
          return [label, number(raw?.[key]), number(selection[key])]
        })} /><MomentSubstitution trace={trace} target={target} /></div>
  }
}

function RecordedStepDetails({ trace, rSquared, target, readers }: { trace: CalculationTrace; rSquared?: number | null; target?: FlowChartTarget; readers: Readers }) {
  const details = trace.details as Record<string, unknown> | undefined
  const { selection } = trace
  if (target === 'samples' && trace.method === 'wmle') return <WeightedLikelihoodWeights trace={trace} />
  if (target === 'result') {
    return <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 tabular-nums">
      <dt>形状 β̂</dt><dd>{number(selection.beta)}</dd>
      <dt>尺度 η̂</dt><dd>{number(selection.eta)}</dd>
      <dt>位置 γ̂</dt><dd>{number(selection.gamma)}</dd>
      {trace.method !== 'mmle' && <><dt>拟合优度 R²</dt><dd>{number(rSquared)}</dd></>}
    </dl>
  }
  if (target === 'scale' && (trace.method === 'wmle' || trace.method === 'mmle')) {
    return <PowerScaleCalculation trace={trace} view="details" />
  }
  if (target === 'location' && trace.method === 'mmle') {
    const scale = readPowerScaleCalculation(trace)
    return scale && <p>γ̂ = {number(scale.gamma)}。删去该一个观测，保留 {scale.count} 个样本。</p>
  }
  if (target === 'shape' && trace.method === 'mmle') {
    const { frame, iteration } = readModifiedProcess(trace, readers.iterationIndex)
    return <p>当前查看第 {String(frame?.iteration ?? 0)} 次迭代，{iteration ? '绝对步长为 ' + number(iteration.shape_step) : '尚未执行更新'}。停止容差为 {number(details?.shape_absolute_step_tolerance)}，最终 β̂ = {number(selection.beta)}。</p>
  }
  if (trace.method === 'wmle') {
    const frame = readWeightedProcess(trace, readers.weightedIndex).frame
    if (target === 'trial' && frame) return <p>当前试算 γ = {number(frame.gamma)}，对应 β*(γ) = {number(frame.beta)}，T₁ = {number(frame.t1)}。辅助曲线由同一方程补充求值，实际求解点单独标记。</p>
    if (target === 'location' && frame) return <p>同一试算位置的 T₂ = {number(frame.t2)}。通过残差检查的接受候选交给下一步核对。</p>
  }
  if (trace.method === 'lse' || trace.method === 'lre') {
    if (target === 'location' && typeof selection.gamma === 'number') { const view = readRegressionProcess(trace, readers.regressionIndex).view; return <p>当前查看 γ = {number(view?.gamma)}，{trace.method === 'lse' ? 'F' : 'ρ'} = {number(view?.criterion)}。本次采纳 γ̂ = {number(selection.gamma)}。</p> }
    if (target === 'regression' && details?.slope !== undefined) return <p>固定 γ̂ = {number(selection.gamma)}，截距 a = {number(details.intercept)}，斜率 b = {number(details.slope)}。得到 β̂ = {number(selection.beta)}，η̂ = {number(selection.eta)}。</p>
  }
  if (trace.method === 'mm') {
    const values = details?.formula_values as { d12: number; d24: number; minimum: number } | undefined
    const raw = details?.raw_estimate as { beta: number; eta: number; gamma: number } | undefined
    const location = details?.location_calculation as { alternative: number | null } | undefined
    if (target === 'estimate' && values && raw) return <p>本次矩差分别为 {number(values.d12)} 和 {number(values.d24)}。显式解为 β* = {number(raw.beta)}、γ* = {number(raw.gamma)}、η* = {number(raw.eta)}。</p>
    if (target === 'adjustment' && values && raw) return <p>最小观测 t₍₁₎ = {number(values.minimum)}，显式位置 γ* = {number(raw.gamma)}
      {typeof location?.alternative === 'number' ? '，替代位置 γ** = ' + number(location.alternative) : ''}。本次返回 β̂ = {number(selection.beta)}、γ̂ = {number(selection.gamma)}、η̂ = {number(selection.eta)}。</p>
    if (target === 'comparison' && details?.two_param_shape != null) return <p>两参数对照的形状为 {number(details.two_param_shape)}，尺度为 {number(details.two_param_scale)}。</p>
  }
}

function RootComparison({ chart }: { chart: CalculationChart }) {
  return <ProcessValueTable label="接受候选与最终选根" minColumnWidth={405}
    columns={['候选', '形状', '位置', '形状残差', '位置残差', '联合残差'].map((label, i) => ({ label, math: ['c', String.raw`\beta`, String.raw`\gamma`, 'T_1', 'T_2', 'Q'][i], align: 'right' }))}
    rows={chart.series.flatMap(series => series.points).map((point, index) => {
      const selected = chart.selected?.some(item => item.x === point.x && item.y === point.y)
      const label = String(selected ? '最终选择' : index + 1) + (point.candidate_kind === 'boundary_residual_tolerance' ? '（边界近似）' : '')
      return [label, ...[point.beta, point.gamma, point.t1, point.t2, point.y].map(number)]
    })} />
}

const math = (value: unknown) => number(value).replace(/e([+-]?\d+)/, String.raw`\times10^{$1}`)

function MomentSubstitution({ trace, target }: { trace: CalculationTrace; target: FlowChartTarget }) {
  const d = recordedDetails(trace), v = d.formula_values, raw = d.raw_estimate
  if (!v || !raw) return null
  if (target === 'estimate') return <div className="space-y-4" aria-label="样本矩代入显式三参数解">
    <ProcessEquation expression={String.raw`d_{12}=${math(v.d12)}>d_{24}=${math(v.d24)}>0`} />
    <ProcessEquation expression={String.raw`\beta^*=\frac{\ln2}{\ln(${math(v.d12)})-\ln(${math(v.d24)})}\approx\frac{\ln2}{${math(v.shape_denominator)}}\approx${math(raw.beta)}`} />
    <ProcessEquation expression={String.raw`\gamma^*=\frac{${math(d.m1)}\times${math(d.m4)}-${math(d.m2)}^2}{${math(d.m1)}+${math(d.m4)}-2\times${math(d.m2)}}\approx\frac{${math(v.location_numerator)}}{${math(v.location_denominator)}}\approx${math(raw.gamma)}`} />
    <ProcessEquation expression={String.raw`\eta^*=\frac{${math(d.m1)}-(${math(raw.gamma)})}{${math(v.gamma_function)}}\approx${math(raw.eta)}`} />
  </div>
  if (target === 'adjustment') return <div className="space-y-4" aria-label="位置处理后的尺度恢复">
    {d.location_adjustment === 'alternative_a_star_star' && <ProcessEquation expression={String.raw`\gamma^{**}=${math(v.minimum)}-\frac{${math(raw.eta)}\times${math(v.gamma_function)}}{${math(d.location_calculation?.sample_size_root)}}\approx${math(d.location_calculation?.alternative)}`} />}
    <ProcessEquation expression={String.raw`\hat\eta=\frac{${math(d.m1)}-${math(trace.selection.gamma)}}{${math(v.gamma_function)}}\approx${math(trace.selection.eta)}`} />
  </div>
  if (target === 'comparison') return <div className="space-y-4" aria-label="两参数矩估计对照">
    {d.two_param_shape != null && d.two_param_scale != null ? <>
      <ProcessEquation expression={String.raw`\beta_{2P}=\frac{\ln2}{\ln(${math(d.m1)})-\ln(${math(d.m2)})}\approx${math(d.two_param_shape)}`} />
      <ProcessEquation expression={String.raw`\eta_{2P}=\frac{${math(d.m1)}}{\Gamma(1+1/${math(d.two_param_shape)})}\approx${math(d.two_param_scale)}`} />
      <ProcessValueTable label="同一样本的两参数与三参数结果" minColumnWidth={320}
        columns={['参数', '2P', '3P'].map(label => ({ label, align: 'right' }))}
        rows={[
          ['β', number(d.two_param_shape), number(trace.selection.beta)],
          ['η', number(d.two_param_scale), number(trace.selection.eta)],
          ['γ', '0', number(trace.selection.gamma)],
        ]} />
    </> : <p role="status">本次样本未形成有限的两参数对照。</p>}
  </div>
  return null
}
