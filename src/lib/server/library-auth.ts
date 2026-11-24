import { createHmac, randomBytes, randomInt, scrypt, timingSafeEqual } from 'node:crypto'
import { librarySmsSender } from './library-sms-provider'
import { acceptLibrarySms, getLibraryPasswordHash, markLibrarySmsSent, readLibrarySmsSession, reserveLibrarySms, revokeLibrarySmsSession, startLibraryPasswordSession } from './library-sms-store'
import { isLibraryRegistrationOpen, libraryRegistrationWindow } from './library-registration'

const COOKIE_NAME = 'weibull_library_session'
const SESSION_SECONDS = 7 * 24 * 60 * 60
const RETRY_WINDOW_MS = 15 * 60 * 1000
const MAX_ATTEMPTS = 6
const PRIVATE_HEADERS = { 'Cache-Control': 'private, no-store', Vary: 'Cookie' }
const DUMMY_PASSWORD_HASH = `scrypt:${'0'.repeat(32)}:${'0'.repeat(128)}`

interface AuthConfig { phone: string; passwordHash: string; secret: string }
export interface LibrarySession {
  authenticated: boolean
  user?: { phone: string; canRead?: boolean }
  expiresAt?: number
  legacyAccountId?: string | null
}

const loginMode = () => process.env.WEIBULL_LIBRARY_AUTH_MODE === 'password' ? 'password' : 'sms'
const smsSecret = () => (process.env.WEIBULL_SESSION_SECRET || '').length >= 32 ? process.env.WEIBULL_SESSION_SECRET! : ''

function smsModeUser(phone: string) {
  return { phone, canRead: phone === process.env.WEIBULL_LIBRARY_PHONE }
}

function configuration(): AuthConfig | null {
  const phone = process.env.WEIBULL_LIBRARY_PHONE || ''
  const passwordHash = process.env.WEIBULL_LIBRARY_PASSWORD_HASH || ''
  const secret = process.env.WEIBULL_SESSION_SECRET || ''
  return /^1\d{10}$/.test(phone) && /^scrypt:[a-f0-9]{32}:[a-f0-9]{128}$/i.test(passwordHash) && secret.length >= 32
    ? { phone, passwordHash, secret } : null
}

function signature(value: string, config: AuthConfig): string {
  // Changing the account, password hash or signing secret invalidates previous sessions.
  return createHmac('sha256', config.secret).update(`${config.phone}\0${config.passwordHash}\0${value}`).digest('base64url')
}

function sameString(left: string, right: string): boolean {
  const a = Buffer.from(left)
  const b = Buffer.from(right)
  return a.length === b.length && timingSafeEqual(a, b)
}

function cookieValue(request: Request): string {
  const entry = request.headers.get('cookie')?.split(';').map(part => part.trim()).find(part => part.startsWith(`${COOKIE_NAME}=`))
  return entry?.slice(COOKIE_NAME.length + 1) || ''
}

function isHttps(request: Request): boolean {
  return new URL(request.url).protocol === 'https:' || request.headers.get('x-forwarded-proto')?.split(',')[0].trim() === 'https'
}

function sessionCookie(request: Request, value: string, maxAge: number): string {
  return `${COOKIE_NAME}=${value}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}${isHttps(request) ? '; Secure' : ''}`
}

export function getLibrarySession(request: Request, now = Date.now()): LibrarySession {
  const token = cookieValue(request)
  if (loginMode() === 'sms') {
    const secret = smsSecret()
    if (!secret || !/^[A-Za-z0-9_-]{43}$/.test(token)) return { authenticated: false }
    try {
      const row = readLibrarySmsSession(token, secret, now)
      if (row) return { authenticated: true, user: smsModeUser(row.phone), expiresAt: row.expires_at, legacyAccountId: row.legacy_account_id }
    } catch (error) { console.error('[library-sms] Session read failed', (error as Error).name) }
    return { authenticated: false }
  }
  const config = configuration()
  if (!config || token.length > 1024 || !/^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]{43}$/.test(token)) return { authenticated: false }
  const [value, signed] = token.split('.')
  if (!sameString(signed, signature(value, config))) return { authenticated: false }
  try {
    const payload = JSON.parse(Buffer.from(value, 'base64url').toString('utf8'))
    const seconds = Math.floor(now / 1000)
    if (payload.v !== 1 || payload.phone !== config.phone || !Number.isInteger(payload.iat) || !Number.isInteger(payload.exp) ||
      payload.iat > seconds + 30 || payload.exp <= seconds || payload.exp - payload.iat !== SESSION_SECONDS) return { authenticated: false }
    return { authenticated: true, user: { phone: config.phone }, expiresAt: payload.exp * 1000 }
  } catch { return { authenticated: false } }
}

export function requireLibraryLogin(request: Request): Response | null {
  const session = getLibrarySession(request)
  if (session.user?.canRead === false) return Response.json({
    error: '此账号尚未开通全文及单篇问答权限。', code: 'LIBRARY_ACCESS_DENIED',
  }, { status: 403, headers: PRIVATE_HEADERS })
  return session.authenticated ? null : Response.json({
    error: '请登录后阅读原文或译文。', code: 'AUTH_REQUIRED',
  }, { status: 401, headers: PRIVATE_HEADERS })
}

export function librarySessionResponse(request: Request): Response {
  const { authenticated, user, expiresAt } = getLibrarySession(request)
  const mode = loginMode()
  return Response.json({
    authenticated, user, expiresAt, loginMode: mode,
    registrationWindow: mode === 'sms' ? libraryRegistrationWindow() : null,
  }, { headers: PRIVATE_HEADERS })
}

export function isLibrarySameOrigin(request: Request): boolean {
  if (request.headers.get('sec-fetch-site') === 'cross-site') return false
  const origin = request.headers.get('origin')
  if (!origin) return false
  try {
    const url = new URL(request.url)
    const host = request.headers.get('x-forwarded-host')?.split(',')[0].trim() || request.headers.get('host') || url.host
    const protocol = isHttps(request) ? 'https:' : 'http:'
    return new URL(origin).origin === `${protocol}//${host}`
  } catch { return false }
}

interface Attempt { count: number; until: number }
const attemptKey = Symbol.for('weibull.library-login-attempts.v1')
const shared = globalThis as unknown as Record<symbol, Map<string, Attempt>>
const attempts = shared[attemptKey] ??= new Map<string, Attempt>()

function requestSource(request: Request) {
  // Cloudflare supplies CF-Connecting-IP; the local fallback is deliberately shared.
  return (request.headers.get('cf-connecting-ip') || request.headers.get('x-forwarded-for')?.split(',')[0] || 'local').trim().slice(0, 100)
}

function attemptFor(key: string, now: number): Attempt {
  for (const [ip, value] of Array.from(attempts)) if (value.until <= now) attempts.delete(ip)
  if (attempts.size >= 1000 && !attempts.has(key)) attempts.delete(attempts.keys().next().value!)
  let attempt = attempts.get(key)
  if (!attempt) { attempt = { count: 0, until: now + RETRY_WINDOW_MS }; attempts.set(key, attempt) }
  return attempt
}

function derivePassword(password: string, salt: string) {
  // The configured salt is its hex text, matching the credential setup command.
  return new Promise<Buffer>((resolve, reject) => {
    scrypt(password, salt, 64, (error, key) => error ? reject(error) : resolve(key))
  })
}

async function validPassword(password: string, passwordHash: string): Promise<boolean> {
  const [, salt, expected] = passwordHash.split(':')
  const derived = await derivePassword(password, salt)
  return timingSafeEqual(derived, Buffer.from(expected, 'hex'))
}

async function readAuthInput(request: Request): Promise<Record<string, unknown> | null> {
  if (!request.headers.get('content-type')?.includes('application/json') || Number(request.headers.get('content-length')) > 2048) return null
  try {
    const body = await request.text()
    if (body.length > 2048) return null
    const input = JSON.parse(body)
    return input && typeof input === 'object' && !Array.isArray(input) ? input : null
  } catch { return null }
}

function mobileNumber(value: unknown) {
  return typeof value === 'string' ? /^(?:\+?86)?(1[3-9]\d{9})$/.exec(value.trim())?.[1] : undefined
}

function authFailure(error: string, status: number, retryAfter?: number) {
  return Response.json({ error, retryAfter }, {
    status, headers: retryAfter ? { ...PRIVATE_HEADERS, 'Retry-After': String(retryAfter) } : PRIVATE_HEADERS,
  })
}

function registrationClosed() {
  return authFailure('注册暂未开放。', 403)
}

export async function sendLibraryLoginCode(request: Request): Promise<Response> {
  if (!isLibrarySameOrigin(request)) return authFailure('请在本站页面获取验证码。', 403)
  const input = await readAuthInput(request)
  const phone = mobileNumber(input?.phone)
  if (!phone) return authFailure('请输入有效的中国大陆手机号。', 400)
  const purpose = input?.purpose ?? 'login'
  if (purpose !== 'login' && purpose !== 'register') return authFailure('验证码请求无效。', 400)
  if (purpose === 'register' && (loginMode() !== 'sms' || !isLibraryRegistrationOpen())) return registrationClosed()
  const secret = smsSecret()
  const localCode = process.env.WEIBULL_SMS_LOCAL_CODE || ''
  const local = process.env.NODE_ENV === 'development' && /^\d{6}$/.test(localCode) &&
    ['localhost', '127.0.0.1', '[::1]'].includes(new URL(request.headers.get('origin')!).hostname) &&
    !request.headers.has('cf-connecting-ip')
  const send = local ? null : librarySmsSender()
  if (loginMode() !== 'sms' || !secret || (!local && !send)) return authFailure('短信服务暂未开通。', 503)
  try {
    const client = request.headers.get('cf-connecting-ip')?.slice(0, 100) || 'local'
    const reservation = reserveLibrarySms(phone, purpose, client, secret)
    if (reservation.status === 'closed') return registrationClosed()
    if (reservation.status === 'limited') return authFailure('获取验证码过于频繁，请稍后再试。', 429, reservation.retryAfter)
    if (reservation.status === 'reserved') {
      const code = local ? localCode : String(randomInt(1_000_000)).padStart(6, '0')
      if (send) await send(phone, code)
      markLibrarySmsSent(reservation.id, code, secret)
    }
    return Response.json({ resendAfter: reservation.resendAfter }, { headers: PRIVATE_HEADERS })
  } catch (error) {
    console.error('[library-sms] Send failed', (error as Error).name)
    return authFailure('验证码暂时无法发送，请稍后再试。', 503)
  }
}

function accountSessionResponse(request: Request, phone: string, token: string, expiresAt: number) {
  return Response.json({ authenticated: true, user: smsModeUser(phone), expiresAt }, {
    headers: { ...PRIVATE_HEADERS, 'Set-Cookie': sessionCookie(request, token, SESSION_SECONDS) },
  })
}

async function loginLibraryWithCode(request: Request, input: Record<string, unknown> | null, registering = false) {
  const secret = smsSecret()
  if (!secret) return authFailure('登录暂时不可用，请稍后重试。', 503)
  const phone = mobileNumber(input?.phone)
  const code = typeof input?.code === 'string' ? input.code.trim() : ''
  if (!phone || !/^\d{6}$/.test(code)) return authFailure('请填写手机号和 6 位验证码。', 400)
  try {
    let passwordHash: string | undefined
    if (registering) {
      const password = typeof input?.password === 'string' ? input.password.normalize('NFC') : ''
      const length = Array.from(password).length
      if (length < 15 || length > 128 || !password.trim()) return authFailure('请设置 15 至 128 个字符的密码。', 400)
      const now = Date.now()
      const attempt = attemptFor(`register:${requestSource(request)}`, now)
      if (attempt.count >= MAX_ATTEMPTS) return authFailure('注册尝试次数过多，请稍后再试。', 429, Math.ceil((attempt.until - now) / 1000))
      attempt.count++
      const salt = randomBytes(16).toString('hex')
      passwordHash = `scrypt:${salt}:${(await derivePassword(password, salt)).toString('hex')}`
    }
    const result = acceptLibrarySms(phone, code, secret, SESSION_SECONDS * 1000, passwordHash)
    if (result.status === 'closed') return registrationClosed()
    if (result.status === 'invalid') return authFailure('验证码无效或已过期，请重新获取。', 401)
    return accountSessionResponse(request, phone, result.token, result.expiresAt)
  } catch (error) {
    console.error('[library-sms] Verification failed', (error as Error).name)
    return authFailure('登录暂时不可用，请稍后重试。', 503)
  }
}

export async function registerLibrary(request: Request): Promise<Response> {
  if (!isLibrarySameOrigin(request)) return authFailure('请在本站页面注册。', 403)
  if (loginMode() !== 'sms' || !isLibraryRegistrationOpen()) return registrationClosed()
  return loginLibraryWithCode(request, await readAuthInput(request), true)
}

async function loginLibraryWithPassword(request: Request, input: Record<string, unknown> | null, accountMode: boolean) {
  const config = configuration()
  const secret = accountMode ? smsSecret() : config?.secret
  if (!secret) return authFailure('登录暂时不可用，请稍后重试。', 503)
  const phone = accountMode ? mobileNumber(input?.phone) : typeof input?.phone === 'string' ? input.phone.trim() : ''
  const password = input?.password
  if (!phone || typeof password !== 'string' || password.length > 256) return authFailure('请填写手机号和密码。', 400)

  const now = Date.now()
  const sourceKey = `password:source:${requestSource(request)}`
  const phoneKey = `password:phone:${phone}`
  const sourceAttempt = attemptFor(sourceKey, now)
  const phoneAttempt = accountMode ? attemptFor(phoneKey, now) : undefined
  const limited = [sourceAttempt, phoneAttempt].find(attempt => attempt && attempt.count >= MAX_ATTEMPTS)
  if (limited) return authFailure('登录尝试次数过多，请稍后再试。', 429, Math.ceil((limited.until - now) / 1000))
  sourceAttempt.count++
  if (phoneAttempt) phoneAttempt.count++

  try {
    const ownerPassword = config && sameString(phone, config.phone) ? config.passwordHash : null
    const storedHash = accountMode && phone !== process.env.WEIBULL_LIBRARY_PHONE ? getLibraryPasswordHash(phone) : null
    const passwordHash = ownerPassword || storedHash
    const matched = await validPassword(ownerPassword ? password : password.normalize('NFC'), passwordHash || DUMMY_PASSWORD_HASH)
    if (!passwordHash || !matched) return authFailure('手机号或密码不正确。', 401)
    if (attempts.get(sourceKey) === sourceAttempt) attempts.delete(sourceKey)
    if (phoneAttempt && attempts.get(phoneKey) === phoneAttempt) attempts.delete(phoneKey)
    if (accountMode) {
      const expiresAt = now + SESSION_SECONDS * 1000
      return accountSessionResponse(request, phone, startLibraryPasswordSession(phone, secret, now, expiresAt), expiresAt)
    }
    const iat = Math.floor(now / 1000)
    const exp = iat + SESSION_SECONDS
    const value = Buffer.from(JSON.stringify({ v: 1, phone, iat, exp, nonce: randomBytes(16).toString('base64url') })).toString('base64url')
    return Response.json({ authenticated: true, user: { phone }, expiresAt: exp * 1000 }, {
      headers: { ...PRIVATE_HEADERS, 'Set-Cookie': sessionCookie(request, `${value}.${signature(value, config!)}`, SESSION_SECONDS) },
    })
  } catch (error) {
    console.error('[library-auth] Password login failed', (error as Error).name)
    return authFailure('登录暂时不可用，请稍后重试。', 503)
  }
}

export async function loginLibrary(request: Request): Promise<Response> {
  if (!isLibrarySameOrigin(request)) return authFailure('请在本站页面登录。', 403)
  const input = await readAuthInput(request)
  const accountMode = loginMode() === 'sms'
  if (accountMode && input && 'code' in input) {
    if ('password' in input) return authFailure('请选择一种登录方式。', 400)
    return loginLibraryWithCode(request, input)
  }
  return loginLibraryWithPassword(request, input, accountMode)
}

export function logoutLibrary(request: Request): Response {
  if (!isLibrarySameOrigin(request)) return Response.json({ error: '请在本站页面退出登录。' }, { status: 403, headers: PRIVATE_HEADERS })
  if (loginMode() === 'sms') {
    const token = cookieValue(request)
    const secret = smsSecret()
    if (secret && /^[A-Za-z0-9_-]{43}$/.test(token)) {
      try { revokeLibrarySmsSession(token, secret) }
      catch (error) {
        console.error('[library-sms] Logout failed', (error as Error).name)
        return authFailure('退出未完成，请重试。', 503)
      }
    }
  }
  return Response.json({ authenticated: false }, { headers: { ...PRIVATE_HEADERS, 'Set-Cookie': sessionCookie(request, '', 0) } })
}
