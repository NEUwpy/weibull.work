'use client'

import React, { useState } from 'react'
import { libraryPresentedTitle, type LibraryTitlePresentation } from '@/lib/library-titles'
import { LibraryMathMarkdown } from '@/components/shared/LibraryMathMarkdown'

export function LibraryPaperTitle({ paper, highlightTerms }: {
  paper: { title: string; title_en?: string } & LibraryTitlePresentation
  highlightTerms?: string[]
}) {
  const [hovered, setHovered] = useState(false)
  const title = libraryPresentedTitle(paper, hovered)
  return <span className="library-paper-title" onPointerEnter={event => { if (event.pointerType === 'mouse') setHovered(true) }}
    onPointerLeave={() => setHovered(false)}>
    <span key={title} className="library-title-text"><LibraryMathMarkdown inline highlightTerms={highlightTerms}>{title}</LibraryMathMarkdown></span>
  </span>
}
