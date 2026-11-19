'use client'

import { createContext, useContext, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'
import Link from 'next/link'
import { Check, ChevronDown, Folder, Plus, Star, X } from 'lucide-react'
import { usePreviewDialog } from '@/components/shared/usePreviewDialog'
import { libraryAuthClient, useLibrarySession } from '@/lib/library-auth-client'
import {
  MAX_LIBRARY_FOLDER_NAME, UNFILED_LIBRARY_FOLDER, libraryFavoritesHref,
  type LibraryFavoriteAction, type LibraryFavoriteFolder, type LibraryFavoriteResult,
} from '@/lib/library-favorites'
import { libraryRecommendationLabels, type LibraryRecommendationRelation, type LibraryRecommendationRelations } from '@/lib/library-recommendations'
import { cn } from '@/lib/utils'
import { LibraryLoginDialog } from './LibraryLoginDialog'

interface FavoriteSelection {
  paperIds: string[]
  relations?: LibraryRecommendationRelations
  batch?: boolean
  removeOnly?: boolean
}

interface FavoriteStarIntent { paperId: string; relation?: LibraryRecommendationRelation; folderId?: string }

interface FavoritesContext {
  signedIn: boolean
  checkingSession: boolean
  folders?: LibraryFavoriteFolder[]
  foldersByPaper: ReadonlyMap<string, readonly string[]>
  loadError: string
  busy: boolean
  retry: () => void
  login: () => void
  choose: (selection: FavoriteSelection) => void
  toggle: (intent: FavoriteStarIntent) => void
  update: (action: LibraryFavoriteAction) => Promise<LibraryFavoriteResult | null>
}

const Context = createContext<FavoritesContext | null>(null)
const endpoint = '/api/library/favorites'

async function checkedResponse<T>(response: Response): Promise<T> {
  const data = await response.json()
  if (response.status === 401) libraryAuthClient.invalidate()
  if (!response.ok) throw new Error(data.error || '暂时无法使用收藏夹，请重试。')
  return data
}

export function useLibraryFavorites() {
  return useContext(Context)
}

export function LibraryFavoritesProvider({ children }: { children: ReactNode }) {
  const session = useLibrarySession()
  const phone = session.user?.phone
  const [data, setData] = useState<{ phone: string; folders?: LibraryFavoriteFolder[]; error?: string }>()
  const [reload, setReload] = useState(0)
  const [selection, setSelection] = useState<FavoriteSelection>()
  const [loginOpen, setLoginOpen] = useState(false)
  const [loginContainer, setLoginContainer] = useState<HTMLElement | null>(null)
  const [notice, setNotice] = useState<{ text: string; href?: string }>()
  const [busy, setBusy] = useState(false)
  const pending = useRef(false)
  const afterLogin = useRef<FavoriteStarIntent>()
  const folders = data?.phone === phone ? data?.folders : undefined
  const loadError = data?.phone === phone ? data?.error || '' : ''
  const foldersByPaper = useMemo(() => {
    const index = new Map<string, string[]>()
    for (const folder of folders ?? []) {
      for (const id of folder.paperIds) {
        const memberships = index.get(id)
        if (memberships) memberships.push(folder.id)
        else index.set(id, [folder.id])
      }
    }
    return index
  }, [folders])

  useEffect(() => {
    if (!phone) {
      setData(undefined)
      setNotice(undefined)
      return
    }
    const request = new AbortController()
    setData({ phone })
    fetch(endpoint, { cache: 'no-store', signal: request.signal })
      .then(checkedResponse<{ folders: LibraryFavoriteFolder[] }>)
      .then(({ folders }) => { if (!request.signal.aborted) setData({ phone, folders }) })
      .catch(error => {
        if (!request.signal.aborted) setData({ phone, error: error instanceof TypeError ? '收藏夹连接失败，请重试。' : error.message })
      })
    return () => request.abort()
  }, [phone, session.expiresAt, reload])

  useEffect(() => {
    if (!notice) return
    const timeout = setTimeout(() => setNotice(undefined), 5500)
    return () => clearTimeout(timeout)
  }, [notice])

  function login() {
    setLoginContainer(document.activeElement?.closest<HTMLDialogElement>('dialog[open]') ?? null)
    setLoginOpen(true)
  }

  function choose(next: FavoriteSelection) {
    setSelection(next)
    if (!phone) login()
  }

  async function update(action: LibraryFavoriteAction) {
    if (!phone || !folders || pending.current) return null
    const expiresAt = session.expiresAt
    pending.current = true
    setBusy(true)
    try {
      const response = await fetch(endpoint, {
        method: 'POST', cache: 'no-store', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(action),
      })
      const result = await checkedResponse<LibraryFavoriteResult>(response)
      const active = libraryAuthClient.getSnapshot()
      if (active.user?.phone !== phone || active.expiresAt !== expiresAt) return null
      setData({ phone, folders: result.folders })
      if (action.action === 'move' && result.changed) {
        const name = result.folder.subfolders?.find(child => child.id === action.subfolderId)?.name ?? '未分组'
        setNotice({ text: `已移到「${name}」`, href: libraryFavoritesHref(result.folder.id, action.subfolderId ?? UNFILED_LIBRARY_FOLDER) })
      } else if ('paperIds' in action && action.action !== 'move' && action.paperIds.length) {
        let text = `「${result.folder.name}」中已有这些论文`
        if (action.action === 'remove') text = `已从「${result.folder.name}」移除`
        else if (result.changed) text = action.relations && Object.keys(action.relations).length
          ? `已在「${result.folder.name}」按推荐用途整理 ${result.changed} 篇论文`
          : `已将 ${result.changed} 篇论文加入「${result.folder.name}」`
        setNotice({ text, href: libraryFavoritesHref(result.folder.id) })
      }
      return result
    } finally {
      pending.current = false
      setBusy(false)
    }
  }

  function submit(action: LibraryFavoriteAction) {
    void update(action).catch(error => {
      setNotice({ text: error instanceof TypeError ? '收藏夹连接失败，请重试。' : error.message })
    })
  }

  function toggle(intent: FavoriteStarIntent) {
    const { paperId, relation, folderId } = intent
    const paperIds = [paperId]
    const relations = relation ? { [paperId]: relation } : undefined
    if (!phone) {
      afterLogin.current = intent
      login()
      return
    }
    if (!folders) { choose({ paperIds, relations }); return }

    const memberships = foldersByPaper.get(paperId) ?? []
    if (!folderId && memberships.length > 1) {
      choose({ paperIds, removeOnly: true })
      return
    }
    const target = folderId ?? memberships[0] ?? (folders.length === 1 ? folders[0].id : undefined)
    if (!target) { choose({ paperIds, relations }); return }
    if (memberships.includes(target)) submit({ action: 'remove', folderId: target, paperIds })
    else submit({ action: 'add', folderId: target, paperIds, relations })
  }

  useEffect(() => {
    const intent = afterLogin.current
    if (!intent || loginOpen || !phone || (!folders && !loadError)) return
    afterLogin.current = undefined
    toggle(intent)
  })

  const close = () => setSelection(undefined)
  const value: FavoritesContext = {
    signedIn: Boolean(phone), checkingSession: session.status === 'loading', folders, foldersByPaper, busy,
    loadError, retry: () => setReload(value => value + 1),
    login, choose, toggle, update,
  }
  return <Context.Provider value={value}>
    {children}
    <LibraryLoginDialog open={loginOpen} purpose="favorites" container={loginContainer} onClose={() => {
      setLoginOpen(false)
      if (!libraryAuthClient.getSnapshot().user) {
        afterLogin.current = undefined
        close()
      }
    }} />
    {selection && phone && !loginOpen && <FavoritePicker selection={selection} favorites={value} onClose={close} />}
    {notice && <div className="fixed inset-x-4 bottom-5 z-50 mx-auto flex w-fit max-w-[calc(100%-2rem)] flex-wrap items-center gap-x-3 gap-y-1 break-words rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-lg">
      <span role={notice.href ? 'status' : 'alert'} className={notice.href ? undefined : 'text-rose-700'}>{notice.text}</span>
      {notice.href && <Link href={notice.href} prefetch={false} onClick={() => setNotice(undefined)} className="shrink-0 text-blue-700 hover:underline">查看收藏夹</Link>}
    </div>}
  </Context.Provider>
}

const iconButton = 'relative z-20 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-blue-600'

export function LibraryFavoriteButton({ paperId, relation, folderId }: FavoriteStarIntent) {
  const favorites = useLibraryFavorites()
  if (!favorites) return null
  const memberships = favorites.foldersByPaper.get(paperId) ?? []
  const saved = folderId ? memberships.includes(folderId) : memberships.length > 0
  const chooseRemoval = !folderId && memberships.length > 1
  const chooseDestination = !saved && !folderId && favorites.folders?.length !== 1
  const waiting = favorites.checkingSession || (favorites.signedIn && !favorites.folders && !favorites.loadError)
  return <span className="relative z-20 inline-flex shrink-0 items-center">
    <button type="button" aria-label={`${saved ? '取消收藏' : '收藏论文'} ${paperId}`} aria-pressed={saved}
      title={chooseRemoval ? '选择要取消收藏的主题夹' : saved ? '取消收藏' : '收藏论文'}
      aria-haspopup={chooseDestination || chooseRemoval || !favorites.signedIn || !!favorites.loadError ? 'dialog' : undefined}
      disabled={waiting || favorites.busy} className={cn(iconButton, saved && 'text-amber-700')}
      onClick={() => favorites.toggle({ paperId, relation, folderId })}>
      <Star size={15} strokeWidth={1.65} fill={saved ? 'currentColor' : 'none'} aria-hidden="true" />
    </button>
    <button type="button" aria-label={`选择论文 ${paperId} 的收藏夹`} aria-haspopup="dialog" title="选择收藏夹"
      disabled={waiting || favorites.busy} className={cn(iconButton, 'w-6')}
      onClick={() => favorites.choose({ paperIds: [paperId], relations: relation ? { [paperId]: relation } : undefined })}>
      <ChevronDown size={12} aria-hidden="true" />
    </button>
  </span>
}

export function LibraryFavoritesLoading({ error, retry }: { error: string; retry: () => void }) {
  return error ? <p role="alert" className="text-sm leading-6 text-rose-700">{error} <button type="button" className="underline" onClick={retry}>重试</button></p>
    : <p role="status" className="text-sm leading-6 text-slate-500">正在读取收藏夹…</p>
}

export function LibraryFavoriteFolderForm({ busy, onSave, onCancel, label = '收藏夹名称', placeholder = '主题名称' }: {
  busy: boolean; onSave: (name: string) => Promise<void>; onCancel: () => void; label?: string; placeholder?: string
}) {
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim() || busy) return
    setError('')
    try { await onSave(name.trim()) } catch (error) {
      setError(error instanceof Error && !(error instanceof TypeError) ? error.message : '收藏夹连接失败，请重试。')
    }
  }
  return <form onSubmit={submit} className="space-y-2">
    <input autoFocus aria-label={label} placeholder={placeholder} maxLength={MAX_LIBRARY_FOLDER_NAME} required
      value={name} onChange={event => setName(event.target.value)}
      className="h-10 w-full min-w-0 rounded-lg border border-slate-300 px-3 text-sm outline-blue-600" />
    {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
    <div className="flex justify-end gap-2 text-sm">
      <button type="button" onClick={onCancel} className="rounded-lg px-3 py-2 text-slate-600 hover:bg-slate-100">取消</button>
      <button type="submit" disabled={!name.trim() || busy} className="rounded-lg bg-blue-700 px-3 py-2 text-white hover:bg-blue-800 disabled:opacity-40">创建</button>
    </div>
  </form>
}

function FavoritePicker({ selection, favorites, onClose }: { selection: FavoriteSelection; favorites: FavoritesContext; onClose: () => void }) {
  const { dialog, closeButton } = usePreviewDialog(onClose)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const { paperIds: ids, relations, batch, removeOnly } = selection
  const singleRelation = relations?.[ids[0]]
  const description = batch ? `${ids.length} 篇论文${relations ? '，按推荐用途分组' : ''}`
    : singleRelation ? `${ids[0]} · ${libraryRecommendationLabels[singleRelation]}` : ids[0]
  async function save(action: LibraryFavoriteAction) {
    if (await favorites.update(action)) onClose()
  }
  return <dialog {...dialog} aria-labelledby="library-favorite-picker-title"
    className="m-auto max-h-[85dvh] w-[calc(100%-2rem)] max-w-md rounded-2xl p-5 text-slate-800 shadow-2xl backdrop:bg-slate-900/35 sm:p-6">
    <header className="mb-4 flex items-start justify-between gap-3">
      <div>
        <h2 id="library-favorite-picker-title" className="text-lg font-semibold">{removeOnly ? '从哪个收藏夹移除？' : batch ? '批量收藏论文' : '加入收藏夹'}</h2>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </div>
      <button type="button" ref={closeButton} aria-label="关闭收藏夹选择" className={iconButton} onClick={onClose}><X size={18} /></button>
    </header>
    {!favorites.folders ? <LibraryFavoritesLoading error={favorites.loadError} retry={favorites.retry} /> : <>
      <ul className="mb-3 max-h-[42dvh] space-y-1 overflow-y-auto overscroll-contain">
        {favorites.folders.filter(folder => !removeOnly || folder.paperIds.includes(ids[0])).map(folder => {
          const contained = ids.every(id => folder.paperIds.includes(id))
          const organize = contained && ids.some(id => relations?.[id] && !folder.paperSubfolders?.[id])
          const remove = contained && !batch && !organize
          return <li key={folder.id}><button type="button" disabled={favorites.busy || (batch && contained && !organize)}
            onClick={() => {
              setError('')
              const target = { folderId: folder.id, paperIds: ids }
              void save(remove ? { ...target, action: 'remove' } : { ...target, action: 'add', relations }).catch(error => {
                setError(error instanceof TypeError ? '收藏夹连接失败，请重试。' : error.message)
              })
            }}
            className="flex min-h-11 w-full items-center gap-3 rounded-lg px-2 py-2 text-left text-sm hover:bg-slate-100 focus-visible:outline-blue-600 disabled:text-slate-500">
            <Folder size={17} aria-hidden="true" className="shrink-0 text-slate-500" />
            <span className="min-w-0 flex-1 break-words">{folder.name}</span>
            {contained ? <><Check size={15} className="shrink-0 text-emerald-700" aria-hidden="true" />
              <span className="shrink-0 text-xs text-slate-600">{remove ? '移除' : organize ? '整理分组' : '已收藏'}</span></> : <Plus size={15} aria-hidden="true" className="shrink-0 text-slate-500" />}
          </button></li>
        })}
      </ul>
      {error && <p role="alert" className="mb-3 text-sm text-rose-700">{error}</p>}
      {!removeOnly && (creating || !favorites.folders.length ? <LibraryFavoriteFolderForm busy={favorites.busy}
        onSave={name => save({ action: 'create', name, paperIds: ids, relations })}
        onCancel={() => favorites.folders?.length ? setCreating(false) : onClose()} />
        : <button type="button" onClick={() => setCreating(true)} className="inline-flex min-h-10 items-center gap-2 rounded-lg px-2 text-sm text-blue-700 hover:bg-blue-50"><Plus size={16} aria-hidden="true" />新建收藏夹</button>)}
    </>}
  </dialog>
}
