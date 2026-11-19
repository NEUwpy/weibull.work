import { createHmac, randomBytes, randomUUID, timingSafeEqual } from 'node:crypto'
import { legacyLibraryAccountId, libraryTransaction, openLibraryDatabase } from './library-database'

const codeLifetime = 5 * 60_000
const resendInterval = 60_000
const day = 24 * 60 * 60_000
const maxAttempts = 5

const schema = `
  CREATE TABLE IF NOT EXISTS library_phone_users (
    phone TEXT PRIMARY KEY NOT NULL,
    legacy_account_id TEXT UNIQUE,
    created_at INTEGER NOT NULL
  ) STRICT;
  CREATE TABLE IF NOT EXISTS library_sms_requests (
    id TEXT PRIMARY KEY NOT NULL,
    phone TEXT NOT NULL,
    source TEXT NOT NULL,
    requested_at INTEGER NOT NULL,
    digest TEXT,
    attempts INTEGER NOT NULL DEFAULT 0
  ) STRICT;
  CREATE INDEX IF NOT EXISTS library_sms_requests_phone ON library_sms_requests(phone, requested_at);
  CREATE TABLE IF NOT EXISTS library_phone_sessions (
    token_digest TEXT PRIMARY KEY NOT NULL,
    phone TEXT NOT NULL REFERENCES library_phone_users(phone),
    expires_at INTEGER NOT NULL
  ) STRICT;
`

function digest(secret: string, purpose: string, value: string) {
  return createHmac('sha256', secret).update(`${purpose}\0${value}`).digest('hex')
}

export function reserveLibrarySms(phone: string, client: string, secret: string, now: number) {
  const db = openLibraryDatabase()
  try {
    db.exec(schema)
    return libraryTransaction(db, () => {
      db.prepare('DELETE FROM library_sms_requests WHERE requested_at <= ?').run(now - day)
      const source = digest(secret, 'sms-source', client)
      const limits = db.prepare(`
        SELECT COUNT(*) AS total, COUNT(CASE WHEN phone = ? THEN 1 END) AS by_phone,
          COUNT(CASE WHEN source = ? AND requested_at > ? THEN 1 END) AS by_source,
          MAX(CASE WHEN phone = ? THEN requested_at END) AS latest
        FROM library_sms_requests
      `).get(phone, source, now - 15 * 60_000, phone) as { total: number; by_phone: number; by_source: number; latest: number | null }
      if (limits.latest !== null && now - limits.latest < resendInterval) {
        return { retryAfter: Math.ceil((limits.latest + resendInterval - now) / 1000) } as const
      }
      if (limits.total >= 100 || limits.by_phone >= 5 || limits.by_source >= 10) return { retryAfter: 900 } as const
      const id = randomUUID()
      db.prepare('INSERT INTO library_sms_requests (id, phone, source, requested_at) VALUES (?, ?, ?, ?)').run(id, phone, source, now)
      return { id, resendAfter: resendInterval / 1000 } as const
    })
  } finally { db.close() }
}

export function markLibrarySmsSent(id: string, code: string, secret: string) {
  const db = openLibraryDatabase()
  try {
    db.prepare('UPDATE library_sms_requests SET digest = ? WHERE id = ?').run(digest(secret, 'sms-code', `${id}\0${code}`), id)
  } finally { db.close() }
}

export function acceptLibrarySms(phone: string, code: string, secret: string, now: number, expiresAt: number) {
  const db = openLibraryDatabase()
  try {
    db.exec(schema)
    return libraryTransaction(db, () => {
      const latest = db.prepare(`
        SELECT id, digest, attempts FROM library_sms_requests WHERE phone = ? AND requested_at > ?
        ORDER BY requested_at DESC LIMIT 1
      `).get(phone, now - codeLifetime) as { id: string; digest: string | null; attempts: number } | undefined
      if (!latest?.digest || latest.attempts >= maxAttempts) return null
      const expected = digest(secret, 'sms-code', `${latest.id}\0${code}`)
      if (!timingSafeEqual(Buffer.from(latest.digest), Buffer.from(expected))) {
        db.prepare('UPDATE library_sms_requests SET attempts = attempts + 1 WHERE id = ?').run(latest.id)
        return null
      }
      db.prepare('UPDATE library_sms_requests SET digest = NULL WHERE id = ?').run(latest.id)
      const legacyAccount = phone === process.env.WEIBULL_LIBRARY_PHONE ? legacyLibraryAccountId() : null
      db.prepare('INSERT INTO library_phone_users (phone, created_at) VALUES (?, ?) ON CONFLICT(phone) DO NOTHING').run(phone, now)
      if (legacyAccount) db.prepare(`
        UPDATE library_phone_users SET legacy_account_id = ? WHERE phone = ? AND legacy_account_id IS NULL
        AND NOT EXISTS (SELECT 1 FROM library_phone_users WHERE legacy_account_id = ?)
      `).run(legacyAccount, phone, legacyAccount)
      const token = randomBytes(32).toString('base64url')
      db.prepare('DELETE FROM library_phone_sessions WHERE expires_at <= ?').run(now)
      db.prepare('INSERT INTO library_phone_sessions (token_digest, phone, expires_at) VALUES (?, ?, ?)')
        .run(digest(secret, 'sms-session', token), phone, expiresAt)
      return token
    })
  } finally { db.close() }
}

export function readLibrarySmsSession(token: string, secret: string, now: number) {
  const db = openLibraryDatabase()
  try {
    db.exec(schema)
    return db.prepare(`
      SELECT u.phone, u.legacy_account_id, s.expires_at FROM library_phone_sessions s
      JOIN library_phone_users u ON u.phone = s.phone WHERE s.token_digest = ? AND s.expires_at > ?
    `).get(digest(secret, 'sms-session', token), now) as { phone: string; legacy_account_id: string | null; expires_at: number } | undefined
  } finally { db.close() }
}

export function revokeLibrarySmsSession(token: string, secret: string) {
  const db = openLibraryDatabase()
  try {
    db.exec(schema)
    db.prepare('DELETE FROM library_phone_sessions WHERE token_digest = ?').run(digest(secret, 'sms-session', token))
  } finally { db.close() }
}
