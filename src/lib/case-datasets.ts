export type CaseNature = {
  kind: 'observed' | 'simulated' | 'result' | 'unknown'
  observation: 'complete' | 'right_censored' | 'interval_censored' | 'grouped' | 'summary' | 'external' | 'unknown'
  quantity?: string
  unit?: string | null
  note?: string
  tags?: string[]
}

export type CaseSource = {
  paper_id: string
  location: string
  relation: 'direct' | 'secondary'
  original_reference?: string
  original_paper_id?: string
  title?: string
  author?: string
  year?: number
  available?: boolean
}

export type DatasetData = number[]
  | { kind: 'table'; rows: (string | number | null)[][]; html?: string }
  | { kind: 'figure'; asset: string; caption?: string }
  | { kind: 'external'; description: string; url?: string }

export type CaseDataset = {
  id: string
  name: string
  data: DatasetData
  nature: CaseNature
  sources: CaseSource[]
}

export type CatalogDataset = CaseDataset & {
  can_calculate: boolean
  figure_url?: string
  legacy_href?: string
  role?: CaseMemberRole
}

export type CaseMemberRole = 'sample' | 'derived' | 'table' | 'figure' | 'external'
export type CatalogSummary = Omit<CatalogDataset, 'data'> & { scale: string; is_group?: false }

export type CaseCatalogGroup = {
  id: string
  name: string
  kind: 'observed' | 'simulated' | 'result'
  description?: string
  tags?: string[]
  members: { id: string; name: string; role?: CaseMemberRole }[]
}

export type CatalogGroupSummary = {
  id: string
  name: string
  is_group: true
  nature: CaseNature
  sources: CaseSource[]
  scale: string
  can_calculate: false
  member_count: number
  description?: string
}
export type CatalogGroupDetail = CatalogGroupSummary & { members: CatalogSummary[] }
export type CatalogEntry = CatalogSummary | CatalogGroupSummary

export type CaseDatasetIndexEntry = Omit<CaseDataset, 'data'> & {
  file: string
  scale: string
  can_calculate: boolean
  data_kind: 'sample' | 'table' | 'figure' | 'external'
  size: number
  mtime_ms: number
}

export type CaseCatalog = {
  items: CatalogEntry[]
  total: number
  matched: number
  offset: number
  limit: number
  coverage: { total: number; scanned: number; reviewed: number }
  counts: { observed: number; simulated: number; result: number; unknown: number }
  records: number
  pending_records: number
  issues: string[]
}

export const natureLabels: Record<CaseNature['kind'], string> = {
  observed: '实测数据', simulated: '蒙特卡洛数据', result: '估计结果', unknown: '性质待核实',
}

export const observationLabels: Record<CaseNature['observation'], string> = {
  complete: '完整样本', right_censored: '右删失', interval_censored: '区间删失',
  grouped: '分组数据', summary: '汇总数据', external: '外部数据', unknown: '观测规则待核实',
}

export function canCalculateDataset(record: CaseDataset): boolean {
  return Array.isArray(record.data) && record.data.length >= 3
    && record.data.every(value => typeof value === 'number' && Number.isFinite(value) && value > 0)
    && record.nature.observation === 'complete'
    && ['observed', 'simulated'].includes(record.nature.kind)
}

export function datasetText(record: CaseDataset): string {
  if (Array.isArray(record.data)) return record.data.join('\n')
  if (record.data.kind === 'table') return record.data.rows.map(row => row.map(value => value ?? '').join('\t')).join('\n')
  if (record.data.kind === 'figure') return record.data.caption || record.name
  return [record.data.description, record.data.url].filter(Boolean).join('\n')
}

export function datasetScale(record: CaseDataset): string {
  if (Array.isArray(record.data)) return `${record.data.length} 点`
  if (record.data.kind === 'table') return `${record.data.rows.length} 行表格`
  return record.data.kind === 'figure' ? '数据图' : '外部数据'
}
