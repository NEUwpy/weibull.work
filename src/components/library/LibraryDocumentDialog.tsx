'use client'

import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import dynamic from 'next/dynamic'
import { usePathname } from 'next/navigation'
import { Expand } from 'lucide-react'
import { setLibraryChatActive } from '@/lib/library-chat-session'
import { createLibraryPreviewHistory, isLibraryPreviewHref, libraryEntityDirectories, libraryEntityPreviewKind } from '@/lib/library-preview-history'
import { libraryAuthorPreviewHref } from '@/lib/library-authors'
import { LibraryAuthorContext } from './LibraryAuthors'
import { libraryInstitutionPreviewHref } from '@/lib/library-institutions'
import { createLibraryDirectoryIndex } from '@/lib/library-directory-index'
import type { PaperMetadata } from '@/lib/server/literature'
import { LibraryInstitutionContext } from './LibraryInstitutions'
import { LibraryPreviewDialog } from './LibraryPreviewDialog'
import { LibraryEntityDialog } from './LibraryEntityDialog'

const LibraryArticle = dynamic(() => import('./LibraryArticle').then(module => module.LibraryArticle), {
  loading: () => <p role="status" className="p-12 text-center text-sm text-slate-400">正在打开文献…</p>,
})
const DocumentContext = createContext<((href: string) => void) | null>(null)
const LibraryCatalogContext = createContext<ReturnType<typeof createLibraryDirectoryIndex<PaperMetadata>> | undefined>(undefined)

export function useLibraryCatalog() {
  const catalog = useContext(LibraryCatalogContext)
  if (!catalog) throw new Error('缺少图书馆书单')
  return catalog
}

export function useLibraryCatalogPaper(slug: string) {
  return useContext(LibraryCatalogContext)?.catalog.find(paper => paper.slug === slug)
}

function plainClick(event: React.MouseEvent<HTMLAnchorElement>) {
  return !event.defaultPrevented && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey
}

/** Keeps real document URLs available for full-page reading and modified clicks. */
export function LibraryDocumentLink({ href, onClick, ...props }: React.ComponentProps<typeof Link> & { href: string }) {
  const open = useContext(DocumentContext)
  return <Link {...props} aria-haspopup={props['aria-haspopup'] ?? (libraryEntityPreviewKind(href) ? 'dialog' : undefined)} href={href} onClick={event => {
    onClick?.(event)
    if (open && plainClick(event) && props.target !== '_blank' && isLibraryPreviewHref(href)) {
      event.preventDefault()
      event.currentTarget?.focus({ preventScroll: true })
      open(href)
    }
  }} />
}

export function LibraryDocumentProvider({ children, returnLabel, catalog }: {
  children: React.ReactNode; returnLabel?: string; catalog?: PaperMetadata[]
}) {
  const directory = useMemo(() => catalog && createLibraryDirectoryIndex(catalog), [catalog])
  const [trail, setTrail] = useState<string[]>([])
  const [homeVersion, setHomeVersion] = useState(0)
  const [directHref, setDirectHref] = useState<string | null>(null)
  const previewHistory = useRef<ReturnType<typeof createLibraryPreviewHistory> | null>(null)
  const pathname = usePathname()
  const getPreviewHistory = useCallback(() => {
    return previewHistory.current ??= createLibraryPreviewHistory(window, (_href, nextTrail) => setTrail(nextTrail))
  }, [])

  useEffect(() => { previewHistory.current?.restore() }, [pathname])
  useEffect(() => {
    const history = getPreviewHistory()
    return () => { history.dispose(); previewHistory.current = null }
  }, [getPreviewHistory])
  useEffect(() => {
    // Query links still open as previews when followed in a new tab or refreshed.
    const syncDirectPreview = () => {
      const href = window.location.pathname + window.location.search
      setDirectHref(libraryEntityPreviewKind(href) ? href : null)
    }
    syncDirectPreview()
    window.addEventListener('popstate', syncDirectPreview)
    return () => window.removeEventListener('popstate', syncDirectPreview)
  }, [pathname])
  useEffect(() => {
    const home = (event: Event) => {
      if ((event as CustomEvent).detail !== '/library') return
      setLibraryChatActive(false)
      previewHistory.current?.leave()
      setDirectHref(null)
      setHomeVersion(value => value + 1)
    }
    window.addEventListener('weibull:module-home', home)
    return () => window.removeEventListener('weibull:module-home', home)
  }, [])
  const layers = directHref ? [directHref, ...trail] : trail
  // Opening a layer should not re-render every link on the page behind it.
  const open = useCallback((next: string) => {
    const history = getPreviewHistory()
    const currentHref = history.currentHref() ?? window.location.pathname + window.location.search
    if (libraryEntityPreviewKind(next) || libraryEntityPreviewKind(currentHref)) history.push(next)
    else history.open(next)
  }, [getPreviewHistory])
  const openAuthor = useCallback((name: string, from?: string) => open(libraryAuthorPreviewHref(name, from)), [open])
  const openInstitution = useCallback((name: string, from?: string) => open(libraryInstitutionPreviewHref(name, from)), [open])
  return <DocumentContext.Provider value={open}>
    <LibraryAuthorContext.Provider value={openAuthor}>
      <LibraryInstitutionContext.Provider value={openInstitution}>
        <LibraryCatalogContext.Provider value={directory}>
          <React.Fragment key={homeVersion}>{children}</React.Fragment>
          {layers.map((href, index) => {
            const kind = libraryEntityPreviewKind(href)
            const previous = index > 0 ? libraryEntityPreviewKind(layers[index - 1]) : undefined
            const backLabel = index > 0 ? (previous ? { author: '返回作者', institution: '返回单位', journal: '返回期刊' }[previous] : '返回文献') : returnLabel
            const onClose = () => {
              if (!(index === 0 && directHref && kind)) { previewHistory.current?.close(); return }
              const url = new URL(window.location.href)
              url.searchParams.delete(kind)
              url.searchParams.delete('from')
              url.searchParams.set('view', libraryEntityDirectories[kind])
              window.history.replaceState(null, '', url.pathname + url.search)
              setDirectHref(null)
            }
            if (kind) return <LibraryEntityDialog key={index} href={href} backLabel={backLabel} onClose={onClose} findEntity={directory?.findEntity} />
            return <LibraryDocumentDialog key={index} href={href} backLabel={backLabel} onNavigate={open} onClose={onClose} onLeave={() => previewHistory.current?.leave()} />
          })}
        </LibraryCatalogContext.Provider>
      </LibraryInstitutionContext.Provider>
    </LibraryAuthorContext.Provider>
  </DocumentContext.Provider>
}

function LibraryDocumentDialog({ href, backLabel, onNavigate, onClose, onLeave }: { href: string; backLabel?: string; onNavigate: (href: string) => void; onClose: () => void; onLeave: () => void }) {
  const scroll = useRef<HTMLDivElement>(null)
  const url = new URL(href, 'http://library.local')
  const slug = decodeURIComponent(url.pathname.split('/')[2])

  useEffect(() => { scroll.current?.scrollTo(0, 0) }, [slug])

  return <LibraryPreviewDialog title="文献资料" detail={slug} backLabel={backLabel} onClose={onClose}
    actions={<Link href={href} replace className="library-document-dialog-expand" onClick={event => { if (plainClick(event)) onLeave() }}><Expand size={16} aria-hidden="true" />完整打开</Link>}
    scroll={{ ref: scroll, onClick: event => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
      const anchor = (event.target as Element).closest('a[href^="#"]')
      if (!anchor) return
      event.preventDefault()
      const next = new URL(href, 'http://library.local')
      next.hash = anchor.getAttribute('href') || ''
      onNavigate(next.pathname + next.search + next.hash)
    } }}>
    <LibraryArticle key={slug} slug={slug} locationHref={href} onNavigate={onNavigate} />
  </LibraryPreviewDialog>
}
