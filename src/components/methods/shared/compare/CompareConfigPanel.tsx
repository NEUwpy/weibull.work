"use client"

import React from 'react'
import { Settings, FlaskConical } from 'lucide-react'
import { cn } from '@/lib/utils'

// 参数定义
const PARAM_DEFINITIONS = [
  { id: 'beta', name: '形状参数', symbol: 'β', chunkKey: 'beta' },
  { id: 'eta', name: '尺度参数', symbol: 'η', chunkKey: 'eta' },
  { id: 'gamma', name: '位置参数', symbol: 'γ', chunkKey: 'gamma' },
  { id: 'sampleSize', name: '样本量', symbol: 'n', chunkKey: 'n' },
]

const SIM_CONFIG_DEFINITIONS = [
  { id: 'rep', name: '重复次数', symbol: 'rep', chunkKey: 'rep' },
  { id: 'seed', name: '随机种子', symbol: 'seed', chunkKey: 'seed' },
]

const CALC_CONFIG_DEFINITIONS = [
  { id: 'step', name: '迭代步长', symbol: 'step', chunkKey: 'step' },
]

// 样式常量
const PARAM_COLORS: Record<string, string> = {
  beta: 'border-blue-200 bg-blue-50',
  eta: 'border-emerald-200 bg-emerald-50',
  gamma: 'border-amber-200 bg-amber-50',
  sampleSize: 'border-purple-200 bg-purple-50',
  rep: 'border-violet-200 bg-violet-50',
  seed: 'border-indigo-200 bg-indigo-50',
  step: 'border-cyan-200 bg-cyan-50',
  offset: 'border-rose-200 bg-rose-50',  // MDM 偏移量
}

const BORDER_STYLES = {
  red: 'border border-red-400 bg-red-50 text-red-700',
  green: 'border border-green-300 bg-green-50 text-green-700 cursor-pointer hover:bg-green-100',
  white: 'border border-slate-200 bg-white text-slate-400',
}

interface CompareConfigPanelProps {
  // 各方法的可用参数值
  availableParams: {
    beta: number[]
    eta: number[]
    gamma: number[]
    n: number[]
    rep: number[]
    seed: number[]
    step: number[]
    offset: number[]
  }
  // 参数交集（多选模式用）
  paramIntersection: {
    beta: number[]
    eta: number[]
    gamma: number[]
    n: number[]
    rep: number[]
    seed: number[]
    step: number[]
    offset: number[]
  }
  // 当前选择状态
  selectedParams: {
    beta: number[]
    eta: number[]
    gamma: number[]
    n: number[]
    rep: number[]
    seed: number[]
    step: number[]
    offset: number[]
  }
  fixedValues: Record<string, number>
  // 变量维度
  variableDimensions: string[]
  // 选中的方法（用于判断是否需要显示 MDM 的 offset）
  selectedMethods: string[]
  // 回调
  onToggleValue: (paramId: string, value: number) => void
  onSelectAll: (paramId: string) => void
  onToggleVariable: (paramId: string) => void
  // 模式
  isMultiSelectMode: boolean
}

export default function CompareConfigPanel({
  availableParams,
  paramIntersection,
  selectedParams,
  fixedValues,
  variableDimensions,
  selectedMethods,
  onToggleValue,
  onSelectAll,
  onToggleVariable,
  isMultiSelectMode
}: CompareConfigPanelProps) {
  const canAddVariable = variableDimensions.length < 2
  const hasMDM = selectedMethods.some(m => m.toLowerCase() === 'mdm')

  const formatValue = (v: number) => {
    if (v < 1 && v !== 0) return v.toFixed(2)
    if (v >= 1000) return `${v / 1000}k`
    return String(v)
  }

  const getBorderState = (paramId: string, chunkKey: string, value: number): 'red' | 'green' | 'white' => {
    // 使用 chunkKey 来判断是否是变量（因为 variableDimensions 存的是 chunkKey）
    const isVariable = variableDimensions.includes(chunkKey)
    // 使用 chunkKey 来查找 selectedParams（如 sampleSize -> n）
    const selected = selectedParams[chunkKey as keyof typeof selectedParams] || []
    const fixed = fixedValues[chunkKey]
    const isSelected = isVariable ? selected.includes(value) : fixed === value

    if (isSelected) return 'red'

    // 多选模式：检查是否在交集中
    if (isMultiSelectMode && isVariable) {
      const intersection = paramIntersection[chunkKey as keyof typeof paramIntersection] || []
      return intersection.includes(value) ? 'green' : 'white'
    }

    // 单选模式：所有可选值都是绿色
    return 'green'
  }

  const renderParamCard = (
    param: { id: string; name: string; symbol: string; chunkKey: string },
    values: number[]
  ) => {
    // 使用 chunkKey 来判断是否是变量
    const isVariable = variableDimensions.includes(param.chunkKey)

    return (
      <div
        className={cn(
          "rounded-xl border-2 p-3 transition-all h-full flex flex-col",
          PARAM_COLORS[param.id] || "border-slate-200 bg-slate-50"
        )}
      >
        <div className="flex items-center justify-between mb-2 min-h-[28px]">
          <div className="flex items-center gap-1">
            <span className="text-sm font-bold">{param.name}</span>
            <span className="text-xs font-mono text-slate-500">{param.symbol}</span>
          </div>
          <div
            className={cn(
              "px-2 py-0.5 rounded text-xs font-bold",
              isVariable
                ? "bg-purple-600 text-white"
                : "bg-white text-purple-700 border border-purple-200"
            )}
          >
            {isVariable ? "变量" : "可选"}
          </div>
        </div>

        <div className="flex flex-wrap gap-1 flex-1 content-start">
          {values.map((v) => {
            const state = getBorderState(param.id, param.chunkKey, v)
            const isClickable = state !== "white"

            return (
              <span
                key={v}
                onClick={() => isClickable && onToggleValue(param.chunkKey, v)}
                className={cn(
                  "px-1.5 py-0.5 rounded text-xs font-mono font-bold transition-all",
                  BORDER_STYLES[state],
                  isClickable && "cursor-pointer"
                )}
              >
                {formatValue(v)}
              </span>
            )
          })}
        </div>

        <div className="mt-auto pt-2 border-t border-slate-200/50 flex gap-2 min-h-[36px]">
          {isVariable && (
            <button
              onClick={() => onSelectAll(param.chunkKey)}
              className="flex-1 text-xs font-bold text-slate-500 hover:text-slate-700 py-1.5 rounded hover:bg-slate-100"
            >
              全选
            </button>
          )}
          <button
            onClick={() => onToggleVariable(param.chunkKey)}
            disabled={!isVariable && !canAddVariable}
            className={cn(
              "flex-1 text-xs font-bold py-1.5 rounded transition-all",
              isVariable
                ? "bg-purple-600 text-white hover:bg-purple-700"
                : canAddVariable
                  ? "text-slate-500 hover:text-slate-700 hover:bg-slate-100"
                  : "text-slate-300 cursor-not-allowed"
            )}
          >
            {isVariable ? "取消变量" : "设为变量"}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 参数配置 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Settings className="text-slate-600" size={20} />
            <h3 className="text-lg font-bold text-slate-800">参数配置</h3>
          </div>
          <div className="text-sm text-slate-500">
            变量: <span className="font-bold text-purple-600">{variableDimensions.length}</span>/2
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          {PARAM_DEFINITIONS.map((param) => {
            const values = availableParams[param.chunkKey as keyof typeof availableParams] || []
            const isSingleValue = values.length <= 1
            return (
              <div key={param.id} className={cn("flex flex-col", isSingleValue ? "flex-shrink-0 min-w-[100px]" : "flex-1 min-w-[140px]")}>
                {renderParamCard(param, values)}
              </div>
            )
          })}
          {/* MDM 偏移量参数 */}
          {hasMDM && (() => {
            const values = availableParams.offset || []
            const isSingleValue = values.length <= 1
            return (
              <div className={cn("flex flex-col", isSingleValue ? "flex-shrink-0 min-w-[100px]" : "flex-1 min-w-[140px]")}>
                {renderParamCard(
                  { id: 'offset', name: '偏移量', symbol: 'δ', chunkKey: 'offset' },
                  values
                )}
              </div>
            )
          })()}
        </div>
      </div>

      {/* 仿真与计算配置 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 仿真配置 */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <FlaskConical className="text-violet-600" size={20} />
            <h3 className="text-lg font-bold text-slate-800">仿真配置</h3>
          </div>
          <div className="flex flex-wrap gap-3">
            {SIM_CONFIG_DEFINITIONS.map((config) => {
              const values = availableParams[config.chunkKey as keyof typeof availableParams] || [1000]
              const isSingleValue = values.length <= 1
              return (
                <div key={config.id} className={cn("flex flex-col", isSingleValue ? "flex-shrink-0 min-w-[100px]" : "flex-1 min-w-[140px]")}>
                  {renderParamCard(
                    { ...config, id: config.chunkKey },
                    values
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* 计算配置 */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <Settings className="text-cyan-600" size={20} />
            <h3 className="text-lg font-bold text-slate-800">计算配置</h3>
          </div>
          <div className="flex flex-wrap gap-3">
            {CALC_CONFIG_DEFINITIONS.map((config) => {
              const values = availableParams[config.chunkKey as keyof typeof availableParams] || [60]
              const isSingleValue = values.length <= 1
              return (
                <div key={config.id} className={cn("flex flex-col", isSingleValue ? "flex-shrink-0 min-w-[100px]" : "flex-1 min-w-[140px]")}>
                  {renderParamCard(
                    { ...config, id: config.chunkKey },
                    values
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
