import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'
import { isContentSlug } from './content-files'
import { extractLibraryNoteSummary } from '../library-note-summary'

export interface SourcePaper {
  id: string
  root: string
  directory: string
  original?: string
  translation?: string
  note?: string
  catalog?: Record<string, any>
  assetDirectory?: string
}

export type SourceIndex = Map<string, SourcePaper>

const excluded = new Set(['历史', '_archive', 'archive', 'history', '待回收', '已经移动了', '190_待处理与日志', 'images'])

function within(root: string, candidate: string): boolean {
  const relative = path.relative(root, candidate)
  return relative !== '..' && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative)
}

function sourceDirectory(directory: string): string | null {
  try {
    const real = fs.realpathSync(directory)
    if (!fs.statSync(real).isDirectory()) throw new Error('源资料 root 必须为目录')
    return real
  } catch (error) {
    if (['ENOENT', 'ENOTDIR'].includes((error as NodeJS.ErrnoException).code || '')) return null
    throw error
  }
}

/** The selection is configuration; bodies, notes and images stay in their original source. */
export function indexSourcePapers(sources: unknown, observedDirectories?: string[]): SourceIndex {
  if (!Array.isArray(sources) || sources.length === 0) throw new Error('sources 必须列出资料根目录与选用编号')
  const index: SourceIndex = new Map()
  for (const source of sources) {
    if (!source || typeof source.root !== 'string' || !path.isAbsolute(source.root)) throw new Error('源资料 root 必须为绝对路径')
    if (!Array.isArray(source.papers)) throw new Error('papers 必须为文献编号或题录对象数组')
    const entries = source.papers.map((item: any) => {
      const id = typeof item === 'string' ? item : item?.id
      if (typeof id !== 'string' || !isContentSlug(id)) throw new Error('题录必须有合法文献编号 id')
      const metadata = typeof item === 'string' ? undefined : item.metadata
      if (metadata !== undefined && (!metadata || typeof metadata !== 'object' || Array.isArray(metadata))) throw new Error(`metadata 必须为题录对象：${id}`)
      const allowed = new Set(['title', 'title_en', 'author', 'doi', 'affiliation', 'publication', 'short_publication', 'type', 'year', 'tags', 'summary', 'related_method_id'])
      if (metadata && Object.keys(metadata).some(key => !allowed.has(key))) throw new Error(`题录包含未支持字段：${id}`)
      for (const [field, value] of Object.entries(metadata ?? {})) {
        const valid = field === 'year' ? typeof value === 'number' && Number.isInteger(value) && value >= 1000 && value <= 9999
          : field === 'tags' ? Array.isArray(value) && value.every(tag => typeof tag === 'string') : typeof value === 'string'
        if (!valid) throw new Error(`JSON题录字段格式无效：${id} / ${field}`)
      }
      return { id, metadata }
    })
    const existingRoot = sourceDirectory(source.root)
    const root = existingRoot ?? path.resolve(source.root)
    observedDirectories?.push(source.root)
    if (source.layout !== undefined && source.layout !== 'v1') throw new Error('不支持的资料目录 layout')
    // Explicitly retained website books use the preserved content/assets
    // layout. This is a selected source, never an implicit library fallback.
    const contentRoot = source.layout === 'v1' ? sourceDirectory(path.join(root, 'content')) : existingRoot
    const assetsRoot = source.layout === 'v1' ? sourceDirectory(path.join(root, 'assets')) ?? path.join(root, 'assets') : undefined
    if (source.layout === 'v1') observedDirectories?.push(path.join(root, 'content'), path.join(root, 'assets'))
    if ((contentRoot && !within(root, contentRoot)) || (assetsRoot && !within(root, assetsRoot))) throw new Error('资料目录越过根目录')
    const selected = new Set<string>(entries.map((item: { id: string }) => item.id))
    if (selected.size !== entries.length) throw new Error('选用编号重复')
    for (const id of Array.from(selected)) if (index.has(id)) throw new Error(`选用编号重复：${id}`)
    const found = new Map<string, SourcePaper>()
    const walk = (directory: string): void => {
      observedDirectories?.push(directory)
      for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
        if (entry.isSymbolicLink()) continue
        const file = path.join(directory, entry.name)
        if (entry.isDirectory()) {
          if (!entry.name.startsWith('.') && !entry.name.endsWith('-图片') && !excluded.has(entry.name.toLowerCase())) walk(file)
          continue
        }
        const match = /^(.*)-(pdf原文|pdf翻译|笔记)\.md$/.exec(entry.name)
        if (!entry.isFile() || !match || !selected.has(match[1])) continue
        const real = fs.realpathSync(file)
        if (!within(root, real)) throw new Error('源文献越过资料根目录')
        const paper: SourcePaper = found.get(match[1]) ?? { id: match[1], root, directory,
          ...(assetsRoot ? { assetDirectory: path.join(assetsRoot, `${match[1]}-图片`) } : {}) }
        if (paper.directory !== directory) throw new Error(`源文献存在多个目录，需先确认版本：${paper.id}`)
        const key = match[2] === 'pdf原文' ? 'original' : match[2] === 'pdf翻译' ? 'translation' : 'note'
        if (paper[key]) throw new Error(`源文献存在多个版本：${paper.id}`)
        paper[key] = real
        found.set(paper.id, paper)
      }
    }
    if (contentRoot) walk(contentRoot)
    for (const id of Array.from(selected)) {
      // A missing mount or document does not remove its selected catalog entry.
      const paper = found.get(id) ?? { id, root, directory: contentRoot ?? root }
      paper.catalog = entries.find((item: { id: string }) => item.id === id)?.metadata
      index.set(id, paper)
    }
  }
  return index
}

function readText(file: string): string {
  const bytes = fs.readFileSync(file)
  try { return new TextDecoder('utf-8', { fatal: true }).decode(bytes) }
  catch { return new TextDecoder('gbk', { fatal: true }).decode(bytes) }
}

const noteSummaryCache = new Map<string, { mtime: number; ctime: number; size: number; summary: string }>()

/** Read only the selected note's summary, and invalidate it when the note changes. */
export function readSourceNoteSummary(paper: SourcePaper): string {
  if (!paper.note) return ''
  try {
    const stat = fs.statSync(paper.note)
    const cached = noteSummaryCache.get(paper.note)
    if (cached && cached.mtime === stat.mtimeMs && cached.ctime === stat.ctimeMs && cached.size === stat.size) return cached.summary
    const note = matter(readText(paper.note))
    const noteId = note.data.id ?? note.data.论文编号 ?? note.data.编号
    if (noteId !== undefined && String(noteId) !== paper.id) throw new Error(`笔记编号与文件名不一致：${paper.id}`)
    const summary = extractLibraryNoteSummary(note.content)
    noteSummaryCache.set(paper.note, { mtime: stat.mtimeMs, ctime: stat.ctimeMs, size: stat.size, summary })
    return summary
  } catch (error) {
    if (['ENOENT', 'ENOTDIR'].includes((error as NodeJS.ErrnoException).code || '')) return ''
    throw error
  }
}

/** Only exact, contained paper resources are readable; notes and neighbouring files are excluded. */
export function sourceAsset(paper: SourcePaper, segments: string[]): string | null {
  if (!segments.length || segments.some(s => !s || s === '.' || s === '..' || /[/\\:\x00-\x1f\x7f]/.test(s))) return null
  try {
    const assetRoot = paper.assetDirectory ?? path.join(paper.directory, `${paper.id}-图片`)
    if (!fs.readdirSync(path.dirname(assetRoot)).includes(path.basename(assetRoot))) return null
    const realRoot = fs.realpathSync(assetRoot)
    if (!within(paper.root, realRoot)) return null
    let current = realRoot
    for (const segment of segments) {
      if (!fs.readdirSync(current).includes(segment)) return null
      current = fs.realpathSync(path.join(current, segment))
      if (!within(realRoot, current)) return null
    }
    return fs.statSync(current).isFile() ? current : null
  } catch (error) {
    if (['ENOENT', 'ENOTDIR', 'ELOOP'].includes((error as NodeJS.ErrnoException).code || '')) return null
    throw error
  }
}

function imageUrl(paper: SourcePaper, value: string): string {
  if (/^(?:https?:|data:|\/)/i.test(value) || /[\r\n]/.test(value)) return value
  let relative = value
  try { relative = decodeURIComponent(value) } catch { return value }
  if (relative.startsWith('./')) relative = relative.slice(2)
  const prefix = `${paper.id}-图片/`
  const candidates = relative.startsWith(prefix) ? [relative.slice(prefix.length)]
    : relative.startsWith('images/') ? [relative, relative.slice('images/'.length)] : []
  const matches = candidates.filter(candidate => sourceAsset(paper, candidate.split('/')))
  if (matches.length > 1) throw new Error(`图片地址有歧义：${paper.id} / ${value}`)
  if (!matches.length) return value // Do not silently hide a missing resource; checks must report it.
  return `/${paper.id}-图片/` + matches[0].split('/').map(encodeURIComponent).join('/')
}

/** Adapt addresses and metadata in memory. Never rewrite a source file or publish private note sections. */
export function sourceDocument(paper: SourcePaper, version: string): { raw: string; metadata: Record<string, any>; body: string } | null {
  const file = version === '原文' ? paper.original : version === '翻译' ? paper.translation : undefined
  if (!file) return null
  const document = matter(readText(file))
  const note = paper.note ? matter(readText(paper.note)) : { data: {}, content: '' }
  // Website JSON is the public catalog; source Markdown remains untouched.
  const data = { ...document.data, ...paper.catalog }
  const n: Record<string, any> = note.data
  const noteId = n.id ?? n.论文编号 ?? n.编号
  if (noteId !== undefined && String(noteId) !== paper.id) throw new Error(`笔记编号与文件名不一致：${paper.id}`)
  const heading = /^#\s+(.+)$/m.exec(document.content)?.[1]?.trim()
  const title = data.title ?? heading ?? (version === '翻译' ? n.中文标题 : n.英文标题) ?? n.中文标题 ?? n.标题
  if (typeof title !== 'string' || !title.trim()) throw new Error(`源文献缺少可核实标题：${paper.id}`)
  const year = Number(data.year ?? n.年份)
  if (!Number.isInteger(year) || year < 1000 || year > 9999) throw new Error(`源文献缺少有效发表年份：${paper.id}`)
  const tags = data.tags ?? n.关键词 ?? n.tags ?? []
  if (!(typeof tags === 'string' || (Array.isArray(tags) && tags.every(tag => typeof tag === 'string')))) {
    throw new Error(`关键词必须为字符串或字符串数组：${paper.id}`)
  }
  const metadata = Object.fromEntries(Object.entries({
    title, title_en: data.title_en ?? n.英文标题,
    author: data.author ?? n.作者 ?? 'Unknown', doi: data.doi, affiliation: data.affiliation ?? n.单位,
    publication: data.publication ?? n.出版物 ?? n.期刊或类型 ?? n.期刊,
    short_publication: data.short_publication ?? n.出版简称 ?? n.期刊简称,
    type: data.type ?? n.文献类型 ?? n.type ?? '文献', year,
    tags: Array.from(new Set<string>(typeof tags === 'string' ? [tags] : tags)),
    summary: readSourceNoteSummary(paper) || (data.summary ?? ''),
    related_method_id: data.related_method_id ?? n.关联方法,
  }).filter(([, value]) => value !== undefined))
  for (const [field, value] of Object.entries(metadata)) {
    if (field !== 'year' && field !== 'tags' && typeof value !== 'string') throw new Error(`题录字段应为字符串：${paper.id} / ${field}`)
  }
  const body = document.content.replace(/(!\[[^\]\r\n]*\])\(([^)\r\n]+)\)/g, (match, alt, target) => `${alt}(${imageUrl(paper, target)})`)
  const display = document.data.citation_style === 'numeric-parentheses' ? { citation_style: 'numeric-parentheses' } : {}
  return { raw: matter.stringify(body, { ...metadata, ...display }), metadata, body }
}
