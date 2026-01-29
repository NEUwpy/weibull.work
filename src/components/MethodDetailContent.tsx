import React, { useState, useEffect } from 'react'
import { Sigma, Info } from 'lucide-react'
import katex from 'katex'
import matter from 'gray-matter'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import rehypeRaw from 'rehype-raw'
import 'katex/dist/katex.min.css'
import { cn } from '@/lib/utils'
import { MethodNode } from '@/lib/methods'

// KaTeX Renderer Component with timeout protection
const LatexRenderer = ({ math, block = false }: { math: string, block?: boolean }) => {
  const [renderedHtml, setRenderedHtml] = React.useState<string | null>(null)
  const [error, setError] = React.useState<boolean>(false)

  React.useEffect(() => {
    let timeoutId: NodeJS.Timeout

    try {
      timeoutId = setTimeout(() => {
        setError(true)
        console.error('[LatexRenderer] Timeout rendering formula:', math.substring(0, 50) + '...')
      }, 5000) // 5 second timeout

      const html = katex.renderToString(math, {
        throwOnError: false,
        displayMode: block,
        trust: true,
        strict: false
      })

      clearTimeout(timeoutId)
      setRenderedHtml(html)
    } catch (e) {
      clearTimeout(timeoutId)
      setError(true)
      console.error('[LatexRenderer] Error rendering formula:', e)
    }

    return () => clearTimeout(timeoutId)
  }, [math, block])

  if (error) {
    return <span className="text-amber-500 font-mono text-xs break-all">{math}</span>
  }

  if (!renderedHtml) {
    return <span className="text-slate-300 font-mono text-xs">Loading formula...</span>
  }

  return <div className={cn("overflow-x-auto", block ? "py-2" : "inline")} dangerouslySetInnerHTML={{ __html: renderedHtml }} />
}

interface MethodDetailContentProps {
  method: MethodNode
  category?: {
    shortName: string
    name: string
  }
}

/**
 * 方法详情内容组件
 * 用于展示方法的核心公式和描述
 * 在计算器弹窗和方法详情页中共享使用
 */
export function MethodDetailContent({ method, category }: MethodDetailContentProps) {
  const [mdContent, setMdContent] = useState<string | null>(null)
  const [frontmatter, setFrontmatter] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  // Track render count to detect infinite loops
  const renderCount = React.useRef(0)
  renderCount.current += 1
  if (renderCount.current > 50) {
    console.error('[MethodDetailContent] INFINITE RENDER LOOP! Count:', renderCount.current)
  }

  useEffect(() => {
    console.log('[MethodDetailContent] Starting load for:', method.slug, 'render #:', renderCount.current)
    let cancelled = false

    async function loadAlgorithmDoc() {
      // Check if method has a detailed MD file
      if (!method.slug) {
        setLoading(false)
        return
      }

      try {
        console.log('[MethodDetailContent] Fetching:', method.slug)
        const response = await fetch(`/api/algorithms?slug=${method.slug}`)
        console.log('[MethodDetailContent] Response received:', response.status)
        if (!response.ok || cancelled) {
          setLoading(false)
          return
        }
        const text = await response.text()
        console.log('[MethodDetailContent] Parsing frontmatter, text length:', text.length)
        const { data, content: mdContent } = matter(text)
        console.log('[MethodDetailContent] Frontmatter parsed, setting state')
        if (!cancelled) {
          setFrontmatter(data)
          setMdContent(mdContent)
          console.log('[MethodDetailContent] State updated')
        }
      } catch (err) {
        console.error('Failed to load algorithm doc:', err)
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }
    loadAlgorithmDoc()

    // Cleanup function to cancel async operations
    return () => {
      console.log('[MethodDetailContent] Cleanup for:', method.slug)
      cancelled = true
    }
  }, [method.slug])

  // If MD content exists, show full documentation
  if (mdContent && frontmatter) {
    return (
      <div className="space-y-6">
        {/* Formula from MD */}
        {frontmatter.formula && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-slate-900 font-bold text-sm uppercase tracking-wider">
              <Sigma size={16} className="text-blue-500" />
              核心公式 (Formula)
            </div>
            <div className="bg-slate-900 rounded-2xl p-6 shadow-inner overflow-x-auto border border-slate-800">
              <div className="text-white">
                <LatexRenderer math={frontmatter.formula} block />
              </div>
            </div>
          </div>
        )}

        {/* Description from MD */}
        {frontmatter.description && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-slate-900 font-bold text-sm uppercase tracking-wider">
              <Info size={16} className="text-blue-500" />
              算法描述 (Description)
            </div>
            <div className="bg-slate-50 p-6 rounded-2xl border border-slate-100 text-slate-600 leading-relaxed text-sm">
              {frontmatter.description}
            </div>
          </div>
        )}

        {/* Variables */}
        {frontmatter.variables && frontmatter.variables.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-slate-900 font-bold text-sm uppercase tracking-wider">
              <Info size={16} className="text-blue-500" />
              变量说明
            </div>
            <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-3 text-left font-bold text-slate-900">符号</th>
                    <th className="px-4 py-3 text-left font-bold text-slate-900">说明</th>
                    <th className="px-4 py-3 text-left font-bold text-slate-900">范围</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {frontmatter.variables.map((v: any, i: number) => (
                    <tr key={i}>
                      <td className="px-4 py-3 text-blue-600 font-mono">{v.symbol}</td>
                      <td className="px-4 py-3 text-slate-600">{v.description}</td>
                      <td className="px-4 py-3 text-slate-500">{v.range || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* MD Content */}
        {mdContent && (
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <article className="prose prose-slate prose-sm max-w-none">
              <Markdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeRaw, rehypeKatex]}
              >
                {mdContent}
              </Markdown>
            </article>
          </div>
        )}
      </div>
    )
  }

  // Fallback: show basic info from JSON
  return (
    <div className="space-y-8">
      {/* Formula Section */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-slate-900 font-bold text-sm uppercase tracking-wider">
          <Sigma size={16} className="text-blue-500" />
          核心公式 (Formula)
        </div>
        <div className="bg-slate-900 rounded-2xl p-6 shadow-inner overflow-x-auto border border-slate-800">
          <div className="text-white">
            <LatexRenderer math={method.formula} block />
          </div>
        </div>
      </div>

      {/* Description Section */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-slate-900 font-bold text-sm uppercase tracking-wider">
          <Info size={16} className="text-blue-500" />
          算法描述 (Description)
        </div>
        <div className="bg-slate-50 p-6 rounded-2xl border border-slate-100 text-slate-600 leading-relaxed text-sm">
          {method.description}
        </div>
      </div>

      {/* No detailed doc warning */}
      {!method.slug && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-700">
          该方法暂无详细文档，仅显示基本信息。
        </div>
      )}
    </div>
  )
}
