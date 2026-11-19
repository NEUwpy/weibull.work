"use client"

import { useState, type ReactNode } from 'react'

export function ProcessDetails({ children, title = '查看计算细节' }: { children: ReactNode; title?: string }) {
  const [open, setOpen] = useState(false)
  return <details className="rounded-xl border border-slate-200 px-4 py-3" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary className="cursor-pointer text-base text-slate-600">{title}</summary>
    {open && <div className="mt-4 min-w-0 space-y-4">{children}</div>}
  </details>
}
