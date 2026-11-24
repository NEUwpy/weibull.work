import type { LibraryFavoriteFolder } from '../library-favorites'
import { libraryFavoritesSyncOwner, validLibraryFavoriteFolder } from './library-favorites'
import { readSqliteLibraryFavoriteSyncState, updateSqliteLibraryFavoriteSyncState } from './library-favorites-sqlite'
import type { LibraryFavoriteSyncState } from './library-favorites-sqlite'

type Folders = LibraryFavoriteFolder[]

function unique(values: string[]) {
  return new Set(values).size === values.length
}

function parseFolders(value: unknown): Folders {
  if (!Array.isArray(value) || !value.every(validLibraryFavoriteFolder) ||
    !unique(value.map(folder => folder.id)) || !unique(value.map(folder => folder.name))) {
    throw new Error('收藏快照格式无效或含有重复文献组。')
  }
  return value.map(folder => {
    const { id, name } = folder
    const paperIds = Array.from(new Set<string>(folder.paperIds))
    const subfolders = folder.subfolders?.map(child => ({ id: child.id, name: child.name })) ?? []
    if (!unique(subfolders.map(child => child.id)) || !unique(subfolders.map(child => child.name))) {
      throw new Error('收藏快照含有重复子文件夹。')
    }
    const assignments = new Map<string, string>(Object.entries(folder.paperSubfolders ?? {}))
    const paperSubfolders = Object.fromEntries(paperIds.flatMap(paperId => {
      const child = assignments.get(paperId)
      return child ? [[paperId, child]] : []
    }))
    return {
      id, name, paperIds,
      ...(subfolders.length ? { subfolders } : {}),
      ...(Object.keys(paperSubfolders).length ? { paperSubfolders } : {}),
    }
  })
}

function same(left: unknown, right: unknown) {
  return JSON.stringify(left) === JSON.stringify(right)
}

function mergeFolders(baseline: Folders | null, local: Folders, remote: Folders) {
  const before = new Map(baseline?.map(folder => [folder.id, folder]))
  const onLocal = new Map(local.map(folder => [folder.id, folder]))
  const onRemote = new Map(remote.map(folder => [folder.id, folder]))
  const order = same(baseline?.map(folder => folder.id), remote.map(folder => folder.id)) ? [local, remote] : [remote, local]
  const ids = Array.from(new Set(order.flatMap(folders => folders.map(folder => folder.id))))
  const merged: Folders = []
  const names = new Set<string>()
  const conflicts = new Set<string>()
  for (const id of ids) {
    const left = onLocal.get(id)
    const right = onRemote.get(id)
    const initial = before.get(id)
    if (!same(left, right) && !same(left, initial) && !same(right, initial)) {
      conflicts.add((left ?? right ?? initial)!.name)
      continue
    }
    const folder = same(left, initial) ? right : left
    if (folder) {
      if (names.has(folder.name)) conflicts.add(folder.name)
      else { names.add(folder.name); merged.push(folder) }
    }
  }
  if (conflicts.size) throw new Error(`收藏同步有冲突，请先核对文献组 ${JSON.stringify(Array.from(conflicts))}。`)
  return merged
}

export async function readLibraryFavoriteSync(peer: string) {
  const { ownerKey, account } = libraryFavoritesSyncOwner()
  const { folders, baseline } = await readSqliteLibraryFavoriteSyncState(account, peer)
  return { ownerKey, folders: parseFolders(folders), baseline: baseline === null ? null : parseFolders(baseline) }
}

export async function receiveLibraryFavoriteSync(input: unknown) {
  if (!input || typeof input !== 'object') throw new Error('收藏同步请求无效。')
  const request = input as Record<string, unknown>
  const { ownerKey, account } = libraryFavoritesSyncOwner()
  if (request.ownerKey !== ownerKey) throw new Error('本机与 NAS 的预设手机号不同。')
  if (typeof request.dryRun !== 'boolean') throw new Error('收藏同步请求无效。')
  const local = parseFolders(request.folders)
  const baseline = request.baseline === null ? null : parseFolders(request.baseline)

  function change(state: LibraryFavoriteSyncState) {
    const remote = parseFolders(state.folders)
    const folders = mergeFolders(baseline, local, remote)
    return { folders, modified: !same(remote, folders) }
  }

  if (request.dryRun) return change(await readSqliteLibraryFavoriteSyncState(account))
  let modified = false
  const folders = await updateSqliteLibraryFavoriteSyncState(account, undefined, state => {
    const result = change(state)
    modified = result.modified
    return result
  })
  return { folders, modified }
}

export function applyLibraryFavoriteSync(peer: string, sent: Awaited<ReturnType<typeof readLibraryFavoriteSync>>, reply: unknown) {
  if (!reply || typeof reply !== 'object') throw new Error('NAS 收藏同步响应无效。')
  const folders = parseFolders((reply as Record<string, unknown>).folders)
  const { ownerKey, account } = libraryFavoritesSyncOwner()
  if (sent.ownerKey !== ownerKey) throw new Error('本机收藏账号已变更。')
  return updateSqliteLibraryFavoriteSyncState(account, peer, current => {
    const before = current.baseline === null ? null : parseFolders(current.baseline)
    const local = parseFolders(current.folders)
    if (!same(before, sent.baseline) || !same(local, sent.folders)) {
      throw new Error('本机收藏在同步期间有更新，请重新运行同步。')
    }
    return { folders, modified: !same(local, folders) }
  })
}
