'use client'

import React, { useId, useState } from 'react'
import { Book, FileText, Link2 } from 'lucide-react'
import { libraryTypeLabel } from '@/lib/library-types'

function MetadataHint({ label, value, children }: { label: string; value: string; children: React.ReactNode }) {
  const id = useId()
  const [dismissed, setDismissed] = useState(false)
  return <span className="library-card-info" data-dismissed={dismissed || undefined} onPointerEnter={() => setDismissed(false)}>
    <button type="button" aria-label={label} aria-describedby={id}
      className={`library-card-info-trigger${value ? '' : ' library-card-info-missing'}`}
      onFocus={() => setDismissed(false)} onClick={() => setDismissed(false)}
      onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); setDismissed(true) } }}>
      {children}
    </button>
    <span role="tooltip" id={id} className="library-card-tooltip">
      <span className="library-card-tooltip-body">
        <span className="mb-1 block text-xs text-slate-400">{label}</span>
        <span className={label === 'DOI' ? 'font-mono text-xs' : 'text-sm'}>{value || `未登记${label}`}</span>
      </span>
    </span>
  </span>
}

export function LibraryCardMetadata({ id, type, publication, year, doi, available }: {
  id: string; type?: string; publication?: string; year: number; doi?: string; available: boolean
}) {
  return <div className="library-card-metadata flex items-center justify-between gap-3">
    <span className={`shrink-0 whitespace-nowrap text-sm font-normal italic font-serif ${available ? 'text-rose-400' : 'text-slate-400'}`}>{id}</span>
    <div className="flex shrink-0 items-center gap-2">
      <MetadataHint label="出版信息" value={publication ? `${libraryTypeLabel(type)} · ${publication}` : ''}>
        {type === '书籍' ? <Book size={14} aria-hidden="true" /> : <FileText size={14} aria-hidden="true" />}
      </MetadataHint>
      <MetadataHint label="DOI" value={doi || ''}><Link2 size={14} aria-hidden="true" /></MetadataHint>
      <span className="whitespace-nowrap text-xs tabular-nums text-slate-400" aria-label={`发表年份：${year > 0 ? year : '未登记'}`}>{year > 0 ? year : '—'}</span>
    </div>
  </div>
}
