"use client"

import React, { useState, useMemo } from 'react'
import Link from 'next/link'
import { BookOpen, FileText, Calendar, User, Filter } from 'lucide-react'
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
    <main className="flex-1 bg-slate-50">
      <div className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12 space-y-8">

        {/* Type Filter Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Filter size={20} className="text-emerald-600" />
            <span className="text-lg font-black text-slate-700">文献类型</span>
          </div>

          <div className="flex bg-slate-100 p-0.5 rounded-xl border border-slate-200 h-9">
            <button
              onClick={() => setTypeFilter('all')}
              className={cn(
                "px-5 h-full rounded-lg text-sm font-black transition-all flex items-center justify-center gap-2",
                typeFilter === 'all' ? "bg-white text-emerald-600 shadow-sm" : "text-slate-400 hover:text-slate-600"
              )}
            >
              全部
              <span className="text-xs font-bold opacity-60">({papers.length})</span>
            </button>
            <button
              onClick={() => setTypeFilter('book')}
              className={cn(
                "px-5 h-full rounded-lg text-sm font-black transition-all flex items-center justify-center gap-2",
                typeFilter === 'book' ? "bg-white text-emerald-600 shadow-sm" : "text-slate-400 hover:text-slate-600"
              )}
            >
              书籍
              <span className="text-xs font-bold opacity-60">({papers.filter(p => (p.type || '其它') === '书籍').length})</span>
            </button>
            <button
              onClick={() => setTypeFilter('journal-conf')}
              className={cn(
                "px-5 h-full rounded-lg text-sm font-black transition-all flex items-center justify-center gap-2",
                typeFilter === 'journal-conf' ? "bg-white text-emerald-600 shadow-sm" : "text-slate-400 hover:text-slate-600"
              )}
            >
              期刊 & 会议
              <span className="text-xs font-bold opacity-60">({papers.filter(p => (p.type || '其它') === '期刊' || (p.type || '其它') === '会议').length})</span>
            </button>
          </div>
        </div>

        {/* AI Chat Dialog */}
        <ChatDialog papers={papers} />

        {/* Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredPapers.map(paper => (
            <Link
              key={paper.slug}
              href={`/library/${paper.slug}`}
              className="group bg-white rounded-2xl p-6 border border-slate-200 shadow-sm hover:shadow-xl hover:border-blue-300 transition-all duration-300 flex flex-col h-full"
            >
              {/* Card Header */}
              <div className="flex justify-between items-center mb-6 h-8">
                 <div className="flex items-center gap-3 min-w-0">
                   <div className="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center text-blue-600 group-hover:bg-blue-600 group-hover:text-white transition-colors shrink-0">
                      <FileText size={18} />
                   </div>
                   <div className="text-sm font-bold text-slate-600 truncate">
                     {paper.type && <span className="text-slate-400 mr-1">{paper.type}：</span>}
                     {paper.short_publication || paper.publication}
                   </div>
                 </div>
                 {paper.year && (
                   <span className="flex items-center gap-2 text-sm font-bold text-slate-400 shrink-0 ml-4">
                     <Calendar size={14} />
                     {paper.year}
                   </span>
                 )}
              </div>

              {/* Title & Author */}
              <h3 className="text-xl font-black text-slate-800 mb-2 leading-tight group-hover:text-blue-700 transition-colors">
                {paper.title}
              </h3>
              <p className="text-sm font-bold text-slate-400 mb-4 flex items-center gap-2">
                <User size={14} className="text-blue-400/50" />
                {paper.author}
              </p>

              {/* Summary */}
              <p className="text-sm text-slate-500 leading-relaxed mb-6 line-clamp-3 flex-1">
                {paper.summary}
              </p>

              {/* Tags & Footer */}
              <div className="mt-auto pt-4 border-t border-slate-100 flex flex-wrap gap-2">
                 {paper.tags.map(tag => (
                   <span key={tag} className="text-sm font-bold text-blue-600 bg-blue-50 px-3 py-1.5 rounded-lg border border-blue-100/50">
                     #{tag}
                   </span>
                 ))}
              </div>
            </Link>
          ))}

          {/* Empty State */}
          {filteredPapers.length === 0 && (
            <div className="col-span-full py-20 text-center text-slate-400">
               <BookOpen size={48} className="mx-auto mb-4 opacity-20" />
               <p>未找到匹配的文献。</p>
            </div>
          )}
        </div>

      </div>
    </main>
  )
}
