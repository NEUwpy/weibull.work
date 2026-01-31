"use client"

import React, { useState, useEffect } from 'react'
import katex from 'katex'
import { ChevronLeft, ChevronRight, SkipBack, GitBranch, FileCode, Database, Code, ArrowRight } from 'lucide-react'
import { cn } from '@/lib/utils'

// ========================================
// 类型定义
// ========================================

interface Variable {
  symbol: string
  math: string
  code: string
  value?: string | number
}

interface Formula {
  expression: string
  symbols: Array<{
    symbol: string
    meaning: string
  }>
  explanation: string
}

interface FlowStep {
  id: number
  name: string
  description: string
  codeLines: number[]
  inputs: Variable[]
  formula: Formula
  outputs: Variable[]
  otherVariables: Variable[]
  isLoop?: boolean
  loopCount?: string
}

interface MethodFlow {
  methodId: string
  methodName: string
  description: string
  code: string[]
  steps: FlowStep[]
}

interface VariableFlowViewerProps {
  methodId: string
}

// ========================================
// LaTeX 渲染器
// ========================================

const LatexRenderer = ({ math, block = false }: { math: string, block?: boolean }) => {
  try {
    const html = katex.renderToString(math, {
      throwOnError: false,
      displayMode: block,
      trust: true,
      strict: false
    })
    return <div className={cn("overflow-x-auto", block ? "py-2" : "inline")} dangerouslySetInnerHTML={{ __html: html }} />
  } catch (e) {
    return <span className="text-red-400 font-mono text-xs">LaTeX Error</span>
  }
}

// ========================================
// 主组件
// ========================================

export default function VariableFlowViewer({ methodId }: VariableFlowViewerProps) {
  const [flowData, setFlowData] = useState<MethodFlow | null>(null)
  const [loading, setLoading] = useState(true)
  const [currentStepIndex, setCurrentStepIndex] = useState(0)

  useEffect(() => {
    async function loadFlowData() {
      try {
        const response = await fetch(`/api/method-flow/${methodId}`)
        if (response.ok) {
          const data = await response.json()
          setFlowData(data)
        } else {
          console.error('Failed to load flow data')
        }
      } catch (e) {
        console.error('Error loading flow data:', e)
      } finally {
        setLoading(false)
      }
    }
    loadFlowData()
  }, [methodId])

  const handlePrev = () => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex(prev => prev - 1)
    }
  }

  const handleNext = () => {
    if (flowData && currentStepIndex < flowData.steps.length - 1) {
      setCurrentStepIndex(prev => prev + 1)
    }
  }

  const handleReset = () => {
    setCurrentStepIndex(0)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-slate-200 border-t-emerald-500"></div>
        <span className="ml-4 text-slate-600 font-bold">加载程序流程...</span>
      </div>
    )
  }

  if (!flowData) {
    return (
      <div className="text-center py-20 text-slate-400 bg-white rounded-3xl border border-slate-200">
        <FileCode className="mx-auto mb-4" size={48} />
        <p className="font-bold">暂无程序流程数据</p>
        <p className="text-sm mt-2">该方法尚未添加算法透明化视图</p>
      </div>
    )
  }

  const currentStep = flowData.steps[currentStepIndex]
  const isLastStep = currentStepIndex === flowData.steps.length - 1
  const isFirstStep = currentStepIndex === 0
  const totalSteps = flowData.steps.length

  return (
    <div className="bg-slate-50 rounded-3xl overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-emerald-600 to-teal-600 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <GitBranch className="text-white" size={24} />
              <h2 className="text-xl font-black text-white">{flowData.methodName}</h2>
            </div>
            <p className="text-emerald-100 text-sm mt-1 ml-9">{flowData.description}</p>
          </div>
          <div className="text-right">
            <div className="text-emerald-100 text-sm">步骤进度</div>
            <div className="text-white font-bold text-lg">{currentStepIndex + 1} / {totalSteps}</div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mt-4 h-2 bg-emerald-900/30 rounded-full overflow-hidden">
          <div
            className="h-full bg-white transition-all duration-300"
            style={{ width: `${((currentStepIndex + 1) / totalSteps) * 100}%` }}
          />
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white px-6 py-3 border-b border-slate-200 flex items-center justify-between">
        <div className="text-sm text-slate-500">
          <span className="font-medium">当前：</span>
          <span className="font-bold text-slate-700">{currentStep.name}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleReset}
            className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
            title="重置"
          >
            <SkipBack size={18} />
          </button>
          <button
            onClick={handlePrev}
            disabled={isFirstStep}
            className={cn(
              "flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-bold transition-all",
              isFirstStep
                ? "text-slate-300 cursor-not-allowed"
                : "text-slate-600 hover:text-emerald-600 hover:bg-emerald-50"
            )}
            title="上一步"
          >
            <ChevronLeft size={16} />
            上一步
          </button>
          <button
            onClick={handleNext}
            disabled={isLastStep}
            className={cn(
              "flex items-center gap-1 px-4 py-1.5 rounded-lg text-sm font-bold transition-all",
              isLastStep
                ? "text-slate-300 cursor-not-allowed"
                : "bg-emerald-600 text-white hover:bg-emerald-700"
            )}
            title="下一步"
          >
            下一步
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {/* Three Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-0">
        {/* Left Column: Flow Steps */}
        <div className="lg:col-span-3 border-r border-slate-200 bg-white max-h-[600px] overflow-y-auto">
          <div className="sticky top-0 bg-white border-b border-slate-100 px-4 py-3 z-10">
            <div className="flex items-center gap-2 text-sm font-bold text-slate-700">
              <GitBranch size={16} className="text-emerald-600" />
              计算流程
            </div>
          </div>
          <div className="p-3 space-y-2">
            {flowData.steps.map((step, index) => {
              const isCurrent = index === currentStepIndex
              const isPast = index < currentStepIndex

              return (
                <div
                  key={step.id}
                  className={cn(
                    "p-3 rounded-xl border-2 cursor-pointer transition-all",
                    isCurrent
                      ? "border-emerald-500 bg-emerald-50 shadow-md"
                      : isPast
                      ? "border-emerald-200 bg-emerald-50/50 hover:bg-emerald-50"
                      : "border-slate-200 hover:border-slate-300"
                  )}
                  onClick={() => setCurrentStepIndex(index)}
                >
                  <div className="flex items-start gap-2">
                    <div className={cn(
                      "flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold",
                      isCurrent
                        ? "bg-emerald-600 text-white"
                        : isPast
                        ? "bg-emerald-400 text-white"
                        : "bg-slate-200 text-slate-500"
                    )}>
                      {step.id}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className={cn(
                        "font-bold text-sm truncate",
                        isCurrent ? "text-emerald-900" : "text-slate-700"
                      )}>
                        {step.name}
                      </div>
                      {step.isLoop && (
                        <span className="inline-flex items-center gap-1 text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded mt-1">
                          循环 {step.loopCount}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Middle Column: Code */}
        <div className="lg:col-span-6 border-r border-slate-200 bg-slate-900 max-h-[600px] overflow-y-auto">
          <div className="sticky top-0 bg-slate-800 border-b border-slate-700 px-4 py-3 z-10 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-bold text-slate-300">
              <Code size={16} className="text-emerald-400" />
              Python 代码
            </div>
            <div className="text-xs text-slate-500">
              {currentStep.codeLines.length > 0 ? `行 ${currentStep.codeLines[0] + 1}` : '-'}
            </div>
          </div>
          <div className="p-4 font-mono text-sm">
            {flowData.code.map((line, index) => {
              const lineNumber = index + 1
              const isCurrentLine = currentStep.codeLines.includes(index)

              return (
                <div
                  key={index}
                  className={cn(
                    "flex items-start gap-3 py-1 px-2 rounded-lg",
                    isCurrentLine && "bg-emerald-900/30 border-l-2 border-emerald-500 -ml-2 pl-4"
                  )}
                >
                  <span className={cn(
                    "text-slate-600 select-none flex-shrink-0 text-xs w-6 text-right",
                    isCurrentLine && "text-emerald-400"
                  )}>
                    {lineNumber}
                  </span>
                  <span className={cn(
                    "flex-1 whitespace-pre",
                    isCurrentLine ? "text-white" : "text-slate-400"
                  )}>
                    {line || <span className="text-slate-700">&nbsp;</span>}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Right Column: Current Step Details */}
        <div className="lg:col-span-3 bg-white max-h-[600px] overflow-y-auto">
          <div className="sticky top-0 bg-white border-b border-slate-100 px-4 py-3 z-10">
            <div className="flex items-center gap-2 text-sm font-bold text-slate-700">
              <Database size={16} className="text-emerald-600" />
              步骤详情
            </div>
          </div>
          <div className="p-4 space-y-4">
            {/* 1. Step Description */}
            <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
              <h4 className="text-sm font-bold text-slate-900 mb-2">{currentStep.name}</h4>
              <p className="text-sm text-slate-600 leading-relaxed">{currentStep.description}</p>
            </div>

            {/* 2. Formula */}
            <div>
              <h5 className="text-xs font-bold text-purple-600 uppercase mb-2 flex items-center gap-1">
                <ArrowRight size={12} />
                公式
              </h5>
              <div className="bg-slate-900 rounded-xl p-3 overflow-x-auto mb-2">
                <LatexRenderer math={currentStep.formula.expression} block />
              </div>

              {/* Symbols Explanation */}
              {currentStep.formula.symbols.length > 0 && (
                <div className="bg-purple-50 rounded-lg p-2 border border-purple-200 mb-2">
                  <div className="text-xs font-bold text-purple-700 mb-2">符号说明</div>
                  <div className="space-y-1">
                    {currentStep.formula.symbols.map((sym, index) => (
                      <div key={index} className="flex items-start gap-2 text-xs">
                        <code className="font-mono bg-purple-200 text-purple-800 px-1.5 py-0.5 rounded whitespace-nowrap">
                          {sym.symbol}
                        </code>
                        <span className="text-slate-700 leading-tight">{sym.meaning}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Formula Explanation */}
              <div className="bg-slate-50 rounded-lg p-2 border border-slate-200">
                <div className="text-xs text-slate-600 leading-relaxed">{currentStep.formula.explanation}</div>
              </div>
            </div>

            {/* 3. Inputs & Outputs - Two Columns */}
            <div className="space-y-3">
              {/* Inputs */}
              {currentStep.inputs.length > 0 && (
                <div>
                  <h5 className="text-xs font-bold text-blue-600 uppercase mb-2 flex items-center gap-1">
                    <ArrowRight size={12} />
                    输入
                  </h5>
                  <div className="space-y-2">
                    {currentStep.inputs.map((input, index) => (
                      <div key={index} className="border border-blue-200 rounded-lg overflow-hidden">
                        {/* Symbol Header */}
                        <div className="bg-blue-100 px-3 py-1.5 flex items-center justify-between">
                          <code className="font-bold text-sm text-blue-800">{input.symbol}</code>
                          {input.value !== undefined && (
                            <span className="font-mono text-xs bg-blue-200 text-blue-800 px-2 py-0.5 rounded">
                              {typeof input.value === 'number'
                                ? (Number.isInteger(input.value) ? input.value : input.value.toFixed(4))
                                : input.value}
                            </span>
                          )}
                        </div>
                        {/* Two Column Content */}
                        <div className="grid grid-cols-2 divide-x divide-blue-200">
                          <div className="p-2">
                            <div className="text-xs text-blue-600 font-bold mb-1">数学变量</div>
                            <div className="text-xs text-slate-700">{input.math}</div>
                          </div>
                          <div className="p-2">
                            <div className="text-xs text-blue-600 font-bold mb-1">代码变量</div>
                            <div className="text-xs text-slate-700 font-mono bg-blue-50 px-1.5 py-1 rounded">{input.code}</div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Outputs */}
              {currentStep.outputs.length > 0 && (
                <div>
                  <h5 className="text-xs font-bold text-green-600 uppercase mb-2 flex items-center gap-1">
                    <ArrowRight size={12} />
                    输出
                  </h5>
                  <div className="space-y-2">
                    {currentStep.outputs.map((output, index) => (
                      <div key={index} className="border border-green-200 rounded-lg overflow-hidden">
                        {/* Symbol Header */}
                        <div className="bg-green-100 px-3 py-1.5 flex items-center justify-between">
                          <code className="font-bold text-sm text-green-800">{output.symbol}</code>
                          {output.value !== undefined && (
                            <span className="font-mono text-xs bg-green-200 text-green-800 px-2 py-0.5 rounded">
                              {typeof output.value === 'number'
                                ? (Number.isInteger(output.value) ? output.value : output.value.toFixed(4))
                                : output.value}
                            </span>
                          )}
                        </div>
                        {/* Two Column Content */}
                        <div className="grid grid-cols-2 divide-x divide-green-200">
                          <div className="p-2">
                            <div className="text-xs text-green-600 font-bold mb-1">数学变量</div>
                            <div className="text-xs text-slate-700">{output.math}</div>
                          </div>
                          <div className="p-2">
                            <div className="text-xs text-green-600 font-bold mb-1">代码变量</div>
                            <div className="text-xs text-slate-700 font-mono bg-green-50 px-1.5 py-1 rounded">{output.code}</div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* 4. Other Variables (按需显示) */}
            {currentStep.otherVariables.length > 0 && (
              <div>
                <h5 className="text-xs font-bold text-amber-600 uppercase mb-2 flex items-center gap-1">
                  <ArrowRight size={12} />
                  其它变量
                </h5>
                <div className="space-y-2">
                  {currentStep.otherVariables.map((variable, index) => (
                    <div key={index} className="border border-amber-200 rounded-lg overflow-hidden">
                      {/* Symbol Header */}
                      <div className="bg-amber-100 px-3 py-1.5 flex items-center justify-between">
                        <code className="font-bold text-xs text-amber-800">{variable.symbol}</code>
                        {variable.value !== undefined && (
                          <span className="font-mono text-xs bg-amber-200 text-amber-800 px-2 py-0.5 rounded">
                            {typeof variable.value === 'number'
                              ? (Number.isInteger(variable.value) ? variable.value : variable.value.toFixed(4))
                              : variable.value}
                          </span>
                        )}
                      </div>
                      {/* Two Column Content */}
                      <div className="grid grid-cols-2 divide-x divide-amber-200">
                        <div className="p-2">
                          <div className="text-xs text-amber-600 font-bold mb-1">数学变量</div>
                          <div className="text-xs text-slate-700">{variable.math}</div>
                        </div>
                        <div className="p-2">
                          <div className="text-xs text-amber-600 font-bold mb-1">代码变量</div>
                          <div className="text-xs text-slate-700 font-mono bg-amber-50 px-1.5 py-1 rounded">{variable.code}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
