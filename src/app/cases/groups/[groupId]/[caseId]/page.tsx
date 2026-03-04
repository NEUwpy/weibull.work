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
  Check,
  Tag
} from 'lucide-react'
import { cn } from '@/lib/utils'

type SubCase = {
  id: string
  title: string
  industry: string
  type: string
  size: string
  tags: string[]
  data_raw: string
  content: string
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

  const handleCopyData = () => {
    if (subCase?.data_raw) {
      navigator.clipboard.writeText(subCase.data_raw)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleAnalyze = () => {
    if (subCase?.data_raw) {
      router.push(`/?caseData=${encodeURIComponent(subCase.data_raw)}`)
    }
  }

  if (isLoading) {
    return (
      <main className="flex-1 bg-slate-50 min-h-screen">
        <div className="max-w-4xl mx-auto px-8 py-12">
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
        <div className="max-w-4xl mx-auto px-8 py-12">
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

  const dataPoints = subCase.data_raw?.split('\n').filter(Boolean).length || 0

  return (
    <main className="flex-1 bg-slate-50 min-h-screen">
      <div className="max-w-4xl mx-auto px-8 py-8 space-y-6">

        {/* 面包屑导航 */}
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Link href="/cases" className="hover:text-slate-600 transition-colors">案例库</Link>
          <span>/</span>
          <Link href={`/cases/groups/${groupId}`} className="hover:text-slate-600 transition-colors flex items-center gap-1">
            <FolderOpen size={14} />
            {groupId}
          </Link>
          <span>/</span>
          <span className="text-slate-600 font-medium">{subCase.id}</span>
        </div>

        {/* 头部 */}
        <div className="flex items-start justify-between">
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
                {subCase.type} · {subCase.size} · {dataPoints} 个数据点
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {subCase.related_paper_slug && (
              <Link
                href={`/library/${subCase.related_paper_slug}`}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-xl transition-colors"
              >
                <BookOpen size={16} />
                查看文献
              </Link>
            )}
            <button
              onClick={handleAnalyze}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold rounded-xl shadow-sm shadow-emerald-200 transition-all"
            >
              <Calculator size={16} />
              去计算
            </button>
          </div>
        </div>

        {/* 元数据卡片 */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <span className="text-xs font-bold text-slate-400 uppercase">ID</span>
              <p className="text-sm font-mono text-slate-600 mt-1">{subCase.id}</p>
            </div>
            <div>
              <span className="text-xs font-bold text-slate-400 uppercase">类型</span>
              <p className="text-sm text-slate-600 mt-1">{subCase.type}</p>
            </div>
            <div>
              <span className="text-xs font-bold text-slate-400 uppercase">规模</span>
              <span className={cn(
                "inline-block px-2 py-0.5 rounded text-xs font-bold mt-1",
                subCase.size === '小样本' ? "bg-orange-50 text-orange-600" :
                subCase.size === '大样本' ? "bg-emerald-50 text-emerald-600" :
                "bg-slate-100 text-slate-500"
              )}>
                {subCase.size}
              </span>
            </div>
            <div>
              <span className="text-xs font-bold text-slate-400 uppercase">数据点</span>
              <p className="text-sm font-bold text-slate-600 mt-1">{dataPoints} 个</p>
            </div>
          </div>

          {/* 参数（如果有） */}
          {subCase.parameters && (
            <div className="pt-4 mt-4 border-t border-slate-100">
              <span className="text-xs font-bold text-slate-400 uppercase">参数</span>
              <div className="flex items-center gap-6 mt-2">
                {subCase.parameters.beta && (
                  <span className="text-sm">
                    <span className="text-slate-400">β = </span>
                    <span className="font-bold text-slate-700">{subCase.parameters.beta}</span>
                  </span>
                )}
                {subCase.parameters.eta && (
                  <span className="text-sm">
                    <span className="text-slate-400">η = </span>
                    <span className="font-bold text-slate-700">{subCase.parameters.eta}</span>
                  </span>
                )}
                {subCase.parameters.gamma && (
                  <span className="text-sm">
                    <span className="text-slate-400">γ = </span>
                    <span className="font-bold text-slate-700">{subCase.parameters.gamma}</span>
                  </span>
                )}
              </div>
            </div>
          )}

          {/* 标签 */}
          {subCase.tags.length > 0 && (
            <div className="flex flex-wrap gap-2 pt-4 mt-4 border-t border-slate-100">
              <Tag size={14} className="text-slate-400" />
              {subCase.tags.map(tag => (
                <span key={tag} className="text-xs font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded-lg">
                  #{tag}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* 案例描述 */}
        {subCase.content && (
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <h2 className="text-sm font-bold text-slate-400 uppercase mb-4">案例描述</h2>
            <div className="prose prose-sm prose-slate max-w-none">
              {subCase.content.split('\n').map((paragraph, idx) => (
                <p key={idx} className="text-slate-600 leading-relaxed mb-3">
                  {paragraph}
                </p>
              ))}
            </div>
          </div>
        )}

        {/* 原始数据 */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-400 uppercase">原始数据</h2>
            <button
              onClick={handleCopyData}
              className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
            >
              {copied ? (
                <>
                  <Check size={14} className="text-emerald-500" />
                  已复制
                </>
              ) : (
                <>
                  <Copy size={14} />
                  复制数据
                </>
              )}
            </button>
          </div>
          <div className="bg-slate-50 rounded-xl p-4 font-mono text-sm text-slate-600 max-h-64 overflow-y-auto">
            {subCase.data_raw ? (
              subCase.data_raw.split('\n').filter(Boolean).map((line, idx) => (
                <div key={idx} className="py-0.5 hover:bg-slate-100 px-2 -mx-2 rounded">
                  {line}
                </div>
              ))
            ) : (
              <span className="text-slate-400">无数据</span>
            )}
          </div>
        </div>

      </div>
    </main>
  )
}
