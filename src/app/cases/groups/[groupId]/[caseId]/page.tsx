"use client"

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter, useParams } from 'next/navigation'
import {
  ArrowLeft,
  FileText,
  FolderOpen,
  BookOpen,
  Calculator,
  Copy,
  Check
} from 'lucide-react'

type SubCase = {
  id: string
  title: string
  type: string
  tags: string[]
  data_raw: string
  description: string
  groupId: string
  related_paper_slug?: string
  parameters?: {
    beta?: number
    eta?: number
    gamma?: number
  }
}

export default function SubCasePage() {
  const params = useParams()
  const groupId = params.groupId as string
  const caseId = params.caseId as string
  const router = useRouter()

  const [subCase, setSubCase] = useState<SubCase | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    fetch(`/api/cases/groups/${groupId}/${caseId}`)
      .then(res => res.json())
      .then(data => {
        if (data.error) {
          console.error(data.error)
        } else {
          setSubCase(data)
        }
        setIsLoading(false)
      })
      .catch(err => {
        console.error(err)
        setIsLoading(false)
      })
  }, [groupId, caseId])

  const handleCopy = async () => {
    if (subCase?.data_raw) {
      await navigator.clipboard.writeText(subCase.data_raw)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  if (isLoading) {
    return (
      <main className="flex-1 bg-slate-50 min-h-screen">
        <div className="max-w-6xl mx-auto px-8 py-12">
          <div className="animate-pulse space-y-4">
            <div className="h-8 bg-slate-200 rounded w-1/3"></div>
            <div className="h-4 bg-slate-200 rounded w-1/2"></div>
          </div>
        </div>
      </main>
    )
  }

  if (!subCase) {
    return (
      <main className="flex-1 bg-slate-50 min-h-screen">
        <div className="max-w-6xl mx-auto px-8 py-12">
          <div className="text-center text-slate-400">
            <FileText size={48} className="mx-auto mb-4 opacity-20" />
            <p>子案例不存在</p>
            <Link href={`/cases/groups/${groupId}`} className="text-emerald-600 hover:underline mt-4 inline-block">
              返回案例组
            </Link>
          </div>
        </div>
      </main>
    )
  }

  const dataPoints = subCase.data_raw?.split('\n').filter(Boolean) ?? []

  return (
    <main className="flex-1 bg-slate-50 min-h-screen">
      <div className="max-w-6xl mx-auto px-8 py-8 space-y-6">

        {/* 头部导航 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href={`/cases/groups/${groupId}`}
              className="p-2 text-slate-400 hover:text-slate-600 hover:bg-white rounded-lg transition-colors"
            >
              <ArrowLeft size={20} />
            </Link>
            <div>
              <div className="flex items-center gap-2">
                <FileText size={20} className="text-blue-500" />
                <h1 className="text-2xl font-bold text-slate-800">{subCase.title}</h1>
              </div>
              <p className="text-sm text-slate-400 mt-1">
                1 组 · {dataPoints.length} 点/组 · {subCase.type}
              </p>
            </div>
          </div>

          {subCase.related_paper_slug && (
            <Link
              href={`/library/${subCase.related_paper_slug}`}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-600 bg-white hover:bg-slate-50 rounded-xl shadow-sm transition-colors"
            >
              <BookOpen size={16} />
              查看文献
            </Link>
          )}
        </div>

        {/* 元数据卡片 */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
          {/* 真实参数 */}
          {subCase.parameters && (
            <div>
              <span className="text-xs font-bold text-slate-400 uppercase">估计参数</span>
              <div className="flex items-center gap-6 mt-2">
                {subCase.parameters.beta !== undefined && (
                  <span className="text-base">
                    <span className="text-slate-400">β̂ = </span>
                    <span className="font-bold text-slate-700">{subCase.parameters.beta}</span>
                  </span>
                )}
                {subCase.parameters.eta !== undefined && (
                  <span className="text-base">
                    <span className="text-slate-400">η̂ = </span>
                    <span className="font-bold text-slate-700">{subCase.parameters.eta}</span>
                  </span>
                )}
                {subCase.parameters.gamma !== undefined && (
                  <span className="text-base">
                    <span className="text-slate-400">γ̂ = </span>
                    <span className="font-bold text-slate-700">{subCase.parameters.gamma}</span>
                  </span>
                )}
              </div>
            </div>
          )}

          {/* 描述 */}
          {subCase.description && (
            <div className="pt-4 border-t border-slate-100">
              <p className="text-sm text-slate-600 leading-relaxed">{subCase.description}</p>
            </div>
          )}
        </div>

        {/* 样本数据 */}
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
            <span className="font-bold text-slate-700">样本数据</span>
            <span className="text-sm text-slate-400">1 组</span>
          </div>

          <div className="divide-y divide-slate-50">
            <div className="px-6 py-4 flex items-center gap-6">
              {/* 序号 */}
              <div className="w-8 flex-shrink-0">
                <span className="text-base font-mono text-slate-400">1</span>
              </div>

              {/* 样本值 - 使用网格均匀排布 */}
              <div className="flex-1 grid grid-cols-5 sm:grid-cols-7 lg:grid-cols-10 gap-2">
                {dataPoints.map((val, i) => (
                  <span key={i} className="text-sm font-mono text-slate-600 bg-slate-50 px-2 py-1 rounded text-center">
                    {parseFloat(val).toFixed(1)}
                  </span>
                ))}
              </div>

              {/* 操作按钮 */}
              <div className="flex-shrink-0 flex items-center gap-2">
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-600 text-sm font-bold rounded-lg shadow-sm transition-colors"
                  title="复制数据"
                >
                  {copied ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
                  {copied ? '已复制' : '复制'}
                </button>
                <button
                  onClick={() => router.push(`/?caseData=${encodeURIComponent(subCase.data_raw)}`)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-600 text-sm font-bold rounded-lg shadow-sm transition-colors"
                >
                  <Calculator size={14} />
                  去计算
                </button>
              </div>
            </div>
          </div>
        </div>

      </div>
    </main>
  )
}
