'use client'

import { useEffect, useId, useRef, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { BookOpen, ChevronDown, FileText, Info, LogIn, LogOut, Star, User } from 'lucide-react'
import { APP_VERSION } from '@/lib/config'
import { libraryAuthClient, maskLibraryPhone, useLibrarySession } from '@/lib/library-auth-client'
import { libraryFavoritesHref } from '@/lib/library-favorites'
import { cn } from '@/lib/utils'

const items = [
  { id: 'software', label: '软件信息', Icon: Info },
  { id: 'user', label: '用户信息', Icon: User },
] as const
const row = 'flex w-full items-center gap-3 px-4 py-2 text-left text-sm text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900'

export function SiteInfoMenus({ compact, onLogin, onNavigate }: {
  compact?: boolean
  onLogin: () => void
  onNavigate?: () => void
}) {
  const pathname = usePathname()
  const panelId = useId()
  const group = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState<typeof items[number]['id'] | null>(null)

  useEffect(() => { setOpen(null) }, [pathname])
  useEffect(() => {
    if (!open) return
    function closeOutside(event: PointerEvent) {
      if (!group.current?.contains(event.target as Node)) setOpen(null)
    }
    document.addEventListener('pointerdown', closeOutside)
    return () => document.removeEventListener('pointerdown', closeOutside)
  }, [open])

  function closeToTrigger() {
    if (open) document.getElementById(`${panelId}-${open}`)?.focus({ preventScroll: true })
    setOpen(null)
  }

  function followLink() {
    setOpen(null)
    onNavigate?.()
  }

  return <div ref={group} className={cn('relative', compact && 'col-span-full mt-1 border-t border-slate-100 pt-2')}
    onBlur={event => { if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget)) setOpen(null) }}
    onKeyDown={event => {
      if (event.key === 'Escape' && open) {
        event.preventDefault()
        event.stopPropagation()
        closeToTrigger()
      }
    }}>
    <div className={cn('items-center gap-1', compact ? 'grid grid-cols-2' : 'flex')}>
      {items.map(({ id, label, Icon }) => <button key={id} id={`${panelId}-${id}`} type="button" aria-expanded={open === id}
        aria-controls={open === id ? panelId : undefined} onClick={() => setOpen(current => current === id ? null : id)}
        className={cn('flex items-center gap-1.5 whitespace-nowrap rounded-lg text-sm font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700 aria-expanded:bg-slate-100 aria-expanded:text-slate-800',
          compact ? 'min-h-11 px-4' : 'min-h-9 px-2.5')}>
        <Icon size={15} aria-hidden="true" />{label}
        <ChevronDown size={12} aria-hidden="true" className={cn('transition-transform', open === id && 'rotate-180')} />
      </button>)}
    </div>
    {open && <div id={panelId} role="region" aria-labelledby={`${panelId}-${open}`}
      className={cn('mt-2 rounded-xl border border-slate-200 bg-white py-1', compact ? 'mb-1' : 'absolute top-full z-50 w-56 shadow-lg ring-1 ring-black/5', !compact && (open === 'software' ? 'right-1/2' : 'right-0'))}>
      {open === 'software' ? <>
        <div className="border-b border-slate-100 px-4 py-2.5">
          <div className="text-xs font-medium text-slate-400">版本号</div>
          <div className="mt-0.5 font-mono text-sm font-bold text-slate-700">{APP_VERSION}</div>
        </div>
        <div className="py-1">
          <Link href="/help/manual/about" onClick={followLink} className={row}><BookOpen size={16} className="text-slate-400" aria-hidden="true" />用户手册</Link>
          <Link href="/help/changelog" onClick={followLink} className={row}><FileText size={16} className="text-slate-400" aria-hidden="true" />更新日志</Link>
        </div>
        <div className="border-t border-slate-100 px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-slate-300">by wpyneu</div>
      </> : <UserInfo onNavigate={followLink} onLogin={() => { closeToTrigger(); onLogin() }} />}
    </div>}
  </div>
}

function UserInfo({ onNavigate, onLogin }: { onNavigate: () => void; onLogin: () => void }) {
  const session = useLibrarySession()
  const [error, setError] = useState('')
  const signedIn = session.status === 'authenticated'
  const phone = session.user && maskLibraryPhone(session.user.phone)
  async function logout() {
    setError('')
    try { await libraryAuthClient.logout() }
    catch (cause) { setError(cause instanceof Error ? cause.message : '退出未完成，请重试。') }
  }

  return <>
    <div className="border-b border-slate-100 px-4 py-2.5 text-sm text-slate-600">
      {session.status === 'loading' ? '正在确认登录状态…' : signedIn ? `已登录${phone ? ` · ${phone}` : ''}` : '未登录'}
    </div>
    <Link href={libraryFavoritesHref()} prefetch={false} onClick={onNavigate} className={row}>
      <Star size={16} className="text-slate-400" aria-hidden="true" />收藏夹
    </Link>
    {session.status !== 'loading' && (signedIn
      ? <button type="button" onClick={logout} className={row}><LogOut size={16} className="text-slate-400" aria-hidden="true" />退出登录</button>
      : <button type="button" onClick={onLogin} className={row}><LogIn size={16} className="text-slate-400" aria-hidden="true" />登录</button>)}
    {error && <p role="alert" className="px-4 pb-2 text-xs leading-5 text-rose-700">{error}</p>}
  </>
}
