"use client"

import React, { useState, useMemo, useEffect } from 'react'
import { LibraryDocumentLink as Link } from './LibraryDocumentDialog'
import { useRouter, useSearchParams } from 'next/navigation'
import { Loader2, LayoutGrid, FileText, BookOpen, ArrowDownWideNarrow } from 'lucide-react'
import type { LibrarySearchResponse, LibraryVersion } from '@/lib/library-search-types'
import { librarySearchHitHref } from '@/lib/library-search-highlight'
import { matchesLibraryType, type LibraryTypeFilter } from '@/lib/library-types'
import { compareLibraryOrder, isLibrarySort, librarySortOptions, type LibrarySort } from '@/lib/library-sort'
import { libraryCategoryGroups, matchesLibraryCategory, validLibraryCategoryFilter, type LibraryCategory } from '@/lib/library-categories'
import { scheduleLibraryResultPrefetch } from '@/lib/library-document-client'
import { useLibrarySession } from '@/lib/library-auth-client'
import { LibraryMathMarkdown } from '@/components/shared/LibraryMathMarkdown'
import { LibraryCard } from './LibraryCard'
import { LibraryMasonry } from './LibraryMasonry'
import { LibraryFilterMenu, type LibraryFilterOption } from './LibraryFilterMenu'
import { LibraryPaperTitle } from './LibraryPaperTitle'
import type { LibraryTitlePresentation } from '@/lib/library-titles'
import { cn } from '@/lib/utils'
import { CatalogSearchForm } from '@/components/shared/CatalogSearchForm'
import { ChatDialog } from '@/components/chat'
import { readLibraryChatSession, setLibraryChatActive, startLibraryChat } from '@/lib/library-chat-session'
import './responsive.css'


type PaperMetadata = LibraryTitlePresentation & {
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
  category?: LibraryCategory
}

type TypeFilter = LibraryTypeFilter

interface LibraryPageClientProps {
  papers: PaperMetadata[]
}

const PAGE_SIZE = 10

export function LibraryPageClient({ papers }: LibraryPageClientProps) {
  const session = useLibrarySession()
  const router = useRouter()
  const searchParams = useSearchParams()
  const query = searchParams.get('q')?.trim() || ''
  const searchScope = searchParams.get('scope') === 'text' ? 'text' : 'auto'
  const categoryFilter = searchParams.get('category') || 'all'
  const isNumberQuery = searchScope !== 'text' && /^(?:\d{1,3}|\d{3}-\d{0,3})$/.test(query)
  const browsingCards = !query || isNumberQuery
  const requestedSort = searchParams.get('sort') || ''
  const sortMode: LibrarySort = isLibrarySort(requestedSort) && (!browsingCards || requestedSort !== 'relevance')
    ? requestedSort : browsingCards ? 'year-desc' : 'relevance'
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all')
  const [draftQuery, setDraftQuery] = useState(query)
  const [offset, setOffset] = useState(0)
  const [retry, setRetry] = useState(0)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [searchResponse, setSearchResponse] = useState<LibrarySearchResponse | null>(null)
  const [mode, setMode] = useState<'search' | 'answer'>('search')
  const [answerRequest, setAnswerRequest] = useState<{ id: number; question: string } | null>(null)
  const categoryGroups = useMemo(() => libraryCategoryGroups(papers), [papers])
  const categoryOptions = useMemo<LibraryFilterOption[]>(() => [
    { value: 'all', label: '全部主题', count: papers.length },
    ...categoryGroups.flatMap(group => [
      { value: group.key, label: group.name, count: group.count, divider: true },
      ...group.categories.filter(category => category.key !== group.key).map(category => ({
        value: category.key, label: category.name, count: category.count, child: true,
      })),
    ]),
  ], [categoryGroups, papers.length])
  const categoryPapers = useMemo(() => papers.filter(paper => matchesLibraryCategory(paper, categoryFilter)), [papers, categoryFilter])

  useEffect(() => {
    setDraftQuery(query)
    setOffset(0)
    setMode('search')
  }, [query, searchScope])

  useEffect(() => { setOffset(0); setMode('search') }, [categoryFilter, sortMode])

  useEffect(() => {
    const saved = readLibraryChatSession()
    if (!saved?.active) return
    setAnswerRequest(saved.request)
    setDraftQuery(saved.request.question)
    setMode('answer')
  }, [])

  useEffect(() => {
    setSearchResponse(null)
    setSearchError('')
    if (!query || isNumberQuery || mode !== 'search') { setSearching(false); return }
    const controller = new AbortController()
    let active = true
    setSearching(true)
    const params = new URLSearchParams({ q: query, offset: String(offset), limit: String(PAGE_SIZE), type: typeFilter, scope: searchScope, category: categoryFilter, sort: sortMode })
    fetch(`/api/library/search?${params}`, { signal: controller.signal, cache: 'no-store' })
      .then(async response => {
        const data = await response.json().catch(() => { throw new Error('检索暂时不可用，请稍后重试。') })
        if (!response.ok) throw new Error(data.error || '检索暂时不可用，请稍后重试。')
        if (active) setSearchResponse(data)
      })
      .catch(cause => { if (active && !controller.signal.aborted) setSearchError(cause instanceof Error && cause.name !== 'TypeError' ? cause.message : '检索连接失败，请稍后重试。') })
      .finally(() => { if (active) setSearching(false) })
    return () => { active = false; controller.abort() }
  }, [query, searchScope, isNumberQuery, offset, typeFilter, categoryFilter, sortMode, retry, mode])

  useEffect(() => {
    if (session.status !== 'authenticated' || searching || isNumberQuery || mode !== 'search' || !searchResponse?.results.length || searchResponse.query !== query) return
    return scheduleLibraryResultPrefetch(searchResponse.results)
  }, [session.status, searchResponse, searching, query, isNumberQuery, offset, typeFilter, retry, mode])

  function runSearch() {
    const next = draftQuery.trim()
    setLibraryChatActive(false)
    setMode('search')
    setOffset(0)
    if (next === query && searchScope === 'auto') setRetry(value => value + 1)
    const url = new URL(window.location.href)
    if (next) url.searchParams.set('q', next)
    else url.searchParams.delete('q')
    url.searchParams.delete('scope')
    router.replace(url.pathname + url.search, { scroll: false })
  }

  function askQuestion() {
    const question = draftQuery.trim()
    if (!question) return
    const request = { id: Math.max(Date.now(), (answerRequest?.id || 0) + 1), question }
    startLibraryChat(request)
    setAnswerRequest(request)
    setMode('answer')
  }

  function chooseType(type: TypeFilter) { setTypeFilter(type); setOffset(0) }

  function chooseSort(sort: string) {
    if (!isLibrarySort(sort)) return
    setLibraryChatActive(false)
    setOffset(0)
    const url = new URL(window.location.href)
    url.searchParams.set('sort', sort)
    router.replace(url.pathname + url.search, { scroll: false })
  }

  function chooseCategory(category: string) {
    if (!validLibraryCategoryFilter(category)) return
    setLibraryChatActive(false)
    setOffset(0)
    setMode('search')
    const url = new URL(window.location.href)
    if (category === 'all') url.searchParams.delete('category')
    else url.searchParams.set('category', category)
    router.replace(url.pathname + url.search, { scroll: false })
  }

  function clearSearch() {
    setLibraryChatActive(false)
    setDraftQuery('')
    setOffset(0)
    const url = new URL(window.location.href)
    url.searchParams.delete('q')
    url.searchParams.delete('scope')
    router.replace(url.pathname + url.search, { scroll: false })
  }

  // Number queries filter the same cards used by the library homepage.
  const filteredPapers = useMemo<PaperMetadata[]>(() => {
    return categoryPapers.filter(paper => {
      if (isNumberQuery && !paper.slug.startsWith(query)) return false
      return matchesLibraryType(paper, typeFilter)
    }).sort((left, right) => compareLibraryOrder(left, right, sortMode))
  }, [categoryPapers, typeFilter, query, isNumberQuery, sortMode])

  return (
    <main className="library-page flex-1 bg-neutral-50 min-h-screen">
      <div className="library-page-shell page-shell w-full max-w-[95%] xl:max-w-[1800px] mx-auto py-16 space-y-8">

        <div className="space-y-3">
          <CatalogSearchForm value={draftQuery} onChange={setDraftQuery} onSearch={runSearch} onAsk={askQuestion}
            label="搜索文献" placeholder="输入编号、关键词、句子或问题…" searching={searching} />
        </div>

        {mode === 'answer' && answerRequest && <ChatDialog key={answerRequest.id} request={answerRequest} />}

        {mode === 'search' && <section aria-label="文献筛选" className="library-toolbar">
          <div className="library-toolbar-topic">
            <LibraryFilterMenu label="主题" value={categoryFilter} options={categoryOptions} onChange={chooseCategory} />
          </div>
          <div role="group" aria-label="文献类型" className="library-type-switch">
            {([
              { value: 'all', label: '全部', icon: LayoutGrid },
              { value: 'paper', label: '论文', icon: FileText },
              { value: 'book', label: '书籍', icon: BookOpen },
            ] as const).map(({ value, label, icon: Icon }) => {
              const count = categoryPapers.filter(paper => matchesLibraryType(paper, value)).length
              return <button key={value} type="button" aria-label={`${label}（${count}）`} title={`${label}（${count}）`}
                aria-pressed={typeFilter === value} onClick={() => chooseType(value)}><Icon size={18} strokeWidth={1.6} aria-hidden="true" /></button>
            })}
          </div>
          <div className="library-toolbar-sort">
            <ArrowDownWideNarrow size={16} aria-hidden="true" className="library-sort-icon" />
            <LibraryFilterMenu label="排序方式" value={sortMode} align="end" onChange={chooseSort}
              options={librarySortOptions.filter(option => !browsingCards || option.value !== 'relevance').map(option => ({
                ...option, description: { 'year-desc': '最新发表优先', 'year-asc': '最早发表优先', 'id-asc': '按文献编号排列', relevance: '与搜索内容最相关' }[option.value],
              }))} />
          </div>
        </section>}

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
            <Link href={librarySearchHitHref(hit.href, searchResponse.terms)} className="library-title inline-block text-lg leading-7 text-blue-800 hover:underline"><LibraryPaperTitle paper={hit} highlightTerms={searchResponse.terms} /></Link>
            <LibraryMathMarkdown highlightTerms={searchResponse.terms} className="text-sm leading-7 text-slate-600 [&_p]:my-0">{hit.excerpt}</LibraryMathMarkdown>
          </article>)}
          {searchResponse && !searchResponse.total && <div className="rounded-xl bg-white px-6 py-12 text-sm leading-7 text-slate-500"><p>未找到相关内容。</p><p>可以缩短检索句，或换用术语的另一种中英文表达。</p></div>}
          {searchResponse && searchResponse.total > PAGE_SIZE && <nav aria-label="检索结果分页" className="flex flex-wrap items-center gap-4 pt-3 text-sm">
            <button type="button" disabled={offset === 0 || searching} onClick={() => setOffset(value => Math.max(0, value - PAGE_SIZE))} className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-slate-600 hover:bg-slate-50 disabled:opacity-40">上一页</button>
            <span className="text-slate-500">第 {Math.floor(offset / PAGE_SIZE) + 1} / {Math.ceil(searchResponse.total / PAGE_SIZE)} 页</span>
            <button type="button" disabled={offset + PAGE_SIZE >= searchResponse.total || searching} onClick={() => setOffset(value => value + PAGE_SIZE)} className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-slate-600 hover:bg-slate-50 disabled:opacity-40">下一页</button>
          </nav>}
        </section>}

        {mode === 'search' && (!query || isNumberQuery) && (filteredPapers.length > 0
          ? <LibraryMasonry>{filteredPapers.map(paper => <LibraryCard key={paper.slug} paper={paper} />)}</LibraryMasonry>
          : <div className="py-32 text-center"><p className="text-neutral-400 text-sm">未找到匹配的文献</p></div>)}

      </div>
    </main>
  )
}
