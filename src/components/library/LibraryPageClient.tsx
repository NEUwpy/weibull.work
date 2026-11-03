"use client"

import React, { useState, useMemo, useEffect, useRef } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { FileText, Book, User, Search, Loader2 } from 'lucide-react'
import type { LibrarySearchResponse, LibraryVersion } from '@/lib/library-search-types'
import { librarySearchHitHref } from '@/lib/library-search-highlight'
import { libraryTypeLabel, matchesLibraryType, type LibraryTypeFilter } from '@/lib/library-types'
import { scheduleLibraryResultPrefetch } from '@/lib/library-document-client'
import { useLibrarySession } from '@/lib/library-auth-client'
import { LibraryMathMarkdown } from '@/components/shared/LibraryMathMarkdown'
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
  availableVersions: LibraryVersion[]
}

type TypeFilter = LibraryTypeFilter

interface LibraryPageClientProps {
  papers: PaperMetadata[]
}

const PAGE_SIZE = 10

function fitSearchInput(input: HTMLTextAreaElement) {
  input.style.height = 'auto'
  input.style.height = `${Math.min(input.scrollHeight, 168)}px`
  input.style.overflowY = input.scrollHeight > 168 ? 'auto' : 'hidden'
}

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
  const session = useLibrarySession()
  const router = useRouter()
  const searchParams = useSearchParams()
  const query = searchParams.get('q')?.trim() || ''
  const searchScope = searchParams.get('scope') === 'text' ? 'text' : 'auto'
  const isNumberQuery = searchScope !== 'text' && /^(?:\d{1,3}|\d{3}-\d{0,3})$/.test(query)
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all')
  const [draftQuery, setDraftQuery] = useState(query)
  const [offset, setOffset] = useState(0)
  const [retry, setRetry] = useState(0)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [searchResponse, setSearchResponse] = useState<LibrarySearchResponse | null>(null)
  const [mode, setMode] = useState<'search' | 'answer'>('search')
  const [answerRequest, setAnswerRequest] = useState<{ id: number; question: string } | null>(null)
  const searchInput = useRef<HTMLTextAreaElement>(null)

  useEffect(() => { if (searchInput.current) fitSearchInput(searchInput.current) }, [draftQuery])
  useEffect(() => {
    const input = searchInput.current
    if (!input) return
    let width = 0
    const observer = new ResizeObserver(entries => {
      const nextWidth = entries[0].contentRect.width
      if (nextWidth !== width) { width = nextWidth; fitSearchInput(input) }
    })
    observer.observe(input)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    setDraftQuery(query)
    setOffset(0)
    setMode('search')
  }, [query, searchScope])

  useEffect(() => {
    setSearchResponse(null)
    setSearchError('')
    if (!query || isNumberQuery || mode !== 'search') { setSearching(false); return }
    const controller = new AbortController()
    let active = true
    setSearching(true)
    const params = new URLSearchParams({ q: query, offset: String(offset), limit: String(PAGE_SIZE), type: typeFilter, scope: searchScope })
    fetch(`/api/library/search?${params}`, { signal: controller.signal, cache: 'no-store' })
      .then(async response => {
        const data = await response.json().catch(() => { throw new Error('检索暂时不可用，请稍后重试。') })
        if (!response.ok) throw new Error(data.error || '检索暂时不可用，请稍后重试。')
        if (active) setSearchResponse(data)
      })
      .catch(cause => { if (active && !controller.signal.aborted) setSearchError(cause instanceof Error && cause.name !== 'TypeError' ? cause.message : '检索连接失败，请稍后重试。') })
      .finally(() => { if (active) setSearching(false) })
    return () => { active = false; controller.abort() }
  }, [query, searchScope, isNumberQuery, offset, typeFilter, retry, mode])

  useEffect(() => {
    if (session.status !== 'authenticated' || searching || isNumberQuery || mode !== 'search' || !searchResponse?.results.length || searchResponse.query !== query) return
    return scheduleLibraryResultPrefetch(searchResponse.results)
  }, [session.status, searchResponse, searching, query, isNumberQuery, offset, typeFilter, retry, mode])

  function runSearch(scope: 'auto' | 'text' = 'auto') {
    const next = draftQuery.trim()
    setMode('search')
    setOffset(0)
    if (next === query && scope === searchScope) setRetry(value => value + 1)
    const url = new URL(window.location.href)
    if (next) url.searchParams.set('q', next)
    else url.searchParams.delete('q')
    if (next && scope === 'text') url.searchParams.set('scope', 'text')
    else url.searchParams.delete('scope')
    router.replace(url.pathname + url.search, { scroll: false })
  }

  function submitSearch(event: React.FormEvent) {
    event.preventDefault()
    runSearch()
  }

  function askQuestion() {
    const question = draftQuery.trim()
    if (!question) return
    setAnswerRequest(previous => ({ id: (previous?.id || 0) + 1, question }))
    setMode('answer')
  }

  function chooseType(type: TypeFilter) { setTypeFilter(type); setOffset(0) }

  function clearSearch() {
    setDraftQuery('')
    setOffset(0)
    const url = new URL(window.location.href)
    url.searchParams.delete('q')
    url.searchParams.delete('scope')
    router.replace(url.pathname + url.search, { scroll: false })
  }

  // Number queries filter the same cards used by the library homepage.
  const filteredPapers = useMemo<PaperMetadata[]>(() => {
    return papers.filter(paper => {
      if (isNumberQuery && !paper.slug.startsWith(query)) return false
      return matchesLibraryType(paper, typeFilter)
    })
  }, [papers, typeFilter, query, isNumberQuery])

  return (
    <main className="library-page flex-1 bg-neutral-50 min-h-screen">
      <div className="library-page-shell page-shell w-full max-w-[95%] xl:max-w-[1800px] mx-auto py-16 space-y-12">

        <div className="space-y-3">
          <form onSubmit={submitSearch} className="library-search-form flex items-start gap-3 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm focus-within:border-blue-300 focus-within:ring-2 focus-within:ring-blue-50">
            <Search size={21} className="library-search-icon shrink-0 text-slate-400" />
            <textarea ref={searchInput} aria-label="搜索文献" rows={1} maxLength={2000} value={draftQuery} onChange={event => setDraftQuery(event.target.value)}
              onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }}
              placeholder="输入编号、关键词、句子或问题…"
              className="min-w-0 flex-1 resize-none bg-transparent py-3 text-sm leading-6 text-slate-700 outline-none" />
            <div className="library-search-actions grid shrink-0 grid-cols-2 items-start gap-x-2 gap-y-1">
              <button type="submit" disabled={searching} className="library-search-primary rounded-xl bg-blue-600 px-5 py-3 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60">搜索</button>
              <button type="button" onClick={askQuestion} disabled={!draftQuery.trim()} className="library-search-primary rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-40">AI 问答</button>
              <button type="button" onClick={() => runSearch('text')} disabled={!draftQuery.trim()} className="col-start-2 rounded px-1 py-1 text-xs leading-5 text-slate-500 hover:text-slate-700 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500 disabled:cursor-not-allowed disabled:text-slate-300 disabled:no-underline">搜索该文本</button>
            </div>
          </form>
        </div>

        {mode === 'answer' && answerRequest && <ChatDialog key={answerRequest.id} request={answerRequest} />}

        {/* Type Filter Header */}
        {mode === 'search' && <div className="library-filters flex items-center justify-end">
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
              书籍 <span className="opacity-70 ml-1">{papers.filter(p => matchesLibraryType(p, 'book')).length}</span>
            </button>
            <button
              onClick={() => chooseType('paper')}
              className={cn(
                "px-5 py-2 text-sm font-medium rounded-full transition-all",
                typeFilter === 'paper'
                  ? "bg-emerald-600 text-white shadow-md shadow-emerald-500/20"
                  : "bg-white text-neutral-500 hover:text-neutral-800 hover:bg-neutral-100 border border-neutral-200"
              )}
            >
              论文 <span className="opacity-70 ml-1">{papers.filter(p => matchesLibraryType(p, 'paper')).length}</span>
            </button>
          </div>
        </div>}

        {mode === 'search' && isNumberQuery && <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4">
          <p role="status" className="text-sm leading-6 text-slate-500">“{query}” · 找到 <span className="font-semibold text-slate-800">{filteredPapers.length}</span> 篇文献</p>
          <button type="button" onClick={clearSearch} className="text-sm text-blue-600 hover:underline">浏览全部文献</button>
        </div>}

        {mode === 'search' && query && !isNumberQuery && <section aria-label="文献检索结果" className="library-search-results space-y-7">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4">
            <p role="status" className="text-sm leading-6 text-slate-500">
              {searching ? <span className="flex items-center gap-2"><Loader2 size={15} className="animate-spin" />正在检索文献正文…</span>
                : searchResponse ? <>“{query}” · 找到 <span className="font-semibold text-slate-800">{searchResponse.total}</span> 处相关内容</> : '检索结果'}
            </p>
            <button type="button" onClick={clearSearch} className="text-sm text-blue-600 hover:underline">浏览全部文献</button>
          </div>
          {searchError && <div role="alert" className="rounded-xl border border-rose-100 bg-rose-50 p-5 text-sm text-rose-700">{searchError}<button type="button" onClick={() => setRetry(value => value + 1)} className="ml-3 underline">重试</button></div>}
          {searchResponse?.results.map(hit => <article key={hit.id} className="max-w-5xl space-y-2 rounded-xl bg-white p-5 sm:p-6">
            <p className="text-xs leading-5 text-slate-500">{hit.slug} · {hit.version} · {hit.section}</p>
            <Link href={librarySearchHitHref(hit.href, searchResponse.terms)} className="inline-block text-lg font-medium leading-7 text-blue-800 hover:underline"><Highlight text={hit.title} terms={searchResponse.terms} /></Link>
            <LibraryMathMarkdown highlightTerms={searchResponse.terms} className="text-sm leading-7 text-slate-600 [&_p]:my-0">{hit.excerpt}</LibraryMathMarkdown>
          </article>)}
          {searchResponse && !searchResponse.total && <div className="rounded-xl bg-white px-6 py-12 text-sm leading-7 text-slate-500"><p>未找到相关内容。</p><p>可以缩短检索句，或换用术语的另一种中英文表达。</p></div>}
          {searchResponse && searchResponse.total > PAGE_SIZE && <nav aria-label="检索结果分页" className="flex flex-wrap items-center gap-4 pt-3 text-sm">
            <button type="button" disabled={offset === 0 || searching} onClick={() => setOffset(value => Math.max(0, value - PAGE_SIZE))} className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-slate-600 hover:bg-slate-50 disabled:opacity-40">上一页</button>
            <span className="text-slate-500">第 {Math.floor(offset / PAGE_SIZE) + 1} / {Math.ceil(searchResponse.total / PAGE_SIZE)} 页</span>
            <button type="button" disabled={offset + PAGE_SIZE >= searchResponse.total || searching} onClick={() => setOffset(value => value + PAGE_SIZE)} className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-slate-600 hover:bg-slate-50 disabled:opacity-40">下一页</button>
          </nav>}
        </section>}

        {/* Masonry Waterfall Layout */}
        {mode === 'search' && (!query || isNumberQuery) && <div className="library-cards columns-1 md:columns-2 lg:columns-3 gap-8">
          {filteredPapers.map(paper => {
            const hasVersions = paper.availableVersions.length > 0
            const card = (
              <article className={cn('rounded-xl border border-slate-200 transition-all duration-300', hasVersions ? 'bg-white hover:border-slate-300 hover:shadow-xl hover:shadow-slate-200/50' : 'bg-slate-50')}>
                <div className="p-7 space-y-5">
                  {/* Header: ID left, Publication & Year right */}
                  <div className="flex justify-between items-start gap-3">
                    <span className={cn('shrink-0 whitespace-nowrap text-sm font-normal italic font-serif', hasVersions ? 'text-rose-400' : 'text-slate-400')}>
                      {paper.slug}
                    </span>
                    <div className="min-w-0 text-right flex items-center gap-1.5">
                      {paper.type === '书籍' ? (
                        <Book size={13} className={cn('shrink-0', hasVersions ? 'text-amber-500' : 'text-slate-400')} />
                      ) : (
                        <FileText size={13} className={cn('shrink-0', hasVersions ? 'text-blue-500' : 'text-slate-400')} />
                      )}
                      <span className="text-xs text-slate-400">
                        {[libraryTypeLabel(paper.type), paper.short_publication || paper.publication, paper.year > 0 ? paper.year : null].filter(Boolean).join(' · ')}
                      </span>
                    </div>
                  </div>

                  {/* Title - Serif Academic Style, Justified */}
                  <h3 className={cn('text-xl font-semibold leading-relaxed transition-colors font-serif tracking-wide text-justify', hasVersions ? 'text-slate-800 group-hover:text-blue-800' : 'text-slate-500')}>
                    {paper.title}
                  </h3>

                  {/* Author with icon */}
                  <p className="text-sm text-slate-500 flex items-center gap-1.5">
                    <User size={13} className="text-slate-400 shrink-0" />
                    {paper.author}
                  </p>
                  {paper.doi && <p className="break-all font-mono text-xs text-slate-400">DOI: {paper.doi}</p>}

                  {/* Summary - justified */}
                  <LibraryMathMarkdown className={cn('library-card-summary line-clamp-4 text-sm leading-relaxed text-justify', hasVersions ? 'text-slate-600' : 'text-slate-500')}>
                    {paper.summary}
                  </LibraryMathMarkdown>

                  {/* Footer: Tags and availability */}
                  {(paper.tags.length > 0 || !hasVersions) && (
                    <div className="pt-4 border-t border-slate-100 space-y-3">
                      {!hasVersions && <p className="text-xs font-medium text-slate-500">资料待补齐</p>}
                      {paper.tags.length > 0 && <div className="flex flex-wrap gap-2">
                        {paper.tags.slice(0, 3).map(tag => (
                          <span
                            key={tag}
                            className={cn('text-xs px-2 py-0.5 rounded transition-colors', hasVersions ? 'text-blue-600 bg-blue-50 group-hover:bg-blue-100' : 'text-slate-500 bg-slate-100')}
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>}
                    </div>
                  )}
                </div>
              </article>
            )
            return hasVersions
              ? <Link key={paper.slug} href={`/library/${paper.slug}`} className="group block break-inside-avoid mb-8">{card}</Link>
              : <div key={paper.slug} aria-disabled="true" className="block break-inside-avoid mb-8">{card}</div>
          })}

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
