"use client"

import React, { useState, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { ArrowLeft, Play, BarChart3, RefreshCw, TrendingUp } from 'lucide-react'
import { INITIAL_METHOD_TREE, MethodNode, getMethodInfo } from '@/lib/methods'
import { cn } from '@/lib/utils'
import ResultAnalysisLab from '@/components/ResultAnalysisLab'

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

interface MethodAnalysisPageProps {
  params: { methodId: string }
}

export default function MethodAnalysisPage({ params }: MethodAnalysisPageProps) {
  const { methodId } = params
  const searchParams = useSearchParams()
  const result = findMethodById(methodId)

  if (!result) return notFound()

  const { category, method } = result
  if (!method) return notFound()

  // Get true parameters from URL
  const trueBeta = parseFloat(searchParams.get('trueBeta') || '2')
  const trueEta = parseFloat(searchParams.get('trueEta') || '1000')
  const trueGamma = parseFloat(searchParams.get('trueGamma') || '1000')

  const methodInfo = getMethodInfo(methodId)

  return (
    <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12">
      {/* Header */}
      <div className="mb-8">
        <Link
          href={`/methods/${methodId}`}
          className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-800 transition-colors font-bold mb-6"
        >
          <ArrowLeft size={18} /> 返回方法详情
        </Link>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-black text-slate-900">{method.name}</h1>
            <span className="text-lg font-mono text-slate-400">{methodInfo.short.toUpperCase()}</span>
          </div>
        </div>
        <p className="text-slate-500 mt-2">参数估计结果分析 - 蒙特卡洛模拟评估准确性与波动性</p>
      </div>

      {/* True Parameters Display */}
      <div className="mb-6 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-2xl border border-blue-100 p-5">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp className="text-blue-600" size={18} />
          <span className="font-bold text-slate-900 text-sm uppercase tracking-wider">真实参数 (True Parameters)</span>
        </div>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className="text-xs font-black text-slate-500">β (形状)</span>
            <span className="text-lg font-mono font-bold text-blue-600">{trueBeta.toFixed(3)}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-black text-slate-500">η (尺度)</span>
            <span className="text-lg font-mono font-bold text-blue-600">{trueEta.toFixed(1)}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-black text-slate-500">γ (位置)</span>
            <span className="text-lg font-mono font-bold text-blue-600">{trueGamma.toFixed(1)}</span>
          </div>
        </div>
      </div>

      {/* Analysis Lab */}
      <ResultAnalysisLab
        methodId={methodId}
        trueBeta={trueBeta}
        trueEta={trueEta}
        trueGamma={trueGamma}
      />
    </section>
  )
}
