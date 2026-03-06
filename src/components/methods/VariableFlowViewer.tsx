"use client"

import React, { useState, useEffect, useRef } from 'react'
import katex from 'katex'
import { ChevronLeft, ChevronRight, SkipBack, GitBranch, FileCode, Database, Code, ArrowRight } from 'lucide-react'
import { cn } from '@/lib/utils'

// ========================================
// 类型定义
// ========================================

interface Variable {
  symbol: string    // 数学符号
  meaning: string   // 含义说明
  code: string      // 代码变量名
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
  const codeContainerRef = useRef<HTMLDivElement>(null)

  // 当步骤改变时，滚动到对应的代码行
  useEffect(() => {
    if (!flowData || !codeContainerRef.current) return

    const currentStep = flowData.steps[currentStepIndex]
    if (!currentStep || currentStep.codeLines.length === 0) return

    // 找到第一个非元数据注释的代码行
    const codeLines = currentStep.codeLines.filter(lineIndex => {
      const line = flowData.code[lineIndex]
      return line && !/^\s*#\s*@/.test(line)
    })

    if (codeLines.length === 0) return

    // 滚动到第一个代码行
    const targetLine = codeLines[0]
    const lineElement = codeContainerRef.current.querySelector(`[data-line="${targetLine}"]`)

    if (lineElement) {
      lineElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [currentStepIndex, flowData])

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
        <div
          ref={codeContainerRef}
          className="lg:col-span-6 border-r border-slate-200 bg-slate-900 max-h-[600px] overflow-y-auto"
        >
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
              // 检测是否是元数据注释行（# @step:, # @formula: 等）
              const isMetaComment = /^\s*#\s*@/.test(line)
              // 只有非元数据注释行才高亮
              const shouldHighlight = isCurrentLine && !isMetaComment

              return (
                <div
                  key={index}
                  data-line={index}
                  className={cn(
                    "flex items-start gap-3 py-1 px-2 rounded-lg transition-colors",
                    shouldHighlight && "bg-emerald-900/30 border-l-2 border-emerald-500 -ml-2 pl-4"
                  )}
                >
                  <span className={cn(
                    "text-slate-600 select-none flex-shrink-0 text-xs w-6 text-right",
                    shouldHighlight && "text-emerald-400"
                  )}>
                    {lineNumber}
                  </span>
                  <span className={cn(
                    "flex-1 whitespace-pre",
                    shouldHighlight ? "text-white" : isMetaComment ? "text-slate-600" : "text-slate-400"
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
              <div className="bg-slate-900 rounded-xl p-3 overflow-x-auto mb-2 text-white">
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

            {/* 3. Inputs & Outputs - Three Columns (3:4:3) */}
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
                        <div className="grid grid-cols-10 divide-x divide-blue-200">
                          <div className="col-span-3 p-2 bg-blue-50 flex items-center" style={{ paddingLeft: '18px' }}>
                            <LatexRenderer math={input.symbol} />
                          </div>
                          <div className="col-span-4 p-2 flex items-center">
                            <div className="text-xs text-slate-700">{input.meaning}</div>
                          </div>
                          <div className="col-span-3 p-2 flex items-center">
                            <div className="text-xs text-slate-700 font-mono">{input.code}</div>
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
                        <div className="grid grid-cols-10 divide-x divide-green-200">
                          <div className="col-span-3 p-2 bg-green-50 flex items-center" style={{ paddingLeft: '18px' }}>
                            <LatexRenderer math={output.symbol} />
                          </div>
                          <div className="col-span-4 p-2 flex items-center">
                            <div className="text-xs text-slate-700">{output.meaning}</div>
                          </div>
                          <div className="col-span-3 p-2 flex items-center">
                            <div className="text-xs text-slate-700 font-mono">{output.code}</div>
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
    </div>
  )
}
