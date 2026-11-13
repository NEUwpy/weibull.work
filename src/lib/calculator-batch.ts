import type { CalculatorParameters } from './calculator-state'
import { generateWeibullSample, getEstimateFailure } from './calculator-state'
import type { DataSource } from './weibull'
import { MULTI_CURVE_COLORS } from './weibull'
import { CalculationError } from './calculation-feedback'
import type { CalculateResponse } from '../hooks/useWeibullCalculation'
import type { MonteCarloWorkbook } from './monte-carlo'

export interface BatchProgress { completed: number; total: number; runId?: string }
export const SAMPLE_COUNTS = [1, 50, 100, 200, 500, 1000]

export function inheritSampleSources(sources: DataSource[]): DataSource[] {
  const groupId = 'inherited-' + crypto.randomUUID()
  return sources.map((source, index) => ({
    id: groupId + '-' + (index + 1), groupId, name: source.name, color: source.color, sourceType: 'custom',
    data: source.data.map(point => ({ ...point })),
    generatedFrom: source.generatedFrom ? { ...source.generatedFrom } : undefined,
  }))
}

export function workbookSampleSources(book: MonteCarloWorkbook, n: number, methodId: string, delta: number): DataSource[] {
  const group = book.groups[String(n)]
  const block = group?.blocks.find(block => block.method === methodId && (methodId !== 'mdm' || block.delta === delta))
  if (!group || !block) throw new Error('这组样本没有对应的方法结果')
  const origin = book.truth?.length === 3 ? { beta: book.truth[0], eta: book.truth[1], gamma: book.truth[2] } : undefined
  const results = new Map(group.resultRows.map(row => [row[0], row]))
  return group.samples.map((row, index) => {
    if (typeof row[0] !== 'number' || row.length !== n + 1 || row.slice(1).some(value => typeof value !== 'number' || !Number.isFinite(value))) {
      throw new Error('归档样本不完整，无法载入卡片')
    }
    const values = results.get(row[0])?.slice(block.column, block.column + 3)
    const valid = values?.length === 3 && values.every(value => typeof value === 'number' && Number.isFinite(value))
      && Number(values[0]) > 0 && Number(values[1]) > 0
    const groupId = 'archive-' + book.id + '-' + n + '-' + delta
    return { id: groupId + '-' + row[0], groupId, name: '第 ' + row[0] + ' 组',
      sourceType: 'custom', color: MULTI_CURVE_COLORS[index % MULTI_CURVE_COLORS.length],
      data: row.slice(1).map((value, id) => ({ id, value: Number(value), status: 'F' as const })),
      generatedFrom: origin, archive: { id: book.id, n, delta, runId: row[0] },
      result: valid ? { beta: Number(values![0]), eta: Number(values![1]), gamma: Number(values![2]), rSquared: null, points: [], converged: true } : undefined,
      calculationOffset: methodId === 'mdm' ? delta : undefined,
      calculationError: valid ? undefined : '归档中未记录有效估计',
    }
  })
}

export function generateSampleSources(count: number, n: number, parameters: CalculatorParameters): DataSource[] {
  if (!Number.isInteger(count) || count < 1 || count > 1000) throw new Error('组数须为 1–1000 的整数')
  const groupId = 'generated-' + crypto.randomUUID()
  return Array.from({ length: count }, (_, index) => ({
    id: groupId + '-' + (index + 1), name: '第 ' + (index + 1) + ' 组', groupId,
    sourceType: 'custom' as const, color: MULTI_CURVE_COLORS[index % MULTI_CURVE_COLORS.length],
    data: generateWeibullSample(n, parameters), generatedFrom: { ...parameters },
  }))
}

/** Each response stays with its original sample, including rejected estimates. */
export async function estimateSampleSources(
  sources: DataSource[],
  estimate: (source: DataSource) => Promise<CalculateResponse & {
    calculationOffset?: number; mdmOptimization?: DataSource['mdmOptimization']; fixedComparison?: DataSource['fixedComparison']
  }>,
  options: { isCurrent: () => boolean; onProgress: (sources: DataSource[], progress: BatchProgress) => void },
): Promise<DataSource[] | null> {
  if (!options.isCurrent()) return null
  const runId = crypto.randomUUID()
  const updated = sources.map(source => ({ ...source, result: undefined, traceData: undefined,
    calculation: undefined, calculationError: undefined, calculationOffset: undefined,
    mdmOptimization: undefined, fixedComparison: undefined, archive: undefined } as DataSource))
  options.onProgress(updated.slice(), { completed: 0, total: sources.length, runId })
  for (let index = 0; index < sources.length; index++) {
    if (!options.isCurrent()) return null
    const source = sources[index]
    try {
      const response = await estimate(source)
      const failure = getEstimateFailure(response.result)
      if (failure) throw new CalculationError(failure, response.calculation, response.traceData, { kind: 'solver' })
      updated[index] = { ...source, result: response.result, traceData: response.traceData,
        calculation: response.calculation, calculationOffset: response.calculationOffset,
        mdmOptimization: response.mdmOptimization, fixedComparison: response.fixedComparison,
        archive: undefined, calculationError: undefined }
    } catch (error) {
      updated[index] = { ...updated[index], calculationError: error instanceof Error ? error.message : String(error),
        traceData: error instanceof CalculationError ? error.traceData : undefined,
        calculation: error instanceof CalculationError ? error.calculation : undefined }
    }
    if (!options.isCurrent()) return null
    options.onProgress(updated.slice(), { completed: index + 1, total: sources.length, runId })
  }
  return updated
}

const handoffKey = 'weibull-calculation-batch:'
type StoredBatch = {
  methodId: string
  sources: DataSource[]
  activeIndex: number
  offset: number
  generatedFrom?: CalculatorParameters
  analysis?: { offsetMode: 'fixed' | 'ai' }
}
const processBatches = new Map<string, StoredBatch>()
export function storeCalculationBatch(sources: DataSource[], methodId: string, activeIndex: number,
  offset: number, generatedFrom?: CalculatorParameters, analysis?: StoredBatch['analysis']): string {
  const id = crypto.randomUUID()
  processBatches.set(id, { sources, methodId, activeIndex, offset, generatedFrom, analysis })
  if (processBatches.size > 3) processBatches.delete(processBatches.keys().next().value!)
  // Samples are retained for an exact handoff. Process records are obtained by
  // the method page, so large trace payloads do not enter session storage.
  try {
    sessionStorage.setItem(handoffKey + id, JSON.stringify({ methodId, activeIndex, offset, generatedFrom, analysis,
      sources: sources.map(({ id, name, color, data, groupId, sourceType, generatedFrom, archive, result, calculationError, calculationOffset }) =>
        ({ id, name, color, data, groupId, sourceType, generatedFrom, archive,
          ...(analysis && { result: result && { ...result, points: [] }, calculationError, calculationOffset }),
        })) }))
  } catch { /* The current tab can still use the in-memory records. */ }
  return id
}

export function readCalculationBatch(id: string, methodId: string, reuseSamples = false): StoredBatch | null {
  const cached = processBatches.get(id)
  const forMethod = (batch: StoredBatch) => batch.methodId === methodId ? batch : reuseSamples ? {
    ...batch, methodId, analysis: undefined, sources: batch.sources.map(({ id, name, color, data, groupId, sourceType, generatedFrom }) =>
      ({ id, name, color, data, groupId, sourceType, generatedFrom })),
  } : null
  if (cached) return forMethod(cached)
  let raw: string | null
  try { raw = sessionStorage.getItem(handoffKey + id) } catch { return null }
  if (!raw) return null
  let batch: StoredBatch
  try { batch = JSON.parse(raw) } catch { return null }
  if (typeof batch.methodId !== 'string' || !Array.isArray(batch.sources) || !batch.sources.length ||
      !Number.isFinite(batch.offset) || batch.sources.length > 1000 || batch.sources.some(source =>
        !source || typeof source.id !== 'string' || !Array.isArray(source.data) ||
        source.data.some(point => !point || !Number.isFinite(point.value) || !['F', 'S'].includes(point.status)))) return null
  return forMethod({ ...batch, activeIndex: Math.max(0, Math.min(batch.sources.length - 1, Number.isInteger(batch.activeIndex) ? batch.activeIndex : 0)) })
}
