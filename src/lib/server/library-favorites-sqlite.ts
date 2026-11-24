import { existsSync } from 'node:fs'
import path from 'node:path'
import type { DatabaseSync } from 'node:sqlite'
import { LEGACY_LIBRARY_FOLDER, type LibraryFavoriteFolder, type LibraryFavoriteResult } from '../library-favorites'
import { legacyFavoriteFolderName, removeDefaultFavoriteFolder } from './library-favorites-legacy'
import { libraryTransaction as transaction, openLibraryDatabase } from './library-database'

interface SQLiteAccount {
  directory: string
  userId: string
  readInitialFolders: () => Promise<LibraryFavoriteFolder[]>
}

const schema = `
  CREATE TABLE favorite_users (
    id TEXT PRIMARY KEY NOT NULL
  ) STRICT;
  CREATE TABLE favorite_folders (
    user_id TEXT NOT NULL REFERENCES favorite_users(id),
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (user_id, id),
    UNIQUE (user_id, name)
  ) STRICT;
  CREATE TABLE favorite_papers (
    user_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    paper_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (user_id, folder_id, paper_id),
    FOREIGN KEY (user_id, folder_id) REFERENCES favorite_folders(user_id, id) ON DELETE CASCADE
  ) STRICT;
  PRAGMA user_version = 1;
`

const addSubfolders = `
  CREATE TABLE favorite_subfolders (
    user_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (user_id, folder_id, id),
    UNIQUE (user_id, folder_id, name),
    FOREIGN KEY (user_id, folder_id) REFERENCES favorite_folders(user_id, id) ON DELETE CASCADE
  ) STRICT;
  CREATE TABLE favorite_papers_v2 (
    user_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    paper_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    subfolder_id TEXT,
    PRIMARY KEY (user_id, folder_id, paper_id),
    FOREIGN KEY (user_id, folder_id) REFERENCES favorite_folders(user_id, id) ON DELETE CASCADE,
    FOREIGN KEY (user_id, folder_id, subfolder_id) REFERENCES favorite_subfolders(user_id, folder_id, id)
  ) STRICT;
  INSERT INTO favorite_papers_v2 (user_id, folder_id, paper_id, position)
    SELECT user_id, folder_id, paper_id, position FROM favorite_papers;
  DROP TABLE favorite_papers;
  ALTER TABLE favorite_papers_v2 RENAME TO favorite_papers;
  PRAGMA user_version = 2;
`

function schemaVersion(db: DatabaseSync) {
  return db.prepare('PRAGMA user_version').get()?.user_version
}

function writeFolder(db: DatabaseSync, userId: string, folder: LibraryFavoriteFolder) {
  db.prepare(`
    INSERT INTO favorite_folders (user_id, id, name, position)
    VALUES (?, ?, ?, (SELECT COALESCE(MAX(position), -1) + 1 FROM favorite_folders WHERE user_id = ?))
    ON CONFLICT(user_id, id) DO NOTHING
  `).run(userId, folder.id, folder.name, userId)
  const insertSubfolder = db.prepare(`
    INSERT INTO favorite_subfolders (user_id, folder_id, id, name, position) VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(user_id, folder_id, id) DO NOTHING
  `)
  folder.subfolders?.forEach((child, index) => insertSubfolder.run(userId, folder.id, child.id, child.name, index))
  db.prepare('DELETE FROM favorite_papers WHERE user_id = ? AND folder_id = ?').run(userId, folder.id)
  const insert = db.prepare('INSERT INTO favorite_papers (user_id, folder_id, paper_id, position, subfolder_id) VALUES (?, ?, ?, ?, ?)')
  const assignments = new Map(Object.entries(folder.paperSubfolders ?? {}))
  Array.from(new Set(folder.paperIds)).forEach((id, index) => insert.run(userId, folder.id, id, index, assignments.get(id) ?? null))
}

function readFolders(db: DatabaseSync, userId: string, withSubfolders = true) {
  const rows = db.prepare(`
    SELECT f.id, f.name, p.paper_id, ${withSubfolders ? 'p.subfolder_id' : 'NULL'} AS subfolder_id
    FROM favorite_folders f
    LEFT JOIN favorite_papers p ON (p.user_id, p.folder_id) = (f.user_id, f.id)
    WHERE f.user_id = ?
    ORDER BY f.position, p.position
  `).all(userId) as Array<{ id: string; name: string; paper_id: string | null; subfolder_id: string | null }>
  const folders = new Map<string, LibraryFavoriteFolder>()
  for (const row of rows) {
    let folder = folders.get(row.id)
    if (!folder) {
      folder = { id: row.id, name: row.name, paperIds: [] }
      folders.set(row.id, folder)
    }
    if (row.paper_id !== null) {
      folder.paperIds.push(row.paper_id)
      if (row.subfolder_id !== null) {
        const placements = folder.paperSubfolders ??= Object.create(null) as Record<string, string>
        placements[row.paper_id] = row.subfolder_id
      }
    }
  }
  if (!withSubfolders) return Array.from(folders.values())
  const children = db.prepare(`
    SELECT folder_id, id, name FROM favorite_subfolders WHERE user_id = ? ORDER BY position
  `).all(userId) as Array<{ folder_id: string; id: string; name: string }>
  for (const child of children) {
    const folder = folders.get(child.folder_id)!
    const subfolders = folder.subfolders ??= []
    subfolders.push({ id: child.id, name: child.name })
  }
  return Array.from(folders.values())
}

function upgradeDefaultFolder(db: DatabaseSync, userId: string) {
  const legacy = db.prepare('SELECT name FROM favorite_folders WHERE user_id = ? AND id = ?')
  if (legacy.get(userId, LEGACY_LIBRARY_FOLDER)?.name !== legacyFavoriteFolderName) return

  transaction(db, () => {
    const existing = readFolders(db, userId)
    const updated = removeDefaultFavoriteFolder(existing)
    if (updated === existing) return
    const retained = updated.find(folder => folder.id === LEGACY_LIBRARY_FOLDER)
    if (retained) {
      db.prepare(`UPDATE favorite_folders SET name = ?, position = (
        SELECT COALESCE(MAX(position), -1) + 1 FROM favorite_folders WHERE user_id = ?
      ) WHERE user_id = ? AND id = ?`).run(retained.name, userId, userId, LEGACY_LIBRARY_FOLDER)
    } else {
      db.prepare('DELETE FROM favorite_folders WHERE user_id = ? AND id = ?').run(userId, LEGACY_LIBRARY_FOLDER)
    }
  })
}

async function withDatabase<T>({ directory, userId, readInitialFolders }: SQLiteAccount, work: (db: DatabaseSync) => T): Promise<T> {
  const db = openLibraryDatabase(directory)
  try {
    if (schemaVersion(db) !== 2) transaction(db, () => {
      if (schemaVersion(db) === 0) db.exec(schema)
      if (schemaVersion(db) === 1) db.exec(addSubfolders)
      if (schemaVersion(db) !== 2) throw new Error('Unsupported library favorites database version')
    })
    const account = db.prepare('SELECT 1 FROM favorite_users WHERE id = ?')
    if (!account.get(userId)) {
      const initial = await readInitialFolders()
      // The account row and import commit together. Future reads use SQLite even if the JSON changes.
      transaction(db, () => {
        if (account.get(userId)) return
        db.prepare('INSERT INTO favorite_users (id) VALUES (?)').run(userId)
        initial.forEach(folder => writeFolder(db, userId, folder))
      })
    }
    upgradeDefaultFolder(db, userId)
    return work(db)
  } finally {
    db.close()
  }
}

export function readSqliteLibraryFavorites(account: SQLiteAccount) {
  return withDatabase(account, db => transaction(db, () => readFolders(db, account.userId), 'BEGIN'))
}

export function updateSqliteLibraryFavorites(account: SQLiteAccount, change: (folders: LibraryFavoriteFolder[]) => {
  result: LibraryFavoriteResult; modified: boolean
}) {
  return withDatabase(account, db => transaction(db, () => {
    const { result, modified } = change(readFolders(db, account.userId))
    if (modified) writeFolder(db, account.userId, result.folder)
    return result
  }))
}

export interface LibraryFavoriteSyncState {
  folders: LibraryFavoriteFolder[]
  baseline: LibraryFavoriteFolder[] | null
}

function readSyncBaseline(db: DatabaseSync, userId: string, peer?: string): LibraryFavoriteFolder[] | null {
  if (!peer || !db.prepare("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'favorite_sync_checkpoints'").get()) return null
  const row = db.prepare('SELECT snapshot FROM favorite_sync_checkpoints WHERE user_id = ? AND peer = ?')
    .get(userId, peer) as { snapshot: string } | undefined
  return row ? JSON.parse(row.snapshot) : null
}

export async function readSqliteLibraryFavoriteSyncState(account: SQLiteAccount, peer?: string): Promise<LibraryFavoriteSyncState> {
  const { directory, userId, readInitialFolders } = account
  if (existsSync(path.join(directory, 'library-favorites.sqlite3'))) {
    const db = openLibraryDatabase(directory, true)
    try {
      const state = transaction(db, () => {
        const version = schemaVersion(db)
        if (version === 0) return null
        if (version !== 1 && version !== 2) throw new Error('收藏数据库版本不受支持。')
        if (!db.prepare('SELECT 1 FROM favorite_users WHERE id = ?').get(userId)) return null
        return {
          folders: removeDefaultFavoriteFolder(readFolders(db, userId, version === 2)),
          baseline: readSyncBaseline(db, userId, peer),
        }
      }, 'BEGIN')
      if (state) return state
    } finally { db.close() }
  }
  return { folders: await readInitialFolders(), baseline: null }
}

export function updateSqliteLibraryFavoriteSyncState(
  account: SQLiteAccount,
  peer: string | undefined,
  change: (state: LibraryFavoriteSyncState) => { folders: LibraryFavoriteFolder[]; modified: boolean },
) {
  const { userId } = account
  return withDatabase(account, db => transaction(db, () => {
    const folders = readFolders(db, userId)
    const next = change({ folders, baseline: readSyncBaseline(db, userId, peer) })
    if (next.modified) {
      db.prepare('DELETE FROM favorite_folders WHERE user_id = ?').run(userId)
      for (const folder of next.folders) writeFolder(db, userId, folder)
    }
    if (peer) {
      db.exec(`
        CREATE TABLE IF NOT EXISTS favorite_sync_checkpoints (
          user_id TEXT NOT NULL REFERENCES favorite_users(id),
          peer TEXT NOT NULL,
          snapshot TEXT NOT NULL,
          PRIMARY KEY (user_id, peer)
        ) STRICT;
      `)
      db.prepare(`
        INSERT INTO favorite_sync_checkpoints (user_id, peer, snapshot) VALUES (?, ?, ?)
        ON CONFLICT(user_id, peer) DO UPDATE SET snapshot = excluded.snapshot
      `).run(userId, peer, JSON.stringify(next.folders))
    }
    return next.folders
  }))
}
