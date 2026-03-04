"use client"

import React, { useState, useMemo, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  Database,
  Search,
  Filter,
  BookOpen,
  Calculator,
  FolderOpen,
  FileText,
  Layers
} from 'lucide-react'
import { cn } from '@/lib/utils'

type CaseOrGroup = {
  id: string
  title: string
  industry: string
  type: string
  size?: string
  tags: string[]
  data_raw?: string
  created_at: string
  description?: string
  content?: string
  related_paper_slug?: string
  related_paper?: string
  sample_count?: number
  isGroup: boolean
}

export default function CasesPage() {
  const router = useRouter()
  const [allItems, setAllItems] = useState<CaseOrGroup[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [industryFilter, setIndustryFilter] = useState<string>('全部行业')
  const [typeFilter, setTypeFilter] = useState<string>('全部类型')
  const [viewMode, setViewMode] = useState<'all' | 'groups' | 'cases'>('all')

  // Load data
  useEffect(() => {
    fetch('/api/cases/all')
      .then(res => res.json())
      .then(data => {
        const mappedData = data.map((item: any) => {
          let desc = item.description || item.content || ''
          desc = desc.replace(/^#+\s+/gm, '')
                     .replace(/\*\*/g, '')
                     .replace(/\n/g, ' ')
                     .trim()

          if (desc.length > 100) {
            desc = desc.slice(0, 100) + '...'
          }

          return {
            ...item,
            description: desc
          }
        })
        setAllItems(mappedData)
        setIsLoading(false)
      })
      .catch(err => {
        console.error(err)
        setIsLoading(false)
      })
  }, [])

  // Derived filters
  const industries = useMemo(() =>
    ['全部行业', ...Array.from(new Set(allItems.map(c => c.industry)))],
    [allItems]
  )
  const types = useMemo(() =>
    ['全部类型', ...Array.from(new Set(allItems.map(c => c.type)))],
    [allItems]
  )

  // Filter Logic
  const filteredItems = useMemo(() => {
    return allItems.filter(item => {
      // 视图模式过滤
      if (viewMode === 'groups' && !item.isGroup) return false
      if (viewMode === 'cases' && item.isGroup) return false

      const matchesSearch = item.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                            (item.description || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
                            item.tags.some(t => t.toLowerCase().includes(searchTerm.toLowerCase()))
      const matchesIndustry = industryFilter === '全部行业' || item.industry === industryFilter
      const matchesType = typeFilter === '全部类型' || item.type === typeFilter

      return matchesSearch && matchesIndustry && matchesType
    })
  }, [allItems, searchTerm, industryFilter, typeFilter, viewMode])

  // 统计
  const stats = useMemo(() => {
    const groups = allItems.filter(i => i.isGroup)
    const cases = allItems.filter(i => !i.isGroup)
    return { groups: groups.length, cases: cases.length }
  }, [allItems])

  const handleAnalyze = (item: CaseOrGroup) => {
    if (item.isGroup) {
      router.push(`/cases/groups/${item.id}`)
    } else if (item.data_raw) {
      router.push(`/?caseData=${encodeURIComponent(item.data_raw)}`)
    }
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

          {/* Filters */}
          <div className="flex items-center gap-2">
            <Filter size={16} className="text-slate-400" />
            <select
              className="bg-slate-50 border border-slate-200 text-slate-600 text-sm font-bold rounded-xl px-3 py-2 focus:outline-none focus:border-emerald-500"
              value={industryFilter}
              onChange={(e) => setIndustryFilter(e.target.value)}
            >
              {industries.map(i => <option key={i} value={i}>{i}</option>)}
            </select>
            <select
              className="bg-slate-50 border border-slate-200 text-slate-600 text-sm font-bold rounded-xl px-3 py-2 focus:outline-none focus:border-emerald-500"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
            >
              {types.map(t => <option key={t} value={t}>{t}</option>)}
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
                <th className="px-6 py-4 text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {filteredItems.map((item) => (
                <tr key={`${item.isGroup ? 'group' : 'case'}-${item.id}`} className="hover:bg-slate-50/80 transition-colors group">
                  <td className="px-6 py-4">
                    <div className="flex flex-col">
                      <div className="flex items-center gap-2">
                        {item.isGroup ? (
                          <FolderOpen size={18} className="text-emerald-500" />
                        ) : (
                          <FileText size={18} className="text-blue-500" />
                        )}
                        {item.isGroup ? (
                          <Link
                            href={`/cases/groups/${item.id}`}
                            className="font-bold text-slate-800 text-base hover:text-emerald-600 transition-colors"
                          >
                            {item.title}
                          </Link>
                        ) : (
                          <span className="font-bold text-slate-800 text-base">{item.title}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-1 ml-6">
                        <span className="text-[10px] font-mono text-slate-400 bg-slate-100 px-1.5 rounded">{item.id}</span>
                        {item.isGroup && item.sample_count && (
                          <span className="text-[10px] font-bold text-emerald-500 bg-emerald-50 px-1.5 rounded flex items-center gap-1">
                            <Layers size={10} /> {item.sample_count} 子案例
                          </span>
                        )}
                        {!item.isGroup && (item.related_paper_slug || item.related_paper) && (
                          <span className="text-[10px] font-bold text-blue-500 bg-blue-50 px-1.5 rounded flex items-center gap-1">
                            <BookOpen size={10} /> 文献可查
                          </span>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-col gap-1">
                      <span className="text-sm font-bold text-slate-600">{item.industry}</span>
                      <span className="text-xs text-slate-400">{item.type}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    {item.isGroup ? (
                      <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-600">
                        {item.sample_count || 0} 组
                      </span>
                    ) : (
                      <>
                        <span className={cn(
                          "px-2.5 py-1 rounded-full text-xs font-bold",
                          item.size === '小样本' ? "bg-orange-50 text-orange-600" :
                          item.size === '大样本' ? "bg-emerald-50 text-emerald-600" : "bg-slate-100 text-slate-500"
                        )}>
                          {item.size || '未知'}
                        </span>
                        <div className="text-[10px] text-slate-400 mt-1 pl-1">
                          {item.data_raw?.split('\n').filter(Boolean).length ?? 0} Points
                        </div>
                      </>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <p className="text-sm text-slate-500 leading-relaxed line-clamp-2">{item.description}</p>
                    <div className="flex gap-1 mt-2">
                      {item.tags.slice(0, 4).map(tag => (
                        <span key={tag} className="text-[10px] font-bold text-slate-400 bg-white border border-slate-200 px-1.5 rounded">#{tag}</span>
                      ))}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      {item.isGroup ? (
                        <>
                          <Link
                            href={`/cases/groups/${item.id}`}
                            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold rounded-xl shadow-sm shadow-emerald-200 transition-all"
                          >
                            <FolderOpen size={16} />
                            查看详情
                          </Link>
                        </>
                      ) : (
                        <>
                          {(item.related_paper_slug || item.related_paper) && (
                            <Link
                              href={`/library/${item.related_paper_slug || item.related_paper}`}
                              className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                              title="查看关联文献"
                            >
                              <BookOpen size={18} />
                            </Link>
                          )}
                          <button
                            onClick={() => handleAnalyze(item)}
                            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold rounded-xl shadow-sm shadow-emerald-200 transition-all active:scale-95"
                          >
                            <Calculator size={16} />
                            去计算
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
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
