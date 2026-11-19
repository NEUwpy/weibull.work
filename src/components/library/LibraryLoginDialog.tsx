"use client"

import React, { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ArrowRight, Loader2, LockKeyhole, X } from 'lucide-react'
import { libraryAuthClient, useLibrarySession } from '@/lib/library-auth-client'
import './login.css'

const loginCopy = {
  reading: { title: '登录，继续阅读', description: '登录后查看文献原文与译文。' },
  favorites: { title: '登录，使用收藏夹', description: '收藏夹随你的账号保存。' },
  account: { title: '登录图书馆账号', description: '登录后可查看个人收藏。' },
}

export function LibraryLoginDialog({ open, onClose, container, purpose = 'reading' }: {
  open: boolean; onClose: () => void; container?: HTMLElement | null; purpose?: keyof typeof loginCopy
}) {
  const [mounted, setMounted] = useState(false)
  const [phone, setPhone] = useState('')
  const [credential, setCredential] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [sending, setSending] = useState(false)
  const [resendAt, setResendAt] = useState(0)
  const [countdown, setCountdown] = useState(0)
  const { status, loginMode } = useLibrarySession()
  const sms = loginMode === 'sms'
  const panel = useRef<HTMLDivElement>(null)
  const codeInput = useRef<HTMLInputElement>(null)
  const close = useRef(onClose)
  close.current = onClose
  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    if (!open) { setCredential(''); setError(''); return }
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

  useEffect(() => {
    if (!open || !resendAt) return
    function update() { setCountdown(Math.max(0, Math.ceil((resendAt - Date.now()) / 1000))) }
    update()
    const timer = setInterval(update, 1000)
    return () => clearInterval(timer)
  }, [open, resendAt])

  async function sendCode() {
    if (busy || sending || countdown > 0) return
    setError('')
    if (!/^(?:\+?86)?1[3-9]\d{9}$/.test(phone.trim())) {
      setError('请输入有效的中国大陆手机号。')
      return
    }
    setSending(true)
    try {
      const seconds = await libraryAuthClient.sendCode(phone.trim())
      setCountdown(seconds)
      setResendAt(Date.now() + seconds * 1000)
      setCredential('')
      codeInput.current?.focus()
    } catch (cause) {
      setError(cause instanceof Error && cause.name !== 'TypeError' ? cause.message : '连接失败，请稍后重试。')
    } finally { setSending(false) }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (busy || sending || status === 'loading' || !loginMode) return
    setError(''); setBusy(true)
    try {
      const result = await libraryAuthClient.login(phone.trim(), credential, loginMode)
      if (result.status === 'authenticated') { setCredential(''); close.current() }
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
        <h2 id="library-login-title">{loginCopy[purpose].title}</h2>
        <p id="library-login-description" className="library-login-description">{sms ? '手机号即账号，首次验证成功会自动注册。' : loginCopy[purpose].description}</p>
        <form onSubmit={submit} className="library-login-form">
          <label htmlFor="library-login-phone">手机号</label>
          <input id="library-login-phone" name="username" type="tel" inputMode="tel" autoComplete={sms ? 'tel' : 'username'} maxLength={20} required placeholder="请输入手机号" value={phone} readOnly={sending || busy} onChange={event => { setPhone(event.target.value); if (sms) setCredential('') }} />
          {sms ? <>
            <label htmlFor="library-login-code">短信验证码</label>
            <div className="library-login-code-row">
              <input ref={codeInput} id="library-login-code" name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required placeholder="6 位验证码" value={credential} onChange={event => setCredential(event.target.value.replace(/[^0-9]/g, ''))} aria-describedby={error ? 'library-login-error' : undefined} />
              <button type="button" disabled={busy || sending || countdown > 0} onClick={sendCode}>{sending ? '发送中…' : countdown > 0 ? `${countdown} 秒后重发` : '获取验证码'}</button>
            </div>
          </> : loginMode === 'password' && <>
            <label htmlFor="library-login-password">密码</label>
            <input id="library-login-password" name="password" type="password" autoComplete="current-password" maxLength={256} required placeholder="请输入密码" value={credential} onChange={event => setCredential(event.target.value)} aria-invalid={Boolean(error)} aria-describedby={error ? 'library-login-error' : undefined} />
          </>}
          {error && <p id="library-login-error" role="alert" className="library-login-error">{error}</p>}
          {!loginMode && status !== 'loading'
            ? <button type="button" className="library-login-submit" onClick={() => { void libraryAuthClient.refresh() }}>重新加载登录</button>
            : <button type="submit" disabled={busy || sending || !loginMode} className="library-login-submit">{busy ? <><Loader2 size={18} className="animate-spin" />正在登录</> : <>登录并继续<ArrowRight size={18} /></>}</button>}
        </form>
      </div>
    </div>, container || document.body,
  )
}
