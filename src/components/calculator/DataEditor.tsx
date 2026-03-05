"use client"

import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, FileText, AlertCircle, Check, Plus, Trash2, Edit2, Database, ChevronDown, ChevronRight, Folder, File, Users } from 'lucide-react'
import { DataPoint, DataSource, MULTI_CURVE_COLORS } from '@/lib/weibull'

// 树节点类型
type CaseTreeNode =
  | { type: 'group'; id: string; title: string; sample_count: number; children: CaseItemNode[]; expanded?: boolean }
  | { type: 'case'; id: string; title: string; data_raw: string; dataPoints: number }

type CaseItemNode = {
  id: string
  title: string
  data_raw: string
  dataPoints: number
  groupId: string
}

interface DataEditorProps {
  isOpen: boolean
  initialData?: DataPoint[]
  onClose: () => void
  // 单选模式回调（保留兼容）
  onSave: (data: DataPoint[]) => void
  // 多选模式回调
  onSaveMulti?: (selections: DataSource[]) => void
  // 初始模式
  initialMode?: 'single' | 'multi'
}

export default function DataEditor({
  isOpen,
  initialData,
  onClose,
  onSave,
  onSaveMulti,
  initialMode = 'single'
}: DataEditorProps) {
  // 模式状态
  const [mode, setMode] = useState<'single' | 'multi'>(initialMode)

  // 树形数据
  const [treeData, setTreeData] = useState<CaseTreeNode[]>([])
  const [isLoading, setIsLoading] = useState(false)

  // 单选模式状态
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null)

  // 多选模式状态
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())

  // 编辑状态
  const [editingCaseId, setEditingCaseId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [editName, setEditName] = useState('')
  const [parseError, setParseError] = useState<string | null>(null)

  // 加载数据
  useEffect(() => {
    if (isOpen) {
      // 重置选择状态
      setSelectedIds(new Set())
      setSelectedCaseId(null)
      setMode(initialMode)
      setIsLoading(true)
      fetch('/api/cases/tree')
        .then(res => res.json())
        .then(data => {
          setTreeData(data)
          setIsLoading(false)
        })
        .catch(err => {
          console.error(err)
          setIsLoading(false)
        })
    }
  }, [isOpen, initialMode])

  // 解析数据
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

  // 查找案例数据
  const findCaseData = (id: string): { data_raw: string; title: string; groupId?: string } | null => {
    for (const node of treeData) {
      if (node.type === 'case' && node.id === id) {
        return { data_raw: node.data_raw, title: node.title }
      }
      if (node.type === 'group') {
        const child = node.children.find(c => c.id === id)
        if (child) {
          return { data_raw: child.data_raw, title: child.title, groupId: node.id }
        }
      }
    }
    return null
  }

  // 切换组展开状态
  const toggleGroupExpand = (groupId: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev)
      if (next.has(groupId)) {
        next.delete(groupId)
      } else {
        next.add(groupId)
      }
      return next
    })
  }

  // 切换单个选择
  const toggleSelection = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  // 全选/取消全选组
  const toggleGroupSelection = (groupId: string, childIds: string[]) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      const allSelected = childIds.every(id => next.has(id))

      if (allSelected) {
        childIds.forEach(id => next.delete(id))
      } else {
        childIds.forEach(id => next.add(id))
      }
      return next
    })
  }

  // 获取选中的数据源
  const getSelectedDataSources = (): DataSource[] => {
    const sources: DataSource[] = []
    let colorIndex = 0

    selectedIds.forEach(id => {
      const caseData = findCaseData(id)
      if (caseData && caseData.data_raw) {
        const { data } = parseData(caseData.data_raw)
        if (data.length > 0) {
          sources.push({
            id,
            name: caseData.title,
            color: MULTI_CURVE_COLORS[colorIndex % MULTI_CURVE_COLORS.length],
            data,
            sourceType: caseData.groupId ? 'group-subcase' : 'case',
            groupId: caseData.groupId,
            visible: true
          })
          colorIndex++
        }
      }
    })

    return sources
  }

  // 确认选择
  const handleConfirmSelection = () => {
    if (mode === 'multi') {
      // 多选模式
      const sources = getSelectedDataSources()
      if (sources.length > 0 && onSaveMulti) {
        onSaveMulti(sources)
        onClose() // 关闭 DataEditor
      } else if (sources.length === 1 && !onSaveMulti) {
        // 降级为单选
        onSave(sources[0].data)
        onClose()
      }
    } else {
      // 单选模式
      const activeId = editingCaseId || selectedCaseId
      if (!activeId) return

      let textToParse = ''
      if (editingCaseId) {
        textToParse = editText
      } else {
        const caseData = findCaseData(activeId)
        if (caseData) textToParse = caseData.data_raw
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

      onSave(data)
    }
  }

  // 编辑相关
  const handleEditClick = (id: string) => {
    const caseData = findCaseData(id)
    if (caseData) {
      setEditingCaseId(id)
      setEditName(caseData.title)
      setEditText(caseData.data_raw)
      setParseError(null)
      if (mode === 'single') {
        setSelectedCaseId(id)
      }
    }
  }

  const handleSaveEdit = () => {
    const { error } = parseData(editText)
    if (error) {
      setParseError(error)
      return
    }
    // 编辑保存逻辑（本地更新）
    setEditingCaseId(null)
    setParseError(null)
  }

  const handleCancelEdit = () => {
    setEditingCaseId(null)
    setParseError(null)
  }

  // 统计选中数量
  const selectedCount = selectedIds.size

  // 获取选中项名称预览
  const getSelectedPreview = (): string[] => {
    const names: string[] = []
    selectedIds.forEach(id => {
      const caseData = findCaseData(id)
      if (caseData) {
        names.push(caseData.title)
      }
    })
    return names.slice(0, 5) // 最多显示5个
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
            className="fixed right-0 top-0 bottom-0 w-[650px] bg-slate-50 shadow-2xl z-[150] flex flex-col border-l border-slate-200"
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

            {/* Mode Toggle & Search */}
            <div className="p-4 bg-white border-b border-slate-200 flex items-center gap-4">
              <div className="bg-slate-100 p-1 rounded-lg flex border border-slate-200">
                <button
                  onClick={() => setMode('single')}
                  className={`px-4 py-2 rounded-md text-sm font-bold transition-all ${
                    mode === 'single'
                      ? 'bg-white text-slate-800 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  <Users size={16} className="inline mr-2" />
                  单选
                </button>
                <button
                  onClick={() => setMode('multi')}
                  className={`px-4 py-2 rounded-md text-sm font-bold transition-all ${
                    mode === 'multi'
                      ? 'bg-white text-emerald-600 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  <Folder size={16} className="inline mr-2" />
                  多选
                </button>
              </div>
              {mode === 'multi' && (
                <span className="text-sm text-slate-500">
                  已选择 <span className="font-bold text-emerald-600">{selectedCount}</span> 项
                </span>
              )}
            </div>

            {/* List Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              {isLoading ? (
                <div className="text-center py-12 text-slate-400">加载中...</div>
              ) : (
                treeData.map(node => {
                  if (node.type === 'group') {
                    const isExpanded = expandedGroups.has(node.id)
                    const childIds = node.children.map(c => c.id)
                    const selectedInGroup = childIds.filter(id => selectedIds.has(id)).length

                    return (
                      <div key={node.id} className="border border-slate-200 rounded-xl bg-white overflow-hidden">
                        {/* Group Header */}
                        <div
                          className="flex items-center justify-between p-3 bg-slate-50 cursor-pointer hover:bg-slate-100 transition-colors"
                          onClick={() => toggleGroupExpand(node.id)}
                        >
                          <div className="flex items-center gap-3">
                            {isExpanded ? <ChevronDown size={18} className="text-slate-400" /> : <ChevronRight size={18} className="text-slate-400" />}
                            <Folder size={18} className="text-amber-500" />
                            <div>
                              <span className="font-bold text-slate-800">{node.title}</span>
                              <span className="text-xs text-slate-400 ml-2">({node.sample_count}个子案例)</span>
                            </div>
                          </div>

                          {mode === 'multi' && (
                            <button
                              onClick={(e) => { e.stopPropagation(); toggleGroupSelection(node.id, childIds) }}
                              className={`px-3 py-1 text-xs font-bold rounded-full transition-colors ${
                                selectedInGroup === childIds.length
                                  ? 'bg-emerald-500 text-white'
                                  : selectedInGroup > 0
                                    ? 'bg-emerald-100 text-emerald-700'
                                    : 'bg-slate-200 text-slate-600 hover:bg-slate-300'
                              }`}
                            >
                              {selectedInGroup === childIds.length ? '取消全选' : selectedInGroup > 0 ? `${selectedInGroup}/${childIds.length}` : '全选'}
                            </button>
                          )}
                        </div>

                        {/* Children */}
                        <AnimatePresence>
                          {isExpanded && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className="border-t border-slate-100"
                            >
                              {node.children.map(child => {
                                const isSelected = mode === 'multi'
                                  ? selectedIds.has(child.id)
                                  : selectedCaseId === child.id
                                const isEditing = editingCaseId === child.id

                                return (
                                  <div
                                    key={child.id}
                                    onClick={() => {
                                      if (mode === 'multi') {
                                        toggleSelection(child.id)
                                      } else if (!isEditing) {
                                        setSelectedCaseId(child.id)
                                      }
                                    }}
                                    className={`flex items-center justify-between p-3 border-b border-slate-50 last:border-b-0 cursor-pointer transition-colors ${
                                      isSelected ? 'bg-emerald-50' : 'hover:bg-slate-50'
                                    }`}
                                  >
                                    <div className="flex items-center gap-3">
                                      {mode === 'multi' ? (
                                        <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                                          isSelected ? 'bg-emerald-500 border-emerald-500' : 'border-slate-300'
                                        }`}>
                                          {isSelected && <Check size={14} className="text-white" />}
                                        </div>
                                      ) : (
                                        <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                                          isSelected ? 'border-emerald-500' : 'border-slate-300'
                                        }`}>
                                          {isSelected && <div className="w-2 h-2 rounded-full bg-emerald-500" />}
                                        </div>
                                      )}
                                      <File size={16} className="text-slate-400" />
                                      <div>
                                        <span className="font-medium text-slate-700">{child.title}</span>
                                        <span className="text-xs text-slate-400 ml-2">{child.dataPoints}点</span>
                                      </div>
                                    </div>

                                    {!isEditing && (
                                      <button
                                        onClick={(e) => { e.stopPropagation(); handleEditClick(child.id) }}
                                        className="p-1.5 hover:bg-slate-100 rounded text-slate-400 hover:text-blue-500 transition-colors"
                                      >
                                        <Edit2 size={14} />
                                      </button>
                                    )}
                                  </div>
                                )
                              })}
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    )
                  } else {
                    // 独立案例
                    const isSelected = mode === 'multi'
                      ? selectedIds.has(node.id)
                      : selectedCaseId === node.id
                    const isEditing = editingCaseId === node.id

                    return (
                      <div
                        key={node.id}
                        onClick={() => {
                          if (mode === 'multi') {
                            toggleSelection(node.id)
                          } else if (!isEditing) {
                            setSelectedCaseId(node.id)
                          }
                        }}
                        className={`border rounded-xl transition-all overflow-hidden ${
                          isSelected ? 'border-emerald-500 shadow-sm ring-1 ring-emerald-100 bg-white' : 'border-slate-200 bg-white hover:border-emerald-300'
                        }`}
                      >
                        <div className="flex items-center justify-between p-4 cursor-pointer">
                          <div className="flex items-center gap-3">
                            {mode === 'multi' ? (
                              <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                                isSelected ? 'bg-emerald-500 border-emerald-500' : 'border-slate-300'
                              }`}>
                                {isSelected && <Check size={14} className="text-white" />}
                              </div>
                            ) : (
                              <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                                isSelected ? 'border-emerald-500' : 'border-slate-300'
                              }`}>
                                {isSelected && <div className="w-2 h-2 rounded-full bg-emerald-500" />}
                              </div>
                            )}
                            <div>
                              <h3 className="font-bold text-slate-800">{node.title}</h3>
                              <p className="text-xs text-slate-400">{node.dataPoints} 个数据点</p>
                            </div>
                          </div>

                          {!isEditing && (
                            <button
                              onClick={(e) => { e.stopPropagation(); handleEditClick(node.id) }}
                              className="p-2 hover:bg-slate-100 rounded-lg text-slate-400 hover:text-blue-500 transition-colors"
                            >
                              <Edit2 size={16} />
                            </button>
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
                  }
                })
              )}
            </div>

            {/* Selection Preview (Multi-mode) */}
            {mode === 'multi' && selectedCount > 0 && (
              <div className="p-4 bg-emerald-50 border-t border-emerald-100">
                <div className="text-xs font-bold text-emerald-700 mb-2">已选择 {selectedCount} 项:</div>
                <div className="flex flex-wrap gap-2">
                  {getSelectedPreview().map((name, i) => (
                    <span key={i} className="px-2 py-1 bg-white text-emerald-700 text-xs rounded-full border border-emerald-200">
                      {name}
                    </span>
                  ))}
                  {selectedCount > 5 && (
                    <span className="px-2 py-1 bg-emerald-100 text-emerald-600 text-xs rounded-full">
                      +{selectedCount - 5} 更多
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Footer Actions */}
            <div className="p-6 bg-white border-t border-slate-200 flex items-center justify-between z-20 shadow-[0_-10px_40px_-15px_rgba(0,0,0,0.1)]">
              <div className="text-sm text-slate-500">
                {mode === 'multi'
                  ? (selectedCount > 0 ? `已选择 ${selectedCount} 个案例` : '请选择案例')
                  : (selectedCaseId ? '已选择 1 个案例' : '请选择一个案例')
                }
              </div>
              <button
                onClick={handleConfirmSelection}
                disabled={mode === 'multi' ? selectedCount === 0 : (!selectedCaseId && !editingCaseId)}
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
