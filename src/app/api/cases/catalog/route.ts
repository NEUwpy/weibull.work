import { NextResponse } from 'next/server'
import { getMarkdownCases, getAllGroups, getSubCases, type CaseItem } from '@/lib/cases_md'
import { listPapers } from '@/lib/server/literature'
import { datasetFigureUrl, readCaseCoverage, readCaseDatasetIndex, readCaseDatasetById } from '@/lib/server/case-datasets'
import { canCalculateDataset, datasetScale, type CaseDataset, type CatalogDataset, type CatalogSummary, type CaseSource } from '@/lib/case-datasets'

export const dynamic = 'force-dynamic'

function legacyRecord(item: CaseItem, href: string): CatalogDataset {
  const values = item.data_raw.split(/\r?\n/).filter(line => line.trim()).map(line => Number(line.trim()))
  const record: CaseDataset = {
    id: item.id, name: item.title, data: values,
    nature: {
      kind: item.type === '抽样样本' ? 'simulated' : 'observed',
      observation: 'complete', note: [item.description, item.related_paper_slug ? `关联方法文献 [${item.related_paper_slug}]` : ''].filter(Boolean).join('。'),
    },
    sources: [],
  }
  return { ...record, can_calculate: canCalculateDataset(record), legacy_href: href }
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
    const issues = [...external.issues]
    let papers: ReturnType<typeof listPapers> = []
    try { papers = listPapers() } catch { issues.push('文献题录暂不可用，来源编号仍保留。') }
    const paperById = new Map(papers.map(paper => [paper.slug, paper]))
    const publicSources = (sources: CaseSource[]) => sources.map(source => ({
        paper_id: source.paper_id, location: source.location, relation: source.relation,
        original_reference: source.original_reference, original_paper_id: source.original_paper_id,
    }))
    const records: CatalogSummary[] = external.records.map(record => ({
      id: record.id, name: record.name, nature: record.nature, sources: publicSources(record.sources),
      can_calculate: record.can_calculate, scale: record.scale,
    }))
    const legacy: CatalogDataset[] = []
    const ids = new Set(records.map(record => record.id))
    for (const item of getMarkdownCases()) {
      if (!ids.has(item.id)) legacy.push(legacyRecord(item, `/cases/${encodeURIComponent(item.id)}`))
    }
    for (const group of getAllGroups()) {
      for (const item of getSubCases(group.id)) {
        if (!ids.has(item.id)) legacy.push(legacyRecord({ ...item, type: group.type, related_paper_slug: item.related_paper_slug || group.related_paper },
          `/cases/groups/${encodeURIComponent(group.id)}/${encodeURIComponent(item.id)}`))
      }
    }
    records.push(...legacy.map(record => {
      const { data, ...summary } = record
      return { ...summary, scale: datasetScale(record) }
    }))
    const natureOrder = { observed: 0, simulated: 1, result: 2, unknown: 3 }
    records.sort((left, right) => Number(right.can_calculate) - Number(left.can_calculate)
      || natureOrder[left.nature.kind] - natureOrder[right.nature.kind]
      || left.id.localeCompare(right.id, 'en', { numeric: true }))
    const matches = records.filter(record => (kind === 'all' || record.nature.kind === kind)
      && (!term || [record.id, record.name, record.nature.quantity, record.nature.note,
        ...record.sources.flatMap(source => [source.paper_id, source.location, source.original_reference, paperById.get(source.paper_id)?.title])]
        .filter(Boolean).join(' ').toLocaleLowerCase().includes(term)))
    const withSources = (record: CatalogDataset | CatalogSummary) => ({ ...record,
      sources: record.sources.map(source => {
        const paper = paperById.get(source.paper_id)
        return { ...source, title: paper?.display_title || paper?.title, author: paper?.author, year: paper?.year, available: !!paper }
      }),
    })
    if (requestedId) {
      const dataset = readCaseDatasetById(requestedId)
      const record = dataset ? { id: dataset.id, name: dataset.name, data: dataset.data,
        nature: dataset.nature, sources: publicSources(dataset.sources), can_calculate: canCalculateDataset(dataset),
        figure_url: datasetFigureUrl(dataset) } : legacy.find(record => record.id === requestedId)
      return record ? NextResponse.json({ item: withSources(record) }, { headers: { 'Cache-Control': 'no-store' } })
        : NextResponse.json({ error: '案例不存在。' }, { status: 404 })
    }
    const items = matches.slice(offset, offset + limit).map(withSources)
    const covered = readCaseCoverage()
    return NextResponse.json({ items, total: records.length, matched: matches.length, offset, limit,
      coverage: { total: papers.length, scanned: papers.filter(paper => covered.scanned.has(paper.slug)).length,
        reviewed: papers.filter(paper => covered.reviewed.has(paper.slug)).length }, issues },
      { headers: { 'Cache-Control': 'no-store' } })
  } catch (error) {
    console.error('Failed to read case catalog:', error)
    return NextResponse.json({ error: '案例数据暂时无法读取。' }, { status: 500 })
  }
}
