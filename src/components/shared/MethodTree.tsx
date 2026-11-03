'use client'

import Link from 'next/link'
import { Check, ChevronRight } from 'lucide-react'
import { INITIAL_METHOD_TREE } from '@/lib/methods'
import { isCalculatorEnabled } from '@/lib/method-status'
import styles from './MethodTree.module.css'

interface MethodTreeProps {
  selectedId?: string | null
  onSelect?: (methodId: string) => void
  showAvailability?: boolean
  showCategoryDescription?: boolean
  label?: string
}

/** The original methods overview is the shared presentation for all method pickers. */
export default function MethodTree({
  selectedId, onSelect, showAvailability = false, showCategoryDescription = false, label = '参数估计方法',
}: MethodTreeProps) {
  return <nav aria-label={label} className={`${styles.tree} space-y-4`} data-description={showCategoryDescription} onKeyDown={event => {
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
    const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('[data-method-id]'))
    const index = items.indexOf(document.activeElement as HTMLElement)
    event.preventDefault()
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1
      : index < 0 ? (event.key === 'ArrowUp' ? items.length - 1 : 0)
      : (index + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length
    items[next]?.focus()
  }}>
    {INITIAL_METHOD_TREE.map((category, index) => {
      const categoryInfo = <>
        <div className={`${styles.categoryTitleBox} w-[40%] p-5 pr-4 pl-[60px] max-[1279px]:pl-5 max-[767px]:w-full max-[767px]:p-4 flex flex-col justify-center shrink-0`}>
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 bg-amber-600 rounded-lg text-white shadow-sm shrink-0 flex items-center justify-center">
              <span className="text-lg font-black leading-none" style={{ fontFamily: 'Georgia, serif' }}>{index + 1}</span>
            </div>
            <span className="text-[14px] font-mono font-bold text-amber-600 bg-amber-50 px-2 py-1 rounded border border-amber-100 leading-tight">{category.shortName}</span>
          </div>
          <div className="text-lg font-black text-slate-900 leading-tight">{category.name}</div>
        </div>
        {showCategoryDescription && <>
          <div className="flex-none w-px bg-amber-200/50 my-5 max-[767px]:hidden" />
          <div className="flex-1 p-5 pr-6 max-[767px]:px-4 max-[767px]:pt-0 max-[767px]:pb-4 flex items-center">
            <div className="text-sm text-slate-500 leading-relaxed">{category.description}</div>
          </div>
        </>}
      </>
      const categoryClass = `${styles.categoryInfo} w-[40%] min-w-[320px] max-[1279px]:w-full max-[1279px]:min-w-0 max-[1279px]:border-r-0 max-[1279px]:border-b max-[767px]:flex-col flex bg-gradient-to-br from-amber-50 to-white border-r border-slate-100 hover:bg-amber-100/50 transition-colors`
      return <div key={category.id} className="block group" data-category-id={category.id}>
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 hover:shadow-md hover:border-amber-300 transition-all overflow-hidden">
          <div className={`${styles.row} flex h-[140px] max-[1279px]:h-auto max-[1279px]:flex-col`}>
            {onSelect ? <div className={categoryClass}>{categoryInfo}</div>
              : <Link href={`/methods/${category.id}`} className={categoryClass}>{categoryInfo}</Link>}
            <div className="flex-1 p-6 max-[1279px]:min-w-0 max-[767px]:p-4">
              <div className={`${styles.methodsList} flex items-center gap-3 overflow-x-auto scrollbar-hide h-full max-[1279px]:flex-wrap max-[1279px]:h-auto`}>
                {category.children?.length ? category.children.map(method => {
                  const card = <div className={`${styles.methodCard} px-7 py-4 max-[767px]:px-4 bg-slate-50 hover:bg-amber-50 border border-slate-200 hover:border-amber-300 rounded-xl transition-all cursor-pointer`}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-bold text-slate-700 group-hover/method:text-amber-700">{method.shortName}</span>
                      {showAvailability && !isCalculatorEnabled(method.id) && <span className={styles.availability}>未开放</span>}
                      {selectedId === method.id && <Check size={16} className="text-amber-600 shrink-0" aria-hidden="true" />}
                    </div>
                    <div className="text-sm text-slate-400 font-mono">{method.name}</div>
                  </div>
                  const methodClass = `${styles.method} flex-none group/method text-left`
                  return onSelect ? <button key={method.id} type="button" className={methodClass} data-method-id={method.id}
                    aria-pressed={selectedId === method.id} onClick={() => onSelect(method.id)}>{card}</button>
                    : <Link key={method.id} href={`/methods/${method.id}`} className={methodClass} data-method-id={method.id}
                      aria-current={selectedId === method.id ? 'page' : undefined}>{card}</Link>
                }) : <div className="text-sm text-slate-400 italic">暂无细分方法</div>}
                <div className={`${styles.trailingArrow} flex-none text-slate-300 max-[1279px]:hidden`}><ChevronRight size={20} /></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    })}
  </nav>
}
