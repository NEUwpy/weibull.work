"use client"

import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useMethodFlow } from './useMethodFlow'
import katex from 'katex'
import { AlertCircle, ArrowDown, ChevronLeft, ChevronRight, Code2, FileCode2, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { FlowStep, FlowVariable, MethodFlow } from '@/lib/method-flow'
import { ProcessEquation } from '@/components/shared/charts/ProcessEquation'

function MathText({ math, block = false }: { math: string; block?: boolean }) {
  const html = katex.renderToString(math, { throwOnError: false, displayMode: block, trust: false, strict: false })
  return <span className={cn(block ? 'block max-w-full overflow-x-auto py-3' : 'inline-block align-middle')} dangerouslySetInnerHTML={{ __html: html }} />
}

function Variables({ title, items, values, compact = false }: {
  title: string; items: FlowVariable[]; values?: Record<string, string>; compact?: boolean
}) {
  return <section>
    <h4 className="mb-2 flex items-center gap-2 font-semibold text-slate-800"><ArrowDown size={16} className="text-emerald-600" />{title}</h4>
    <dl className="divide-y divide-slate-200/70">
      {items.map((item, index) => <div key={index} className="grid grid-cols-[minmax(64px,auto)_minmax(0,1fr)] items-start gap-x-3 py-2">
        <dt className="text-emerald-800"><MathText math={item.symbol} /></dt>
        <dd className="min-w-0 text-slate-700">{item.meaning}
          {values?.[item.code] !== undefined && <span className="mt-1 block break-words font-medium tabular-nums text-slate-900">{values[item.code]}</span>}
          {!compact && <code className="mt-1 block break-all font-mono text-sm text-slate-500">{item.code}</code>}</dd>
      </div>)}
    </dl>
  </section>
}

const keywords = new Set(['def', 'class', 'if', 'elif', 'else', 'for', 'in', 'while', 'return', 'try', 'except', 'with', 'as', 'from', 'import', 'None', 'True', 'False', 'and', 'or', 'not', 'is', 'raise', 'break', 'continue', 'lambda', 'global'])
function PythonLine({ line }: { line: string }) {
  return <>{line.split(/("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|#.*$|\b[A-Za-z_]\w*\b|\b\d+(?:\.\d*)?(?:e[+-]?\d+)?\b)/g).map((token, i) =>
    <span key={i} className={token.startsWith('#') ? 'text-slate-400' : /^['"]/.test(token) ? 'text-amber-200' : keywords.has(token) ? 'text-violet-300' : /^\d/.test(token) ? 'text-teal-300' : undefined}>{token}</span>
  )}</>
}

export default function VariableFlowViewer({ methodId, programSteps, focusStep, onStepChange, loadedFlow }: {
  methodId: string; loadedFlow?: MethodFlow; programSteps?: readonly number[]; focusStep?: number
  onStepChange?: (step: number) => void
}) {
  const request = useMethodFlow(loadedFlow ? null : methodId)
  const flow = loadedFlow ?? request.flow

  if (!loadedFlow && request.loading) return <div className="flex items-center justify-center gap-3 py-20 text-slate-600" role="status"><Loader2 className="animate-spin text-emerald-600" size={24} />加载程序流程…</div>
  if (!loadedFlow && request.error) return <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-800" role="alert"><p className="flex items-center gap-2"><AlertCircle size={20} />{request.error}</p><button onClick={request.retry} className="mt-3 rounded-lg px-3 py-2 font-semibold hover:bg-rose-100">重新加载</button></div>
  const steps = flow?.steps.filter(step => !programSteps || programSteps.includes(step.id))
  if (!flow || !steps?.length) return <div className="rounded-2xl bg-slate-50 py-16 text-center text-slate-500"><FileCode2 className="mx-auto mb-3" size={28} />暂无对应源码</div>
  const primary = focusStep ?? programSteps?.[0]
  const activeStep = steps.find(step => step.id === primary) ?? steps[0]
  if (onStepChange) {
    const index = steps.indexOf(activeStep)
    return <section className="min-w-0 overflow-hidden rounded-xl border border-slate-200 bg-white" data-method-flow={methodId}>
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-emerald-50/50 px-4 py-3">
        <h3 className="font-semibold text-slate-800">{index + 1}　{activeStep.name}</h3>
        <div className="flex items-center gap-2">
          <button type="button" aria-label="上一步" disabled={index === 0} onClick={() => onStepChange(steps[index - 1].id)} className="rounded-md p-1.5 text-slate-600 hover:bg-emerald-100 disabled:opacity-30"><ChevronLeft size={19} /></button>
          <span className="text-sm tabular-nums text-slate-500" aria-live="polite">{index + 1} / {steps.length}</span>
          <button type="button" aria-label="下一步" disabled={index === steps.length - 1} onClick={() => onStepChange(steps[index + 1].id)} className="rounded-md p-1.5 text-slate-600 hover:bg-emerald-100 disabled:opacity-30"><ChevronRight size={19} /></button>
        </div>
      </header>
      <ProgramStep key={activeStep.id} flow={flow} step={activeStep} initiallyOpen inline />
    </section>
  }
  return <div className="min-w-0 space-y-3 text-base" data-method-flow={methodId}>
    {steps.map(step => <ProgramStep key={step.id} flow={flow} step={step} initiallyOpen={step.id === activeStep.id} />)}
  </div>
}

function ProgramStep({ flow, step, initiallyOpen, inline = false }: {
  flow: MethodFlow; step: FlowStep; initiallyOpen: boolean; inline?: boolean
}) {
  const body = <div className="grid min-w-0 grid-cols-1 min-[720px]:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
    <FlowStepCode flow={flow} step={step} inline={inline} />
    <div className="min-w-0 p-4 sm:p-5"><FlowStepDetails step={step} /></div>
  </div>
  return inline ? <div data-program-step={step.id}>{body}</div>
    : <details open={initiallyOpen} data-program-step={step.id} className="min-w-0 overflow-hidden rounded-xl border border-slate-200">
      <summary className="cursor-pointer bg-slate-50 px-4 py-3 font-semibold text-slate-800">{step.name}</summary>
      {body}
    </details>
}

export function FlowStepCode({ flow, step, inline = false, continuous = false }: {
  flow: MethodFlow; step: FlowStep; inline?: boolean; continuous?: boolean
}) {
  const codePane = useRef<HTMLDivElement>(null)
  const stepFiles = flow.sources.filter(item => step.sources.some(ref => ref.file === item.path))
  useEffect(() => {
    if (continuous) return
    const pane = codePane.current
    const target = pane?.querySelector<HTMLElement>('[data-primary-source="true"]')
    const focus = () => { if (pane && target) pane.scrollTop = target.offsetTop - 12 }
    const details = pane?.closest('details[data-program-step]')
    focus()
    details?.addEventListener('toggle', focus)
    return () => details?.removeEventListener('toggle', focus)
  }, [continuous, step.id])
  return (
      <section className="min-w-0 overflow-hidden rounded-xl bg-slate-900 text-slate-200" aria-label="真实Python源码">
        <div className="border-b border-slate-700 px-4 py-3">
          <div className="mb-3">
            <h3 className="flex items-center gap-2 font-semibold text-white"><Code2 size={18} />Python 源码</h3>
          </div>
        </div>
        <div ref={codePane} className={cn('relative py-3', !continuous && 'overflow-auto', continuous ? 'overflow-x-auto' : inline ? 'max-h-[520px]' : 'max-h-[45vh]')} tabIndex={0} aria-label="源码内容">
          {step.sources.map((ref, blockIndex) => {
            const file = flow.sources.find(item => item.path === ref.file)!
            const lines = file.lines.map((line, index) => ({ line, index })).filter(({ line, index }) => index >= ref.start && index < ref.end && !/^\s*#\s*@/.test(line) && !/^\s*#\s{2,}\\/.test(line))
            return <div key={blockIndex} data-source-block={blockIndex} data-primary-source={blockIndex === (step.primarySource ?? 0)} className={cn(blockIndex > 0 && 'mt-5 border-t border-slate-700 pt-4', blockIndex === (step.primarySource ?? 0) && 'bg-emerald-400/5')}>
              <p className="mb-2 break-all px-4 font-mono text-sm text-slate-400">{file.path}<span className="ml-2 whitespace-nowrap">L{ref.start + 1}–{ref.end}</span></p>
              <pre className="min-w-max text-sm leading-6"><code>{lines.map(({ line, index }) => <span key={index} data-line={index} className="flex min-h-6 pr-5">
            <span aria-hidden="true" className="sticky left-0 mr-4 w-12 shrink-0 select-none bg-slate-900 pr-2 text-right tabular-nums text-slate-500">{index + 1}</span><span><PythonLine line={line} /></span>
              </span>)}</code></pre>
            </div>
          })}
        </div>
        <details className="border-t border-slate-700 px-4 py-3 text-sm text-slate-400">
          <summary className="cursor-pointer text-slate-300">查看完整源文件</summary>
          {stepFiles.map(file => <div key={file.path}><p className="mt-3 break-all font-mono">{file.path}</p><pre className="mt-2 max-h-96 overflow-auto text-sm leading-6"><code>{file.lines.join('\n')}</code></pre></div>)}
        </details>
        <details className="border-t border-slate-700 px-4 py-3 text-sm text-slate-400">
          <summary className="cursor-pointer text-slate-300">来源与实现说明</summary>
          {flow.implementation && <p className="mt-3 leading-relaxed">{flow.implementation}</p>}
          <p className="mt-3 leading-relaxed">{step.basis}</p>
          {step.notes && <p className="mt-2 leading-relaxed">{step.notes}</p>}
          <dl className="mt-3 space-y-3">{[...flow.sources, ...flow.artifacts].map(item => <div key={item.path}><dt className="break-all font-mono text-slate-300">{item.path}</dt><dd className="mt-1 break-all font-mono">SHA-256 {item.sha256}</dd></div>)}</dl>
        </details>
      </section>

  )
}

export function FlowStepDetails({ step, children, values, compact = false, formulaVariant, equationStart }: {
  step: FlowStep; children?: ReactNode; values?: Record<string, string>; compact?: boolean; formulaVariant?: string; equationStart?: number
}) {
  const mappedSymbols = new Set([...step.inputs, ...step.outputs].map(item => item.symbol))
  const extraSymbols = step.formula.symbols.filter(item => !mappedSymbols.has(item.symbol))
  const equations = (formulaVariant && step.formula.variantEquations?.[formulaVariant]) || step.formula.equations
  const symbols = <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-2 text-sm text-slate-600">{extraSymbols.map((item, index) => <div key={index} className="flex min-w-0 items-center gap-2"><dt><MathText math={item.symbol} /></dt><dd>{item.meaning}</dd></div>)}</dl>
  return (
      <article className="min-w-0 space-y-5" aria-label="本步公式与变量">
        {!compact && <p className="leading-relaxed text-slate-600">{step.description}</p>}
        <section className={cn('min-w-0', compact ? 'space-y-3 border-b border-slate-100 pb-5 text-slate-800' : 'rounded-xl bg-emerald-50/70 px-3 py-2 text-emerald-950')} aria-label="本步公式">
          {compact && equations ? equations.map((expression, index) => <ProcessEquation key={index} expression={expression}
            number={equationStart === undefined ? undefined : equationStart + index} />)
            : <MathText math={(formulaVariant && step.formula.variants?.[formulaVariant]) || step.formula.expression} block />}
        </section>
        {children}
        {!!extraSymbols.length && (compact ? <details><summary className="cursor-pointer text-sm text-slate-600">符号说明</summary>{symbols}</details> : symbols)}
        <Variables title="输入" items={step.inputs} values={values} compact={compact} />
        <Variables title="输出" items={step.outputs} values={values} compact={compact} />
      </article>
  )
}
