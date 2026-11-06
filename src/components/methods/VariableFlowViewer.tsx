"use client"

import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import katex from 'katex'
import { AlertCircle, ArrowDown, ChevronLeft, ChevronRight, Code2, FileCode2, GitBranch, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { FlowVariable, MethodFlow } from '@/lib/method-flow'

function MathText({ math, block = false }: { math: string; block?: boolean }) {
  const html = katex.renderToString(math, { throwOnError: false, displayMode: block, trust: false, strict: false })
  return <span className={cn(block ? 'block max-w-full overflow-x-auto py-3' : 'inline-block align-middle')} dangerouslySetInnerHTML={{ __html: html }} />
}

function Variables({ title, items }: { title: string; items: FlowVariable[] }) {
  return <section>
    <h4 className="mb-2 flex items-center gap-2 font-semibold text-slate-800"><ArrowDown size={16} className="text-emerald-600" />{title}</h4>
    <dl className="divide-y divide-slate-200/70">
      {items.map((item, index) => <div key={index} className="grid grid-cols-[minmax(64px,auto)_minmax(0,1fr)] items-start gap-x-3 py-2">
        <dt className="text-emerald-800"><MathText math={item.symbol} /></dt>
        <dd className="min-w-0 text-slate-700">{item.meaning}<code className="mt-1 block break-all font-mono text-sm text-slate-500">{item.code}</code></dd>
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

export default function VariableFlowViewer({ methodId }: { methodId: string }) {
  const requestedStep = Number(useSearchParams().get('step'))
  const [flow, setFlow] = useState<MethodFlow | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [stepIndex, setStepIndex] = useState(0)
  const codePane = useRef<HTMLDivElement>(null)
  const detailPane = useRef<HTMLElement>(null)
  const stepList = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setFlow(null)
    setError('')
    setStepIndex(0)
    async function read() {
      try {
        const response = await fetch(`/api/method-flow/${methodId}`, { signal: controller.signal, cache: 'no-store' })
        if (response.status === 404) return
        if (!response.ok) throw new Error('程序流程读取或源码定位失败，请重试。')
        const data: MethodFlow = await response.json()
        if (data.schemaVersion !== 2 || data.methodId !== methodId || !data.steps?.length || !data.sources?.length || data.steps.some(item => !item.sources.length)) throw new Error('程序流程不完整，无法展示。')
        if (!controller.signal.aborted) {
          setFlow(data)
          setStepIndex(Math.max(0, data.steps.findIndex(item => item.id === requestedStep)))
        }
      } catch (cause) {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : '程序流程读取失败。')
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    void read()
    return () => controller.abort()
  }, [methodId, retry, requestedStep])

  const step = flow?.steps[stepIndex]
  const reference = step?.sources[0]
  const source = flow?.sources.find(item => item.path === reference?.file)
  useEffect(() => {
    const pane = codePane.current
    if (!pane) return
    const target = pane.querySelector<HTMLElement>('[data-primary-source="true"]')
    pane.scrollTop = target ? target.getBoundingClientRect().top - pane.getBoundingClientRect().top + pane.scrollTop - 12 : 0
    pane.scrollLeft = 0
    if (detailPane.current) detailPane.current.scrollTop = 0
    const list = stepList.current
    const active = list?.querySelector<HTMLElement>('[aria-current="step"]')
    if (list && active) {
      if (active.offsetTop < list.scrollTop || active.offsetTop + active.offsetHeight > list.scrollTop + list.clientHeight) list.scrollTop = active.offsetTop - 12
      if (active.offsetLeft < list.scrollLeft || active.offsetLeft + active.offsetWidth > list.scrollLeft + list.clientWidth) list.scrollLeft = active.offsetLeft - 12
    }
  }, [stepIndex, flow])

  if (loading || (flow && flow.methodId !== methodId)) return <div className="flex items-center justify-center gap-3 py-20 text-slate-600" role="status"><Loader2 className="animate-spin text-emerald-600" size={24} />加载程序流程…</div>
  if (error) return <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-800" role="alert"><p className="flex items-center gap-2"><AlertCircle size={20} />{error}</p><button onClick={() => setRetry(value => value + 1)} className="mt-3 rounded-lg px-3 py-2 font-semibold hover:bg-rose-100">重新加载</button></div>
  if (!flow || !step || !reference || !source) return <div className="rounded-2xl bg-slate-50 py-16 text-center text-slate-500"><FileCode2 className="mx-auto mb-3" size={28} />暂无程序流程说明</div>

  const go = (index: number) => setStepIndex(index)
  const stepFiles = flow.sources.filter(item => step.sources.some(ref => ref.file === item.path))
  const mappedSymbols = new Set([...step.inputs, ...step.outputs].map(item => item.symbol))
  const extraSymbols = step.formula.symbols.filter(item => !mappedSymbols.has(item.symbol))
  return <div className="min-w-0 overflow-hidden rounded-2xl border border-slate-200 bg-white text-base" data-method-flow={methodId}>
    <header className="border-b border-slate-200 bg-gradient-to-r from-emerald-50/80 to-white px-4 py-4 sm:px-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-xl font-bold text-slate-900"><GitBranch size={21} className="text-emerald-600" />程序流程</h2>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="mr-2 tabular-nums text-slate-500" aria-live="polite">{stepIndex + 1} / {flow.steps.length}</span>
          <button aria-label="上一步" title="上一步" disabled={stepIndex === 0} onClick={() => go(stepIndex - 1)} className="rounded-lg p-2 text-slate-600 hover:bg-emerald-100 disabled:opacity-25"><ChevronLeft size={22} /></button>
          <button aria-label="下一步" title="下一步" disabled={stepIndex === flow.steps.length - 1} onClick={() => go(stepIndex + 1)} className="rounded-lg p-2 text-slate-600 hover:bg-emerald-100 disabled:opacity-25"><ChevronRight size={22} /></button>
        </div>
      </div>
    </header>

    <div className="grid min-w-0 grid-cols-1 md:grid-cols-2 xl:grid-cols-[210px_minmax(0,1.15fr)_minmax(0,1fr)]">
      <nav aria-label="算法步骤" className="min-w-0 max-[767px]:order-1 border-b border-slate-200 bg-slate-50/70 p-3 md:col-span-2 xl:col-span-1 xl:border-b-0 xl:border-r">
        <div ref={stepList} className="relative flex gap-1 overflow-x-auto pb-1 xl:max-h-[840px] xl:flex-col xl:overflow-y-auto xl:pb-0">
          {flow.steps.map((item, index) => <button key={item.id} onClick={() => go(index)} aria-current={index === stepIndex ? 'step' : undefined} className={cn('flex shrink-0 items-start gap-3 rounded-xl px-3 py-3 text-left transition-colors xl:shrink', index === stepIndex ? 'bg-emerald-100/80 text-emerald-950' : 'text-slate-600 hover:bg-slate-200/60')}>
            <span className={cn('mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-sm tabular-nums', index === stepIndex ? 'bg-emerald-600 text-white' : 'bg-slate-200/70 text-slate-500')}>{index + 1}</span>
            <span className="max-w-[220px] font-medium leading-relaxed xl:max-w-none">{item.name}</span>
          </button>)}
        </div>
      </nav>

      <section className="min-w-0 max-[767px]:order-3 bg-slate-900 text-slate-200" aria-label="真实Python源码">
        <div className="border-b border-slate-700 px-4 py-3">
          <div className="mb-3">
            <h3 className="flex items-center gap-2 font-semibold text-white"><Code2 size={18} />Python 源码</h3>
          </div>
        </div>
        <div ref={codePane} className="relative max-h-[560px] overflow-auto py-3 xl:h-[650px] xl:max-h-[650px]" tabIndex={0} aria-label="源码内容">
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
        <details key={reference.file + stepIndex} className="border-t border-slate-700 px-4 py-3 text-sm text-slate-400">
          <summary className="cursor-pointer text-slate-300">查看完整源文件</summary>
          {stepFiles.map(file => <div key={file.path}><p className="mt-3 break-all font-mono">{file.path}</p><pre className="mt-2 max-h-96 overflow-auto text-sm leading-6"><code>{file.lines.join('\n')}</code></pre></div>)}
        </details>
        <details key={`notes-${stepIndex}`} className="border-t border-slate-700 px-4 py-3 text-sm text-slate-400">
          <summary className="cursor-pointer text-slate-300">来源与实现说明</summary>
          {flow.implementation && <p className="mt-3 leading-relaxed">{flow.implementation}</p>}
          <p className="mt-3 leading-relaxed">{step.basis}</p>
          {step.notes && <p className="mt-2 leading-relaxed">{step.notes}</p>}
          <dl className="mt-3 space-y-3">{[...flow.sources, ...flow.artifacts].map(item => <div key={item.path}><dt className="break-all font-mono text-slate-300">{item.path}</dt><dd className="mt-1 break-all font-mono">SHA-256 {item.sha256}</dd></div>)}</dl>
        </details>
      </section>

      <article ref={detailPane} className="min-w-0 max-[767px]:order-2 space-y-5 p-4 sm:p-5 xl:max-h-[890px] xl:overflow-y-auto" aria-label="本步公式与变量">
        <div><p className="mb-1 text-sm font-medium text-emerald-700">步骤 {stepIndex + 1}</p><h3 className="text-xl font-bold leading-relaxed text-slate-900">{step.name}</h3><p className="mt-2 leading-relaxed text-slate-600">{step.description}</p></div>
        <section className="min-w-0 rounded-xl bg-emerald-50/70 px-3 py-2 text-emerald-950" aria-label="本步公式"><MathText math={step.formula.expression} block /></section>
        {!!extraSymbols.length && <dl className="flex flex-wrap gap-x-4 gap-y-2 text-sm text-slate-600">{extraSymbols.map((item, index) => <div key={index} className="flex min-w-0 items-center gap-2"><dt><MathText math={item.symbol} /></dt><dd>{item.meaning}</dd></div>)}</dl>}
        <Variables title="输入" items={step.inputs} />
        <Variables title="输出" items={step.outputs} />
      </article>
    </div>
  </div>
}
