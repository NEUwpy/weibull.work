"use client"

import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, FileText, AlertCircle, Check, Plus, Trash2, Edit2, Database } from 'lucide-react'
import { DataPoint } from '@/lib/weibull'
import { CASE_LIBRARY, CaseItem } from '@/lib/cases'

interface DataEditorProps {
  isOpen: boolean
  initialData?: DataPoint[]
  onClose: () => void
  onSave: (data: DataPoint[]) => void
}

export default function DataEditor({ isOpen, initialData, onClose, onSave }: DataEditorProps) {
  const [cases, setCases] = useState<CaseItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null)
  const [editingCaseId, setEditingCaseId] = useState<string | null>(null)
  
  // Temporary state for the case being edited
  const [editText, setEditText] = useState('')
  const [editName, setEditName] = useState('')
  const [parseError, setParseError] = useState<string | null>(null)

  // Initialize: if initialData is provided, maybe highlight a "Custom" case or just ready to add new
  useEffect(() => {
    if (isOpen) {
      setIsLoading(true)
      fetch('/api/cases')
        .then(res => res.json())
        .then(data => {
          const mappedData = data.map((c: any) => {
             // Simple mapping for DataEditor, detailed desc not critical here
             return {
                ...c,
                name: c.title || c.name,
                dataRaw: c.data_raw || c.dataRaw
             }
          })
          setCases(mappedData)
          setIsLoading(false)
        })
        .catch(err => {
          console.error(err)
          setIsLoading(false)
        })
    }
  }, [isOpen])

  const parseData = (text: string): { data: DataPoint[], error: string | null } => {
    if (!text.trim()) return { data: [], error: null }
    
    const lines = text.split('\n')
    const newData: DataPoint[] = []
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim()
      if (!line) continue

      const match = line.match(/^([\d.]+)(?:[,\s]+([FSfs]))?$/)
      if (match) {
        const val = parseFloat(match[1])
        const statusChar = match[2]?.toUpperCase() || 'F'
        if (isNaN(val)) return { data: [], error: `第 ${i + 1} 行: 数字格式无效` }
        newData.push({ id: i, value: val, status: statusChar as 'F' | 'S' })
      } else if (!line.startsWith('#')) {
        return { data: [], error: `第 ${i + 1} 行: 格式无效` }
      }
    }
    return { data: newData, error: null }
  }

  const handleEditClick = (c: CaseItem) => {
    setEditingCaseId(c.id)
    setEditName(c.name)
    setEditText(c.dataRaw)
    setParseError(null)
    // Also select it
    setSelectedCaseId(c.id)
  }

  const handleSaveEdit = () => {
    const { error } = parseData(editText)
    if (error) {
      setParseError(error)
      return
    }

    setCases(prev => prev.map(c => {
      if (c.id === editingCaseId) {
        return { ...c, name: editName, dataRaw: editText }
      }
      return c
    }))
    setEditingCaseId(null)
    setParseError(null)
  }

  const handleCancelEdit = () => {
    setEditingCaseId(null)
    setParseError(null)
  }

  const handleAddNew = () => {
    const newId = `new_${Date.now()}`
    const newCase: CaseItem = {
      id: newId,
      name: '新案例数据',
      dataRaw: '',
      description: '请点击编辑输入数据',
      industry: '其他',
      type: '完全样本',
      size: '小样本',
      tags: [],
      created_at: new Date().toISOString().split('T')[0]
    }
    setCases(prev => [...prev, newCase])
    // Immediately enter edit mode
    handleEditClick(newCase)
  }

  const handleDelete = (id: string) => {
    if (confirm('确定要删除这个案例吗？')) {
      setCases(prev => prev.filter(c => c.id !== id))
      if (selectedCaseId === id) setSelectedCaseId(null)
      if (editingCaseId === id) setEditingCaseId(null)
    }
  }

  const handleConfirmSelection = () => {
    const activeId = editingCaseId || selectedCaseId
    if (!activeId) return

    // If currently editing, try to save first
    let textToParse = ''
    if (editingCaseId) {
        textToParse = editText
    } else {
        const c = cases.find(c => c.id === activeId)
        if (c) textToParse = c.dataRaw
    }

    const { data, error } = parseData(textToParse)
    if (error) {
      setParseError(error)
      return
    }

    if (data.length === 0) {
      setParseError("数据为空")
      return
    }

    // Save changes to list if editing
    if (editingCaseId) {
        handleSaveEdit()
    }

    onSave(data)
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.3 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black z-[140] backdrop-blur-sm"
          />

          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 bottom-0 w-[600px] bg-slate-50 shadow-2xl z-[150] flex flex-col border-l border-slate-200"
          >
            {/* Header */}
            <div className="p-6 border-b border-slate-200 bg-white flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-emerald-500 rounded-lg flex items-center justify-center text-white shadow-md">
                   <Database size={20} />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-slate-900">案例数据库</h2>
                  <p className="text-xs text-slate-500 font-medium">Case Database</p>
                </div>
              </div>
              <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-full transition-colors text-slate-400">
                <X size={24} />
              </button>
            </div>

            {/* List Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
               {cases.map(item => {
                 const isEditing = editingCaseId === item.id
                 const isSelected = selectedCaseId === item.id
                 
                 return (
                   <div 
                     key={item.id}
                     onClick={() => !isEditing && setSelectedCaseId(item.id)}
                     className={`
                       border rounded-2xl transition-all duration-300 overflow-hidden
                       ${isSelected ? 'border-emerald-500 shadow-md ring-1 ring-emerald-100 bg-white' : 'border-slate-200 bg-white hover:border-emerald-300'}
                     `}
                   >
                     {/* Case Header Row */}
                     <div className="flex items-center justify-between p-4 cursor-pointer">
                        <div className="flex items-center gap-3">
                           <div className={`
                             w-4 h-4 rounded-full border-2 flex items-center justify-center
                             ${isSelected ? 'border-emerald-500' : 'border-slate-300'}
                           `}>
                              {isSelected && <div className="w-2 h-2 rounded-full bg-emerald-500" />}
                           </div>
                           <div>
                              <h3 className="font-bold text-slate-800">{item.name}</h3>
                              <p className="text-xs text-slate-400">{item.dataRaw.split('\n').filter(l=>l.trim()).length} 个数据点</p>
                           </div>
                        </div>
                        
                        {!isEditing && (
                          <div className="flex gap-2">
                             <button 
                               onClick={(e) => { e.stopPropagation(); handleEditClick(item); }}
                               className="p-2 hover:bg-slate-100 rounded-lg text-slate-400 hover:text-blue-500 transition-colors"
                             >
                                <Edit2 size={16} />
                             </button>
                             <button 
                               onClick={(e) => { e.stopPropagation(); handleDelete(item.id); }}
                               className="p-2 hover:bg-red-50 rounded-lg text-slate-400 hover:text-red-500 transition-colors"
                             >
                                <Trash2 size={16} />
                             </button>
                          </div>
                        )}
                     </div>

                     {/* Inline Editor */}
                     <AnimatePresence>
                       {isEditing && (
                         <motion.div
                           initial={{ height: 0, opacity: 0 }}
                           animate={{ height: 'auto', opacity: 1 }}
                           exit={{ height: 0, opacity: 0 }}
                           className="bg-slate-50 border-t border-slate-100 p-4"
                         >
                            <div className="space-y-4">
                               <div>
                                  <label className="text-xs font-bold text-slate-500 uppercase">案例名称</label>
                                  <input 
                                    type="text" 
                                    value={editName}
                                    onChange={(e) => setEditName(e.target.value)}
                                    className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:border-emerald-500 text-sm font-bold"
                                  />
                               </div>
                               <div>
                                  <div className="flex justify-between items-center mb-1">
                                    <label className="text-xs font-bold text-slate-500 uppercase">数据样本</label>
                                    <span className="text-[10px] text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">支持复制粘贴</span>
                                  </div>
                                  <textarea
                                    value={editText}
                                    onChange={(e) => setEditText(e.target.value)}
                                    rows={6}
                                    className="w-full p-3 border border-slate-200 rounded-lg font-mono text-sm focus:outline-none focus:border-emerald-500 resize-none"
                                    placeholder="100&#10;120 F&#10;150 S"
                                  />
                               </div>

                               {parseError && (
                                 <div className="flex items-center gap-2 text-xs text-red-500 font-bold bg-red-50 p-2 rounded">
                                   <AlertCircle size={14} />
                                   {parseError}
                                 </div>
                               )}

                               <div className="flex justify-end gap-3 pt-2">
                                  <button 
                                    onClick={handleCancelEdit}
                                    className="px-4 py-2 text-sm text-slate-500 hover:bg-slate-200 rounded-lg transition-colors"
                                  >
                                    取消
                                  </button>
                                  <button 
                                    onClick={handleSaveEdit}
                                    className="px-4 py-2 text-sm bg-slate-800 text-white hover:bg-slate-900 rounded-lg transition-colors font-medium"
                                  >
                                    保存修改
                                  </button>
                               </div>
                            </div>
                         </motion.div>
                       )}
                     </AnimatePresence>
                   </div>
                 )
               })}

               <button 
                 onClick={handleAddNew}
                 className="w-full py-4 border-2 border-dashed border-slate-300 rounded-2xl text-slate-400 hover:border-emerald-400 hover:text-emerald-600 hover:bg-emerald-50 transition-all flex items-center justify-center gap-2 font-bold group"
               >
                 <div className="w-6 h-6 rounded-full bg-slate-200 group-hover:bg-emerald-200 flex items-center justify-center transition-colors">
                    <Plus size={14} className="text-slate-500 group-hover:text-emerald-700" />
                 </div>
                 新建空白案例
               </button>
            </div>

            {/* Footer Actions */}
            <div className="p-6 bg-white border-t border-slate-200 flex items-center justify-between z-20 shadow-[0_-10px_40px_-15px_rgba(0,0,0,0.1)]">
               <div className="text-sm text-slate-500">
                  {selectedCaseId ? '已选择 1 个案例' : '请选择一个案例'}
               </div>
               <button
                 onClick={handleConfirmSelection}
                 disabled={!selectedCaseId && !editingCaseId}
                 className="px-8 py-3 bg-emerald-500 hover:bg-emerald-600 disabled:bg-slate-300 disabled:cursor-not-allowed text-white rounded-xl font-bold transition-all shadow-lg shadow-emerald-200 flex items-center gap-2"
               >
                 <Check size={18} />
                 确定选用
               </button>
            </div>

          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
