'use client'

import { useEffect, useId, useState, type ReactNode } from 'react'
import { useSearchParams } from 'next/navigation'
import { Folder, FolderInput, Plus, Star, X } from 'lucide-react'
import { usePreviewDialog } from '@/components/shared/usePreviewDialog'
import { UNFILED_LIBRARY_FOLDER, libraryFavoritesHref, type LibraryFavoriteAction, type LibraryFavoriteFolder, type LibraryFavoriteResult, type LibraryFavoriteSubfolder } from '@/lib/library-favorites'
import type { PaperMetadata } from '@/lib/server/literature'
import { cn } from '@/lib/utils'
import { LibraryCard } from './LibraryCard'
import { LibraryFavoriteButton, LibraryFavoriteFolderForm, LibraryFavoritesLoading, useLibraryFavorites } from './LibraryFavorites'
import { LibraryMasonry } from './LibraryMasonry'
import { useLibraryScrollBatches } from './useLibraryScrollBatches'

const favoritePaperDragType = 'application/x-weibull-favorite-paper'
const panel = 'min-w-0 rounded-xl border border-slate-200 bg-white p-3 sm:p-4 xl:sticky xl:top-20 xl:max-h-[calc(100dvh-6rem)] xl:overflow-y-auto'
const createButton = 'inline-flex min-h-9 items-center gap-1 rounded-lg px-2 text-sm text-blue-700 hover:bg-blue-50'
const iconButton = 'inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-blue-600'

function sectionHeadingId(id: string) {
  return `favorite-section-${id}`
}

function scrollToFavoriteSection(id: string) {
  document.getElementById(sectionHeadingId(id))?.scrollIntoView({ block: 'start' })
}

function FavoritePaperCards({ folderId, ids, papers, actions }: {
  folderId: string; ids: string[]; papers: ReadonlyMap<string, PaperMetadata>
  actions: (id: string) => ReactNode
}) {
  const { visibleCount, hasMore, sentinel } = useLibraryScrollBatches(ids.length, 12)
  return <>
    <LibraryMasonry maxColumns={3}>
      {ids.slice(-visibleCount).reverse().map(id => {
        const paper = papers.get(id)
        if (paper) return <LibraryCard key={id} paper={paper} favoriteFolderId={folderId} actions={actions(id)} />
        return <article key={id} className="library-card rounded-xl border border-slate-200 bg-slate-50">
          <div className="flex items-start justify-between gap-3 p-7">
            <div className="min-w-0 break-words">
              <h4 className="text-base font-medium text-slate-700">{id}</h4>
              <p className="mt-1 text-sm text-slate-500">文献当前未上架</p>
            </div>
            <div className="flex shrink-0 items-center">{actions(id)}<LibraryFavoriteButton paperId={id} folderId={folderId} /></div>
          </div>
        </article>
      })}
    </LibraryMasonry>
    {hasMore && <div ref={sentinel} className="h-px" aria-hidden="true" />}
  </>
}

export function LibraryFavoritesPage({ papers }: { papers: ReadonlyMap<string, PaperMetadata> }) {
  const favorites = useLibraryFavorites()
  const searchParams = useSearchParams()
  const selectedId = searchParams.get('folder')
  const selectedSubfolderId = searchParams.get('subfolder')
  const [creating, setCreating] = useState(false)
  if (!favorites) return null

  if (favorites.checkingSession || (favorites.signedIn && !favorites.folders)) return <section aria-label="收藏夹" className="rounded-xl border border-slate-200 bg-white p-6">
    <LibraryFavoritesLoading error={favorites.loadError} retry={favorites.retry} />
  </section>

  if (!favorites.signedIn || !favorites.folders) return <section aria-label="收藏夹" className="rounded-xl border border-slate-200 bg-white px-5 py-14 text-center">
    <Star size={24} aria-hidden="true" className="mx-auto mb-3 text-slate-400" />
    <h2 className="text-lg font-semibold text-slate-800">个人收藏夹</h2>
    <button type="button" onClick={favorites.login} className="mt-4 rounded-lg bg-blue-700 px-4 py-2.5 text-sm text-white hover:bg-blue-800">登录查看收藏</button>
  </section>

  // Older links to the system folder could contain only a subfolder ID.
  const folder = favorites.folders.find(item => item.id === selectedId)
    ?? (!selectedId ? favorites.folders.find(item => item.subfolders?.some(child => child.id === selectedSubfolderId)) : undefined)
    ?? favorites.folders[0]
  const selectFolder = (folderId: string) => window.history.replaceState(null, '', libraryFavoritesHref(folderId))
  return <section aria-label="个人收藏夹" className="grid min-w-0 items-start gap-4 xl:grid-cols-[13rem_minmax(0,1fr)_12rem] xl:gap-5">
    <aside className={panel}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 px-2">
        <h2 className="text-sm font-semibold text-slate-800">个人收藏夹</h2>
        {!creating && <button type="button" className={createButton}
          onClick={() => setCreating(true)}><Plus size={15} aria-hidden="true" />新建</button>}
      </div>
      {creating && <div className="mb-3 px-2"><LibraryFavoriteFolderForm busy={favorites.busy} onCancel={() => setCreating(false)} onSave={async name => {
        const result = await favorites.update({ action: 'create', name, paperIds: [] })
        if (!result) return
        selectFolder(result.folder.id)
        setCreating(false)
      }} /></div>}
      <ul className="flex flex-wrap gap-1 xl:grid">
        {favorites.folders.map(item => <li key={item.id} className="min-w-0 max-w-full">
          <button type="button" aria-pressed={item.id === folder?.id} onClick={() => selectFolder(item.id)}
            className={`flex min-h-10 w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm ${item.id === folder?.id ? 'bg-blue-50 font-medium text-blue-800' : 'text-slate-700 hover:bg-slate-100'}`}>
            <Folder size={16} aria-hidden="true" className="shrink-0" />
            <span className="min-w-0 flex-1 break-words">{item.name}</span>
            <span className="tabular-nums text-slate-500">{item.paperIds.length}</span>
          </button>
        </li>)}
      </ul>
    </aside>

    {folder ? <FavoriteFolderContents key={folder.id} folder={folder} selectedId={selectedSubfolderId}
      papers={papers} busy={favorites.busy} update={favorites.update} />
      : <div className="rounded-xl border border-slate-200 bg-white px-5 py-14 text-center xl:col-span-2">
        <h2 className="text-base font-semibold text-slate-800">还没有收藏夹</h2>
        <p className="mt-2 text-sm text-slate-500">新建一个主题夹，开始收藏论文。</p>
      </div>}
  </section>
}

function FavoriteFolderContents({ folder, selectedId, papers, busy, update }: {
  folder: LibraryFavoriteFolder; selectedId: string | null; papers: ReadonlyMap<string, PaperMetadata>; busy: boolean
  update: (action: LibraryFavoriteAction) => Promise<LibraryFavoriteResult | null>
}) {
  const [creating, setCreating] = useState(false)
  const [moving, setMoving] = useState<string>()
  const [dragged, setDragged] = useState<string>()
  const [dropTarget, setDropTarget] = useState<string>()
  const [error, setError] = useState('')
  const children = [...(folder.subfolders ?? []), { id: UNFILED_LIBRARY_FOLDER, name: '未分组' }]
  const currentSection = children.find(child => child.id === selectedId)?.id
  const assignments = new Map(Object.entries(folder.paperSubfolders ?? {}))
  const byChild = new Map(children.map(child => [child.id, [] as string[]]))
  for (const id of folder.paperIds) byChild.get(assignments.get(id) ?? UNFILED_LIBRARY_FOLDER)?.push(id)

  useEffect(() => {
    if (currentSection) scrollToFavoriteSection(currentSection)
  }, [currentSection])

  function select(id: string) {
    if (currentSection === id) scrollToFavoriteSection(id)
    else window.history.replaceState(null, '', libraryFavoritesHref(folder.id, id))
  }
  const targetFor = (id: string) => assignments.get(id) ?? UNFILED_LIBRARY_FOLDER
  const clearDrag = () => { setDragged(undefined); setDropTarget(undefined) }
  const move = (id: string, target: string) => update({ action: 'move', folderId: folder.id, paperIds: [id],
    subfolderId: target === UNFILED_LIBRARY_FOLDER ? undefined : target })

  function moveButton(id: string) {
    if (children.length === 1) return null
    return <button type="button" className={cn(iconButton, 'cursor-grab active:cursor-grabbing')} disabled={busy}
      aria-haspopup="dialog" aria-label={`移动论文 ${id}`} title="移动论文，或拖到目标小节" draggable={!busy}
      onClick={() => setMoving(id)} onDragStart={event => {
        event.dataTransfer.effectAllowed = 'move'
        event.dataTransfer.setData(favoritePaperDragType, id)
        setDragged(id)
      }} onDragEnd={clearDrag}><FolderInput size={16} aria-hidden="true" /></button>
  }

  return <>
    <nav aria-label="收藏目录" className={cn(panel, 'xl:order-3')}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 px-2">
        <h2 className="text-sm font-semibold text-slate-800">目录</h2>
        {!creating && <button type="button" onClick={() => setCreating(true)} className={createButton}><Plus size={15} aria-hidden="true" />新建子夹</button>}
      </div>
      {creating && <div className="mb-3 px-2"><LibraryFavoriteFolderForm label="子文件夹名称" placeholder="子文件夹名称" busy={busy}
        onCancel={() => setCreating(false)} onSave={async name => {
          const result = await update({ action: 'create-subfolder', folderId: folder.id, name })
          if (!result) return
          const child = result.folder.subfolders?.find(item => item.name === name.normalize('NFC'))
          if (child) select(child.id)
          setCreating(false)
        }} /></div>}
      <ol className="space-y-0.5">
        {children.map(child => <li key={child.id} className="min-w-0"><button type="button"
          aria-current={currentSection === child.id ? 'location' : undefined} onClick={() => select(child.id)}
          className={cn(childRow(currentSection === child.id), dropTarget === child.id && 'bg-blue-100 text-blue-900')}>
          <span className="min-w-0 flex-1 break-words">{child.name}</span>
          <span className="tabular-nums text-slate-500">{byChild.get(child.id)?.length ?? 0}</span>
        </button></li>)}
      </ol>
    </nav>

    <div className="min-w-0 xl:order-2">
      <header className="mb-5 flex items-baseline justify-between gap-3 rounded-xl border border-slate-200 bg-white px-5 py-4 sm:px-6">
        <h2 className="min-w-0 break-words text-lg font-semibold text-slate-800">{folder.name}</h2>
        <span className="shrink-0 text-sm tabular-nums text-slate-500">{folder.paperIds.length} 篇</span>
      </header>
      {error && <p role="alert" className="mb-3 text-sm text-rose-700">{error}</p>}
      {children.map(child => {
        const ids = byChild.get(child.id) ?? []
        const headingId = sectionHeadingId(child.id)
        const activeDrop = dropTarget === child.id
        return <section key={child.id} aria-labelledby={headingId} data-drop-active={activeDrop || undefined}
          className={cn('min-w-0 rounded-lg', activeDrop && 'bg-blue-50 ring-2 ring-inset ring-blue-500')}
          onDragOver={event => {
            if (!dragged || busy || !event.dataTransfer.types.includes(favoritePaperDragType)) return
            event.preventDefault()
            event.dataTransfer.dropEffect = 'move'
            if (!activeDrop) setDropTarget(child.id)
          }}
          onDragLeave={event => {
            if (!(event.relatedTarget instanceof Node && event.currentTarget.contains(event.relatedTarget))) {
              setDropTarget(current => current === child.id ? undefined : current)
            }
          }}
          onDrop={event => {
            if (!event.dataTransfer.types.includes(favoritePaperDragType)) return
            event.preventDefault()
            clearDrag()
            const id = event.dataTransfer.getData(favoritePaperDragType)
            if (busy || !id || id !== dragged || targetFor(id) === child.id) return
            setError('')
            void move(id, child.id).catch(cause => setError(moveError(cause)))
          }}>
          <div className="mb-3 flex items-baseline justify-between gap-3 border-b border-slate-200 px-2 pb-2">
            <h3 id={headingId} className="min-w-0 scroll-mt-24 break-words text-base font-semibold text-slate-800">{child.name}</h3>
            <span className="shrink-0 text-sm tabular-nums text-slate-500">{ids.length} 篇</span>
          </div>
          {ids.length ? <FavoritePaperCards folderId={folder.id} ids={ids} papers={papers} actions={moveButton} />
            : <div className={cn('rounded-lg border border-dashed px-4 py-5 text-center text-sm text-slate-500', activeDrop ? 'border-blue-400 bg-blue-100/50' : 'border-slate-300')}>
              {folder.paperIds.length ? '此处暂无论文' : '这里还没有收藏的论文'}
            </div>}
          {/* The space before the next heading is part of this section's drop target. */}
          <div className="min-h-9 px-2 py-2 text-xs text-blue-800" aria-hidden="true">
            {activeDrop && `松手放入「${child.name}」`}
          </div>
        </section>
      })}
    </div>
    {moving && <MoveFavoritePaper id={moving} children={children} current={targetFor(moving)} busy={busy}
      onClose={() => setMoving(undefined)} onMove={async child => { if (await move(moving, child)) setMoving(undefined) }} />}
  </>
}

function childRow(active: boolean) {
  return cn('flex min-h-10 w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm',
    active ? 'bg-blue-50 font-medium text-blue-800' : 'text-slate-700 hover:bg-slate-100')
}

function moveError(cause: unknown) {
  return cause instanceof Error && !(cause instanceof TypeError) ? cause.message : '移动失败，请重试。'
}

function MoveFavoritePaper({ id, children, current, busy, onMove, onClose }: {
  id: string; children: LibraryFavoriteSubfolder[]; current: string; busy: boolean
  onMove: (target: string) => Promise<void>; onClose: () => void
}) {
  const titleId = useId()
  const { dialog, closeButton } = usePreviewDialog(onClose)
  const [error, setError] = useState('')
  return <dialog {...dialog} aria-labelledby={titleId}
    className="m-auto max-h-[85dvh] w-[calc(100%-2rem)] max-w-md rounded-2xl p-5 text-slate-800 shadow-2xl backdrop:bg-slate-900/35">
    <header className="mb-4 flex items-start justify-between gap-3">
      <div><h2 id={titleId} className="text-lg font-semibold">移动论文</h2><p className="mt-1 text-sm text-slate-500">{id}</p></div>
      <button type="button" ref={closeButton} onClick={onClose} aria-label="关闭移动论文" className={iconButton}><X size={18} /></button>
    </header>
    <ul className="space-y-1 overflow-y-auto overscroll-contain">
      {children.map(child => <li key={child.id}><button type="button" disabled={busy || child.id === current}
        onClick={() => { setError(''); void onMove(child.id).catch(cause => setError(moveError(cause))) }}
        className={cn(childRow(child.id === current), 'min-h-11')}>
        <Folder size={16} aria-hidden="true" className="shrink-0" />
        <span className="min-w-0 flex-1 break-words">{child.name}</span>
        {child.id === current && <span className="shrink-0 text-xs">当前位置</span>}
      </button></li>)}
    </ul>
    {error && <p role="alert" className="mt-3 text-sm text-rose-700">{error}</p>}
  </dialog>
}
