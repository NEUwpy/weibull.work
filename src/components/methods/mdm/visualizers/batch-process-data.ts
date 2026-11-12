import type { DataSource } from '@/lib/weibull'
import type { CalculatorParameters } from '@/lib/calculator-state'
import type { ArchivedMDMProcess, ArchivedMDMRun } from '@/lib/monte-carlo'
import { readCalculationTrace } from '@/lib/calculation-trace'
import { mdmProcessData } from './process-data'

export function liveMDMBatch(sources: DataSource[], origin: CalculatorParameters | undefined, offset: number) {
  const runs = sources.flatMap((source, index): ArchivedMDMRun[] => {
    const { trace } = readCalculationTrace(source.calculation, 'mdm')
    const model = trace && mdmProcessData(source.traceData, trace)
    const result = source.result
    if (!trace || !model || !result || result.rSquared === null || model.scaleSum === null ||
        model.pseudoScales.length !== source.data.length || model.pseudoScales.some(point => point.denominator === undefined) ||
        result.beta !== model.finalSlice.beta || result.gamma !== model.finalSlice.gamma || result.eta !== model.finalSlice.eta) return []
    const branch = trace.selection.approximate === true ? 'extrapolated'
      : trace.selection.strategy === 'truncated_at_zero' ? 'zero' : 'ready'
    const bracket: [number, number] = model.interpolation
      ? [model.interpolation.left.gamma, model.interpolation.right.gamma] : [result.gamma, result.gamma]
    return [{
      id: index + 1, sample: model.pseudoScales.map(point => point.observation),
      beta: model.finalSlice.beta, eta: model.finalSlice.eta!, gamma: model.finalSlice.gamma,
      rSquared: result.rSquared, solver: String(trace.selection.solver ?? ''), branch, offset: model.offset, bracket,
      sampleRanks: model.pseudoScales.map(point => point.rank), rankMethod: model.rankMethod ?? undefined,
      curve: model.gradients.map(({ gamma, gradient }) => ({ gamma, gradient })),
      trace: {
        profile: model.slices.map(slice => [slice.gamma, slice.sigma, slice.beta]),
        shape: model.finalSlice.points.map(point => [point.beta, point.sigma]),
        trialShapes: model.slices.map(slice => slice.points.map(point => [point.beta, point.sigma])),
        pseudoScales: model.pseudoScales.map(point => [point.denominator!, point.eta]), scaleSum: model.scaleSum,
      },
    }]
  })
  return {
    selection: { id: sources[0]?.groupId ?? sources[0]?.id ?? 'current', n: sources[0]?.data.length ?? 0, delta: offset },
    title: origin ? 'W(' + [origin.beta, origin.eta, origin.gamma].join(',') + ')' : '本批样本',
    truth: origin ? [origin.beta, origin.eta, origin.gamma] : [], runs,
  } satisfies Omit<ArchivedMDMProcess, 'flow'>
}
