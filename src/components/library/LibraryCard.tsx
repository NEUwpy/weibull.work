'use client'

import React, { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { ChevronDown, ChevronUp, User } from 'lucide-react'
import type { LibraryCategory } from '@/lib/library-categories'
import type { LibraryVersion } from '@/lib/library-search-types'
import { libraryAuthorPreview } from '@/lib/library-card-presentation'
import { LibraryMathMarkdown } from '@/components/shared/LibraryMathMarkdown'
import { LibraryCardMetadata } from './LibraryCardMetadata'
import { LibraryPaperTitle } from './LibraryPaperTitle'
import type { LibraryTitlePresentation } from '@/lib/library-titles'
import { cn } from '@/lib/utils'

interface CardPaper extends LibraryTitlePresentation {
  slug: string; title: string; author: string; year: number; summary: string; tags: string[]
  type?: string; publication?: string; short_publication?: string; doi?: string
  category?: LibraryCategory; availableVersions: LibraryVersion[]
}

export function LibraryCard({ paper }: { paper: CardPaper }) {
  const slot = useRef<HTMLDivElement>(null)
  const summary = useRef<HTMLDivElement>(null)
  const pending = useRef<ReturnType<typeof setTimeout>>()
  const touch = useRef<{ x: number; y: number } | null>(null)
  const suppressClick = useRef<{ x: number; y: number; until: number } | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [summaryHeight, setSummaryHeight] = useState(0)
  const contentId = useId()
  const available = paper.availableVersions.length > 0
  const tags = Array.from(new Set(paper.tags)).filter(tag => tag !== paper.category?.groupName && tag !== paper.category?.name)

  const cancelPending = useCallback(() => { clearTimeout(pending.current) }, [])
  const close = useCallback(() => { cancelPending(); setExpanded(false) }, [cancelPending])
  const open = useCallback(() => { cancelPending(); setExpanded(true) }, [cancelPending])

  useLayoutEffect(() => {
    if (!summary.current) return
    const measure = () => setSummaryHeight(summary.current?.scrollHeight || 0)
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(summary.current)
    return () => observer.disconnect()
  }, [paper.summary])

  useEffect(() => {
    if (!expanded) return
    const outside = (event: PointerEvent) => { if (!slot.current?.contains(event.target as Node)) close() }
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') close() }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    window.addEventListener('resize', close)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
      window.removeEventListener('resize', close)
    }
  }, [expanded, close])
  useEffect(() => cancelPending, [cancelPending])

  return <div ref={slot} className="library-card-slot group block break-inside-avoid mb-8"
    data-expanded={expanded || undefined} aria-disabled={!available || undefined}
    onPointerEnter={event => { if (event.pointerType === 'mouse') { cancelPending(); pending.current = setTimeout(open, 220) } }}
    onPointerLeave={event => { if (event.pointerType === 'mouse') { cancelPending(); pending.current = setTimeout(close, 120) } }}
    onPointerDown={event => {
      if (event.pointerType === 'mouse' || (event.target as Element).closest('button')) return
      touch.current = { x: event.clientX, y: event.clientY }
      cancelPending()
      pending.current = setTimeout(() => {
        if (!touch.current) return
        suppressClick.current = { ...touch.current, until: Number.POSITIVE_INFINITY }
        open()
      }, 480)
    }}
    onPointerMove={event => {
      if (touch.current && Math.hypot(event.clientX - touch.current.x, event.clientY - touch.current.y) > 10) {
        touch.current = null; cancelPending()
      }
    }}
    onPointerUp={() => {
      if (suppressClick.current?.until === Number.POSITIVE_INFINITY) suppressClick.current.until = Date.now() + 1200
      touch.current = null; cancelPending()
    }}
    onPointerCancel={() => { touch.current = null; suppressClick.current = null; cancelPending() }}
    onContextMenu={event => { if (touch.current || (suppressClick.current && suppressClick.current.until > Date.now())) event.preventDefault() }}
    onClickCapture={event => {
      const held = suppressClick.current
      if (held && held.until > Date.now() && Math.hypot(event.clientX - held.x, event.clientY - held.y) < 20) {
        event.preventDefault(); event.stopPropagation(); suppressClick.current = null
      }
    }}
    onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) close() }}>
    <article className={cn('library-card relative rounded-xl border border-slate-200', available ? 'bg-white' : 'bg-slate-50')}>
      <div className="p-7 space-y-5">
        <LibraryCardMetadata id={paper.slug} type={paper.type} publication={paper.publication || paper.short_publication}
          year={paper.year} doi={paper.doi} available={available} />
        <h3 className={cn('library-title text-xl leading-relaxed transition-colors', available ? 'text-slate-800 group-hover:text-blue-800' : 'text-slate-500')}>
          {available ? <Link href={`/library/${paper.slug}`} className="library-card-link"><LibraryPaperTitle paper={paper} /></Link>
            : <LibraryPaperTitle paper={paper} />}
        </h3>
        <p className="library-card-authors relative z-20 text-sm text-slate-500 flex items-start gap-1.5" title={paper.author}>
          <User size={13} className="text-slate-400 shrink-0" />
          <span className="min-w-0 line-clamp-2">{libraryAuthorPreview(paper.author)}</span>
        </p>
        <div id={contentId}>
          <div className="library-card-summary-clip text-sm" style={{ '--library-summary-height': `${summaryHeight}px` } as React.CSSProperties}>
            <div ref={summary}>
              <LibraryMathMarkdown className={cn('library-card-summary text-sm leading-relaxed text-justify', available ? 'text-slate-600' : 'text-slate-500')}>
                {paper.summary || '暂无文献介绍。'}
              </LibraryMathMarkdown>
            </div>
          </div>
          <div className="mt-5 pt-4 border-t border-slate-100">
            {!available && <p className="mb-3 text-xs font-medium text-slate-500">资料待补齐</p>}
            <div className="library-card-tag-row flex items-center gap-2">
              <div className="library-card-tags library-card-key-tags flex flex-1 gap-2">
                {paper.category && <>
                  <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">#{paper.category.groupName}</span>
                  {paper.category.key !== paper.category.groupKey && <span className="rounded border border-emerald-200 px-2 py-0.5 text-xs text-emerald-700">#{paper.category.name}</span>}
                </>}
                {!paper.category && tags[0] && <span className="text-xs px-2 py-0.5 rounded text-blue-600 bg-blue-50">#{tags[0]}</span>}
              </div>
              <button type="button" className="library-card-expand" aria-label={`${expanded ? '收起' : '展开'}卡片：${paper.slug}`}
                aria-expanded={expanded} aria-controls={contentId} title={expanded ? '收起' : '展开完整介绍与标签'}
                onClick={() => expanded ? close() : open()}>
                {!expanded && tags.length > (paper.category ? 0 : 1) && <span>+{tags.length - (paper.category ? 0 : 1)}</span>}
                {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
              </button>
            </div>
            <div className="library-card-extra-tags" aria-hidden={!expanded}>
              <div>
                <div className="library-card-tags library-card-keywords flex flex-wrap gap-2">
                  {(paper.category ? tags : tags.slice(1)).map(tag => <span key={tag}
                    className={cn('text-xs px-2 py-0.5 rounded', available ? 'text-blue-600 bg-blue-50' : 'text-slate-500 bg-slate-100')}>#{tag}</span>)}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </article>
  </div>
}
