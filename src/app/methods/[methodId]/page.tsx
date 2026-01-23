import React from 'react'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { INITIAL_METHOD_TREE, MethodNode } from '@/lib/methods'
import { ArrowLeft, BookOpen, Sigma, Info, Code, PlayCircle, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'
import 'katex/dist/katex.min.css'
import katex from 'katex'

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
        <h1 className="text-3xl font-black text-slate-900 mb-2">{category.name}</h1>
        <p className="text-slate-500">{category.shortName} — {category.description}</p>
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
      <div className="mb-8 flex items-center justify-between">
        <div>
          <Link
            href="/methods"
            className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-800 transition-colors font-bold mb-4"
          >
            <ArrowLeft size={18} />
            返回方法总览
          </Link>
          <div className="flex items-center gap-3 mb-2">
            <span className="px-3 py-1 bg-amber-600 text-white text-xs font-bold rounded-full">
              {category.shortName}
            </span>
            <span className="text-sm font-mono text-slate-400">{method.id}</span>
          </div>
          <h1 className="text-3xl font-black text-slate-900 mb-1">{method.name}</h1>
          <p className="text-slate-500">{method.shortName}</p>
        </div>

        {/* Link to Library */}
        <Link
          href="/library/181-004"
          className="inline-flex items-center gap-2 px-5 py-3 bg-emerald-50 text-emerald-600 border border-emerald-100 hover:bg-emerald-100 font-bold rounded-xl transition-all"
        >
          <BookOpen size={18} />
          查看相关文献
          <ExternalLink size={14} />
        </Link>
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Content (2/3) */}
        <div className="lg:col-span-2 space-y-8">
          {/* Formula Section */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2">
              <Sigma className="text-amber-500" size={18} />
              <span className="font-bold text-slate-900">核心公式</span>
            </div>
            <div className="p-6 bg-slate-900">
              <div className="text-white overflow-x-auto">
                <LatexRenderer math={method.formula} block />
              </div>
            </div>
          </div>

          {/* Description Section */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2">
              <Info className="text-amber-500" size={18} />
              <span className="font-bold text-slate-900">方法描述</span>
            </div>
            <div className="p-6">
              <p className="text-slate-600 leading-relaxed">{method.description}</p>
            </div>
          </div>

          {/* Algorithm Flow - Placeholder for future expansion */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2">
              <PlayCircle className="text-amber-500" size={18} />
              <span className="font-bold text-slate-900">算法流程</span>
              <span className="ml-auto text-xs text-slate-400">待完善</span>
            </div>
            <div className="p-8 text-center">
              <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Code size={24} className="text-slate-300" />
              </div>
              <p className="text-slate-400">该方法的详细算法流程正在开发中...</p>
              <p className="text-sm text-slate-300 mt-2">请稍后回来查看完整内容</p>
            </div>
          </div>

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

        {/* Sidebar (1/3) */}
        <div className="space-y-6">
          {/* Quick Info */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
            <h3 className="font-bold text-slate-900 mb-4">快速信息</h3>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-slate-500">方法ID</dt>
                <dd className="font-mono text-amber-600 bg-amber-50 px-2 py-0.5 rounded">{method.id}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">所属类别</dt>
                <dd className="font-medium text-slate-700">{category.shortName}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">缩写</dt>
                <dd className="font-mono text-slate-700">{method.shortName}</dd>
              </div>
            </dl>
          </div>

          {/* Actions */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
            <h3 className="font-bold text-slate-900 mb-4">快捷操作</h3>
            <div className="space-y-3">
              <Link
                href={`/?method=${method.id}`}
                className="block w-full px-4 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl text-center transition-all"
              >
                在计算器中使用
              </Link>
              <Link
                href={`/methods/${method.id}/edit`}
                className="block w-full px-4 py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl text-center transition-all"
              >
                编辑方法配置
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
