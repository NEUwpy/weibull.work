import { summarizeStandardErrors } from './metrics'
import type { MethodComparisonResult } from './method-comparison-loader'
import type { AnalysisParameter } from './simulation-analysis'

type ReadyResult = Extract<MethodComparisonResult, { status: 'ready' }>
const parameters = ['beta', 'eta', 'gamma'] as const

interface ParameterSummary {
  values: number[]
  truth: number | null
  mean: number | null
  bias: number | null
  sd: number | null
}

export interface MethodComparisonStatistics {
  count: number
  includedCount: number
  failures: number | null
  parameters: Record<AnalysisParameter, ParameterSummary>
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

export function summarizeMethodComparison(result: ReadyResult): MethodComparisonStatistics {
  const simulation = result.source === 'simulation' ? result : null
  const included = simulation
    ? simulation.rows.filter(row => row.status === 'success')
    : result.rows.filter(row => parameters.every(key => isFiniteNumber(row[`est_${key}`])))
  const first = result.rows[0]

  function summarize(key: AnalysisParameter): ParameterSummary {
    const truthValue = key === 'gamma' ? first?.gamma : first?.[`${key}_true`]
    const truth = isFiniteNumber(truthValue) ? truthValue : null
    const values = included.map(row => row[`est_${key}`]).filter(isFiniteNumber)
    const mean = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null
    const summary = simulation
      ? simulation.metrics.param_standard?.[key].absolute
      : summarizeStandardErrors(truth === null ? values : values.map(value => value - truth))
    return {
      values, truth, mean,
      bias: truth === null ? null : summary?.bias ?? null,
      sd: summary?.sd ?? null,
    }
  }

  return {
    count: simulation?.metrics.n_total ?? result.rows.length,
    includedCount: simulation?.metrics.n_valid ?? included.length,
    failures: simulation?.metrics.n_failure ?? null,
    parameters: { beta: summarize('beta'), eta: summarize('eta'), gamma: summarize('gamma') },
  }
}
