import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import Markdown from 'react-markdown'
import { LIBRARY_RENDERER_VERSION, processLibraryContent, getLibraryMarkdownOptions, getLibraryReferenceMarkdownOptions } from './library-markdown.ts'

/** Render exactly the website's Markdown pipeline, without loading a browser. */
export async function compileLibraryMarkdown(raw, options = {}) {
  const processed = processLibraryContent(raw, options)
  const observation = { diagnostics: [...processed.diagnostics], images: [], citations: [], counts: { math: 0, tables: 0, headings: 0 } }
  let html = renderToStaticMarkup(React.createElement(Markdown, {
    ...getLibraryMarkdownOptions(processed, observation), children: processed.body,
  }))
  if (processed.referenceEntries.length) {
    html += renderToStaticMarkup(React.createElement('section', { id: 'references-section' },
      React.createElement('h2', null, processed.referenceTitle),
      ...processed.referenceEntries.map(entry => React.createElement('div', { id: entry.id ? `ref-${entry.id}` : undefined },
        entry.id ? React.createElement('a', { href: `#cite-${entry.id}` }, `[${entry.id}]`) : null,
        React.createElement(Markdown, { ...getLibraryReferenceMarkdownOptions(processed, entry, observation), children: entry.content }))),
    ))
  }
  const sourceLines = raw.split(/\r?\n/)
  for (const diagnostic of observation.diagnostics) {
    diagnostic.excerpt = sourceLines[diagnostic.line - 1] || ''
    diagnostic.context = sourceLines.slice(Math.max(0, diagnostic.line - 2), diagnostic.line + 2).join('\n').slice(0, 2000)
  }
  return {
    version: LIBRARY_RENDERER_VERSION,
    diagnostics: observation.diagnostics,
    images: observation.images,
    citations: observation.citations,
    referenceEntries: processed.referenceEntries,
    counts: { ...observation.counts, references: processed.referenceEntries.length, images: observation.images.length, citations: observation.citations.length },
    html,
  }
}
