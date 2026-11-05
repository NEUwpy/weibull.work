'use client'

import React, { createContext, useContext, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import dynamic from 'next/dynamic'
import { usePathname } from 'next/navigation'
import { ArrowLeft, Expand, X } from 'lucide-react'
import { setLibraryChatActive } from '@/lib/library-chat-session'
import { createLibraryPreviewHistory } from '@/lib/library-preview-history'
import { usePreviewDialog } from '@/components/shared/usePreviewDialog'
import './dialog.css'

const LibraryArticle = dynamic(() => import('./LibraryArticle').then(module => module.LibraryArticle), {
  loading: () => <p role="status" className="p-12 text-center text-sm text-slate-400">正在打开文献…</p>,
})
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

export function LibraryDocumentProvider({ children }: { children: React.ReactNode }) {
  const [href, setHref] = useState<string | null>(null)
  const [homeVersion, setHomeVersion] = useState(0)
  const previewHistory = useRef<ReturnType<typeof createLibraryPreviewHistory> | null>(null)
  const pathname = usePathname()
  useEffect(() => { setHref(null) }, [pathname])
  useEffect(() => {
    const history = createLibraryPreviewHistory(window, setHref)
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
  const open = (next: string) => previewHistory.current?.open(next)
  return <DocumentContext.Provider value={open}>
    <React.Fragment key={homeVersion}>{children}</React.Fragment>
    {href && <LibraryDocumentDialog href={href} onNavigate={open} onClose={() => previewHistory.current?.close()} onLeave={() => previewHistory.current?.leave()} />}
  </DocumentContext.Provider>
}

function LibraryDocumentDialog({ href, onNavigate, onClose, onLeave }: { href: string; onNavigate: (href: string) => void; onClose: () => void; onLeave: () => void }) {
  const { dialog, closeButton } = usePreviewDialog(onClose)
  const scroll = useRef<HTMLDivElement>(null)
  const url = new URL(href, 'http://library.local')
  const slug = decodeURIComponent(url.pathname.split('/')[2])

  useEffect(() => { scroll.current?.scrollTo(0, 0) }, [href])

  return <dialog {...dialog} className="library-document-dialog" aria-label="文献资料">
    <div className="library-document-dialog-bar">
      <button type="button" className="library-document-dialog-back" aria-label="返回原窗口" onClick={onClose}><ArrowLeft size={20} aria-hidden="true" />返回</button>
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
