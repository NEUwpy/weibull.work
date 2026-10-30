import { createHmac, randomBytes, scrypt, timingSafeEqual } from 'node:crypto'

const COOKIE_NAME = 'weibull_library_session'
const SESSION_SECONDS = 7 * 24 * 60 * 60
const RETRY_WINDOW_MS = 15 * 60 * 1000
const MAX_ATTEMPTS = 6
const PRIVATE_HEADERS = { 'Cache-Control': 'private, no-store', Vary: 'Cookie' }

interface AuthConfig { phone: string; passwordHash: string; secret: string }
export interface LibrarySession {
  authenticated: boolean
  user?: { phone: string }
  expiresAt?: number
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
  const config = configuration()
  const token = cookieValue(request)
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
  return getLibrarySession(request).authenticated ? null : Response.json({
    error: '请登录后阅读原文或译文。', code: 'AUTH_REQUIRED',
  }, { status: 401, headers: PRIVATE_HEADERS })
}

export function librarySessionResponse(request: Request): Response {
  return Response.json(getLibrarySession(request), { headers: PRIVATE_HEADERS })
}

function sameOrigin(request: Request): boolean {
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

function attemptFor(request: Request, now: number): { key: string; attempt: Attempt } {
  // Cloudflare supplies CF-Connecting-IP; the local fallback is deliberately shared.
  const key = (request.headers.get('cf-connecting-ip') || request.headers.get('x-forwarded-for')?.split(',')[0] || 'local').trim().slice(0, 100)
  for (const [ip, value] of Array.from(attempts)) if (value.until <= now) attempts.delete(ip)
  if (attempts.size >= 1000 && !attempts.has(key)) attempts.delete(attempts.keys().next().value!)
  let attempt = attempts.get(key)
  if (!attempt) { attempt = { count: 0, until: now + RETRY_WINDOW_MS }; attempts.set(key, attempt) }
  return { key, attempt }
}

async function validPassword(password: string, passwordHash: string): Promise<boolean> {
  const [, salt, expected] = passwordHash.split(':')
  // The configured salt is its hex text, matching the credential setup command.
  const digest = await new Promise<Buffer>((resolve, reject) => {
    scrypt(password, salt, 64, (error, key) => error ? reject(error) : resolve(key))
  })
  return timingSafeEqual(digest, Buffer.from(expected, 'hex'))
}

export async function loginLibrary(request: Request): Promise<Response> {
  if (!sameOrigin(request)) return Response.json({ error: '请在本站页面登录。' }, { status: 403, headers: PRIVATE_HEADERS })
  const config = configuration()
  if (!config) return Response.json({ error: '登录暂时不可用，请稍后重试。' }, { status: 503, headers: PRIVATE_HEADERS })
  if (!request.headers.get('content-type')?.includes('application/json')) {
    return Response.json({ error: '登录信息格式无效。' }, { status: 400, headers: PRIVATE_HEADERS })
  }
  const now = Date.now()
  const { key, attempt } = attemptFor(request, now)
  if (attempt.count >= MAX_ATTEMPTS) return Response.json({ error: '登录尝试次数过多，请稍后再试。' }, {
    status: 429, headers: { ...PRIVATE_HEADERS, 'Retry-After': String(Math.ceil((attempt.until - now) / 1000)) },
  })
  let input: { phone?: unknown; password?: unknown }
  try {
    if (Number(request.headers.get('content-length')) > 2048) throw new Error('Too large')
    const body = await request.text()
    if (body.length > 2048) throw new Error('Too large')
    input = JSON.parse(body)
    if (!input || typeof input !== 'object' || typeof input.phone !== 'string' || typeof input.password !== 'string' || input.password.length > 256) throw new Error('Invalid fields')
  } catch { return Response.json({ error: '请填写手机号和密码。' }, { status: 400, headers: PRIVATE_HEADERS }) }
  attempt.count++
  const passwordOk = await validPassword(input.password as string, config.passwordHash)
  if (!passwordOk || !sameString((input.phone as string).trim(), config.phone)) {
    return Response.json({ error: '手机号或密码不正确。' }, { status: 401, headers: PRIVATE_HEADERS })
  }
  attempts.delete(key)
  const iat = Math.floor(now / 1000)
  const exp = iat + SESSION_SECONDS
  const value = Buffer.from(JSON.stringify({ v: 1, phone: config.phone, iat, exp, nonce: randomBytes(16).toString('base64url') })).toString('base64url')
  return Response.json({ authenticated: true, user: { phone: config.phone }, expiresAt: exp * 1000 }, {
    headers: { ...PRIVATE_HEADERS, 'Set-Cookie': sessionCookie(request, `${value}.${signature(value, config)}`, SESSION_SECONDS) },
  })
}

export function logoutLibrary(request: Request): Response {
  if (!sameOrigin(request)) return Response.json({ error: '请在本站页面退出登录。' }, { status: 403, headers: PRIVATE_HEADERS })
  return Response.json({ authenticated: false }, { headers: { ...PRIVATE_HEADERS, 'Set-Cookie': sessionCookie(request, '', 0) } })
}
