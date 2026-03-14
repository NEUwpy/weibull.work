"use client"

import React, { useState, useMemo } from 'react'
import Link from 'next/link'
import { BookOpen, FileText, Filter, Book, User } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ChatDialog } from '@/components/chat'


type PaperMetadata = {
  slug: string
  title: string
  title_en?: string
  author: string
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

export function LibraryPageClient({ papers }: LibraryPageClientProps) {
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all')

  // Filter papers based on type
  const filteredPapers = useMemo(() => {
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
    <main className="flex-1 bg-neutral-50 min-h-screen">
      <div className="w-full max-w-[92%] xl:max-w-[1600px] mx-auto pl-[4.5rem] pr-[3rem] py-16 space-y-12">

        {/* AI Chat Dialog */}
        <ChatDialog papers={papers} />

        {/* Type Filter Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-1 h-8 bg-neutral-800 rounded-full" />
            <span className="text-sm font-medium text-neutral-500 tracking-wide uppercase">Filter</span>
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => setTypeFilter('all')}
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
              onClick={() => setTypeFilter('book')}
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
              onClick={() => setTypeFilter('journal-conf')}
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

        {/* Masonry Waterfall Layout */}
        <div className="columns-1 md:columns-2 lg:columns-3 gap-8">
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
        </div>

      </div>
    </main>
  )
}
