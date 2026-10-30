"use client"

import React, { useState, useEffect } from 'react'
import Markdown from 'react-markdown'
import Link from 'next/link'
import { ArrowLeft, User, Calendar, List, MapPin, Book, Languages } from 'lucide-react'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import '@/components/library/responsive.css'
import { cn } from '@/lib/utils'
import { processLibraryContent, getLibraryMarkdownOptions, getLibraryReferenceMarkdownOptions } from '@/lib/library-markdown'


// Helper to render text with inline math for TOC
function renderTextWithMath(text: string): React.ReactNode {
  const parts: React.ReactNode[] = []
  let lastIndex = 0
  const mathRegex = /\$([^$]+)\$/g
  let match

  while ((match = mathRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index))
    }
    const mathHtml = katex.renderToString(match[1], { throwOnError: false, displayMode: false })
    parts.push(<span key={`math-${match.index}`} dangerouslySetInnerHTML={{ __html: mathHtml }} />)
    lastIndex = match.index + match[0].length
  }

  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex))
  }

  return parts.length > 0 ? parts : text
}

// -------------------------------------------------------------------------
// Read the same selected documents used by library search.
// -------------------------------------------------------------------------
async function fetchFile(slug: string, type: '翻译' | '原文') {
  const response = await fetch(`/api/content?slug=${slug}&type=${type}`)
  if (response.status === 404) return null
  if (!response.ok) throw new Error('文献库暂时不可用，请稍后重试。')
  return response.text()
}

function clearPassageTarget() {
  document.querySelectorAll('.library-reader [data-library-target]').forEach(node => node.removeAttribute('data-library-target'))
}

export default function ArticlePage({ params }: { params: { slug: string } }) {
  const [version, setVersion] = useState<'翻译' | '原文'>('翻译')
  const [versionReady, setVersionReady] = useState(false)
  const [fileContent, setFileContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [hasOriginal, setHasOriginal] = useState(false)
  const [references, setReferences] = useState<Record<string, string>>({})
  const [error, setError] = useState('')

  const slug = params.slug

  useEffect(() => {
    const readVersion = () => {
      setVersion(new URLSearchParams(window.location.search).get('version') === '原文' ? '原文' : '翻译')
      setVersionReady(true)
    }
    readVersion()
    window.addEventListener('popstate', readVersion)
    return () => window.removeEventListener('popstate', readVersion)
  }, [slug])

  function chooseVersion(next: '翻译' | '原文') {
    clearPassageTarget()
    setVersion(next)
    const url = new URL(window.location.href)
    url.searchParams.set('version', next)
    // A passage anchor belongs to one version; discard it when switching.
    if (url.hash.startsWith('#passage-')) url.hash = ''
    window.history.replaceState(window.history.state, '', url)
  }

  // Initial load
  useEffect(() => {
    if (!versionReady) return
    let active = true
    async function load() {
      setLoading(true)
      setError('')
      try {
        const [trans, orig] = await Promise.all([
          fetchFile(slug, '翻译'), fetchFile(slug, '原文'),
        ])
        const actualVersion = version === '翻译' ? (trans ? '翻译' : '原文') : (orig ? '原文' : '翻译')
        const referenceResponse = await fetch(`/api/library/references?slug=${encodeURIComponent(slug)}&type=${encodeURIComponent(actualVersion)}`, { cache: 'no-store' })
        const nextReferences = referenceResponse.ok ? await referenceResponse.json() : {}
        if (!active) return
        setReferences(nextReferences)

        // Only show toggle if BOTH files are found
        setHasOriginal(!!trans && !!orig)

        if (version === '翻译' && trans) {
          setFileContent(trans)
        } else if (version === '原文' && orig) {
          setFileContent(orig)
        } else {
          setFileContent(trans || orig || null)
        }
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : '文献库暂时不可用，请稍后重试。')
      } finally { if (active) setLoading(false) }
    }
    load()
    return () => { active = false }
  }, [slug, version, versionReady])

  useEffect(() => {
    if (loading || !fileContent) return
    function scrollToTarget() {
      clearPassageTarget()
      let id = ''
      try { id = decodeURIComponent(window.location.hash.slice(1)) } catch { return }
      const target = id ? document.getElementById(id) : null
      if (target?.id.startsWith('passage-')) target.setAttribute('data-library-target', 'true')
      target?.scrollIntoView({ block: 'start' })
    }
    const frame = requestAnimationFrame(scrollToTarget)
    const settle = window.setTimeout(scrollToTarget, 350)
    window.addEventListener('hashchange', scrollToTarget)
    return () => { cancelAnimationFrame(frame); clearTimeout(settle); window.removeEventListener('hashchange', scrollToTarget); clearPassageTarget() }
  }, [loading, fileContent, slug, version])

  if (loading) return <div className="p-20 text-center text-slate-400">正在加载文献...</div>
  if (error) return <div className="p-20 text-center text-red-400">{error}</div>
  if (!fileContent) return <div className="p-20 text-center text-red-400">文献未找到 (ID: {slug})</div>

  const processed = processLibraryContent(fileContent)
  const { frontmatter, body, referenceTitle, referenceEntries, headings: rawToc } = processed

  // Normalize TOC levels: Shift so the top-most heading starts at level 1
  const minLevel = rawToc.length > 0 ? Math.min(...rawToc.map(h => h.level)) : 1
  const toc = rawToc.map(h => ({ ...h, renderLevel: h.level - minLevel + 1 }))

  return (
    <main className="library-reader flex-1 bg-slate-50 min-h-screen">
      {/* Top Banner */}
      <div className="bg-white border-b border-slate-200">
        <div className="page-shell max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-10">

           <div className="flex flex-col gap-6">
             <div className="reader-toolbar flex justify-between items-start">
                <div className="flex flex-wrap gap-2">
                  {frontmatter.tags?.map((tag: string) => (
                    <span key={tag} className="flex items-center h-8 px-3 rounded-lg bg-blue-100 text-blue-700 text-sm font-bold uppercase tracking-wider border border-blue-200/50">#{tag}</span>
                  ))}
                </div>

                {/* VERSION TOGGLE - Only if both exist */}
                {hasOriginal && (
                  <div className="flex bg-slate-100 p-0.5 rounded-xl border border-slate-200 h-8">
                    <button
                      onClick={() => chooseVersion('翻译')}
                      className={cn("px-5 h-full rounded-lg text-sm font-black transition-all flex items-center justify-center", version === '翻译' ? "bg-white text-blue-600 shadow-sm" : "text-slate-400 hover:text-slate-600")}
                    >
                      中文
                    </button>
                    <button
                      onClick={() => chooseVersion('原文')}
                      className={cn("px-5 h-full rounded-lg text-sm font-black transition-all flex items-center justify-center", version === '原文' ? "bg-white text-blue-600 shadow-sm" : "text-slate-400 hover:text-slate-600")}
                    >
                      英文
                    </button>
                  </div>
                )}
             </div>

             <div>
               <h1 className="text-3xl md:text-4xl font-black text-slate-900 leading-tight mb-2 flex items-center gap-3">
                 <span>{frontmatter.title}</span>
                 <span className="text-sm font-bold text-white bg-emerald-500 px-2.5 py-1 rounded shrink-0">ID: {slug}</span>
               </h1>
               {frontmatter.title_en && <h2 className="text-xl md:text-2xl font-bold text-slate-400 leading-tight">{frontmatter.title_en}</h2>}
             </div>

             <div className="flex flex-wrap items-center gap-x-8 gap-y-3 text-slate-500 text-sm font-bold">
                <div className="flex items-center gap-2"><div className="p-1.5 bg-blue-50 rounded-lg"><User size={16} className="text-blue-500" /></div>{frontmatter.author}</div>
                {frontmatter.affiliation && <div className="flex items-center gap-2"><div className="p-1.5 bg-blue-50 rounded-lg"><MapPin size={16} className="text-blue-500" /></div>{frontmatter.affiliation}</div>}
                {frontmatter.publication && <div className="flex items-center gap-2"><div className="p-1.5 bg-blue-50 rounded-lg"><Book size={16} className="text-blue-500" /></div><span className="italic">{frontmatter.publication}</span></div>}
                <div className="flex items-center gap-2"><div className="p-1.5 bg-blue-50 rounded-lg"><Calendar size={16} className="text-blue-500" /></div>{frontmatter.year}</div>
             </div>
           </div>
        </div>
      </div>

      <div className="reader-layout page-shell max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12 flex gap-12 items-start">
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
              <Markdown {...getLibraryMarkdownOptions(processed)}>
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
    </main>
  )
}
