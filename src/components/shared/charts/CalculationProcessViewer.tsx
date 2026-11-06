"use client"

import { Check, Info } from 'lucide-react'
import { ProcessChart, ProcessFormula } from './CalculationProcessChart'
import { MethodCalculationSteps } from '@/components/methods/MethodCalculationSteps'
import { ProcessDetails } from '@/components/methods/CalculationSteps'
import {
  type CalculationChart,
  formatCalculationNumber, readCalculationTrace,
} from '@/lib/calculation-trace'

interface CalculationProcessViewerProps {
  calculation: unknown
  methodId?: string
  stale?: boolean
  isUpdating?: boolean
}

function RootComparison({ chart }: { chart: CalculationChart }) {
  const points = chart.series.flatMap(series => series.points)
  return <section className="min-w-0 rounded-xl border border-slate-200/70 px-4 py-3">
    <h3 title={chart.description} className="text-base font-semibold text-slate-800">{chart.title}</h3>
    {chart.formula && <ProcessFormula expression={chart.formula} />}
    <div className="mt-2 overflow-x-auto"><table className="w-full text-right text-base tabular-nums">
      <thead className="text-slate-500"><tr>{['候选','β','γ','T₁','T₂','T₁²+T₂²'].map(label=><th key={label} className="whitespace-nowrap px-2 py-2 font-medium">{label}</th>)}</tr></thead>
      <tbody>{points.map((point,index)=><tr key={index} className={chart.selected?.some(p=>p.x===point.x && p.y===point.y) ? 'bg-amber-50/70 text-amber-900' : 'text-slate-700'}>
        <td className="whitespace-nowrap px-2 py-2">{chart.selected?.some(p=>p.x===point.x && p.y===point.y) ? '最终选择' : index+1}{point.candidate_kind==='boundary_residual_tolerance' ? '（边界近似）' : ''}</td>
        {[point.beta,point.gamma,point.t1,point.t2,point.y].map((value,i)=><td key={i} className="px-2 py-2">{formatCalculationNumber(value)}</td>)}
      </tr>)}</tbody>
    </table></div>
  </section>
}

export function CalculationProcessViewer({ calculation, methodId, stale = false, isUpdating = false }: CalculationProcessViewerProps) {
  const { trace, error } = readCalculationTrace(calculation, methodId)
  if (!trace) {
    const message = error === 'method_mismatch'
      ? '这份运行记录属于其他方法，请重新计算。'
      : error === 'invalid'
        ? '本次计算记录不完整，暂时无法展示过程图。请重新计算。'
        : '这份结果尚无真实计算过程记录，请重新计算后查看。'
    return <div role="status" className="flex items-start gap-2 rounded-xl bg-slate-100/70 px-4 py-4 text-base leading-relaxed text-slate-600"><Info size={19} className="mt-0.5 shrink-0" />{message}</div>
  }

  const runId = trace.run && typeof trace.run === 'object' && 'id' in trace.run ? String(trace.run.id) : undefined
  const failed = typeof trace.selection.status === 'string' && trace.selection.status !== 'ok'
  const showSelection = failed || trace.selection.approximate === true || !trace.recovery?.length
  const mainCharts = trace.charts.filter(chart => chart.id !== 'candidate-residuals')
  const viewKey = runId ?? `${trace.method}-${trace.selection.beta}-${trace.selection.gamma}`
  const stepped = ['mle', 'wmle', 'mmle', 'lse', 'lre', 'mm'].includes(trace.method)

  return (
    <div className="min-w-0 space-y-4" data-calculation-method={trace.method}>
      {stale && <p role="status" className="rounded-xl bg-amber-50 px-4 py-3 text-base text-amber-800">{isUpdating ? '正在按新设置重新计算；下方为上一次计算的记录。' : '设置已改变；下方仍是上一次计算的记录，请重新计算。'}</p>}
      {showSelection && <div className={`flex items-start gap-3 rounded-xl px-4 py-4 ${failed || trace.selection.approximate === true ? 'bg-amber-50' : 'bg-slate-100/70'}`}>
        {failed ? <Info size={20} className="mt-0.5 shrink-0 text-amber-700" /> : <Check size={20} className="mt-0.5 shrink-0 text-amber-700" />}
        <div className="min-w-0">
          <h2 className={`text-lg font-semibold leading-snug ${failed ? 'text-amber-900' : 'text-slate-800'}`}>{failed ? '未得到可采纳结果' : trace.selection.approximate === true ? '近似结果' : '本次估计'}</h2>
          {(failed || trace.selection.approximate === true) && <p className="mt-1 text-base leading-relaxed text-slate-700">{trace.selection.description}</p>}
          <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-base tabular-nums text-slate-800">
            {(['beta', 'eta', 'gamma'] as const).map((key, index) => trace.selection[key] !== undefined && trace.selection[key] !== null && (
              <div key={key} className="flex items-baseline gap-1"><dt className="text-slate-500">{['β̂', 'η̂', 'γ̂'][index]} =</dt><dd className="font-semibold">{formatCalculationNumber(trace.selection[key])}</dd></div>
            ))}
          </dl>
        </div>
      </div>}
      {stepped ? <MethodCalculationSteps key={viewKey} trace={trace} />
        : <div className={`grid min-w-0 grid-cols-1 items-start gap-4 ${mainCharts.length === 3 ? 'xl:grid-cols-3' : 'xl:grid-cols-2'}`}>
        {mainCharts.map(chart => <ProcessChart key={`${runId ?? ''}-${chart.id}`} chart={chart} />)}
      </div>}
      {!stepped && !!trace.recovery?.length && <section aria-label="由判据确定参数" className="grid min-w-0 grid-cols-1 gap-0 rounded-2xl bg-slate-100/60 sm:grid-cols-3">
        {trace.recovery.map((step, index) => <div key={step.title} className="min-w-0 px-4 py-4 sm:px-5">
          <h3 className="text-base font-semibold text-slate-800"><span className="mr-2 text-slate-400">{index + 1}</span>{step.title}</h3>
          <ProcessFormula expression={step.formula} />
          <dl className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-base tabular-nums">
            {step.values.map(item => <div key={item.label} className="flex gap-1"><dt className="text-slate-500">{item.label} =</dt><dd className="font-medium text-slate-800">{formatCalculationNumber(item.value)}</dd></div>)}
          </dl>
        </div>)}
      </section>}
      {trace.charts.filter(chart=>chart.id==='candidate-residuals').map(chart=><ProcessDetails key={chart.id} title="查看候选数值"><RootComparison chart={chart} /></ProcessDetails>)}
    </div>
  )
}
