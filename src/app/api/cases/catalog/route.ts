import { NextResponse } from 'next/server'
import { getMarkdownCases, getAllGroups, getSubCases, type CaseItem } from '@/lib/cases_md'
import { listPapers } from '@/lib/server/literature'
import { datasetFigureUrl, readCaseCoverage, readCaseDatasetIndex, readCaseDatasetById, readCaseCatalogLayout } from '@/lib/server/case-datasets'
import { canCalculateDataset, datasetScale, type CaseDataset, type CatalogDataset, type CatalogSummary, type CaseSource,
  type CatalogEntry, type CatalogGroupDetail, type CaseCatalogGroup } from '@/lib/case-datasets'

export const dynamic = 'force-dynamic'

function legacyRecord(item: CaseItem, href: string): CatalogDataset {
  const values = item.data_raw.split(/\r?\n/).filter(line => line.trim()).map(line => Number(line.trim()))
  const simulated = item.type === '抽样样本'
  const record: CaseDataset = {
    id: item.id, name: item.title, data: values,
    nature: { kind: simulated ? 'simulated' : 'observed', observation: 'complete',
      note: [simulated ? '平台生成的威布尔抽样数据。' : '', item.description,
        item.related_paper_slug ? `关联方法文献 [${item.related_paper_slug}]，不表示样本摘自该文。` : ''].filter(Boolean).join(' ') },
    sources: [],
  }
  return { ...record, can_calculate: canCalculateDataset(record), legacy_href: href }
}

function summarize(record: CatalogDataset): CatalogSummary {
  const { data, ...summary } = record
  return { ...summary, scale: datasetScale(record) }
}

function groupDetail(group: Omit<CaseCatalogGroup, 'members'>, members: CatalogSummary[]): CatalogGroupDetail {
  const samples = members.filter(member => member.role === 'sample' || (member.can_calculate && member.role !== 'derived')).length
  const derived = members.filter(member => member.role === 'derived').length
  const materials = members.length - samples - derived
  const parts = [samples ? `${samples} 组样本` : '', derived ? `${derived} 份合并视图` : '', materials ? `${materials} 份${group.kind === 'result' ? '结果' : ''}材料` : ''].filter(Boolean)
  const sources = new Map<string, CaseSource>()
  for (const member of members) for (const source of member.sources) {
    const key = `${source.paper_id}:${source.location}:${source.relation}`
    if (!sources.has(key)) sources.set(key, source)
  }
  return { id: group.id, name: group.name, is_group: true, can_calculate: false,
    nature: { kind: group.kind, observation: 'grouped' }, scale: parts.join(' · '),
    member_count: members.length, description: group.description, sources: Array.from(sources.values()), members }
}

export async function GET(request: Request) {
  try {
    const url = new URL(request.url)
    const term = (url.searchParams.get('q') || '').trim().toLocaleLowerCase()
    const requestedId = url.searchParams.get('id')
    const kind = url.searchParams.get('kind') || 'all'
    const limit = Math.min(100, Math.max(1, Number.parseInt(url.searchParams.get('limit') || '40', 10) || 40))
    const offset = Math.max(0, Number.parseInt(url.searchParams.get('offset') || '0', 10) || 0)
    const external = readCaseDatasetIndex()
    const layout = readCaseCatalogLayout()
    const issues = [...external.issues]
    let papers: ReturnType<typeof listPapers> = []
    try { papers = listPapers() } catch { issues.push('文献题录暂不可用，来源编号仍保留。') }
    const paperById = new Map(papers.map(paper => [paper.slug, paper]))
    const publicSources = (sources: CaseSource[]) => sources.map(source => {
      const paper = paperById.get(source.paper_id)
      return { paper_id: source.paper_id, location: source.location, relation: source.relation,
        original_reference: source.original_reference, original_paper_id: source.original_paper_id,
        title: paper?.display_title || paper?.title, author: paper?.author, year: paper?.year, available: !!paper }
    })
    const summaries = new Map<string, CatalogSummary>(external.records.map(record => [record.id, {
      id: record.id, name: record.name, nature: record.nature, sources: publicSources(record.sources),
      can_calculate: record.can_calculate, scale: record.scale,
    }]))
    const legacy = new Map<string, CatalogDataset>()
    const records: CatalogEntry[] = []
    const groups = new Map<string, CatalogGroupDetail>()
    const groupedIds = new Set<string>()
    for (const definition of layout.groups) {
      const members = definition.members.flatMap(member => {
        const record = summaries.get(member.id)
        if (!record) return []
        groupedIds.add(member.id)
        return [{ ...record, name: member.name, role: member.role }]
      })
      if (members.length) groups.set(definition.id, groupDetail(definition, members))
    }
    for (const item of getMarkdownCases()) {
      if (summaries.has(item.id)) continue
      const record = legacyRecord(item, `/cases/${encodeURIComponent(item.id)}`)
      legacy.set(record.id, record)
      records.push(summarize(record))
    }
    for (const group of getAllGroups()) {
      const members = getSubCases(group.id).map((item, index) => {
        const record = legacyRecord({ ...item, title: `第${index + 1}次抽样`, type: group.type,
          related_paper_slug: item.related_paper_slug || group.related_paper },
          `/cases/groups/${encodeURIComponent(group.id)}/${encodeURIComponent(item.id)}`)
        legacy.set(record.id, record)
        return { ...summarize(record), role: 'sample' as const }
      })
      const parameters = group.true_params
      const description = [group.description, parameters ? `生成参数：形状 β=${parameters.beta}，尺度 η=${parameters.eta}，位置 γ=${parameters.gamma}。` : '',
        '平台生成的重复抽样；关联文献仅说明方法。'].filter(Boolean).join(' ')
      groups.set(group.id, groupDetail({ id: group.id, name: group.title,
        kind: group.type === '抽样样本' ? 'simulated' : 'observed', description }, members))
    }
    for (const record of Array.from(summaries.values())) if (!groupedIds.has(record.id)) records.push(record)
    for (const group of Array.from(groups.values())) {
      const { members, ...summary } = group
      records.push(summary)
    }
    const searchable = (record: CatalogEntry): string => [record.id, record.name, record.nature.quantity, record.nature.note,
      ...(record.is_group ? [record.description] : []),
      ...record.sources.flatMap(source => [source.paper_id, source.title, source.author, source.location, source.original_reference])]
      .filter(Boolean).join(' ').toLocaleLowerCase()
    const matches = records.filter(record => (kind === 'all' || record.nature.kind === kind)
      && (!term || searchable(record).includes(term)
        || (record.is_group && groups.get(record.id)!.members.some(member => searchable(member).includes(term)))))
    const natureOrder = { observed: 0, simulated: 1, result: 2, unknown: 3 }
    matches.sort((left, right) => natureOrder[left.nature.kind] - natureOrder[right.nature.kind]
      || left.id.localeCompare(right.id, 'en', { numeric: true }))
    if (requestedId) {
      const group = groups.get(requestedId)
      if (group) return NextResponse.json({ group }, { headers: { 'Cache-Control': 'no-store' } })
      const dataset = readCaseDatasetById(requestedId)
      const record = dataset ? { id: dataset.id, name: dataset.name, data: dataset.data, nature: dataset.nature,
        sources: publicSources(dataset.sources), role: dataset.role, can_calculate: canCalculateDataset(dataset), figure_url: datasetFigureUrl(dataset) }
        : legacy.get(requestedId)
      return record ? NextResponse.json({ item: record }, { headers: { 'Cache-Control': 'no-store' } })
        : NextResponse.json({ error: '案例不存在或尚未整理入目录。' }, { status: 404 })
    }
    const covered = readCaseCoverage()
    const counts = { observed: 0, simulated: 0, result: 0, unknown: 0 }
    for (const record of records) counts[record.nature.kind]++
    return NextResponse.json({ items: matches.slice(offset, offset + limit), total: records.length, matched: matches.length, offset, limit,
      counts, records: summaries.size + legacy.size, pending_records: external.pending_records,
      coverage: { total: papers.length, scanned: papers.filter(paper => covered.scanned.has(paper.slug)).length,
        reviewed: papers.filter(paper => covered.reviewed.has(paper.slug)).length }, issues },
      { headers: { 'Cache-Control': 'no-store' } })
  } catch (error) {
    console.error('Failed to read case catalog:', error)
    return NextResponse.json({ error: '案例数据暂时无法读取。' }, { status: 500 })
  }
}
