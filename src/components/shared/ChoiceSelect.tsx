'use client'
import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import styles from './ChoiceSelect.module.css'

export interface ChoiceOption { value: string | number; label?: string; disabled?: boolean }
export default function ChoiceSelect({ label, displayLabel, options, value, onChange, tone = 'parameter' }: {
  label: string; displayLabel: string; options: ChoiceOption[]; value: string | number
  onChange: (value: string | number) => void; tone?: 'parameter' | 'sample'
}) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null), trigger = useRef<HTMLButtonElement>(null)
  const selected = options.find(option => option.value === value)
  useEffect(() => {
    const close = (event: MouseEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  function focusSelected() { requestAnimationFrame(() => root.current?.querySelector<HTMLButtonElement>('[aria-checked="true"]')?.focus()) }
  return <div ref={root} className={`${styles.choice} ${tone === 'sample' ? styles.sample : ''}`} role="group" aria-label={label}
    onKeyDown={event => {
      if (event.key === 'Escape') { setOpen(false); trigger.current?.focus() }
      if (event.key === 'ArrowDown' && !open) { event.preventDefault(); setOpen(true); focusSelected() }
    }}>
    <span className={styles.label}>{displayLabel}<span className={styles.equals}>=</span></span>
    <div className={styles.selector}>
      <button ref={trigger} type="button" className={styles.trigger} aria-label={`${displayLabel} = ${selected?.label ?? value}`} aria-haspopup="menu" aria-expanded={open}
        onClick={() => { setOpen(current => !current); if (!open) focusSelected() }}>
        <span>{selected?.label ?? value}</span><ChevronDown size={14} aria-hidden="true" />
      </button>
      {open && <div className={styles.menu} role="menu" aria-label={`选择${label}`} onKeyDown={event => {
        if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
        event.preventDefault()
        const items = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)'))
        const index = items.indexOf(document.activeElement as HTMLButtonElement)
        items[event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 : (index + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length]?.focus()
      }}>{options.map(option => <button type="button" role="menuitemradio" aria-checked={option.value === value} disabled={option.disabled} key={option.value}
        onClick={() => { onChange(option.value); setOpen(false); trigger.current?.focus() }}>
        {option.label ?? option.value}{option.value === value && <Check size={14} aria-hidden="true" />}
      </button>)}</div>}
    </div>
  </div>
}
