import fs from 'fs'
import path from 'path'
import { createHash } from 'crypto'
import catalog from '@/content/monte-carlo/research00.json'
import { DataConfigurationError, getDataRoot, resolveRootEntry } from './data-root'
import { readCalculationRecordSet, mdmRecordSetProcess } from './calculation-records'
import type { MonteCarloWorkbook, WorkbookCard } from '../monte-carlo'

interface Entry extends WorkbookCard {
  directory: string; manifestSha256: string
  mdmProcess?: {
    n: number; delta: number; recordId: string
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
    const card = { ...fields, mdmProcess: mdmProcess && { n: mdmProcess.n, delta: mdmProcess.delta, recordId: mdmProcess.recordId } }
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

export function registeredWorkbookProcess(id: string, n: number, delta: number) {
  const entry = batchEntry(id), link = entry?.mdmProcess
  if (!entry || !link || link.n !== n || link.delta !== delta) return null
  const set = readCalculationRecordSet(link.recordId)
  if (!set || set.method !== 'mdm' || Number(set.settings.offset) !== delta) throw new WorkbookIntegrityError('计算记录与所选方法或条件不一致')
  const book = registeredWorkbook(id)!, group = book.groups[String(n)]
  const block = group?.blocks.find(block => block.method === 'mdm' && block.delta === delta)
  if (!group || !block || group.samples.length !== set.records.length || group.resultRows.length !== set.records.length) throw new WorkbookIntegrityError('计算记录未覆盖全部样本')
  const samples = new Map(group.samples.map(([id, ...sample]) => [id, sample.sort((a,b) => Number(a)-Number(b))]))
  const results = new Map(group.resultRows.map(row => [row[0], row.slice(block.column, block.column + 3)]))
  if (samples.size !== group.samples.length || results.size !== group.resultRows.length) throw new WorkbookIntegrityError('样本编号不唯一')
  for (const record of set.records) {
    if (record.input.observations.length !== n || JSON.stringify(samples.get(record.id)) !== JSON.stringify([...record.input.observations].sort((a,b) => a-b))
        || JSON.stringify(results.get(record.id)) !== JSON.stringify([record.result.beta, record.result.eta, record.result.gamma])) throw new WorkbookIntegrityError('计算记录与样本或估计值不一致')
  }
  return mdmRecordSetProcess(link.recordId, set)
}

export function registeredWorkbookTrialShapes(id: string, n: number, delta: number, runId: number) {
  if (!registeredWorkbookProcess(id, n, delta)) return null
  const recordId = batchEntry(id)!.mdmProcess!.recordId, set = readCalculationRecordSet(recordId)!
  return mdmRecordSetProcess(recordId, set, true).runs.find(run => run.id === runId)?.trace.trialShapes ?? null
}

export function registeredWorkbookFile(id: string, codePath?: string): { bytes: Buffer; filename: string } | null {
  const entry = batchEntry(id)
  if (!entry) return null
  const manifest = readManifest(entry)
  if (codePath && manifest.files[codePath]?.role !== 'code') return null
  const relative = codePath || 'workbook.xlsx'
  return { bytes: readFile(entry, manifest, relative), filename: codePath ? path.posix.basename(codePath) : entry.filename }
}
