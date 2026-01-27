"use client"

import React, { useState } from 'react'
import { motion, AnimatePresence, Reorder } from 'framer-motion'
import { X, BookOpen, ChevronRight, Edit, CheckCircle, Plus, GripVertical, Settings2 } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { INITIAL_METHOD_TREE, MethodNode } from '@/lib/methods'
import { MethodDetailContent } from '@/components/MethodDetailContent'

interface MethodSelectorProps {
  isOpen: boolean
  onClose: () => void
  onSelect: (methodId: string) => void
}

export default function MethodSelector({ isOpen, onClose, onSelect }: MethodSelectorProps) {
  const router = useRouter()
  // Global tree state to allow persistent reordering
  const [methodTree, setMethodTree] = useState<MethodNode[]>(INITIAL_METHOD_TREE)
  
  // Selection state
  const [selectedCategoryId, setSelectedCategoryId] = useState<string>(INITIAL_METHOD_TREE[0].id)
  const [activeMethodId, setActiveMethodId] = useState<string | null>(null)
  
  // Find current objects based on IDs
  const selectedCategory = methodTree.find(c => c.id === selectedCategoryId) || methodTree[0]
  const activeMethod = selectedCategory.children?.find(m => m.id === activeMethodId)

  // Handle reordering of methods within a category
  const handleReorder = (newOrder: MethodNode[]) => {
    setMethodTree(prev => prev.map(cat => {
      if (cat.id === selectedCategoryId) {
        return { ...cat, children: newOrder }
      }
      return cat
    }))
  }

  const handleAddCategory = () => {
    const newId = `cat_${Date.now()}`
    const newCategory: MethodNode = {
      id: newId,
      name: '新建分类组',
      shortName: 'NEW',
      description: '自定义分类',
      formula: '',
      children: []
    }
    setMethodTree(prev => [...prev, newCategory])
    setSelectedCategoryId(newId)
  }

  const handleAddMethod = () => {
    const newMethod: MethodNode = {
      id: `custom_${Date.now()}`,
      name: '新算法',
      shortName: 'New',
      description: '请点击编辑按钮配置此算法的参数与公式。',
      formula: "f(x) = ..."
    }

    setMethodTree(prev => prev.map(cat => {
      if (cat.id === selectedCategoryId) {
        return { 
          ...cat, 
          children: [...(cat.children || []), newMethod] 
        }
      }
      return cat
    }))
    
    // Automatically select the new method
    setActiveMethodId(newMethod.id)
  }

  const handleConfirm = () => {
    if (activeMethodId) {
      onSelect(activeMethodId)
      onClose()
    }
  }

  const handleEdit = () => {
    if (activeMethodId) {
      router.push(`/methods/${activeMethodId}`)
    }
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.3 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black z-[140] backdrop-blur-sm"
          />

          {/* Drawer (Expanded Width to 4/5) */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 bottom-0 w-[85vw] bg-white shadow-2xl z-[150] flex flex-col border-l border-slate-200"
          >
            {/* Header */}
            <div className="flex-none px-8 py-5 bg-white border-b border-slate-200 flex items-center justify-between z-20 shadow-sm">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-blue-200">
                  <Settings2 size={22} />
                </div>
                <div className="flex flex-col">
                  <h2 className="text-xl font-bold text-slate-900 leading-none">
                    参数估计方法库
                  </h2>
                  <span className="text-xs text-slate-500 font-medium tracking-wide mt-1">Method Taxonomy & Configuration</span>
                </div>
              </div>
              <button 
                onClick={onClose}
                className="p-2 hover:bg-slate-100 rounded-full transition-colors text-slate-400 hover:text-slate-600"
              >
                <X size={24} />
              </button>
            </div>

            {/* Content: Balanced Layout */}
            <div className="flex-1 flex overflow-hidden relative text-slate-700 bg-slate-50">
              
              {/* Layer 1: Categories (20%) */}
              <div className="w-[22%] flex-none flex flex-col border-r border-slate-200 bg-white z-10">
                <div className="p-4 border-b border-slate-100 bg-slate-50/50">
                   <div className="text-xs font-black text-slate-400 uppercase tracking-wider">主要分类 (Categories)</div>
                </div>
                <div className="flex-1 overflow-y-auto p-3 space-y-2">
                  {methodTree.map(cat => (
                    <button
                      key={cat.id}
                      onClick={() => { setSelectedCategoryId(cat.id); setActiveMethodId(null); }}
                      className={cn(
                        "w-full text-left px-4 py-3 rounded-xl transition-all duration-200 flex items-center justify-between group border relative overflow-hidden",
                        selectedCategoryId === cat.id 
                          ? "bg-blue-50 border-blue-200 text-blue-700 shadow-sm" 
                          : "bg-white border-transparent hover:bg-slate-50 text-slate-600"
                      )}
                    >
                      <div className="flex flex-col relative z-10">
                        <span className="font-bold text-sm">{cat.name}</span>
                        <span className="text-[10px] opacity-60 font-mono mt-0.5">{cat.shortName}</span>
                      </div>
                      {selectedCategoryId === cat.id && <ChevronRight size={16} className="text-blue-500" />}
                    </button>
                  ))}
                  
                  {/* Add Category Button */}
                  <button 
                    onClick={handleAddCategory}
                    className="w-full mt-4 py-3 border border-dashed border-slate-300 rounded-xl text-slate-400 hover:border-blue-400 hover:text-blue-600 hover:bg-blue-50 transition-all flex items-center justify-center gap-2 font-bold text-xs"
                  >
                    <Plus size={14} />
                    新建分类
                  </button>
                </div>
              </div>

              {/* Layer 2: Methods List (25%) */}
              <div className="w-[28%] flex-none flex flex-col border-r border-slate-200 bg-slate-50 z-10">
                 <div className="p-4 border-b border-slate-200 bg-slate-50 flex justify-between items-center">
                    <div className="text-xs font-black text-slate-400 uppercase tracking-wider">具体算法 (Algorithms)</div>
                    <span className="text-[10px] bg-slate-200 text-slate-500 px-1.5 py-0.5 rounded font-medium">可拖拽</span>
                 </div>
                 
                 <div className="flex-1 overflow-y-auto p-3">
                   <Reorder.Group 
                     axis="y" 
                     values={selectedCategory.children || []} 
                     onReorder={handleReorder}
                     className="space-y-3 pb-6"
                   >
                     {selectedCategory.children?.map(method => (
                       <Reorder.Item key={method.id} value={method}>
                         <div
                           onClick={() => setActiveMethodId(method.id)}
                           className={cn(
                             "w-full text-left p-4 border rounded-2xl shadow-sm transition-all group flex items-start gap-3 cursor-pointer relative bg-white",
                             activeMethodId === method.id
                              ? "border-blue-500 ring-1 ring-blue-500 shadow-md z-10"
                              : "border-slate-200 hover:border-blue-300 hover:shadow-md"
                           )}
                         >
                           {/* Drag Handle */}
                           <div className="text-slate-300 cursor-grab active:cursor-grabbing hover:text-slate-400 mt-1">
                             <GripVertical size={14} />
                           </div>

                           <div className="flex-1 min-w-0">
                             <div className="flex justify-between items-start">
                               <span className={cn(
                                 "font-bold text-sm truncate pr-2 transition-colors",
                                 activeMethodId === method.id ? "text-blue-700" : "text-slate-700"
                               )}>{method.name}</span>
                               {activeMethodId === method.id && <CheckCircle size={16} className="text-blue-600 shrink-0" />}
                             </div>
                             <div className="text-[10px] text-slate-400 font-mono mt-1 flex items-center gap-2">
                               <span className="bg-slate-100 px-1.5 rounded">{method.shortName}</span>
                               <span className="truncate opacity-70">{method.id}</span>
                             </div>
                           </div>
                         </div>
                       </Reorder.Item>
                     ))}
                   </Reorder.Group>

                   {/* Add Method Button (At the end) */}
                   <button 
                      onClick={handleAddMethod}
                      className="w-full py-4 border-2 border-dashed border-slate-300 rounded-2xl text-slate-400 hover:border-blue-400 hover:text-blue-600 hover:bg-blue-50 transition-all flex items-center justify-center gap-2 font-bold text-sm group"
                   >
                      <div className="w-6 h-6 rounded-full bg-slate-200 group-hover:bg-blue-200 flex items-center justify-center transition-colors">
                        <Plus size={14} className="text-slate-500 group-hover:text-blue-600" />
                      </div>
                      新增算法卡片
                   </button>
                 </div>
              </div>

              {/* Layer 3: Details Panel (Remaining) */}
              <div className="flex-1 bg-white p-0 flex flex-col relative overflow-hidden">
                 <AnimatePresence mode="wait">
                   {activeMethod ? (
                     <motion.div
                       key={activeMethod.id}
                       initial={{ opacity: 0, x: 20 }}
                       animate={{ opacity: 1, x: 0 }}
                       exit={{ opacity: 0, x: 20 }}
                       transition={{ duration: 0.2 }}
                       className="h-full flex flex-col"
                     >
                       {/* Detail Content */}
                       <div className="flex-1 overflow-y-auto">
                         {/* Banner */}
                         <div className="bg-slate-50 border-b border-slate-100 p-8 pb-10">
                            <div className="flex items-center gap-3 mb-4">
                              <span className="px-3 py-1 bg-blue-600 text-white text-xs font-bold rounded-full shadow-sm tracking-wide">
                                选中算法
                              </span>
                              <span className="text-xs font-mono text-slate-400">{activeMethod.id}</span>
                            </div>
                            <h1 className="text-3xl font-black text-slate-800 mb-2">{activeMethod.name}</h1>
                            <div className="text-sm font-bold text-blue-500 font-mono tracking-wider">{activeMethod.shortName}</div>
                         </div>

                         <div className="p-8">
                            <MethodDetailContent method={activeMethod} />
                         </div>
                       </div>

                       {/* Footer Actions */}
                       <div className="p-6 border-t border-slate-100 bg-white/80 backdrop-blur-md flex items-center gap-4 z-20">
                          <button
                            onClick={handleEdit}
                            disabled={!activeMethodId}
                            className={cn(
                              "flex-1 h-12 border font-bold rounded-xl transition-all flex items-center justify-center gap-2 group",
                              activeMethodId
                                ? "bg-white border-slate-200 hover:border-blue-300 hover:shadow-lg text-slate-600"
                                : "bg-slate-50 border-slate-100 text-slate-300 cursor-not-allowed"
                            )}
                          >
                             <Edit size={18} className={cn(
                               "transition-colors",
                               activeMethodId ? "text-slate-400 group-hover:text-blue-500" : "text-slate-300"
                             )} />
                             编辑详情
                          </button>

                          <button
                            onClick={handleConfirm}
                            disabled={!activeMethodId}
                            className={cn(
                              "flex-[2] h-12 font-bold rounded-xl transition-all flex items-center justify-center gap-2",
                              activeMethodId
                                ? "bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-200 hover:shadow-blue-300 hover:translate-y-[-1px] active:translate-y-[1px] cursor-pointer"
                                : "bg-slate-100 text-slate-300 cursor-not-allowed"
                            )}
                          >
                             <CheckCircle size={18} />
                             确定选择
                          </button>
                       </div>

                     </motion.div>
                   ) : (
                     <div className="h-full flex flex-col justify-center items-center text-slate-300 bg-slate-50/30">
                        <div className="w-20 h-20 bg-slate-100 rounded-full flex items-center justify-center mb-4">
                           <BookOpen size={32} className="opacity-40" />
                        </div>
                        <p className="text-lg font-bold text-slate-400">请选择一个算法</p>
                        <p className="text-sm opacity-50 mt-1">点击左侧列表查看详细信息</p>
                     </div>
                   )}
                 </AnimatePresence>
              </div>

            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

const cn = (...classes: (string | undefined | null | false)[]) => classes.filter(Boolean).join(' ')