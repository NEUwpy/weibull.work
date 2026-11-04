import fs from 'fs'
import path from 'path'
import { resolveDataEntry } from './data-root'
import { canCalculateDataset, datasetScale, natureLabels, observationLabels, type CaseDataset, type CaseDatasetIndexEntry, type CaseCatalogGroup, type CaseMemberRole } from '../case-datasets'

const cached = new Map<string, { revision: string; record: CaseDataset }>()
const identifier = /^[A-Za-z0-9\u3400-\u9fff][A-Za-z0-9\u3400-\u9fff_-]*$/

/** Scanning finds materials; this explicit directory selects and groups publishable cases. */
export function readCaseCatalogLayout(): { configured: boolean; groups: CaseCatalogGroup[]; issues: string[] } {
  const file = resolveDataEntry(['cases', 'catalog.json'])
  if (!file) return { configured: false, groups: [], issues: [] }
  try {
    const value = JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''))
    if (value?.schema_version !== 1 || !Array.isArray(value.groups)) throw new Error('案例分组目录格式无效')
    const ids = new Set<string>()
    const members = new Set<string>()
    for (const group of value.groups) {
      if (!object(group) || typeof group.id !== 'string' || !identifier.test(group.id) || ids.has(group.id)
        || typeof group.name !== 'string' || !group.name.trim()
        || !['observed', 'simulated', 'result'].includes(group.kind)
        || (group.description !== undefined && typeof group.description !== 'string')
        || !Array.isArray(group.members) || !group.members.length) throw new Error('案例分组条目无效')
      ids.add(group.id)
      for (const member of group.members) {
        if (!object(member) || typeof member.id !== 'string' || !identifier.test(member.id) || members.has(member.id)
          || typeof member.name !== 'string' || !member.name.trim()
          || (member.role !== undefined && !['sample', 'derived', 'table', 'figure', 'external'].includes(member.role))) throw new Error('案例组内成员无效或重复')
        members.add(member.id)
      }
    }
    if (Array.from(ids).some(id => members.has(id))) throw new Error('案例组编号不能与数据编号重复')
    return { configured: true, groups: value.groups, issues: [] }
  } catch (error) {
    return { configured: true, groups: [], issues: [(error as Error).message] }
  }
}

function object(value: unknown): value is Record<string, any> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function validData(value: unknown): boolean {
  if (Array.isArray(value)) return value.length > 0 && value.every(point => typeof point === 'number' && Number.isFinite(point))
  if (!object(value)) return false
  if (value.kind === 'table') return Array.isArray(value.rows) && value.rows.length > 0
    && value.rows.every((row: unknown) => Array.isArray(row) && row.every(cell => cell === null || typeof cell === 'string' || (typeof cell === 'number' && Number.isFinite(cell))))
    && (value.html === undefined || typeof value.html === 'string')
  if (value.kind === 'figure') return typeof value.asset === 'string' && !!value.asset
    && (value.caption === undefined || typeof value.caption === 'string')
  return value.kind === 'external' && typeof value.description === 'string' && !!value.description.trim()
    && (value.url === undefined || typeof value.url === 'string')
}

function validMetadata(value: unknown): boolean {
  return object(value) && typeof value.id === 'string' && identifier.test(value.id)
    && typeof value.name === 'string' && !!value.name.trim()
    && object(value.nature) && Object.hasOwn(natureLabels, value.nature.kind)
    && Object.hasOwn(observationLabels, value.nature.observation)
    && ['quantity', 'note'].every(key => value.nature[key] === undefined || typeof value.nature[key] === 'string')
    && (value.nature.unit === undefined || value.nature.unit === null || typeof value.nature.unit === 'string')
    && Array.isArray(value.sources) && value.sources.length > 0 && value.sources.every((source: unknown) => object(source)
      && typeof source.paper_id === 'string' && identifier.test(source.paper_id)
      && typeof source.location === 'string' && !!source.location.trim()
      && ['direct', 'secondary'].includes(source.relation)
      && ['original_reference', 'original_paper_id'].every(key => source[key] === undefined || typeof source[key] === 'string'))
}

export function validateCaseDataset(value: unknown): value is CaseDataset {
  return validMetadata(value) && object(value) && validData(value.data)
}

function readRecordFile(directory: string, name: string, stat = fs.lstatSync(path.join(directory, name))): CaseDataset {
  if (!stat.isFile() || stat.isSymbolicLink()) throw new Error('案例文件必须为普通文件')
  const file = path.join(directory, name)
  const revision = `${stat.mtimeMs}:${stat.size}`
  const previous = cached.get(file)
  if (previous?.revision === revision) return previous.record
  const value = JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''))
  if (!validateCaseDataset(value)) throw new Error('数据、性质或来源格式无效')
  const record: CaseDataset = { id: value.id, name: value.name, data: value.data, nature: value.nature, sources: value.sources }
  cached.set(file, { revision, record })
  return record
}

function recordFileName(file: unknown): string | null {
  if (typeof file !== 'string') return null
  const name = file.startsWith('records/') ? file.slice(8) : file
  return /^[A-Za-z0-9\u3400-\u9fff][A-Za-z0-9\u3400-\u9fff_.-]*\.json$/.test(name) ? name : null
}

let indexCache: { path: string; revision: string; entries: Map<string, CaseDatasetIndexEntry> } | undefined

function storedIndex(): Map<string, CaseDatasetIndexEntry> {
  const file = resolveDataEntry(['cases', 'index.json'])
  if (!file) return new Map()
  const stat = fs.statSync(file)
  const revision = `${stat.mtimeMs}:${stat.size}`
  if (indexCache?.path === file && indexCache.revision === revision) return indexCache.entries
  const value = JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''))
  if (value?.schema_version !== 1 || !Array.isArray(value.records)) throw new Error('案例目录索引格式无效')
  const entries = new Map<string, CaseDatasetIndexEntry>()
  for (const entry of value.records) {
    const name = recordFileName(entry?.file)
    if (!name || !validMetadata(entry) || typeof entry.scale !== 'string'
      || typeof entry.can_calculate !== 'boolean' || !['sample', 'table', 'figure', 'external'].includes(entry.data_kind)
      || !Number.isFinite(entry.size) || !Number.isFinite(entry.mtime_ms) || entries.has(name)) throw new Error('案例目录索引条目无效')
    entries.set(name, entry)
  }
  indexCache = { path: file, revision, entries }
  return entries
}

/** The generated index avoids opening thousands of tables for a directory request. */
export function readCaseDatasetIndex(): { records: CaseDatasetIndexEntry[]; issues: string[]; pending_records: number } {
  const directory = resolveDataEntry(['cases', 'records'], 'directory')
  if (!directory) return { records: [], issues: [], pending_records: 0 }
  const issues: string[] = []
  let stored = new Map<string, CaseDatasetIndexEntry>()
  try { stored = storedIndex() } catch (error) { issues.push((error as Error).message) }
  const records: CaseDatasetIndexEntry[] = []
  const ids = new Set<string>()
  for (const name of fs.readdirSync(directory).filter(name => name.endsWith('.json')).sort()) {
    try {
      const stat = fs.lstatSync(path.join(directory, name))
      if (!stat.isFile() || stat.isSymbolicLink()) throw new Error('案例文件必须为普通文件')
      let entry = stored.get(name)
      if (!entry || entry.size !== stat.size || Math.abs(entry.mtime_ms - stat.mtimeMs) >= 1) {
        const record = readRecordFile(directory, name, stat)
        entry = { id: record.id, name: record.name, nature: record.nature, sources: record.sources,
          file: name, scale: datasetScale(record), can_calculate: canCalculateDataset(record),
          data_kind: Array.isArray(record.data) ? 'sample' : record.data.kind, size: stat.size, mtime_ms: stat.mtimeMs }
      }
      if (ids.has(entry.id)) throw new Error(`编号重复 ${entry.id}`)
      ids.add(entry.id)
      records.push(entry)
    } catch (error) { issues.push(`${name} · ${(error as Error).message}`) }
  }
  const layout = readCaseCatalogLayout()
  issues.push(...layout.issues)
  if (!layout.configured) {
    if (records.length) issues.push('案例分组目录暂缺，请先整理并生成目录。')
    return { records: [], issues, pending_records: records.length }
  }
  const selected = new Map(layout.groups.flatMap(group => group.members.map(member => [member.id, member] as const)))
  const published = records.filter(record => selected.has(record.id)).map(record => ({ ...record, name: selected.get(record.id)!.name }))
  const available = new Set(published.map(record => record.id))
  for (const id of Array.from(selected.keys())) if (!available.has(id)) issues.push(`组内数据暂缺：${id}`)
  return { records: published, issues, pending_records: records.length - published.length }
}

function readIndexedDataset(entry: CaseDatasetIndexEntry): CaseDataset | null {
  const directory = resolveDataEntry(['cases', 'records'], 'directory')
  const name = recordFileName(entry.file)
  if (!directory || !name) return null
  const record = readRecordFile(directory, name)
  if (record.id !== entry.id) throw new Error('案例目录与数据文件编号不一致')
  return record
}

export function readCaseDatasetById(id: string): (CaseDataset & { role?: CaseMemberRole }) | null {
  const entry = readCaseDatasetIndex().records.find(entry => entry.id === id)
  if (!entry) return null
  const record = readIndexedDataset(entry)
  const member = readCaseCatalogLayout().groups.flatMap(group => group.members).find(member => member.id === id)
  return record ? { ...record, name: entry.name, ...(member?.role ? { role: member.role } : {}) } : null
}

export function readCalculableCaseDatasets(): CaseDataset[] {
  return readCaseDatasetIndex().records.filter(entry => entry.can_calculate).flatMap(entry => {
    const record = readIndexedDataset(entry)
    return record && canCalculateDataset(record) ? [{ ...record, name: entry.name }] : []
  })
}

export function datasetCaseItem(record: CaseDataset) {
  return {
    id: record.id, title: record.name,
    type: record.nature.kind === 'simulated' ? '抽样样本' : record.nature.kind === 'observed' ? '真实样本' : natureLabels[record.nature.kind],
    tags: [natureLabels[record.nature.kind], observationLabels[record.nature.observation]],
    data_raw: canCalculateDataset(record) ? (record.data as number[]).join('\n') : '',
    created_at: '', description: record.nature.note || record.nature.quantity || '',
    related_paper_slug: record.sources[0]?.paper_id,
    can_calculate: canCalculateDataset(record), dataset: record,
    isGroup: false as const,
  }
}

/** Only numbered paper assets can be linked, through the library's existing public asset resolver. */
export function datasetFigureUrl(record: CaseDataset): string | undefined {
  if (Array.isArray(record.data) || record.data.kind !== 'figure') return undefined
  let asset: string
  try { asset = decodeURIComponent(record.data.asset) } catch { return undefined }
  if (asset.startsWith('./')) asset = asset.slice(2)
  if (asset.startsWith('/api/library/assets/')) asset = asset.slice('/api/library/assets/'.length)
  else if (asset.startsWith('/')) asset = asset.slice(1)
  const segments = asset.split('/')
  if (segments.length < 2 || segments.some(segment => !segment || segment === '.' || segment === '..' || /[\\:\x00-\x1f]/.test(segment))) return undefined
  if (!record.sources.some(source => segments[0] === `${source.paper_id}-图片`)) return undefined
  return `/api/library/assets/${segments.map(encodeURIComponent).join('/')}`
}

export function readCaseCoverage(): { scanned: Set<string>; reviewed: Set<string> } {
  const directory = resolveDataEntry(['cases', 'coverage'], 'directory')
  const coverage = { scanned: new Set<string>(), reviewed: new Set<string>() }
  if (!directory) return coverage
  for (const name of fs.readdirSync(directory).filter(name => name.endsWith('.json'))) {
    const file = path.join(directory, name)
    try {
      if (!fs.lstatSync(file).isFile() || fs.lstatSync(file).isSymbolicLink()) continue
      const value = JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''))
      const entries = Array.isArray(value) ? value : Array.isArray(value.papers) ? value.papers : [value]
      for (const entry of entries) {
        if (typeof entry?.paper_id !== 'string') continue
        if (['extracted', 'reviewed', 'complete', 'no_data'].includes(entry.status)) coverage.scanned.add(entry.paper_id)
        if (['reviewed', 'complete', 'no_data'].includes(entry.status)) coverage.reviewed.add(entry.paper_id)
      }
    } catch { /* An unfinished review does not count as coverage. */ }
  }
  return coverage
}
