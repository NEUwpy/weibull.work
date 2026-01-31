"use client"

import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Play, Pause, SkipBack, SkipForward, FastForward, Code, Database, ChevronRight, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

// ========================================
// 类型定义
// ========================================

export interface CodeStep {
  line: number              // 代码行号
  code: string              // 代码内容
  description?: string      // 步骤描述
  formula?: string          // 相关公式（LaTeX）
  highlights?: number[]     // 需要高亮的变量索引
}

export interface VariableChange {
  name: string              // 变量名
  value: string | number    // 变量值
  type: 'input' | 'output' | 'intermediate' | 'final'
  highlighted?: boolean     // 是否高亮显示
}

export interface AnimationStep {
  id: number
  title: string             // 步骤标题
  description?: string      // 步骤描述
  codeStep: CodeStep        // 代码步骤
  variables: VariableChange[] // 变量变化
  isLoop?: boolean          // 是否是循环步骤
  loopCount?: number        // 循环次数
  formula?: string          // 公式
}

export interface AlgorithmAnimation {
  methodId: string
  methodName: string
  description: string
  code: string[]            // 完整代码（按行分割）
  steps: AnimationStep[]    // 动画步骤
}

// ========================================
// 组件
// ========================================

interface AlgorithmVisualizerProps {
  animation: AlgorithmAnimation
  className?: string
}

export default function AlgorithmVisualizer({ animation, className }: AlgorithmVisualizerProps) {
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [speed, setSpeed] = useState(1) // 1x, 2x, 4x
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['code', 'variables']))

  const currentStep = animation.steps[currentStepIndex]
  const isLastStep = currentStepIndex === animation.steps.length - 1
  const isFirstStep = currentStepIndex === 0

  // 自动播放
  useEffect(() => {
    if (!isPlaying || isLastStep) return

    const delay = 2000 / speed // 根据速度调整延迟
    const timer = setTimeout(() => {
      setCurrentStepIndex(prev => Math.min(prev + 1, animation.steps.length - 1))
    }, delay)

    return () => clearTimeout(timer)
  }, [isPlaying, currentStepIndex, isLastStep, speed, animation.steps.length])

  const handleNext = () => {
    if (!isLastStep) {
      setCurrentStepIndex(prev => prev + 1)
    }
  }

  const handlePrev = () => {
    if (!isFirstStep) {
      setCurrentStepIndex(prev => prev - 1)
    }
  }

  const handleReset = () => {
    setCurrentStepIndex(0)
    setIsPlaying(false)
  }

  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const newSet = new Set(prev)
      if (newSet.has(section)) {
        newSet.delete(section)
      } else {
        newSet.add(section)
      }
      return newSet
    })
  }

  return (
    <div className={cn("bg-slate-900 rounded-3xl overflow-hidden shadow-2xl", className)}>
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-900 to-indigo-900 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-black text-white">{animation.methodName}</h2>
            <p className="text-purple-200 text-sm mt-1">{animation.description}</p>
          </div>
          <div className="flex items-center gap-2 text-purple-200 text-sm">
            <Code size={16} />
            <span>步骤 {currentStepIndex + 1} / {animation.steps.length}</span>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mt-4 h-2 bg-slate-800 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-purple-500 to-pink-500"
            initial={false}
            animate={{ width: `${((currentStepIndex + 1) / animation.steps.length) * 100}%` }}
            transition={{ duration: 0.3 }}
          />
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-0">
        {/* Left: Code Panel */}
        <Section
          title="代码执行"
          icon={<Code size={18} />}
          expanded={expandedSections.has('code')}
          onToggle={() => toggleSection('code')}
          className="border-r border-slate-700"
        >
          <CodePanel
            code={animation.code}
            currentStep={currentStep}
            currentLine={currentStep.codeStep.line}
          />
        </Section>

        {/* Right: Variables Panel */}
        <Section
          title="变量状态"
          icon={<Database size={18} />}
          expanded={expandedSections.has('variables')}
          onToggle={() => toggleSection('variables')}
        >
          <VariablesPanel variables={currentStep.variables} />
        </Section>
      </div>

      {/* Formula Section (if exists) */}
      {currentStep.formula && (
        <div className="px-6 py-4 bg-slate-800/50 border-t border-slate-700">
          <div className="flex items-center gap-2 mb-2 text-purple-400 text-sm font-bold">
            <span>∑</span>
            <span>当前公式</span>
          </div>
          <LatexRenderer math={currentStep.formula} />
        </div>
      )}

      {/* Step Description */}
      {currentStep.description && (
        <div className="px-6 py-3 bg-purple-900/20 border-t border-purple-500/20">
          <AnimatePresence mode="wait">
            <motion.p
              key={currentStep.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="text-purple-200 text-sm"
            >
              {currentStep.description}
            </motion.p>
          </AnimatePresence>
        </div>
      )}

      {/* Controls */}
      <div className="bg-slate-800 px-6 py-4 border-t border-slate-700">
        <div className="flex items-center justify-between">
          {/* Playback Controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleReset}
              className="p-2 text-slate-400 hover:text-white transition-colors"
              title="重置"
            >
              <SkipBack size={20} />
            </button>
            <button
              onClick={handlePrev}
              disabled={isFirstStep}
              className={cn(
                "p-2 rounded-lg transition-colors",
                isFirstStep ? "text-slate-600 cursor-not-allowed" : "text-slate-400 hover:text-white hover:bg-slate-700"
              )}
              title="上一步"
            >
              <ChevronRight size={20} className="rotate-180" />
            </button>
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              className={cn(
                "p-3 rounded-xl transition-all",
                isPlaying
                  ? "bg-purple-600 text-white hover:bg-purple-700"
                  : "bg-purple-600 text-white hover:bg-purple-700"
              )}
              title={isPlaying ? "暂停" : "播放"}
            >
              {isPlaying ? <Pause size={24} /> : <Play size={24} className="ml-1" />}
            </button>
            <button
              onClick={handleNext}
              disabled={isLastStep}
              className={cn(
                "p-2 rounded-lg transition-colors",
                isLastStep ? "text-slate-600 cursor-not-allowed" : "text-slate-400 hover:text-white hover:bg-slate-700"
              )}
              title="下一步"
            >
              <ChevronRight size={20} />
            </button>
          </div>

          {/* Speed Control */}
          <div className="flex items-center gap-2">
            <span className="text-slate-400 text-sm">速度:</span>
            {[1, 2, 4].map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                className={cn(
                  "px-3 py-1 rounded-lg text-sm font-bold transition-colors",
                  speed === s
                    ? "bg-purple-600 text-white"
                    : "text-slate-400 hover:text-white hover:bg-slate-700"
                )}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ========================================
// 子组件
// ========================================

interface SectionProps {
  title: string
  icon: React.ReactNode
  expanded: boolean
  onToggle: () => void
  children: React.ReactNode
  className?: string
}

function Section({ title, icon, expanded, onToggle, children, className }: SectionProps) {
  return (
    <div className={cn("flex flex-col", className)}>
      {/* Section Header */}
      <div
        className="flex items-center justify-between px-6 py-3 bg-slate-800/50 cursor-pointer hover:bg-slate-800 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center gap-2 text-slate-300">
          {icon}
          <span className="font-bold">{title}</span>
        </div>
        {expanded ? <ChevronDown size={18} className="text-slate-400" /> : <ChevronRight size={18} className="text-slate-400" />}
      </div>

      {/* Section Content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="p-6">
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

interface CodePanelProps {
  code: string[]
  currentStep: AnimationStep
  currentLine: number
}

function CodePanel({ code, currentStep, currentLine }: CodePanelProps) {
  return (
    <div className="space-y-2">
      {code.map((line, index) => {
        const lineNumber = index + 1
        const isCurrentLine = lineNumber === currentLine
        const isHighlightedLine = currentStep.codeStep.highlights?.includes(lineNumber)

        return (
          <motion.div
            key={lineNumber}
            initial={false}
            animate={{
              backgroundColor: isCurrentLine ? 'rgba(168, 85, 247, 0.2)' : isHighlightedLine ? 'rgba(168, 85, 247, 0.1)' : 'transparent',
              x: isCurrentLine ? [0, -5, 0] : 0,
            }}
            transition={{ duration: 0.3 }}
            className={cn(
              "flex items-start gap-3 px-3 py-2 rounded-lg font-mono text-sm",
              isCurrentLine && "border-l-4 border-purple-500"
            )}
          >
            <span className={cn(
              "text-slate-600 select-none flex-shrink-0",
              isCurrentLine && "text-purple-400"
            )}>
              {lineNumber.toString().padStart(2, '0')}
            </span>
            <span className={cn(
              "flex-1",
              isCurrentLine ? "text-white" : "text-slate-300"
            )}>
              {line || <span className="text-slate-600">&nbsp;</span>}
            </span>
            {isCurrentLine && (
              <motion.span
                initial={{ opacity: 0, scale: 0 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex-shrink-0 w-2 h-2 rounded-full bg-purple-500 mt-1.5"
              />
            )}
          </motion.div>
        )
      })}
    </div>
  )
}

interface VariablesPanelProps {
  variables: VariableChange[]
}

function VariablesPanel({ variables }: VariablesPanelProps) {
  return (
    <div className="space-y-3">
      {variables.map((variable, index) => {
        const typeColors = {
          input: 'bg-blue-900/30 border-blue-500/50 text-blue-300',
          output: 'bg-green-900/30 border-green-500/50 text-green-300',
          intermediate: 'bg-yellow-900/30 border-yellow-500/50 text-yellow-300',
          final: 'bg-purple-900/30 border-purple-500/50 text-purple-300',
        }

        return (
          <motion.div
            key={variable.name}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1 }}
            className={cn(
              "p-3 rounded-lg border",
              typeColors[variable.type],
              variable.highlighted && "ring-2 ring-white/50"
            )}
          >
            <div className="flex items-center justify-between">
              <code className="font-bold text-sm">{variable.name}</code>
              <span className="font-mono text-sm">{typeof variable.value === 'number'
                ? (Number.isInteger(variable.value) ? variable.value : variable.value.toFixed(4))
                : variable.value}</span>
            </div>
          </motion.div>
        )
      })}

      {variables.length === 0 && (
        <div className="text-center text-slate-500 py-8">
          暂无变量变化
        </div>
      )}
    </div>
  )
}

// ========================================
// 工具组件
// ========================================

function LatexRenderer({ math }: { math: string }) {
  // 简单的 LaTeX 渲染（生产环境应使用 KaTeX）
  return (
    <div className="bg-slate-900 rounded-lg p-4 overflow-x-auto">
      <pre className="text-purple-300 text-sm font-mono whitespace-pre-wrap">
        {math}
      </pre>
    </div>
  )
}
