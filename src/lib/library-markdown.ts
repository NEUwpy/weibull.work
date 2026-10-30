import matter from 'gray-matter'
import { unified, type PluggableList } from 'unified'
import remarkParse from 'remark-parse'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeRaw from 'rehype-raw'
import rehypeSlug from 'rehype-slug'
import rehypeKatex from 'rehype-katex'
import { visit } from 'unist-util-visit'
import GithubSlugger from 'github-slugger'

export const LIBRARY_RENDERER_VERSION = '1.1.0'

export interface LibraryDiagnostic {
  code: string
  line: number
  message: string
  severity: 'error' | 'warning'
}

export interface LibraryReference {
  id: string | null
  content: string
  raw: string
  line: number
}

export interface ProcessedLibraryContent {
  frontmatter: Record<string, any>
  body: string
  referenceTitle: string
  referenceList: string[]
  referenceEntries: LibraryReference[]
  headings: { level: number; text: string; slug: string }[]
  diagnostics: LibraryDiagnostic[]
  bodyLineOffset: number
}

export interface LibraryRenderObservation {
  diagnostics: LibraryDiagnostic[]
  images: { url: string; line: number }[]
  citations: { id: string; line: number }[]
  counts: { math: number; tables: number; headings: number }
}

export const libraryPassageId = (line: number): string => `passage-${line}`

export interface LibraryPassage {
  section: string
  sectionStartLine: number
  kind: 'paragraph' | 'table' | 'code' | 'math'
  startLine: number
  endLine: number
  text: string
  plainText: string
}

/** Source positions come from the same Markdown body used by the reader. */
export function extractLibraryPassages(raw: string, includeMath = false): LibraryPassage[] {
  const processed = processLibraryContent(raw)
  const tree: any = unified().use(remarkParse).use(remarkGfm).use(remarkMath).parse(processed.body)
  const passages: LibraryPassage[] = []
  const sections: string[] = []
  let sectionStartLine = 0
  visit(tree, (node: any) => {
    if (node.type === 'heading') {
      sections.length = node.depth
      sections[node.depth - 1] = nodeText(node).trim()
      sectionStartLine = node.position.start.line + processed.bodyLineOffset
    }
    if (!['paragraph', 'table', 'code', ...(includeMath ? ['math'] : [])].includes(node.type) || !node.position) return
    const text = processed.body.slice(node.position.start.offset, node.position.end.offset).trim()
    const plainText = nodeText(node).replace(/\s+/g, ' ').trim()
    if (!plainText) return
    passages.push({ section: sections.filter(Boolean).join(' / ') || '正文', sectionStartLine, kind: node.type,
      startLine: node.position.start.line + processed.bodyLineOffset,
      endLine: node.position.end.line + processed.bodyLineOffset, text, plainText })
  })
  return passages
}

// The source line numbers remain intact: removing a reference section replaces it
// with blank lines, so diagnostics still point to the original Markdown.
export function processLibraryContent(rawMarkdown: string): ProcessedLibraryContent {
  const { data, content } = matter(rawMarkdown)
  const prefix = rawMarkdown.slice(0, rawMarkdown.length - content.length)
  const bodyLineOffset = (prefix.match(/\n/g) || []).length
  const tree: any = unified().use(remarkParse).use(remarkGfm).use(remarkMath).parse(content)
  const diagnostics: LibraryDiagnostic[] = []
  const referenceEntries: LibraryReference[] = []
  const children: any[] = tree.children
  let body = content
  let referenceTitle = '参考文献'
  const referenceIndex = children.findIndex(node => node.type === 'heading' && /^(参考文献|references|bibliography)\s*[:：]?$/i.test(nodeText(node).trim()))

  if (referenceIndex !== -1) {
    const heading = children[referenceIndex]
    referenceTitle = nodeText(heading).trim().replace(/[:：]$/, '')
    const nextHeading = children.slice(referenceIndex + 1).find(node => node.type === 'heading' && node.depth <= heading.depth)
    const start = heading.position.start.offset
    const refsStart = heading.position.end.offset
    const end = nextHeading?.position.start.offset ?? content.length
    const lines = content.slice(refsStart, end).split(/\r?\n/)
    let current: LibraryReference | null = null
    const flush = () => { if (current) referenceEntries.push(current); current = null }
    lines.forEach((line, index) => {
      const text = line.trim()
      if (!text) { if (current?.id === null) flush(); return }
      const marker = text.match(/^(?:\[\s*(\d+)\s*\]|［\s*(\d+)\s*］|\(\s*(\d+)\s*\)|（\s*(\d+)\s*）|(\d+)[.)、．])\s*/)
      const sourceLine = heading.position.end.line + index + bodyLineOffset
      if (marker) {
        flush()
        current = { id: String(Number(marker.slice(1).find(Boolean))), content: text.slice(marker[0].length), raw: text, line: sourceLine }
      } else if (current) {
        current.content += '\n' + text
        current.raw += '\n' + text
      } else {
        current = { id: null, content: text, raw: text, line: sourceLine }
      }
    })
    flush()
    const seen = new Set<string>()
    for (const entry of referenceEntries) {
      if (entry.id && seen.has(entry.id)) diagnostics.push({ code: 'reference.duplicate', line: entry.line, severity: 'error', message: `参考文献编号 ${entry.id} 重复。` })
      if (entry.id) seen.add(entry.id)
    }
    body = content.slice(0, start) + content.slice(start, end).replace(/[^\r\n]/g, '') + content.slice(end)
  }

  const slugger = new GithubSlugger()
  const bodyTree: any = unified().use(remarkParse).use(remarkGfm).use(remarkMath).parse(body)
  const headings: ProcessedLibraryContent['headings'] = []
  visit(bodyTree, 'heading', (node: any) => {
    const text = headingText(node).trim()
    const slug = slugger.slug(nodeText(node).trim())
    if (node.depth <= 3) headings.push({ level: node.depth, text, slug })
  })
  return { frontmatter: data, body, referenceTitle, referenceList: referenceEntries.map(entry => entry.raw), referenceEntries, headings, diagnostics, bodyLineOffset }
}

function nodeText(node: any): string {
  return typeof node.value === 'string' ? node.value : (node.children || []).map(nodeText).join('')
}

function headingText(node: any): string {
  if (node.type === 'inlineMath') return `$${node.value}$`
  return typeof node.value === 'string' ? node.value : (node.children || []).map(headingText).join('')
}

function classes(node: any): string[] {
  const value = node.properties?.className
  return Array.isArray(value) ? value : typeof value === 'string' ? value.split(/\s+/) : []
}

function element(tagName: string, properties: Record<string, any>, children: any[]): any {
  return { type: 'element', tagName, properties, children }
}

// Preserve the established $$...$$ display convention without rewriting the
// source string or changing single-dollar math into a different expression.
function remarkLibraryDisplayMath() {
  return (tree: any, file: any) => {
    const source = String(file.value)
    visit(tree, 'inlineMath', (node: any) => {
      const literal = source.slice(node.position.start.offset, node.position.end.offset)
      if (/^\$\$[^$]/.test(literal) && literal.endsWith('$$')) {
        node.data = { ...node.data, hProperties: { ...node.data?.hProperties, className: ['language-math', 'math-display'] } }
      }
    })
  }
}

function remarkLibraryFormatDiagnostics(options: { processed: ProcessedLibraryContent; observation?: LibraryRenderObservation }) {
  return (tree: any, file: any) => {
    if (!options.observation) return
    const source = String(file.value)
    const report = (node: any, code: string, message: string, severity: 'error' | 'warning' = 'error') => {
      options.observation!.diagnostics.push({ code, message, severity, line: (node.position?.start.line || 1) + options.processed.bodyLineOffset })
    }
    visit(tree, (node: any) => {
      if (!node.position) return
      const literal = source.slice(node.position.start.offset, node.position.end.offset)
      if (node.type === 'math') {
        const lines = literal.trimEnd().split(/\r?\n/)
        const opening = lines[0].trim().match(/^(\${2,})/)
        const closing = lines.length > 1 ? lines.at(-1)?.match(/^\s*(\${2,})\s*$/) : null
        if (opening && (!closing || closing[1].length < opening[1].length)) {
          report(node, 'math.unclosed-display', '块公式缺少结束的美元符号定界行。')
        }
      }
      if (node.type === 'text' && /(^|[^\\])\$/.test(literal.replace(/\\\\/g, ''))) {
        report(node, 'math.unmatched-delimiter', '正文存在未被数学解析器识别的美元符号；核对公式定界符，金额美元符号应写为 \\$.')
      }
    })
  }
}

function rehypeLibraryCitations(options: { processed: ProcessedLibraryContent; observation?: LibraryRenderObservation }) {
  return (tree: any) => {
    const { processed, observation } = options
    const known = new Set(processed.referenceEntries.flatMap(entry => entry.id ? [entry.id] : []))
    const first = new Set<string>()
    const excludedTags = new Set(['a', 'code', 'pre', 'script', 'style', 'math', 'annotation', 'svg', 'textarea'])
    const scan = (parent: any, excluded = false) => {
      if (!parent.children) return
      const blocked = excluded || excludedTags.has(parent.tagName) || classes(parent).some(name => name === 'katex' || name === 'katex-display' || name === 'katex-error')
      for (let index = 0; index < parent.children.length; index++) {
        const node = parent.children[index]
        if (node.type !== 'text' || blocked) { if (!blocked) scan(node); continue }
        const parentheses = processed.frontmatter.citation_style === 'numeric-parentheses'
        const regex = parentheses
          ? /(?:\[([1-9]\d*(?:\s*[,，\-–]\s*[1-9]\d*)*)\]|\(([1-9]\d*(?:\s*[,，\-–]\s*[1-9]\d*)*)\)|（([1-9]\d*(?:\s*[,，\-–]\s*[1-9]\d*)*)）)/g
          : /\[([1-9]\d*(?:\s*[,，\-–]\s*[1-9]\d*)*)\]/g
        const parts: any[] = []
        let last = 0
        for (const match of node.value.matchAll(regex)) {
          const round = match[0][0] !== '['
          if (round && /(?:\b(?:eqs?|figs?|figures?|tables?|sections?)\.?|公式|式|图|表)\s*$/i.test(node.value.slice(0, match.index))) continue
          const ids: string[] = []
          let valid = true
          for (const part of (match[1] ?? match[2] ?? match[3]).split(/[,，]/)) {
            const bounds = part.trim().split(/[-–]/).map(Number)
            if (bounds.length > 2 || bounds[0] > (bounds[1] ?? bounds[0]) || (bounds[1] ?? bounds[0]) - bounds[0] > 500) { valid = false; break }
            for (let id = bounds[0]; id <= (bounds[1] ?? bounds[0]); id++) ids.push(String(id))
          }
          if (!valid) continue
          const line = (node.position?.start.line || 1) + processed.bodyLineOffset + (node.value.slice(0, match.index).match(/\n/g) || []).length
          const missing = ids.filter(id => !known.has(id))
          if (missing.length) {
            if (!round) observation?.diagnostics.push({ code: 'citation.missing-reference', line, severity: 'warning', message: `方括号编号 ${missing.join(', ')} 无对应参考文献；保留原文，未建立跳转。` })
            continue
          }
          parts.push({ type: 'text', value: node.value.slice(last, match.index) })
          const links = ids.flatMap((id, i) => {
            const properties: Record<string, any> = { href: `#ref-${id}`, className: ['no-underline', 'text-blue-600', 'hover:underline'] }
            if (!first.has(id)) { properties.id = `cite-${id}`; first.add(id) }
            observation?.citations.push({ id, line })
            return [...(i ? [{ type: 'text', value: ', ' }] : []), element('a', properties, [{ type: 'text', value: `${match[0][0]}${id}${match[0].at(-1)}` }])]
          })
          parts.push(element('sup', {}, links))
          last = match.index! + match[0].length
        }
        if (parts.length) {
          parts.push({ type: 'text', value: node.value.slice(last) })
          parent.children.splice(index, 1, ...parts)
          index += parts.length - 1
        }
      }
    }
    scan(tree)
  }
}

export function rehypeStyleCaptions() {
  return (tree: any) => {
    visit(tree, 'element', (node: any, index: number | undefined, parent: any) => {
      if (node.tagName !== 'p' || !parent || index === undefined) return
      const siblings = parent.children.filter((child: any) => child.type === 'element')
      const position = siblings.indexOf(node)
      const before = siblings[position - 1]
      const after = siblings[position + 1]
      const caption = /^(?:图\s*\d|fig(?:ure)?\.?\s*\d)/i.test(nodeText(node).trim())
      const containsImage = (candidate: any) => candidate && (candidate.tagName === 'img' || candidate.children?.some((child: any) => child.tagName === 'img'))
      let className = ''
      if (after?.tagName === 'table') className = 'table-caption'
      if (caption && (containsImage(before) || containsImage(node))) className = 'figure-caption'
      if (className) node.properties.className = Array.from(new Set([...classes(node), className]))
    })
  }
}

function rehypeLibraryObserve(options: { processed: ProcessedLibraryContent; observation?: LibraryRenderObservation }) {
  return (tree: any, file: any) => {
    const observation = options.observation
    if (!observation) return
    visit(tree, 'element', (node: any) => {
      const names = classes(node)
      if (names.includes('katex')) observation.counts.math++
      if (node.tagName === 'table') observation.counts.tables++
      if (/^h[1-6]$/.test(node.tagName)) observation.counts.headings++
      if (node.tagName === 'img') observation.images.push({ url: String(node.properties.src || ''), line: (node.position?.start.line || 1) + options.processed.bodyLineOffset })
    })
    for (const message of file.messages) {
      if (message.source === 'rehype-katex') {
        // Flow math's generated <code> has no position; its <pre> ancestor
        // retains the Markdown location even after KaTeX replaces that node.
        const ancestorLine = [...(message.ancestors || [])].reverse().find((node: any) => node.position)?.position.start.line
        observation.diagnostics.push({ code: 'math.katex', severity: 'error', line: (message.line || ancestorLine || 1) + options.processed.bodyLineOffset, message: String(message.cause?.message || message.reason) })
      }
    }
  }
}

function rehypeLibraryPassages(options: { processed: ProcessedLibraryContent }) {
  return (tree: any) => {
    const assigned = new Set<number>()
    visit(tree, 'element', (node: any) => {
      if (!['p', 'table', 'pre', 'li'].includes(node.tagName) || !node.position) return
      const line = node.position.start.line + options.processed.bodyLineOffset
      if (assigned.has(line)) return
      assigned.add(line)
      node.properties ??= {}
      if (!node.properties.id) node.properties = { id: libraryPassageId(line), ...node.properties }
    })
  }
}

// Both ReactMarkdown in the daily website and the compiler use these exact
// plugin instances/options, including citations after math has been parsed.
export function getLibraryMarkdownOptions(processed: ProcessedLibraryContent, observation?: LibraryRenderObservation, linkCitations = true) {
  const remarkPlugins: PluggableList = [remarkGfm, remarkMath, remarkLibraryDisplayMath,
    [remarkLibraryFormatDiagnostics, { processed, observation }]]
  const rehypePlugins: PluggableList = [rehypeRaw, rehypeSlug, rehypeKatex,
    ...(linkCitations ? [[rehypeLibraryCitations, { processed, observation }] as any] : []), rehypeStyleCaptions,
    ...(linkCitations ? [[rehypeLibraryPassages, { processed }] as any] : []),
    [rehypeLibraryObserve, { processed, observation }]]
  return { remarkPlugins, rehypePlugins }
}

/** Bibliographic formulas and links use the same pipeline as the article. */
export function getLibraryReferenceMarkdownOptions(processed: ProcessedLibraryContent, entry: LibraryReference, observation?: LibraryRenderObservation) {
  return getLibraryMarkdownOptions({ ...processed, body: entry.content, bodyLineOffset: entry.line - 1 }, observation, false)
}
