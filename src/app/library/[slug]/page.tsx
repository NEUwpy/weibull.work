"use client"

import React, { useState, useEffect, useMemo } from 'react'
import Markdown from 'react-markdown'
import Link from 'next/link'
import { ArrowLeft, ArrowRight, User, Calendar, List, Book, BookOpen, FileText, Languages, LockKeyhole, Loader2 } from 'lucide-react'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import '@/components/library/responsive.css'
import '@/components/library/login.css'
import { cn } from '@/lib/utils'
import { processLibraryContent, getLibraryMarkdownOptions, getLibraryReferenceMarkdownOptions } from '@/lib/library-markdown'
import { readLibrarySearchHighlight, rehypeLibrarySearchHighlights, type LibrarySearchHighlight } from '@/lib/library-search-highlight'
import { LibraryAuthenticationError, libraryDocumentClient } from '@/lib/library-document-client'
import { libraryAuthClient, useLibrarySession } from '@/lib/library-auth-client'
import { LibraryLoginDialog } from '@/components/library/LibraryLoginDialog'
import type { LibraryVersion } from '@/lib/library-search-types'

type ReadingView = '介绍' | LibraryVersion
interface PublicPaper {
  slug: string
  title: string
  title_en?: string
  author: string
  affiliation?: string
  publication?: string
  year: number
  type?: string
  doi?: string
  summary: string
  tags: string[]
}

function renderTextWithMath(text: string): React.ReactNode {
  const parts: React.ReactNode[] = []
  let lastIndex = 0
  const mathRegex = /\$([^$]+)\$/g
  let match
  while ((match = mathRegex.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.substring(lastIndex, match.index))
    const mathHtml = katex.renderToString(match[1], { throwOnError: false, displayMode: false })
    parts.push(<span key={`math-${match.index}`} dangerouslySetInnerHTML={{ __html: mathHtml }} />)
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < text.length) parts.push(text.substring(lastIndex))
  return parts.length > 0 ? parts : text
}

export default function ArticlePage({ params }: { params: { slug: string } }) {
  const slug = params.slug
  const [view, setView] = useState<ReadingView>('介绍')
  const [paper, setPaper] = useState<PublicPaper | null>(null)
  const [versions, setVersions] = useState<LibraryVersion[]>([])
  const [loading, setLoading] = useState(true)
  const [loadedSlug, setLoadedSlug] = useState('')
  const [error, setError] = useState('')
  const [loginOpen, setLoginOpen] = useState(false)
  const [sessionError, setSessionError] = useState('')
  const auth = useLibrarySession()

  useEffect(() => {
    const readView = () => {
      const requested = new URLSearchParams(window.location.search).get('version')
      setView(requested === '原文' || requested === '翻译' ? requested : '介绍')
    }
    readView()
    window.addEventListener('popstate', readView)
    return () => window.removeEventListener('popstate', readView)
  }, [slug])

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError(''); setPaper(null)
    fetch(`/api/library/papers/${encodeURIComponent(slug)}`, { cache: 'no-store', signal: controller.signal })
      .then(async response => {
        const data = await response.json()
        if (!response.ok) throw new Error(data.error || '文献暂时无法加载。')
        if (!controller.signal.aborted) { setPaper(data.paper); setVersions(data.versions); setLoadedSlug(slug) }
      })
      .catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error && cause.name !== 'TypeError' ? cause.message : '连接失败，请稍后重试。') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [slug])

  useEffect(() => {
    if (view !== '介绍' && auth.status === 'anonymous') setLoginOpen(true)
    if (auth.status === 'authenticated') setLoginOpen(false)
  }, [view, auth.status])

  function chooseView(next: ReadingView) {
    setView(next)
    const url = new URL(window.location.href)
    if (next === '介绍') url.searchParams.delete('version')
    else url.searchParams.set('version', next)
    if (url.hash.startsWith('#passage-')) url.hash = ''
    url.searchParams.delete('highlight')
    window.history.replaceState(window.history.state, '', url)
    if (next !== '介绍' && auth.status === 'anonymous') setLoginOpen(true)
  }

  async function logout() {
    chooseView('介绍'); setLoginOpen(false); setSessionError('')
    try { await libraryAuthClient.logout() }
    catch (cause) { setSessionError(cause instanceof Error ? cause.message : '退出未完成，请重试。') }
  }

  if (loading || (!error && loadedSlug !== slug)) return <main className="library-reader flex-1 bg-slate-50 min-h-screen"><div role="status" className="p-20 text-center text-sm text-slate-400">正在加载文献介绍…</div></main>
  if (error || !paper) return <main className="library-reader flex-1 bg-slate-50 min-h-screen"><div role="alert" className="p-12 text-center text-sm text-slate-500"><p>{error || '文献未找到。'}</p><Link href="/library" className="mt-4 inline-block text-blue-600">返回图书馆</Link></div></main>
  const selectedVersion = view === '介绍' ? null : view

  return (
    <main className="library-reader flex-1 bg-slate-50 min-h-screen">
      <div className="bg-white border-b border-slate-200">
        <div className="library-entry-shell pt-8">
          <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
            <Link href="/library" className="library-entry-back"><ArrowLeft size={16} />可靠性图书馆</Link>
            <div className="library-entry-session">
              {auth.status === 'authenticated' ? <><span>已登录 · {auth.user?.phone ? auth.user.phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2') : '阅读账号'}</span><span aria-hidden="true">·</span><button type="button" onClick={logout}>退出登录</button></>
                : auth.status === 'loading' ? <span>确认登录状态…</span> : <button type="button" onClick={() => setLoginOpen(true)}>登录</button>}
            </div>
          </div>
          {sessionError && <p role="alert" className="mb-4 text-sm text-rose-600">{sessionError}</p>}
          <div className="flex flex-wrap gap-2 mb-5">{paper.tags?.map(tag => <span key={tag} className="rounded-md bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500">{tag}</span>)}</div>
          <h1 className="text-3xl md:text-4xl font-semibold tracking-tight text-slate-900 leading-tight">{paper.title}</h1>
          {paper.title_en && <h2 className="mt-3 text-lg md:text-xl font-normal text-slate-400 leading-relaxed">{paper.title_en}</h2>}
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3 mt-6 text-slate-500 text-sm">
            <span className="inline-flex items-center gap-2"><User size={15} className="text-slate-400" />{paper.author}</span>
            {paper.publication && <span className="inline-flex items-center gap-2"><Book size={15} className="text-slate-400" />{paper.publication}</span>}
            <span className="inline-flex items-center gap-2"><Calendar size={15} className="text-slate-400" />{paper.year}</span>
            <span className="text-xs text-slate-400">{slug}</span>
          </div>
          <div role="tablist" aria-label="文献内容" className="library-entry-tabs">
            <button type="button" role="tab" aria-selected={view === '介绍'} aria-controls="library-reading-panel" onClick={() => chooseView('介绍')}><BookOpen size={16} />介绍</button>
            {versions.map(version => <button key={version} type="button" role="tab" aria-selected={view === version} aria-controls="library-reading-panel" onClick={() => chooseView(version)}>{version === '原文' ? <FileText size={16} /> : <Languages size={16} />}{version === '翻译' ? '译文' : '原文'}{auth.status !== 'authenticated' && <LockKeyhole size={12} className="text-slate-400" />}</button>)}
          </div>
        </div>
      </div>
      <div id="library-reading-panel" role="tabpanel">
        {view === '介绍' ? (
          <div className="library-entry-shell py-12">
            <div className="reader-paper bg-white p-10 rounded-3xl border border-slate-200 shadow-sm library-entry-introduction">
              <div>
                <p className="text-xs tracking-widest text-slate-400 mb-5">文献介绍</p>
                <p className="library-entry-summary">{paper.summary || '暂无文献介绍。'}</p>
                <div className="library-entry-actions">{versions.map((version, index) => <button type="button" key={version} onClick={() => chooseView(version)} className={cn('library-entry-read', index === 0 && 'library-entry-read-primary')}>{version === '翻译' ? <Languages size={16} /> : <FileText size={16} />}阅读{version === '翻译' ? '译文' : '原文'}<ArrowRight size={15} /></button>)}</div>
              </div>
              <dl className="library-entry-aside"><dt>文献编号</dt><dd>{slug}</dd>{paper.type && <><dt>类型</dt><dd>{paper.type}</dd></>}{paper.affiliation && <><dt>机构</dt><dd>{paper.affiliation}</dd></>}{paper.doi && <><dt>DOI</dt><dd>{paper.doi}</dd></>}<dt>可阅读版本</dt><dd>{versions.map(version => version === '翻译' ? '译文' : '原文').join(' / ')}</dd></dl>
            </div>
          </div>
        ) : auth.status === 'loading' ? <div className="library-entry-shell py-12"><p role="status" className="flex items-center justify-center gap-2 py-20 text-sm text-slate-400"><Loader2 size={18} className="animate-spin" />正在确认阅读权限…</p></div>
          : auth.status !== 'authenticated' ? <div className="library-entry-shell py-12"><div className="library-access-wall"><div aria-hidden="true" className="library-access-preview">{Array.from({ length: 16 }, (_, index) => <div key={index} />)}</div><div className="library-access-cover"><div className="library-access-card"><div className="library-login-emblem"><LockKeyhole size={25} strokeWidth={1.6} /></div><h2>登录后，阅读完整{view === '翻译' ? '译文' : '原文'}</h2><p>文献介绍与搜索片段公开可见。<br />登录已开放账号，即可继续阅读全文。</p><button type="button" className="library-entry-read library-entry-read-primary" onClick={() => setLoginOpen(true)}>登录并继续<ArrowRight size={16} /></button></div></div></div></div>
            : selectedVersion && versions.includes(selectedVersion) ? <LibraryDocument key={`${slug}:${selectedVersion}`} slug={slug} version={selectedVersion} />
              : <p className="p-12 text-center text-sm text-slate-400">本篇暂未收录这个版本。</p>}
      </div>
      <LibraryLoginDialog open={loginOpen} onClose={() => setLoginOpen(false)} />
    </main>
  )
}

function LibraryDocument({ slug, version }: { slug: string; version: LibraryVersion }) {
  const [fileContent, setFileContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [references, setReferences] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [highlight, setHighlight] = useState<LibrarySearchHighlight>({ passageId: '', terms: [] })
  const processed = useMemo(() => fileContent ? processLibraryContent(fileContent) : null, [fileContent])

  useEffect(() => {
    let active = true
    setLoading(true); setError(''); setFileContent(null)
    async function load() {
      try {
        const [content, nextReferences] = await Promise.all([
          libraryDocumentClient.readFile(slug, version),
          libraryDocumentClient.readReferences(slug, version).catch(cause => {
            if (cause instanceof LibraryAuthenticationError) throw cause
            return {}
          }),
        ])
        if (!active) return
        setReferences(nextReferences); setFileContent(content)
      } catch (cause) {
        if (!active || (cause instanceof Error && cause.name === 'AbortError')) return
        if (cause instanceof LibraryAuthenticationError) libraryAuthClient.invalidate()
        else setError(cause instanceof Error ? cause.message : '文献库暂时不可用，请稍后重试。')
      } finally { if (active) setLoading(false) }
    }
    void load()
    return () => { active = false }
  }, [slug, version])

  useEffect(() => {
    if (loading || !fileContent) return
    function scrollToTarget() {
      const next = readLibrarySearchHighlight(window.location.search, window.location.hash)
      setHighlight(previous => JSON.stringify(previous) === JSON.stringify(next) ? previous : next)
      let id = ''
      try { id = decodeURIComponent(window.location.hash.slice(1)) } catch { return }
      const target = id ? document.getElementById(id) : null
      target?.scrollIntoView({ block: 'start' })
    }
    const frame = requestAnimationFrame(scrollToTarget)
    const settle = window.setTimeout(scrollToTarget, 350)
    window.addEventListener('hashchange', scrollToTarget)
    window.addEventListener('popstate', scrollToTarget)
    return () => { cancelAnimationFrame(frame); clearTimeout(settle); window.removeEventListener('hashchange', scrollToTarget); window.removeEventListener('popstate', scrollToTarget) }
  }, [loading, fileContent, slug, version])

  if (loading) return <div role="status" className="p-20 text-center text-sm text-slate-400">正在加载文献…</div>
  if (error) return <div role="alert" className="p-20 text-center text-sm text-rose-600">{error}</div>
  if (!processed) return <div className="p-20 text-center text-sm text-slate-400">这个版本暂时无法加载。</div>
  const { body, referenceTitle, referenceEntries, headings: rawToc } = processed
  const markdownOptions = getLibraryMarkdownOptions(processed)
  const minLevel = rawToc.length > 0 ? Math.min(...rawToc.map(h => h.level)) : 1
  const toc = rawToc.map(h => ({ ...h, renderLevel: h.level - minLevel + 1 }))
  return (
      <div className="reader-layout library-entry-shell py-12 flex gap-12 items-start">
        {toc.length > 0 && (
          <details className="reader-mobile-toc">
            <summary><List size={18} />目录</summary>
            <nav aria-label="文献目录">
              {toc.map((item, idx) => (
                <a key={idx} href={`#${item.slug}`} style={{ paddingLeft: `${(item.renderLevel - 1) * 12 + 12}px` }}>
                  {renderTextWithMath(item.text)}
                </a>
              ))}
              {referenceEntries.length > 0 && <a href="#references-section">{referenceTitle}</a>}
            </nav>
          </details>
        )}
        {/* TOC Sidebar */}
        <aside className="hidden lg:block w-64 shrink-0 sticky top-24 max-h-[calc(100vh-8rem)] overflow-y-auto pr-4 scrollbar-hide">
           <div className="mb-6 flex items-center gap-2 text-slate-900 font-black text-base uppercase tracking-widest">
              <List size={18} className="text-blue-600" />
              <span>目录</span>
           </div>
                      <nav className="space-y-1 relative border-l-2 border-slate-100">
                         {toc.map((item, idx) => (
                           <a
                             key={idx}
                             href={`#${item.slug}`}
                             className={`
                               block py-2 transition-all border-l-2 -ml-[2px] font-bold
                               ${item.renderLevel === 1 ? 'text-base text-slate-800 hover:border-blue-500 hover:text-blue-600 pl-4' : ''}
                               ${item.renderLevel === 2 ? 'text-sm text-slate-500 hover:text-slate-800 hover:border-slate-300 pl-8 font-normal' : ''}
                               ${item.renderLevel >= 3 ? 'text-xs text-slate-400 hover:text-slate-600 pl-14 font-normal' : ''}
                               border-transparent
                             `}
                           >
                             {renderTextWithMath(item.text)}
                           </a>
                         ))}
                         {referenceEntries.length > 0 && (
                            <a href="#references-section" className="block py-2 transition-all border-l-2 -ml-[2px] pl-4 font-bold text-base text-slate-800 hover:border-blue-500 hover:text-blue-600 border-transparent">
                              {referenceTitle}
                            </a>
                         )}
                      </nav>
        </aside>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="reader-paper bg-white p-10 rounded-3xl border border-slate-200 shadow-sm">
            <article className="prose prose-slate prose-base max-w-none prose-headings:scroll-mt-28 prose-headings:font-black prose-headings:tracking-tight prose-headings:text-slate-900 prose-h1:text-3xl prose-h2:text-2xl prose-h3:text-xl prose-p:text-slate-600 prose-p:leading-7 prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline prose-strong:text-slate-900 prose-strong:font-bold prose-code:text-blue-600 prose-code:bg-blue-50 prose-code:px-1 prose-code:rounded prose-pre:bg-slate-900 prose-pre:text-white prose-pre:shadow-lg prose-pre:rounded-2xl prose-img:rounded-lg prose-img:max-w-[33%] prose-img:mx-auto prose-img:my-6">
              <Markdown {...markdownOptions} rehypePlugins={[...markdownOptions.rehypePlugins, [rehypeLibrarySearchHighlights, highlight]]}>
                {body}
              </Markdown>
            </article>

            {/* References Section */}
            {referenceEntries.length > 0 && (
              <div id="references-section" className="mt-16 pt-10 border-t border-slate-100 scroll-mt-28">
                <h2 className="text-2xl font-black text-slate-900 mb-6">{referenceTitle}</h2>
                <div className="space-y-4">
                  {referenceEntries.map((entry, idx) => {
                    const refId = entry.id
                    const refContent = entry.content

                    // Check if this reference has a linked article
                    const currentPaperRefs = references
                    const targetSlug = currentPaperRefs[refId ?? `entry-${idx + 1}`]
                    const hasLink = targetSlug && typeof targetSlug === 'string'

                    return (
                      <div key={idx} id={refId ? `ref-${refId}` : undefined} className="flex gap-4 text-sm text-slate-600 leading-relaxed group scroll-mt-32">
                        {refId && <a href={`#cite-${refId}`} className="font-bold text-slate-400 select-none shrink-0 group-hover:text-blue-500 hover:underline transition-colors no-underline">[{refId}]</a>}
                        <div className="min-w-0 flex-1 [&_p]:m-0">
                          {hasLink ? (
                            <Link href={`/library/${targetSlug}`} className="block text-blue-600 hover:underline">
                              <Markdown {...getLibraryReferenceMarkdownOptions(processed, entry)}
                                components={{ a: ({ children }) => <span>{children}</span> }}>{refContent}</Markdown>
                            </Link>
                          ) : (
                            <Markdown {...getLibraryReferenceMarkdownOptions(processed, entry)}>{refContent}</Markdown>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
  )
}
