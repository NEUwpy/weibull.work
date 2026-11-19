'use client'

import React, { createContext, useContext } from 'react'
import { libraryInstitutionIdentity, libraryInstitutionNames, libraryInstitutionPreviewLimit } from '@/lib/library-institutions'
import type { LibraryCredits } from '@/lib/library-credits'

export const LibraryInstitutionContext = createContext<((name: string, from?: string) => void) | null>(null)

export function LibraryInstitutions({ affiliation, credits, from, names, preview = false }: {
  affiliation?: string; credits?: LibraryCredits; from?: string; names?: string[]; preview?: boolean
}) {
  const open = useContext(LibraryInstitutionContext)
  const institutions = names ?? (credits ? (credits.institutions || []).map(unit => unit.name) : libraryInstitutionNames(affiliation))
  const catalog = credits ? [{ slug: from || '', author: '', credits }] : undefined
  const identities = institutions.map(name => libraryInstitutionIdentity(name, catalog))
  const distinct = Array.from(new Map(identities.map(identity => [identity.key, identity])).values())
  if (!distinct.length) return <>未登记</>
  const visible = preview ? distinct.slice(0, libraryInstitutionPreviewLimit) : distinct
  const additional = distinct.length - visible.length
  return <span className={preview ? 'flex min-w-0 items-start gap-2' : undefined}>
    <span className={preview ? 'grid min-w-0' : undefined}>
      {visible.map((identity, index) => <span key={identity.key} className={preview ? 'truncate' : undefined}>
        {index > 0 && !preview && '；'}
        {open && !/^(?:unknown|未登记|未知单位)$/i.test(identity.key)
          ? <button type="button" className="library-author-link" aria-haspopup="dialog" title={`查看单位 ${[identity.name, identity.englishName].filter(Boolean).join(' · ')}`} onClick={() => open(identity.name, from)}>{identity.name}</button>
          : identity.name}
      </span>)}
    </span>
    {additional > 0 && <span className="shrink-0 whitespace-nowrap text-xs leading-5" title={distinct.map(unit => unit.name).join('；')}>另 {additional} 家</span>}
  </span>
}
