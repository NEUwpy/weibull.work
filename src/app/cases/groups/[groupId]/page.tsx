"use client"

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter, useParams } from 'next/navigation'
import {
  ArrowLeft,
  FolderOpen,
  FileText,
  BookOpen,
  Calculator,
  Copy,
  Check,
  Database
} from 'lucide-react'

type SubCase = {
  id: string
  title: string
  type: string
  tags: string[]
  data_raw: string
  description: string
  groupId: string
  parameters?: {
    beta?: number
    eta?: number
    gamma?: number
  }
}

type CaseGroup = {
  id: string
  title: string
  type: string
  description: string
  related_paper?: string
  sample_count: number
  true_params?: {
    beta?: number
    eta?: number
    gamma?: number
  }
  created_at: string
  tags: string[]
  subCases: SubCase[]
}

export default function CaseGroupPage() {
  const params = useParams()
  const groupId = params.groupId as string
  const router = useRouter()

  const [group, setGroup] = useState<CaseGroup | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  useEffect(() => {
    fetch(`/api/cases/groups/${groupId}`)
      .then(res => res.json())
      .then(data => {
        if (data.error) {
          console.error(data.error)
        } else {
          setGroup(data)
        }
        setIsLoading(false)
      })
      .catch(err => {
        console.error(err)
        setIsLoading(false)
      })
  }, [groupId])

  const handleCopy = async (data_raw: string, id: string) => {
    await navigator.clipboard.writeText(data_raw)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
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

  if (!group) {
    return (
      <main className="flex-1 bg-slate-50 min-h-screen">
        <div className="max-w-6xl mx-auto px-8 py-12">
          <div className="text-center text-slate-400">
            <FolderOpen size={48} className="mx-auto mb-4 opacity-20" />
            <p>案例组不存在</p>
            <Link href="/cases" className="text-emerald-600 hover:underline mt-4 inline-block">
              返回案例列表
            </Link>
          </div>
        </div>
      </main>
    )
  }

  // 获取每组点数（从第一个子案例推断）
  const pointsPerGroup = group.subCases[0]?.data_raw?.split('\n').filter(Boolean).length ?? 0

  return (
    <main className="flex-1 bg-slate-50 min-h-screen">
      <div className="max-w-6xl mx-auto px-8 py-8 space-y-6">

        {/* 头部导航 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/cases"
              className="p-2 text-slate-400 hover:text-slate-600 hover:bg-white rounded-lg transition-colors"
            >
              <ArrowLeft size={20} />
            </Link>
            <div>
              <div className="flex items-center gap-2">
                <FolderOpen size={20} className="text-emerald-500" />
                <h1 className="text-2xl font-bold text-slate-800">{group.title}</h1>
              </div>
              <p className="text-sm text-slate-400 mt-1">
                {group.subCases.length} 组 · {pointsPerGroup}点/组 · {group.type}
              </p>
            </div>
          </div>

          {group.related_paper && (
            <Link
              href={`/library/${group.related_paper}`}
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
          {group.true_params && (
            <div>
              <span className="text-xs font-bold text-slate-400 uppercase">真实参数</span>
              <div className="flex items-center gap-6 mt-2">
                {group.true_params.beta !== undefined && (
                  <span className="text-base">
                    <span className="text-slate-400">β = </span>
                    <span className="font-bold text-slate-700">{group.true_params.beta}</span>
                  </span>
                )}
                {group.true_params.eta !== undefined && (
                  <span className="text-base">
                    <span className="text-slate-400">η = </span>
                    <span className="font-bold text-slate-700">{group.true_params.eta}</span>
                  </span>
                )}
                {group.true_params.gamma !== undefined && (
                  <span className="text-base">
                    <span className="text-slate-400">γ = </span>
                    <span className="font-bold text-slate-700">{group.true_params.gamma}</span>
                  </span>
                )}
              </div>
            </div>
          )}

          {/* 描述 */}
          {group.description && (
            <div className="pt-4 border-t border-slate-100">
              <p className="text-sm text-slate-600 leading-relaxed">{group.description}</p>
            </div>
          )}
        </div>

        {/* 子案例列表 */}
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
            <span className="font-bold text-slate-700">样本数据</span>
            <span className="text-sm text-slate-400">{group.subCases.length} 组</span>
          </div>

          {group.subCases.length === 0 ? (
            <div className="p-12 text-center text-slate-400">
              <Database size={48} className="mx-auto mb-4 opacity-20" />
              <p>暂无子案例</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-50">
              {group.subCases.map((subCase, index) => {
                const values = subCase.data_raw?.split('\n').filter(Boolean) ?? []

                return (
                  <div
                    key={subCase.id}
                    onClick={() => router.push(`/cases/groups/${groupId}/${subCase.id}`)}
                    className="px-6 py-4 hover:bg-slate-50/80 transition-colors cursor-pointer group flex items-center gap-6"
                  >
                    {/* 序号 */}
                    <div className="w-8 flex-shrink-0">
                      <span className="text-base font-mono text-slate-400">{index + 1}</span>
                    </div>

                    {/* 样本值 - 使用网格均匀排布 */}
                    <div className="flex-1 grid grid-cols-7 gap-2">
                      {values.map((val, i) => (
                        <span key={i} className="text-sm font-mono text-slate-600 bg-slate-50 px-2 py-1 rounded text-center">
                          {parseFloat(val).toFixed(1)}
                        </span>
                      ))}
                    </div>

                    {/* 操作按钮 */}
                    <div className="flex-shrink-0 flex items-center gap-2" onClick={e => e.stopPropagation()}>
                      <button
                        onClick={() => handleCopy(subCase.data_raw, subCase.id)}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-600 text-sm font-bold rounded-lg shadow-sm transition-colors"
                        title="复制数据"
                      >
                        {copiedId === subCase.id ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
                        {copiedId === subCase.id ? '已复制' : '复制'}
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
                )
              })}
            </div>
          )}
        </div>

      </div>
    </main>
  )
}
