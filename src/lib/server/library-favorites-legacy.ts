import { LEGACY_LIBRARY_FOLDER, type LibraryFavoriteFolder } from '../library-favorites'

export const legacyFavoriteFolderName = '我的收藏'

export function removeDefaultFavoriteFolder(folders: LibraryFavoriteFolder[]): LibraryFavoriteFolder[] {
  const legacy = folders.find(folder => folder.id === LEGACY_LIBRARY_FOLDER && folder.name === legacyFavoriteFolderName)
  if (!legacy) return folders

  const remaining = folders.filter(folder => folder !== legacy)
  if (legacy.paperIds.length || legacy.subfolders?.length) {
    const names = new Set(remaining.map(folder => folder.name))
    const base = '此前收藏'
    let name = base
    for (let suffix = 2; names.has(name); suffix++) name = `${base} ${suffix}`
    remaining.push({ ...legacy, name })
  }
  return remaining
}
