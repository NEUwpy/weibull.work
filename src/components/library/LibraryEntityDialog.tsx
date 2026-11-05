'use client'

import React, { useEffect, useState } from 'react'
import { ArrowLeft, ArrowUpRight, X } from 'lucide-react'
import { usePreviewDialog } from '@/components/shared/usePreviewDialog'
import type { LibraryAuthor } from '@/lib/library-authors'
import type { LibraryInstitution } from '@/lib/library-institutions'
import type { LibraryCredits } from '@/lib/library-credits'
import { libraryPaperInstitutions } from '@/lib/library-institutions'
import type { LibraryVersion } from '@/lib/library-search-types'
import type { LibraryTitlePresentation } from '@/lib/library-titles'
import { LibraryDocumentLink } from './LibraryDocumentDialog'
import { LibraryPaperTitle } from './LibraryPaperTitle'
import { LibraryAuthors } from './LibraryAuthors'
import { LibraryInstitutions } from './LibraryInstitutions'

interface EntityPaper extends LibraryTitlePresentation {
  slug: string; title: string; author: string; year: number; publication?: string; type?: string; affiliation?: string
  availableVersions: LibraryVersion[]; credits?: LibraryCredits
}

export function LibraryEntityDialog({ href, backLabel, onClose }: { href: string; backLabel?: string; onClose: () => void }) {
  const { dialog, closeButton } = usePreviewDialog(onClose)
  const query = new URL(href, 'http://library.local').searchParams
  const institution = query.has('institution')
  const label = institution ? '单位' : '作者'
  const name = query.get(institution ? 'institution' : 'author') || ''
  const from = query.get('from')
  const [data, setData] = useState<{ profile: LibraryAuthor | LibraryInstitution; papers: EntityPaper[] } | null>(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setData(null); setError('')
    fetch(`/api/library/${institution ? 'institutions' : 'authors'}?${new URLSearchParams({ name })}`, { cache: 'no-store', signal: controller.signal })
      .then(async response => {
        const result = await response.json()
        if (!response.ok) throw new Error(result.error || `${label}资料暂时无法加载。`)
        if (!controller.signal.aborted) setData({ profile: result.author || result.institution, papers: result.papers })
      })
      .catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error && cause.name !== 'TypeError' ? cause.message : '连接失败，请稍后重试。') })
    return () => controller.abort()
  }, [name, institution, label, retry])

  return <dialog {...dialog} className="library-document-dialog library-entity-dialog" data-has-parent={Boolean(backLabel) || undefined} aria-label={`${label}资料`}>
    <div className="library-document-dialog-bar">
      <button type="button" className="library-document-dialog-back" aria-label={backLabel || '返回原窗口'} onClick={onClose}><ArrowLeft size={20} aria-hidden="true" /></button>
      <span className="library-document-dialog-heading">{label}资料</span>
      <button type="button" ref={closeButton} className="library-document-dialog-close" aria-label={`关闭${label}资料`} onClick={onClose}><X size={22} /></button>
    </div>
    <div className="library-document-dialog-scroll library-entity-content">
      {error ? <div role="alert" className="py-16 text-center text-sm text-slate-500"><p>{error}</p><button type="button" className="mt-4 text-blue-600 hover:underline" onClick={() => setRetry(value => value + 1)}>重试</button></div>
        : !data ? <p role="status" className="py-16 text-center text-sm text-slate-400">正在查找{label}的在库文献…</p>
          : <>
            <header className="library-entity-header">
              <div className="min-w-0">
                <h2 className="text-2xl font-medium text-slate-800">{data.profile.name}</h2>
                {data.profile.englishName && <p lang="en" className="mt-2 text-lg text-slate-500">{data.profile.englishName}</p>}
                {data.profile.aliases.some(alias => alias !== data.profile.name && alias !== data.profile.englishName) && <p className="mt-3 text-sm leading-6 text-slate-500">其他{institution ? '名称' : '署名'} · {data.profile.aliases.filter(alias => alias !== data.profile.name && alias !== data.profile.englishName).join(' / ')}</p>}
                {'affiliations' in data.profile && data.profile.affiliations.length > 0 && <div className="mt-5 text-sm leading-7 text-slate-600"><p className="mb-1 text-xs text-slate-400">论文署名单位</p><ul>{data.profile.affiliations.map(item => <li key={`${item.name}-${item.slug}`}><LibraryInstitutions affiliation={item.name} from={item.slug} /><LibraryDocumentLink href={`/library/${item.slug}`} className="ml-2 whitespace-nowrap text-xs text-blue-600 hover:underline">{item.year || item.slug}</LibraryDocumentLink></li>)}</ul></div>}
                {'parent' in data.profile && data.profile.parent && <p className="mt-5 text-sm leading-7 text-slate-600">所属单位 · <LibraryInstitutions affiliation={data.profile.parent} from={from || undefined} /></p>}
              </div>
            </header>
            <div className="mt-7 flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4">
              <h3 className="text-base font-medium text-slate-700">在库文献 <span className="ml-2 text-sm font-normal text-slate-400">{data.papers.length} 篇</span></h3>
              <a href={`https://scholar.google.com/scholar?${new URLSearchParams({ q: `${institution ? '' : 'author:'}"${data.profile.englishName || data.profile.name}"` })}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline">检索更多论文<ArrowUpRight size={15} aria-hidden="true" /></a>
            </div>
            {!data.profile.evidence.length && <p className="mt-4 text-xs leading-6 text-slate-400">按完整{institution ? '单位名称' : '署名'}匹配，可能包含同名{label}。</p>}
            <ol className="library-entity-papers">
              {data.papers.map(paper => <li key={paper.slug} className="library-entity-paper">
                <div className="mb-3 flex flex-wrap items-center gap-3 text-xs text-slate-400"><span>{paper.year > 0 ? paper.year : '年份未登记'}</span><span>{paper.slug}</span>{paper.slug === from && <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-emerald-700">当前文献</span>}</div>
                <LibraryDocumentLink href={`/library/${paper.slug}`} className="library-title text-xl leading-8 text-slate-800 hover:text-blue-800 hover:underline"><LibraryPaperTitle paper={paper} /></LibraryDocumentLink>
                <p className="mt-3 text-sm leading-7 text-slate-500"><LibraryAuthors author={paper.author} credits={paper.credits} from={paper.slug} /></p>
                <p className="mt-2 text-xs leading-6 text-slate-400">{[paper.type, paper.publication].filter(Boolean).join(' · ')}{!paper.availableVersions.length && ' · 全文待补齐'}</p>
                <p className="mt-1 text-xs leading-6 text-slate-500">文献署名单位 · <LibraryInstitutions affiliation={libraryPaperInstitutions(paper).join('；')} credits={paper.credits} from={paper.slug} /></p>
              </li>)}
            </ol>
            {data.profile.evidence.length > 0 && <details className="mt-8 text-xs leading-6 text-slate-400"><summary className="cursor-pointer">{institution ? '名称' : '姓名'}对应依据</summary><ul className="mt-3 space-y-2">{data.profile.evidence.map(item => <li key={item.slug}><LibraryDocumentLink href={`/library/${item.slug}`} className="text-blue-600 hover:underline">{item.slug}</LibraryDocumentLink> · {item.note}</li>)}</ul></details>}
          </>}
    </div>
  </dialog>
}
