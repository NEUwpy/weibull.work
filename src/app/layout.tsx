"use client"

import React from 'react'
import './globals.css'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Calculator, Library, Database, Settings2 } from 'lucide-react'
import { cn } from '@/lib/utils'

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const pathname = usePathname()
  const isLibrary = pathname.startsWith('/library')
  const isCases = pathname.startsWith('/cases')
  const isMethods = pathname.startsWith('/methods')

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
               
               <div className="flex flex-col items-end leading-tight hidden sm:flex">
                  <div className="text-sm text-slate-400 font-mono font-bold">
                     v3.0
                  </div>
                  <div className="text-[10px] text-slate-300 font-bold tracking-wider uppercase">
                     by wpyneu
                  </div>
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
