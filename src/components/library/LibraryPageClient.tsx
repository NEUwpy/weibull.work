"use client"

import React, { useState, useMemo, useEffect } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { ArrowRight, FileText, Book, User, Search, Loader2 } from 'lucide-react'
import type { LibrarySearchResponse } from '@/lib/library-search-types'
import { cn } from '@/lib/utils'
import { ChatDialog } from '@/components/chat'
import './responsive.css'


type PaperMetadata = {
  slug: string
  title: string
  title_en?: string
  author: string
  doi?: string
  affiliation?: string
  publication?: string
  short_publication?: string
  type?: string
  year: number
  tags: string[]
  summary: string
  related_method_id?: string
}

type TypeFilter = 'all' | 'book' | 'journal-conf'

interface LibraryPageClientProps {
  papers: PaperMetadata[]
}

const PAGE_SIZE = 10

function Highlight({ text, terms }: { text: string; terms: string[] }) {
  const words = Array.from(new Set(terms.filter(term => term.length > 1).slice(0, 30))).sort((a, b) => b.length - a.length)
  if (!words.length) return <>{text}</>
  const escaped = words.map(word => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const pattern = new RegExp(`(${escaped.join('|')})`, 'gi')
  const known = new Set(words.map(word => word.toLowerCase()))
  return <>{text.split(pattern).map((part, index) => known.has(part.toLowerCase())
    ? <mark key={index} className="rounded bg-amber-100 px-0.5 text-inherit">{part}</mark>
    : <React.Fragment key={index}>{part}</React.Fragment>)}</>
}

export function LibraryPageClient({ papers }: LibraryPageClientProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const query = searchParams.get('q')?.trim() || ''
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all')
  const [draftQuery, setDraftQuery] = useState(query)
  const [offset, setOffset] = useState(0)
  const [retry, setRetry] = useState(0)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [searchResponse, setSearchResponse] = useState<LibrarySearchResponse | null>(null)

  useEffect(() => {
    setDraftQuery(query)
    setOffset(0)
  }, [query])

  useEffect(() => {
    setSearchResponse(null)
    setSearchError('')
    if (!query) { setSearching(false); return }
    const controller = new AbortController()
    let active = true
    setSearching(true)
    const params = new URLSearchParams({ q: query, offset: String(offset), limit: String(PAGE_SIZE), type: typeFilter })
    fetch(`/api/library/search?${params}`, { signal: controller.signal, cache: 'no-store' })
      .then(async response => {
        const data = await response.json().catch(() => { throw new Error('检索暂时不可用，请稍后重试。') })
        if (!response.ok) throw new Error(data.error || '检索暂时不可用，请稍后重试。')
        if (active) setSearchResponse(data)
      })
      .catch(cause => { if (active && !controller.signal.aborted) setSearchError(cause instanceof Error && cause.name !== 'TypeError' ? cause.message : '检索连接失败，请稍后重试。') })
      .finally(() => { if (active) setSearching(false) })
    return () => { active = false; controller.abort() }
  }, [query, offset, typeFilter, retry])

  function submitSearch(event: React.FormEvent) {
    event.preventDefault()
    const next = draftQuery.trim()
    setOffset(0)
    if (next === query) setRetry(value => value + 1)
    const url = new URL(window.location.href)
    if (next) url.searchParams.set('q', next)
    else url.searchParams.delete('q')
    router.replace(url.pathname + url.search, { scroll: false })
  }

  function chooseType(type: TypeFilter) { setTypeFilter(type); setOffset(0) }

  // Filter papers based on type
  const filteredPapers = useMemo<PaperMetadata[]>(() => {
    if (typeFilter === 'all') return papers

    return papers.filter(paper => {
      const paperType = paper.type || '其它'
      if (typeFilter === 'book') {
        return paperType === '书籍'
      } else if (typeFilter === 'journal-conf') {
        return paperType === '期刊' || paperType === '会议'
      }
      return true
    })
  }, [papers, typeFilter])

  return (
    <main className="library-page flex-1 bg-neutral-50 min-h-screen">
      <div className="page-shell w-full max-w-[92%] xl:max-w-[1600px] mx-auto pl-[4.5rem] pr-[3rem] py-16 space-y-12">

        {/* AI Chat Dialog */}
        <ChatDialog />

        <div className="space-y-3">
          <form onSubmit={submitSearch} className="library-search-form flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3 pl-5 shadow-sm focus-within:border-blue-300 focus-within:ring-2 focus-within:ring-blue-50">
            <Search size={21} className="shrink-0 text-slate-400" />
            <textarea aria-label="搜索文献" rows={2} maxLength={2000} value={draftQuery} onChange={event => setDraftQuery(event.target.value)}
              onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }}
              placeholder="搜索名词、句子或一小段话…"
              className="min-w-0 flex-1 resize-none bg-transparent py-2 text-sm leading-6 text-slate-700 outline-none" />
            <button type="submit" disabled={searching} className="shrink-0 rounded-xl bg-blue-600 px-5 py-3 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60">搜索</button>
          </form>
          <p className="px-1 text-xs leading-5 text-slate-500">搜索正文段落，也支持题名、作者、DOI 和编号；中英文资料均可检索。</p>
        </div>

        {/* Type Filter Header */}
        <div className="library-filters flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-1 h-8 bg-neutral-800 rounded-full" />
            <span className="text-sm font-medium text-neutral-500 tracking-wide uppercase">Filter</span>
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => chooseType('all')}
              className={cn(
                "px-5 py-2 text-sm font-medium rounded-full transition-all",
                typeFilter === 'all'
                  ? "bg-emerald-600 text-white shadow-md shadow-emerald-500/20"
                  : "bg-white text-neutral-500 hover:text-neutral-800 hover:bg-neutral-100 border border-neutral-200"
              )}
            >
              全部 <span className="opacity-70 ml-1">{papers.length}</span>
            </button>
            <button
              onClick={() => chooseType('book')}
              className={cn(
                "px-5 py-2 text-sm font-medium rounded-full transition-all",
                typeFilter === 'book'
                  ? "bg-emerald-600 text-white shadow-md shadow-emerald-500/20"
                  : "bg-white text-neutral-500 hover:text-neutral-800 hover:bg-neutral-100 border border-neutral-200"
              )}
            >
              书籍 <span className="opacity-70 ml-1">{papers.filter(p => (p.type || '其它') === '书籍').length}</span>
            </button>
            <button
              onClick={() => chooseType('journal-conf')}
              className={cn(
                "px-5 py-2 text-sm font-medium rounded-full transition-all",
                typeFilter === 'journal-conf'
                  ? "bg-emerald-600 text-white shadow-md shadow-emerald-500/20"
                  : "bg-white text-neutral-500 hover:text-neutral-800 hover:bg-neutral-100 border border-neutral-200"
              )}
            >
              期刊 & 会议 <span className="opacity-70 ml-1">{papers.filter(p => (p.type || '其它') === '期刊' || (p.type || '其它') === '会议').length}</span>
            </button>
          </div>
        </div>

        {query && <section aria-label="文献检索结果" className="library-search-results space-y-7">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4">
            <p role="status" className="text-sm leading-6 text-slate-500">
              {searching ? <span className="flex items-center gap-2"><Loader2 size={15} className="animate-spin" />正在检索文献正文…</span>
                : searchResponse ? <>“{query}” · 找到 <span className="font-semibold text-slate-800">{searchResponse.total}</span> 处相关内容</> : '检索结果'}
            </p>
            <button type="button" onClick={() => { setDraftQuery(''); setOffset(0); const url = new URL(window.location.href); url.searchParams.delete('q'); router.replace(url.pathname + url.search, { scroll: false }) }} className="text-sm text-blue-600 hover:underline">浏览全部文献</button>
          </div>
          {searchError && <div role="alert" className="rounded-xl border border-rose-100 bg-rose-50 p-5 text-sm text-rose-700">{searchError}<button type="button" onClick={() => setRetry(value => value + 1)} className="ml-3 underline">重试</button></div>}
          {searchResponse?.results.map(hit => <article key={hit.id} className="max-w-5xl space-y-2 rounded-xl bg-white p-5 sm:p-6">
            <p className="text-xs leading-5 text-slate-500">{hit.slug} · {hit.version} · {hit.section}</p>
            <Link href={hit.href} className="inline-block text-lg font-medium leading-7 text-blue-800 hover:underline"><Highlight text={hit.title} terms={searchResponse.terms} /></Link>
            <p className="whitespace-pre-wrap text-sm leading-7 text-slate-600"><Highlight text={hit.excerpt} terms={searchResponse.terms} /></p>
            <Link href={hit.href} className="inline-flex items-center gap-1 pt-1 text-xs font-medium text-blue-600 hover:underline">查看所在段落<ArrowRight size={13} /></Link>
          </article>)}
          {searchResponse && !searchResponse.total && <div className="rounded-xl bg-white px-6 py-12 text-sm leading-7 text-slate-500"><p>未找到相关内容。</p><p>可以缩短检索句，或换用术语的另一种中英文表达。</p></div>}
          {searchResponse && searchResponse.total > PAGE_SIZE && <nav aria-label="检索结果分页" className="flex flex-wrap items-center gap-4 pt-3 text-sm">
            <button type="button" disabled={offset === 0 || searching} onClick={() => setOffset(value => Math.max(0, value - PAGE_SIZE))} className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-slate-600 hover:bg-slate-50 disabled:opacity-40">上一页</button>
            <span className="text-slate-500">第 {Math.floor(offset / PAGE_SIZE) + 1} / {Math.ceil(searchResponse.total / PAGE_SIZE)} 页</span>
            <button type="button" disabled={offset + PAGE_SIZE >= searchResponse.total || searching} onClick={() => setOffset(value => value + PAGE_SIZE)} className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-slate-600 hover:bg-slate-50 disabled:opacity-40">下一页</button>
          </nav>}
        </section>}

        {/* Masonry Waterfall Layout */}
        {!query && <div className="library-cards columns-1 md:columns-2 lg:columns-3 gap-8">
          {filteredPapers.map(paper => (
            <Link
              key={paper.slug}
              href={`/library/${paper.slug}`}
              className="group block break-inside-avoid mb-8"
            >
              <article className="bg-white rounded-xl border border-slate-200 hover:border-slate-300 hover:shadow-xl hover:shadow-slate-200/50 transition-all duration-300">
                <div className="p-7 space-y-5">
                  {/* Header: ID left, Publication & Year right */}
                  <div className="flex justify-between items-start">
                    <span className="text-sm font-normal italic text-rose-400 font-serif">
                      {paper.slug}
                    </span>
                    <div className="text-right flex items-center gap-1.5">
                      {paper.type === '书籍' ? (
                        <Book size={13} className="text-amber-500 shrink-0" />
                      ) : (
                        <FileText size={13} className="text-blue-500 shrink-0" />
                      )}
                      <span className="text-xs text-slate-400">
                        {paper.short_publication || paper.publication} · {paper.year}
                      </span>
                    </div>
                  </div>

                  {/* Title - Serif Academic Style, Justified */}
                  <h3 className="text-xl font-semibold text-slate-800 leading-relaxed group-hover:text-blue-800 transition-colors font-serif tracking-wide text-justify">
                    {paper.title}
                  </h3>

                  {/* Author with icon */}
                  <p className="text-sm text-slate-500 flex items-center gap-1.5">
                    <User size={13} className="text-slate-400 shrink-0" />
                    {paper.author}
                  </p>
                  {paper.doi && <p className="break-all font-mono text-xs text-slate-400">DOI: {paper.doi}</p>}

                  {/* Summary - justified */}
                  <p className="text-sm text-slate-600 leading-relaxed text-justify">
                    {paper.summary}
                  </p>

                  {/* Footer: Tags only */}
                  {paper.tags.length > 0 && (
                    <div className="pt-4 border-t border-slate-100">
                      <div className="flex flex-wrap gap-2">
                        {paper.tags.slice(0, 3).map(tag => (
                          <span
                            key={tag}
                            className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded group-hover:bg-blue-100 transition-colors"
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </article>
            </Link>
          ))}

          {/* Empty State */}
          {filteredPapers.length === 0 && (
            <div className="break-inside-avoid col-span-full py-32 text-center">
              <p className="text-neutral-400 text-sm">未找到匹配的文献</p>
            </div>
          )}
        </div>}

      </div>
    </main>
  )
}
