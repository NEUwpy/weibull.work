/**
 * 案例数据库页面
 *
 * ============================================================================
 * 案例数据统一格式规范
 * ============================================================================
 *
 * 【名称】格式：[id] 标题 [文献ID]
 *   - 示例：[c1] MDM方法验证样本 [182-030]
 *   - 示例：[g1] MDM方法验证样本组 [182-046]
 *   - 文献ID可选，无关联文献则省略
 *
 * 【类型】只有两种：
 *   - 抽样样本：Monte Carlo 等模拟生成的数据，有已知真实参数
 *   - 真实样本：实际工程/实验中的失效数据，无已知参数
 *
 * 【数据规模】格式：X点×Y组
 *   - 示例：15点×1组（单案例，15个数据点）
 *   - 示例：7点×30组（案例组，30个子案例，每个7点）
 *
 * 【描述】统一模板（描述数据本质来源）：
 *   - 抽样样本：W(β=2, η=1000, γ=1000)分布随机抽样，用于XX验证
 *   - 真实样本：XX设备/XX实验失效数据
 *
 * 【Tags】必选标签（3-4个）：
 *   - 方法：MDM / MLE / WMLE / 通用
 *   - 参数类型：三参数Weibull / 两参数Weibull
 *   - 样本量：大样本 / 小样本
 *   - 数据完整度（真实样本必选）：完全样本 / 截断样本
 *
 * ============================================================================
 */

"use client"

import React, { useState, useMemo, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  Database,
  Search,
  BookOpen,
  Calculator,
  FolderOpen,
  FileText,
  Dna,
  FlaskConical
} from 'lucide-react'
import { cn } from '@/lib/utils'

type CaseOrGroup = {
  id: string
  title: string
  type: string  // 抽样样本 | 真实样本
  tags: string[]
  data_raw?: string
  created_at: string
  description?: string
  related_paper_slug?: string
  related_paper?: string
  sample_count?: number
  true_params?: { beta?: number; eta?: number; gamma?: number }
  parameters?: { beta?: number; eta?: number; gamma?: number }
  isGroup: boolean
}

export default function CasesPage() {
  const router = useRouter()
  const [allItems, setAllItems] = useState<CaseOrGroup[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('全部')
  const [viewMode, setViewMode] = useState<'all' | 'groups' | 'cases'>('all')

  // Load data
  useEffect(() => {
    fetch('/api/cases/all')
      .then(res => res.json())
      .then(data => {
        setAllItems(data)
        setIsLoading(false)
      })
      .catch(err => {
        console.error(err)
        setIsLoading(false)
      })
  }, [])

  // 类型过滤选项
  const typeOptions = ['全部', '抽样样本', '真实样本']

  // Filter Logic
  const filteredItems = useMemo(() => {
    return allItems.filter(item => {
      if (viewMode === 'groups' && !item.isGroup) return false
      if (viewMode === 'cases' && item.isGroup) return false

      const matchesSearch = item.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                            (item.description || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
                            item.tags.some(t => t.toLowerCase().includes(searchTerm.toLowerCase()))
      const matchesType = typeFilter === '全部' || item.type === typeFilter

      return matchesSearch && matchesType
    })
  }, [allItems, searchTerm, typeFilter, viewMode])

  // 统计
  const stats = useMemo(() => {
    const groups = allItems.filter(i => i.isGroup)
    const cases = allItems.filter(i => !i.isGroup)
    return { groups: groups.length, cases: cases.length }
  }, [allItems])

  // 计算数据规模
  const getDataScale = (item: CaseOrGroup): { points: number; groups: number } => {
    if (item.isGroup) {
      const count = item.sample_count || 0
      const points = 7  // 案例组通常每组点数相同
      return { points, groups: count }
    } else {
      const points = item.data_raw?.split('\n').filter(Boolean).length ?? 0
      return { points, groups: 1 }
    }
  }

  // 获取文献ID
  const getPaperId = (item: CaseOrGroup): string | null => {
    return item.related_paper_slug || item.related_paper || null
  }

  // 获取方法标签
  const getMethodTag = (tags: string[]): string | null => {
    const methods = ['MDM', 'MLE', 'WMLE', '通用']
    return tags.find(t => methods.includes(t)) || null
  }

  // 获取参数类型标签
  const getParamTypeTag = (tags: string[]): string | null => {
    return tags.find(t => t.includes('参数Weibull')) || null
  }

  // 获取样本量标签
  const getSampleSizeTag = (tags: string[]): string | null => {
    return tags.find(t => t === '大样本' || t === '小样本') || null
  }

  // 获取数据完整度标签
  const getCompletenessTag = (tags: string[]): string | null => {
    return tags.find(t => t === '完全样本' || t === '截断样本') || null
  }

  const handleAnalyze = (item: CaseOrGroup) => {
    if (item.isGroup) {
      router.push(`/cases/groups/${item.id}`)
    } else if (item.data_raw) {
      router.push(`/?caseData=${encodeURIComponent(item.data_raw)}`)
    }
  }

  // 获取详情页链接
  const getDetailUrl = (item: CaseOrGroup): string => {
    if (item.isGroup) {
      return `/cases/groups/${item.id}`
    }
    return `/cases/${item.id}`
  }

  return (
    <main className="flex-1 bg-slate-50 min-h-screen">
      <div className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12 space-y-8">

        {/* 标题和统计 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">案例数据库</h1>
            <p className="text-sm text-slate-400 mt-1">
              共 {stats.groups} 个案例组，{stats.cases} 个单案例
            </p>
          </div>
        </div>

        {/* Toolbar */}
        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-wrap items-center gap-4">
          {/* Search */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              type="text"
              placeholder="搜索案例名称、描述或标签..."
              className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          {/* View Mode Toggle */}
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl">
            <button
              onClick={() => setViewMode('all')}
              className={cn(
                "px-3 py-1.5 text-xs font-bold rounded-lg transition-all",
                viewMode === 'all' ? "bg-white text-slate-700 shadow-sm" : "text-slate-500 hover:text-slate-700"
              )}
            >
              全部
            </button>
            <button
              onClick={() => setViewMode('groups')}
              className={cn(
                "px-3 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center gap-1",
                viewMode === 'groups' ? "bg-white text-slate-700 shadow-sm" : "text-slate-500 hover:text-slate-700"
              )}
            >
              <FolderOpen size={12} />
              案例组
            </button>
            <button
              onClick={() => setViewMode('cases')}
              className={cn(
                "px-3 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center gap-1",
                viewMode === 'cases' ? "bg-white text-slate-700 shadow-sm" : "text-slate-500 hover:text-slate-700"
              )}
            >
              <FileText size={12} />
              单案例
            </button>
          </div>

          {/* Type Filter */}
          <div className="flex items-center gap-2">
            <select
              className="bg-slate-50 border border-slate-200 text-slate-600 text-sm font-bold rounded-xl px-3 py-2 focus:outline-none focus:border-emerald-500"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
            >
              {typeOptions.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>

        {/* Data Grid / Table */}
        <div className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/50 border-b border-slate-100 text-xs font-black text-slate-400 uppercase tracking-wider">
                <th className="px-6 py-4">名称</th>
                <th className="px-6 py-4">类型</th>
                <th className="px-6 py-4">数据规模</th>
                <th className="px-6 py-4 w-1/3">描述</th>
                <th className="px-6 py-4">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {filteredItems.map((item) => {
                const paperId = getPaperId(item)
                const scale = getDataScale(item)
                const methodTag = getMethodTag(item.tags)
                const paramTypeTag = getParamTypeTag(item.tags)
                const sampleSizeTag = getSampleSizeTag(item.tags)
                const completenessTag = getCompletenessTag(item.tags)
                const detailUrl = getDetailUrl(item)

                return (
                  <tr
                    key={`${item.isGroup ? 'group' : 'case'}-${item.id}`}
                    onClick={() => router.push(detailUrl)}
                    className="hover:bg-slate-50/80 transition-colors cursor-pointer group"
                  >
                    {/* 名称列 */}
                    <td className="px-6 py-4" onClick={e => e.stopPropagation()}>
                      <div className="flex items-center gap-2.5">
                        {item.isGroup ? (
                          <FolderOpen size={16} className="text-emerald-500 flex-shrink-0" />
                        ) : (
                          <FileText size={16} className="text-blue-500 flex-shrink-0" />
                        )}
                        <div className="flex items-center gap-2 flex-wrap">
                          {/* ID 徽章 */}
                          <span className="inline-flex items-center px-2 py-1 bg-violet-100 border border-violet-200 rounded text-xs font-bold text-violet-600">
                            [{item.id}]
                          </span>
                          {/* 标题 */}
                          <span className="font-bold text-slate-800 text-sm">
                            {item.title}
                          </span>
                          {/* 文献ID - 如果存在 */}
                          {paperId && (
                            <Link
                              href={`/library/${paperId}`}
                              onClick={e => e.stopPropagation()}
                              className="inline-flex items-center gap-1 px-2 py-1 bg-amber-50 border border-amber-200 rounded text-xs font-medium text-amber-600 hover:bg-amber-100 transition-colors"
                            >
                              <BookOpen size={12} />
                              [{paperId}]
                            </Link>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* 类型列 */}
                    <td className="px-6 py-4">
                      <span className={cn(
                        "inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-bold border",
                        item.type === '抽样样本'
                          ? "bg-purple-50 text-purple-600 border-purple-200"
                          : "bg-amber-50 text-amber-600 border-amber-200"
                      )}>
                        {item.type === '抽样样本' ? (
                          <Dna size={12} className="text-purple-400" />
                        ) : (
                          <FlaskConical size={12} className="text-amber-400" />
                        )}
                        {item.type}
                      </span>
                    </td>

                    {/* 数据规模列 */}
                    <td className="px-6 py-4">
                      <div className="inline-flex items-center gap-1.5 px-2 py-1 bg-sky-50 border border-sky-200 rounded text-xs font-bold text-sky-600">
                        {scale.points}点×{scale.groups}组
                      </div>
                    </td>

                    {/* 描述列 */}
                    <td className="px-6 py-4">
                      <div className="space-y-2">
                        <p className="text-sm text-slate-500 leading-relaxed">
                          {item.description || '暂无描述'}
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {methodTag && (
                            <span className="text-[10px] font-medium text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded">
                              #{methodTag}
                            </span>
                          )}
                          {paramTypeTag && (
                            <span className="text-[10px] font-medium text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded">
                              #{paramTypeTag}
                            </span>
                          )}
                          {sampleSizeTag && (
                            <span className="text-[10px] font-medium text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded">
                              #{sampleSizeTag}
                            </span>
                          )}
                          {completenessTag && (
                            <span className="text-[10px] font-medium text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded">
                              #{completenessTag}
                            </span>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* 操作列 */}
                    <td className="px-6 py-4" onClick={e => e.stopPropagation()}>
                      <button
                        onClick={() => handleAnalyze(item)}
                        className="flex items-center gap-2 px-4 py-2 bg-white hover:bg-slate-50 text-slate-600 text-sm font-bold rounded-xl transition-all active:scale-95 shadow-sm"
                      >
                        <Calculator size={16} />
                        去计算
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          {filteredItems.length === 0 && (
            <div className="p-12 text-center text-slate-400">
              <Database size={48} className="mx-auto mb-4 opacity-20" />
              <p>未找到匹配的案例。</p>
            </div>
          )}
        </div>

      </div>
    </main>
  )
}
