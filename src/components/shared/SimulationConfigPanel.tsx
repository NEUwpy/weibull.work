"use client"

import React from 'react'
import { FlaskConical, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'
import { BorderState } from './ParamSelector'

/**
 * 仿真/计算配置面板
 *
 * 支持选择仿真配置（重复次数、随机种子）和计算配置（方法特有参数）
 */

export interface SimulationConfig {
  rep: number
  seed: number
}

export interface MDMCalculationConfig {
  step: number
}

export interface SimulationConfigPanelProps {
  // 仿真配置
  repValues: number[]
  seedValues: number[]
  selectedRep: number
  selectedSeed: number

  // 计算配置 (MDM特有)
  mdmConfig?: {
    stepValues: number[]
    selectedStep: number
  }

  // 兼容性检查
  getBorderState: (type: 'rep' | 'seed' | 'step', value: number) => BorderState

  // 回调
  onRepChange: (rep: number) => void
  onSeedChange: (seed: number) => void
  onStepChange?: (step: number) => void
}

// 边框样式
const BORDER_STYLES: Record<BorderState, string> = {
  red: 'border-2 text-red-500 bg-gradient-to-r from-red-100 to-orange-50',
  green: 'border-2 border-green-400 text-green-600 bg-green-50 cursor-pointer hover:bg-green-100',
  white: 'border border-slate-200 text-slate-400'
}

export function SimulationConfigPanel({
  repValues,
  seedValues,
  selectedRep,
  selectedSeed,
  mdmConfig,
  getBorderState,
  onRepChange,
  onSeedChange,
  onStepChange
}: SimulationConfigPanelProps) {
  // 格式化显示值
  const formatRep = (v: number): string => {
    if (v >= 1000) return `${v / 1000}k`
    return String(v)
  }

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <FlaskConical className="text-purple-600" size={20} />
        <h3 className="text-lg font-bold text-slate-800">仿真与计算设置</h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 蒙特卡洛仿真 */}
        <div className="bg-purple-50 rounded-xl p-4 border border-purple-200">
          <h4 className="text-sm font-bold text-purple-800 mb-3">蒙特卡洛仿真</h4>
          <div className="space-y-3 text-sm">
            {/* 重复次数 */}
            <div className="flex justify-between items-center">
              <span className="text-slate-600">每组重复次数</span>
              <div className="flex flex-wrap gap-1 justify-end">
                {repValues.map(rep => {
                  const state = getBorderState('rep', rep)
                  const isSelected = state === 'red'
                  const isClickable = state === 'green' || isSelected

                  return (
                    <span
                      key={rep}
                      onClick={() => isClickable && onRepChange(rep)}
                      className={cn(
                        "px-1.5 py-0.5 rounded text-xs font-mono font-bold transition-all bg-white",
                        BORDER_STYLES[state],
                        isClickable && "cursor-pointer"
                      )}
                      style={isSelected ? { borderColor: '#f87171' } : {}}
                    >
                      {formatRep(rep)}
                    </span>
                  )
                })}
              </div>
            </div>

            {/* 随机种子 */}
            <div className="flex justify-between items-center">
              <span className="text-slate-600">随机种子</span>
              <div className="flex flex-wrap gap-1 justify-end">
                {seedValues.map(seed => {
                  const state = getBorderState('seed', seed)
                  const isSelected = state === 'red'
                  const isClickable = state === 'green' || isSelected

                  return (
                    <span
                      key={seed}
                      onClick={() => isClickable && onSeedChange(seed)}
                      className={cn(
                        "px-1.5 py-0.5 rounded text-xs font-mono font-bold transition-all bg-white",
                        BORDER_STYLES[state],
                        isClickable && "cursor-pointer"
                      )}
                      style={isSelected ? { borderColor: '#f87171' } : {}}
                    >
                      {seed}
                    </span>
                  )
                })}
              </div>
            </div>
          </div>
        </div>

        {/* 计算设置 (MDM特有) */}
        {mdmConfig && (
          <div className="bg-blue-50 rounded-xl p-4 border border-blue-200">
            <div className="flex items-center gap-2 mb-3">
              <Settings className="text-blue-600" size={16} />
              <h4 className="text-sm font-bold text-blue-800">MDM 算法参数</h4>
            </div>
            <div className="space-y-3 text-sm">
              {/* 计算步长 */}
              <div className="flex justify-between items-center">
                <span className="text-slate-600">梯度计算步数</span>
                <div className="flex flex-wrap gap-1 justify-end">
                  {mdmConfig.stepValues.map(step => {
                    const state = getBorderState('step', step)
                    const isSelected = state === 'red'
                    const isClickable = state === 'green' || isSelected

                    return (
                      <span
                        key={step}
                        onClick={() => isClickable && onStepChange?.(step)}
                        className={cn(
                          "px-1.5 py-0.5 rounded text-xs font-mono font-bold transition-all bg-white",
                          BORDER_STYLES[state],
                          isClickable && "cursor-pointer"
                        )}
                        style={isSelected ? { borderColor: '#f87171' } : {}}
                      >
                        {step}
                      </span>
                    )
                  })}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * 静态展示版仿真配置面板（用于无可选配置的情况）
 */
export function StaticSimulationPanel({
  rep,
  seed,
  step
}: {
  rep: number
  seed: number
  step?: number
}) {
  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <FlaskConical className="text-purple-600" size={20} />
        <h3 className="text-lg font-bold text-slate-800">仿真与计算设置</h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-purple-50 rounded-xl p-4 border border-purple-200">
          <h4 className="text-sm font-bold text-purple-800 mb-3">蒙特卡洛仿真</h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-600">每组重复次数</span>
              <span className="font-mono font-bold text-purple-700">{rep.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-600">随机种子</span>
              <span className="font-mono font-bold text-purple-700">{seed}</span>
            </div>
          </div>
        </div>

        {step !== undefined && (
          <div className="bg-blue-50 rounded-xl p-4 border border-blue-200">
            <h4 className="text-sm font-bold text-blue-800 mb-3">MDM 算法参数</h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-600">梯度计算步数</span>
                <span className="font-mono font-bold text-blue-700">{step}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
