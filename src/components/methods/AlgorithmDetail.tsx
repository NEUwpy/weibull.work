"use client"

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import matter from 'gray-matter'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeSlug from 'rehype-slug'
import rehypeKatex from 'rehype-katex'
import rehypeRaw from 'rehype-raw'
import rehypeAutolinkHeadings from 'rehype-autolink-headings'
import katex from 'katex'
import mermaid from 'mermaid'
import 'katex/dist/katex.min.css'
import { cn } from '@/lib/utils'
import { BookOpen, CheckCircle, XCircle, Sigma, Info } from 'lucide-react'

// Initialize Mermaid
if (typeof window !== 'undefined') {
  mermaid.initialize({
    startOnLoad: false,
    theme: 'base',
    themeVariables: {
      primaryColor: '#fef3c7',
      primaryTextColor: '#1e293b',
      primaryBorderColor: '#f59e0b',
      lineColor: '#cbd5e1',
      secondaryColor: '#ecfdf5',
      tertiaryColor: '#f8fafc',
      fontSize: '17px',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      background: '#ffffff',
      nodeBorder: 2,
    },
    flowchart: {
      useMaxWidth: true,
      htmlLabels: true,
      curve: 'basis',
      padding: 20,
    },
  })
}

// KaTeX Renderer Component
const LatexRenderer = ({ math, block = false }: { math: string, block?: boolean }) => {
  try {
    const html = katex.renderToString(math, {
      throwOnError: false,
      displayMode: block,
      trust: true,
      strict: false
    })
    return <div className={cn("overflow-x-auto", block ? "py-2" : "inline")} dangerouslySetInnerHTML={{ __html: html }} />
  } catch (e) {
    return <span className="text-red-500 font-mono text-xs">LaTeX Error</span>
  }
}

// Mermaid Renderer Component
const MermaidRenderer = ({ chart }: { chart: string }) => {
  const [svg, setSvg] = useState<string>('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    mermaid.render('mermaid-chart', chart).then((result) => {
      setSvg(result.svg)
    }).catch((err) => {
      setError(err.message)
    })
  }, [chart])

  if (error) {
    return <div className="text-red-500 text-sm">流程图渲染错误: {error}</div>
  }

  if (!svg) {
    return <div className="text-slate-400 text-sm">加载流程图中...</div>
  }

  return (
    <div className="flex justify-center">
      <div dangerouslySetInnerHTML={{ __html: svg }} className="w-full" />
    </div>
  )
}

interface AlgorithmDetailProps {
  slug: string
}

export function AlgorithmDetail({ slug }: AlgorithmDetailProps) {
  const [content, setContent] = useState<string | null>(null)
  const [frontmatter, setFrontmatter] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadAlgorithmDoc() {
      try {
        setLoading(true)
        const response = await fetch(`/api/algorithms?slug=${slug}`)
        if (!response.ok) {
          throw new Error('Failed to load algorithm documentation')
        }
        const text = await response.text()
        const { data, content: mdContent } = matter(text)
        setFrontmatter(data)
        setContent(mdContent)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }
    loadAlgorithmDoc()
  }, [slug])

  if (loading) {
    return (
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 text-center">
        <div className="text-slate-400">加载算法文档中...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 text-center">
        <div className="text-red-400">文档加载失败: {error}</div>
      </div>
    )
  }

  if (!content) {
    return (
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 text-center">
        <div className="text-slate-400">暂无详细文档</div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Algorithm Description */}
      {frontmatter?.description && (
        <div className="text-slate-600 leading-relaxed text-base -mt-4">
          {frontmatter.description}
        </div>
      )}

      {/* Core Formula */}
      {frontmatter?.formula && (
        <div className="bg-slate-900 rounded-2xl p-6 shadow-inner overflow-x-auto border border-slate-800">
          <div className="flex items-center gap-2 mb-4">
            <Sigma className="text-amber-400" size={20} />
            <span className="text-sm font-bold text-slate-300 uppercase tracking-wider">核心公式</span>
          </div>
          <div className="text-white">
            <LatexRenderer math={frontmatter.formula} block />
          </div>
        </div>
      )}

      {/* Variable Definitions */}
      {frontmatter?.variables && (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <h3 className="font-bold text-slate-900 mb-4">变量说明</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-left font-bold text-slate-900">符号</th>
                  <th className="px-4 py-3 text-left font-bold text-slate-900">说明</th>
                  <th className="px-4 py-3 text-left font-bold text-slate-900">单位/范围</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {frontmatter.variables.map((variable: any, index: number) => (
                  <tr key={index}>
                    <td className="px-4 py-3 text-blue-600 font-mono">{variable.symbol}</td>
                    <td className="px-4 py-3 text-slate-600">{variable.description}</td>
                    <td className="px-4 py-3 text-slate-500">{variable.range || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Applicability & Related Papers - Side by Side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Applicability */}
        {frontmatter?.applicability && (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
            <h3 className="font-bold text-slate-900 mb-4">适用场景</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="flex items-center gap-2">
                {frontmatter.applicability.complete_sample ? (
                  <CheckCircle size={16} className="text-emerald-500" />
                ) : (
                  <XCircle size={16} className="text-slate-300" />
                )}
                <span className="text-sm text-slate-600">完全样本</span>
              </div>
              <div className="flex items-center gap-2">
                {frontmatter.applicability.censored_sample ? (
                  <CheckCircle size={16} className="text-emerald-500" />
                ) : (
                  <XCircle size={16} className="text-slate-300" />
                )}
                <span className="text-sm text-slate-600">截尾样本</span>
              </div>
              <div className="flex items-center gap-2">
                {frontmatter.applicability.small_sample ? (
                  <CheckCircle size={16} className="text-emerald-500" />
                ) : (
                  <XCircle size={16} className="text-slate-300" />
                )}
                <span className="text-sm text-slate-600">小样本</span>
              </div>
              <div className="flex items-center gap-2">
                {frontmatter.applicability.large_sample ? (
                  <CheckCircle size={16} className="text-emerald-500" />
                ) : (
                  <XCircle size={16} className="text-slate-300" />
                )}
                <span className="text-sm text-slate-600">大样本</span>
              </div>
            </div>
          </div>
        )}

        {/* Related Papers */}
        {frontmatter?.references && frontmatter.references.length > 0 && (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
            <div className="flex items-center gap-2 mb-4">
              <BookOpen className="text-amber-500" size={18} />
              <h3 className="font-bold text-slate-900">相关文献</h3>
            </div>
            <div className="space-y-3">
              {frontmatter.references.map((ref: any, index: number) => (
                <Link
                  key={index}
                  href={`/library/${ref.id}`}
                  className="block px-4 py-3 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-medium rounded-xl transition-all border border-emerald-100"
                >
                  <div className="font-semibold text-sm">{ref.title}</div>
                  <div className="text-xs text-emerald-600 mt-1">
                    {ref.author} ({ref.year})
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Algorithm Flow Chart */}
      {frontmatter?.flowchart && (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2">
            <Sigma className="text-amber-500" size={18} />
            <span className="font-bold text-slate-900">计算流程</span>
          </div>
          <div className="p-6">
            <MermaidRenderer chart={frontmatter.flowchart} />
          </div>
        </div>
      )}

      {/* Algorithm Documentation */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="px-8 py-6 border-b border-slate-100 bg-slate-50/50">
          <div className="flex items-center gap-4">
            <div className="px-3 py-1 bg-blue-600 text-white text-xs font-bold rounded-full">
              算法文档
            </div>
            {frontmatter && (
              <div className="text-sm text-slate-500">
                {frontmatter.short_name} · {frontmatter.category}
              </div>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="p-8">
          <article className="prose prose-slate prose-base max-w-none
          prose-headings:scroll-mt-28
          prose-headings:font-black
          prose-headings:tracking-tight
          prose-headings:text-slate-900
          prose-h1:text-2xl
          prose-h2:text-xl
          prose-h3:text-lg
          prose-h4:text-base
          prose-p:text-slate-600
          prose-p:leading-7
          prose-a:text-blue-600
          prose-a:no-underline
          hover:prose-a:underline
          prose-strong:text-slate-900
          prose-strong:font-bold
          prose-code:text-blue-600
          prose-code:bg-blue-50
          prose-code:px-1
          prose-code:rounded
          prose-code:py-0.5
          prose-code:text-sm
          prose-pre:bg-slate-900
          prose-pre:text-white
          prose-pre:shadow-lg
          prose-pre:rounded-2xl
          prose-table:my-6
          prose-table:text-sm
          prose-thead:bg-slate-50
          prose-thead:border-b
          prose-thead:border-slate-200
          prose-th:text-left
          prose-th:font-bold
          prose-th:text-slate-900
          prose-th:px-4
          prose-th:py-3
          prose-td:border-b
          prose-td:border-slate-100
          prose-td:px-4
          prose-td:py-3
          prose-td:text-slate-600
          prose-blockquote:border-l-4
          prose-blockquote:border-blue-500
          prose-blockquote:bg-blue-50
          prose-blockquote:py-2
          prose-blockquote:px-4
          prose-blockquote:italic
          prose-blockquote:text-slate-600
          prose-ul:list-disc
          prose-ul:pl-6
          prose-ol:decimal
          prose-ol:pl-6
          prose-li:my-1
        ">
          <Markdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeRaw, rehypeSlug, rehypeKatex, rehypeAutolinkHeadings]}
          >
            {content}
          </Markdown>
        </article>
        </div>
      </div>
    </div>
  )
}
