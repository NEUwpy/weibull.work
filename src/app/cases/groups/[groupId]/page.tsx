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
  BarChart3,
  Tag,
  Layers,
  Database
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
  parameters?: {
    beta?: number
    eta?: number
    gamma?: number
  }
}

type CaseGroup = {
  id: string
  title: string
  industry: string
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
                {group.subCases.length} 个子案例 · {group.industry}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {group.related_paper && (
              <Link
                href={`/library/${group.related_paper}`}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-xl transition-colors"
              >
                <BookOpen size={16} />
                查看文献
              </Link>
            )}
          </div>
        </div>

        {/* 元数据卡片 */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <span className="text-xs font-bold text-slate-400 uppercase">ID</span>
              <p className="text-sm font-mono text-slate-600 mt-1">{group.id}</p>
            </div>
            <div>
              <span className="text-xs font-bold text-slate-400 uppercase">案例数量</span>
              <p className="text-sm font-bold text-slate-600 mt-1">{group.sample_count} 组</p>
            </div>
            <div>
              <span className="text-xs font-bold text-slate-400 uppercase">行业</span>
              <p className="text-sm text-slate-600 mt-1">{group.industry}</p>
            </div>
            <div>
              <span className="text-xs font-bold text-slate-400 uppercase">关联文献</span>
              <p className="text-sm text-slate-600 mt-1">{group.related_paper || '-'}</p>
            </div>
          </div>

          {/* 真实参数 */}
          {group.true_params && (
            <div className="pt-4 border-t border-slate-100">
              <span className="text-xs font-bold text-slate-400 uppercase">真实参数</span>
              <div className="flex items-center gap-6 mt-2">
                {group.true_params.beta && (
                  <span className="text-sm">
                    <span className="text-slate-400">β = </span>
                    <span className="font-bold text-slate-700">{group.true_params.beta}</span>
                  </span>
                )}
                {group.true_params.eta && (
                  <span className="text-sm">
                    <span className="text-slate-400">η = </span>
                    <span className="font-bold text-slate-700">{group.true_params.eta}</span>
                  </span>
                )}
                {group.true_params.gamma && (
                  <span className="text-sm">
                    <span className="text-slate-400">γ = </span>
                    <span className="font-bold text-slate-700">{group.true_params.gamma}</span>
                  </span>
                )}
              </div>
            </div>
          )}

          {/* 标签 */}
          {group.tags.length > 0 && (
            <div className="flex flex-wrap gap-2 pt-4 border-t border-slate-100">
              {group.tags.map(tag => (
                <span key={tag} className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-1 rounded-lg">
                  #{tag}
                </span>
              ))}
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
            <div className="flex items-center gap-2">
              <Layers size={18} className="text-slate-400" />
              <span className="font-bold text-slate-700">子案例列表</span>
            </div>
            <span className="text-sm text-slate-400">{group.subCases.length} 个</span>
          </div>

          {group.subCases.length === 0 ? (
            <div className="p-12 text-center text-slate-400">
              <Database size={48} className="mx-auto mb-4 opacity-20" />
              <p>暂无子案例</p>
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50/50 border-b border-slate-100 text-xs font-black text-slate-400 uppercase tracking-wider">
                  <th className="px-6 py-3">#</th>
                  <th className="px-6 py-3">案例名称</th>
                  <th className="px-6 py-3">类型</th>
                  <th className="px-6 py-3">数据量</th>
                  <th className="px-6 py-3">标签</th>
                  <th className="px-6 py-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {group.subCases.map((subCase, index) => (
                  <tr key={subCase.id} className="hover:bg-slate-50/80 transition-colors group">
                    <td className="px-6 py-4">
                      <span className="text-sm font-mono text-slate-400">{index + 1}</span>
                    </td>
                    <td className="px-6 py-4">
                      <Link
                        href={`/cases/groups/${groupId}/${subCase.id}`}
                        className="font-bold text-slate-800 hover:text-emerald-600 transition-colors"
                      >
                        {subCase.title}
                      </Link>
                      <span className="text-xs text-slate-400 ml-2">({subCase.id})</span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm text-slate-600">{subCase.type}</span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={cn(
                        "px-2 py-0.5 rounded text-xs font-bold",
                        subCase.size === '小样本' ? "bg-orange-50 text-orange-600" :
                        subCase.size === '大样本' ? "bg-emerald-50 text-emerald-600" :
                        "bg-slate-100 text-slate-500"
                      )}>
                        {subCase.size}
                      </span>
                      <span className="text-xs text-slate-400 ml-2">
                        {subCase.data_raw?.split('\n').filter(Boolean).length || 0} 点
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1">
                        {subCase.tags.slice(0, 3).map(tag => (
                          <span key={tag} className="text-[10px] font-bold text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                            #{tag}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Link
                          href={`/cases/groups/${groupId}/${subCase.id}`}
                          className="p-2 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
                          title="查看详情"
                        >
                          <FileText size={16} />
                        </Link>
                        <button
                          onClick={() => router.push(`/?caseData=${encodeURIComponent(subCase.data_raw)}`)}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg transition-colors"
                        >
                          <Calculator size={14} />
                          计算
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

      </div>
    </main>
  )
}
