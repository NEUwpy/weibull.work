import React from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { remarkLibraryAnswerCitations } from '@/lib/library-answer-markdown'
import { normalizeLibraryMath, rehypeLibraryTextHighlights } from '@/lib/library-math-markdown'
import 'katex/dist/katex.min.css'

interface LibraryMathMarkdownProps {
  children: string
  className?: string
  highlightTerms?: readonly string[]
  evidence?: readonly { citation: number; href: string }[]
}

/** Shared safe Markdown for answers and public search/evidence excerpts. */
export function LibraryMathMarkdown({ children, className = '', highlightTerms = [], evidence = [] }: LibraryMathMarkdownProps) {
  const links = new Set(evidence.map(item => item.href))
  return <div className={`library-math-markdown min-w-0 [&_.katex-display]:max-w-full [&_.katex-display]:overflow-x-auto [&_.katex-display]:overflow-y-hidden [&_pre]:overflow-x-auto [&_table]:block [&_table]:overflow-x-auto ${className}`}>
    <Markdown skipHtml remarkPlugins={[remarkGfm, remarkMath, [remarkLibraryAnswerCitations, { evidence }]]}
      rehypePlugins={[rehypeKatex, [rehypeLibraryTextHighlights, { terms: highlightTerms }]]}
      components={{
        a: ({ href, children }) => href && links.has(href)
          ? <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
          : <span>{children}</span>,
        img: ({ alt }) => <span>{alt}</span>,
      }}>{normalizeLibraryMath(children)}</Markdown>
  </div>
}
