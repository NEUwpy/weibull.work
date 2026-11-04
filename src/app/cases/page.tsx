"use client"

import React, { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import Markdown from 'react-markdown'
import { Search, Copy, Download, Calculator, ChevronDown, ChevronLeft, ChevronRight, BookOpen } from 'lucide-react'
import { LibraryMathMarkdown } from '@/components/shared/LibraryMathMarkdown'
import { processLibraryContent, getLibraryMarkdownOptions } from '@/lib/library-markdown'
import { datasetText, natureLabels, observationLabels, type CatalogDataset, type CatalogSummary, type CaseCatalog } from '@/lib/case-datasets'
import '@/components/library/document.css'
import '@/components/library/table.css'
import 'katex/dist/katex.min.css'

const buttonStyle = 'inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40'

function TableData({ record }: { record: CatalogDataset }) {
  const data = record.data
  const processed = useMemo(() => processLibraryContent(!Array.isArray(data) && data.kind === 'table' ? data.html || '' : ''), [data])
  if (Array.isArray(data) || data.kind !== 'table') return null
  if (data.html) return <div className="library-document min-w-0">
    <Markdown {...getLibraryMarkdownOptions(processed, undefined, false)}>{processed.body}</Markdown>
  </div>
  return <div className="overflow-x-auto rounded-lg border border-slate-200"><table className="min-w-full border-collapse text-sm">
    <tbody>{data.rows.map((row, index) => <tr key={index}>{row.map((cell, column) => <td key={column} className="border border-slate-200 px-3 py-2 align-top">
      <LibraryMathMarkdown>{String(cell ?? '')}</LibraryMathMarkdown>
    </td>)}</tr>)}</tbody>
  </table></div>
}

function DatasetRow({ summary }: { summary: CatalogSummary }) {
  const [open, setOpen] = useState(false)
  const [record, setRecord] = useState<CatalogDataset | null>(null)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  useEffect(() => {
    if (!open || record) return
    const controller = new AbortController()
    setError('')
    fetch('/api/cases/catalog?id=' + encodeURIComponent(summary.id), { signal: controller.signal, cache: 'no-store' })
      .then(async response => { const data = await response.json(); if (!response.ok) throw new Error(data.error || '数据暂时无法读取。'); return data.item })
      .then(item => { if (!controller.signal.aborted) setRecord(item) })
      .catch(cause => { if (!controller.signal.aborted) setError(cause.message || '连接失败，请重试。') })
    return () => controller.abort()
  }, [open, record, summary.id, reload])
  return <details className="group rounded-xl border border-slate-200 bg-white" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-4 gap-y-2 px-4 py-4 sm:px-5 [&::-webkit-details-marker]:hidden">
      <ChevronDown size={18} className="shrink-0 text-slate-400 transition-transform group-open:rotate-180" />
      <span className="line-clamp-2 min-w-0 flex-1 basis-[220px] font-semibold text-slate-800"><LibraryMathMarkdown inline>{summary.name}</LibraryMathMarkdown></span>
      <span className="text-sm text-emerald-700">{natureLabels[summary.nature.kind]}</span>
      <span className="text-sm text-slate-500">{summary.scale}</span>
      <span className="text-sm text-slate-500">{summary.sources.map(source => source.paper_id).join(' · ') || '平台样本'}</span>
    </summary>
    {open && (record ? <DatasetDetails record={record} /> : <div className="border-t border-slate-100 p-5 text-sm text-slate-500">
      {error ? <div role="alert" className="flex flex-wrap items-center gap-3"><span>{error}</span><button className={buttonStyle} onClick={() => setReload(value => value + 1)}>重试</button></div> : '正在读取这份数据…'}
    </div>)}
  </details>
}

function DatasetDetails({ record }: { record: CatalogDataset }) {
  const [message, setMessage] = useState('')
  async function copy() {
    try { await navigator.clipboard.writeText(datasetText(record)); setMessage('已复制') }
    catch { setMessage('复制未完成，可下载 JSON') }
  }
  function download() {
    const content = { id: record.id, name: record.name, data: record.data, nature: record.nature,
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
          <p>{source.location}{source.relation === 'secondary' ? ' · 经该文转引' : ''}{source.available === false ? ' · 文献待补' : ''}</p>
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
  const [kind, setKind] = useState('all')
  const [offset, setOffset] = useState(0)
  const [catalog, setCatalog] = useState<CaseCatalog | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(() => {
      setLoading(true); setError('')
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
        <p className="mt-2 text-sm text-slate-500">{catalog ? '共 ' + catalog.total + ' 份数据 · 当前书单 ' + catalog.coverage.total + ' 篇资料，已扫描 ' + catalog.coverage.scanned + ' 篇，已核查 ' + catalog.coverage.reviewed + ' 篇' : '数据、性质与来源'}</p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[200px] flex-1"><Search size={18} className="absolute left-3 top-3 text-slate-400" /><input aria-label="搜索案例数据" value={query}
          onChange={event => { setQuery(event.target.value); setOffset(0) }} placeholder="搜索数据名称、文献编号或来源"
          className="min-h-[44px] w-full rounded-lg border border-slate-200 bg-white py-2 pl-10 pr-3 text-base outline-none focus:border-emerald-500" /></div>
        <select aria-label="数据性质" value={kind} onChange={event => { setKind(event.target.value); setOffset(0) }} className="min-h-[44px] rounded-lg border border-slate-200 bg-white px-3 text-base text-slate-700">
          <option value="all">全部性质</option>{Object.entries(natureLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </div>
      {error && <div role="alert" className="flex items-center gap-3 text-red-700"><p>{error}</p><button className={buttonStyle} onClick={() => setReload(value => value + 1)}>重试</button></div>}
      {catalog?.issues.length ? <details className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"><summary className="cursor-pointer">有 {catalog.issues.length} 项数据读取问题</summary><ul className="mt-2 space-y-1">{catalog.issues.map((issue, index) => <li key={index}>{issue}</li>)}</ul></details> : null}
      <div aria-busy={loading} className="space-y-3">
        {loading ? <p className="py-8 text-center text-slate-500">正在读取数据…</p> : catalog?.items.map(record => <DatasetRow key={record.id} summary={record} />)}
        {!loading && !error && !catalog?.items.length && <p className="py-8 text-center text-slate-500">没有匹配的数据。</p>}
      </div>
      {catalog && catalog.matched > 0 && <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-500">
        <p>{offset + 1}–{Math.min(offset + catalog.items.length, catalog.matched)} / {catalog.matched}</p>
        <div className="flex gap-2"><button className={buttonStyle} disabled={loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - catalog.limit))}><ChevronLeft size={16} />上一页</button>
          <button className={buttonStyle} disabled={loading || offset + catalog.limit >= catalog.matched} onClick={() => setOffset(offset + catalog.limit)}>下一页<ChevronRight size={16} /></button></div>
      </div>}
    </div>
  </main>
}
