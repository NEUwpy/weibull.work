import fs from 'fs'
import path from 'path'
import { createHash } from 'crypto'
import catalog from '@/content/monte-carlo/research00.json'
import { DataConfigurationError, getDataRoot, resolveRootEntry } from './data-root'
import { archivedMDMFlow } from './archived-mdm-flow'
import type { ArchivedMDMProcess, ArchivedMDMRun, ArchivedMDMTrace, MonteCarloWorkbook, WorkbookCard } from '../monte-carlo'

interface Entry extends WorkbookCard {
  directory: string; manifestSha256: string
  mdmProcess?: {
    n: number; delta: number; records: string; source: string; base: string
    replay: { path: string; sha256: string }
  }
}
interface Manifest {
  schemaVersion: number; id: string; importedAt: string; calculationTime: string | null; protocol: string
  configuration: Record<string, unknown>; files: Record<string, { sha256: string; bytes: number; role: string }>
}
export class WorkbookIntegrityError extends Error {}
const entries: Entry[] = catalog.entries
const sha = (data: Buffer) => createHash('sha256').update(data).digest('hex')

function batchEntry(id: string): Entry | undefined { return entries.find(e => e.id === id) }
function batchFile(entry: Entry, relative: string): string {
  const segments = entry.directory.split('/')
  if (segments.shift() !== 'monte-carlo') throw new WorkbookIntegrityError('数据卡目录无效')
  const file = resolveRootEntry(path.join(getDataRoot(), 'monte-carlo'), [...segments, ...relative.split('/')])
  if (!file) throw new DataConfigurationError('已登记工作簿文件缺失：' + relative)
  return file
}
function readManifest(entry: Entry): Manifest {
  const raw = fs.readFileSync(batchFile(entry, 'manifest.json'))
  if (sha(raw) !== entry.manifestSha256) throw new WorkbookIntegrityError('计算来源记录的哈希已变化')
  const manifest: Manifest = JSON.parse(raw.toString('utf8'))
  if (manifest.schemaVersion !== 1 || manifest.id !== entry.id) throw new WorkbookIntegrityError('计算来源与数据卡不匹配')
  return manifest
}
function readFile(entry: Entry, manifest: Manifest, relative: string): Buffer {
  const record = manifest.files[relative]
  if (!record) throw new WorkbookIntegrityError('文件未在计算来源中登记')
  const raw = fs.readFileSync(batchFile(entry, relative))
  if (raw.length !== record.bytes || sha(raw) !== record.sha256) throw new WorkbookIntegrityError('文件身份已变化：' + relative)
  return raw
}
export function workbookCatalog(): WorkbookCard[] {
  return entries.map(entry => {
    const { directory: _directory, manifestSha256: _hash, mdmProcess, ...fields } = entry
    const card = { ...fields, mdmProcess: mdmProcess && { n: mdmProcess.n, delta: mdmProcess.delta } }
    try { const manifest = readManifest(entry); readFile(entry, manifest, 'workbook.json'); readFile(entry, manifest, 'workbook.xlsx'); return { ...card, available: true } }
    catch (error) { return { ...card, available: false, error: error instanceof Error ? error.message : '数据不可读取' } }
  })
}
export function registeredWorkbook(id: string): MonteCarloWorkbook | null {
  const entry = batchEntry(id)
  if (!entry) return null
  const manifest = readManifest(entry)
  return readWorkbook(entry, manifest)
}
function readWorkbook(entry: Entry, manifest: Manifest): MonteCarloWorkbook {
  const book: MonteCarloWorkbook = JSON.parse(readFile(entry, manifest, 'workbook.json').toString('utf8'))
  if (book.id !== entry.id || book.sha256 !== entry.workbookSha256) throw new WorkbookIntegrityError('工作簿与数据卡不匹配')
  book.source = { kind: 'archive', calculationTime: manifest.calculationTime, importedAt: manifest.importedAt,
    protocol: manifest.protocol, directory: entry.directory, manifestSha256: entry.manifestSha256,
    configuration: manifest.configuration, code: Object.entries(manifest.files).filter(([, v]) => v.role === 'code').map(([p, v]) => ({ path: p, sha256: v.sha256 })) }
  return book
}

type ReplayRun = ArchivedMDMTrace & { id: number; trialShapes: ArchivedMDMTrace['shape'][] }

function readReplay(entry: Entry, process: NonNullable<Entry['mdmProcess']>) {
  const file = resolveRootEntry(path.join(getDataRoot(), 'monte-carlo'), process.replay.path.split('/'))
  if (!file) throw new DataConfigurationError('归档 MDM 的补录计算记录缺失')
  const bytes = fs.readFileSync(file)
  if (sha(bytes) !== process.replay.sha256) throw new WorkbookIntegrityError('补录计算记录的身份已变化')
  const replay: { manifestSha256: string; n: number; delta: number; runs: ReplayRun[] }
    = JSON.parse(bytes.toString('utf8'))
  const traces = new Map(replay.runs.map(run => [run.id, run]))
  if (replay.manifestSha256 !== entry.manifestSha256 || replay.n !== process.n || replay.delta !== process.delta ||
      traces.size !== replay.runs.length) throw new WorkbookIntegrityError('补录计算记录与归档批次不一致')
  return { traces, artifact: { path: process.replay.path, sha256: process.replay.sha256, bytes: bytes.length } }
}

function finiteTuples(value: unknown, size: number): value is number[][] {
  return Array.isArray(value) && value.every(tuple => Array.isArray(tuple) && tuple.length === size && tuple.every(Number.isFinite))
}

export function registeredWorkbookProcess(id: string, n: number, delta: number): ArchivedMDMProcess | null {
  const entry = batchEntry(id)
  const process = entry?.mdmProcess
  if (!entry || !process || process.n !== n || process.delta !== delta) return null
  const manifest = readManifest(entry)
  const book = readWorkbook(entry, manifest)
  const group = book.groups[String(n)]
  const block = group?.blocks.find(block => block.method === 'mdm' && block.delta === delta)
  if (!block || !book.truth || book.truth.length !== 3 || !book.truth.every(Number.isFinite)) throw new WorkbookIntegrityError('归档过程与工作簿条件不匹配')
  const sampleById = new Map(group.samples.map(([id, ...sample]) => [id, sample]))
  const resultById = new Map(group.resultRows.map(row => [row[0], row.slice(block.column, block.column + 3)]))
  if (sampleById.size !== group.samples.length || resultById.size !== group.resultRows.length) {
    throw new WorkbookIntegrityError('工作簿的重复编号不唯一')
  }
  const { traces, artifact } = readReplay(entry, process)
  const rows = readFile(entry, manifest, process.records).toString('utf8').trim().split(/\r?\n/).map(line => JSON.parse(line))
  const runs = rows.filter(row => row.method_id === 'mdm' && row.n === n && row.delta === delta).map((row): ArchivedMDMRun => {
    const sample = sampleById.get(row.id)
    const result = resultById.get(row.id)
    const estimates = [row.beta_hat, row.eta_hat, row.gamma_hat]
    const info = row.extra?.solution_info
    const bracket: [number, number] = [info?.root_bracket?.left?.gamma, info?.root_bracket?.right?.gamma]
    const curve = row.criterion_curve
    if (!Number.isInteger(row.id) || !sample || sample.length !== n || !sample.every(Number.isFinite) ||
        !result || !estimates.every((value, index) => Number.isFinite(value) && value === result[index]) ||
        !Number.isFinite(row.r_squared) || row.converged !== true ||
        info?.root_solver !== 'brent' || info.target_offset !== delta || info.optimal_gamma !== row.gamma_hat ||
        !bracket.every(Number.isFinite) || bracket[0] > row.gamma_hat || bracket[1] < row.gamma_hat ||
        !Array.isArray(curve) || curve.length < 2 || curve.some(point => !Number.isFinite(point.gamma) || !Number.isFinite(point.gradient))) {
      throw new WorkbookIntegrityError('某次归档曲线、求解记录或估计值与工作簿不一致')
    }
    const replay = traces.get(row.id)
    const gradient: ArchivedMDMRun['curve'] = curve.map(({ gamma, gradient }) => ({ gamma, gradient })).sort((a, b) => a.gamma - b.gamma)
    if (!replay || !finiteTuples(replay.profile, 3) || replay.profile.length !== gradient.length ||
        replay.profile.some(([gamma], index) => gamma !== gradient[index].gamma) ||
        !Array.isArray(replay.trialShapes) || replay.trialShapes.length !== gradient.length ||
        !finiteTuples(replay.shape, 2) || !replay.shape.some(([beta]) => beta === row.beta_hat) ||
        !finiteTuples(replay.pseudoScales, 2) || replay.pseudoScales.length !== n ||
        !Number.isFinite(replay.scaleSum) || replay.scaleSum / n !== row.eta_hat) {
      throw new WorkbookIntegrityError('补录计算点与归档记录不一致')
    }
    const { profile, shape, pseudoScales, scaleSum } = replay
    return { id: row.id, sample: (sample as number[]).slice().sort((a, b) => a - b),
      beta: row.beta_hat, eta: row.eta_hat, gamma: row.gamma_hat, rSquared: row.r_squared, bracket, curve: gradient,
      trace: { profile, shape, pseudoScales, scaleSum } }
  }).sort((a, b) => a.id - b.id)
  if (!runs.length || runs.length !== sampleById.size || runs.length !== resultById.size ||
      runs.length !== traces.size || new Set(runs.map(run => run.id)).size !== runs.length) {
    throw new WorkbookIntegrityError('归档过程没有覆盖该组的全部重复')
  }
  const frozen = (relative: string) => ({
    path: relative, sha256: manifest.files[relative]?.sha256,
    lines: readFile(entry, manifest, relative).toString('utf8').split(/\r?\n/),
  })
  const flow = archivedMDMFlow(frozen(process.source), frozen(process.base))
  flow.artifacts = [process.records, 'workbook.json'].map(relative => ({
    path: relative, sha256: manifest.files[relative].sha256, bytes: manifest.files[relative].bytes,
  }))
  flow.artifacts.push(artifact)
  return { selection: { id, n, delta }, title: book.title, truth: book.truth, flow, runs }
}

export function registeredWorkbookTrialShapes(id: string, n: number, delta: number, runId: number): ReplayRun['trialShapes'] | null {
  const entry = batchEntry(id)
  const process = entry?.mdmProcess
  if (!entry || !process || process.n !== n || process.delta !== delta || !Number.isInteger(runId)) return null
  readManifest(entry)
  const { traces } = readReplay(entry, process)
  const run = traces.get(runId)
  if (!run) return null
  if (!Array.isArray(run.trialShapes) || run.trialShapes.length !== run.profile.length ||
      run.trialShapes.some((points, index) => !finiteTuples(points, 2) ||
        !points.some(([beta, sigma]) => beta === run.profile[index][2] && sigma === run.profile[index][1]))) {
    throw new WorkbookIntegrityError('形状试算点与归档廓线不一致')
  }
  return run.trialShapes
}
export function registeredWorkbookFile(id: string, codePath?: string): { bytes: Buffer; filename: string } | null {
  const entry = batchEntry(id)
  if (!entry) return null
  const manifest = readManifest(entry)
  if (codePath && manifest.files[codePath]?.role !== 'code') return null
  const relative = codePath || 'workbook.xlsx'
  return { bytes: readFile(entry, manifest, relative), filename: codePath ? path.posix.basename(codePath) : entry.filename }
}
