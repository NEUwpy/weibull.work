"use client"

import React, { useState, useEffect, useMemo, useRef, useId } from 'react'
import Markdown from 'react-markdown'
import { LibraryDocumentLink as Link } from './LibraryDocumentDialog'
import { ArrowRight, Calendar, BookOpen, FileText, Languages, LockKeyhole, Loader2, PanelLeft, PanelRight } from 'lucide-react'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import '@/components/library/document.css'
import '@/components/library/table.css'
import '@/components/library/responsive.css'
import '@/components/library/login.css'
import { cn } from '@/lib/utils'
import { processLibraryContent, getLibraryMarkdownOptions, getLibraryReferenceMarkdownOptions } from '@/lib/library-markdown'
import { readLibrarySearchHighlight, rehypeLibrarySearchHighlights, type LibrarySearchHighlight } from '@/lib/library-search-highlight'
import { LibraryAuthenticationError, libraryDocumentClient, scheduleLibraryResultPrefetch } from '@/lib/library-document-client'
import { libraryAuthClient, useLibrarySession } from '@/lib/library-auth-client'
import { LibraryLoginDialog } from '@/components/library/LibraryLoginDialog'
import { LibraryMathMarkdown } from '@/components/shared/LibraryMathMarkdown'
import type { LibraryVersion } from '@/lib/library-search-types'
import type { LibraryCategory } from '@/lib/library-categories'
import type { LibraryTitlePresentation } from '@/lib/library-titles'
import type { LibraryCredits } from '@/lib/library-credits'
import { LibraryPaperTitle } from '@/components/library/LibraryPaperTitle'
import { LibraryAuthors } from './LibraryAuthors'
import { LibraryInstitutions } from './LibraryInstitutions'
import { libraryPaperInstitutions } from '@/lib/library-institutions'
import { LibraryArticleChat } from './LibraryArticleChat'

type ReadingView = '简介' | LibraryVersion
const READING_VERSIONS: LibraryVersion[] = ['原文', '翻译']
interface PublicPaper extends LibraryTitlePresentation {
  slug: string
  title: string
  title_en?: string
  author: string
  affiliation?: string
  credits?: LibraryCredits
  publication?: string
  year: number
  type?: string
  doi?: string
  summary: string
  tags: string[]
  category?: LibraryCategory
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

export function LibraryArticle({ slug, locationHref, onNavigate }: { slug: string; locationHref?: string; onNavigate?: (href: string) => void }) {
  const article = useRef<HTMLElement>(null)
  const panelId = useId()
  const [view, setView] = useState<ReadingView>('简介')
  const [readerVersion, setReaderVersion] = useState<LibraryVersion | null>(null)
  const [preparedVersion, setPreparedVersion] = useState<LibraryVersion | null>(null)
  const [introExpanded, setIntroExpanded] = useState(true)
  const [readerVisible, setReaderVisible] = useState(false)
  const [leftOpen, setLeftOpen] = useState(true)
  const [rightOpen, setRightOpen] = useState(false)
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
      const requested = new URL(locationHref || window.location.href, window.location.origin).searchParams.get('version')
      setView(requested === '原文' || requested === '翻译' ? requested : '简介')
    }
    readView()
    if (locationHref) return
    window.addEventListener('popstate', readView)
    return () => window.removeEventListener('popstate', readView)
  }, [slug, locationHref])

  useEffect(() => {
    const controller = new AbortController()
    const requested = new URL(locationHref || window.location.href, window.location.origin).searchParams.get('version')
    const readingRequested = requested === '原文' || requested === '翻译'
    setLoading(true); setError(''); setPaper(null); setVersions([]); setReaderVersion(null)
    setPreparedVersion(null); setIntroExpanded(!readingRequested); setReaderVisible(readingRequested)
    setLeftOpen(true); setRightOpen(false)
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
    if (loading || loadedSlug !== slug || auth.status !== 'authenticated') return
    return scheduleLibraryResultPrefetch(READING_VERSIONS.filter(version => versions.includes(version))
      .map(version => ({ slug, version })))
  }, [loading, loadedSlug, slug, versions, auth.status])

  useEffect(() => {
    if (auth.status === 'authenticated') setLoginOpen(false)
    else setPreparedVersion(null)
    if (loading || loadedSlug !== slug || view === '简介') return
    if (!versions.includes(view)) { chooseView('简介'); return }
    setReaderVersion(view)
    if (auth.status === 'anonymous') setLoginOpen(true)
  }, [view, auth.status, versions, loading, loadedSlug, slug])

  useEffect(() => {
    if (loading || loadedSlug !== slug) return
    if (view === '简介') {
      setIntroExpanded(true)
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) setReaderVisible(false)
      return
    }
    if (auth.status === 'loading' || (auth.status === 'authenticated' && preparedVersion !== view)) return
    setReaderVisible(true)
    // Lay out the prepared reader before starting the drawer animation.
    let settle = 0
    const prepare = requestAnimationFrame(() => {
      settle = requestAnimationFrame(() => setIntroExpanded(false))
    })
    return () => { cancelAnimationFrame(prepare); cancelAnimationFrame(settle) }
  }, [view, auth.status, preparedVersion, loading, loadedSlug, slug])

  function chooseView(next: ReadingView) {
    if (next !== '简介' && !versions.includes(next)) return
    setView(next)
    if (next !== '简介') setReaderVersion(next)
    if (next === '简介') setLoginOpen(false)
    const url = new URL(locationHref || window.location.href, window.location.origin)
    if (next === '简介') url.searchParams.delete('version')
    else url.searchParams.set('version', next)
    if (url.hash.startsWith('#passage-')) url.hash = ''
    url.searchParams.delete('highlight')
    if (onNavigate) onNavigate(url.pathname + url.search + url.hash)
    else window.history.replaceState(window.history.state, '', url)
    if (next === '简介') requestAnimationFrame(() => {
      const scroller = article.current?.closest<HTMLElement>('[data-library-dialog-scroll]')
      const behavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'
      if (scroller) scroller.scrollTo({ top: 0, behavior })
      else window.scrollTo({ top: 0, behavior })
    })
    if (next !== '简介' && auth.status === 'anonymous') setLoginOpen(true)
  }

  async function logout() {
    chooseView('简介'); setLoginOpen(false); setSessionError('')
    try { await libraryAuthClient.logout() }
    catch (cause) { setSessionError(cause instanceof Error ? cause.message : '退出未完成，请重试。') }
  }

  if (loading || (!error && loadedSlug !== slug)) return <main className="library-reader flex-1 bg-slate-50 min-h-screen"><div role="status" className="p-20 text-center text-sm text-slate-400">正在加载文献简介…</div></main>
  if (error || !paper) return <main className="library-reader flex-1 bg-slate-50 min-h-screen"><div role="alert" className="p-12 text-center text-sm text-slate-500"><p>{error || '文献未找到。'}</p></div></main>
  const selectedVersion = view !== '简介' && versions.includes(view) ? view : null
  const readingView = selectedVersion || '简介'
  const documentVersion = selectedVersion || readerVersion
  const readingControlsVisible = !introExpanded && readingView !== '简介' && auth.status === 'authenticated'
  const topics = Array.from(new Set([paper.category?.groupName, paper.category?.name, ...paper.tags].filter((tag): tag is string => Boolean(tag))))
  const institutions = libraryPaperInstitutions(paper)
  function openCitation(href: string) {
    const version = new URL(href, window.location.origin).searchParams.get('version')
    if (version === '原文' || version === '翻译') { setView(version); setReaderVersion(version) }
    if (onNavigate) onNavigate(href)
    else {
      window.history.replaceState(window.history.state, '', href)
      window.dispatchEvent(new Event('hashchange'))
    }
  }

  const versionTabs = <div role="tablist" aria-label="文献内容" className="library-entry-tabs library-reading-tabs">
    <button type="button" role="tab" aria-selected={readingView === '简介'} aria-controls={panelId + '-intro'} onClick={() => chooseView('简介')}><BookOpen size={16} />简介</button>
    {READING_VERSIONS.map(version => <button key={version} type="button" role="tab" disabled={!versions.includes(version)}
      aria-selected={selectedVersion === version} aria-controls={panelId}
      aria-busy={selectedVersion === version && auth.status === 'authenticated' && preparedVersion !== version}
      title={!versions.includes(version) ? (version === '翻译' ? '译文' : '原文') + '资料待补齐' : undefined} onClick={() => chooseView(version)}>
      {selectedVersion === version && auth.status === 'authenticated' && preparedVersion !== version ? <Loader2 size={16} className="animate-spin" /> : version === '原文' ? <FileText size={16} /> : <Languages size={16} />}{version === '翻译' ? '译文' : '原文'}
      {versions.includes(version) && auth.status !== 'authenticated' && <LockKeyhole size={12} className="text-slate-400" />}
    </button>)}
  </div>

  return (
    <main ref={article} className="library-reader flex-1 bg-slate-50 min-h-screen">
      <div className="library-article-heading bg-white border-b border-slate-200">
        <div className="library-entry-shell pt-8">
          <div className="flex flex-wrap items-center justify-end gap-4 mb-8">
            <div className="library-entry-session">
              {auth.status === 'authenticated' ? <><span>已登录 · {auth.user?.phone ? auth.user.phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2') : '阅读账号'}</span><span aria-hidden="true">·</span><button type="button" onClick={logout}>退出登录</button></>
                : auth.status === 'loading' ? <span>确认登录状态…</span> : <button type="button" onClick={() => setLoginOpen(true)}>登录</button>}
            </div>
          </div>
          {sessionError && <p role="alert" className="mb-4 text-sm text-rose-600">{sessionError}</p>}
          <h1 className="library-title text-3xl md:text-4xl text-slate-900 leading-tight"><LibraryPaperTitle paper={paper} /></h1>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3 mt-6 text-slate-500 text-sm">
            {paper.type && <span>{paper.type}</span>}
            {paper.year > 0 && <span className="inline-flex items-center gap-2"><Calendar size={15} className="text-slate-400" />{paper.year}</span>}
            <span className="text-xs text-slate-400">{slug}</span>
          </div>
        </div>
      </div>
      <div className="library-article-toolbar-band" data-reading={readingControlsVisible}>
        <div className="library-article-toolbar library-entry-shell">
          <button type="button" disabled={!readingControlsVisible} aria-expanded={leftOpen} aria-controls={panelId + '-toc'}
            aria-label={leftOpen ? '收起目录' : '展开目录'} title={leftOpen ? '收起目录' : '展开目录'}
            onClick={() => setLeftOpen(open => !open)}><PanelLeft size={17} /></button>
          <div className="library-article-toolbar-center">{versionTabs}</div>
          <button type="button" disabled={!readingControlsVisible} aria-expanded={rightOpen} aria-controls={panelId + '-chat'}
            aria-label={rightOpen ? '收起 AI 问答' : '展开 AI 问答'} title={rightOpen ? '收起 AI 问答' : '展开 AI 问答'}
            onClick={() => setRightOpen(open => !open)}><PanelRight size={17} /></button>
        </div>
      </div>
      <div id={panelId + '-intro'} role="tabpanel" aria-label="文献简介" className="library-article-intro" data-expanded={introExpanded} aria-hidden={readingView !== '简介'}
        ref={element => { if (element) element.inert = readingView !== '简介' }}
        onTransitionEnd={event => {
          if (event.target === event.currentTarget && event.propertyName === 'grid-template-rows' && readingView === '简介') setReaderVisible(false)
        }}>
        <div className="library-article-intro-clip">
          <div className="library-entry-shell library-article-intro-content">
            <div className="library-article-intro-details">
              {paper.summary && <section className="mb-8 border-b border-slate-100 pb-8">
                <LibraryMathMarkdown className="text-base leading-8 text-slate-600">{paper.summary}</LibraryMathMarkdown>
              </section>}
              <dl className="library-entry-details">
                <div><dt>文献编号</dt><dd>{slug}</dd></div>
                <div><dt>类型</dt><dd>{paper.type || '未登记'}</dd></div>
                <div><dt>发表年份</dt><dd>{paper.year > 0 ? paper.year : '未登记'}</dd></div>
                {(paper.original_title || paper.title_en) && <div><dt>{paper.original_language === 'en' ? '英文原名' : '英文题名'}</dt><dd><LibraryMathMarkdown inline>{paper.original_title || paper.title_en || ''}</LibraryMathMarkdown></dd></div>}
                <div><dt>作者</dt><dd><LibraryAuthors author={paper.author || '未登记'} credits={paper.credits} from={paper.slug} /></dd></div>
                <div><dt>出版信息</dt><dd>{paper.publication || '未登记'}</dd></div>
                {institutions.length > 0 && <div><dt>机构</dt><dd><LibraryInstitutions affiliation={institutions.join('；')} credits={paper.credits} from={paper.slug} /></dd></div>}
                <div><dt>DOI</dt><dd>{paper.doi ? <a href={'https://doi.org/' + paper.doi} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">{paper.doi}</a> : '未登记'}</dd></div>
                <div><dt>主题</dt><dd>{topics.length ? topics.join(' · ') : '未登记'}</dd></div>
                <div><dt>可阅读版本</dt><dd>{versions.map(version => version === '翻译' ? '译文' : '原文').join(' / ') || '资料待补齐'}</dd></div>
              </dl>
              {!versions.length && <p role="status" className="mt-6 text-sm text-slate-500">资料待补齐，原文与译文暂未收录。</p>}
              <div className="library-entry-actions">{READING_VERSIONS.map(version => <button type="button" key={version} disabled={!versions.includes(version)} aria-disabled={!versions.includes(version)} onClick={() => chooseView(version)} className={cn('library-entry-read', version === versions[0] && 'library-entry-read-primary')}>{version === '翻译' ? <Languages size={16} /> : <FileText size={16} />}阅读{version === '翻译' ? '译文' : '原文'}{versions.includes(version) ? <ArrowRight size={15} /> : <span className="text-xs">待补齐</span>}</button>)}</div>
            </div>
          </div>
        </div>
      </div>
      <div id={panelId} role="tabpanel" className="library-article-reader-panel" hidden={!readerVisible} data-active={readingView !== '简介'}
        aria-hidden={readingView === '简介'} ref={element => { if (element) element.inert = readingView === '简介' }}>
        {auth.status === 'loading' ? <div className="library-entry-shell py-12"><p role="status" className="flex items-center justify-center gap-2 py-20 text-sm text-slate-400"><Loader2 size={18} className="animate-spin" />正在确认阅读权限…</p></div>
          : auth.status !== 'authenticated' ? <div className="library-entry-shell py-12"><div className="library-access-wall"><div aria-hidden="true" className="library-access-preview">{Array.from({ length: 16 }, (_, index) => <div key={index} />)}</div><div className="library-access-cover"><div className="library-access-card"><div className="library-login-emblem"><LockKeyhole size={25} strokeWidth={1.6} /></div><h2>登录后，阅读完整{view === '翻译' ? '译文' : '原文'}</h2><p>卡片介绍、文献简介与搜索片段公开可见。<br />登录已开放账号，即可继续阅读全文。</p><button type="button" className="library-entry-read library-entry-read-primary" onClick={() => setLoginOpen(true)}>登录并继续<ArrowRight size={16} /></button></div></div></div></div>
            : documentVersion ? <LibraryDocument key={slug} slug={paper.slug} version={documentVersion} locationHref={locationHref || undefined}
              onLogin={() => setLoginOpen(true)} onCitation={openCitation}
              onReady={setPreparedVersion}
              controlsId={panelId} leftOpen={leftOpen} rightOpen={rightOpen} setRightOpen={setRightOpen} />
              : <p className="p-12 text-center text-sm text-slate-400">本篇暂未收录这个版本。</p>}
      </div>
      <LibraryLoginDialog open={loginOpen} onClose={() => setLoginOpen(false)} container={article.current} />
    </main>
  )
}

function LibraryDocument({ slug, version, locationHref, onLogin, onCitation, onReady, controlsId, leftOpen, rightOpen, setRightOpen }: {
  slug: string; version: LibraryVersion; locationHref?: string; onLogin: () => void; onCitation: (href: string) => void; controlsId: string; leftOpen: boolean; rightOpen: boolean; setRightOpen: (open: boolean) => void
  onReady: (version: LibraryVersion) => void
}) {
  const content = useRef<HTMLDivElement>(null)
  const [document, setDocument] = useState<{ version: LibraryVersion; raw?: string; references?: Record<string, string>; error?: string } | null>(null)
  const current = document
  const fileContent = current?.raw
  const references = current?.references || {}
  const [highlight, setHighlight] = useState<LibrarySearchHighlight>({ passageId: '', terms: [] })
  const processed = useMemo(() => fileContent ? processLibraryContent(fileContent) : null, [fileContent])

  useEffect(() => {
    if (document?.version === version) onReady(version)
  }, [document, version, onReady])

  useEffect(() => {
    let active = true
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
        setDocument(content === null
          ? { version, error: '这个版本暂时无法加载。' }
          : { version, raw: content, references: nextReferences })
      } catch (cause) {
        if (!active || (cause instanceof Error && cause.name === 'AbortError')) return
        if (cause instanceof LibraryAuthenticationError) libraryAuthClient.invalidate()
        else setDocument({ version, error: cause instanceof Error ? cause.message : '文献库暂时不可用，请稍后重试。' })
      }
    }
    void load()
    return () => { active = false }
  }, [slug, version])

  useEffect(() => {
    if (!fileContent || current?.version !== version) return
    function scrollToTarget() {
      const url = new URL(locationHref || window.location.href, window.location.origin)
      const next = readLibrarySearchHighlight(url.search, url.hash)
      setHighlight(previous => JSON.stringify(previous) === JSON.stringify(next) ? previous : next)
      let id = ''
      try { id = decodeURIComponent(url.hash.slice(1)) } catch { return }
      const target = id ? content.current?.querySelector<HTMLElement>(`#${CSS.escape(id)}`) : null
      const scroller = content.current?.closest<HTMLElement>('[data-library-dialog-scroll]')
      if (target && scroller) scroller.scrollTo({ top: target.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - 62 })
      else target?.scrollIntoView({ block: 'start' })
    }
    const frame = requestAnimationFrame(scrollToTarget)
    const settle = window.setTimeout(scrollToTarget, 350)
    if (!locationHref) {
      window.addEventListener('hashchange', scrollToTarget)
      window.addEventListener('popstate', scrollToTarget)
    }
    return () => { cancelAnimationFrame(frame); clearTimeout(settle); window.removeEventListener('hashchange', scrollToTarget); window.removeEventListener('popstate', scrollToTarget) }
  }, [fileContent, current?.version, slug, version, locationHref])

  const { body, referenceTitle, referenceEntries, headings: rawToc } = processed || { body: '', referenceTitle: '', referenceEntries: [], headings: [] }
  const minLevel = rawToc.length > 0 ? Math.min(...rawToc.map(h => h.level)) : 1
  const contents = (rawToc.length > 0 || referenceEntries.length > 0) ? <nav aria-label="文献目录">
    {rawToc.map(item => <a key={item.slug} href={`#${item.slug}`}
      data-nested={item.level > minLevel || undefined} style={{ paddingInlineStart: `${(item.level - minLevel) * 12}px` }}>
      {renderTextWithMath(item.text)}
    </a>)}
    {referenceEntries.length > 0 && <a href="#references-section">{referenceTitle}</a>}
  </nav> : undefined
  const markdownOptions = useMemo(() => processed && getLibraryMarkdownOptions(processed), [processed])
  // Keep the Markdown tree stable while the drawer and sidebars animate.
  const renderedDocument = useMemo(() => (
    !current ? <div role="status" className="p-20 text-center text-sm text-slate-400">正在加载文献…</div>
        : current.error || !processed || !markdownOptions ? <div role="alert" className="p-20 text-center text-sm text-rose-600">{current.error || '这个版本暂时无法加载。'}</div>
        : <div ref={content} data-library-selection className="reader-paper library-document bg-white p-10 rounded-3xl border border-slate-200">
            <article>
              <Markdown {...markdownOptions} rehypePlugins={[...markdownOptions.rehypePlugins, [rehypeLibrarySearchHighlights, highlight]]}>
                {body}
              </Markdown>
            </article>

            {/* References Section */}
            {referenceEntries.length > 0 && (
              <section id="references-section">
                <h2>{referenceTitle}</h2>
                  {referenceEntries.map((entry, idx) => {
                    const refId = entry.id
                    const refContent = entry.content

                    // Check if this reference has a linked article
                    const currentPaperRefs = references
                    const targetSlug = currentPaperRefs[refId ?? `entry-${idx + 1}`]
                    const hasLink = targetSlug && typeof targetSlug === 'string'

                    return (
                      <div key={idx} id={refId ? `ref-${refId}` : undefined}>
                        {refId && <a href={`#cite-${refId}`}>[{refId}]</a>}
                        <div className="reference-body">
                          {hasLink ? (
                            <Link href={`/library/${targetSlug}`} className="paper-reference">
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
              </section>
            )}
          </div>
  ), [current, processed, markdownOptions, body, highlight, referenceEntries, referenceTitle, references])
  return (
    <LibraryArticleChat slug={slug} version={current?.version || version} onLogin={onLogin} onCitation={onCitation} contents={contents} controlsId={controlsId} leftOpen={leftOpen} rightOpen={rightOpen} setRightOpen={setRightOpen}>
      {renderedDocument}
    </LibraryArticleChat>
  )
}
