"use client"

import React, { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import Markdown from 'react-markdown'
import { Search, Copy, Download, Calculator, ChevronDown, ChevronLeft, ChevronRight, BookOpen } from 'lucide-react'
import { LibraryMathMarkdown } from '@/components/shared/LibraryMathMarkdown'
import { processLibraryContent, getLibraryMarkdownOptions } from '@/lib/library-markdown'
import { datasetText, natureLabels, observationLabels, type CatalogDataset, type CatalogSummary, type CatalogGroupSummary, type CatalogGroupDetail, type CaseCatalog } from '@/lib/case-datasets'
import '@/components/library/document.css'
import '@/components/library/table.css'
import 'katex/dist/katex.min.css'

const buttonStyle = 'inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-base font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40'
const catalogKinds = ['observed', 'simulated', 'result'] as const
type CatalogKind = typeof catalogKinds[number]

function ReadStatus({ error, retry, children }: { error: string; retry: () => void; children: React.ReactNode }) {
  return <div className="border-t border-slate-100 p-5 text-sm text-slate-500">
    {error ? <div role="alert" className="flex flex-wrap items-center gap-3"><span>{error}</span><button className={buttonStyle} onClick={retry}>重试</button></div> : children}
  </div>
}

function TableData({ record }: { record: CatalogDataset }) {
  const data = record.data
  const processed = useMemo(() => processLibraryContent(!Array.isArray(data) && data.kind === 'table' ? data.html || '' : ''), [data])
  if (Array.isArray(data) || data.kind !== 'table') return null
  if (data.html) return <div className="library-document min-w-0 max-w-full overflow-x-auto">
    <Markdown {...getLibraryMarkdownOptions(processed, undefined, false)}>{processed.body}</Markdown>
  </div>
  return <div className="overflow-x-auto rounded-lg border border-slate-200"><table className="min-w-full border-collapse text-sm">
    <tbody>{data.rows.map((row, index) => <tr key={index}>{row.map((cell, column) => <td key={column} className="border border-slate-200 px-3 py-2 align-top">
      <LibraryMathMarkdown>{String(cell ?? '')}</LibraryMathMarkdown>
    </td>)}</tr>)}</tbody>
  </table></div>
}

function DatasetContent({ summary }: { summary: CatalogSummary }) {
  const [record, setRecord] = useState<CatalogDataset | null>(null)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  useEffect(() => {
    if (record) return
    const controller = new AbortController()
    setError('')
    fetch('/api/cases/catalog?id=' + encodeURIComponent(summary.id), { signal: controller.signal, cache: 'no-store' })
      .then(async response => { const data = await response.json(); if (!response.ok || !data.item) throw new Error(data.error || '数据暂时无法读取。'); return data.item })
      .then(item => { if (!controller.signal.aborted) setRecord(item) })
      .catch(cause => { if (!controller.signal.aborted) setError(cause.message || '连接失败，请重试。') })
    return () => controller.abort()
  }, [record, summary.id, reload])
  return record ? <DatasetDetails record={{ ...record, name: summary.name, role: summary.role || record.role }} />
    : <ReadStatus error={error} retry={() => setReload(value => value + 1)}>正在读取这份数据…</ReadStatus>
}

function DatasetRow({ summary, member = false }: { summary: CatalogSummary; member?: boolean }) {
  const [visited, setVisited] = useState(false)
  return <details className="group/dataset min-w-0 rounded-xl border border-slate-200 bg-white" onToggle={event => {
    if (event.target === event.currentTarget && event.currentTarget.open) setVisited(true)
  }}>
    <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-4 gap-y-2 px-4 py-4 sm:px-5 [&::-webkit-details-marker]:hidden">
      <ChevronDown size={18} className="shrink-0 text-slate-400 transition-transform group-open/dataset:rotate-180" />
      <span className="line-clamp-2 min-w-0 flex-1 basis-[220px] font-semibold text-slate-800"><LibraryMathMarkdown inline>{summary.name}</LibraryMathMarkdown></span>
      {summary.role === 'derived' && <span className="rounded-md bg-slate-100 px-2 py-1 text-sm text-slate-600">合并视图</span>}
      <span className="text-sm text-slate-500">{summary.scale}</span>
      {!member && <span className="text-sm text-slate-500">{Array.from(new Set(summary.sources.map(source => source.paper_id))).join(' · ') || '平台样本'}</span>}
    </summary>
    {visited && <DatasetContent summary={summary} />}
  </details>
}

function DatasetGroup({ summary }: { summary: CatalogGroupSummary }) {
  const [open, setOpen] = useState(false)
  const [group, setGroup] = useState<CatalogGroupDetail | null>(null)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  useEffect(() => {
    if (!open || group) return
    const controller = new AbortController()
    setError('')
    fetch('/api/cases/catalog?id=' + encodeURIComponent(summary.id), { signal: controller.signal, cache: 'no-store' })
      .then(async response => { const data = await response.json(); if (!response.ok || !data.group) throw new Error(data.error || '这组数据暂时无法读取。'); return data.group })
      .then(item => { if (!controller.signal.aborted) setGroup(item) })
      .catch(cause => { if (!controller.signal.aborted) setError(cause.message || '连接失败，请重试。') })
    return () => controller.abort()
  }, [open, group, summary.id, reload])

  return <details className="group/catalog min-w-0 rounded-xl border border-slate-200 bg-white" onToggle={event => {
    if (event.target === event.currentTarget) setOpen(event.currentTarget.open)
  }}>
    <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-4 gap-y-2 px-4 py-4 sm:px-5 [&::-webkit-details-marker]:hidden">
      <ChevronDown size={18} className="shrink-0 text-slate-400 transition-transform group-open/catalog:rotate-180" />
      <span className="min-w-0 flex-1 basis-[220px] font-semibold text-slate-800"><LibraryMathMarkdown inline>{summary.name}</LibraryMathMarkdown></span>
      <span className="text-sm text-emerald-700">{summary.scale}</span>
      <span className="text-sm text-slate-500">{Array.from(new Set(summary.sources.map(source => source.paper_id))).join(' · ') || '平台样本'}</span>
    </summary>
    {group ? <>
      {group.description && <LibraryMathMarkdown className="border-t border-slate-100 px-4 py-4 text-sm leading-6 text-slate-600 sm:px-5">{group.description}</LibraryMathMarkdown>}
      {group.members.length === 1 ? <DatasetContent summary={group.members[0]} />
        : <div className="min-w-0 space-y-3 border-t border-slate-100 bg-slate-50/70 p-3 sm:p-5">
          {group.members.map(member => <DatasetRow key={member.id} summary={member} member />)}
          {!group.members.length && <p className="text-sm text-slate-500">这组数据暂时没有可用内容。</p>}
        </div>}
    </> : open && <ReadStatus error={error} retry={() => setReload(value => value + 1)}>正在读取这组数据…</ReadStatus>}
  </details>
}

function DatasetDetails({ record }: { record: CatalogDataset }) {
  const [message, setMessage] = useState('')
  async function copy() {
    try { await navigator.clipboard.writeText(datasetText(record)); setMessage('已复制') }
    catch { setMessage('复制未完成，可下载 JSON') }
  }
  function download() {
    const content = { id: record.id, name: record.name, data: record.data, nature: record.nature, ...(record.role ? { role: record.role } : {}),
      sources: record.sources.map(({ paper_id, location, relation, original_reference, original_paper_id }) => ({ paper_id, location, relation, original_reference, original_paper_id })) }
    const href = URL.createObjectURL(new Blob([JSON.stringify(content, null, 2) + '\n'], { type: 'application/json;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = href
    link.download = record.id + '.json'
    link.click()
    URL.revokeObjectURL(href)
  }
  const data = record.data
  return <div className="min-w-0 space-y-5 border-t border-slate-100 px-4 py-5 sm:px-5">
      {record.role === 'derived' && <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">合并视图：由本组样本合并生成，不另计独立样本。</p>}
      <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
        <span>{observationLabels[record.nature.observation]}</span>
        {record.nature.quantity && <span>· {record.nature.quantity}</span>}
        <span>· 单位{record.nature.unit ? ' ' + record.nature.unit : '未注明'}</span>
        <span className="ml-auto break-all text-slate-400">{record.id}</span>
      </div>
      {record.nature.note && <LibraryMathMarkdown className="text-sm text-slate-600">{record.nature.note}</LibraryMathMarkdown>}
      {Array.isArray(data) ? <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-slate-50 p-4 font-mono text-base leading-8 text-slate-700">{data.join('，')}</pre>
        : data.kind === 'table' ? <TableData record={record} />
          : data.kind === 'figure' ? <figure className="min-w-0 space-y-2">
            {record.figure_url ? <a href={record.figure_url} target="_blank" rel="noreferrer" className="block"><img loading="lazy" src={record.figure_url} alt={data.caption || record.name} className="mx-auto max-h-[720px] max-w-full object-contain" /></a> : <p className="text-slate-500">原图请从下方文献出处查看。</p>}
            {data.caption && <figcaption><LibraryMathMarkdown className="text-sm text-slate-600">{data.caption}</LibraryMathMarkdown></figcaption>}
          </figure> : <div className="space-y-2 text-slate-600"><LibraryMathMarkdown>{data.description}</LibraryMathMarkdown>
            {data.url && /^https?:\/\//i.test(data.url) && <a className="break-all text-emerald-700 underline" href={data.url} target="_blank" rel="noreferrer">{data.url}</a>}
          </div>}
      <div className="space-y-3 border-t border-slate-100 pt-4">
        {record.sources.map((source, index) => <div key={source.paper_id + '-' + index} className="space-y-1 text-sm text-slate-600">
          <p><Link href={'/library/' + encodeURIComponent(source.paper_id) + '?version=' + encodeURIComponent('原文')} className="inline-flex items-start gap-1 text-emerald-700 hover:underline"><BookOpen size={15} className="mt-0.5 shrink-0" />
            <span>[{source.paper_id}] {source.title || '查看文献'}{source.year ? '（' + source.year + '）' : ''}</span>
          </Link></p>
          <LibraryMathMarkdown className="text-sm text-slate-600">{source.location + (source.relation === 'secondary' ? ' · 经该文转引' : '') + (source.available === false ? ' · 文献待补' : '')}</LibraryMathMarkdown>
          {source.original_reference && <LibraryMathMarkdown className="text-sm text-slate-500">{'原始文献线索　' + source.original_reference}</LibraryMathMarkdown>}
          {source.original_paper_id && <Link className="text-emerald-700 hover:underline" href={'/library/' + encodeURIComponent(source.original_paper_id)}>原始文献 [{source.original_paper_id}]</Link>}
        </div>)}
        {!record.sources.length && <p className="text-sm text-slate-500">平台保留样本，来源信息见原案例。</p>}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button className={buttonStyle} onClick={copy}><Copy size={16} />{Array.isArray(data) || data.kind === 'table' ? '复制数据' : '复制说明'}</button>
        <button className={buttonStyle} onClick={download}><Download size={16} />下载 JSON</button>
        {record.can_calculate && <Link className={buttonStyle} href={record.legacy_href?.includes('/groups/') ? '/?data=' + encodeURIComponent((data as number[]).join(',')) : '/?caseId=' + encodeURIComponent(record.id)}><Calculator size={16} />去计算</Link>}
        {record.legacy_href && <Link className={buttonStyle} href={record.legacy_href}>原案例</Link>}
        <span role="status" className="text-sm text-emerald-700">{message}</span>
      </div>
    </div>
}

export default function CasesPage() {
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState<CatalogKind>('observed')
  const [offset, setOffset] = useState(0)
  const [catalog, setCatalog] = useState<CaseCatalog | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError('')
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ q: query, kind, offset: String(offset), limit: '40' })
      fetch('/api/cases/catalog?' + params, { signal: controller.signal, cache: 'no-store' })
        .then(async response => { const data = await response.json(); if (!response.ok) throw new Error(data.error || '案例暂时无法加载。'); return data })
        .then(data => { if (!controller.signal.aborted) setCatalog(data) })
        .catch(cause => { if (!controller.signal.aborted) setError(cause.message || '连接失败，请重试。') })
        .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    }, 200)
    return () => { clearTimeout(timer); controller.abort() }
  }, [query, kind, offset, reload])

  return <main className="min-h-screen flex-1 bg-slate-50">
    <div className="page-shell mx-auto w-full max-w-[1500px] space-y-6 px-5 py-8 sm:px-10">
      <div><h1 className="text-2xl font-bold text-slate-800">案例数据库</h1>
        <p className="mt-2 text-sm leading-6 text-slate-500">按组查阅数据，展开查看样本、性质与文献来源。{catalog ? '已整理 ' + catalog.total + ' 组。' : ''}</p>
      </div>
      <nav aria-label="按数据性质浏览" className="grid grid-cols-3 gap-2 sm:gap-3">
        {catalogKinds.map(value => <button key={value} type="button" aria-pressed={kind === value}
          onClick={() => { setKind(value); setOffset(0) }}
          className={'flex min-h-[76px] min-w-0 flex-col items-center justify-center gap-1 rounded-xl border px-2 py-3 text-base font-semibold transition-colors sm:flex-row sm:gap-3 sm:px-4 ' + (kind === value
            ? 'border-emerald-600 bg-emerald-700 text-white'
            : 'border-slate-200 bg-white text-slate-600 hover:border-emerald-300 hover:bg-emerald-50')}>
          <span>{natureLabels[value]}</span>
          {catalog && <span className={'text-sm font-normal ' + (kind === value ? 'text-emerald-100' : 'text-slate-400')}>{catalog.counts[value]} 组</span>}
        </button>)}
      </nav>
      <div className="relative min-w-0"><Search size={18} className="absolute left-3 top-3 text-slate-400" /><input aria-label={'搜索' + natureLabels[kind]} value={query}
          onChange={event => { setQuery(event.target.value); setOffset(0) }} placeholder="搜索本类数据名称、文献编号或来源"
          className="min-h-[44px] w-full rounded-lg border border-slate-200 bg-white py-2 pl-10 pr-3 text-base outline-none focus:border-emerald-500" /></div>
      {error && <div role="alert" className="flex flex-wrap items-center gap-3 text-red-700"><p>{error}</p><button className={buttonStyle} onClick={() => setReload(value => value + 1)}>重试</button></div>}
      {catalog?.issues.length ? <details className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"><summary className="cursor-pointer">有 {catalog.issues.length} 项数据读取问题</summary><ul className="mt-2 space-y-1">{catalog.issues.map((issue, index) => <li key={index}>{issue}</li>)}</ul></details> : null}
      <div aria-busy={loading} className="space-y-3">
        {loading ? <p className="py-8 text-center text-slate-500">正在读取{natureLabels[kind]}…</p> : !error && catalog?.items.map(record => record.is_group
          ? <DatasetGroup key={record.id} summary={record} />
          : <DatasetRow key={record.id} summary={record} />)}
        {!loading && !error && !catalog?.items.length && <p className="py-8 text-center text-slate-500">{query ? '本类中没有匹配的数据组。' : '本类暂未整理数据组。'}</p>}
      </div>
      {!loading && !error && catalog && catalog.matched > 0 && <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-500">
        <p>第 {offset + 1}–{Math.min(offset + catalog.items.length, catalog.matched)} 组，共 {catalog.matched} 组</p>
        <div className="flex gap-2"><button className={buttonStyle} disabled={loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - catalog.limit))}><ChevronLeft size={16} />上一页</button>
          <button className={buttonStyle} disabled={loading || offset + catalog.limit >= catalog.matched} onClick={() => setOffset(offset + catalog.limit)}>下一页<ChevronRight size={16} /></button></div>
      </div>}
    </div>
  </main>
}
