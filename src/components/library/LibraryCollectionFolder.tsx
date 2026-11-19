'use client'

import React from 'react'
import { libraryInstitutionPreviewLimit } from '@/lib/library-institutions'
import { LibraryDocumentLink as Link } from './LibraryDocumentDialog'

type FolderKind = 'problem' | 'author' | 'institution'

export function LibraryCollectionFolder({ kind, folderKey, name, description, affiliations, count, href, onOpen, title, selected, opensDialog }: {
  kind: FolderKind
  folderKey: string; name: string; description?: string
  affiliations?: string[]
  count: number; href: string; onOpen?: () => void; title?: string; selected?: boolean; opensDialog?: boolean
}) {
  const affiliationLabel = affiliations?.join('；')
  const displayedAffiliations = affiliations?.slice(0, libraryInstitutionPreviewLimit) ?? []
  const additionalAffiliations = (affiliations?.length ?? 0) - libraryInstitutionPreviewLimit
  return <Link href={href} prefetch={false} className="library-collection-folder" data-kind={kind} data-folder-key={folderKey} data-open={selected || undefined}
    aria-label={`${name}，${count} 篇文献${displayedAffiliations.length ? `，署名机构 ${displayedAffiliations.join('；')}` : ''}${additionalAffiliations > 0 ? `，另 ${additionalAffiliations} 家` : ''}`}
    aria-current={!opensDialog && selected ? 'page' : undefined}
    aria-haspopup={opensDialog ? 'dialog' : undefined} aria-expanded={opensDialog ? !!selected : undefined}
    title={title || [name, description, affiliationLabel].filter(Boolean).join('\n')}
    onClick={onOpen && (event => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
      event.preventDefault()
      if (opensDialog) event.currentTarget.focus({ preventScroll: true })
      onOpen()
    })}>
    {kind === 'problem' && <span className="collection-folder-back" aria-hidden="true">
      {count > 0 && <span className="collection-folder-sheet" />}
      {count > 1 && <span className="collection-folder-sheet" />}
    </span>}
    <span className="collection-folder-face">
      <span className="collection-folder-name" dir="auto">{name}</span>
      {description && kind !== 'author' && <span className="collection-folder-detail" dir="auto">{description}</span>}
      {displayedAffiliations.length > 0 && <span className="collection-folder-affiliations">
        {displayedAffiliations.map(affiliation => <span key={affiliation} dir="auto">{affiliation}</span>)}
        {additionalAffiliations > 0 && <span>另 {additionalAffiliations} 家</span>}
      </span>}
      <span className="collection-folder-count" data-empty={count === 0 || undefined}><b>{count}</b> 篇</span>
    </span>
  </Link>
}
