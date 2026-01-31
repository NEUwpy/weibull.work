"use client"

import React, { useState, useEffect } from 'react'
import katex from 'katex'
import { ChevronDown, ChevronRight, Code, ArrowDown, Repeat, GitBranch, FileCode, Database } from 'lucide-react'
import { cn } from '@/lib/utils'

// LaTeX Renderer
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
    return <span className="text-red-500 font-mono text-xs">LaTeX Error</span>
  }
}

interface FlowStep {
  id: number
  name: string
  description: string
  formula: string
  detailFormula?: string
  detailFormula2?: string
  inputs: Record<string, string>
  outputs: Record<string, string>
  code?: string
  isLoop?: boolean
  loopCount?: number
  method?: string
  note?: string
}

interface MethodFlow {
  methodId: string
  methodName: string
  description: string
  steps: FlowStep[]
}

interface VariableFlowViewerProps {
  methodId: string
}

export default function VariableFlowViewer({ methodId }: VariableFlowViewerProps) {
  const [flowData, setFlowData] = useState<MethodFlow | null>(null)
  const [loading, setLoading] = useState(true)
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set([1]))

  useEffect(() => {
    async function loadFlowData() {
      try {
        const response = await await fetch(`/api/method-flow/${methodId}`)
        if (response.ok) {
          const data = await response.json()
          setFlowData(data)
          // Auto-expand first step
          setExpandedSteps(new Set([1]))
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

  const toggleStep = (stepId: number) => {
    setExpandedSteps(prev => {
      const newSet = new Set(prev)
      if (newSet.has(stepId)) {
        newSet.delete(stepId)
      } else {
        newSet.add(stepId)
      }
      return newSet
    })
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
        <p className="text-sm mt-2">该方法尚未添加变量流转可视化</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-emerald-50 to-teal-50 rounded-2xl p-6 border border-emerald-200">
        <div className="flex items-center gap-3 mb-3">
          <GitBranch className="text-emerald-600" size={24} />
          <h2 className="text-2xl font-black text-slate-900">{flowData.methodName}</h2>
        </div>
        <p className="text-slate-600">{flowData.description}</p>
        <div className="mt-4 flex items-center gap-4 text-sm text-slate-500">
          <span className="flex items-center gap-1">
            <Database size={16} />
            共 {flowData.steps.length} 个计算步骤
          </span>
        </div>
      </div>

      {/* Flow Steps */}
      <div className="space-y-4">
        {flowData.steps.map((step, index) => {
          const isExpanded = expandedSteps.has(step.id)
          const isLast = index === flowData.steps.length - 1

          return (
            <div key={step.id} className="relative">
              {/* Step Card */}
              <div
                className={cn(
                  "bg-white rounded-2xl border-2 transition-all cursor-pointer overflow-hidden",
                  isExpanded ? "border-emerald-300 shadow-lg" : "border-slate-200 hover:border-emerald-200"
                )}
                onClick={() => toggleStep(step.id)}
              >
                {/* Step Header */}
                <div className="flex items-center gap-4 p-5">
                  {/* Step Number */}
                  <div className={cn(
                    "flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center font-black text-lg",
                    step.isLoop
                      ? "bg-amber-100 text-amber-700 border-2 border-amber-300"
                      : "bg-emerald-100 text-emerald-700 border-2 border-emerald-300"
                  )}>
                    {step.id}
                  </div>

                  {/* Step Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-bold text-slate-900 text-lg">{step.name}</h3>
                      {step.isLoop && (
                        <span className="flex items-center gap-1 px-2 py-0.5 bg-amber-100 text-amber-700 text-xs font-bold rounded-full">
                          <Repeat size={12} />
                          循环 {step.loopCount || 'N'} 次
                        </span>
                      )}
                    </div>
                    <p className="text-slate-500 text-sm line-clamp-1">{step.description}</p>
                  </div>

                  {/* Expand Icon */}
                  <div className="flex-shrink-0">
                    {isExpanded ? <ChevronDown className="text-slate-400" size={20} /> : <ChevronRight className="text-slate-400" size={20} />}
                  </div>
                </div>

                {/* Expanded Content */}
                {isExpanded && (
                  <div className="border-t border-slate-100 p-6 space-y-6" onClick={e => e.stopPropagation()}>
                    {/* Formula Section */}
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-1 rounded border border-emerald-200">核心公式</span>
                      </div>
                      <div className="bg-slate-900 rounded-xl p-4 overflow-x-auto">
                        <LatexRenderer math={step.formula} block />
                      </div>
                      {step.detailFormula && (
                        <div className="mt-3 bg-slate-50 rounded-xl p-4 overflow-x-auto border border-slate-200">
                          <div className="text-xs font-bold text-slate-500 mb-2">详细公式</div>
                          <LatexRenderer math={step.detailFormula} block />
                          {step.detailFormula2 && <LatexRenderer math={step.detailFormula2} block />}
                        </div>
                      )}
                    </div>

                    {/* Input/Output Section */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Inputs */}
                      <div className="bg-blue-50 rounded-xl p-4 border border-blue-200">
                        <div className="flex items-center gap-2 mb-3">
                          <Database size={16} className="text-blue-600" />
                          <span className="text-sm font-bold text-blue-900">输入变量</span>
                        </div>
                        <div className="space-y-2">
                          {Object.entries(step.inputs).map(([key, value]) => (
                            <div key={key} className="flex items-start gap-2">
                              <code className="flex-shrink-0 px-2 py-0.5 bg-blue-200 text-blue-800 text-xs font-mono rounded">
                                {key}
                              </code>
                              <span className="text-sm text-slate-600">{value}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Outputs */}
                      <div className="bg-green-50 rounded-xl p-4 border border-green-200">
                        <div className="flex items-center gap-2 mb-3">
                          <Database size={16} className="text-green-600" />
                          <span className="text-sm font-bold text-green-900">输出变量</span>
                        </div>
                        <div className="space-y-2">
                          {Object.entries(step.outputs).map(([key, value]) => (
                            <div key={key} className="flex items-start gap-2">
                              <code className="flex-shrink-0 px-2 py-0.5 bg-green-200 text-green-800 text-xs font-mono rounded">
                                {key}
                              </code>
                              <span className="text-sm text-slate-600">{value}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Code Snippet */}
                    {step.code && (
                      <div className="bg-slate-900 rounded-xl p-4 border border-slate-700">
                        <div className="flex items-center gap-2 mb-3">
                          <Code size={16} className="text-emerald-400" />
                          <span className="text-xs font-bold text-slate-400">PYTHON 代码</span>
                        </div>
                        <pre className="text-emerald-300 text-sm font-mono overflow-x-auto">
                          <code>{step.code}</code>
                        </pre>
                      </div>
                    )}

                    {/* Method */}
                    {step.method && (
                      <div className="bg-amber-50 rounded-xl p-4 border border-amber-200">
                        <div className="flex items-center gap-2 mb-2">
                          <GitBranch size={16} className="text-amber-600" />
                          <span className="text-sm font-bold text-amber-900">计算方法</span>
                        </div>
                        <p className="text-slate-700">{step.method}</p>
                      </div>
                    )}

                    {/* Note */}
                    {step.note && (
                      <div className="bg-purple-50 rounded-xl p-4 border border-purple-200">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-lg">💡</span>
                          <span className="text-sm font-bold text-purple-900">说明</span>
                        </div>
                        <p className="text-slate-700">{step.note}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Arrow to next step */}
              {!isLast && (
                <div className="flex justify-center py-2">
                  <div className="flex flex-col items-center text-slate-400">
                    <ArrowDown size={24} className="animate-bounce" />
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
