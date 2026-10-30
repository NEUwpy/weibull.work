interface CitationSource {
  citation: number
  href: string
}

/** Resolve citation labels through supplied evidence, never through a model-written URL. */
export function remarkLibraryAnswerCitations({ evidence }: { evidence: readonly CitationSource[] }) {
  const links = new Map(evidence.filter(item => Number.isSafeInteger(item.citation) && item.citation > 0 && item.href.startsWith('/library/'))
    .map(item => [item.citation, item.href]))
  const literalNodes = new Set(['code', 'inlineCode', 'math', 'inlineMath', 'html'])
  const text = (value: string) => ({ type: 'text', value })
  const citation = (number: number) => ({ type: 'link', url: links.get(number), children: [text(`[${number}]`)] })

  function splitCitations(value: string): any[] {
    const result: any[] = []
    const pattern = /\[(\d+)\](?:\([^\r\n)]*\))?/g
    let consumed = 0
    for (const match of Array.from(value.matchAll(pattern))) {
      const number = Number(match[1])
      if (!links.has(number)) continue
      if (match.index! > consumed) result.push(text(value.slice(consumed, match.index)))
      result.push(citation(number))
      consumed = match.index! + match[0].length
    }
    if (!consumed) return [text(value)]
    if (consumed < value.length) result.push(text(value.slice(consumed)))
    return result
  }

  function rewrite(parent: any) {
    if (!Array.isArray(parent.children)) return
    for (let index = 0; index < parent.children.length; index++) {
      const node = parent.children[index]
      if (node.type === 'link' || node.type === 'linkReference') {
        const label = node.children?.every((child: any) => child.type === 'text')
          ? node.children.map((child: any) => child.value).join('') : ''
        const match = /^(?:\[(\d+)\]|(\d+))$/.exec(label)
        if (match) {
          const number = Number(match[1] || match[2])
          parent.children[index] = links.has(number) ? citation(number) : text(`[${match[1] || match[2]}]`)
        }
        // Never introduce a nested link inside another link's label.
        continue
      }
      if (node.type === 'text') {
        const replacement = splitCitations(node.value)
        parent.children.splice(index, 1, ...replacement)
        index += replacement.length - 1
      } else if (!literalNodes.has(node.type)) rewrite(node)
    }
  }

  return (tree: any) => { rewrite(tree) }
}
