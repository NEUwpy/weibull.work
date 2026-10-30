interface MarkdownSpan {
  start: number
  end: number
  kind: 'literal' | 'math'
  body?: string
  display?: boolean
}

function escaped(value: string, index: number): boolean {
  let slashes = 0
  while (index > 0 && value[--index] === '\\') slashes++
  return slashes % 2 === 1
}

function closing(value: string, token: string, from: number): number {
  let index = value.indexOf(token, from)
  while (index >= 0) {
    if (!escaped(value, index) && (token !== '$' || value[index - 1] !== '$' && value[index + 1] !== '$')) return index
    index = value.indexOf(token, index + token.length)
  }
  return -1
}

/** Recognize atomic Markdown without parsing the corpus again for every query. */
function markdownSpans(value: string): MarkdownSpan[] {
  const spans: MarkdownSpan[] = []
  for (let index = 0; index < value.length;) {
    const start = index
    const rest = value.slice(index)
    const lineStart = value.lastIndexOf('\n', index - 1) + 1
    const fence = /^[`~]{3,}/.exec(rest)
    if (fence && /^ {0,3}$/.test(value.slice(lineStart, index)) && /^(?:`+|~+)$/.test(fence[0])) {
      const marker = fence[0][0]
      const lines = new RegExp(`^ {0,3}${marker === '`' ? '`' : '~'}{${fence[0].length},}[ \\t]*$`, 'gm')
      lines.lastIndex = value.indexOf('\n', index) + 1
      const end = lines.lastIndex > index ? lines.exec(value) : null
      index = end ? end.index + end[0].length : value.length
      spans.push({ start, end: index, kind: 'literal' })
      continue
    }
    if (value[index] === '`' && !escaped(value, index)) {
      const token = /^`+/.exec(rest)![0]
      const end = value.indexOf(token, index + token.length)
      if (end >= 0) {
        index = end + token.length
        spans.push({ start, end: index, kind: 'literal' })
        continue
      }
    }
    // Preserve complete links/images, including parentheses inside their destinations.
    if ((value[index] === '[' || rest.startsWith('![')) && !escaped(value, index)) {
      const labelStart = index + (value[index] === '!' ? 1 : 0)
      let bracket = labelStart + 1
      let depth = 1
      while (bracket < value.length && depth) {
        if (!escaped(value, bracket)) {
          if (value[bracket] === '[') depth++
          if (value[bracket] === ']') depth--
        }
        bracket++
      }
      const open = value[bracket]
      if (!depth && (open === '(' || open === '[')) {
        const close = open === '(' ? ')' : ']'
        let end = bracket + 1
        depth = 1
        while (end < value.length && depth) {
          if (!escaped(value, end)) {
            if (value[end] === open) depth++
            if (value[end] === close) depth--
          }
          end++
        }
        if (!depth) {
          index = end
          spans.push({ start, end: index, kind: 'literal' })
          continue
        }
      }
    }
    const tag = /^<[^>\n]+>/.exec(rest)
    if (tag) {
      index += tag[0].length
      spans.push({ start, end: index, kind: 'literal' })
      continue
    }
    const open = !escaped(value, index)
      ? rest.startsWith('\\[') ? '\\[' : rest.startsWith('\\(') ? '\\(' : rest.startsWith('$$') ? '$$' : rest.startsWith('$') ? '$' : ''
      : ''
    if (open) {
      const close = open === '\\[' ? '\\]' : open === '\\(' ? '\\)' : open
      const end = closing(value, close, index + open.length)
      if (end >= 0) {
        const body = value.slice(index + open.length, end)
        index = end + close.length
        spans.push({ start, end: index, kind: 'math', body,
          display: open === '$$' || open === '\\[' || /\\tag\s*\{/.test(body) })
        continue
      }
    }
    index++
  }
  return spans
}

/** Accept common model delimiters; code and links stay byte-for-byte unchanged. */
export function normalizeLibraryMath(value: string): string {
  let consumed = 0
  const output: string[] = []
  for (const span of markdownSpans(value)) {
    if (span.kind !== 'math') continue
    output.push(value.slice(consumed, span.start))
    const body = span.body!
    if (span.display) output.push(`\n\n$$${body.startsWith('\n') ? '' : '\n'}${body}${body.endsWith('\n') ? '' : '\n'}$$\n\n`)
    else output.push(`$${body}$`)
    consumed = span.end
  }
  output.push(value.slice(consumed))
  return output.join('')
}

/** A soft 360-character window may expand to retain a whole formula or Markdown link. */
export function libraryMathExcerpt(value: string, terms: readonly string[], size = 360): string {
  const normalized = value.toLowerCase()
  const positions = terms.map(term => normalized.indexOf(term.toLowerCase())).filter(index => index >= 0)
  let start = Math.max(0, (positions.length ? Math.min(...positions) : 0) - 70)
  let end = Math.min(value.length, start + size)
  for (const span of markdownSpans(value)) {
    if (span.start < start && start < span.end) start = span.start
    if (span.start < end && end < span.end) {
      // Huge code blocks/links remain bounded rather than becoming a full-text preview.
      end = span.end - start <= 1200 ? span.end : span.start
    }
  }
  return `${start ? '…' : ''}${value.slice(start, end)}${end < value.length ? '…' : ''}`
}

/** Highlight ordinary text after KaTeX, leaving formulas, code and links untouched. */
export function rehypeLibraryTextHighlights({ terms = [] }: { terms?: readonly string[] } = {}) {
  const words = Array.from(new Set(terms.filter(term => term.length > 1).slice(0, 30))).sort((a, b) => b.length - a.length)
  if (!words.length) return () => {}
  const pattern = new RegExp(`(${words.map(word => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi')
  const known = new Set(words.map(word => word.toLowerCase()))
  function walk(parent: any) {
    if (parent.type === 'element' && (['code', 'pre', 'a', 'math'].includes(parent.tagName) ||
      parent.properties?.className?.some((name: string) => name === 'katex' || name.startsWith('math-')))) return
    if (!Array.isArray(parent.children)) return
    for (let index = 0; index < parent.children.length; index++) {
      const node = parent.children[index]
      if (node.type !== 'text') { walk(node); continue }
      const replacement = String(node.value).split(pattern).filter(Boolean).map(value => known.has(value.toLowerCase())
        ? { type: 'element', tagName: 'mark', properties: { className: ['rounded', 'bg-amber-100', 'px-0.5', 'text-inherit'] }, children: [{ type: 'text', value }] }
        : { type: 'text', value })
      parent.children.splice(index, 1, ...replacement)
      index += replacement.length - 1
    }
  }
  return (tree: any) => { walk(tree) }
}
