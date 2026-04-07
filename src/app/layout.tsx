"use client"

import React, { useState, useRef, useEffect } from 'react'
import './globals.css'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Calculator, Library, Database, Settings2, ChevronDown, BookOpen, FileText, Info } from 'lucide-react'
import { cn } from '@/lib/utils'
import { APP_VERSION } from '@/lib/config'

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const pathname = usePathname()
  const isLibrary = pathname.startsWith('/library')
  const isCases = pathname.startsWith('/cases')
  const isMethods = pathname.startsWith('/methods')
  const isHelp = pathname.startsWith('/help')
  const [infoOpen, setInfoOpen] = useState(false)
  const infoRef = useRef<HTMLDivElement>(null)

  // 点击外部关闭下拉
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (infoRef.current && !infoRef.current.contains(e.target as Node)) {
        setInfoOpen(false)
      }
    }
    if (infoOpen) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [infoOpen])

  let title = 'Weibull Calculator'
  let subtitle = '威布尔计算器'
  let Icon = Calculator
  let themeColor = 'bg-blue-600 shadow-blue-200'

  if (isLibrary) {
    title = 'Reliability Library'
    subtitle = '可靠性图书馆'
    Icon = Library
    themeColor = 'bg-emerald-600 shadow-emerald-200'
  } else if (isCases) {
    title = 'Case Database'
    subtitle = '案例数据库'
    Icon = Database
    themeColor = 'bg-indigo-600 shadow-indigo-200'
  } else if (isMethods) {
    title = 'Parameter Estimation Methods'
    subtitle = '参数估计方法'
    Icon = Settings2
    themeColor = 'bg-amber-600 shadow-amber-200'
  } else if (isHelp) {
    title = 'Help Center'
    subtitle = '帮助中心'
    Icon = BookOpen
    themeColor = 'bg-violet-600 shadow-violet-200'
  }

  return (
    <html lang="zh-CN">
      <body className="bg-slate-50 min-h-screen flex flex-col">
        {/* Global Immersive Header */}
        <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-slate-200">
          <div className="max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] h-16 flex items-center justify-between">
            {/* Left: Dynamic Title */}
            <div className="flex items-center gap-3">
               <div className={cn(
                 "p-2 rounded-lg text-white shadow-sm transition-colors",
                 themeColor
               )}>
                 <Icon size={20} />
               </div>
               <div className="flex flex-col">
                  <h1 className="text-lg font-bold text-slate-900 leading-none">
                    {title}
                  </h1>
                  <span className="text-sm text-slate-500 font-medium tracking-wide mt-0.5">
                    {subtitle}
                  </span>
               </div>
            </div>

            {/* Right: Navigation Switcher */}
            <div className="flex items-center gap-8">
               {/* Segmented Control */}
               <div className="flex bg-slate-100/80 p-1 rounded-xl border border-slate-200/50">
                  <Link
                    href="/"
                    className={cn(
                      "px-5 py-2 rounded-lg text-base font-bold flex items-center gap-2 transition-all whitespace-nowrap",
                      !isLibrary && !isCases && !isMethods
                        ? "bg-white text-blue-600 shadow-sm ring-1 ring-black/5"
                        : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"
                    )}
                  >
                    <Calculator size={18} />
                    威布尔计算器
                  </Link>
                  <Link
                    href="/methods"
                    className={cn(
                      "px-5 py-2 rounded-lg text-base font-bold flex items-center gap-2 transition-all whitespace-nowrap",
                      isMethods
                        ? "bg-white text-amber-600 shadow-sm ring-1 ring-black/5"
                        : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"
                    )}
                  >
                    <Settings2 size={18} />
                    参数估计方法
                  </Link>
                  <Link
                    href="/cases"
                    className={cn(
                      "px-5 py-2 rounded-lg text-base font-bold flex items-center gap-2 transition-all whitespace-nowrap",
                      isCases
                        ? "bg-white text-indigo-600 shadow-sm ring-1 ring-black/5"
                        : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"
                    )}
                  >
                    <Database size={18} />
                    案例数据库
                  </Link>
                  <Link
                    href="/library"
                    className={cn(
                      "px-5 py-2 rounded-lg text-base font-bold flex items-center gap-2 transition-all whitespace-nowrap",
                      isLibrary
                        ? "bg-white text-emerald-600 shadow-sm ring-1 ring-black/5"
                        : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"
                    )}
                  >
                    <Library size={18} />
                    可靠性图书馆
                  </Link>
               </div>
               
               {/* Software Info Dropdown */}
               <div ref={infoRef} className="relative hidden sm:block">
                  <button
                    onClick={() => setInfoOpen(!infoOpen)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                  >
                    <Info size={14} />
                    <span className="font-medium">软件信息</span>
                    <ChevronDown size={12} className={cn("transition-transform", infoOpen && "rotate-180")} />
                  </button>

                  {infoOpen && (
                    <div className="absolute right-0 top-full mt-2 w-56 bg-white rounded-xl shadow-lg ring-1 ring-black/5 border border-slate-200 py-1 z-50">
                      {/* Version */}
                      <div className="px-4 py-2.5 border-b border-slate-100">
                        <div className="text-xs text-slate-400 font-medium">版本号</div>
                        <div className="text-sm text-slate-700 font-mono font-bold mt-0.5">{APP_VERSION}</div>
                      </div>

                      {/* Menu Items */}
                      <div className="py-1">
                        <Link
                          href="/help/manual/about"
                          onClick={() => setInfoOpen(false)}
                          className="flex items-center gap-3 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors"
                        >
                          <BookOpen size={16} className="text-slate-400" />
                          用户手册
                        </Link>
                        <Link
                          href="/help/changelog"
                          onClick={() => setInfoOpen(false)}
                          className="flex items-center gap-3 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors"
                        >
                          <FileText size={16} className="text-slate-400" />
                          更新日志
                        </Link>
                      </div>

                      {/* Footer */}
                      <div className="px-4 py-2 border-t border-slate-100">
                        <div className="text-[10px] text-slate-300 font-bold tracking-wider uppercase">
                          by wpyneu
                        </div>
                      </div>
                    </div>
                  )}
                </div>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <div className="flex-1 relative">
           {children}
        </div>
      </body>
    </html>
  )
}
