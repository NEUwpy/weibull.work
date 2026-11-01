import fs from 'fs'
import path from 'path'
import { createHash } from 'crypto'
import catalog from '@/content/monte-carlo/research00.json'
import { DataConfigurationError, getDataRoot, resolveRootEntry } from './data-root'
import type { MonteCarloWorkbook, WorkbookCard } from '../monte-carlo'

interface Entry extends WorkbookCard { directory: string; manifestSha256: string }
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
    const { directory: _directory, manifestSha256: _hash, ...card } = entry
    try { const manifest = readManifest(entry); readFile(entry, manifest, 'workbook.json'); readFile(entry, manifest, 'workbook.xlsx'); return { ...card, available: true } }
    catch (error) { return { ...card, available: false, error: error instanceof Error ? error.message : '数据不可读取' } }
  })
}
export function registeredWorkbook(id: string): MonteCarloWorkbook | null {
  const entry = batchEntry(id)
  if (!entry) return null
  const manifest = readManifest(entry)
  const book: MonteCarloWorkbook = JSON.parse(readFile(entry, manifest, 'workbook.json').toString('utf8'))
  if (book.id !== id || book.sha256 !== entry.workbookSha256) throw new WorkbookIntegrityError('工作簿与数据卡不匹配')
  book.source = { kind: 'archive', calculationTime: manifest.calculationTime, importedAt: manifest.importedAt,
    protocol: manifest.protocol, directory: entry.directory, manifestSha256: entry.manifestSha256,
    configuration: manifest.configuration, code: Object.entries(manifest.files).filter(([, v]) => v.role === 'code').map(([p, v]) => ({ path: p, sha256: v.sha256 })) }
  return book
}
export function registeredWorkbookFile(id: string, codePath?: string): { bytes: Buffer; filename: string } | null {
  const entry = batchEntry(id)
  if (!entry) return null
  const manifest = readManifest(entry)
  if (codePath && manifest.files[codePath]?.role !== 'code') return null
  const relative = codePath || 'workbook.xlsx'
  return { bytes: readFile(entry, manifest, relative), filename: codePath ? path.posix.basename(codePath) : entry.filename }
}
