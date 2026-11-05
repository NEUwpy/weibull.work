"use client"

import React, { useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import Markdown from 'react-markdown'
import { Search, Copy, Download, Calculator, ArrowLeft, ArrowUpRight, ChevronLeft, ChevronRight, BookOpen, Database, Dices, BarChart3, X } from 'lucide-react'
import { LibraryMathMarkdown } from '@/components/shared/LibraryMathMarkdown'
import { usePreviewDialog } from '@/components/shared/usePreviewDialog'
import { createPreviewHistory } from '@/lib/library-preview-history'
import { processLibraryContent, getLibraryMarkdownOptions } from '@/lib/library-markdown'
import { datasetText, natureLabels, observationLabels, type CatalogDataset, type CatalogEntry, type CatalogSummary, type CatalogGroupDetail, type CaseCatalog } from '@/lib/case-datasets'
import '@/components/library/document.css'
import '@/components/library/table.css'
import 'katex/dist/katex.min.css'
import './case-catalog.css'

const buttonStyle = 'inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-base font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40'
const catalogKinds = ['observed', 'simulated', 'result'] as const
type CatalogKind = typeof catalogKinds[number]
const caseIcons = { observed: Database, simulated: Dices, result: BarChart3, unknown: Database }

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

type CaseDetail = { item: CatalogDataset; group?: never } | { group: CatalogGroupDetail; item?: never }

function useCaseDetail(id: string) {
  const [detail, setDetail] = useState<CaseDetail | null>(null)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setError('')
    fetch('/api/cases/catalog?id=' + encodeURIComponent(id), { signal: controller.signal, cache: 'no-store' })
      .then(async response => { const data = await response.json(); if (!response.ok || (!data.group && !data.item)) throw new Error(data.error || '数据暂时无法读取。'); return data as CaseDetail })
      .then(data => { if (!controller.signal.aborted) setDetail(data) })
      .catch(cause => { if (!controller.signal.aborted) setError(cause.message || '连接失败，请重试。') })
    return () => controller.abort()
  }, [id, reload])
  return { detail, error, retry: () => setReload(value => value + 1) }
}

function CaseCard({ entry, onOpen }: { entry: CatalogEntry; onOpen: () => void }) {
  const kind = entry.nature.kind
  const Icon = caseIcons[kind]
  const description = entry.is_group ? entry.description : entry.nature.quantity || entry.nature.note
  return <button type="button" className="case-card" data-kind={kind} onClick={onOpen} aria-haspopup="dialog">
    <span className="case-card-kind"><Icon size={18} aria-hidden="true" />{natureLabels[kind]}</span>
    <span className="case-card-title">{entry.name}</span>
    {description && <span className="case-card-description">{description}</span>}
    <span className="case-card-footer"><span>{entry.scale}</span><ArrowUpRight size={19} aria-hidden="true" /></span>
  </button>
}

function DatasetContent({ summary, onLeave }: { summary: CatalogSummary; onLeave: () => void }) {
  const { detail, error, retry } = useCaseDetail(summary.id)
  return detail?.item ? <DatasetDetails record={{ ...detail.item, name: summary.name, role: summary.role || detail.item.role }} onLeave={onLeave} />
    : <ReadStatus error={error} retry={retry}>正在读取这份数据…</ReadStatus>
}

function GroupContent({ group, onLeave }: { group: CatalogGroupDetail; onLeave: () => void }) {
  const [selectedId, setSelectedId] = useState(group.members[0]?.id)
  const selected = group.members.find(member => member.id === selectedId)
  const scroll = useRef<HTMLDivElement>(null)
  function select(id: string) {
    setSelectedId(id)
    scroll.current?.scrollTo(0, 0)
  }

  return <>
    {group.description && <LibraryMathMarkdown className="case-group-note">{group.description}</LibraryMathMarkdown>}
    <div className={'case-group-body' + (group.members.length > 1 ? ' has-members' : '')}>
      {group.members.length > 1 && <>
        <nav className="case-members" aria-label="组内数据">
          <p>组内数据</p>
          {group.members.map(member => <button type="button" key={member.id} aria-pressed={selectedId === member.id} onClick={() => select(member.id)}>
            <span>{member.name}</span><small>{member.role === 'derived' ? '合并视图 · ' : ''}{member.scale}</small>
          </button>)}
        </nav>
        <label className="case-member-select">组内数据
          <select value={selectedId} onChange={event => select(event.target.value)}>
            {group.members.map(member => <option key={member.id} value={member.id}>{member.name}</option>)}
          </select>
        </label>
      </>}
      <div className="case-preview-scroll" ref={scroll}>
        {selected ? <DatasetContent key={selected.id} summary={selected} onLeave={onLeave} /> : <p className="p-5">这组数据暂时没有可用内容。</p>}
      </div>
    </div>
  </>
}

function CasePreview({ id, entry, onClose, onLeave }: { id: string; entry?: CatalogEntry; onClose: () => void; onLeave: () => void }) {
  const { dialog, closeButton } = usePreviewDialog(onClose)
  const { detail, error, retry } = useCaseDetail(id)
  const record = detail?.group || detail?.item || entry
  return <dialog {...dialog} className="case-preview" aria-labelledby="case-preview-title">
    <header className="case-preview-header">
      <button type="button" className="case-preview-back" onClick={onClose} aria-label="返回案例目录"><ArrowLeft size={20} aria-hidden="true" /></button>
      <div className="min-w-0">
        <p>{record ? natureLabels[record.nature.kind] : '案例数据'}</p>
        <h2 id="case-preview-title">{record?.name || '查看案例'}</h2>
      </div>
      <button type="button" ref={closeButton} className="case-preview-close" aria-label="关闭案例详情" onClick={onClose}><X size={23} aria-hidden="true" /></button>
    </header>
    {detail?.group ? <GroupContent group={detail.group} onLeave={onLeave} />
      : <div className="case-preview-scroll">
        {detail?.item ? <DatasetDetails record={detail.item} onLeave={onLeave} />
          : <ReadStatus error={error} retry={retry}>正在读取案例数据…</ReadStatus>}
      </div>}
  </dialog>
}

function DatasetDetails({ record, onLeave }: { record: CatalogDataset; onLeave: () => void }) {
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
  return <div className="min-w-0 space-y-5 px-4 pb-5 sm:px-6">
      <div className="case-data-toolbar">
        <h3>{record.name}</h3>
        {record.can_calculate && <Link className="case-calculate" replace onClick={event => {
          if (!event.defaultPrevented && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) onLeave()
        }} href={record.legacy_href?.includes('/groups/') ? '/?data=' + encodeURIComponent((data as number[]).join(',')) : '/?caseId=' + encodeURIComponent(record.id)}>
          <Calculator size={17} aria-hidden="true" />带入威布尔计算器
        </Link>}
      </div>
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
  const [previewId, setPreviewId] = useState<string | null>(null)
  const preview = useRef<ReturnType<typeof createPreviewHistory> | null>(null)
  useEffect(() => {
    const history = createPreviewHistory(window, setPreviewId, '__weibullCasePreview', id => /^[\w\u3400-\u9fff-]+$/.test(id))
    preview.current = history
    return () => { history.dispose(); preview.current = null }
  }, [])
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
        <p className="mt-2 text-sm leading-6 text-slate-600">查阅威布尔参数估计用的样本和研究结果。</p>
      </div>
      <nav aria-label="按数据性质浏览" className="case-filters">
        {catalogKinds.map(value => <button key={value} type="button" aria-pressed={kind === value}
          onClick={() => { setKind(value); setOffset(0) }}
          >
          <span>{natureLabels[value]}</span>
        </button>)}
      </nav>
      <div className="relative min-w-0"><Search size={18} className="absolute left-3 top-3 text-slate-400" /><input aria-label={'搜索' + natureLabels[kind]} value={query}
          onChange={event => { setQuery(event.target.value); setOffset(0) }} placeholder="搜索本类数据名称、文献编号或来源"
          className="min-h-[44px] w-full rounded-lg border border-slate-200 bg-white py-2 pl-10 pr-3 text-base outline-none focus:border-emerald-500" /></div>
      {error && <div role="alert" className="flex flex-wrap items-center gap-3 text-red-700"><p>{error}</p><button className={buttonStyle} onClick={() => setReload(value => value + 1)}>重试</button></div>}
      {catalog?.issues.length ? <details className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"><summary className="cursor-pointer">有 {catalog.issues.length} 项数据读取问题</summary><ul className="mt-2 space-y-1">{catalog.issues.map((issue, index) => <li key={index}>{issue}</li>)}</ul></details> : null}
      <div aria-busy={loading}>
        {loading ? <p className="py-8 text-center text-slate-500">正在读取{natureLabels[kind]}…</p>
          : !error && <div className="case-grid">{catalog?.items.map(entry => <CaseCard key={entry.id} entry={entry} onOpen={() => preview.current?.open(entry.id)} />)}</div>}
        {!loading && !error && !catalog?.items.length && <p className="py-8 text-center text-slate-500">{query ? '本类中没有匹配的数据组。' : '本类暂未整理数据组。'}</p>}
      </div>
      {!loading && !error && catalog && catalog.matched > catalog.limit && <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-500">
        <p>第 {offset + 1}–{Math.min(offset + catalog.items.length, catalog.matched)} 组，共 {catalog.matched} 组</p>
        <div className="flex gap-2"><button className={buttonStyle} disabled={loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - catalog.limit))}><ChevronLeft size={16} />上一页</button>
          <button className={buttonStyle} disabled={loading || offset + catalog.limit >= catalog.matched} onClick={() => setOffset(offset + catalog.limit)}>下一页<ChevronRight size={16} /></button></div>
      </div>}
    </div>
    {previewId && <CasePreview key={previewId} id={previewId} entry={catalog?.items.find(entry => entry.id === previewId)}
      onClose={() => preview.current?.close()} onLeave={() => preview.current?.leave()} />}
  </main>
}
