import { createHmac, randomBytes, randomUUID, timingSafeEqual } from 'node:crypto'
import type { DatabaseSync } from 'node:sqlite'
import { legacyLibraryAccountId, libraryTransaction, openLibraryDatabase } from './library-database'
import { isLibraryRegistrationOpen } from './library-registration'

const codeLifetime = 5 * 60_000
const resendInterval = 60_000
const day = 24 * 60 * 60_000
const maxAttempts = 5
export type LibrarySmsPurpose = 'login' | 'register'

const usersTable = 'library_phone_users'
const requestsTable = 'library_sms_requests'

const schema = `
  CREATE TABLE IF NOT EXISTS library_phone_users (
    phone TEXT PRIMARY KEY NOT NULL,
    legacy_account_id TEXT UNIQUE,
    created_at INTEGER NOT NULL,
    password_hash TEXT
  ) STRICT;
  CREATE TABLE IF NOT EXISTS library_sms_requests (
    id TEXT PRIMARY KEY NOT NULL,
    phone TEXT NOT NULL,
    source TEXT NOT NULL,
    requested_at INTEGER NOT NULL,
    digest TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    purpose TEXT NOT NULL DEFAULT 'login' CHECK (purpose IN ('login', 'register'))
  ) STRICT;
  CREATE INDEX IF NOT EXISTS library_sms_requests_phone ON library_sms_requests(phone, requested_at);
  CREATE TABLE IF NOT EXISTS library_phone_sessions (
    token_digest TEXT PRIMARY KEY NOT NULL,
    phone TEXT NOT NULL REFERENCES library_phone_users(phone),
    expires_at INTEGER NOT NULL
  ) STRICT;
`

function openSmsDatabase() {
  const db = openLibraryDatabase()
  try {
    db.exec(schema)
    const hasPassword = () => db.prepare(`PRAGMA table_info(${usersTable})`).all().some(column => column.name === 'password_hash')
    const hasPurpose = () => db.prepare(`PRAGMA table_info(${requestsTable})`).all().some(column => column.name === 'purpose')
    if (!hasPassword() || !hasPurpose()) libraryTransaction(db, () => {
      if (!hasPassword()) db.exec(`ALTER TABLE ${usersTable} ADD COLUMN password_hash TEXT`)
      if (!hasPurpose()) db.exec(`ALTER TABLE ${requestsTable} ADD COLUMN purpose TEXT NOT NULL DEFAULT 'login' CHECK (purpose IN ('login', 'register'))`)
    })
    return db
  } catch (error) {
    db.close()
    throw error
  }
}

function digest(secret: string, purpose: string, value: string) {
  return createHmac('sha256', secret).update(`${purpose}\0${value}`).digest('hex')
}

function phoneAccount(db: DatabaseSync, phone: string) {
  return db.prepare('SELECT password_hash FROM library_phone_users WHERE phone = ?')
    .get(phone) as { password_hash: string | null } | undefined
}

function isOwner(phone: string) {
  return phone === process.env.WEIBULL_LIBRARY_PHONE
}

function ensureOwnerAccount(db: DatabaseSync, phone: string, now: number) {
  db.prepare('INSERT INTO library_phone_users (phone, created_at) VALUES (?, ?) ON CONFLICT(phone) DO NOTHING').run(phone, now)
  const legacyAccount = legacyLibraryAccountId()
  if (legacyAccount) db.prepare(`
    UPDATE library_phone_users SET legacy_account_id = ? WHERE phone = ? AND legacy_account_id IS NULL
    AND NOT EXISTS (SELECT 1 FROM library_phone_users WHERE legacy_account_id = ?)
  `).run(legacyAccount, phone, legacyAccount)
}

function createSession(db: DatabaseSync, phone: string, secret: string, now: number, expiresAt: number) {
  const token = randomBytes(32).toString('base64url')
  db.prepare('DELETE FROM library_phone_sessions WHERE expires_at <= ?').run(now)
  db.prepare('INSERT INTO library_phone_sessions (token_digest, phone, expires_at) VALUES (?, ?, ?)')
    .run(digest(secret, 'sms-session', token), phone, expiresAt)
  return token
}

export function getLibraryPasswordHash(phone: string) {
  const db = openSmsDatabase()
  try { return phoneAccount(db, phone)?.password_hash }
  finally { db.close() }
}

export function startLibraryPasswordSession(phone: string, secret: string, now: number, expiresAt: number) {
  const db = openSmsDatabase()
  try {
    return libraryTransaction(db, () => {
      if (isOwner(phone)) ensureOwnerAccount(db, phone, now)
      return createSession(db, phone, secret, now, expiresAt)
    })
  } finally { db.close() }
}

export function reserveLibrarySms(phone: string, purpose: LibrarySmsPurpose, client: string, secret: string) {
  const db = openSmsDatabase()
  try {
    return libraryTransaction(db, () => {
      const now = Date.now()
      const registering = purpose === 'register'
      if (registering && !isLibraryRegistrationOpen(now)) return { status: 'closed' } as const
      const exists = isOwner(phone) || Boolean(phoneAccount(db, phone))
      const resendAfter = resendInterval / 1000
      if (registering === exists) return { status: 'skipped', resendAfter } as const
      db.prepare('DELETE FROM library_sms_requests WHERE requested_at <= ?').run(now - day)
      const source = digest(secret, 'sms-source', client)
      const limits = db.prepare(`
        SELECT COUNT(*) AS total, COUNT(CASE WHEN phone = ? THEN 1 END) AS by_phone,
          COUNT(CASE WHEN source = ? AND requested_at > ? THEN 1 END) AS by_source,
          MAX(CASE WHEN phone = ? THEN requested_at END) AS latest
        FROM library_sms_requests
      `).get(phone, source, now - 15 * 60_000, phone) as { total: number; by_phone: number; by_source: number; latest: number | null }
      if (limits.latest !== null && now - limits.latest < resendInterval) {
        return { status: 'limited', retryAfter: Math.ceil((limits.latest + resendInterval - now) / 1000) } as const
      }
      if (limits.total >= 100 || limits.by_phone >= 5 || limits.by_source >= 10) return { status: 'limited', retryAfter: 900 } as const
      const id = randomUUID()
      db.prepare('INSERT INTO library_sms_requests (id, phone, source, requested_at, purpose) VALUES (?, ?, ?, ?, ?)').run(id, phone, source, now, purpose)
      return { status: 'reserved', id, resendAfter } as const
    })
  } finally { db.close() }
}

export function markLibrarySmsSent(id: string, code: string, secret: string) {
  const db = openLibraryDatabase()
  try {
    db.prepare('UPDATE library_sms_requests SET digest = ? WHERE id = ?').run(digest(secret, 'sms-code', `${id}\0${code}`), id)
  } finally { db.close() }
}

export function acceptLibrarySms(phone: string, code: string, secret: string, sessionLifetimeMs: number, passwordHash?: string) {
  const db = openSmsDatabase()
  try {
    return libraryTransaction(db, () => {
      const now = Date.now()
      const registering = passwordHash !== undefined
      const purpose = registering ? 'register' : 'login'
      if (registering && !isLibraryRegistrationOpen(now)) return { status: 'closed' } as const
      const owner = isOwner(phone)
      const exists = owner || Boolean(phoneAccount(db, phone))
      if (registering === exists) return { status: 'invalid' } as const
      const latest = db.prepare(`
        SELECT id, digest, attempts FROM library_sms_requests WHERE phone = ? AND purpose = ? AND requested_at > ?
        ORDER BY requested_at DESC LIMIT 1
      `).get(phone, purpose, now - codeLifetime) as { id: string; digest: string | null; attempts: number } | undefined
      if (!latest?.digest || latest.attempts >= maxAttempts) return { status: 'invalid' } as const
      const expected = digest(secret, 'sms-code', `${latest.id}\0${code}`)
      if (!timingSafeEqual(Buffer.from(latest.digest), Buffer.from(expected))) {
        db.prepare('UPDATE library_sms_requests SET attempts = attempts + 1 WHERE id = ?').run(latest.id)
        return { status: 'invalid' } as const
      }
      if (registering) {
        db.prepare('INSERT INTO library_phone_users (phone, created_at, password_hash) VALUES (?, ?, ?)').run(phone, now, passwordHash)
      } else if (owner) {
        ensureOwnerAccount(db, phone, now)
      }
      db.prepare('UPDATE library_sms_requests SET digest = NULL WHERE id = ?').run(latest.id)
      const expiresAt = now + sessionLifetimeMs
      return { status: 'accepted', token: createSession(db, phone, secret, now, expiresAt), expiresAt } as const
    })
  } finally { db.close() }
}

export function readLibrarySmsSession(token: string, secret: string, now: number) {
  const db = openSmsDatabase()
  try {
    return db.prepare(`
      SELECT u.phone, u.legacy_account_id, s.expires_at FROM library_phone_sessions s
      JOIN library_phone_users u ON u.phone = s.phone WHERE s.token_digest = ? AND s.expires_at > ?
    `).get(digest(secret, 'sms-session', token), now) as { phone: string; legacy_account_id: string | null; expires_at: number } | undefined
  } finally { db.close() }
}

export function revokeLibrarySmsSession(token: string, secret: string) {
  const db = openSmsDatabase()
  try {
    db.prepare('DELETE FROM library_phone_sessions WHERE token_digest = ?').run(digest(secret, 'sms-session', token))
  } finally { db.close() }
}
