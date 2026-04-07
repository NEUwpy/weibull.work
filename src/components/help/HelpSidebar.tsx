"use client"

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'

const NAV_STRUCTURE = [
  {
    group: '用户手册',
    items: [
      { label: '软件结构', href: '/help/manual/about' },
      { label: '功能详情', href: '/help/manual/features' },
      { label: '工作流介绍', href: '/help/manual/workflow' },
    ]
  },
  {
    group: '更新日志',
    items: [
      { label: '功能状态', href: '/help/changelog' },
      { label: '版本记录', href: '/help/changelog/versions' },
      { label: '更新计划', href: '/help/changelog/todos' },
    ]
  },
]

export default function HelpSidebar() {
  const pathname = usePathname()

  return (
    <aside className="hidden lg:block w-64 shrink-0 sticky top-24 max-h-[calc(100vh-8rem)] overflow-y-auto pr-6">
      {NAV_STRUCTURE.map(group => (
        <div key={group.group} className="mb-6">
          <div className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">
            {group.group}
          </div>
          <nav className="space-y-1">
            {group.items.map(item => {
              const isActive = pathname === item.href
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "block py-2 px-3 text-sm rounded-lg transition-colors",
                    isActive
                      ? "text-blue-600 bg-blue-50 font-bold"
                      : "text-slate-500 hover:text-slate-800 hover:bg-slate-50"
                  )}
                >
                  {item.label}
                </Link>
              )
            })}
          </nav>
        </div>
      ))}
    </aside>
  )
}
