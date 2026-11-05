'use client'

import React, { createContext, useContext } from 'react'
import { libraryInstitutionIdentity, libraryInstitutionNames } from '@/lib/library-institutions'
import type { LibraryCredits } from '@/lib/library-credits'

export const LibraryInstitutionContext = createContext<((name: string, from?: string) => void) | null>(null)

export function LibraryInstitutions({ affiliation, credits, from }: { affiliation?: string; credits?: LibraryCredits; from?: string }) {
  const open = useContext(LibraryInstitutionContext)
  const names = credits ? (credits.institutions || []).map(unit => unit.name) : libraryInstitutionNames(affiliation)
  if (!names.length) return <>未登记</>
  return <span>{names.map((name, index) => {
    const identity = libraryInstitutionIdentity(name, credits ? [{ slug: from || '', author: '', credits }] : [])
    return <React.Fragment key={name}>
      {index > 0 && '；'}
      {open && !/^(?:unknown|未登记|未知单位)$/i.test(name)
        ? <button type="button" className="library-author-link" aria-haspopup="dialog" title={`查看单位 ${[identity.name, identity.englishName].filter(Boolean).join(' · ')}`} onClick={() => open(name, from)}>{identity.name}</button>
        : name}
    </React.Fragment>
  })}</span>
}
