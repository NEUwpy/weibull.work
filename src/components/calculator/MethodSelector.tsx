'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { motion } from 'framer-motion'
import { X, BookOpen, CheckCircle, Settings2, ExternalLink } from 'lucide-react'
import { INITIAL_METHOD_TREE } from '@/lib/methods'
import { isCalculatorEnabled } from '@/lib/method-status'
import { MethodDetailContent } from '@/components/methods/MethodDetailContent'
import MethodTree from '@/components/shared/MethodTree'
import styles from './MethodSelector.module.css'

interface MethodSelectorProps {
  isOpen: boolean
  onClose: () => void
  onSelect: (methodId: string) => void
  currentMethodId?: string
}

export default function MethodSelector({ isOpen, onClose, onSelect, currentMethodId }: MethodSelectorProps) {
  const [activeMethodId, setActiveMethodId] = useState<string | null>(currentMethodId ?? null)
  const dialogRef = useRef<HTMLDivElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const closeHandler = useRef(onClose)
  const activeMethod = INITIAL_METHOD_TREE.flatMap(category => category.children ?? []).find(method => method.id === activeMethodId)
  const canConfirm = isCalculatorEnabled(activeMethodId ?? undefined)

  useEffect(() => { closeHandler.current = onClose }, [onClose])

  useEffect(() => {
    if (isOpen) setActiveMethodId(currentMethodId ?? null)
  }, [isOpen, currentMethodId])

  useEffect(() => {
    if (!isOpen) return
    const previousFocus = document.activeElement as HTMLElement | null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeHandler.current()
      if (event.key !== 'Tab') return
      const elements = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input, select, textarea, [tabindex="0"]') ?? [])
      const first = elements[0], last = elements[elements.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    document.addEventListener('keydown', keyboard)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', keyboard)
      previousFocus?.focus()
    }
  }, [isOpen])

  if (!isOpen) return null
  return <>
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className={styles.backdrop} onClick={onClose} />
    <motion.div ref={dialogRef} initial={{ x: '100%' }} animate={{ x: 0 }} transition={{ type: 'spring', damping: 30, stiffness: 260 }}
      role="dialog" aria-modal="true" aria-labelledby="calculator-method-title" className={styles.drawer}>
      <header className={styles.header}>
        <Settings2 size={22} aria-hidden="true" />
        <h2 id="calculator-method-title">选择估计方法</h2>
        <button ref={closeRef} type="button" aria-label="关闭方法库" onClick={onClose} className={styles.close}><X size={22} /></button>
      </header>
      <div className={styles.content}>
        <aside className={styles.treePane}>
          <MethodTree selectedId={activeMethodId} onSelect={setActiveMethodId} showAvailability label="计算器方法选择" />
        </aside>
        <div className={styles.details}>
          {activeMethod ? <>
            <div className={styles.detailBody}>
              <h3 className={styles.methodTitle}>{activeMethod.name}<span>{activeMethod.shortName}</span></h3>
              <MethodDetailContent key={activeMethod.id} method={activeMethod} />
            </div>
            <footer className={styles.footer}>
              <Link href={`/methods/${activeMethod.id}`} onClick={onClose} className={styles.detailLink}><ExternalLink size={17} />方法详情</Link>
              <button type="button" disabled={!canConfirm} className={styles.confirm} onClick={() => {
                if (canConfirm) { onSelect(activeMethod.id); onClose() }
              }}><CheckCircle size={18} />{canConfirm ? '确定选择' : '尚未开放计算'}</button>
            </footer>
          </> : <div className={styles.empty}><BookOpen size={32} aria-hidden="true" /><p>选择具体方法，查看详情</p></div>}
        </div>
      </div>
    </motion.div>
  </>
}
