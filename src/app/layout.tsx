"use client"

import React, { useState, useRef, useEffect } from 'react'
import './globals.css'
import './site-shell.css'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Calculator, Library, Database, Settings2, SlidersHorizontal, Info, Cpu, Menu, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { SiteInfoMenus } from '@/components/shared/SiteInfoMenus'
import { LibraryLoginDialog } from '@/components/library/LibraryLoginDialog'

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
  const [loginOpen, setLoginOpen] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const menuButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => { setMobileNavOpen(false) }, [pathname])

  useEffect(() => {
    if (!mobileNavOpen) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !event.defaultPrevented) {
        setMobileNavOpen(false)
        menuButtonRef.current?.focus()
      }
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [mobileNavOpen])

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
          <div className="site-header-inner page-shell site-aligned-shell h-16 flex items-center justify-between">
            {/* Left: Dynamic Title */}
            <div className="site-title flex items-center gap-3">
               <Link
                 href={homeHref}
                 aria-label={homeLabel}
                 title={homeLabel}
                 onClick={event => {
                   setMobileNavOpen(false)
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
            <div className="desktop-navigation flex shrink-0 items-center gap-4 2xl:gap-6">
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
               <SiteInfoMenus onLogin={() => setLoginOpen(true)} />
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
              <SiteInfoMenus compact onNavigate={() => setMobileNavOpen(false)} onLogin={() => {
                menuButtonRef.current?.focus()
                setMobileNavOpen(false)
                setLoginOpen(true)
              }} />
            </nav>
          )}
        </header>

        {/* Main Content */}
        <div className="flex-1 relative">
           {children}
        </div>
        <LibraryLoginDialog open={loginOpen} purpose="account" onClose={() => setLoginOpen(false)} />
      </body>
    </html>
  )
}
