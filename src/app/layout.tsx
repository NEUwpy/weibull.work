"use client"

import React, { useState, useRef, useEffect } from 'react'
import './globals.css'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Calculator, Library, Database, Settings2, SlidersHorizontal, ChevronDown, BookOpen, FileText, Info, Cpu, Menu, X } from 'lucide-react'
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
  const isAI = pathname.startsWith('/ai')
  const isHelp = pathname.startsWith('/help')
  const [infoOpen, setInfoOpen] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const infoRef = useRef<HTMLDivElement>(null)
  const menuButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => { setMobileNavOpen(false) }, [pathname])

  useEffect(() => {
    if (!mobileNavOpen) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMobileNavOpen(false)
        menuButtonRef.current?.focus()
      }
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [mobileNavOpen])

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
  let themeColor = 'bg-blue-50 text-blue-600 border-blue-200'
  let homeHref = '/'

  if (isLibrary) {
    title = 'Reliability Library'
    subtitle = '可靠性图书馆'
    Icon = Library
    themeColor = 'bg-emerald-50 text-emerald-600 border-emerald-200'
    homeHref = '/library'
  } else if (isAI) {
    title = 'AI Methods'
    subtitle = '人工智能方法'
    Icon = Cpu
    themeColor = 'bg-violet-50 text-violet-600 border-violet-200'
    homeHref = '/ai'
  } else if (isCases) {
    title = 'Case Database'
    subtitle = '案例数据库'
    Icon = Database
    themeColor = 'bg-indigo-50 text-indigo-600 border-indigo-200'
    homeHref = '/cases'
  } else if (isMethods) {
    title = 'Parameter Estimation Methods'
    subtitle = '参数估计方法'
    Icon = SlidersHorizontal
    themeColor = 'bg-amber-50 text-amber-600 border-amber-200'
    homeHref = '/methods'
  } else if (isHelp) {
    title = 'Software Info'
    subtitle = '软件信息'
    Icon = Info
    themeColor = 'bg-slate-100 text-slate-600 border-slate-300'
    homeHref = '/help'
  }

  const homeLabel = isMethods ? '返回方法总览' : `返回${subtitle}主页`

  return (
    <html lang="zh-CN">
      <body className="bg-slate-50 min-h-screen flex flex-col">
        {/* Global Immersive Header */}
        <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-slate-200">
          <div className="site-header-inner page-shell max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] h-16 flex items-center justify-between">
            {/* Left: Dynamic Title */}
            <div className="site-title flex items-center gap-3">
               <Link
                 href={homeHref}
                 aria-label={homeLabel}
                 title={homeLabel}
                 onClick={event => {
                   setMobileNavOpen(false); setInfoOpen(false)
                   if (!event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) window.dispatchEvent(new CustomEvent('weibull:module-home', { detail: homeHref }))
                 }}
                 className={cn("site-title-icon rounded-[9px] border transition-colors hover:brightness-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2", themeColor)}
               >
                 <Icon size={26} strokeWidth={1.7} aria-hidden="true" />
               </Link>
               <div className="flex flex-col">
                  <h1 className="text-lg font-bold text-slate-900 leading-none">
                    {title}
                  </h1>
                  <span className="text-sm text-slate-500 font-medium tracking-wide mt-1">
                    {subtitle}
                  </span>
               </div>
            </div>

            {/* Right: Navigation Switcher */}
            <div className="desktop-navigation flex items-center gap-8">
               {/* Segmented Control */}
               <div className="site-navigation-frame flex bg-slate-100/80 p-1 rounded-xl border border-slate-200/50">
                  <Link
                    href="/"
                    className={cn(
                      "px-5 py-2 rounded-lg text-base font-bold flex items-center gap-2 transition-all whitespace-nowrap",
                      !isLibrary && !isCases && !isMethods && !isAI
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
                    href="/ai"
                    className={cn(
                      "px-5 py-2 rounded-lg text-base font-bold flex items-center gap-2 transition-all whitespace-nowrap",
                      isAI
                        ? "bg-white text-violet-600 shadow-sm ring-1 ring-black/5"
                        : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"
                    )}
                  >
                    <Cpu size={18} />
                    人工智能方法
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
            <button
              ref={menuButtonRef}
              type="button"
              aria-label={mobileNavOpen ? '关闭导航菜单' : '打开导航菜单'}
              aria-expanded={mobileNavOpen}
              aria-controls="compact-navigation"
              onClick={() => setMobileNavOpen(open => !open)}
              className="compact-navigation-toggle items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600"
            >
              {mobileNavOpen ? <X size={22} /> : <Menu size={22} />}
            </button>
          </div>
          {mobileNavOpen && (
            <nav id="compact-navigation" aria-label="网站导航" className="compact-navigation border-t border-slate-200 bg-white">
              {[
                { href: '/', label: '威布尔计算器', Icon: Calculator },
                { href: '/methods', label: '参数估计方法', Icon: Settings2 },
                { href: '/ai', label: '人工智能方法', Icon: Cpu },
                { href: '/cases', label: '案例数据库', Icon: Database },
                { href: '/library', label: '可靠性图书馆', Icon: Library },
                { href: '/help/manual/about', label: '用户手册', Icon: BookOpen },
                { href: '/help/changelog', label: '更新日志', Icon: FileText },
              ].map(item => (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileNavOpen(false)}
                  aria-current={(item.href === '/' ? pathname === '/' : pathname.startsWith(item.href)) ? 'page' : undefined}
                  className="flex items-center gap-3 rounded-lg px-4 py-3 text-sm font-bold text-slate-600 hover:bg-slate-50 aria-[current=page]:bg-blue-50 aria-[current=page]:text-blue-600"
                >
                  <item.Icon size={18} />{item.label}
                </Link>
              ))}
              <span className="px-4 py-3 text-xs text-slate-400">{APP_VERSION}</span>
            </nav>
          )}
        </header>

        {/* Main Content */}
        <div className="flex-1 relative">
           {children}
        </div>
      </body>
    </html>
  )
}
