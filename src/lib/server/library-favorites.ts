import { createHash, randomUUID } from 'node:crypto'
import fs from 'node:fs/promises'
import path from 'node:path'
import type { LibraryFavoriteAction, LibraryFavoriteFolder, LibraryFavoriteResult } from '../library-favorites'
import { isLibraryRecommendationRelation, libraryRecommendationLabels } from '../library-recommendations'
import { legacyLibraryAccountId, libraryDatabaseDirectory } from './library-database'
import { readSqliteLibraryFavorites, updateSqliteLibraryFavorites } from './library-favorites-sqlite'
import { removeDefaultFavoriteFolder } from './library-favorites-legacy'

export class LibraryFolderNotFound extends Error {}

function validFolder(folder: LibraryFavoriteFolder) {
  if (typeof folder?.id !== 'string' || typeof folder.name !== 'string' ||
      !Array.isArray(folder.paperIds) || !folder.paperIds.every(id => typeof id === 'string')) return false
  if (folder.subfolders !== undefined && (!Array.isArray(folder.subfolders) ||
      !folder.subfolders.every(child => typeof child?.id === 'string' && typeof child.name === 'string'))) return false
  if (folder.paperSubfolders === undefined) return true
  if (!folder.paperSubfolders || typeof folder.paperSubfolders !== 'object' || Array.isArray(folder.paperSubfolders)) return false
  const children = new Set(folder.subfolders?.map(child => child.id))
  return Object.values(folder.paperSubfolders).every(id => children.has(id))
}

function storageFor(phone: string, legacyId?: string | null) {
  const directory = libraryDatabaseDirectory()
  const key = createHash('sha256').update(phone).digest('hex')
  const file = path.join(directory, `${key}.json`)
  const mode = process.env.WEIBULL_FAVORITES_STORAGE?.trim() || 'json'
  if (mode === 'json') return { mode, file } as const
  if (mode !== 'sqlite') throw new Error('Invalid library favorites storage mode')

  const accountId = legacyId === undefined ? legacyLibraryAccountId() : legacyId
  return { mode, account: { directory, userId: accountId ? `account:${accountId}` : `phone:${key}`, readInitialFolders: () => readFolders(file) } } as const
}

async function readFolders(file: string): Promise<LibraryFavoriteFolder[]> {
  try {
    const data = JSON.parse(await fs.readFile(file, 'utf8'))
    if (data.version !== 1 || !Array.isArray(data.folders) || !data.folders.every(validFolder)) {
      throw new Error('Invalid library favorites file')
    }
    return removeDefaultFavoriteFolder(data.folders)
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error
    return []
  }
}

export function readLibraryFavorites(phone: string, legacyId?: string | null) {
  const storage = storageFor(phone, legacyId)
  return storage.mode === 'sqlite' ? readSqliteLibraryFavorites(storage.account) : readFolders(storage.file)
}

// Next renders the route in a single frontend process. Serialize account writes
// there and publish each complete snapshot with an atomic rename.
const queueKey = Symbol.for('weibull.library-favorites-writes.v1')
const shared = globalThis as unknown as Record<symbol, Map<string, Promise<unknown>>>
const writes = shared[queueKey] ??= new Map<string, Promise<unknown>>()

async function writeFolders(file: string, folders: LibraryFavoriteFolder[]) {
  await fs.mkdir(path.dirname(file), { recursive: true, mode: 0o700 })
  const temporary = `${file}.${randomUUID()}.tmp`
  try {
    await fs.writeFile(temporary, JSON.stringify({ version: 1, folders }), { encoding: 'utf8', flag: 'wx', mode: 0o600, flush: true })
    await fs.rename(temporary, file)
  } catch (error) {
    await fs.unlink(temporary).catch(() => {})
    throw error
  }
}

function applyFavoriteAction(folders: LibraryFavoriteFolder[], input: LibraryFavoriteAction) {
  let folder = input.action === 'create' ? folders.find(item => item.name === input.name)
    : folders.find(item => item.id === input.folderId)
  const created = !folder
  if (!folder) {
    if (input.action !== 'create') throw new LibraryFolderNotFound()
    folder = { id: randomUUID(), name: input.name, paperIds: [] }
    folders.push(folder)
  }
  const assignments = new Map(Object.entries(folder.paperSubfolders ?? {}))
  const subfolders = folder.subfolders ?? []
  const paperIds = new Set(folder.paperIds)
  const changed = new Set<string>()
  let madeSubfolder = false

  function subfolderByName(name: string) {
    const existing = subfolders.find(item => item.name === name)
    if (existing) return existing
    const subfolder = { id: randomUUID(), name }
    subfolders.push(subfolder)
    madeSubfolder = true
    return subfolder
  }

  if (input.action === 'create-subfolder') {
    subfolderByName(input.name)
  } else {
    if (input.action === 'move' && input.subfolderId && !subfolders.some(item => item.id === input.subfolderId)) {
      throw new LibraryFolderNotFound()
    }
    for (const id of input.paperIds) {
      if (input.action === 'remove') {
        if (paperIds.delete(id)) changed.add(id)
        assignments.delete(id)
      } else if (input.action === 'move') {
        if (!paperIds.has(id) || assignments.get(id) === input.subfolderId) continue
        if (input.subfolderId) assignments.set(id, input.subfolderId)
        else assignments.delete(id)
        changed.add(id)
      } else {
        if (!paperIds.has(id)) changed.add(id)
        paperIds.add(id)
        const relation = input.relations?.[id]
        if (!assignments.has(id) && isLibraryRecommendationRelation(relation)) {
          assignments.set(id, subfolderByName(libraryRecommendationLabels[relation]).id)
          changed.add(id)
        }
      }
    }
  }
  folder.paperIds = Array.from(paperIds)
  if (subfolders.length) folder.subfolders = subfolders
  if (assignments.size) folder.paperSubfolders = Object.fromEntries(assignments)
  else delete folder.paperSubfolders
  return { result: { folders, folder, changed: changed.size }, modified: created || madeSubfolder || changed.size > 0 }
}

export async function updateLibraryFavorites(phone: string, input: LibraryFavoriteAction, legacyId?: string | null): Promise<LibraryFavoriteResult> {
  const storage = storageFor(phone, legacyId)
  if (storage.mode === 'sqlite') return updateSqliteLibraryFavorites(storage.account, folders => applyFavoriteAction(folders, input))

  const { file } = storage
  const next = (writes.get(file) ?? Promise.resolve()).catch(() => {}).then(async () => {
    const { result, modified } = applyFavoriteAction(await readFolders(file), input)
    if (modified) await writeFolders(file, result.folders)
    return result
  })
  writes.set(file, next)
  try { return await next } finally { if (writes.get(file) === next) writes.delete(file) }
}
