'use client'

import React, { useEffect, useId, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'

export interface LibraryFilterOption {
  value: string
  label: string
  count?: number
  description?: string
  child?: boolean
  divider?: boolean
}

export function LibraryFilterMenu({ label, value, options, onChange, align = 'start' }: {
  label: string; value: string; options: LibraryFilterOption[]; onChange: (value: string) => void
  align?: 'start' | 'end'
}) {
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const [placement, setPlacement] = useState({ side: 'bottom', height: 420 })
  const id = useId()
  const selected = options.find(option => option.value === value)

  useEffect(() => {
    if (!open) return
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    const resize = () => setOpen(false)
    document.addEventListener('pointerdown', outside)
    window.addEventListener('resize', resize)
    return () => { document.removeEventListener('pointerdown', outside); window.removeEventListener('resize', resize) }
  }, [open])

  function show(last = false) {
    const rect = trigger.current?.getBoundingClientRect()
    if (rect) {
      const below = window.innerHeight - rect.bottom - 20
      const above = rect.top - 20
      const up = below < 200 && above > below
      setPlacement({ side: up ? 'top' : 'bottom', height: Math.min(440, Math.max(120, up ? above : below)) })
    }
    setOpen(true)
    requestAnimationFrame(() => {
      const items = root.current?.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]')
      const current = root.current?.querySelector<HTMLButtonElement>('[aria-checked="true"]')
      const target = last ? items?.[items.length - 1] : current || items?.[0]
      target?.focus({ preventScroll: true })
      target?.scrollIntoView({ block: 'nearest' })
    })
  }

  return <div ref={root} className={`library-filter-menu library-filter-menu-${align}`} data-open={open || undefined}
    onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setOpen(false) }}
    onKeyDown={event => {
      if (event.key === 'Escape') { event.preventDefault(); setOpen(false); trigger.current?.focus() }
    }}>
    <button ref={trigger} type="button" className="library-filter-trigger" aria-label={`${label}：${selected?.label || label}`}
      aria-haspopup="menu" aria-expanded={open} aria-controls={open ? id : undefined}
      onClick={() => open ? setOpen(false) : show()}
      onKeyDown={event => {
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); show(event.key === 'ArrowUp') }
      }}>
      <span>{selected?.label || label}</span><ChevronDown size={14} aria-hidden="true" />
    </button>
    {open && <div id={id} role="menu" aria-label={`选择${label}`} className="library-filter-panel" data-side={placement.side}
      style={{ maxHeight: placement.height }} onKeyDown={event => {
        if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
        event.preventDefault()
        const items = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]'))
        const current = items.indexOf(document.activeElement as HTMLButtonElement)
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1
          : (current + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length
        items[next]?.focus()
      }}>
      {options.map(option => <React.Fragment key={option.value}>
        {option.divider && <div role="separator" className="library-filter-divider" />}
        <button type="button" role="menuitemradio" aria-checked={value === option.value}
          className={`library-filter-option${option.child ? ' library-filter-child' : ''}`}
          onClick={() => { setOpen(false); trigger.current?.focus(); onChange(option.value) }}>
          <span className="library-filter-option-text"><span>{option.label}</span>
            {option.description && <small>{option.description}</small>}
          </span>
          <span className="library-filter-option-end">
            {option.count !== undefined && <span className="library-filter-count">{option.count}</span>}
            <Check size={14} aria-hidden="true" className="library-filter-check" />
          </span>
        </button>
      </React.Fragment>)}
    </div>}
  </div>
}
