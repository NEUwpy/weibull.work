"use client"

import { type CSSProperties, type ReactNode, useEffect, useId, useRef, useState } from 'react'
import { Info, X } from 'lucide-react'
import { calculationSteps } from '@/lib/calculation-steps'
import { CalculationSourceButton, useCalculationStage } from './CalculationSource'

function StepExplanation({ title, children }: { title: string; children: ReactNode }) {
  const id = useId()
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const closeTimer = useRef<ReturnType<typeof setTimeout>>()
  const [open, setOpen] = useState<{ pinned: boolean; position: CSSProperties } | null>(null)

  function show(pinned: boolean) {
    clearTimeout(closeTimer.current)
    const anchor = trigger.current?.getBoundingClientRect()
    if (!anchor) return
    const width = Math.min(560, window.innerWidth - 24)
    const below = window.innerHeight - anchor.bottom - 18
    const above = anchor.top - 18
    const showAbove = below < 260 && above > below
    setOpen({ pinned, position: {
      width,
      left: Math.max(12, Math.min(anchor.right - width, window.innerWidth - width - 12)),
      maxHeight: Math.min(520, Math.max(1, showAbove ? above : below)),
      ...(showAbove ? { bottom: window.innerHeight - anchor.top + 6 } : { top: anchor.bottom + 6 }),
    } })
  }

  useEffect(() => () => clearTimeout(closeTimer.current), [])
  useEffect(() => {
    if (!open) return
    const dismiss = () => setOpen(null)
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) dismiss()
    }
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      if (panel.current?.contains(document.activeElement)) trigger.current?.focus({ preventScroll: true })
      dismiss()
    }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    window.addEventListener('scroll', dismiss)
    window.addEventListener('resize', dismiss)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
      window.removeEventListener('scroll', dismiss)
      window.removeEventListener('resize', dismiss)
    }
  }, [open])

  return <div ref={root} className="shrink-0"
    onPointerEnter={event => {
      if (event.pointerType !== 'mouse') return
      clearTimeout(closeTimer.current)
      if (!open) show(false)
    }}
    onPointerLeave={event => {
      if (event.pointerType !== 'mouse' || !open || open.pinned) return
      closeTimer.current = setTimeout(() => setOpen(current => current?.pinned ? current : null), 160)
    }}>
    <button ref={trigger} type="button" aria-label={`${title}的说明`} aria-haspopup="dialog" aria-expanded={!!open} aria-controls={open ? id : undefined}
      onClick={() => open?.pinned ? setOpen(null) : show(true)}
      className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm text-blue-700 hover:bg-blue-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500">
      <Info size={16} aria-hidden="true" />说明
    </button>
    {open && <div ref={panel} id={id} role="dialog" aria-label={`${title}的计算与符号说明`} style={open.position}
      className="fixed z-[60] overflow-y-auto overscroll-contain rounded-xl border border-slate-200 bg-white shadow-xl">
      <div className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-2.5">
        <h4 className="font-semibold text-slate-800">计算与符号说明</h4>
        <button type="button" aria-label="关闭说明" onClick={() => { trigger.current?.focus({ preventScroll: true }); setOpen(null) }}
          className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500"><X size={18} aria-hidden="true" /></button>
      </div>
      <div className="min-w-0 space-y-4 p-4">{children}</div>
    </div>}
  </div>
}

export function CalculationStepContent({ title, figure, axes, calculation, criterion, symbols, details, actions, stacked = false }: {
  title: string
  figure?: ReactNode
  axes?: { x: string; y: string }
  calculation?: ReactNode
  criterion: ReactNode
  symbols: ReadonlyArray<readonly [string, string]>
  details?: ReactNode
  actions?: ReactNode
  stacked?: boolean
}) {
  const split = figure && !stacked
  const terms = [...(axes ? [['横轴', axes.x], ['纵轴', axes.y]] : []), ...symbols]
  return <section className="min-w-0 space-y-5 rounded-2xl border border-slate-200 bg-white p-4 sm:p-5" data-step-content>
    <div className="flex items-start justify-between gap-3">
      <h3 className="text-lg font-semibold text-slate-800">{title}</h3>
      <div className="flex flex-wrap items-center justify-end">
        {actions}
        {(calculation || terms.length > 0 || details) && <StepExplanation title={title}>
          {calculation && <section className="min-w-0" aria-label="计算说明">
            <h5 className="font-semibold text-slate-800">计算说明</h5>
            {calculation}
          </section>}
          {terms.length > 0 && <section className={`min-w-0 ${calculation ? 'border-t border-slate-200 pt-3' : ''}`} aria-label="符号说明">
            <h5 className="font-semibold text-slate-800">符号说明</h5>
            <dl className="mt-2 grid gap-2 text-base leading-relaxed text-slate-700">
              {terms.map(([symbol, meaning]) => <div key={symbol} className="flex min-w-0 gap-2">
                <dt className="shrink-0 font-medium text-slate-800">{symbol}</dt><dd className="min-w-0">{meaning}</dd>
              </div>)}
            </dl>
          </section>}
          {details}
        </StepExplanation>}
      </div>
    </div>
    <div className={`grid min-w-0 items-start gap-5 ${split ? 'xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]' : ''}`}>
      {figure && <section className="min-w-0 space-y-2" aria-label="图示">
        {figure}
      </section>}
      <div className={`min-w-0 space-y-4 ${figure ? 'border-t border-slate-200 pt-4' : ''} ${split ? 'xl:border-l xl:border-t-0 xl:pl-5 xl:pt-0' : ''}`}>
        <section className="min-w-0" aria-label="取值判据与结果">
          <h4 className="font-semibold text-slate-800">取值判据与结果</h4>
          {criterion}
        </section>
      </div>
    </div>
  </section>
}

export function ProcessDetails({ children, title = '查看计算细节' }: { children: ReactNode; title?: string }) {
  const [open, setOpen] = useState(false)
  return <details className="rounded-xl border border-slate-200 px-4 py-3" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary className="cursor-pointer text-base text-slate-600">{title}</summary>
    {open && <div className="mt-4 min-w-0 space-y-4">{children}</div>}
  </details>
}

export function CalculationOverview({ method }: { method: string }) {
  const definitions = calculationSteps[method]
  if (!definitions) return <CalculationSourceButton stage={-1} />
  return <CalculationSteps method={method} />
}

export function CalculationSteps({ method, children }: { method: string; children?: ReactNode[] }) {
  const definitions = calculationSteps[method]
  const stage = useCalculationStage()
  const [localIndex, setLocalIndex] = useState(0)
  const index = stage?.activeStage ?? localIndex
  const setIndex = stage?.selectStage ?? setLocalIndex
  const step = definitions[index]
  return <section className="min-w-0 space-y-4" aria-label="分步计算过程">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <nav aria-label="计算步骤" className="flex flex-wrap gap-2">
        {definitions.map((item, i) => <button key={item.label} type="button" aria-current={i === index ? 'step' : undefined}
          onClick={() => setIndex(i)} className={`rounded-lg border px-3 py-2 text-base ${i === index ? 'border-emerald-600 bg-emerald-50 font-medium text-emerald-900' : 'border-slate-200 text-slate-600 hover:bg-slate-50'}`}>
          {i + 1}　{item.label}
        </button>)}
      </nav>
      <CalculationSourceButton stage={index} label={step.label} />
    </div>
    {children && <div role="region" aria-label={`第 ${index + 1} 步：${step.label}`} className="min-w-0 space-y-4">{children[index]}</div>}
    {children && <div className="flex items-center justify-between gap-3 border-t border-slate-200 pt-3">
      <button type="button" aria-label="计算上一步" disabled={index === 0} onClick={() => setIndex(index - 1)} className="rounded-lg px-3 py-2 text-base text-slate-600 hover:bg-slate-100 disabled:opacity-30">上一步</button>
      <span className="text-sm tabular-nums text-slate-500">{index + 1} / {definitions.length}</span>
      <button type="button" aria-label="计算下一步" disabled={index === definitions.length - 1} onClick={() => setIndex(index + 1)} className="rounded-lg bg-emerald-50 px-3 py-2 text-base text-emerald-800 hover:bg-emerald-100 disabled:opacity-30">下一步</button>
    </div>}
  </section>
}
