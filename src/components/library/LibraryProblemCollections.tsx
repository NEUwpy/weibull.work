'use client'

import React from 'react'
import { ArrowUpRight } from 'lucide-react'
import type { PaperMetadata } from '@/lib/server/literature'
import type { LibraryCollectionSort } from '@/lib/library-collections'
import { libraryProblemSource, type libraryProblemGroups } from '@/lib/library-problems'
import { LibraryCollectionFolder } from './LibraryCollectionFolder'
import { LibraryCollectionDetails } from './LibraryCollectionDetails'
import { LibraryPreviewDialog } from './LibraryPreviewDialog'

export default function LibraryProblemCollections({ relatedPapers, groups, selectedKey, direction, sort, onOpen, onClose, hrefFor }: {
  relatedPapers: PaperMetadata[]; groups: ReturnType<typeof libraryProblemGroups>; selectedKey: string; direction: string; sort: LibraryCollectionSort
  onOpen: (key: string) => void; onClose: () => void; hrefFor: (key: string) => string
}) {
  const visibleGroups = groups.filter(group => direction === 'all' || direction === group.key)
  if (sort === 'count-desc') visibleGroups.sort((a, b) => b.count - a.count)
  const selectedDirection = groups.find(group => group.key === selectedKey || group.problems.some(problem => problem.key === selectedKey))
  const selectedProblem = selectedDirection?.problems.find(problem => problem.key === selectedKey)

  return <section aria-label="科学问题" className="library-problem-collections">
    <header className="library-problem-intro">
      <p className="library-problem-source">{libraryProblemSource.organizer}<span>{libraryProblemSource.period}</span></p>
      <h1>
        <a href={libraryProblemSource.url} target="_blank" rel="noopener noreferrer">
          <span>可靠性领域关键科学问题</span><wbr /><span>与工程挑战难题<ArrowUpRight size={18} aria-hidden="true" /></span>
        </a>
      </h1>
    </header>
    {visibleGroups.map(group => <section key={group.key} id={`problem-${group.key}`} aria-labelledby={`problem-heading-${group.key}`}
      className="library-problem-group">
      <div className="library-problem-heading">
        <h2 id={`problem-heading-${group.key}`}>{group.name}</h2>
        <p>{group.description}</p>
      </div>
      <div className="library-problem-folder-grid">
        {(sort === 'count-desc' ? [...group.problems].sort((a, b) => b.count - a.count) : group.problems).map(problem => <LibraryCollectionFolder key={problem.key} kind="problem" folderKey={problem.key} name={problem.name} description={problem.proposer}
          count={problem.count} selected={selectedProblem?.key === problem.key} href={hrefFor(problem.key)}
          onOpen={() => onOpen(problem.key)} title={problem.challenge} opensDialog />)}
      </div>
    </section>)}
    {selectedDirection && <LibraryProblemFolderDialog key={selectedKey}
      title={selectedProblem?.name ?? selectedDirection.name} description={selectedProblem?.challenge ?? selectedDirection.description}
      proposer={selectedProblem?.proposer} papers={relatedPapers} onClose={onClose} />}
  </section>
}

function LibraryProblemFolderDialog({ title, description, proposer, papers, onClose }: {
  title: string; description: string; proposer?: string; papers: PaperMetadata[]; onClose: () => void
}) {
  return <LibraryPreviewDialog title="科学问题资料" onClose={onClose} padded>
    <LibraryCollectionDetails title={title} papers={papers}>
      <p>{description}</p>
      {proposer && <p>提出人 · {proposer}</p>}
    </LibraryCollectionDetails>
  </LibraryPreviewDialog>
}
