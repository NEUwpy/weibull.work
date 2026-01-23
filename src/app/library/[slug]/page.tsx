"use client"

import React, { useState, useEffect } from 'react'
import matter from 'gray-matter'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeSlug from 'rehype-slug'
import rehypeKatex from 'rehype-katex'
import rehypeRaw from 'rehype-raw'
import Link from 'next/link'
import { ArrowLeft, User, Calendar, List, MapPin, Book, Languages } from 'lucide-react'
import 'katex/dist/katex.min.css'
import { cn } from '@/lib/utils'

// -------------------------------------------------------------------------
// REFACTOR: Moving heavy logic to a shared processing function
// -------------------------------------------------------------------------

function processContent(rawMarkdown: string) {
  const { data, content } = matter(rawMarkdown)

  // 1. Split content into Main Body and References
  // Match any level of header (#, ##, ###) followed by 参考文献 or References
  const refSplitRegex = /(#+\s*(?:参考文献|References))/i
  const splitMatch = content.match(refSplitRegex)

  let mainBody = content
  let referenceTitle = '参考文献'
  let referenceList: string[] = []

  if (splitMatch && splitMatch.index !== undefined) {
    mainBody = content.substring(0, splitMatch.index)
    referenceTitle = splitMatch[1].replace(/#+\s*/, '')

    const rawRefs = content.substring(splitMatch.index + splitMatch[0].length)
    const refLines = rawRefs.split(/\r?\n/)
    let currentRef = ''

    refLines.forEach(line => {
      const trimmed = line.trim()
      if (!trimmed) return

      // Match [1], 1., (1), etc.
      if (/^(\[\d+\]|\d+\.|\(\d+\))/.test(trimmed)) {
        if (currentRef) referenceList.push(currentRef)
        currentRef = trimmed
      } else {
        if (currentRef) currentRef += ' ' + trimmed
      }
    })
    if (currentRef) referenceList.push(currentRef)
  }

  // 2. Preprocess Main Body (Math & Citations)
  const normalizedBody = mainBody
    .replace(/\$\$(.*?)\$\$/g, (match, body) => {
      if (body.includes('\\') || body.length > 20) return `\n$$\n${body.trim()}\n$$\n`
      return match
    })
    .replace(/(\[[1-9][0-9]*(?:,-?[1-9][0-9]*)*\])/g, (match) => {
       return `<sup><a href="#ref-${match.replace(/[[\]]/g, '')}" class="no-underline text-blue-600 hover:underline">${match}</a></sup>`
    })

  // 3. Fix Image URLs and mark image captions
  // After an image, mark the next paragraph if it's short (likely a caption)
  const imageProcessedBody = normalizedBody.replace(/(!\[.*?\]\(.*?\))\n+([^\n]+)\n*/g, (match, imageMd, nextLine) => {
    const encodedPath = imageMd.replace(/(!\[.*?\])\((.*?)\)/g, (match, alt, path) => {
      return `${alt}(${path.replace(/ /g, '%20')})`
    })
    // Check if the next line looks like a caption (short text)
    let trimmedLine = nextLine.trim()
    const isLikelyCaption = trimmedLine.length > 0 && trimmedLine.length < 200

    if (isLikelyCaption) {
      // Convert markdown bold **text** to HTML <strong>text</strong>
      trimmedLine = trimmedLine.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      return `${encodedPath}\n\n<p class="figure-caption">${trimmedLine}</p>\n\n`
    }
    return `${encodedPath}\n\n${nextLine}\n`
  })

  // 4. Mark table captions (short paragraph before/after a table)
  const tableProcessedBody = imageProcessedBody.replace(
    /([^\n]{5,200})\n\n(\|[^\n]+\|[^\n]*\n(?:\|[-:\s|]+\|[^\n]*\n)?(?:[^\n]*\|[^\n]*\n)+)/g,
    (match, captionLine, tableMd) => {
      let trimmedCaption = captionLine.trim()
      // Don't mark if it looks like a regular paragraph (contains period, very long, etc.)
      if (trimmedCaption.includes('。') || trimmedCaption.includes('.') || trimmedCaption.length > 150) {
        return match
      }
      // Convert markdown bold **text** to HTML <strong>text</strong>
      trimmedCaption = trimmedCaption.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      return `<p class="table-caption">${trimmedCaption}</p>\n\n${tableMd}`
    }
  )

  // Handle remaining images that weren't followed by captions
  const finalBody = tableProcessedBody.replace(/(!\[.*?\])\((.*?)\)/g, (match, alt, path) => {
    const encodedPath = path.replace(/ /g, '%20')
    return `${alt}(${encodedPath})`
  })

  return { frontmatter: data, body: finalBody, referenceTitle, referenceList }
}

function extractHeadings(markdown: string) {
  const headings: { level: number; text: string; slug: string }[] = []
  const lines = markdown.split(/\r?\n/)
  // Strict regex: Headings must start at line beginning
  const headingRegex = /^(#{1,3})\s+(.+)$/

  lines.forEach(line => {
    const match = line.trimEnd().match(headingRegex)
    if (match) {
      const text = match[2].trim()
      const slug = text.toLowerCase().replace(/\s+/g, '-').replace(/[^\w\u4e00-\u9fa5-]/g, '')
      headings.push({ level: match[1].length, text, slug })
    }
  })
  return headings
}

// -------------------------------------------------------------------------
// API Simulation (Since we are in a client component now)
// -------------------------------------------------------------------------
async function fetchFile(slug: string, type: '翻译' | '原文') {
  const response = await fetch(`/api/content?slug=${slug}&type=${type}`)
  if (!response.ok) return null
  return response.text()
}

export default function ArticlePage({ params }: { params: { slug: string } }) {
  const [version, setVersion] = useState<'翻译' | '原文'>('翻译')
  const [fileContent, setFileContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [hasOriginal, setHasOriginal] = useState(false)

  const slug = params.slug

  // Initial load
  useEffect(() => {
    async function load() {
      setLoading(true)
      const trans = await fetchFile(slug, '翻译')
      const orig = await fetchFile(slug, '原文')
      
      // Only show toggle if BOTH files are found
      setHasOriginal(!!trans && !!orig)
      
      if (version === '翻译' && trans) {
        setFileContent(trans)
      } else if (version === '原文' && orig) {
        setFileContent(orig)
      } else {
        setFileContent(trans || orig || null)
      }
      setLoading(false)
    }
    load()
  }, [slug, version])

  if (loading) return <div className="p-20 text-center text-slate-400">正在加载文献...</div>
  if (!fileContent) return <div className="p-20 text-center text-red-400">文献未找到 (ID: {slug})</div>

  const { frontmatter, body, referenceTitle, referenceList } = processContent(fileContent)
  const rawToc = extractHeadings(body)
  
  // Normalize TOC levels: Shift so the top-most heading starts at level 1
  const minLevel = rawToc.length > 0 ? Math.min(...rawToc.map(h => h.level)) : 1
  const toc = rawToc.map(h => ({ ...h, renderLevel: h.level - minLevel + 1 }))

  return (
    <main className="flex-1 bg-slate-50 min-h-screen">
      {/* Top Banner */}
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-10">
           
           <div className="flex flex-col gap-6">
             <div className="flex justify-between items-start">
                <div className="flex flex-wrap gap-2">
                  {frontmatter.tags?.map((tag: string) => (
                    <span key={tag} className="flex items-center h-8 px-3 rounded-lg bg-blue-100 text-blue-700 text-sm font-bold uppercase tracking-wider border border-blue-200/50">#{tag}</span>
                  ))}
                </div>
                
                {/* VERSION TOGGLE - Only if both exist */}
                {hasOriginal && (
                  <div className="flex bg-slate-100 p-0.5 rounded-xl border border-slate-200 h-8">
                    <button 
                      onClick={() => setVersion('翻译')}
                      className={cn("px-5 h-full rounded-lg text-sm font-black transition-all flex items-center justify-center", version === '翻译' ? "bg-white text-blue-600 shadow-sm" : "text-slate-400 hover:text-slate-600")}
                    >
                      中文
                    </button>
                    <button 
                      onClick={() => setVersion('原文')}
                      className={cn("px-5 h-full rounded-lg text-sm font-black transition-all flex items-center justify-center", version === '原文' ? "bg-white text-blue-600 shadow-sm" : "text-slate-400 hover:text-slate-600")}
                    >
                      英文
                    </button>
                  </div>
                )}
             </div>
             
             <div>
               <h1 className="text-3xl md:text-4xl font-black text-slate-900 leading-tight mb-2">{frontmatter.title}</h1>
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

      <div className="max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12 flex gap-12 items-start">
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
                             {item.text}
                           </a>
                         ))}
                         {referenceList.length > 0 && (
                            <a href="#references-section" className="block py-2 transition-all border-l-2 -ml-[2px] pl-4 font-bold text-base text-slate-800 hover:border-blue-500 hover:text-blue-600 border-transparent">
                              {referenceTitle}
                            </a>
                         )}
                      </nav>
        </aside>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="bg-white p-10 rounded-3xl border border-slate-200 shadow-sm">
            <article className="prose prose-slate prose-base max-w-none prose-headings:scroll-mt-28 prose-headings:font-black prose-headings:tracking-tight prose-headings:text-slate-900 prose-h1:text-3xl prose-h2:text-2xl prose-h3:text-xl prose-p:text-slate-600 prose-p:leading-7 prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline prose-strong:text-slate-900 prose-strong:font-bold prose-code:text-blue-600 prose-code:bg-blue-50 prose-code:px-1 prose-code:rounded prose-pre:bg-slate-900 prose-pre:shadow-lg prose-pre:rounded-2xl prose-img:rounded-lg prose-img:max-w-[33%] prose-img:mx-auto prose-img:my-6">
              <Markdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeRaw, rehypeSlug, rehypeKatex]}>
                {body}
              </Markdown>
            </article>

            {/* References Section */}
            {referenceList.length > 0 && (
              <div id="references-section" className="mt-16 pt-10 border-t border-slate-100 scroll-mt-28">
                <h2 className="text-2xl font-black text-slate-900 mb-6">{referenceTitle}</h2>
                <div className="space-y-4">
                  {referenceList.map((refItem, idx) => {
                    // Try to extract ID in format [1], 1., or (1)
                    // Improved regex to catch [1], [ 1 ], 1., (1)
                    const refIdMatch = refItem.match(/^(\[\s*\d+\s*\]|\d+\.|\(\d+\))/)
                    const refId = refIdMatch ? refIdMatch[1].replace(/[\[\]().\s]/g, '') : idx + 1
                    
                    // Strip the ID from the content
                    const refContent = refItem.replace(/^(\[\s*\d+\s*\]|\d+\.|\(\d+\))\s*/, '')
                    
                    return (
                      <div key={idx} id={`ref-${refId}`} className="flex gap-4 text-sm text-slate-600 leading-relaxed group scroll-mt-32">
                        <span className="font-bold text-slate-400 select-none shrink-0 group-hover:text-blue-500 transition-colors">[{refId}]</span>
                        <div>{refContent}</div>
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
