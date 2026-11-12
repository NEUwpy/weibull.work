import fs from 'fs'
import path from 'path'
import { createHash } from 'crypto'
import { DataConfigurationError, getDataRoot, resolveRootEntry } from './data-root'
import { loadMethodFlow } from './method-flow.mjs'
import { readCalculationTrace } from '../calculation-trace'
import { liveMDMBatch } from '../../components/methods/mdm/visualizers/batch-process-data'
import type { CalculationRecordSet, MDMProcessBatch, MDMProcessRun } from '../calculation-records'
import type { MethodFlow } from '../method-flow'

export class CalculationRecordIntegrityError extends Error {}
const fail = (message: string): never => { throw new CalculationRecordIntegrityError(message) }
const tuples = (value: unknown, length: number): value is number[][] => Array.isArray(value)
  && value.every(row => Array.isArray(row) && row.length === length && row.every(Number.isFinite))

export function readCalculationRecordSet(id: string): CalculationRecordSet | null {
  const match = /^([a-z][a-z0-9]*)-([a-f0-9]{64})$/.exec(id)
  if (!match) return null
  const file = resolveRootEntry(path.join(getDataRoot(), 'calculation-records'), [match[1], match[2] + '.json'])
  if (!file) throw new DataConfigurationError('计算记录集不存在')
  const bytes = fs.readFileSync(file)
  if (createHash('sha256').update(bytes).digest('hex') !== match[2]) fail('计算记录集的内容哈希不一致')
  const set: CalculationRecordSet = JSON.parse(bytes.toString('utf8'))
  if (set.schemaVersion !== 1 || set.method !== match[1] || set.model !== '3p'
      || typeof set.title !== 'string' || !set.settings || !Array.isArray(set.truth) || !set.truth.every(Number.isFinite)
      || !set.implementation?.sources?.length || set.implementation.sources.some(source =>
        !/^[a-f0-9]{64}$/.test(source.sha256) || !/^(methods\/[a-z0-9_]+\.(py|tsv)|base\.py)$/.test(source.path))
      || !Array.isArray(set.records) || !set.records.length || new Set(set.records.map(run => run.id)).size !== set.records.length) {
    fail('计算记录集格式或算法身份不完整')
  }
  for (const record of set.records) {
    if (!Number.isInteger(record.id) || !record.input?.observations?.length || !record.input.observations.every(Number.isFinite)
        || !record.result || !['beta', 'eta', 'gamma', 'rSquared'].every(key => {
          const value = record.result[key as keyof typeof record.result]
          return value === null || typeof value === 'number' && Number.isFinite(value)
        }) || !['boolean', 'string'].includes(typeof record.result.converged)) fail('计算记录的样本或结果不完整')
    if (record.calculation) {
      if (!readCalculationTrace(record.calculation, set.method).trace) fail('计算过程记录无效')
      const identity = record.calculation.run as { observations?: number[]; sources?: { path: string; sha256: string }[] } | undefined
      if (!identity || JSON.stringify(identity.observations) !== JSON.stringify([...record.input.observations].sort((a,b) => a-b))
          || !set.implementation.sources.every(source => identity.sources?.some(item => item.path === source.path && item.sha256 === source.sha256))) {
        fail('计算过程与样本或算法身份不一致')
      }
    }
    if (!record.calculation && !record.process) fail('计算记录缺少完整过程')
  }
  return set
}

export function mdmRecordSetProcess(id: string, set: CalculationRecordSet, includeTrials = false): MDMProcessBatch {
  if (set.method !== 'mdm') fail('该记录集不是 MDM 方法')
  if (typeof set.settings.offset !== 'number' || !Number.isFinite(set.settings.offset)) fail('MDM 计算设置不完整')
  const flow = structuredClone(set.flow ?? loadMethodFlow('mdm')) as MethodFlow
  if (!flow?.workflow || flow.steps.length !== 6 || !flow.sources.every(file =>
      set.implementation.sources.some(source => file.path.replace(/^python\//, '') === source.path && file.sha256 === source.sha256))) {
    fail('计算流程与已保存的算法身份不一致')
  }
  let runs: MDMProcessRun[]
  if (set.records.every(record => record.process)) {
    runs = set.records.map(record => ({ id: record.id, sample: record.input.observations,
      ...record.result, ...record.process! }) as MDMProcessRun)
  } else {
    const sources = set.records.map(record => ({ id: String(record.id), name: String(record.id), color: '#2563eb', sourceType: 'custom' as const,
      data: record.input.observations.map((value, index) => ({ id: index, value, status: 'F' as const })),
      result: { ...record.result, gamma: record.result.gamma ?? 0, points: [] },
      traceData: record.traceData, calculation: record.calculation }))
    runs = liveMDMBatch(sources, undefined, Number(set.settings.offset)).runs.map((run, index) => ({ ...run, id: set.records[index].id }))
    if (runs.length !== set.records.length) fail('计算记录缺少某组的完整过程')
  }
  for (const run of runs) {
    const trace = run.trace
    if (![run.beta, run.eta, run.gamma, run.rSquared, trace?.scaleSum].every(Number.isFinite)
        || !tuples(trace.profile, 3) || !tuples(trace.shape, 2) || !tuples(trace.pseudoScales, 2)
        || trace.pseudoScales.length !== run.sample.length || trace.scaleSum / run.sample.length !== run.eta
        || !trace.shape.some(([beta]) => beta === run.beta) || !Array.isArray(run.curve) || !run.curve.length
        || run.curve.some(point => !Number.isFinite(point.gradient) || !Number.isFinite(point.gamma))
        || !trace.trialShapes || trace.trialShapes.length !== trace.profile.length || trace.trialShapes.some((points, index) =>
          !tuples(points, 2) || !points.some(([beta, sigma]) => beta === trace.profile[index][2] && sigma === trace.profile[index][1]))) {
      fail('MDM 各阶段的实际计算点不一致或不完整')
    }
  }
  if (!includeTrials) runs = runs.map(run => ({ ...run, trace: { ...run.trace, trialShapes: undefined } }))
  return { selection: { id, n: runs[0].sample.length, delta: Number(set.settings.offset) },
    title: set.title, truth: set.truth, flow, runs }
}
