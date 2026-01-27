import React from 'react'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { INITIAL_METHOD_TREE, MethodNode } from '@/lib/methods'
import { ArrowLeft, Code, ExternalLink, Info, Sigma, BookOpen } from 'lucide-react'
import { cn } from '@/lib/utils'
import { AlgorithmDetail } from '@/components/AlgorithmDetail'
import 'katex/dist/katex.min.css'
import katex from 'katex'

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

// Find a method by ID (flatten the tree)
function findMethodById(methodId: string): { category: MethodNode; method?: MethodNode } | null {
  for (const category of INITIAL_METHOD_TREE) {
    // If the methodId matches a category, return the category
    if (category.id === methodId) {
      return { category }
    }
    // If the methodId matches a child method, return both
    if (category.children) {
      const method = category.children.find(m => m.id === methodId)
      if (method) {
        return { category, method }
      }
    }
  }
  return null
}

interface MethodDetailPageProps {
  params: { methodId: string }
}

export default function MethodDetailPage({ params }: MethodDetailPageProps) {
  const { methodId } = params
  const result = findMethodById(methodId)

  if (!result) {
    notFound()
  }

  const { category, method } = result

  // If methodId is a category (not a specific method), show category overview
  if (!method) {
    return <CategoryOverview category={category} />
  }

  // Show specific method detail
  return <MethodDetail category={category} method={method} />
}

// Category Overview Component
function CategoryOverview({ category }: { category: MethodNode }) {
  return (
    <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12">
      {/* Header */}
      <div className="mb-8">
        <Link
          href="/methods"
          className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-800 transition-colors font-bold mb-4"
        >
          <ArrowLeft size={18} />
          返回方法总览
        </Link>
        <div className="flex items-center gap-3 mb-3">
          <span className="px-3 py-1 bg-amber-600 text-white text-xs font-bold rounded-full">
            {category.shortName}
          </span>
        </div>
        <h1 className="text-3xl font-black text-slate-900 mb-2">{category.name}</h1>
      </div>

      {/* Description Card */}
      <div className="mb-8 bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Info className="text-amber-500" size={18} />
          <span className="font-bold text-slate-900">类别概述</span>
        </div>
        <p className="text-slate-600 leading-relaxed">{category.description}</p>
      </div>

      {/* Formula */}
      <div className="mb-8 p-6 bg-slate-900 rounded-2xl overflow-x-auto">
        <div className="flex items-center gap-2 mb-4">
          <Sigma className="text-amber-400" size={20} />
          <span className="text-sm font-bold text-slate-300 uppercase tracking-wider">核心公式</span>
        </div>
        <div className="text-white">
          <LatexRenderer math={category.formula} block />
        </div>
      </div>

      {/* Methods in this category */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 mb-4">该类别下的具体算法</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {category.children?.map((child) => (
            <Link
              key={child.id}
              href={`/methods/${child.id}`}
              className="p-5 bg-white rounded-2xl border border-slate-200 hover:border-amber-300 hover:shadow-md transition-all"
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-mono text-amber-600 bg-amber-50 px-2 py-0.5 rounded border border-amber-100">
                  {child.shortName}
                </span>
              </div>
              <h3 className="font-bold text-slate-800 mb-2">{child.name}</h3>
              <p className="text-sm text-slate-500 line-clamp-2">{child.description}</p>
            </Link>
          ))}
        </div>
      </div>
    </section>
  )
}

// Method Detail Component
function MethodDetail({ category, method }: { category: MethodNode; method: MethodNode }) {
  return (
    <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12">
      {/* Header */}
      <div className="mb-8">
        <Link
          href="/methods"
          className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-800 transition-colors font-bold mb-6"
        >
          <ArrowLeft size={18} />
          返回方法总览
        </Link>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-black text-slate-900">{method.name}</h1>
            <span className="text-lg font-mono text-slate-400">{method.shortName.toUpperCase()}</span>
          </div>

          {/* Calculator Application Link */}
          <Link
            href={`/?method=${method.id}`}
            className="inline-flex items-center gap-2 px-5 py-3 bg-blue-600 text-white hover:bg-blue-700 font-bold rounded-xl transition-all"
          >
            <Sigma size={18} />
            在计算器中应用
            <ExternalLink size={14} />
          </Link>
        </div>
      </div>

      {/* Full-width Content */}
      <div className="space-y-8">
        {/* Algorithm Documentation (from MD file) - includes all content */}
        {'slug' in method && method.hasDetail && method.slug && (
          <AlgorithmDetail slug={method.slug} />
        )}

        {/* Process Variables - Placeholder for future expansion */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2">
            <Code className="text-amber-500" size={18} />
            <span className="font-bold text-slate-900">过程量可视化</span>
            <span className="ml-auto text-xs text-slate-400">待完善</span>
          </div>
          <div className="p-8 text-center">
            <p className="text-slate-400">该方法的中间过程量展示正在开发中...</p>
          </div>
        </div>
      </div>
    </section>
  )
}
