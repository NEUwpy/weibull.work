export interface LibrarySearchHighlight {
  passageId: string
  terms: string[]
}

export function libraryHighlightTerms(values: readonly string[]): string[] {
  return Array.from(new Set(values.map(value => value.trim().slice(0, 200)).filter(Boolean))).slice(0, 64)
}

/** Highlight terms travel only with ordinary search links, leaving evidence URLs unchanged. */
export function librarySearchHitHref(href: string, terms: readonly string[]): string {
  const url = new URL(href, 'https://library.invalid')
  url.searchParams.delete('highlight')
  for (const term of libraryHighlightTerms(terms)) url.searchParams.append('highlight', term)
  return url.pathname + url.search + url.hash
}

export function readLibrarySearchHighlight(search: string, hash: string): LibrarySearchHighlight {
  const passageId = /^#passage-\d+$/.test(hash) ? hash.slice(1) : ''
  return { passageId, terms: passageId ? libraryHighlightTerms(new URLSearchParams(search).getAll('highlight')) : [] }
}

/** Mark matching visible text while retaining links, emphasis, citations, code and KaTeX nodes. */
export function rehypeLibrarySearchHighlights(options: LibrarySearchHighlight) {
  const excludedTags = new Set(['code', 'pre', 'math', 'annotation', 'svg', 'script', 'style', 'textarea', 'sup', 'img'])
  const boundaries = new Set(['p', 'li', 'th', 'td', 'tr', 'br'])
  const terms = libraryHighlightTerms(options.terms).sort((left, right) => right.length - left.length)
  const pattern = terms.length ? new RegExp(terms.map(term => term.split(/\s+/).map(word => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('\\s+')).join('|'), 'gi') : null

  return (tree: any) => {
    let target: any
    function cleanAndFind(parent: any) {
      if (!parent.children) return
      parent.children = parent.children.flatMap((node: any) => node.type === 'element' && node.properties?.dataLibrarySearchHighlight
        ? node.children : [node])
      for (const node of parent.children) {
        if (node.properties?.id === options.passageId) target = node
        cleanAndFind(node)
      }
    }
    cleanAndFind(tree)
    if (!target || !pattern || !/^passage-\d+$/.test(options.passageId)) return
    let source = ''
    const segments: { node: any; parent: any; start: number; end: number }[] = []
    function collect(node: any, parent?: any) {
      if (node.type === 'text') {
        const start = source.length
        source += node.value
        segments.push({ node, parent, start, end: source.length })
        return
      }
      const classNames = node.properties?.className
      const classes = Array.isArray(classNames) ? classNames : typeof classNames === 'string' ? classNames.split(/\s+/) : []
      if (excludedTags.has(node.tagName) || classes.some((name: string) => name.startsWith('katex'))) { source += '\0'; return }
      if (boundaries.has(node.tagName)) source += '\0'
      node.children?.forEach((child: any) => collect(child, node))
      if (boundaries.has(node.tagName)) source += '\0'
    }
    collect(target)
    const matches = Array.from(source.matchAll(pattern), match => ({ start: match.index!, end: match.index! + match[0].length }))
    for (const segment of segments) {
      const ranges = matches.filter(match => match.start < segment.end && match.end > segment.start)
      if (!ranges.length) continue
      const nodes: any[] = []
      let consumed = 0
      for (const range of ranges) {
        const start = Math.max(0, range.start - segment.start)
        const end = Math.min(segment.node.value.length, range.end - segment.start)
        if (start > consumed) nodes.push({ type: 'text', value: segment.node.value.slice(consumed, start) })
        nodes.push({ type: 'element', tagName: 'mark', properties: { className: ['library-search-match'], dataLibrarySearchHighlight: true },
          children: [{ type: 'text', value: segment.node.value.slice(start, end) }] })
        consumed = end
      }
      if (consumed < segment.node.value.length) nodes.push({ type: 'text', value: segment.node.value.slice(consumed) })
      const index = segment.parent.children.indexOf(segment.node)
      segment.parent.children.splice(index, 1, ...nodes)
    }
  }
}
