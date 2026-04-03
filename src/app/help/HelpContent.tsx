"use client"

import React, { useState, useEffect } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSlug from 'rehype-slug'
import { List, BookOpen, ChevronRight, ChevronDown } from 'lucide-react'
import Link from 'next/link'

interface Heading {
  level: number
  text: string
  slug: string
}

function extractHeadings(markdown: string): Heading[] {
  const headings: Heading[] = []
  const lines = markdown.split(/\r?\n/)
  lines.forEach(line => {
    const match = line.trimEnd().match(/^(#{1,3})\s+(.+)$/)
    if (match) {
      const text = match[2].trim()
      const slug = text.toLowerCase().replace(/\s+/g, '-').replace(/[^\w\u4e00-\u9fa5-]/g, '')
      headings.push({ level: match[1].length, text, slug })
    }
  })
  return headings
}

// 组合多个 markdown 文档的标题，添加分隔标题
function buildToc(featuresHeadings: Heading[], modulesHeadings: Heading[], structureHeadings: Heading[]): (Heading & { renderLevel: number })[] {
  const toc: (Heading & { renderLevel: number })[] = []

  // 功能介绍部分标题（直接用）
  featuresHeadings.forEach(h => toc.push({ ...h, renderLevel: h.level }))

  // 模块介绍（从 06-模块.md 提取 h2 级别的模块标题）
  toc.push({ level: 2, text: '模块介绍', slug: 'modules-section', renderLevel: 2 })
  modulesHeadings
    .filter(h => h.level === 2 && h.text !== '三个蒙特卡洛相关模块的区分')
    .forEach(h => toc.push({ ...h, renderLevel: 3 }))

  // 软件结构（从 01-结构.md 提取 h2 级别标题）
  toc.push({ level: 2, text: '软件结构', slug: 'structure-section', renderLevel: 2 })
  structureHeadings
    .filter(h => h.level === 2 && !h.text.includes('目录结构') && !h.text.includes('方法'))
    .forEach(h => toc.push({ ...h, renderLevel: 3 }))

  return toc
}

interface HelpContentProps {
  helpBody: string
  modulesBody: string
  structureBody: string
}

export default function HelpContent({ helpBody, modulesBody, structureBody }: HelpContentProps) {
  const [modulesOpen, setModulesOpen] = useState(false)
  const [structureOpen, setStructureOpen] = useState(false)
  const [activeHash, setActiveHash] = useState('')

  // 提取各文档标题
  const featuresHeadings = extractHeadings(helpBody)
  const modulesHeadings = extractHeadings(modulesBody)
  const structureHeadings = extractHeadings(structureBody)
  const toc = buildToc(featuresHeadings, modulesHeadings, structureHeadings)

  // 滚动监听，高亮当前标题
  useEffect(() => {
    const handleScroll = () => {
      const headingElements = document.querySelectorAll('h1[id], h2[id], h3[id]')
      let current = ''
      headingElements.forEach(el => {
        const rect = el.getBoundingClientRect()
        if (rect.top <= 120) current = el.id
      })
      setActiveHash(current)
    }
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  return (
    <div className="max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12 flex gap-12 items-start">
      {/* TOC Sidebar */}
      <aside className="hidden lg:block w-64 shrink-0 sticky top-24 max-h-[calc(100vh-8rem)] overflow-y-auto pr-4">
        <div className="mb-6 flex items-center gap-2 text-slate-900 font-black text-base uppercase tracking-widest">
          <List size={18} className="text-blue-600" />
          <span>目录</span>
        </div>
        <nav className="space-y-1 relative border-l-2 border-slate-100">
          {toc.map((item, idx) => {
            const isActive = activeHash === item.slug
            return (
              <a
                key={idx}
                href={`#${item.slug}`}
                className={`
                  block py-2 transition-all border-l-2 -ml-[2px] font-bold
                  ${item.renderLevel === 1 ? 'text-base pl-4' : ''}
                  ${item.renderLevel === 2 ? 'text-sm pl-8 font-normal' : ''}
                  ${item.renderLevel >= 3 ? 'text-xs pl-12 font-normal' : ''}
                  ${isActive ? 'text-blue-600 border-blue-500' : 'text-slate-500 border-transparent hover:text-slate-800 hover:border-slate-300'}
                `}
              >
                {item.text}
              </a>
            )
          })}
        </nav>
      </aside>

      {/* Main Content */}
      <div className="flex-1 min-w-0 space-y-8">
        {/* 功能介绍 + 计算器 + 工作流 + FAQ */}
        <div className="bg-white p-10 rounded-3xl border border-slate-200 shadow-sm">
          <article className="prose prose-slate prose-base max-w-none prose-headings:scroll-mt-28 prose-headings:font-black prose-headings:tracking-tight prose-headings:text-slate-900 prose-h1:text-3xl prose-h2:text-2xl prose-h3:text-xl prose-p:text-slate-600 prose-p:leading-7 prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline prose-strong:text-slate-900 prose-strong:font-bold prose-table:text-sm">
            <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug]}>
              {helpBody}
            </Markdown>
          </article>
        </div>

        {/* 模块介绍（从 06-模块.md 拉取） */}
        <div id="modules-section" className="bg-white p-10 rounded-3xl border border-slate-200 shadow-sm scroll-mt-28">
          <button
            onClick={() => setModulesOpen(!modulesOpen)}
            className="w-full flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg text-white shadow-sm bg-amber-600 shadow-amber-200">
                <BookOpen size={18} />
              </div>
              <h2 className="text-2xl font-black text-slate-900">模块介绍</h2>
            </div>
            {modulesOpen ? <ChevronDown size={20} className="text-slate-400" /> : <ChevronRight size={20} className="text-slate-400" />}
          </button>
          <p className="text-sm text-slate-400 mt-2 ml-12">点击展开查看各模块详细介绍</p>

          {modulesOpen && (
            <article className="prose prose-slate prose-base max-w-none mt-6 prose-headings:scroll-mt-28 prose-headings:font-black prose-headings:tracking-tight prose-headings:text-slate-900 prose-h1:text-3xl prose-h2:text-2xl prose-h3:text-xl prose-p:text-slate-600 prose-p:leading-7 prose-strong:text-slate-900 prose-strong:font-bold prose-table:text-sm">
              <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug]}>
                {modulesBody}
              </Markdown>
            </article>
          )}
        </div>

        {/* 软件结构（从 01-结构.md 拉取） */}
        <div id="structure-section" className="bg-white p-10 rounded-3xl border border-slate-200 shadow-sm scroll-mt-28">
          <button
            onClick={() => setStructureOpen(!structureOpen)}
            className="w-full flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg text-white shadow-sm bg-indigo-600 shadow-indigo-200">
                <BookOpen size={18} />
              </div>
              <h2 className="text-2xl font-black text-slate-900">软件结构</h2>
            </div>
            {structureOpen ? <ChevronDown size={20} className="text-slate-400" /> : <ChevronRight size={20} className="text-slate-400" />}
          </button>
          <p className="text-sm text-slate-400 mt-2 ml-12">点击展开查看系统架构概览</p>

          {structureOpen && (
            <article className="prose prose-slate prose-base max-w-none mt-6 prose-headings:scroll-mt-28 prose-headings:font-black prose-headings:tracking-tight prose-headings:text-slate-900 prose-h1:text-3xl prose-h2:text-2xl prose-h3:text-xl prose-p:text-slate-600 prose-p:leading-7 prose-strong:text-slate-900 prose-strong:font-bold prose-table:text-sm">
              <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug]}>
                {structureBody}
              </Markdown>
            </article>
          )}
        </div>

        {/* Back to Home */}
        <div className="text-center py-4">
          <Link href="/" className="text-sm text-blue-600 hover:text-blue-800 hover:underline">
            &larr; 返回首页
          </Link>
        </div>
      </div>
    </div>
  )
}
