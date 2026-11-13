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

export const LIBRARY_RENDERER_VERSION = '1.3.0'

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
  abstract?: string
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
  const { content } = matter(raw)
  const prefix = raw.slice(0, raw.length - content.length)
  const bodyLineOffset = (prefix.match(/\n/g) || []).length
  const tree: any = unified().use(remarkParse).use(remarkGfm).use(remarkMath).parse(content)
  const referenceSection = findReferenceSection(tree, content.length)
  const passages: LibraryPassage[] = []
  const sections: string[] = []
  let sectionStartLine = 0
  visit(tree, (node: any) => {
    const offset = node.position?.start.offset
    if (referenceSection && offset >= referenceSection.start && offset < referenceSection.end) return
    if (node.type === 'heading') {
      sections.length = node.depth
      sections[node.depth - 1] = nodeText(node).trim()
      sectionStartLine = node.position.start.line + bodyLineOffset
    }
    if (!['paragraph', 'table', 'code', ...(includeMath ? ['math'] : [])].includes(node.type) || !node.position) return
    const text = content.slice(node.position.start.offset, node.position.end.offset).trim()
    const plainText = nodeText(node).replace(/\s+/g, ' ').trim()
    if (!plainText) return
    passages.push({ section: sections.filter(Boolean).join(' / ') || '正文', sectionStartLine, kind: node.type,
      startLine: node.position.start.line + bodyLineOffset,
      endLine: node.position.end.line + bodyLineOffset, text, plainText })
  })
  return passages
}

function findReferenceSection(tree: any, length: number): { heading: any; start: number; end: number } | null {
  const index = tree.children.findIndex((node: any) => node.type === 'heading' && /^(参考文献|references|bibliography)\s*[:：]?$/i.test(nodeText(node).trim()))
  if (index < 0) return null
  const heading = tree.children[index]
  const next = tree.children.slice(index + 1).find((node: any) => node.type === 'heading' && node.depth <= heading.depth)
  return { heading, start: heading.position.start.offset, end: next?.position.start.offset ?? length }
}

// The source line numbers remain intact: removing a reference section replaces it
// with blank lines, so diagnostics still point to the original Markdown.
export function processLibraryContent(rawMarkdown: string, options: { requireAbstract?: boolean } = {}): ProcessedLibraryContent {
  const { data, content } = matter(rawMarkdown)
  const prefix = rawMarkdown.slice(0, rawMarkdown.length - content.length)
  const bodyLineOffset = (prefix.match(/\n/g) || []).length
  const tree: any = unified().use(remarkParse).use(remarkGfm).use(remarkMath).parse(content)
  const diagnostics: LibraryDiagnostic[] = articleStructureDiagnostics(tree, bodyLineOffset, Boolean(options.requireAbstract))
  const referenceEntries: LibraryReference[] = []
  let body = content
  let referenceTitle = '参考文献'
  const referenceSection = findReferenceSection(tree, content.length)

  if (referenceSection) {
    const { heading, start, end } = referenceSection
    referenceTitle = nodeText(heading).trim().replace(/[:：]$/, '')
    const refsStart = heading.position.end.offset
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

  // The reader already presents the public title and credits above the article.
  // Keep source positions stable while starting article reading at its abstract.
  const abstract = tree.children.find((node: any) => node.type === 'heading' && isAbstractTitle(nodeText(node)))
  let abstractText: string | undefined
  if (abstract && !['书籍', '软件文档', '技术资料'].includes(data.type)) {
    const start = abstract.position.start.offset
    const after = tree.children.slice(tree.children.indexOf(abstract) + 1)
    const next = after.find((node: any) => node.type === 'heading' || isKeywordsTitle(nodeText(node)))
    abstractText = content.slice(abstract.position.end.offset, next?.position.start.offset ?? content.length).trim()
    body = body.slice(0, start).replace(/[^\r\n]/g, '') + body.slice(start)
  }

  const slugger = new GithubSlugger()
  const bodyTree: any = unified().use(remarkParse).use(remarkGfm).use(remarkMath).parse(body)
  const headings: ProcessedLibraryContent['headings'] = []
  visit(bodyTree, 'heading', (node: any) => {
    const text = headingText(node).trim()
    const slug = slugger.slug(nodeText(node).trim())
    if (node.depth <= 3) headings.push({ level: node.depth, text, slug })
  })
  return { frontmatter: data, body, abstract: abstractText, referenceTitle, referenceList: referenceEntries.map(entry => entry.raw), referenceEntries, headings, diagnostics, bodyLineOffset }
}

function nodeText(node: any): string {
  return typeof node.value === 'string' ? node.value : (node.children || []).map(nodeText).join('')
}

function isAbstractTitle(text: string): boolean {
  return /^(?:abstract|摘\s*要|中文摘要|英文摘要)(?:\s*[:：.]|\s*[（(](?:abstract|摘要)[)）])?$/i.test(text.trim())
}

function isKeywordsTitle(text: string): boolean {
  return /^(?:key\s*words?|关键词|关键字)(?:\s*[:：.]|$)/i.test(text.trim())
}

/** Content checks only: visual abstract styling belongs to the shared renderer. */
function articleStructureDiagnostics(tree: any, offset: number, required: boolean): LibraryDiagnostic[] {
  const diagnostics: LibraryDiagnostic[] = []
  const report = (node: any, code: string, message: string) => diagnostics.push({ code, message, severity: 'error', line: (node?.position?.start?.line || 1) + offset })
  const nodes: any[] = tree.children
  const abstractIndex = nodes.findIndex(node => node.type === 'heading' && isAbstractTitle(nodeText(node)))
  // Match standalone publisher controls, never mentions inside scientific prose,
  // code examples, quotations, captions or bibliographic reference entries.
  const publisher = /^(?:view supplementary material|submit your article to this journal|article views\s*[:：]|view related articles|view crossmark data|check for updates|(?:请)?(?:查看|检查)更新|查看补充材料|向本刊投稿|文章浏览量\s*[:：]|查看相关文章|查看\s*crossmark\s*数据|published online\s*[:：]|(?:首次)?在线发表\s*[:：]|to cite this article\s*[:：]|to link to this article\s*[:：]|引用本文\s*[:：]|原文链接\s*[:：]|full terms\s*[&＆]\s*conditions|journal homepage\s*[:：])/i
  for (const node of nodes) {
    if (!['paragraph', 'heading'].includes(node.type)) continue
    const text = nodeText(node).replace(/\s+/g, ' ').trim()
    if (text.length < 1000 && publisher.test(text)) report(node, 'article.publisher-chrome', '正文混入出版商页面控件或封面杂项；对照原文删除该项及仅为该控件服务的图标，保留实际补充材料说明和学术图表。')
  }
  if (!required) return diagnostics
  if (abstractIndex < 0) {
    const inline = nodes.find(node => node.type === 'paragraph' && /^(?:abstract|摘\s*要)\s*[:：.—-]?\s*/i.test(nodeText(node)))
    report(inline || nodes[0], 'article.abstract-missing', '未找到独立的“## Abstract”或“## 摘要”区。请对照原文整理摘要，正文须从摘要开始；不得用笔记总结代替或编造摘要。')
    return diagnostics
  }
  const abstract = nodes[abstractIndex]
  const before = nodes.slice(0, abstractIndex)
  // A single article title and its short bibliographic/author lines are front
  // matter, not body sections. Tables, figures and numbered body sections are not.
  const title = before.find(node => node.type === 'heading' && node.depth === 1)
  for (const node of before) {
    const text = nodeText(node).trim()
    if ((node.type === 'heading' && node !== title) || ['table', 'code', 'math', 'blockquote', 'list'].includes(node.type) ||
        (node.type === 'paragraph' && (node.children?.some((child: any) => child.type === 'image' || child.type === 'imageReference') || text.length > 900)) ||
        (node.type === 'html' && /<(?:img|table)\b/i.test(text))) {
      report(node, 'article.before-abstract', '摘要前存在正文章节、图表或非题录内容；核对PDF，删除识别杂项，实际正文与图表应放在摘要之后。')
    }
  }
  const next = nodes.findIndex((node, index) => index > abstractIndex && node.type === 'heading' && node.depth <= abstract.depth)
  const region = nodes.slice(abstractIndex + 1, next < 0 ? nodes.length : next)
  const prose = region.filter(node => ['paragraph', 'list'].includes(node.type) && !isKeywordsTitle(nodeText(node)))
  if (!prose.some(node => nodeText(node).trim())) report(abstract, 'article.abstract-empty', '摘要区为空或只有关键词；须保留原论文的摘要正文。')
  const following = next < 0 ? [] : nodes.slice(next).filter(node => node.type === 'heading' && !isAbstractTitle(nodeText(node)) && !isKeywordsTitle(nodeText(node)) && !/^(?:references|参考文献|bibliography)\s*[:：]?$/i.test(nodeText(node).trim()))
  if (!following.length) report(abstract, 'article.body-missing', '摘要之后未识别到正文章节；请检查是否仅保留了摘要或正文标题尚未整理，不能以摘要代替全文。')
  return diagnostics
}

function rehypeLibraryAbstract() {
  return (tree: any) => {
    for (let index = 0; index < tree.children.length; index++) {
      const heading = tree.children[index]
      if (heading.type !== 'element' || !/^h[1-6]$/.test(heading.tagName) || !isAbstractTitle(nodeText(heading))) continue
      let end = index + 1
      while (end < tree.children.length) {
        const node = tree.children[end]
        if (node.type === 'element' && ((/^h[1-6]$/.test(node.tagName) && node.tagName <= heading.tagName) || (node.tagName === 'p' && isKeywordsTitle(nodeText(node))))) break
        end++
      }
      const section = element('section', { className: ['library-abstract'], 'aria-label': nodeText(heading).trim() }, tree.children.slice(index, end))
      tree.children.splice(index, end - index, section)
    }
  }
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

// Raw HTML bypasses remark's phrasing parser. Parse only raw <td>/<th> text,
// keeping all non-math text and the original table semantics intact.
function rehypeLibraryHtmlCellMath(options: { processed: ProcessedLibraryContent; observation?: LibraryRenderObservation }) {
  const parser = unified().use(remarkParse).use(remarkMath).use(remarkLibraryDisplayMath)
  const excludedTags = new Set(['code', 'pre', 'script', 'style', 'math', 'annotation', 'svg', 'textarea'])
  return (tree: any, file: any) => {
    const source = String(file.value)
    const scan = (parent: any, rawCell = false) => {
      if (!parent.children || excludedTags.has(parent.tagName) || classes(parent).some(name => name.startsWith('katex'))) return
      const offset = parent.position?.start?.offset
      const cell = rawCell || (['td', 'th'].includes(parent.tagName) && Number.isInteger(offset) && /^<t[dh](?:\s|>)/i.test(source.slice(offset)))
      for (let index = 0; index < parent.children.length; index++) {
        const node = parent.children[index]
        if (!cell || node.type !== 'text' || !node.value.includes('$')) { scan(node, cell); continue }
        const line = node.position?.start?.line || parent.position?.start?.line || 1
        const localFile = { value: node.value }
        const parsed: any = parser.runSync(parser.parse(node.value), localFile)
        remarkLibraryFormatDiagnostics({ ...options, processed: { ...options.processed, bodyLineOffset: options.processed.bodyLineOffset + line - 1 } })(parsed, localFile)
        const maths: any[] = []
        visit(parsed, (candidate: any) => {
          if (candidate.type === 'inlineMath' || candidate.type === 'math') maths.push(candidate)
        })
        if (!maths.length) continue
        const position = (point: any) => ({ line: line + point.line - 1, column: point.line === 1 ? (node.position?.start?.column || 1) + point.column - 1 : point.column })
        const parts: any[] = []
        let last = 0
        const appendText = (end: number) => {
          if (end <= last) return
          const value = node.value.slice(last, end)
          const preceding = node.value.slice(0, last).split('\n')
          parts.push({ type: 'text', value, position: { start: position({ line: preceding.length, column: preceding.at(-1)!.length + 1 }) } })
        }
        for (const math of maths) {
          appendText(math.position.start.offset)
          // These HAST instructions are supplied by remark-math itself.
          parts.push({ ...element(math.data.hName, math.data.hProperties || {}, math.data.hChildren),
            position: { start: position(math.position.start), end: position(math.position.end) } })
          last = math.position.end.offset
        }
        appendText(node.value.length)
        parent.children.splice(index, 1, ...parts)
        index += parts.length - 1
      }
    }
    scan(tree)
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
          const line = (node.position?.start?.line || 1) + processed.bodyLineOffset + (node.value.slice(0, match.index).match(/\n/g) || []).length
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

function rehypeLibraryTables() {
  return (tree: any) => {
    const scan = (parent: any) => {
      if (!parent.children || ['code', 'pre', 'math', 'svg'].includes(parent.tagName) || classes(parent).some(name => name.startsWith('katex'))) return
      for (let index = 0; index < parent.children.length; index++) {
        const node = parent.children[index]
        scan(node)
        if (node.tagName !== 'table') continue
        node.properties ??= {}
        node.properties.className = Array.from(new Set([...classes(node), 'library-table']))
        if (classes(parent).includes('library-table-scroll')) continue
        const previous = parent.children.slice(0, index).filter((child: any) => child.type === 'element').at(-1)
        const caption = previous && classes(previous).includes('table-caption') ? previous : null
        const properties: Record<string, any> = { className: ['library-table-scroll'], tabIndex: 0, role: 'region' }
        if (caption?.properties.id) properties.ariaLabelledBy = caption.properties.id
        else properties.ariaLabel = '表格，可横向滚动'
        parent.children[index] = element('div', properties, [node])
      }
    }
    scan(tree)
  }
}

function rehypeLibraryObserve(options: { processed: ProcessedLibraryContent; observation?: LibraryRenderObservation }) {
  return (tree: any, file: any) => {
    const observation = options.observation
    if (!observation) return
    visit(tree, 'element', (node: any) => {
      const names = classes(node)
      if (names.includes('katex')) observation.counts.math++
      if (node.tagName === 'table' && names.includes('library-table')) observation.counts.tables++
      if (/^h[1-6]$/.test(node.tagName)) observation.counts.headings++
      if (node.tagName === 'img') observation.images.push({ url: String(node.properties.src || ''), line: (node.position?.start?.line || 1) + options.processed.bodyLineOffset })
    })
    for (const message of file.messages) {
      if (message.source === 'rehype-katex') {
        // Flow math's generated <code> has no position; its <pre> ancestor
        // retains the Markdown location even after KaTeX replaces that node.
        const ancestorLine = [...(message.ancestors || [])].reverse().find((node: any) => node.position?.start?.line)?.position.start.line
        observation.diagnostics.push({ code: 'math.katex', severity: 'error', line: (message.line || ancestorLine || 1) + options.processed.bodyLineOffset, message: String(message.cause?.message || message.reason) })
      }
    }
  }
}

function rehypeLibraryPassages(options: { processed: ProcessedLibraryContent }) {
  return (tree: any) => {
    const assigned = new Set<number>()
    visit(tree, 'element', (node: any) => {
      const sourceLine = node.position?.start?.line
      // rehype-raw may merge generated whitespace into a node with only an end position.
      // Generated nodes must not invent a source passage or share its fallback line.
      if (!['p', 'table', 'pre', 'li'].includes(node.tagName) || !Number.isInteger(sourceLine) || sourceLine < 1) return
      const line = sourceLine + options.processed.bodyLineOffset
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
  const rehypePlugins: PluggableList = [rehypeRaw, rehypeSlug, [rehypeLibraryHtmlCellMath, { processed, observation }], rehypeKatex,
    ...(linkCitations ? [[rehypeLibraryCitations, { processed, observation }] as any] : []), rehypeStyleCaptions,
    ...(linkCitations ? [[rehypeLibraryPassages, { processed }] as any] : []),
    rehypeLibraryTables, rehypeLibraryAbstract,
    [rehypeLibraryObserve, { processed, observation }]]
  return { remarkPlugins, rehypePlugins }
}

/** Bibliographic formulas and links use the same pipeline as the article. */
export function getLibraryReferenceMarkdownOptions(processed: ProcessedLibraryContent, entry: LibraryReference, observation?: LibraryRenderObservation) {
  return getLibraryMarkdownOptions({ ...processed, body: entry.content, bodyLineOffset: entry.line - 1 }, observation, false)
}
