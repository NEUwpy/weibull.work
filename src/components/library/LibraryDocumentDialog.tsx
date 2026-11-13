'use client'

import React, { createContext, useContext, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import dynamic from 'next/dynamic'
import { usePathname } from 'next/navigation'
import { ArrowLeft, Expand, X } from 'lucide-react'
import { setLibraryChatActive } from '@/lib/library-chat-session'
import { createLibraryPreviewHistory } from '@/lib/library-preview-history'
import { usePreviewDialog } from '@/components/shared/usePreviewDialog'
import { libraryAuthorPreviewHref } from '@/lib/library-authors'
import { LibraryAuthorContext } from './LibraryAuthors'
import { libraryInstitutionPreviewHref } from '@/lib/library-institutions'
import { LibraryInstitutionContext } from './LibraryInstitutions'
import './dialog.css'

const LibraryArticle = dynamic(() => import('./LibraryArticle').then(module => module.LibraryArticle), {
  loading: () => <p role="status" className="p-12 text-center text-sm text-slate-400">正在打开文献…</p>,
})
const LibraryEntityDialog = dynamic(() => import('./LibraryEntityDialog').then(module => module.LibraryEntityDialog))
const DocumentContext = createContext<((href: string) => void) | null>(null)

function plainClick(event: React.MouseEvent<HTMLAnchorElement>) {
  return !event.defaultPrevented && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey
}

/** Keeps real document URLs available for full-page reading and modified clicks. */
export function LibraryDocumentLink({ href, onClick, ...props }: React.ComponentProps<typeof Link> & { href: string }) {
  const open = useContext(DocumentContext)
  return <Link {...props} href={href} onClick={event => {
    onClick?.(event)
    if (open && plainClick(event) && props.target !== '_blank' && /^\/library\/[^/?#]+(?:[?#]|$)/.test(href)) {
      event.preventDefault()
      open(href)
    }
  }} />
}

export function LibraryDocumentProvider({ children, returnLabel }: { children: React.ReactNode; returnLabel?: string }) {
  const [trail, setTrail] = useState<string[]>([])
  const [homeVersion, setHomeVersion] = useState(0)
  const previewHistory = useRef<ReturnType<typeof createLibraryPreviewHistory> | null>(null)
  const pathname = usePathname()
  useEffect(() => { previewHistory.current?.restore() }, [pathname])
  useEffect(() => {
    const history = createLibraryPreviewHistory(window, (_href, nextTrail) => setTrail(nextTrail))
    previewHistory.current = history
    return () => { history.dispose(); previewHistory.current = null }
  }, [])
  useEffect(() => {
    const home = (event: Event) => {
      if ((event as CustomEvent).detail !== '/library') return
      setLibraryChatActive(false)
      previewHistory.current?.leave()
      setHomeVersion(value => value + 1)
    }
    window.addEventListener('weibull:module-home', home)
    return () => window.removeEventListener('weibull:module-home', home)
  }, [])
  const open = (next: string) => {
    if (trail.at(-1)?.startsWith('/library?')) previewHistory.current?.push(next)
    else previewHistory.current?.open(next)
  }
  const openAuthor = (name: string, from?: string) => previewHistory.current?.push(libraryAuthorPreviewHref(name, from))
  const openInstitution = (name: string, from?: string) => previewHistory.current?.push(libraryInstitutionPreviewHref(name, from))
  return <DocumentContext.Provider value={open}>
    <LibraryAuthorContext.Provider value={openAuthor}>
      <LibraryInstitutionContext.Provider value={openInstitution}>
        <React.Fragment key={homeVersion}>{children}</React.Fragment>
        {trail.map((href, index) => {
          const previous = index > 0 ? new URL(trail[index - 1], 'http://library.local') : null
          const backLabel = previous ? (previous.searchParams.has('institution') ? '返回单位' : previous.searchParams.has('author') ? '返回作者' : '返回文献') : returnLabel
          return href.startsWith('/library?')
            ? <LibraryEntityDialog key={index} href={href} backLabel={backLabel} onClose={() => previewHistory.current?.close()} />
            : <LibraryDocumentDialog key={index} href={href} backLabel={backLabel} onNavigate={open} onClose={() => previewHistory.current?.close()} onLeave={() => previewHistory.current?.leave()} />
        })}
      </LibraryInstitutionContext.Provider>
    </LibraryAuthorContext.Provider>
  </DocumentContext.Provider>
}

function LibraryDocumentDialog({ href, backLabel, onNavigate, onClose, onLeave }: { href: string; backLabel?: string; onNavigate: (href: string) => void; onClose: () => void; onLeave: () => void }) {
  const { dialog, closeButton } = usePreviewDialog(onClose)
  const scroll = useRef<HTMLDivElement>(null)
  const url = new URL(href, 'http://library.local')
  const slug = decodeURIComponent(url.pathname.split('/')[2])

  useEffect(() => { scroll.current?.scrollTo(0, 0) }, [slug])

  return <dialog {...dialog} className="library-document-dialog" data-has-parent={Boolean(backLabel) || undefined} aria-label="文献资料">
    <div className="library-document-dialog-bar">
      <button type="button" className="library-document-dialog-back" aria-label={backLabel || '返回原窗口'} onClick={onClose}><ArrowLeft size={20} aria-hidden="true" /></button>
      <span className="library-document-dialog-heading">文献资料 <span className="library-document-dialog-id">{slug}</span></span>
      <div className="flex items-center gap-2">
        <Link href={href} replace className="library-document-dialog-expand" onClick={event => { if (plainClick(event)) onLeave() }}><Expand size={16} aria-hidden="true" />完整打开</Link>
        <button type="button" ref={closeButton} className="library-document-dialog-close" aria-label="关闭文献资料" title="关闭" onClick={onClose}><X size={22} /></button>
      </div>
    </div>
    <div ref={scroll} className="library-document-dialog-scroll" data-library-dialog-scroll onClick={event => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
      const anchor = (event.target as Element).closest('a[href^="#"]')
      if (!anchor) return
      event.preventDefault()
      const next = new URL(href, 'http://library.local')
      next.hash = anchor.getAttribute('href') || ''
      onNavigate(next.pathname + next.search + next.hash)
    }}>
      <LibraryArticle slug={slug} locationHref={href} onNavigate={onNavigate} />
    </div>
  </dialog>
}
