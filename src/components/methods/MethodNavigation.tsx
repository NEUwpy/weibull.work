'use client'
import Link from 'next/link'
import { useEffect, useId, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ChevronDown, BookOpen, Microscope, BarChart3, FileCheck, Scale, Check, LucideIcon } from 'lucide-react'
import { MethodNode } from '@/lib/methods'
import MethodTree from '@/components/shared/MethodTree'
import { METHOD_ANALYSIS_SOURCES, methodAnalysisSource, methodHref, MethodTab } from '@/lib/method-navigation'
import styles from './MethodNavigation.module.css'

const tabs: { tab: MethodTab; label: string; icon: LucideIcon }[] = [
  { tab: null, label: '方法原理', icon: BookOpen }, { tab: 'lab', label: '计算过程', icon: Microscope },
  { tab: 'analysis', label: '结果分析', icon: BarChart3 }, { tab: 'cases', label: '可信性验证', icon: FileCheck }, { tab: 'compare', label: '方法对比', icon: Scale },
]
export default function MethodNavigation({ method, activeTab, canCalculate }: { method: MethodNode; activeTab: MethodTab; canCalculate: boolean }) {
  const router = useRouter(), query = useSearchParams()
  const navigationQuery = new URLSearchParams(query.toString())
  navigationQuery.delete('sourceStep')
  const [open, setOpen] = useState(false)
  const switchRef = useRef<HTMLDivElement>(null), buttonRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const outside = (event: MouseEvent) => { if (!switchRef.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', outside)
    return () => document.removeEventListener('mousedown', outside)
  }, [])
  useEffect(() => setOpen(false), [method.id])
  const focusMethod = () => requestAnimationFrame(() => {
    const panel = switchRef.current
    const selected = panel?.querySelector<HTMLElement>('[data-method-id][aria-pressed="true"]')
    const target = selected ?? panel?.querySelector<HTMLElement>('[data-method-id]')
    target?.focus()
  })
  return <header className={styles.header}>
    <div className={styles.row}>
      <div ref={switchRef} className={styles.switcher} onBlur={e => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOpen(false)
      }} onKeyDown={e => {
        if (e.key === 'Escape') { setOpen(false); buttonRef.current?.focus() }
        if (e.key === 'ArrowDown' && !open) { e.preventDefault(); setOpen(true); focusMethod() }
      }}>
        <h1><button ref={buttonRef} type="button" className={styles.title} aria-label="切换方法" aria-haspopup="dialog" aria-expanded={open} aria-controls="method-switch-menu" onClick={() => { setOpen(v => !v); if (!open) focusMethod() }}>
          <span>{method.name}</span><span className={styles.abbreviation}>{method.shortName.toUpperCase()}</span><ChevronDown size={18} strokeWidth={1.7} aria-hidden="true" />
        </button></h1>
        {open && <div id="method-switch-menu" className={styles.menu} role="dialog" aria-label="切换方法">
          <MethodTree selectedId={method.id} onSelect={id => {
            setOpen(false)
            buttonRef.current?.focus()
            if (id !== method.id) router.push(methodHref(id, activeTab, navigationQuery), { scroll: false })
          }} />
        </div>}
      </div>
    <nav aria-label="方法功能" className={styles.navigation}>
      {tabs.map(({ tab, label, icon: Icon }) => tab === 'analysis' && activeTab === tab && canCalculate
        ? <AnalysisNavigation key={label} methodId={method.id} query={navigationQuery} />
        : <Link key={label} href={methodHref(method.id, tab, navigationQuery)} scroll={false} aria-current={activeTab === tab ? 'page' : undefined}
          className={styles.link}><Icon size={17} strokeWidth={1.7} aria-hidden="true" />{label}</Link>)}
    </nav>
    </div>
  </header>
}

function AnalysisNavigation({ methodId, query }: { methodId: string; query: URLSearchParams }) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const id = useId()
  const source = methodAnalysisSource(query)
  const activeLabel = METHOD_ANALYSIS_SOURCES.find(option => option.id === source)?.label

  useEffect(() => {
    if (!open) return
    const dismiss = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('pointerdown', dismiss)
    return () => document.removeEventListener('pointerdown', dismiss)
  }, [open])

  return <div ref={root} className={styles.analysisNav} onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false)
  }} onKeyDown={event => {
    if (event.key === 'Escape' && open) {
      setOpen(false)
      trigger.current?.focus()
    }
  }}>
    <button ref={trigger} type="button" className={styles.link} aria-current="page" aria-expanded={open}
      aria-controls={open ? id : undefined} aria-label={`结果分析，当前为${activeLabel}`}
      onClick={() => setOpen(previous => !previous)}>
      <BarChart3 size={17} strokeWidth={1.7} aria-hidden="true" />结果分析<ChevronDown size={13} aria-hidden="true" />
    </button>
    {open && <div id={id} className={styles.analysisOptions} role="group" aria-label="结果来源">
      {METHOD_ANALYSIS_SOURCES.map(({ id: value, label }) => {
        const next = new URLSearchParams(query)
        next.set('source', value)
        return <Link key={value} href={methodHref(methodId, 'analysis', next)} scroll={false}
          aria-current={source === value ? 'true' : undefined}
          onClick={() => { setOpen(false); trigger.current?.focus() }}>
          {label}{source === value && <Check size={15} aria-hidden="true" />}
        </Link>
      })}
    </div>}
  </div>
}
