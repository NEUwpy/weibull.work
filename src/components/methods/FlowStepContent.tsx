"use client"

import type { ReactNode } from 'react'
import { ArrowDown, Code2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { FlowStep, FlowVariable, MethodFlow } from '@/lib/method-flow'
import { ProcessEquation } from '@/components/shared/charts/ProcessEquation'
import { MathText } from '@/components/shared/MathText'

function Variables({ title, items, values }: {
  title: string; items: FlowVariable[]; values?: Record<string, string>
}) {
  return <section>
    <h4 className="mb-2 flex items-center gap-2 font-semibold text-slate-800"><ArrowDown size={16} className="text-emerald-600" />{title}</h4>
    <dl className="divide-y divide-slate-200/70">
      {items.map((item, index) => { const value = values?.[`${title === '输入' ? 'input' : 'output'}.${item.code}`] ?? values?.[item.code]; return <div key={index} data-variable-id={item.id} className="grid grid-cols-[minmax(64px,auto)_minmax(0,1fr)] items-start gap-x-3 py-2">
        <dt className="text-emerald-800"><MathText math={item.symbol} /></dt>
        <dd className="min-w-0 text-slate-700">{item.meaning}
          {value !== undefined && <span className="mt-1 block break-words font-medium tabular-nums text-slate-900">{value}</span>}
        </dd>
      </div>})}
    </dl>
  </section>
}

const keywords = new Set(['def', 'class', 'if', 'elif', 'else', 'for', 'in', 'while', 'return', 'try', 'except', 'with', 'as', 'from', 'import', 'None', 'True', 'False', 'and', 'or', 'not', 'is', 'raise', 'break', 'continue', 'lambda', 'global'])
function PythonLine({ line }: { line: string }) {
  return <>{line.split(/("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|#.*$|\b[A-Za-z_]\w*\b|\b\d+(?:\.\d*)?(?:e[+-]?\d+)?\b)/g).map((token, i) =>
    <span key={i} className={token.startsWith('#') ? 'text-slate-400' : /^['"]/.test(token) ? 'text-amber-200' : keywords.has(token) ? 'text-violet-300' : /^\d/.test(token) ? 'text-teal-300' : undefined}>{token}</span>
  )}</>
}

export function FlowStepCode({ flow, step }: { flow: MethodFlow; step: FlowStep }) {
  const stepFiles = flow.sources.filter(item => step.sources.some(ref => ref.file === item.path))
  return (
      <section className="min-w-0 overflow-hidden rounded-xl bg-slate-900 text-slate-200" aria-label="真实Python源码">
        <div className="border-b border-slate-700 px-4 py-3">
          <div className="mb-3">
            <h3 className="flex items-center gap-2 font-semibold text-white"><Code2 size={18} />Python 源码</h3>
          </div>
        </div>
        <div className="relative overflow-x-auto py-3" tabIndex={0} aria-label="源码内容">
          {step.sources.map((ref, blockIndex) => {
            const file = flow.sources.find(item => item.path === ref.file)!
            const lines = file.lines.slice(ref.start, ref.end)
              .map((line, index) => ({ line, index: ref.start + index }))
            return <div key={blockIndex} data-source-block={blockIndex} data-primary-source={blockIndex === (step.primarySource ?? 0)} className={cn(blockIndex > 0 && 'mt-5 border-t border-slate-700 pt-4', blockIndex === (step.primarySource ?? 0) && 'bg-emerald-400/5')}>
              <p className="mb-2 break-all px-4 font-mono text-sm text-slate-400">{ref.label}<br />{file.path}<span className="ml-2 whitespace-nowrap">L{ref.start + 1}–{ref.end}</span></p>
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

export function FlowStepDetails({ step, children, values, formulaVariant, equationStart }: {
  step: FlowStep; children?: ReactNode; values?: Record<string, string>; formulaVariant?: string; equationStart?: number
}) {
  const mappedSymbols = new Set([...step.inputs, ...step.outputs].map(item => item.symbol))
  const extraSymbols = step.formula.symbols.filter(item => !mappedSymbols.has(item.symbol))
  const equations = (formulaVariant && step.formula.variantEquations?.[formulaVariant]) || step.formula.equations
  const symbols = <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-2 text-sm text-slate-600">{extraSymbols.map((item, index) => <div key={index} className="flex min-w-0 items-center gap-2"><dt><MathText math={item.symbol} /></dt><dd>{item.meaning}</dd></div>)}</dl>
  return (
      <article className="min-w-0 space-y-5" aria-label="本步公式与变量">
        <section className="min-w-0 space-y-3 border-b border-slate-100 pb-5 text-slate-800" aria-label="本步公式">
          <p className="text-sm leading-relaxed text-slate-600">{step.formula.explanation}</p>
          {equations.map((expression, index) => <ProcessEquation key={index} expression={expression}
            number={equationStart === undefined ? undefined : equationStart + index} />)}
        </section>
        {children}
        {!!extraSymbols.length && <details><summary className="cursor-pointer text-sm text-slate-600">符号说明</summary>{symbols}</details>}
        <Variables title="输入" items={step.inputs} values={values} />
        <Variables title="输出" items={step.outputs} values={values} />
        {!!(step.extraInputs?.length || step.extraOutputs?.length) && <details>
          <summary className="cursor-pointer text-sm text-slate-600">设置与补充量</summary>
          <div className="mt-3 space-y-4">
            {!!step.extraInputs?.length && <Variables title="输入" items={step.extraInputs} values={values} />}
            {!!step.extraOutputs?.length && <Variables title="输出" items={step.extraOutputs} values={values} />}
          </div>
        </details>}
      </article>
  )
}
