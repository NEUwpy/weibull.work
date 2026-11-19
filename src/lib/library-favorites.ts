import type { LibraryRecommendationRelations } from './library-recommendations'

export const LEGACY_LIBRARY_FOLDER = 'default'
export const UNFILED_LIBRARY_FOLDER = 'unfiled'
export const MAX_LIBRARY_FOLDER_NAME = 60

export function libraryFavoritesHref(folderId?: string, subfolderId?: string) {
  const params = new URLSearchParams({ view: 'favorites' })
  if (folderId) params.set('folder', folderId)
  if (subfolderId) params.set('subfolder', subfolderId)
  return `/library?${params}`
}

export interface LibraryFavoriteSubfolder {
  id: string
  name: string
}

export interface LibraryFavoriteFolder extends LibraryFavoriteSubfolder {
  paperIds: string[]
  subfolders?: LibraryFavoriteSubfolder[]
  paperSubfolders?: Record<string, string>
}

export type LibraryFavoriteAction =
  | { action: 'create'; name: string; paperIds: string[]; relations?: LibraryRecommendationRelations }
  | { action: 'add'; folderId: string; paperIds: string[]; relations?: LibraryRecommendationRelations }
  | { action: 'remove'; folderId: string; paperIds: string[] }
  | { action: 'create-subfolder'; folderId: string; name: string }
  | { action: 'move'; folderId: string; paperIds: string[]; subfolderId?: string }

export interface LibraryFavoriteResult {
  folders: LibraryFavoriteFolder[]
  folder: LibraryFavoriteFolder
  changed: number
}
