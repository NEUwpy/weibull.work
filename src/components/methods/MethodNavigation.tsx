'use client'
import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ChevronDown, Check, BookOpen, GitBranch, Microscope, BarChart3, Gauge, FileCheck, Scale, LucideIcon } from 'lucide-react'
import { INITIAL_METHOD_TREE, MethodNode } from '@/lib/methods'
import { methodHref, MethodTab } from '@/lib/method-navigation'
import styles from './MethodNavigation.module.css'

const tabs: { tab: MethodTab; label: string; icon: LucideIcon }[] = [
  { tab: null, label: '方法原理', icon: BookOpen }, { tab: 'flow', label: '程序流程', icon: GitBranch }, { tab: 'lab', label: '计算过程', icon: Microscope },
  { tab: 'analysis', label: '结果分析', icon: BarChart3 }, { tab: 'examples', label: '适用范围', icon: Gauge }, { tab: 'cases', label: '可信性验证', icon: FileCheck }, { tab: 'compare', label: '方法对比', icon: Scale },
]
export default function MethodNavigation({ method, activeTab }: { method: MethodNode; activeTab: MethodTab }) {
  const router = useRouter(), query = useSearchParams()
  const [open, setOpen] = useState(false)
  const switchRef = useRef<HTMLDivElement>(null), buttonRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const outside = (event: MouseEvent) => { if (!switchRef.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', outside)
    return () => document.removeEventListener('mousedown', outside)
  }, [])
  useEffect(() => setOpen(false), [method.id])
  const leaves = INITIAL_METHOD_TREE.flatMap(node => node.children ?? [])
  const workbookOrder = ['mdm', 'mle', 'wmle', 'lse', 'lre', 'mmle']
  const options = activeTab === 'examples'
    ? [...workbookOrder, ...(workbookOrder.includes(method.id) ? [] : [method.id])].map(id => leaves.find(m => m.id === id)!).filter(Boolean)
    : leaves
  return <header className={styles.header}>
    <div className={styles.row}>
      <div ref={switchRef} className={styles.switcher} onKeyDown={e => {
        if (e.key === 'Escape') { setOpen(false); buttonRef.current?.focus() }
        if (e.key === 'ArrowDown' && !open) { e.preventDefault(); setOpen(true); requestAnimationFrame(() => switchRef.current?.querySelector<HTMLButtonElement>('[role="menuitemradio"][aria-checked="true"]')?.focus()) }
      }}>
        <h1><button ref={buttonRef} type="button" className={styles.title} aria-label="切换方法" aria-haspopup="menu" aria-expanded={open} aria-controls="method-switch-menu" onClick={() => setOpen(v => !v)}>
          <span>{method.name}</span><span className={styles.abbreviation}>{method.shortName.toUpperCase()}</span><ChevronDown size={18} strokeWidth={1.7} aria-hidden="true" />
        </button></h1>
        {open && <div id="method-switch-menu" className={styles.menu} role="menu" aria-label="切换方法" onKeyDown={e => {
          if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) return
          e.preventDefault(); const items = Array.from(e.currentTarget.querySelectorAll<HTMLButtonElement>('button')), index = items.indexOf(document.activeElement as HTMLButtonElement)
          items[e.key === 'Home' ? 0 : e.key === 'End' ? items.length - 1 : (index + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length]?.focus()
        }}>{options.map(m => <button type="button" key={m.id} role="menuitemradio" aria-checked={m.id === method.id} onClick={() => { setOpen(false); router.push(methodHref(m.id, activeTab, query), { scroll: false }) }}>
          <span className={styles.menuAbbreviation}>{m.shortName.toUpperCase()}</span><span>{m.name}</span>{m.id === method.id && <Check size={16} aria-hidden="true" />}
        </button>)}</div>}
      </div>
    <nav aria-label="方法功能" className={styles.navigation}>
      {tabs.map(({ tab, label, icon: Icon }) => <Link key={label} href={methodHref(method.id, tab, query)} scroll={false} aria-current={activeTab === tab ? 'page' : undefined}
        className={styles.link}><Icon size={17} strokeWidth={1.7} aria-hidden="true" />{label}</Link>)}
    </nav>
    </div>
  </header>
}
