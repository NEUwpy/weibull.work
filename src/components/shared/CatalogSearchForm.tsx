'use client'

import { useEffect, useRef } from 'react'
import { Search } from 'lucide-react'
import './catalog-search.css'

type Props = {
  value: string
  onChange: (value: string) => void
  onSearch: () => void
  onAsk: () => void
  label: string
  placeholder: string
  searching?: boolean
  aiSearching?: boolean
  aiLabel?: string
}

function fitInput(input: HTMLTextAreaElement) {
  input.style.height = 'auto'
  input.style.height = `${Math.min(input.scrollHeight, 168)}px`
  input.style.overflowY = input.scrollHeight > 168 ? 'auto' : 'hidden'
}

export function CatalogSearchForm({ value, onChange, onSearch, onAsk, label, placeholder, searching, aiSearching, aiLabel = 'AI 问答' }: Props) {
  const input = useRef<HTMLTextAreaElement>(null)
  useEffect(() => { if (input.current) fitInput(input.current) }, [value])
  useEffect(() => {
    const element = input.current
    if (!element) return
    let width = 0
    const observer = new ResizeObserver(entries => {
      const next = entries[0].contentRect.width
      if (next !== width) { width = next; fitInput(element) }
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return <form onSubmit={event => { event.preventDefault(); onSearch() }} className="library-search-form flex items-start gap-3 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm focus-within:border-blue-300 focus-within:ring-2 focus-within:ring-blue-50">
    <Search size={21} className="library-search-icon shrink-0 text-slate-400" aria-hidden="true" />
    <textarea ref={input} aria-label={label} rows={1} maxLength={2000} value={value} onChange={event => onChange(event.target.value)}
      onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }}
      placeholder={placeholder} className="min-w-0 flex-1 resize-none bg-transparent py-3 text-sm leading-6 text-slate-700 outline-none" />
    <div className="library-search-actions grid shrink-0 grid-cols-2 gap-2">
      <button type="submit" disabled={searching} className="library-search-primary rounded-xl bg-blue-600 px-5 py-3 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60">搜索</button>
      <button type="button" onClick={onAsk} disabled={!value.trim() || aiSearching} className="library-search-primary rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-40">{aiSearching ? '查找中…' : aiLabel}</button>
    </div>
  </form>
}
