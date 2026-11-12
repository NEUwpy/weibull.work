'use client'

import { createContext, useContext, useMemo, type ReactNode } from 'react'
import type { DataSource } from '@/lib/weibull'
import type { CalculatorParameters } from '@/lib/calculator-state'
import { readCalculationTrace, readPowerScaleCalculation, formatCalculationNumber as number } from '@/lib/calculation-trace'
import type { FlowChartTarget } from '@/lib/method-flow'
import { ProcessSampleChart } from '@/components/shared/charts/ProcessSampleChart'
import { ProcessValueTable } from '@/components/shared/charts/ProcessValueTable'
import { BatchResultTable } from '@/components/calculator/BatchResultTable'

interface BatchContext {
  methodId: string; sources: DataSource[]; activeIndex: number; onSelect: (index: number) => void
  origin?: CalculatorParameters
  records: { source: DataSource; index: number; trace: NonNullable<ReturnType<typeof readCalculationTrace>['trace']> }[]
}
const Context = createContext<BatchContext | null>(null)
export const useCalculationBatch = () => useContext(Context)

export function CalculationBatch({ methodId, sources, activeIndex, onSelect, origin, children }: {
  methodId: string; sources?: DataSource[]; activeIndex: number; onSelect: (index: number) => void
  origin?: CalculatorParameters; children: ReactNode
}) {
  const value = useMemo<BatchContext | null>(() => !sources || sources.length < 2 ? null : ({
    methodId, sources, activeIndex, onSelect,
    origin: origin && sources.every(source => source.generatedFrom?.beta === origin.beta && source.generatedFrom?.eta === origin.eta
      && source.generatedFrom?.gamma === origin.gamma) ? origin : undefined,
    records: sources.flatMap((source, index) => {
      const { trace } = readCalculationTrace(source.calculation, methodId)
      return trace ? [{ source, index, trace }] : []
    }),
  }), [methodId, sources, activeIndex, onSelect, origin])
  return <Context.Provider value={value}>{children}</Context.Provider>
}

export function BatchStepFigure({ target, children }: { target?: FlowChartTarget; children: ReactNode }) {
  const batch = useCalculationBatch()
  if (!batch) return children
  if (target === 'samples') return <div className="space-y-3">
    <ProcessSampleChart runs={batch.sources.map((source, index) => ({ id: index + 1, sample: source.data.map(point => point.value) }))}
      trueGamma={batch.origin?.gamma} selectedRun={batch.activeIndex + 1} onSelect={id => batch.onSelect(id - 1)} />
    {children && <details><summary className="cursor-pointer text-sm text-slate-600">当前组的样本准备</summary><div className="mt-3">{children}</div></details>}
  </div>
  if (target === 'result') return <div className="h-96">
    <BatchResultTable sources={batch.sources} activeIndex={batch.activeIndex} onSelect={batch.onSelect} />
  </div>
  if (target === 'scale' && batch.methodId !== 'mdm') return <div className="space-y-4">
    <div className="max-h-80 overflow-y-auto">
      <ProcessValueTable label="各组尺度计算" minColumnWidth={340}
        columns={[{ label: '组' }, { label: '样本数', align: 'right' }, { label: '幂次合计', align: 'right' }, { label: '尺度 η̂', align: 'right' }]}
        rows={batch.sources.map((source, index) => {
          const trace = batch.records.find(record => record.index === index)?.trace
          const scale = trace && readPowerScaleCalculation(trace)
          return [<button key={source.id} type="button" className="text-blue-700" onClick={() => batch.onSelect(index)}>{index + 1}</button>,
            source.data.length, scale?.use_scaled ? number(scale.scaled_sum) : number(scale?.power_sum), number(source.result?.eta)]
        })} />
    </div>
    {children && <details><summary className="cursor-pointer text-sm text-slate-600">当前组的尺度计算</summary><div className="mt-3">{children}</div></details>}
  </div>
  return children
}
