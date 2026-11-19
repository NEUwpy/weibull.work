'use client'

import React, { useMemo } from 'react'
import { libraryAuthorPreviewHref } from '@/lib/library-authors'
import { libraryInstitutionPreviewHref } from '@/lib/library-institutions'
import { libraryVisiblePeople, type LibraryCollectionSort, type LibraryPeopleCollection, type LibraryPeopleGroup } from '@/lib/library-collections'
import { LibraryCollectionFolder } from './LibraryCollectionFolder'
import { useLibraryScrollBatches } from './useLibraryScrollBatches'

const collectionKinds = {
  authors: { label: '作者', href: libraryAuthorPreviewHref },
  institutions: { label: '机构', href: libraryInstitutionPreviewHref },
}
const PAGE_SIZE = 36

export default function LibraryPeopleCollections({ kind, groups, filter, sort }: {
  kind: LibraryPeopleCollection
  groups: LibraryPeopleGroup[]
  filter: string
  sort: LibraryCollectionSort
}) {
  const { label, href } = collectionKinds[kind]
  const sortedGroups = useMemo(() => libraryVisiblePeople(groups, filter, sort), [groups, filter, sort])
  const { visibleCount, hasMore, sentinel } = useLibraryScrollBatches(sortedGroups.length, PAGE_SIZE)

  return <section aria-label={label} className="library-people-collections">
    <header className="library-directory-heading">
      <h1>{label}名录</h1>
      <p>共 {sortedGroups.length.toLocaleString('zh-CN')} {kind === 'authors' ? '位' : '家'}</p>
    </header>
    {sortedGroups.length ? <div className="library-people-folder-grid" data-kind={kind}>
      {sortedGroups.slice(0, visibleCount).map(({ key, name, englishName, count, affiliations }) => <LibraryCollectionFolder key={key}
        kind={kind === 'authors' ? 'author' : 'institution'} folderKey={key} name={name} description={englishName !== name ? englishName : undefined}
        affiliations={affiliations}
        count={count} href={href(name)} />)}
    </div> : <p className="py-24 text-center text-sm text-slate-500">暂无符合条件的{label}</p>}
    {hasMore && <div ref={sentinel} className="h-px" aria-hidden="true" />}
  </section>
}
