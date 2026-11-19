'use client'

import React, { useId, type ReactNode } from 'react'
import type { PaperMetadata } from '@/lib/server/literature'
import { LibraryCard } from './LibraryCard'
import { LibraryMasonry } from './LibraryMasonry'
import { useLibraryScrollBatches } from './useLibraryScrollBatches'

const PAGE_SIZE = 12

export function LibraryCollectionDetails({ title, children, papers, actions, profile }: {
  title: string
  children?: ReactNode
  papers: PaperMetadata[]
  actions?: ReactNode
  profile?: { sourcePaper: string | null }
}) {
  const headingId = useId()
  const currentIndex = profile?.sourcePaper ? papers.findIndex(paper => paper.slug === profile.sourcePaper) : -1
  const firstCount = Math.max(PAGE_SIZE, Math.ceil((currentIndex + 1) / PAGE_SIZE) * PAGE_SIZE)
  const { visibleCount, hasMore, sentinel } = useLibraryScrollBatches(papers.length, PAGE_SIZE, firstCount)

  return <>
    <header className="mb-6 space-y-2 break-words text-sm leading-6 text-slate-600">
      <h2 className="text-xl font-medium leading-8 text-slate-800 sm:text-2xl">{title}</h2>
      {children}
    </header>
    <section aria-labelledby={headingId} className="library-collection-papers">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-slate-200 pb-3">
        <h3 id={headingId} className="text-base font-medium text-slate-700">在库文献 <span className="ml-2 text-sm font-normal tabular-nums text-slate-600">{papers.length} 篇</span></h3>
        {actions}
      </div>
      {papers.length ? <LibraryMasonry maxColumns={2}>
        {papers.slice(0, visibleCount).map(paper => <LibraryCard key={paper.slug} paper={paper}
          profile={profile && { current: paper.slug === profile.sourcePaper }} />)}
      </LibraryMasonry> : <p className="py-8 text-center text-sm text-slate-500">该目录下暂无文献</p>}
      {hasMore && <div ref={sentinel} className="h-px" aria-hidden="true" />}
    </section>
  </>
}
