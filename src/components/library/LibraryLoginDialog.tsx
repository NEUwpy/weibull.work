"use client"

import React, { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ArrowRight, Eye, EyeOff, Loader2, LockKeyhole, X } from 'lucide-react'
import { libraryAuthClient, useLibrarySession } from '@/lib/library-auth-client'
import './login.css'

const loginCopy = {
  reading: { title: '登录，继续阅读', description: '登录后查看文献原文与译文。' },
  favorites: { title: '登录，使用收藏夹', description: '收藏夹随你的账号保存。' },
  account: { title: '登录图书馆账号', description: '登录后可查看个人收藏。' },
}
type LoginForm = 'sms' | 'password' | 'register'

export function LibraryLoginDialog({ open, onClose, container, purpose = 'reading' }: {
  open: boolean; onClose: () => void; container?: HTMLElement | null; purpose?: keyof typeof loginCopy
}) {
  const [mounted, setMounted] = useState(false)
  const [form, setForm] = useState<LoginForm>('sms')
  const [phone, setPhone] = useState('')
  const [credential, setCredential] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [sending, setSending] = useState(false)
  const [resend, setResend] = useState<{ phone: string; registering: boolean; at: number }>()
  const [countdown, setCountdown] = useState(0)
  const [now, setNow] = useState(Date.now)
  const { status, loginMode, registrationWindow } = useLibrarySession()
  const registering = loginMode === 'sms' && form === 'register'
  const sms = loginMode === 'sms' && form !== 'password'
  const registrationOpen = Boolean(registrationWindow && registrationWindow.opensAt <= now && now < registrationWindow.closesAt)
  const normalizedPhone = phone.trim().replace(/^\+?86(?=1[3-9]\d{9}$)/, '')
  const wait = resend?.phone === normalizedPhone && resend.registering === registering ? countdown : 0
  const working = busy || sending
  const passwordVisible = showPassword ? 'text' : 'password'
  const panel = useRef<HTMLDivElement>(null)
  const codeInput = useRef<HTMLInputElement>(null)
  const close = useRef(onClose)
  close.current = onClose
  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    if (!open) {
      setForm('sms'); setCredential(''); setNewPassword(''); setShowPassword(false); setError('')
      return
    }
    setNow(Date.now())
    void libraryAuthClient.refresh()
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
    if (!open || !resend) return
    const { at } = resend
    let timer: ReturnType<typeof setTimeout>
    function update() {
      const remaining = Math.max(0, Math.ceil((at - Date.now()) / 1000))
      setCountdown(remaining)
      if (remaining) timer = setTimeout(update, 1000)
    }
    update()
    return () => clearTimeout(timer)
  }, [open, resend])

  useEffect(() => {
    if (!open || !registrationWindow) return
    let timer: ReturnType<typeof setTimeout>
    const { opensAt, closesAt } = registrationWindow
    function update() {
      const current = Date.now()
      setNow(current)
      const next = current < opensAt ? opensAt : closesAt
      if (current < next) timer = setTimeout(update, Math.min(next - current, 2 ** 31 - 1))
    }
    update()
    return () => clearTimeout(timer)
  }, [open, registrationWindow])

  function switchForm(next: LoginForm) {
    setForm(next)
    setCredential('')
    setNewPassword('')
    setShowPassword(false)
    setError('')
    requestAnimationFrame(() => panel.current?.querySelector<HTMLInputElement>('input')?.focus())
  }

  async function sendCode() {
    if (working || wait > 0 || (registering && !registrationOpen)) return
    setError('')
    if (!/^(?:\+?86)?1[3-9]\d{9}$/.test(phone.trim())) {
      setError('请输入有效的中国大陆手机号。')
      return
    }
    setSending(true)
    try {
      const seconds = await libraryAuthClient.sendCode(normalizedPhone, registering ? 'register' : 'login')
      setCountdown(seconds)
      setResend({ phone: normalizedPhone, registering, at: Date.now() + seconds * 1000 })
      setCredential('')
      codeInput.current?.focus()
    } catch (cause) {
      setError(cause instanceof Error && cause.name !== 'TypeError' ? cause.message : '连接失败，请稍后重试。')
    } finally { setSending(false) }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (working || status === 'loading' || !loginMode || (registering && !registrationOpen)) return
    setError(''); setBusy(true)
    try {
      const result = registering
        ? await libraryAuthClient.register(normalizedPhone, credential, newPassword)
        : await libraryAuthClient.login(phone.trim(), credential, sms ? 'sms' : 'password')
      if (result.status === 'authenticated') { setCredential(''); setNewPassword(''); close.current() }
    } catch (cause) {
      setError(cause instanceof Error && cause.name !== 'TypeError' ? cause.message : '连接失败，请稍后重试。')
    } finally { setBusy(false) }
  }

  if (!mounted || !open) return null
  const passwordToggle = <button type="button" onClick={() => setShowPassword(visible => !visible)} aria-label={showPassword ? '隐藏密码' : '显示密码'}>
    {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
  </button>
  return createPortal(
    <div className="library-login-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}>
      <div ref={panel} role="dialog" aria-modal="true" aria-labelledby="library-login-title" aria-describedby="library-login-description" className="library-login-dialog">
        <button type="button" className="library-login-close" aria-label="关闭登录" onClick={onClose}><X size={20} /></button>
        <div className="library-login-emblem"><LockKeyhole size={26} strokeWidth={1.6} /></div>
        <p className="library-login-eyebrow">可靠性图书馆</p>
        <h2 id="library-login-title">{registering ? '注册图书馆账号' : loginCopy[purpose].title}</h2>
        <p id="library-login-description" className="library-login-description">{registering ? '验证手机号并设置登录密码。' : loginCopy[purpose].description}</p>
        {loginMode === 'sms' && !registering && <div className="library-login-options" role="group" aria-label="登录方式">
          <button type="button" disabled={working} aria-pressed={sms} onClick={() => switchForm('sms')}>短信登录</button>
          <button type="button" disabled={working} aria-pressed={!sms} onClick={() => switchForm('password')}>密码登录</button>
        </div>}
        <form onSubmit={submit} className="library-login-form">
          <label htmlFor="library-login-phone">手机号</label>
          <input id="library-login-phone" name="username" type="tel" inputMode="tel" autoComplete={sms && !registering ? 'tel' : 'username'} maxLength={20} required placeholder="请输入手机号" value={phone} readOnly={working} onChange={event => { setPhone(event.target.value); if (sms) setCredential('') }} />
          {sms ? <>
            <label htmlFor="library-login-code">短信验证码</label>
            <div className="library-login-code-row">
              <input ref={codeInput} id="library-login-code" name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required placeholder="6 位验证码" value={credential} onChange={event => setCredential(event.target.value.replace(/[^0-9]/g, ''))} aria-describedby={error ? 'library-login-error' : undefined} />
              <button type="button" disabled={working || wait > 0 || (registering && !registrationOpen)} onClick={sendCode}>{sending ? '发送中…' : wait > 0 ? `${wait} 秒后重发` : '获取验证码'}</button>
            </div>
          </> : loginMode && <>
            <label htmlFor="library-login-password">密码</label>
            <div className="library-login-password-row">
              <input id="library-login-password" name="password" type={passwordVisible} autoComplete="current-password" maxLength={256} required placeholder="请输入密码" value={credential} onChange={event => setCredential(event.target.value)} aria-describedby={error ? 'library-login-error' : undefined} />
              {passwordToggle}
            </div>
          </>}
          {registering && <>
            <label htmlFor="library-login-new-password">设置密码</label>
            <div className="library-login-password-row">
              <input id="library-login-new-password" name="new-password" type={passwordVisible} autoComplete="new-password" required placeholder="15 至 128 个字符" maxLength={256} value={newPassword} onChange={event => setNewPassword(event.target.value)} aria-describedby={error ? 'library-login-error' : undefined} />
              {passwordToggle}
            </div>
          </>}
          {error && <p id="library-login-error" role="alert" className="library-login-error">{error}</p>}
          {!loginMode && status !== 'loading'
            ? <button type="button" className="library-login-submit" onClick={() => { void libraryAuthClient.refresh() }}>重新加载登录</button>
            : <button type="submit" disabled={working || !loginMode || (registering && !registrationOpen)} className="library-login-submit">
              {busy ? <><Loader2 size={18} className="animate-spin" />{registering ? '正在注册' : '正在登录'}</> : <>{registering ? '注册并登录' : '登录并继续'}<ArrowRight size={18} /></>}
            </button>}
        </form>
        {loginMode === 'sms' && <div className="library-login-registration">
          {registering ? <>
            {!registrationOpen && <span role="status">注册暂未开放</span>}
            <button type="button" disabled={working} onClick={() => switchForm('sms')}>返回登录</button>
          </> : registrationOpen
            ? <button type="button" disabled={working} onClick={() => switchForm('register')}>注册账号</button>
            : <span>注册暂未开放</span>}
        </div>}
      </div>
    </div>, container || document.body,
  )
}
