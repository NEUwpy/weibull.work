"use client"

import React from 'react'
import { Filter } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * 参数选择器组件
 *
 * 支持三色边框：
 * - 红色：当前选中
 * - 绿色：可切换（与当前其他选择兼容）
 * - 白色：存在但不兼容
 */

export type BorderState = 'red' | 'green' | 'white'

export interface ParamSelectorProps {
  paramId: string
  name: string
  symbol: string
  values: (number | string)[]
  selectedValues: (number | string)[]
  getBorderState: (value: number | string) => BorderState
  isVariable: boolean
  isVariableDimension: boolean  // 是否作为变量维度（多选模式）
  maxVariablesReached: boolean  // 是否已达到2个变量上限
  onToggleValue: (value: number | string) => void
  onSelectAll: () => void
  onToggleVariableMode: () => void
  processSymbol?: string  // MDM特有：偏移量符号
}

// 参数颜色配置
const PARAM_COLORS: Record<string, string> = {
  beta: 'border-blue-200 bg-blue-50',
  eta: 'border-emerald-200 bg-emerald-50',
  gamma: 'border-amber-200 bg-amber-50',
  sampleSize: 'border-purple-200 bg-purple-50',
  n: 'border-purple-200 bg-purple-50',
  process: 'border-rose-200 bg-rose-50',
  d: 'border-rose-200 bg-rose-50',
}

const PARAM_TEXT_COLORS: Record<string, string> = {
  beta: 'text-blue-700',
  eta: 'text-emerald-700',
  gamma: 'text-amber-700',
  sampleSize: 'text-purple-700',
  n: 'text-purple-700',
  process: 'text-rose-700',
  d: 'text-rose-700',
}

// 边框样式
const BORDER_STYLES: Record<BorderState, string> = {
  red: 'border-2 text-red-500 bg-gradient-to-r from-red-100 to-orange-50',
  green: 'border-2 border-green-400 text-green-600 bg-green-50 cursor-pointer hover:bg-green-100',
  white: 'border border-slate-200 text-slate-400'
}

export function ParamSelector({
  paramId,
  name,
  symbol,
  values,
  selectedValues,
  getBorderState,
  isVariable,
  isVariableDimension,
  maxVariablesReached,
  onToggleValue,
  onSelectAll,
  onToggleVariableMode,
  processSymbol
}: ParamSelectorProps) {
  // 格式化显示值
  const formatValue = (v: number | string): string => {
    if (typeof v === 'string') return v
    if (typeof v === 'number' && v < 1 && v !== 0) return v.toFixed(2)
    if (Number.isInteger(v)) return String(v)
    return String(v)
  }

  // 显示的符号
  const displaySymbol = paramId === 'process' || paramId === 'd' ? (processSymbol || 'δ') : symbol

  return (
    <div className={cn(
      "rounded-xl border-2 p-4 transition-all",
      PARAM_COLORS[paramId] || 'border-slate-200 bg-slate-50'
    )}>
      {/* 头部 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1">
          <span className="text-sm font-bold">{name}</span>
          <span className={cn("text-xs font-mono", PARAM_TEXT_COLORS[paramId] || 'text-slate-600')}>
            {displaySymbol}
          </span>
        </div>
        <div className={cn(
          "px-2 py-0.5 rounded text-xs font-bold",
          isVariableDimension ? "bg-purple-600 text-white" :
          isVariable ? "bg-white text-purple-700" : "bg-slate-200 text-slate-500"
        )}>
          {isVariableDimension ? "变量" : isVariable ? "可选" : "固定"}
        </div>
      </div>

      {/* 值列表 */}
      <div className="flex flex-wrap gap-1">
        {values.map(v => {
          const borderState = getBorderState(v)
          const isSelected = borderState === 'red'
          const isClickable = borderState === 'green' || isSelected

          return (
            <span
              key={v}
              onClick={() => isClickable && onToggleValue(v)}
              className={cn(
                "px-1.5 py-0.5 rounded text-xs font-mono font-bold transition-all",
                BORDER_STYLES[borderState],
                isClickable && "cursor-pointer"
              )}
              style={isSelected ? { borderColor: '#f87171' } : {}}
            >
              {formatValue(v)}
            </span>
          )
        })}
      </div>

      {/* 底部按钮 */}
      {isVariable && (
        <div className="mt-3 pt-3 border-t border-black/10 flex gap-2">
          {/* 全选按钮 - 仅变量维度显示 */}
          {isVariableDimension && (
            <button
              onClick={onSelectAll}
              className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-bold transition-all bg-white text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            >
              <Filter size={12} />
              全选
            </button>
          )}

          {/* 设为变量/固定按钮 */}
          <button
            onClick={onToggleVariableMode}
            disabled={!isVariableDimension && maxVariablesReached}
            className={cn(
              "flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-bold transition-all",
              isVariableDimension
                ? "bg-purple-600 text-white hover:bg-purple-700"
                : maxVariablesReached
                  ? "bg-slate-100 text-slate-300 cursor-not-allowed"
                  : "bg-white text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            )}
          >
            {isVariableDimension ? "取消变量" : "设为变量"}
          </button>
        </div>
      )}
    </div>
  )
}

/**
 * 参数选择器简化版 - 用于固定参数
 */
export function FixedParamDisplay({
  paramId,
  name,
  symbol,
  value
}: {
  paramId: string
  name: string
  symbol: string
  value: number | string
}) {
  const formatValue = (v: number | string): string => {
    if (typeof v === 'string') return v
    if (typeof v === 'number' && v < 1 && v !== 0) return v.toFixed(2)
    if (Number.isInteger(v)) return String(v)
    return String(v)
  }

  return (
    <div className={cn(
      "rounded-xl border-2 p-4 transition-all",
      PARAM_COLORS[paramId] || 'border-slate-200 bg-slate-50'
    )}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1">
          <span className="text-sm font-bold">{name}</span>
          <span className={cn("text-xs font-mono", PARAM_TEXT_COLORS[paramId] || 'text-slate-600')}>
            {symbol}
          </span>
        </div>
        <div className="px-2 py-0.5 rounded text-xs font-bold bg-slate-200 text-slate-500">
          固定
        </div>
      </div>

      <div className="flex flex-wrap gap-1">
        <span className="px-1.5 py-0.5 rounded text-xs font-mono font-bold border-2 text-red-500 bg-gradient-to-r from-red-100 to-orange-50"
          style={{ borderColor: '#f87171' }}>
          {formatValue(value)}
        </span>
      </div>
    </div>
  )
}
