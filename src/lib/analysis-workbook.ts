import type { CalculatorParameters } from './calculator-state'
import { checkStatus } from './metrics'
import type { WorkbookCell, WorkbookGroup, WorkbookRun, WorkbookView } from './monte-carlo'
import type { DataSource } from './weibull'

interface AnalysisRun extends WorkbookRun {
  id: number
  observations: number[]
  estimates: [number | null, number | null, number | null]
}

function makeWorkbook(methodId: string, rows: AnalysisRun[], offset?: number) {
  const group: WorkbookGroup = {
    samples: rows.map(row => [row.id, ...row.observations]),
    resultRows: rows.map(row => [row.id, ...row.estimates]),
    blocks: [{
      method: methodId, label: methodId.toUpperCase(), delta: offset ?? null,
      column: 1, parameterLabels: ['β', 'η', 'γ'],
    }],
    sampleSheet: '样本数据',
    resultSheet: '估计结果',
  }
  const runs = new Map<WorkbookCell, WorkbookRun>(rows.map(row => [row.id, { status: row.status, error: row.error }]))
  return { group, runs }
}

export function samplingTruth(sources: DataSource[] | undefined): CalculatorParameters | undefined {
  const truth = sources?.[0]?.generatedFrom
  const n = sources?.[0]?.data.length
  if (!truth || !n || ![truth.beta, truth.eta, truth.gamma].every(Number.isFinite)) return
  if (sources?.every(source => source.data.length === n && source.data.every(point => point.status === 'F') &&
      source.generatedFrom?.beta === truth.beta && source.generatedFrom.eta === truth.eta &&
      source.generatedFrom.gamma === truth.gamma)) return truth
}

export function sampleBatchWorkbook(methodId: string, sources: DataSource[], truth: CalculatorParameters, offset?: number) {
  return makeWorkbook(methodId, sources.map((source, index) => {
    const observations = source.data.map(point => point.value)
    const result = source.result
    const status = source.calculationError ? 'failure' : result ? checkStatus(
      result.beta ?? NaN, result.eta ?? NaN, result.gamma, truth.beta, truth.eta, truth.gamma,
      result.converged !== false && result.converged !== 'unbounded', Math.min(...observations),
    ) : 'pending'
    return {
      id: index + 1,
      observations,
      estimates: [result?.beta ?? null, result?.eta ?? null, result?.gamma ?? null],
      status,
      error: source.calculationError ?? (status === 'failure' ? '该估计未通过有效性检查' : undefined),
    }
  }), offset)
}

export function analysisWorkbookCsv(view: WorkbookView, group: WorkbookGroup, runs: ReadonlyMap<WorkbookCell, WorkbookRun>, n: number) {
  const encode = (value: WorkbookCell | undefined) => {
    const cell = String(value ?? '')
    if (typeof value === 'string' && /^[=+\-@\t\r]/.test(cell)) return '"' + "'" + cell.replace(/"/g, '""') + '"'
    return /[",\r\n]/.test(cell) ? '"' + cell.replace(/"/g, '""') + '"' : cell
  }
  const rows = view === 'samples'
    ? [['样本', ...Array.from({ length: n }, (_, index) => `x${index + 1}`)], ...group.samples]
    : [['样本', '形状 β', '尺度 η', '位置 γ', '状态', '说明'], ...group.resultRows.map(row => [
      ...row, runs.get(row[0])?.status, runs.get(row[0])?.error,
    ])]
  return '\uFEFF' + rows.map(row => row.map(encode).join(',')).join('\r\n')
}
