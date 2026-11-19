'use client'

import React from 'react'
import { libraryJournalMetricsLabel, libraryJournalMetricsSource, type LibraryJournal } from '@/lib/library-journals'
import type { PaperMetadata } from '@/lib/server/literature'
import { LibraryCollectionDetails } from './LibraryCollectionDetails'

export function LibraryJournalDetails({ journal, papers }: { journal: LibraryJournal; papers: PaperMetadata[] }) {
  return <LibraryCollectionDetails title={journal.name} papers={papers}>
    {journal.shortName && journal.shortName !== journal.name && <p>{journal.shortName}</p>}
    <p>
      {libraryJournalMetricsLabel(journal.metrics)}
      {journal.metrics && <a href={journal.metrics.source || libraryJournalMetricsSource} target="_blank" rel="noopener noreferrer" className="ml-3 text-blue-600 hover:underline">指标来源</a>}
    </p>
  </LibraryCollectionDetails>
}
