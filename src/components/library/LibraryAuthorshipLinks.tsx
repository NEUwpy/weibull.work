'use client'

import { useId, useMemo, useState } from 'react'
import { Building2 } from 'lucide-react'
import { libraryAuthorPreviewHref, type LibraryAuthor } from '@/lib/library-authors'
import { libraryAuthorAffiliationGroups, libraryInstitutionPreviewLimit, librarySignedAuthorsByInstitution, type LibraryInstitution } from '@/lib/library-institutions'
import type { PaperMetadata } from '@/lib/server/literature'
import { LibraryDocumentLink } from './LibraryDocumentDialog'
import { LibraryInstitutions } from './LibraryInstitutions'

export function LibraryAuthorInstitutionLinks({ author, papers, from }: {
  author: LibraryAuthor
  papers: PaperMetadata[]
  from: string | null
}) {
  const [expanded, setExpanded] = useState(false)
  const listId = useId()
  const groups = useMemo(() => {
    const affiliations = libraryAuthorAffiliationGroups(author.affiliations, papers)
    if (from) {
      const signedHere = (group: typeof affiliations[number]) => Number(group.records.some(record => record.slug === from))
      affiliations.sort((a, b) => signedHere(b) - signedHere(a))
    }
    return affiliations
  }, [author.affiliations, papers, from])
  if (!groups.length) return null
  const visible = expanded ? groups : groups.slice(0, libraryInstitutionPreviewLimit)
  const additional = groups.length - libraryInstitutionPreviewLimit

  return <div className="library-authorship-links library-author-institutions flex items-start gap-2">
    <Building2 size={15} strokeWidth={1.7} className="mt-1 shrink-0 text-slate-500" aria-hidden="true" />
    <ul id={listId} aria-label="署名机构" className="min-w-0">
      {visible.map(({ key, name, records }) => <li key={key} className={expanded ? 'break-words' : 'truncate'}>
        <LibraryInstitutions names={[name]} from={(records.find(record => record.slug === from) ?? records[0]).slug} />
      </li>)}
    </ul>
    {additional > 0 && <button type="button" aria-controls={listId} aria-expanded={expanded}
      aria-label={expanded ? '收起额外署名机构' : `展开另外 ${additional} 家署名机构`}
      className="library-author-link shrink-0 whitespace-nowrap text-xs leading-6"
      onClick={() => setExpanded(value => !value)}>{expanded ? '收起' : `另 ${additional} 家`}</button>}
  </div>
}

export function LibraryInstitutionAuthorLinks({ institution, papers, from }: {
  institution: LibraryInstitution
  papers: PaperMetadata[]
  from: string | null
}) {
  const authors = useMemo(() => librarySignedAuthorsByInstitution(papers, institution, from), [papers, institution, from])
  if (!authors.length) return null
  return <div className="library-authorship-links">
    <p className="text-xs font-medium text-slate-500">署名作者</p>
    <ul className="flex flex-wrap gap-x-4 gap-y-1">
      {authors.map(({ name, slug }) => <li key={name}>
        <LibraryDocumentLink href={libraryAuthorPreviewHref(name, slug)} prefetch={false} className="library-author-link">
          {name}
        </LibraryDocumentLink>
      </li>)}
    </ul>
  </div>
}
