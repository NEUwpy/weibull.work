"use client"

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { notFound } from 'next/navigation'
import { INITIAL_METHOD_TREE, MethodNode } from '@/lib/methods'
import { ArrowLeft, ExternalLink, Info, Sigma, BookOpen, Microscope, FileText } from 'lucide-react'
import { cn } from '@/lib/utils'
import { AlgorithmDetail } from '@/components/AlgorithmDetail'
import MethodLab from '@/components/MethodLab'
import AnalysisCard from '@/components/AnalysisCard'
import { DataPoint, WeibullResult } from '@/lib/weibull'
import 'katex/dist/katex.min.css'
import katex from 'katex'

// KaTeX Renderer
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

// Finder Helper
function findMethodById(methodId: string): { category: MethodNode; method?: MethodNode } | null {
  for (const category of INITIAL_METHOD_TREE) {
    if (category.id === methodId) return { category }
    if (category.children) {
      const method = category.children.find(m => m.id === methodId)
      if (method) return { category, method }
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

  if (!result) return notFound()

  const { category, method } = result

  if (!method) return <CategoryOverview category={category} />

  return <MethodDetail category={category} method={method} />
}

function CategoryOverview({ category }: { category: MethodNode }) {
  // ... (Keep existing implementation for category overview)
  return (
    <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12">
      <div className="mb-8">
        <Link href="/methods" className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-800 transition-colors font-bold mb-4">
          <ArrowLeft size={18} /> 返回方法总览
        </Link>
        <div className="flex items-center gap-3 mb-3">
          <span className="px-3 py-1 bg-amber-600 text-white text-xs font-bold rounded-full">{category.shortName}</span>
        </div>
        <h1 className="text-3xl font-black text-slate-900 mb-2">{category.name}</h1>
      </div>
      <div className="mb-8 bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Info className="text-amber-500" size={18} />
          <span className="font-bold text-slate-900">类别概述</span>
        </div>
        <p className="text-slate-600 leading-relaxed">{category.description}</p>
      </div>
      <div className="mb-8 p-6 bg-slate-900 rounded-2xl overflow-x-auto">
        <div className="flex items-center gap-2 mb-4">
          <Sigma className="text-amber-400" size={20} />
          <span className="text-sm font-bold text-slate-300 uppercase tracking-wider">核心公式</span>
        </div>
        <div className="text-white"><LatexRenderer math={category.formula} block /></div>
      </div>
      <div>
        <h2 className="text-xl font-bold text-slate-900 mb-4">该类别下的具体算法</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {category.children?.map((child) => (
            <Link key={child.id} href={`/methods/${child.id}`} className="p-5 bg-white rounded-2xl border border-slate-200 hover:border-amber-300 hover:shadow-md transition-all">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-mono text-amber-600 bg-amber-50 px-2 py-0.5 rounded border border-amber-100">{child.shortName}</span>
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

function MethodDetail({ category, method }: { category: MethodNode; method: MethodNode }) {
  const searchParams = useSearchParams()
  const [activeTab, setActiveTab] = useState<'doc' | 'lab'>('doc')
  const [analysisData, setAnalysisData] = useState<DataPoint[]>([])
  const [analysisResult, setAnalysisResult] = useState<WeibullResult | undefined>(undefined)
  
  // Auto-switch to lab if data is present and parse data
  useEffect(() => {
    const dataParam = searchParams.get('data')
    if (dataParam) {
      setActiveTab('lab')
      try {
        const parsed = dataParam.split(',').map(Number).filter(n => !isNaN(n))
        const points: DataPoint[] = parsed.map((v, i) => ({ id: i, value: v, status: 'F' }))
        setAnalysisData(points)
      } catch(e) {
        console.error("Failed to parse data", e)
      }
    }
  }, [searchParams])

  return (
    <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12">
      {/* Header */}
      <div className="mb-8">
        <Link href="/methods" className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-800 transition-colors font-bold mb-6">
          <ArrowLeft size={18} /> 返回方法总览
        </Link>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-black text-slate-900">{method.name}</h1>
            <span className="text-lg font-mono text-slate-400">{method.shortName.toUpperCase()}</span>
          </div>

          <div className="flex items-center gap-4">
             {/* Mode Toggle */}
             <div className="bg-slate-100 p-1 rounded-xl flex gap-1 border border-slate-200">
                <button 
                  onClick={() => setActiveTab('doc')}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all",
                    activeTab === 'doc' ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700"
                  )}
                >
                  <FileText size={16} />
                  原理文档
                </button>
                <button 
                  onClick={() => setActiveTab('lab')}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all",
                    activeTab === 'lab' ? "bg-white text-indigo-600 shadow-sm" : "text-slate-500 hover:text-slate-700"
                  )}
                >
                  <Microscope size={16} />
                  计算过程
                </button>
             </div>

             {/* Apply Link */}
             <Link
               href={`/?method=${method.id}`}
               className="inline-flex items-center gap-2 px-5 py-3 bg-blue-600 text-white hover:bg-blue-700 font-bold rounded-xl transition-all shadow-sm shadow-blue-200"
             >
               <Sigma size={18} />
               在计算器中应用
               <ExternalLink size={14} />
             </Link>
          </div>
        </div>
      </div>

      {/* Content Area */}
      <div className="min-h-[500px]">
        {activeTab === 'doc' ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
             {'slug' in method && method.hasDetail && method.slug ? (
               <AlgorithmDetail slug={method.slug} />
             ) : (
               <div className="p-12 text-center text-slate-400 bg-white rounded-3xl border border-slate-200">
                 暂无详细文档
               </div>
             )}
          </div>
        ) : (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8">
             {/* Analysis Card Preview */}
             {analysisData.length > 0 && (
                <div className="opacity-90 hover:opacity-100 transition-opacity">
                   <div className="text-xs font-bold text-slate-400 mb-2 uppercase tracking-wider ml-1">当前案例概览</div>
                   <AnalysisCard 
                     id="preview"
                     index={0}
                     data={analysisData}
                     result={analysisResult}
                     methodId={method.id}
                     color="#4f46e5" // Indigo-600
                     fitMode="fit"
                     is3P={analysisResult ? analysisResult.gamma !== 0 : false}
                     availableLayers={[]}
                     onAdd={() => {}} // Read-only
                     onDelete={() => {}} // Read-only
                     onDataChange={() => {}} // Read-only
                     onParamsUpdate={() => {}} // Read-only
                   />
                </div>
             )}
          
             {/* Pass data implicitly via URL search params handled inside MethodLab */}
             <MethodLab 
               methodId={method.id} 
               onCalculationComplete={(res) => setAnalysisResult(res)}
             />
          </div>
        )}
      </div>
    </section>
  )
}