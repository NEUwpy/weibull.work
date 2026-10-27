"use client"

import React from 'react'
import { cn } from '@/lib/utils'
import { Check } from 'lucide-react'

// 有studies数据的方法列表
export const AVAILABLE_METHODS = [
  { id: 'mle', name: '极大似然估计', shortName: 'MLE', color: 'bg-blue-100 border-blue-300 text-blue-700' },
  { id: 'wmle', name: '加权极大似然', shortName: 'WMLE', color: 'bg-emerald-100 border-emerald-300 text-emerald-700' },
  { id: 'mdm', name: '最小差异法', shortName: 'MDM', color: 'bg-purple-100 border-purple-300 text-purple-700' },
]

interface MethodSelectorProps {
  currentMethodId: string
  selectedMethods: string[]
  onSelectionChange: (methods: string[]) => void
  maxMethods?: number
}

export default function MethodSelector({
  currentMethodId,
  selectedMethods,
  onSelectionChange,
  maxMethods = 3
}: MethodSelectorProps) {
  const handleToggle = (methodId: string) => {
    // 当前方法不可取消
    if (methodId === currentMethodId) return

    const isSelected = selectedMethods.includes(methodId)

    if (isSelected) {
      // 取消选择
      onSelectionChange(selectedMethods.filter(id => id !== methodId))
    } else {
      // 添加选择
      if (selectedMethods.length < maxMethods) {
        onSelectionChange([...selectedMethods, methodId])
      }
    }
  }

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-slate-800">选择对比方法</h3>
        <span className="text-sm text-slate-500">
          已选 <span className="font-bold text-purple-600">{selectedMethods.length}</span>/{maxMethods}
        </span>
      </div>

      <div className="flex flex-wrap gap-3">
        {AVAILABLE_METHODS.map(method => {
          const isCurrentMethod = method.id === currentMethodId
          const isSelected = selectedMethods.includes(method.id)
          const canSelect = selectedMethods.length < maxMethods || isSelected

          return (
            <button
              key={method.id}
              onClick={() => handleToggle(method.id)}
              disabled={!canSelect && !isSelected}
              className={cn(
                "relative px-4 py-3 rounded-xl border-2 transition-all min-w-[120px]",
                "flex flex-col items-center gap-1",
                isSelected
                  ? `${method.color} border-current`
                  : canSelect
                    ? "bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-slate-100"
                    : "bg-slate-50 border-slate-100 text-slate-300 cursor-not-allowed"
              )}
            >
              {isSelected && (
                <div className={cn(
                  "absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full flex items-center justify-center",
                  isCurrentMethod ? "bg-slate-400" : "bg-green-500"
                )}>
                  <Check size={12} className="text-white" />
                </div>
              )}

              <span className="text-xs font-mono font-bold">{method.shortName}</span>
              <span className="text-[10px] opacity-70">{method.name}</span>

              {isCurrentMethod && (
                <span className="absolute -bottom-2 left-1/2 -translate-x-1/2 text-[9px] font-bold text-slate-400 bg-white px-1">
                  当前
                </span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
