"use client"

import React, { useState, useMemo, useEffect } from 'react'
import dynamic from 'next/dynamic'
import { LibraryDocumentLink as Link, useLibraryCatalog } from './LibraryDocumentDialog'
import { useRouter, useSearchParams } from 'next/navigation'
import { Loader2, LayoutGrid, FileText, BookOpen, Lightbulb, Library, User, Building2, ArrowDownWideNarrow, Star } from 'lucide-react'
import type { LibrarySearchResponse } from '@/lib/library-search-types'
import { librarySearchHitHref } from '@/lib/library-search-highlight'
import { matchesLibraryType, type LibraryTypeFilter } from '@/lib/library-types'
import { isLibrarySort, librarySortOptions, type LibrarySort } from '@/lib/library-sort'
import { libraryPaperOrder } from '@/lib/library-journals'
import { compareLibraryCollectionNames, libraryCollectionSortOptions, libraryPeopleCollectionFilters, libraryPeopleGroups } from '@/lib/library-collections'
import { libraryCategoryGroups, matchesLibraryCategory, validLibraryCategoryFilter } from '@/lib/library-categories'
import { scheduleLibraryResultPrefetch } from '@/lib/library-document-client'
import { useLibrarySession } from '@/lib/library-auth-client'
import { LibraryMathMarkdown } from '@/components/shared/LibraryMathMarkdown'
import { LibraryCard } from './LibraryCard'
import { LibraryFavoriteButton, useLibraryFavorites } from './LibraryFavorites'
import { LibraryFavoritesPage } from './LibraryFavoritesPage'
import { LibraryMasonry } from './LibraryMasonry'
import { LibraryJournalGallery } from './LibraryJournalGallery'
import LibraryProblemCollections from './LibraryProblemCollections'
import { LibraryFilterMenu, type LibraryFilterOption } from './LibraryFilterMenu'
import { LibraryPaperTitle } from './LibraryPaperTitle'
import type { PaperMetadata } from '@/lib/server/literature'
import { CatalogSearchForm } from '@/components/shared/CatalogSearchForm'
import { ChatDialog } from '@/components/chat'
import { readLibraryChatSession, setLibraryChatActive, startLibraryChat } from '@/lib/library-chat-session'
import { isLibraryRecommendationRelation, libraryRecommendationLabels, type LibraryRecommendationRelation } from '@/lib/library-recommendations'
import { libraryAuthorMatchesQuery } from '@/lib/library-authors'
import { libraryInstitutionMatchesQuery } from '@/lib/library-institutions'
import { parseLibraryNumberQuery } from '@/lib/library-number-query'
import { libraryEntityDirectories, libraryEntityPreviewKind } from '@/lib/library-preview-history'
import './responsive.css'
import './collection-folder.css'


type TypeFilter = Exclude<LibraryTypeFilter, 'all'>

const PAGE_SIZE = 10
const collectionTabs = [
  { key: 'problems', label: '科学问题', icon: Lightbulb },
  { key: 'journals', label: '期刊集', icon: Library },
  { key: 'authors', label: '作者', icon: User },
  { key: 'institutions', label: '机构', icon: Building2 },
  { key: 'favorites', label: '收藏夹', icon: Star },
] as const
type CollectionTab = typeof collectionTabs[number]['key']
const collectionNavigationParams = ['view', 'problem', 'folder', 'subfolder', 'from', ...Object.keys(libraryEntityDirectories)]
const collectionControlParams = ['collectionFilter', 'collectionSort'] as const
const collectionParams = [...collectionNavigationParams, ...collectionControlParams]
const collectionFilterLabels = { problems: '研究方向', journals: 'JCR 分区', authors: '署名机构', institutions: '机构层级' }

const LibraryPeopleCollections = dynamic(() => import('./LibraryPeopleCollections'), {
  loading: () => <p role="status" className="py-12 text-sm text-slate-500">正在打开目录…</p>,
})

function LibraryPaperResults({ papers, maxColumns, favoriteRelation }: {
  papers: PaperMetadata[]; maxColumns?: number; favoriteRelation?: LibraryRecommendationRelation
}) {
  return papers.length > 0
    ? <LibraryMasonry maxColumns={maxColumns}>{papers.map(paper => <LibraryCard key={paper.slug} paper={paper} favoriteRelation={favoriteRelation} />)}</LibraryMasonry>
    : <div className="py-24 text-center"><p className="text-neutral-500 text-sm">未找到匹配的文献</p></div>
}

export function LibraryPageClient() {
  const { catalog: papers, journals: journalGroups, problemGroups, problemPapers } = useLibraryCatalog()
  const session = useLibrarySession()
  const favorites = useLibraryFavorites()
  const router = useRouter()
  const searchParams = useSearchParams()
  const query = searchParams.get('q')?.trim() || ''
  const searchScope = searchParams.get('scope') === 'text' ? 'text' : 'auto'
  const categoryFilter = searchParams.get('category') || 'all'
  const selectedProblem = searchParams.get('problem') || ''
  const entity = libraryEntityPreviewKind(`/library?${searchParams}`)
  const collection = entity ? libraryEntityDirectories[entity] : searchParams.get('problem') ? 'problems'
    : collectionTabs.find(tab => tab.key === searchParams.get('view'))?.key
  const problemView = collection === 'problems'
  const journalView = collection === 'journals'
  const peopleView = collection === 'authors' || collection === 'institutions' ? collection : null
  const favoritesView = collection === 'favorites'
  const publicCollection = collection === 'favorites' ? undefined : collection
  const collectionView = Boolean(collection)
  const numberQuery = useMemo(() => searchScope === 'text' ? null : parseLibraryNumberQuery(query), [query, searchScope])
  const isNumberQuery = numberQuery !== null
  const papersById = useMemo(() => new Map(papers.map(paper => [paper.slug, paper])), [papers])
  const missingNumbers = numberQuery?.ids.filter(id => !papersById.has(id)) || []
  const authorPapers = useMemo(() => !collectionView && searchScope !== 'text' && query && !isNumberQuery
    ? papers.filter(paper => libraryAuthorMatchesQuery(paper.author, query, paper.credits, papers)) : [], [papers, query, searchScope, isNumberQuery, collectionView])
  const isAuthorQuery = authorPapers.length > 0
  const institutionPapers = useMemo(() => !collectionView && searchScope !== 'text' && query && !isNumberQuery && !isAuthorQuery
    ? papers.filter(paper => libraryInstitutionMatchesQuery(paper, query, papers)) : [], [papers, query, searchScope, isNumberQuery, isAuthorQuery, collectionView])
  const isInstitutionQuery = institutionPapers.length > 0
  const browsingCards = !query || isNumberQuery || isAuthorQuery || isInstitutionQuery
  const requestedSort = searchParams.get('sort') || ''
  const sortMode: LibrarySort = isLibrarySort(requestedSort) && (!browsingCards || requestedSort !== 'relevance')
    ? requestedSort : browsingCards ? 'year-desc' : 'relevance'
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('paper')
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
  const peopleGroups = useMemo(() => peopleView ? libraryPeopleGroups(papers, peopleView) : [], [papers, peopleView])
  const collectionFilters = useMemo<LibraryFilterOption[]>(() => {
    if (peopleView) return libraryPeopleCollectionFilters(peopleGroups, peopleView)
    if (problemView) return [{ value: 'all', label: '全部方向' },
      ...problemGroups.map(group => ({ value: group.key, label: group.name, count: group.count }))]
    if (journalView) {
      const counts = new Map<string, number>()
      for (const journal of journalGroups) {
        const quartile = journal.metrics?.quartile || 'unclassified'
        counts.set(quartile, (counts.get(quartile) || 0) + 1)
      }
      return [{ value: 'all', label: '全部分区', count: journalGroups.length },
        ...Array.from(counts).sort(([a], [b]) => a.localeCompare(b, 'en')).map(([value, count]) => ({
          value, count, label: value === 'unclassified' ? '未标分区' : `JCR ${value}`,
        }))]
    }
    return []
  }, [peopleView, peopleGroups, problemView, problemGroups, journalView, journalGroups])
  const collectionSortOptions = publicCollection ? libraryCollectionSortOptions[publicCollection] : []
  const collectionFilter = collectionFilters.find(option => option.value === searchParams.get('collectionFilter'))?.value ?? 'all'
  const collectionSort = (collectionSortOptions.find(option => option.value === searchParams.get('collectionSort'))
    ?? collectionSortOptions[0])?.value ?? 'name-asc'
  const visibleJournals = useMemo(() => {
    if (!journalView) return []
    const groups = journalGroups.filter(journal => collectionFilter === 'all'
      || (journal.metrics?.quartile || 'unclassified') === collectionFilter)
    return groups.sort((a, b) => {
      const nameOrder = compareLibraryCollectionNames(a.name, b.name)
      if (collectionSort === 'impact-desc') return (b.metrics?.impactFactor ?? -1) - (a.metrics?.impactFactor ?? -1) || nameOrder
      if (collectionSort === 'count-desc') return b.count - a.count || nameOrder
      return nameOrder
    })
  }, [journalView, journalGroups, collectionFilter, collectionSort])

  useEffect(() => {
    setDraftQuery(query)
    setOffset(0)
    setMode('search')
  }, [query, searchScope])

  useEffect(() => { setOffset(0); setMode('search') }, [categoryFilter, sortMode])

  useEffect(() => { if (favoritesView) setMode('search') }, [favoritesView])

  useEffect(() => {
    if (collectionView) return
    const saved = readLibraryChatSession()
    if (!saved?.active) return
    setAnswerRequest(saved.request)
    setDraftQuery(saved.request.question)
    setMode('answer')
  }, [])

  useEffect(() => {
    setSearchResponse(null)
    setSearchError('')
    if (collectionView || browsingCards || mode !== 'search') { setSearching(false); return }
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
  }, [query, searchScope, browsingCards, collectionView, offset, typeFilter, categoryFilter, sortMode, retry, mode])

  useEffect(() => {
    if (session.status !== 'authenticated' || searching || browsingCards || mode !== 'search' || !searchResponse?.results.length || searchResponse.query !== query) return
    return scheduleLibraryResultPrefetch(searchResponse.results)
  }, [session.status, searchResponse, searching, query, browsingCards, offset, typeFilter, retry, mode])

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
    if (collectionView) collectionParams.forEach(param => url.searchParams.delete(param))
    router.replace(url.pathname + url.search, { scroll: false })
  }

  function askQuestion() {
    const question = draftQuery.trim()
    if (!question) return
    if (favoritesView) {
      const url = new URL(window.location.href)
      collectionParams.forEach(param => url.searchParams.delete(param))
      window.history.pushState(null, '', url.pathname + url.search)
    }
    const request = { id: Math.max(Date.now(), (answerRequest?.id || 0) + 1), question }
    startLibraryChat(request)
    setAnswerRequest(request)
    setMode('answer')
  }

  function chooseType(type: TypeFilter) {
    if (collectionView) {
      setLibraryChatActive(false)
      setMode('search')
      const url = new URL(window.location.href)
      collectionParams.forEach(param => url.searchParams.delete(param))
      window.history.replaceState(null, '', url.pathname + url.search)
    }
    setTypeFilter(type)
    setOffset(0)
  }

  function chooseCollection(view: CollectionTab) {
    setLibraryChatActive(false)
    setDraftQuery('')
    setOffset(0)
    setMode('search')
    setTypeFilter('paper')
    const href = collectionHref(view)
    if (href !== window.location.pathname + window.location.search) window.history.pushState(null, '', href)
  }

  function collectionHref(view: CollectionTab, problem?: string) {
    const params = new URLSearchParams(searchParams.toString())
    collectionNavigationParams.forEach(param => params.delete(param))
    if (view !== collection) collectionControlParams.forEach(param => params.delete(param))
    params.delete('q')
    params.delete('scope')
    params.set('view', view)
    if (problem) params.set('problem', problem)
    return `/library?${params}`
  }

  function problemHref(key: string) {
    return collectionHref('problems', key)
  }

  function chooseProblem(key: string) {
    setLibraryChatActive(false)
    setDraftQuery('')
    setMode('search')
    setOffset(0)
    setTypeFilter('paper')
    window.history.pushState(key ? { __weibullProblemFolder: key } : null, '', problemHref(key))
  }

  function closeProblem() {
    const key = searchParams.get('problem')
    if (key && window.history.state?.__weibullProblemFolder === key) window.history.back()
    else window.history.replaceState(null, '', problemHref(''))
  }

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

  function chooseCollectionControl(param: typeof collectionControlParams[number], value: string) {
    const url = new URL(window.location.href)
    if (param === 'collectionFilter' && value === 'all') url.searchParams.delete(param)
    else url.searchParams.set(param, value)
    window.history.replaceState(null, '', url.pathname + url.search)
  }

  function clearSearch() {
    setLibraryChatActive(false)
    setDraftQuery('')
    setOffset(0)
    setMode('search')
    const url = new URL(window.location.href)
    url.searchParams.delete('q')
    url.searchParams.delete('scope')
    collectionParams.forEach(param => url.searchParams.delete(param))
    router.replace(url.pathname + url.search, { scroll: false })
  }

  // Author and number queries filter the homepage cards before full-text search.
  const filteredPapers = useMemo<PaperMetadata[]>(() => {
    if (collectionView) return []
    const ids = new Set(numberQuery?.ids)
    const matching = categoryPapers.filter(paper => {
      if (numberQuery && !(numberQuery.prefix ? paper.slug.startsWith(numberQuery.prefix) : ids.has(paper.slug))) return false
      if (isAuthorQuery && !authorPapers.includes(paper)) return false
      if (isInstitutionQuery && !institutionPapers.includes(paper)) return false
      return matchesLibraryType(paper, typeFilter)
    })
    return libraryPaperOrder(matching, sortMode)
  }, [collectionView, categoryPapers, typeFilter, numberQuery, isAuthorQuery, authorPapers, isInstitutionQuery, institutionPapers, sortMode])

  return (
    <main className="library-page flex-1 bg-neutral-50 min-h-screen">
      <div className="library-page-shell page-shell w-full max-w-[95%] xl:max-w-[1800px] mx-auto py-16 space-y-8">

        <div className="space-y-3">
          <CatalogSearchForm value={draftQuery} onChange={setDraftQuery} onSearch={runSearch} onAsk={askQuestion}
            label="搜索文献" placeholder="输入文献编号（可多个）、作者、单位、关键词或研究方向…" searching={searching} />
        </div>

        {mode === 'answer' && answerRequest && <ChatDialog key={answerRequest.id} request={answerRequest} renderRecommendations={(ids, relations) => {
          const recommended = ids.flatMap(id => {
            const paper = papersById.get(id)
            return paper ? [paper] : []
          })
          const groups = new Map<LibraryRecommendationRelation, PaperMetadata[]>()
          const saveIds = Array.from(new Set(recommended.filter(paper => matchesLibraryType(paper, 'paper')).map(paper => paper.slug)))
          for (const paper of recommended) {
            const relation = relations?.[paper.slug]
            if (!isLibraryRecommendationRelation(relation)) {
              groups.clear()
              break
            }
            const group = groups.get(relation)
            if (group) group.push(paper)
            else groups.set(relation, [paper])
          }
          const saveSelection = { paperIds: saveIds, relations: groups.size ? relations : undefined, batch: true }
          return <section aria-label="推荐文献" className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4">
              <p role="status" className="text-sm leading-6 text-slate-500">找到 <span className="font-semibold text-slate-800">{recommended.length}</span> 篇相关文献</p>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
                {favorites && saveIds.length > 0 && <button type="button" disabled={favorites.busy || favorites.checkingSession}
                    aria-haspopup="dialog" onClick={() => favorites.choose(saveSelection)} title="选择或新建收藏夹"
                    className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 text-slate-700 hover:bg-slate-50 disabled:opacity-50"><Star size={15} aria-hidden="true" />全部收藏</button>
                }
                <button type="button" onClick={clearSearch} className="min-h-9 text-blue-600 hover:underline">浏览全部文献</button>
              </div>
            </div>
            {groups.size > 0 ? Array.from(groups, ([relation, papers]) => (
              <section key={relation} aria-labelledby={`library-recommendation-${relation}`} className="space-y-3">
                <h2 id={`library-recommendation-${relation}`} className="text-base font-semibold text-slate-800">{libraryRecommendationLabels[relation]}</h2>
                <LibraryPaperResults papers={papers} favoriteRelation={relation} />
              </section>
            )) : <LibraryPaperResults papers={recommended} />}
          </section>
        }} />}

        {mode === 'search' && <div className="library-browse-navigation"><section aria-label={favoritesView ? '文献导航' : '文献筛选'} className="library-toolbar">
          <div className="library-toolbar-topic">
            {publicCollection ? <LibraryFilterMenu key={publicCollection} label={collectionFilterLabels[publicCollection]} value={collectionFilter}
              options={collectionFilters} onChange={value => chooseCollectionControl('collectionFilter', value)} />
              : !favoritesView && <LibraryFilterMenu label="主题" value={categoryFilter} options={categoryOptions} onChange={chooseCategory} />}
          </div>
          <div role="group" aria-label="文献类型" className="library-type-switch">
            <Link href={problemHref('')} prefetch={false} aria-label="论文集" title="论文集"
              aria-current={collectionView ? 'page' : undefined} onClick={event => {
                if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
                event.preventDefault()
                chooseCollection('problems')
              }}><LayoutGrid size={18} strokeWidth={1.6} aria-hidden="true" /></Link>
            {([
              { value: 'paper', label: '论文', icon: FileText },
              { value: 'book', label: '书籍', icon: BookOpen },
            ] as const).map(({ value, label, icon: Icon }) => {
              const count = categoryPapers.filter(paper => matchesLibraryType(paper, value)).length
              return <button key={value} type="button" aria-label={`${label}（${count}）`} title={`${label}（${count}）`}
                aria-pressed={!collectionView && typeFilter === value} onClick={() => chooseType(value)}><Icon size={18} strokeWidth={1.6} aria-hidden="true" /></button>
            })}
          </div>
          <div className="library-toolbar-sort">
            {!favoritesView && <ArrowDownWideNarrow size={16} aria-hidden="true" className="library-sort-icon" />}
            {publicCollection ? <LibraryFilterMenu key={publicCollection} label="目录排序" value={collectionSort} align="end"
              options={[...collectionSortOptions]} onChange={value => chooseCollectionControl('collectionSort', value)} />
              : !favoritesView && <LibraryFilterMenu label="排序方式" value={sortMode} align="end" onChange={chooseSort}
              options={librarySortOptions.filter(option => !browsingCards || option.value !== 'relevance').map(option => ({
                ...option,
                description: {
                  'year-desc': '最新发表优先',
                  'year-asc': '最早发表优先',
                  'id-asc': '按文献编号排列',
                  'impact-desc': '按期刊影响因子从高到低，缺失置后',
                  relevance: '与搜索内容最相关',
                }[option.value],
              }))} />}
          </div>
        </section>
        {collectionView && <nav aria-label="论文集分组" className="library-collection-navigation">
          <div className="library-collection-tabs">
            {collectionTabs.map(({ key, label, icon: Icon }) => <Link key={key} href={collectionHref(key)} prefetch={false}
              aria-current={collection === key ? 'page' : undefined} onClick={event => {
                if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
                event.preventDefault()
                chooseCollection(key)
              }}><Icon size={16} strokeWidth={1.65} aria-hidden="true" />{label}</Link>)}
          </div>
        </nav>}
        </div>}

        {mode === 'search' && problemView && <LibraryProblemCollections relatedPapers={problemPapers.get(selectedProblem) ?? []} groups={problemGroups} selectedKey={selectedProblem}
          direction={collectionFilter} sort={collectionSort} onOpen={chooseProblem} onClose={closeProblem} hrefFor={problemHref} />}

        {mode === 'search' && journalView && <LibraryJournalGallery journals={visibleJournals} />}

        {mode === 'search' && peopleView && <LibraryPeopleCollections key={`${peopleView}:${collectionFilter}`}
          kind={peopleView} groups={peopleGroups} filter={collectionFilter} sort={collectionSort} />}

        {mode === 'search' && favoritesView && <LibraryFavoritesPage papers={papersById} />}

        {mode === 'search' && !collectionView && query && browsingCards && <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4">
          <div className="min-w-0 break-words text-sm leading-6 text-slate-500" role="status">
            <p>{numberQuery?.ids.length ? `按 ${numberQuery.ids.length} 个编号检索` : `“${query}”`} · {isAuthorQuery ? '作者匹配' : isInstitutionQuery ? '单位匹配' : '找到'} <span className="font-semibold text-slate-800">{filteredPapers.length}</span> 篇文献</p>
            {!!missingNumbers.length && <p>未找到的编号：{missingNumbers.join('、')}</p>}
          </div>
          <button type="button" onClick={clearSearch} className="text-sm text-blue-600 hover:underline">浏览全部文献</button>
        </div>}

        {mode === 'search' && !collectionView && !browsingCards && <section aria-label="文献检索结果" className="library-search-results space-y-7">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4">
            <p role="status" className="text-sm leading-6 text-slate-500">
              {searching ? <span className="flex items-center gap-2"><Loader2 size={15} className="animate-spin" />正在检索文献正文…</span>
                : searchResponse ? <>“{query}” · 找到 <span className="font-semibold text-slate-800">{searchResponse.total}</span> 处相关内容</> : '检索结果'}
            </p>
            <button type="button" onClick={clearSearch} className="text-sm text-blue-600 hover:underline">浏览全部文献</button>
          </div>
          {searchError && <div role="alert" className="rounded-xl border border-rose-100 bg-rose-50 p-5 text-sm text-rose-700">{searchError}<button type="button" onClick={() => setRetry(value => value + 1)} className="ml-3 underline">重试</button></div>}
          {searchResponse?.results.map(hit => <article key={hit.id} className="max-w-5xl space-y-2 rounded-xl bg-white p-5 sm:p-6">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs leading-5 text-slate-500">{hit.slug} · {hit.version} · {hit.section}</p>
              {matchesLibraryType(papersById.get(hit.slug) ?? {}, 'paper') && <LibraryFavoriteButton paperId={hit.slug} />}
            </div>
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

        {mode === 'search' && !collectionView && browsingCards && <LibraryPaperResults papers={filteredPapers}
          maxColumns={typeFilter === 'paper' ? 3 : undefined} />}

      </div>
    </main>
  )
}
