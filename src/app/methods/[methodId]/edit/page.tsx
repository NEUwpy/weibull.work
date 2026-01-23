"use client"

import React, { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { INITIAL_METHOD_TREE, MethodNode } from '@/lib/methods'
import { ArrowLeft, Save, Code, BookOpen } from 'lucide-react'
import 'katex/dist/katex.min.css'
import katex from 'katex'

// LaTeX Preview Component
const LatexPreview = ({ math }: { math: string }) => {
  try {
    const html = katex.renderToString(math, {
      throwOnError: false,
      displayMode: true
    })
    return <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg my-2" dangerouslySetInnerHTML={{ __html: html }} />
  } catch (e) {
    return <div className="text-red-500 text-sm">LaTeX Syntax Error</div>
  }
}

export default function MethodEditPage() {
  const params = useParams()
  const router = useRouter()
  const methodId = params.methodId as string

  const [method, setMethod] = useState<MethodNode | null>(null)
  const [loading, setLoading] = useState(true)

  // Load method data (Mocking a fetch)
  useEffect(() => {
    // Flatten tree to find the method
    const allMethods = INITIAL_METHOD_TREE.flatMap(cat => cat.children || [])
    const found = allMethods.find(m => m.id === methodId)
    
    if (found) {
      setMethod({ ...found }) // Clone for editing
    } else if (methodId.startsWith('custom_')) {
      // New custom method
      setMethod({
        id: methodId,
        name: '自定义算法',
        shortName: 'New',
        description: '',
        formula: 'f(x) = ...'
      })
    }
    setLoading(false)
  }, [methodId])

  const handleSave = () => {
    // In a real app, this would make an API call or update a global store.
    // For now, we simulate saving.
    alert('保存成功！(原型演示：此处仅为 UI 交互，刷新后将重置)')
    router.back()
  }

  if (loading) return <div className="p-10 text-slate-400">Loading...</div>
  if (!method) return <div className="p-10 text-red-500">Method not found</div>

  return (
    <div className="min-h-screen bg-slate-50 p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <button 
            onClick={() => router.back()}
            className="flex items-center gap-2 text-slate-500 hover:text-slate-800 transition-colors font-bold"
          >
            <ArrowLeft size={20} />
            返回
          </button>
          <h1 className="text-2xl font-black text-slate-900">算法配置编辑器</h1>
        </div>

        <div className="bg-white rounded-3xl shadow-xl shadow-slate-200/60 overflow-hidden border border-slate-100">
          <div className="p-8 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-blue-200">
                 <Code size={24} />
              </div>
              <div>
                <h2 className="text-xl font-bold text-slate-800">{method.name}</h2>
                <span className="font-mono text-sm text-blue-500 bg-blue-50 px-2 py-0.5 rounded border border-blue-100">{method.id}</span>
              </div>
            </div>
            
            <button
              onClick={handleSave}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl shadow-lg shadow-blue-200 transition-all flex items-center gap-2 hover:scale-105 active:scale-95"
            >
              <Save size={18} />
              保存配置
            </button>
          </div>

          <div className="p-8 space-y-8">
            {/* Basic Info */}
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-black text-slate-400 uppercase tracking-wider">算法全称 (Name)</label>
                <input 
                  type="text" 
                  value={method.name}
                  onChange={e => setMethod({ ...method, name: e.target.value })}
                  className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none font-bold text-slate-700 transition-all"
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-black text-slate-400 uppercase tracking-wider">缩写 (Short Name)</label>
                <input 
                  type="text" 
                  value={method.shortName}
                  onChange={e => setMethod({ ...method, shortName: e.target.value })}
                  className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none font-mono font-bold text-slate-700 transition-all"
                />
              </div>
            </div>

            {/* Description */}
            <div className="space-y-2">
              <label className="text-xs font-black text-slate-400 uppercase tracking-wider">描述 (Description)</label>
              <textarea 
                value={method.description}
                onChange={e => setMethod({ ...method, description: e.target.value })}
                rows={3}
                className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-slate-600 transition-all resize-none"
              />
            </div>

            {/* Formula Editor */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-black text-slate-400 uppercase tracking-wider">数学公式 (LaTeX)</label>
                <a href="https://katex.org/docs/supported.html" target="_blank" className="text-[10px] text-blue-500 hover:underline flex items-center gap-1">
                   <BookOpen size={10} /> KaTeX 参考
                </a>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <textarea 
                  value={method.formula}
                  onChange={e => setMethod({ ...method, formula: e.target.value })}
                  rows={4}
                  className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none font-mono text-sm text-slate-600 transition-all resize-none"
                />
                <div className="flex flex-col justify-center">
                   <div className="text-[10px] text-slate-400 mb-1 uppercase tracking-wider">实时预览</div>
                   <LatexPreview math={method.formula} />
                </div>
              </div>
            </div>

            {/* Python Implementation Stub */}
            <div className="space-y-2 pt-4 border-t border-slate-100">
               <label className="text-xs font-black text-slate-400 uppercase tracking-wider">后端实现映射 (Python Backend)</label>
               <div className="bg-slate-900 rounded-xl p-4 font-mono text-sm text-slate-300 overflow-x-auto">
                 <p className="text-slate-500"># python/main.py mapping</p>
                 <p><span className="text-purple-400">if</span> method_id == <span className="text-green-400">"{method.id}"</span>:</p>
                 <p className="pl-4">return <span className="text-yellow-400">algorithms</span>.<span className="text-blue-400">{method.id.replace('custom_', 'algo_')}</span>(data)</p>
               </div>
               <p className="text-xs text-slate-500 mt-2">
                 *注意: 这是一个高级功能。在添加新算法后，您需要在 <code className="bg-slate-100 px-1 rounded">python/algorithms.py</code> 中实现相应的数学逻辑。
               </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
