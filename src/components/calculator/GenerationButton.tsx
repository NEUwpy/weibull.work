'use client'

import { useEffect, useRef, useState } from 'react'
import { ChevronDown, RefreshCw } from 'lucide-react'
import { SAMPLE_COUNTS } from '@/lib/calculator-batch'

export function GenerationButton({ count, onCountChange, onGenerate, disabled }: {
  count: number; onCountChange: (count: number) => void; onGenerate: () => void; disabled: boolean
}) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false) }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape) }
  }, [open])
  return <div ref={root} className="relative flex h-full min-w-0 flex-1">
    <button type="button" onClick={onGenerate} disabled={disabled}
      className="generation-button-primary flex h-full min-w-0 flex-1 items-center justify-center gap-1.5 rounded-l-md border border-indigo-200 bg-indigo-50 text-sm font-bold text-indigo-600 hover:bg-indigo-100 disabled:opacity-50">
      <RefreshCw size={14} className="shrink-0" /><span className="whitespace-nowrap">生成样本</span>
    </button>
    <button type="button" aria-label="生成样本组数" aria-haspopup="dialog" aria-expanded={open}
      disabled={disabled} onClick={() => setOpen(value => !value)}
      className="flex w-[84px] shrink-0 items-center justify-between gap-1 rounded-r-md border border-l-0 border-indigo-200 bg-indigo-50 px-2 text-sm font-bold tabular-nums text-indigo-600 hover:bg-indigo-100 disabled:opacity-50">
      <span className="min-w-0 flex-1 whitespace-nowrap text-center">{count}组</span><ChevronDown size={12} className="shrink-0" />
    </button>
    {open && <div role="dialog" aria-label="设置生成样本组数"
      className="absolute bottom-full left-0 z-50 mb-2 w-56 rounded-xl border border-slate-200 bg-white p-3 shadow-lg">
      <div className="grid grid-cols-3 gap-1">
        {SAMPLE_COUNTS.map(value => <button key={value} type="button" aria-pressed={count === value}
          onClick={() => { onCountChange(value); setOpen(false) }}
          className={'rounded-md px-2 py-2 text-sm hover:bg-indigo-50 ' + (count === value ? 'bg-indigo-50 font-semibold text-indigo-600' : 'text-slate-600')}>
          {value}组
        </button>)}
      </div>
      <label className="mt-2 flex items-center justify-between gap-2 border-t border-slate-100 pt-3 text-sm text-slate-600">
        自定义
        <input aria-label="自定义生成组数" type="number" min={1} max={1000} step={1} value={count}
          onChange={event => { const value = Number(event.target.value); if (Number.isInteger(value) && value >= 1 && value <= 1000) onCountChange(value) }}
          className="w-24 rounded-md border border-slate-200 px-2 py-1 tabular-nums" />
      </label>
    </div>}
  </div>
}
