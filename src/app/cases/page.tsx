"use client"

import React, { useState, useMemo } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { 
  Database, 
  Search, 
  Filter, 
  ArrowRight, 
  BookOpen, 
  Calculator, 
  Tag, 
  Calendar 
} from 'lucide-react'
import { CASE_LIBRARY, CaseItem } from '@/lib/cases'
import { cn } from '@/lib/utils'

export default function CasesPage() {
  const router = useRouter()
  const [searchTerm, setSearchTerm] = useState('')
  const [industryFilter, setIndustryFilter] = useState<string>('全部行业')
  const [typeFilter, setTypeFilter] = useState<string>('全部类型')

  // Derived filters
  const industries = ['全部行业', ...Array.from(new Set(CASE_LIBRARY.map(c => c.industry)))]
  const types = ['全部类型', ...Array.from(new Set(CASE_LIBRARY.map(c => c.type)))]

  // Filter Logic
  const filteredCases = useMemo(() => {
    return CASE_LIBRARY.filter(item => {
      const matchesSearch = item.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                            (item.description || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
                            item.tags.some(t => t.toLowerCase().includes(searchTerm.toLowerCase()))
      const matchesIndustry = industryFilter === '全部行业' || item.industry === industryFilter
      const matchesType = typeFilter === '全部类型' || item.type === typeFilter
      
      return matchesSearch && matchesIndustry && matchesType
    })
  }, [searchTerm, industryFilter, typeFilter])

  // Handle "Analyze" - Send data to calculator via URL or LocalStorage
  // For simplicity in this static demo, we will just navigate to Home. 
  // In a real app, we'd use a Context or URL params to pass data.
  // Here we simulate it by copying to clipboard or just redirecting.
  const handleAnalyze = (item: CaseItem) => {
    router.push(`/?caseId=${item.id}`)
  }

  return (
    <main className="flex-1 bg-slate-50 min-h-screen">
      <div className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12 space-y-8">
        
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
                <th className="px-6 py-4">案例名称</th>
                <th className="px-6 py-4">行业 / 类型</th>
                <th className="px-6 py-4">数据规模</th>
                <th className="px-6 py-4 w-1/3">描述</th>
                <th className="px-6 py-4 text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {filteredCases.map((item) => (
                <tr key={item.id} className="hover:bg-slate-50/80 transition-colors group">
                  <td className="px-6 py-4">
                    <div className="flex flex-col">
                      <span className="font-bold text-slate-800 text-base">{item.name}</span>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-[10px] font-mono text-slate-400 bg-slate-100 px-1.5 rounded">{item.id}</span>
                        {item.related_paper_slug && (
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
                    <span className={cn(
                      "px-2.5 py-1 rounded-full text-xs font-bold",
                      item.size === '小样本' ? "bg-orange-50 text-orange-600" : 
                      item.size === '大样本' ? "bg-emerald-50 text-emerald-600" : "bg-slate-100 text-slate-500"
                    )}>
                      {item.size}
                    </span>
                    <div className="text-[10px] text-slate-400 mt-1 pl-1">
                       {item.dataRaw.split('\n').length} Points
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <p className="text-sm text-slate-500 leading-relaxed line-clamp-2">{item.description}</p>
                    <div className="flex gap-1 mt-2">
                      {item.tags.map(tag => (
                        <span key={tag} className="text-[10px] font-bold text-slate-400 bg-white border border-slate-200 px-1.5 rounded">#{tag}</span>
                      ))}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                       {item.related_paper_slug && (
                         <Link 
                           href={`/library/${item.related_paper_slug}`}
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
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          
          {filteredCases.length === 0 && (
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
