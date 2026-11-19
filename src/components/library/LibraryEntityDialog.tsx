'use client'

import React, { useEffect, useState } from 'react'
import { ArrowUpRight } from 'lucide-react'
import type { LibraryEntityKind, LibraryEntityProfile } from '@/lib/library-directory-index'
import type { PaperMetadata } from '@/lib/server/literature'
import { libraryEntityPreviewKind } from '@/lib/library-preview-history'
import { LibraryDocumentLink } from './LibraryDocumentDialog'
import { LibraryInstitutions } from './LibraryInstitutions'
import { LibraryPreviewDialog } from './LibraryPreviewDialog'
import { LibraryJournalDetails } from './LibraryJournalDetails'
import { LibraryCollectionDetails } from './LibraryCollectionDetails'
import { LibraryAuthorInstitutionLinks, LibraryInstitutionAuthorLinks } from './LibraryAuthorshipLinks'

const entityResources = {
  author: { label: '作者', endpoint: 'authors', parameter: 'name' },
  institution: { label: '机构', endpoint: 'institutions', parameter: 'name' },
  journal: { label: '期刊', endpoint: 'journals', parameter: 'key' },
}

type EntityData = LibraryEntityProfile<PaperMetadata>

export function LibraryEntityDialog({ href, backLabel, onClose, findEntity }: {
  href: string; backLabel?: string; onClose: () => void
  findEntity?: (kind: LibraryEntityKind, key: string) => EntityData | undefined
}) {
  const query = new URL(href, 'http://library.local').searchParams
  const kind = libraryEntityPreviewKind(href) || 'author'
  const institution = kind === 'institution'
  const { label, endpoint, parameter } = entityResources[kind]
  const name = query.get(kind) || ''
  const from = query.get('from')
  const [remoteData, setRemoteData] = useState<EntityData | null>(null)
  const [remoteError, setRemoteError] = useState('')
  const [retry, setRetry] = useState(0)
  const local = typeof findEntity === 'function'
  const data = local ? findEntity(kind, name) ?? null : remoteData
  const error = local ? data ? '' : `未找到该${label}的在库文献。` : remoteError
  const profile = institution ? data?.institution : data?.author
  const aliases = profile?.aliases.filter(alias => alias !== profile.name && alias !== profile.englishName) || []
  const otherSignatures = data?.author
    ? [data.author.englishName, ...aliases].filter(name => name && name !== data.author?.name)
    : []
  useEffect(() => {
    if (local) return
    const controller = new AbortController()
    setRemoteData(null)
    setRemoteError('')
    fetch(`/api/library/${endpoint}?${new URLSearchParams({ [parameter]: name })}`, { cache: 'no-store', signal: controller.signal })
      .then(async response => {
        const result = await response.json()
        if (!response.ok) throw new Error(result.error || `${label}资料暂时无法加载。`)
        if (!controller.signal.aborted) setRemoteData(result)
      })
      .catch(cause => { if (!controller.signal.aborted) setRemoteError(cause instanceof Error && cause.name !== 'TypeError' ? cause.message : '连接失败，请稍后重试。') })
    return () => controller.abort()
  }, [local, name, endpoint, parameter, label, retry])

  return <LibraryPreviewDialog title={`${label}资料`} backLabel={backLabel} onClose={onClose} padded>
      {error ? <div role="alert" className="py-16 text-center text-sm text-slate-500"><p>{error}</p>{!local && <button type="button" className="mt-4 text-blue-600 hover:underline" onClick={() => setRetry(value => value + 1)}>重试</button>}</div>
        : !data ? <p role="status" className="py-16 text-center text-sm text-slate-400">正在查找{label}的在库文献…</p>
          : kind === 'journal' && data.journal ? <LibraryJournalDetails journal={data.journal} papers={data.papers} />
          : profile && <>
            <LibraryCollectionDetails title={profile.name} papers={data.papers} profile={{ sourcePaper: from }} actions={
              <a href={`https://scholar.google.com/scholar?${new URLSearchParams({ q: `${institution ? '' : 'author:'}"${profile.englishName || profile.name}"` })}`}
                target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline">
                检索更多论文<ArrowUpRight size={15} aria-hidden="true" />
              </a>
            }>
              {data.author && <LibraryAuthorInstitutionLinks key={data.author.key} author={data.author} papers={data.papers} from={from} />}
              {data.institution && <>
                {profile.englishName && profile.englishName !== profile.name && <p lang="en">{profile.englishName}</p>}
                {data.institution.parent && <p>所属单位 · <LibraryInstitutions affiliation={data.institution.parent} from={from || undefined} /></p>}
                <LibraryInstitutionAuthorLinks institution={data.institution} papers={data.papers} from={from} />
                {!profile.evidence.length && <p className="text-xs text-slate-500">按完整单位名称匹配，可能包含同名单位。</p>}
              </>}
            </LibraryCollectionDetails>
            {otherSignatures.length > 0 && <details className="mt-8 text-xs leading-6 text-slate-500">
              <summary className="cursor-pointer">其他署名</summary>
              <p className="mt-2">{otherSignatures.join(' / ')}</p>
            </details>}
            {data.institution && aliases.length > 0 && <details className="mt-8 text-xs leading-6 text-slate-500">
              <summary className="cursor-pointer">其他名称</summary>
              <ul className="mt-2 space-y-1 break-words">{aliases.map(alias => <li key={alias}>{alias}</li>)}</ul>
            </details>}
            {data.institution && profile.evidence.length > 0 && <details className="mt-8 text-xs leading-6 text-slate-400"><summary className="cursor-pointer">名称对应依据</summary><ul className="mt-3 space-y-2">{profile.evidence.map(item => <li key={item.slug}><LibraryDocumentLink href={`/library/${item.slug}`} className="text-blue-600 hover:underline">{item.slug}</LibraryDocumentLink> · {item.note}</li>)}</ul></details>}
          </>}
  </LibraryPreviewDialog>
}
