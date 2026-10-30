"use client"

import React, { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ArrowRight, Loader2, LockKeyhole, X } from 'lucide-react'
import { libraryAuthClient } from '@/lib/library-auth-client'
import './login.css'

export function LibraryLoginDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [mounted, setMounted] = useState(false)
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const panel = useRef<HTMLDivElement>(null)
  const close = useRef(onClose)
  close.current = onClose
  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    if (!open) { setPassword(''); setError(''); return }
    const previousFocus = document.activeElement as HTMLElement | null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const frame = requestAnimationFrame(() => panel.current?.querySelector<HTMLInputElement>('input')?.focus())
    function handleKey(event: KeyboardEvent) {
      if (event.key === 'Escape') { event.preventDefault(); close.current(); return }
      if (event.key !== 'Tab') return
      const controls = Array.from(panel.current?.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), a[href]') ?? [])
      if (!controls.length) return
      const first = controls[0]
      const last = controls[controls.length - 1]
      if (event.shiftKey && (document.activeElement === first || !panel.current?.contains(document.activeElement))) {
        event.preventDefault(); last.focus()
      } else if (!event.shiftKey && (document.activeElement === last || !panel.current?.contains(document.activeElement))) {
        event.preventDefault(); first.focus()
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => {
      cancelAnimationFrame(frame)
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', handleKey)
      previousFocus?.focus()
    }
  }, [open])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (busy) return
    setError(''); setBusy(true)
    try {
      const result = await libraryAuthClient.login(phone.trim(), password)
      if (result.status === 'authenticated') { setPassword(''); close.current() }
    } catch (cause) {
      setError(cause instanceof Error && cause.name !== 'TypeError' ? cause.message : '连接失败，请稍后重试。')
    } finally { setBusy(false) }
  }

  if (!mounted || !open) return null
  return createPortal(
    <div className="library-login-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}>
      <div ref={panel} role="dialog" aria-modal="true" aria-labelledby="library-login-title" aria-describedby="library-login-description" className="library-login-dialog">
        <button type="button" className="library-login-close" aria-label="关闭登录" onClick={onClose}><X size={20} /></button>
        <div className="library-login-emblem"><LockKeyhole size={26} strokeWidth={1.6} /></div>
        <p className="library-login-eyebrow">可靠性图书馆</p>
        <h2 id="library-login-title">登录，继续阅读</h2>
        <p id="library-login-description" className="library-login-description">登录后查看文献原文与译文。</p>
        <form onSubmit={submit} className="library-login-form">
          <label htmlFor="library-login-phone">手机号</label>
          <input id="library-login-phone" name="username" type="tel" inputMode="tel" autoComplete="username" maxLength={20} required placeholder="请输入手机号" value={phone} onChange={event => setPhone(event.target.value)} />
          <label htmlFor="library-login-password">密码</label>
          <input id="library-login-password" name="password" type="password" autoComplete="current-password" maxLength={256} required placeholder="请输入密码" value={password} onChange={event => setPassword(event.target.value)} aria-invalid={Boolean(error)} aria-describedby={error ? 'library-login-error' : undefined} />
          {error && <p id="library-login-error" role="alert" className="library-login-error">{error}</p>}
          <button type="submit" disabled={busy} className="library-login-submit">{busy ? <><Loader2 size={18} className="animate-spin" />正在登录</> : <>登录并继续<ArrowRight size={18} /></>}</button>
        </form>
        <p className="library-login-note">仅限已开放账号 · 暂未开放注册</p>
      </div>
    </div>, document.body,
  )
}
