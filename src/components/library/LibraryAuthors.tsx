'use client'

import React, { createContext, useContext } from 'react'
import { libraryAuthorIdentity, libraryAuthorName, libraryPaperAuthorNames } from '@/lib/library-authors'
import type { LibraryCredits } from '@/lib/library-credits'

export const LibraryAuthorContext = createContext<((name: string, from?: string) => void) | null>(null)

export function LibraryAuthors({ author, credits, from, preview = false }: { author: string; credits?: LibraryCredits; from?: string; preview?: boolean }) {
  const open = useContext(LibraryAuthorContext)
  const names = libraryPaperAuthorNames({ author, credits })
  const shortened = (preview && names.length > 3) || (!credits && /(?:et\s+al\.?|等人?)[.\s]*$/i.test(author))
  const visible = preview ? names.slice(0, 3) : names
  const separator = /[\u3400-\u9fff]/.test(author) ? '、' : ', '
  return <span className="library-authors">
    {visible.map((name, index) => {
      const identity = libraryAuthorIdentity(name, credits ? [{ slug: from || '', author, credits }] : [])
      const label = libraryAuthorName(name)
      const title = [identity.name, identity.englishName].filter(Boolean).join(' · ')
      return <React.Fragment key={`${index}-${name}`}>
        {index > 0 && separator}
        {open && label && !/^(?:unknown|未登记|佚名)$/i.test(label)
          ? <button type="button" className="library-author-link" aria-haspopup="dialog" title={`查看作者 ${title}`} onClick={() => open(name, from)}>{preview ? label : name}</button>
          : label || name}
      </React.Fragment>
    })}
    {shortened && (separator === '、' ? ' 等' : ', et al.')}
  </span>
}
