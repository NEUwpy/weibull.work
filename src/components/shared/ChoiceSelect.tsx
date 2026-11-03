'use client'
import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import styles from './ChoiceSelect.module.css'

export interface ChoiceOption { value: string | number; label?: string; disabled?: boolean }
export default function ChoiceSelect({ label, displayLabel, options, value, onChange, tone = 'parameter' }: {
  label: string; displayLabel: string; options: ChoiceOption[]; value: string | number
  onChange: (value: string | number) => void; tone?: 'parameter' | 'sample'
}) {
  const [open, setOpen] = useState(false), [hovered, setHovered] = useState(false), [canHover, setCanHover] = useState(false)
  const root = useRef<HTMLDivElement>(null), trigger = useRef<HTMLButtonElement>(null), selector = useRef<HTMLDivElement>(null)
  const wheelGesture = useRef({ delta: 0, lastEvent: 0, lastChange: 0 })
  const selected = options.find(option => option.value === value)
  const enabled = options.filter(option => !option.disabled)
  const index = enabled.findIndex(option => option.value === value)
  const previous = index > 0 ? enabled[index - 1] : undefined
  const next = index >= 0 ? enabled[index + 1] : undefined
  const showWheel = canHover && hovered && !open && (previous !== undefined || next !== undefined)
  useEffect(() => {
    const media = window.matchMedia('(hover: hover) and (pointer: fine) and (min-width: 768px)')
    const update = () => { setCanHover(media.matches); if (!media.matches) setHovered(false) }
    update()
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  useEffect(() => {
    const close = (event: MouseEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  useEffect(() => {
    const element = selector.current
    if (!element || !showWheel) return
    wheelGesture.current.delta = 0
    const roll = (event: WheelEvent) => {
      if (!event.deltaY || event.ctrlKey) return
      event.preventDefault()
      const gesture = wheelGesture.current, now = Date.now()
      if (now - gesture.lastEvent > 180) gesture.delta = 0
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? 100 : 1)
      if (Math.sign(gesture.delta) !== Math.sign(delta)) gesture.delta = 0
      gesture.delta += delta
      gesture.lastEvent = now
      if (Math.abs(gesture.delta) < 24 || now - gesture.lastChange < 180) return
      const option = gesture.delta > 0 ? next : previous
      gesture.delta = 0
      if (option) { gesture.lastChange = now; onChange(option.value) }
    }
    element.addEventListener('wheel', roll, { passive: false })
    return () => element.removeEventListener('wheel', roll)
  }, [showWheel, previous, next, onChange])
  function focusSelected() { requestAnimationFrame(() => root.current?.querySelector<HTMLButtonElement>('[aria-checked="true"]')?.focus()) }
  return <div ref={root} className={`${styles.choice} ${tone === 'sample' ? styles.sample : ''}`} role="group" aria-label={label}
    onKeyDown={event => {
      if (event.key === 'Escape') { setOpen(false); setHovered(false); trigger.current?.focus() }
      if (event.key === 'ArrowDown' && !open) { event.preventDefault(); setHovered(false); setOpen(true); focusSelected() }
    }}>
    <span className={styles.label}>{displayLabel}<span className={styles.equals}>=</span></span>
    <div ref={selector} className={styles.selector} data-floating={showWheel || open}
      style={{ '--choice-value-width': `${Math.max(2, ...options.map(option => String(option.label ?? option.value).length)) * 11}px` } as CSSProperties}
      onPointerEnter={event => { if (canHover && event.pointerType === 'mouse') setHovered(true) }} onPointerLeave={() => setHovered(false)}>
      {showWheel && <div className={styles.wheel} data-previous={!!previous} data-next={!!next} role="group" aria-label={`${label}快捷滚轮`}>
        {previous ? <button type="button" className={styles.wheelOption} aria-label={`选择${label} ${previous.label ?? previous.value}`} onClick={() => onChange(previous.value)}><span>{previous.label ?? previous.value}</span></button> : <span aria-hidden="true" />}
        <span aria-hidden="true" />
        {next ? <button type="button" className={styles.wheelOption} aria-label={`选择${label} ${next.label ?? next.value}`} onClick={() => onChange(next.value)}><span>{next.label ?? next.value}</span></button> : <span aria-hidden="true" />}
      </div>}
      <button ref={trigger} type="button" className={styles.trigger} aria-label={`${displayLabel} = ${selected?.label ?? value}`} aria-haspopup="menu" aria-expanded={open}
        onClick={() => { setHovered(false); setOpen(current => !current); if (!open) focusSelected() }}>
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
