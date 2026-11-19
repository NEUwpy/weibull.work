'use client'

import React from 'react'
import { libraryJournalMetricsLabel, libraryJournalPreviewHref, type LibraryJournal } from '@/lib/library-journals'
import { LibraryDocumentLink } from './LibraryDocumentDialog'
import './journal-covers.css'

type ListedJournal = LibraryJournal & { count: number }

const coverTones = ['pine', 'ink', 'plum', 'ochre']

export function LibraryJournalGallery({ journals }: { journals: ListedJournal[] }) {
  return <section aria-label="期刊集" className="library-journal-gallery">
    {journals.length ? <ul className="library-journal-cover-grid">
      {journals.map(journal => <li key={journal.key}><LibraryJournalCover journal={journal} /></li>)}
    </ul> : <p className="py-24 text-center text-sm text-slate-500">该主题下暂无期刊论文</p>}
  </section>
}

function LibraryJournalCover({ journal }: { journal: ListedJournal }) {
  const { key, name, shortName, metrics, count } = journal
  const toneIndex = Array.from(key).reduce((tone, character) => (tone * 31 + character.charCodeAt(0)) % coverTones.length, 0)
  const hasShortName = shortName && shortName.toLowerCase() !== name.toLowerCase()
  const titleSize = name.length > 64 || /[a-z]{17}/i.test(name) ? 'long'
    : name.length > 38 || /[a-z]{12}/i.test(name) ? 'medium' : undefined
  const metricsLabel = libraryJournalMetricsLabel(metrics)
  return <LibraryDocumentLink href={libraryJournalPreviewHref(key)} prefetch={false} className="library-journal-cover" data-tone={coverTones[toneIndex]}
    aria-label={`${name}，${count} 篇论文，${metricsLabel}`} title={metricsLabel}>
    <span className="journal-cover-face">
      <span className="journal-cover-masthead">
        {hasShortName && <span className="journal-cover-abbreviation">{shortName}</span>}
        <span className="journal-cover-name" data-title-size={titleSize} dir="auto">{name}</span>
      </span>
      <span className="journal-cover-stats" aria-hidden="true">
        <span className="journal-cover-stat"><span>JCR</span><strong>{metrics?.quartile || '—'}</strong></span>
        <span className="journal-cover-stat"><span>影响因子</span><strong>{metrics?.impactFactor.toFixed(1) ?? '—'}</strong></span>
        <span className="journal-cover-stat"><span>在库论文</span><strong>{count} 篇</strong></span>
      </span>
    </span>
  </LibraryDocumentLink>
}
