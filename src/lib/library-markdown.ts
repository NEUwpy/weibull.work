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

export const LIBRARY_RENDERER_VERSION = '1.3.1'

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
  inlineAbstractLines?: number[]
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
  const isArticle = !['书籍', '软件文档', '技术资料'].includes(data.type)
  const abstracts = isArticle ? openingAbstracts(tree.children) : []
  const diagnostics = articleStructureDiagnostics(tree.children, bodyLineOffset, Boolean(options.requireAbstract), abstracts)
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
  const firstAbstract = abstracts[0]
  let abstractText: string | undefined
  if (firstAbstract !== undefined) {
    const abstract = tree.children[firstAbstract]
    const start = abstract.position.start.offset
    const next = tree.children[abstractEnd(tree.children, firstAbstract)]
    abstractText = abstractLabel(abstract)?.inline
      ? content.slice(start, abstract.position.end.offset).trim()
      : content.slice(abstract.position.end.offset, next?.position.start.offset ?? content.length).trim()
    if (beforeAbstractIssues(tree.children.slice(0, firstAbstract)).length === 0) {
      body = body.slice(0, start).replace(/[^\r\n]/g, '') + body.slice(start)
    }
  }

  const slugger = new GithubSlugger()
  const bodyTree: any = unified().use(remarkParse).use(remarkGfm).use(remarkMath).parse(body)
  const headings: ProcessedLibraryContent['headings'] = []
  visit(bodyTree, 'heading', (node: any) => {
    const text = headingText(node).trim()
    const slug = slugger.slug(nodeText(node).trim())
    if (node.depth <= 3) headings.push({ level: node.depth, text, slug })
  })
  const inlineAbstractLines = abstracts.map(index => tree.children[index])
    .filter(node => node.type === 'paragraph').map(node => node.position.start.line)
  return { frontmatter: data, body, abstract: abstractText, inlineAbstractLines, referenceTitle, referenceList: referenceEntries.map(entry => entry.raw), referenceEntries, headings, diagnostics, bodyLineOffset }
}

function nodeText(node: any): string {
  return typeof node.value === 'string' ? node.value : (node.children || []).map(nodeText).join('')
}

const abstractTitle = /^(?:abstract|摘\s*要|中文摘要|英文摘要)(?:\s*[:：.]|\s*[（(](?:abstract|摘要)[)）])?$/i
const inlineAbstractTitle = /^\s*(?:【(abstract|摘\s*要|中文摘要|英文摘要)】\s*|(abstract|摘\s*要|中文摘要|英文摘要)(?:\s*[:：.。—–-]+\s*|\s+|$))/i

function isKeywordsTitle(text: string): boolean {
  const label = text.trim()
  return /^(?:key\s*words?|关键词|关键字)(?:\s*[:：.。—–-]|\s+|$)/i.test(label)
}

function headingLevel(node: any): number {
  return node.type === 'heading' ? node.depth : /^h[1-6]$/.test(node.tagName || '') ? Number(node.tagName[1]) : 0
}

function paragraph(node: any): boolean {
  return node.type === 'paragraph' || node.tagName === 'p'
}

function abstractLabel(node: any) {
  if (headingLevel(node)) {
    const title = nodeText(node).trim()
    return abstractTitle.test(title) ? { title, prefixLength: 0, inline: false } : undefined
  }
  if (!paragraph(node)) return
  const text = nodeText(node)
  const match = text.match(inlineAbstractTitle)
  if (!match) return
  const label = match[1] || match[2]
  const prefixLength = match[0].length
  return { title: /^abstract$/i.test(label) ? 'Abstract' : label.replace(/\s+/g, ''), prefixLength, inline: Boolean(text.slice(prefixLength).trim()) }
}

function abstractEnd(nodes: any[], start: number): number {
  const level = headingLevel(nodes[start])
  if (!level && abstractLabel(nodes[start])?.inline) return start + 1
  const next = nodes.findIndex((node, index) => index > start && (
    (headingLevel(node) > 0 && (headingLevel(node) <= Math.max(2, level) || abstractLabel(node))) ||
    ((headingLevel(node) || paragraph(node)) && isKeywordsTitle(nodeText(node)))
  ))
  return next < 0 ? nodes.length : next
}

const articleSectionTitle = /^(?:\d+(?:[.．]\d+)*(?:[\s.．、]|(?=[\u3400-\u9fff]))|[一二三四五六七八九十]+[、.]|引\s*言|前\s*言|introduction\b|参考文献|references\b)/i

function openingAbstracts(nodes: any[]): number[] {
  const first = nodes.findIndex(node => abstractLabel(node))
  if (first < 0) return []
  const abstracts = [first]
  // A bilingual title may precede the companion abstract. Stop at a body section.
  for (let index = abstractEnd(nodes, first); index < nodes.length; index++) {
    const node = nodes[index]
    if (abstractLabel(node)) { abstracts.push(index); break }
    const level = headingLevel(node)
    if (!level) continue
    const title = nodeText(node).trim()
    if (!isKeywordsTitle(title) && (level > 1 || articleSectionTitle.test(title))) break
  }
  return abstracts
}

function beforeAbstractIssues(before: any[]): any[] {
  const title = before.find(node => headingLevel(node) === 1 && !articleSectionTitle.test(nodeText(node).trim()))
  return before.filter(node => {
    const text = nodeText(node).trim()
    // A wrapped affiliation line such as “2. 某大学实验室…” parses as an ordered list.
    const affiliationList = node.type === 'list' && node.ordered && node.children.every((item: any) => {
      const affiliation = nodeText(item).trim()
      return item.children.length === 1 && affiliation.length <= 300 && !/[。！？]/.test(affiliation) &&
        /大学|学院|实验室|研究[所院]|\b(?:university|department|school|laboratory|institute)\b/i.test(affiliation)
    })
    return (headingLevel(node) > 0 && node !== title) || ['table', 'code', 'math', 'blockquote'].includes(node.type) ||
      (node.type === 'list' && !affiliationList) ||
      (paragraph(node) && (isKeywordsTitle(text) || node.children?.some((child: any) => child.type === 'image' || child.type === 'imageReference') || text.length > 900)) ||
      (node.type === 'html' && /<(?:img|table)\b/i.test(text))
  })
}

const articleEndMatter = /^(?:references|bibliography|参考文献|致\s*谢|附\s*录|appendix|acknowledg(?:e)?ments?|funding|data availability|作者贡献|基金资助)(?:$|\s|[:：])/i

function hasArticleBody(nodes: any[], start: number): boolean {
  let inSection = false
  for (const node of nodes.slice(start)) {
    if (headingLevel(node)) {
      const text = nodeText(node).trim()
      if (articleEndMatter.test(text)) return false
      inSection = !abstractLabel(node) && !isKeywordsTitle(text)
    } else if (inSection && ['paragraph', 'list', 'table', 'code', 'math', 'blockquote', 'html'].includes(node.type) &&
      !isKeywordsTitle(nodeText(node)) && (nodeText(node).trim() || node.children?.some((child: any) => ['image', 'imageReference'].includes(child.type)))) return true
  }
  return false
}

/** Content checks only: visual abstract styling belongs to the shared renderer. */
function articleStructureDiagnostics(nodes: any[], offset: number, required: boolean, abstracts: number[]): LibraryDiagnostic[] {
  const diagnostics: LibraryDiagnostic[] = []
  const report = (node: any, code: string, message: string) => diagnostics.push({ code, message, severity: 'error', line: (node?.position?.start?.line || 1) + offset })
  // Match standalone publisher controls, never mentions inside scientific prose,
  // code examples, quotations, captions or bibliographic reference entries.
  const publisher = /^(?:view supplementary material|submit your article to this journal|article views\s*[:：]|view related articles|view crossmark data|check for updates|(?:请)?(?:查看|检查)更新|查看补充材料|向本刊投稿|文章浏览量\s*[:：]|查看相关文章|查看\s*crossmark\s*数据|published online\s*[:：]|(?:首次)?在线发表\s*[:：]|to cite this article\s*[:：]|to link to this article\s*[:：]|引用本文\s*[:：]|原文链接\s*[:：]|full terms\s*[&＆]\s*conditions|journal homepage\s*[:：])/i
  for (const node of nodes) {
    if (!['paragraph', 'heading'].includes(node.type)) continue
    const text = nodeText(node).replace(/\s+/g, ' ').trim()
    if (text.length < 1000 && publisher.test(text)) report(node, 'article.publisher-chrome', '正文混入出版商页面控件或封面杂项；对照原文删除该项及仅为该控件服务的图标，保留实际补充材料说明和学术图表。')
  }
  if (!required) return diagnostics
  if (!abstracts.length) {
    report(nodes[0], 'article.abstract-missing', '未找到摘要区。对照原文补齐实际摘要，使用独立二级标题“## Abstract”或“## 摘要”，其后接正文。')
    return diagnostics
  }
  for (const node of beforeAbstractIssues(nodes.slice(0, abstracts[0]))) {
    report(node, 'article.before-abstract', '摘要前存在正文章节、图表或非题录内容，核对PDF后将实际正文与图表放在摘要之后。')
  }
  let bodyStart = 0
  for (const index of abstracts) {
    const abstract = nodes[index]
    const label = abstractLabel(abstract)!
    if (headingLevel(abstract) !== 2) {
      report(abstract, 'article.abstract-format', '将摘要标签单独写成二级标题“## 摘要”或“## Abstract”，下一段保留原有摘要内容。')
    }
    bodyStart = abstractEnd(nodes, index)
    const prose = nodes.slice(index + 1, bodyStart).filter(node => ['paragraph', 'list'].includes(node.type))
    const hasText = label.inline || prose.some(node => nodeText(node).trim())
    if (!hasText) report(abstract, 'article.abstract-empty', '摘要区为空或只有关键词，须保留原论文的摘要正文。')
  }
  if (!hasArticleBody(nodes, bodyStart)) report(nodes[abstracts.at(-1)!], 'article.body-missing', '摘要后须有包含实际内容的正文章节。核对是否只有题录、空标题、关键词或文末参考文献等附属内容。')
  return diagnostics
}

function removeTextPrefix(node: any, length: number): number {
  if (node.type === 'text') {
    const removed = Math.min(length, node.value.length)
    node.value = node.value.slice(removed)
    return length - removed
  }
  for (const child of node.children || []) {
    length = removeTextPrefix(child, length)
    if (!length) break
  }
  return length
}

function rehypeLibraryAbstract(options: { inlineLines: number[] }) {
  const lines = new Set(options.inlineLines)
  return (tree: any) => {
    for (let index = 0; index < tree.children.length; index++) {
      const node = tree.children[index]
      if (!headingLevel(node) && !lines.has(node.position?.start?.line)) continue
      const label = abstractLabel(node)
      if (!label) continue
      const end = abstractEnd(tree.children, index)
      const children = tree.children.slice(index, end)
      if (label.prefixLength) {
        const title = element('h2', label.inline ? {} : node.properties, [{ type: 'text', value: label.title }])
        if (label.inline) {
          removeTextPrefix(node, label.prefixLength)
          children.unshift(title)
        } else children[0] = title
      }
      const section = element('section', { className: ['library-abstract'], 'aria-label': label.title }, children)
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
    rehypeLibraryTables, [rehypeLibraryAbstract, { inlineLines: linkCitations ? processed.inlineAbstractLines || [] : [] }],
    [rehypeLibraryObserve, { processed, observation }]]
  return { remarkPlugins, rehypePlugins }
}

/** Bibliographic formulas and links use the same pipeline as the article. */
export function getLibraryReferenceMarkdownOptions(processed: ProcessedLibraryContent, entry: LibraryReference, observation?: LibraryRenderObservation) {
  return getLibraryMarkdownOptions({ ...processed, body: entry.content, bodyLineOffset: entry.line - 1 }, observation, false)
}
