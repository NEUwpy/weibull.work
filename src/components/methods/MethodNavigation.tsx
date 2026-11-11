'use client'
import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ChevronDown, BookOpen, Microscope, BarChart3, Gauge, FileCheck, Scale, LucideIcon } from 'lucide-react'
import { MethodNode } from '@/lib/methods'
import MethodTree from '@/components/shared/MethodTree'
import { methodHref, MethodTab } from '@/lib/method-navigation'
import styles from './MethodNavigation.module.css'

const tabs: { tab: MethodTab; label: string; icon: LucideIcon }[] = [
  { tab: null, label: '方法原理', icon: BookOpen }, { tab: 'lab', label: '计算过程', icon: Microscope },
  { tab: 'analysis', label: '结果分析', icon: BarChart3 }, { tab: 'examples', label: '适用范围', icon: Gauge }, { tab: 'cases', label: '可信性验证', icon: FileCheck }, { tab: 'compare', label: '方法对比', icon: Scale },
]
export default function MethodNavigation({ method, activeTab }: { method: MethodNode; activeTab: MethodTab }) {
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
      {tabs.map(({ tab, label, icon: Icon }) => <Link key={label} href={methodHref(method.id, tab, navigationQuery)} scroll={false} aria-current={activeTab === tab ? 'page' : undefined}
        className={styles.link}><Icon size={17} strokeWidth={1.7} aria-hidden="true" />{label}</Link>)}
    </nav>
    </div>
  </header>
}
