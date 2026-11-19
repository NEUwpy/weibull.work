import { mkdirSync } from 'node:fs'
import path from 'node:path'
import type { DatabaseSync } from 'node:sqlite'
import { getDataRoot } from './data-root'

export function libraryDatabaseDirectory() {
  return path.resolve(process.env.WEIBULL_FAVORITES_DIR?.trim() || path.join(getDataRoot(), 'private', 'library-favorites'))
}

export function openLibraryDatabase(directory = libraryDatabaseDirectory()) {
  const sqlite = process.getBuiltinModule('node:sqlite') as typeof import('node:sqlite')
  mkdirSync(directory, { recursive: true, mode: 0o700 })
  const db = new sqlite.DatabaseSync(path.join(directory, 'library-favorites.sqlite3'))
  try {
    db.exec('PRAGMA busy_timeout = 5000; PRAGMA foreign_keys = ON;')
    return db
  } catch (error) {
    db.close()
    throw error
  }
}

export function libraryTransaction<T>(db: DatabaseSync, work: () => T, begin = 'BEGIN IMMEDIATE'): T {
  db.exec(begin)
  try {
    const result = work()
    db.exec('COMMIT')
    return result
  } catch (error) {
    if (db.isTransaction) db.exec('ROLLBACK')
    throw error
  }
}

export function legacyLibraryAccountId() {
  const id = process.env.WEIBULL_LIBRARY_ACCOUNT_ID?.trim()
  if (id && !/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(id)) throw new Error('Invalid library account ID')
  return id || null
}
