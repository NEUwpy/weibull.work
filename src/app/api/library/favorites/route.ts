import { LEGACY_LIBRARY_FOLDER, MAX_LIBRARY_FOLDER_NAME, type LibraryFavoriteAction } from '@/lib/library-favorites'
import { isLibraryRecommendationRelation } from '@/lib/library-recommendations'
import { matchesLibraryType } from '@/lib/library-types'
import { isContentSlug } from '@/lib/server/content-files'
import { getLibrarySession, isLibrarySameOrigin } from '@/lib/server/library-auth'
import { LibraryFolderNotFound, readLibraryFavorites, updateLibraryFavorites } from '@/lib/server/library-favorites'
import { readPaperMetadata } from '@/lib/server/literature'

export const dynamic = 'force-dynamic'

const headers = { 'Cache-Control': 'private, no-store', Vary: 'Cookie' }
const maxBodyLength = 16_384

function respond(body: object, status = 200) {
  return Response.json(body, { status, headers })
}

function folderName(value: unknown) {
  if (typeof value !== 'string') return null
  const name = value.trim().normalize('NFC')
  return name && name.length <= MAX_LIBRARY_FOLDER_NAME && !/[\x00-\x1f\x7f]/.test(name) ? name : null
}

function isFolderId(id: unknown): id is string {
  return typeof id === 'string' && /^[0-9a-f-]{36}$/.test(id)
}

async function readAction(request: Request): Promise<LibraryFavoriteAction | null> {
  if (request.headers.get('content-type')?.split(';')[0] !== 'application/json' ||
      Number(request.headers.get('content-length')) > maxBodyLength) return null
  try {
    const text = await request.text()
    if (text.length > maxBodyLength) return null
    const input = JSON.parse(text)
    const action = input?.action
    const folderId = input?.folderId
    const hasFolder = folderId === LEGACY_LIBRARY_FOLDER || isFolderId(folderId)
    if (action === 'create-subfolder') {
      const name = folderName(input.name)
      return hasFolder && name ? { action, folderId, name } : null
    }
    const paperIds = input?.paperIds
    if (!Array.isArray(paperIds) || paperIds.length > 100 ||
        !paperIds.every(id => typeof id === 'string' && id.length <= 120 && isContentSlug(id))) return null
    if (action === 'create' || action === 'add') {
      const relations = Object.fromEntries(paperIds.flatMap(id => {
        const relation = input.relations?.[id]
        return isLibraryRecommendationRelation(relation) ? [[id, relation] as const] : []
      }))
      if (action === 'create') {
        const name = folderName(input.name)
        return name ? { action, name, paperIds, relations } : null
      }
      return hasFolder && paperIds.length ? { action, folderId, paperIds, relations } : null
    }
    if (hasFolder && paperIds.length) {
      if (action === 'remove') return { action, folderId, paperIds }
      if (action === 'move' && (input.subfolderId === undefined || isFolderId(input.subfolderId))) {
        return { action, folderId, paperIds, subfolderId: input.subfolderId }
      }
    }
  } catch { return null }
  return null
}

export async function GET(request: Request) {
  const { user, legacyAccountId } = getLibrarySession(request)
  if (!user) return respond({ error: '请登录后查看个人收藏。' }, 401)
  try {
    return respond({ folders: await readLibraryFavorites(user.phone, legacyAccountId) })
  } catch (error) {
    console.error('[library-favorites] Read failed', (error as Error).name)
    return respond({ error: '暂时无法读取收藏夹，请重试。' }, 503)
  }
}

export async function POST(request: Request) {
  const { user, legacyAccountId } = getLibrarySession(request)
  if (!user) return respond({ error: '请登录后收藏论文。' }, 401)
  if (!isLibrarySameOrigin(request)) return respond({ error: '请在本站页面操作收藏夹。' }, 403)
  const input = await readAction(request)
  if (!input) return respond({ error: '请检查收藏夹名称或论文编号。' }, 400)
  try {
    if (input.action === 'add' || input.action === 'create') {
      const canonical = new Map<string, string>()
      for (const id of Array.from(new Set(input.paperIds))) {
        const paper = readPaperMetadata(id)
        if (!paper || !matchesLibraryType(paper, 'paper')) return respond({ error: `论文 ${id} 当前无法收藏。` }, 400)
        canonical.set(id, paper.slug)
      }
      const relations = input.relations
      input.paperIds = Array.from(new Set(canonical.values()))
      input.relations = Object.fromEntries(Array.from(canonical).flatMap(([requested, slug]) => {
        const relation = relations?.[requested]
        return relation ? [[slug, relation] as const] : []
      }))
    }
    return respond(await updateLibraryFavorites(user.phone, input, legacyAccountId))
  } catch (error) {
    if (error instanceof LibraryFolderNotFound) return respond({ error: '找不到该收藏夹。' }, 404)
    console.error('[library-favorites] Write failed', (error as Error).name)
    return respond({ error: '暂时无法更新收藏夹，请重试。' }, 503)
  }
}
