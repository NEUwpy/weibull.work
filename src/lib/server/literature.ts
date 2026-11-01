import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'
import { isContentSlug, resolveContentFile } from './content-files'
import { getDataRoot } from './data-root'
import { indexSourcePapers, sourceDocument, sourceAsset, type SourceIndex } from './source-library'
import { readSourceReferenceIndex, readSourceSearchDois, type ReferenceIndexLocation } from './reference-index'

export class LibraryConfigurationError extends Error {
  constructor(message: string) {
    super(`文献库配置错误：${message}`)
    this.name = 'LibraryConfigurationError'
  }
}

export interface LibraryPaths {
  mode: 'external' | 'source'
  root: string
  contentDir: string
  assetsDir: string
  referencesFile: string
  sourceIndex?: SourceIndex
  referenceIndex?: ReferenceIndexLocation
  sourceDirectories?: string[]
}

export interface PaperMetadata {
  slug: string
  title: string
  title_en?: string
  author: string
  doi?: string
  affiliation?: string
  publication?: string
  short_publication?: string
  type?: string
  year: number
  tags: string[]
  summary: string
  related_method_id?: string
}

export interface PreferredPaper {
  slug: string
  raw: string
  metadata: Record<string, any>
  body: string
}

export interface LibraryDocument {
  paper: PaperMetadata
  version: '原文' | '翻译'
  raw: string
}

function isWithin(root: string, candidate: string): boolean {
  const relative = path.relative(root, candidate)
  return relative !== '..' && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative)
}

/** Resolve each component from its exact inventory, then reject links outside the root. */
function resolveEntry(root: string, segments: string[], kind: 'file' | 'directory'): string | null {
  if (!segments.length || segments.some(segment => !segment || segment === '.' || segment === '..' || /[/\\:\x00-\x1f\x7f]/.test(segment))) return null
  try {
    const realRoot = fs.realpathSync(root)
    let current = realRoot
    for (const segment of segments) {
      if (!fs.readdirSync(current).includes(segment)) return null
      current = fs.realpathSync(path.join(current, segment))
      if (!isWithin(realRoot, current)) return null
    }
    const stat = fs.statSync(current)
    return (kind === 'file' ? stat.isFile() : stat.isDirectory()) ? current : null
  } catch (error) {
    if (['ENOENT', 'ENOTDIR', 'ELOOP'].includes((error as NodeJS.ErrnoException).code || '')) return null
    throw error
  }
}

function configuredLibraryRoot(): string {
  return process.env.WEIBULL_LIBRARY_ROOT || path.join(getDataRoot(), 'literature')
}

/** Resolve on every call: a running server can see a replaced library or newly imported paper. */
export function getLibraryPaths(): LibraryPaths {
  const configured = configuredLibraryRoot()
  if (!path.isAbsolute(configured)) throw new LibraryConfigurationError('WEIBULL_LIBRARY_ROOT 必须是绝对路径')
  try {
    const root = fs.realpathSync(configured)
    if (!fs.statSync(root).isDirectory()) throw new Error('指定位置不是文件夹')
    const manifest = resolveEntry(root, ['library.json'], 'file')
    if (!manifest) throw new Error('缺少库内的 library.json')
    const descriptor = JSON.parse(fs.readFileSync(manifest, 'utf8'))
    if (descriptor?.schema_version === 2 && descriptor.mode === 'source') {
      const referencesFile = resolveEntry(root, ['references.json'], 'file')
      if (!referencesFile) throw new Error('源库选择配置须提供 references.json，没有关系时使用 {}')
      const sourceDirectories: string[] = []
      const sourceIndex = indexSourcePapers(descriptor.sources, sourceDirectories)
      let referenceIndex: ReferenceIndexLocation | undefined
      if (descriptor.reference_index !== undefined) {
        const entry = descriptor.reference_index
        if (!entry || typeof entry.root !== 'string' || typeof entry.file !== 'string' || path.isAbsolute(entry.file) ||
          entry.file.split(/[/\\]/).some((part: string) => !part || part === '.' || part === '..')) throw new Error('reference_index 必须指定 root 和库内相对 file')
        referenceIndex = { root: path.resolve(root, entry.root), file: entry.file }
      }
      return { mode: 'source', root, contentDir: root, assetsDir: root, referencesFile, sourceIndex, referenceIndex, sourceDirectories }
    }
    if (!descriptor || Array.isArray(descriptor) || descriptor.schema_version !== 1) throw new Error('library.json 的 schema_version 必须为 1')
    const contentDir = resolveEntry(root, ['content'], 'directory')
    const assetsDir = resolveEntry(root, ['assets'], 'directory')
    const referencesFile = resolveEntry(root, ['references.json'], 'file')
    if (!contentDir || !assetsDir || !referencesFile) throw new Error('需要库内的 content/、assets/ 和 references.json')
    return { mode: 'external', root, contentDir, assetsDir, referencesFile }
  } catch (error) {
    if (error instanceof LibraryConfigurationError) throw error
    throw new LibraryConfigurationError(`无法读取 WEIBULL_LIBRARY_ROOT（${configured}）：${(error as Error).message}`)
  }
}

function readText(file: string): string {
  const bytes = fs.readFileSync(file)
  try {
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  } catch {
    return new TextDecoder('gbk').decode(bytes)
  }
}

// The 100 rename record identifies the former website ID 144-003 as 171-003.
// This compatibility applies only to source mode and never widens its selection.
function canonicalSourceSlug(paths: LibraryPaths, slug: string): string {
  return paths.sourceIndex && slug === '144-003' ? '171-003' : slug
}

function readFrom(paths: LibraryPaths, slug: string, type: string): string | null {
  if (!isContentSlug(slug) || (type !== '原文' && type !== '翻译')) return null
  if (paths.sourceIndex) {
    const paper = paths.sourceIndex.get(canonicalSourceSlug(paths, slug))
    return paper ? sourceDocument(paper, type)?.raw ?? null : null
  }
  const file = resolveContentFile(paths.contentDir, `${slug}-pdf${type}.md`)
  return file ? readText(file) : null
}

export function readPaper(slug: string, type: string): string | null {
  return readFrom(getLibraryPaths(), slug, type)
}

function preferredFrom(paths: LibraryPaths, slug: string): PreferredPaper | null {
  const raw = readFrom(paths, slug, '翻译') ?? readFrom(paths, slug, '原文')
  if (raw === null) return null
  const { data, content } = matter(raw)
  return { slug, raw, metadata: data, body: content }
}

export function readPreferredPaper(slug: string): PreferredPaper | null {
  return preferredFrom(getLibraryPaths(), slug)
}

function selectedSlugs(paths: LibraryPaths): string[] {
  if (!fs.existsSync(paths.contentDir)) return []
  const slugs = new Set<string>()
  if (paths.sourceIndex) for (const slug of Array.from(paths.sourceIndex.keys())) slugs.add(slug)
  else for (const file of fs.readdirSync(paths.contentDir)) {
    const match = /^(.*)-pdf(?:原文|翻译)\.md$/.exec(file)
    if (match && isContentSlug(match[1])) slugs.add(match[1])
  }
  return Array.from(slugs)
}

function publicPaperMetadata(slug: string, data: Record<string, any>, sourceDois: Map<string, string>): PaperMetadata {
  return {
    slug, title: data.title, title_en: data.title_en,
    author: data.author || 'Unknown', affiliation: data.affiliation,
    doi: (typeof data.doi === 'string' ? data.doi : undefined) || sourceDois.get(slug),
    publication: data.publication, short_publication: data.short_publication,
    type: data.type || '文献', year: data.year || new Date().getFullYear(),
    tags: data.tags || [], summary: data.summary || '', related_method_id: data.related_method_id,
  }
}

function listFrom(paths: LibraryPaths): PaperMetadata[] {
  const papers: PaperMetadata[] = []
  const sourceDois = paths.referenceIndex && paths.sourceIndex ? readSourceSearchDois(paths.referenceIndex, paths.sourceIndex) : new Map<string, string>()
  for (const slug of selectedSlugs(paths)) {
    const paper = preferredFrom(paths, slug)
    if (!paper?.metadata.title) continue
    papers.push(publicPaperMetadata(slug, paper.metadata, sourceDois))
  }
  return papers
}

export function listPapers(): PaperMetadata[] {
  return listFrom(getLibraryPaths())
}

interface SearchDocumentCache {
  selector: string
  guards: Map<string, string>
  documents: LibraryDocument[]
  versions: Map<string, { revision: string; raw: string }>
}

// Shared across Next's independently compiled instrumentation and route modules.
// Bump the namespace when the snapshot representation changes.
const documentCacheKey = Symbol.for('weibull.library-documents.v2')
const documentCaches = globalThis as unknown as Record<symbol, SearchDocumentCache>
const documentCache = documentCaches[documentCacheKey] ??= {
  selector: '', guards: new Map(), documents: [], versions: new Map(),
}

function fileRevision(file: string): string {
  try {
    const stat = fs.lstatSync(file, { bigint: true })
    return [stat.dev, stat.ino, stat.mode, stat.size, stat.mtimeNs, stat.ctimeNs,
      stat.isSymbolicLink() ? fs.realpathSync(file) : ''].join(':')
  } catch (error) {
    if (['ENOENT', 'ENOTDIR', 'ELOOP'].includes((error as NodeJS.ErrnoException).code || '')) return 'missing'
    throw error
  }
}

function snapshotGuards(paths: LibraryPaths): Map<string, string> {
  const files = new Set([paths.root, paths.contentDir, paths.referencesFile,
    path.join(paths.root, 'library.json'), configuredLibraryRoot()])
  if (paths.sourceIndex) {
    for (const directory of paths.sourceDirectories || []) files.add(directory)
    for (const paper of Array.from(paths.sourceIndex.values())) {
      for (const file of [paper.original, paper.translation, paper.note]) if (file) files.add(file)
    }
    if (paths.referenceIndex) files.add(path.resolve(paths.referenceIndex.root, paths.referenceIndex.file))
  } else if (fs.existsSync(paths.contentDir)) {
    for (const name of fs.readdirSync(paths.contentDir).sort()) {
      const match = /^(.*)-pdf(?:原文|翻译)\.md$/.exec(name)
      if (!match || !isContentSlug(match[1])) continue
      const file = resolveContentFile(paths.contentDir, name)
      if (file) files.add(file)
    }
  }
  return new Map(Array.from(files, file => [file, fileRevision(file)]))
}

/** Check file metadata; unchanged selected sources never require body reads or full-text hashes. */
export function readLibraryDocuments(): LibraryDocument[] {
  const selector = JSON.stringify([process.cwd(), configuredLibraryRoot()])
  if (documentCache.selector === selector && documentCache.guards.size &&
    Array.from(documentCache.guards).every(([file, revision]) => fileRevision(file) === revision)) return documentCache.documents
  const paths = getLibraryPaths()
  const guards = snapshotGuards(paths)
  const documents: LibraryDocument[] = []
  const nextVersions = new Map<string, { revision: string; raw: string }>()
  const sourceDois = paths.referenceIndex && paths.sourceIndex ? readSourceSearchDois(paths.referenceIndex, paths.sourceIndex) : new Map<string, string>()
  for (const slug of selectedSlugs(paths)) {
    const versions: { version: '原文' | '翻译'; raw: string }[] = []
    for (const version of ['原文', '翻译'] as const) {
      const source = paths.sourceIndex?.get(slug)
      const file = source ? (version === '原文' ? source.original : source.translation)
        : resolveContentFile(paths.contentDir, `${slug}-pdf${version}.md`)
      if (!file) continue
      const revision = JSON.stringify([file, guards.get(file), source?.note && guards.get(source.note), source?.catalog])
      const key = `${slug}:${version}`
      const previous = documentCache.versions.get(key)
      const raw = previous?.revision === revision ? previous.raw : readFrom(paths, slug, version)
      if (raw !== null) { versions.push({ version, raw }); nextVersions.set(key, { revision, raw }) }
    }
    const preferred = versions.find(document => document.version === '翻译') ?? versions[0]
    if (!preferred) continue
    const data = matter(preferred.raw).data
    if (!data.title) continue
    const paper = publicPaperMetadata(slug, data, sourceDois)
    // A translation may omit a DOI present in its explicitly selected original.
    const versionMetadata = versions.map(document => matter(document.raw).data)
    const doi = paper.doi || versionMetadata.map(data => data.doi).find(value => typeof value === 'string')
    const alternateTitle = versionMetadata.map(data => data.title).find(value => typeof value === 'string' && value !== paper.title)
    const catalog = { ...paper, ...(doi ? { doi } : {}), ...(!paper.title_en && alternateTitle ? { title_en: alternateTitle } : {}) }
    for (const document of versions) documents.push({ paper: catalog, ...document })
  }
  documentCache.selector = selector
  documentCache.guards = guards
  documentCache.documents = documents
  documentCache.versions = nextVersions
  return documents
}

export function readReferences(slug: string, type?: string): Record<string, string> {
  const paths = getLibraryPaths()
  if (!isContentSlug(slug)) return {}
  slug = canonicalSourceSlug(paths, slug)
  if (paths.sourceIndex && !paths.sourceIndex.has(slug)) return {}
  if (type !== undefined && type !== '原文' && type !== '翻译') return {}
  if (paths.referenceIndex && paths.sourceIndex) {
    const paper = paths.sourceIndex.get(slug)!
    // Preserve the legacy map for explicitly retained sources outside this index (books).
    const relative = path.relative(paths.referenceIndex.root, paper.directory)
    if (relative !== '..' && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative)) {
      return readSourceReferenceIndex(paths.referenceIndex, paper, type ?? (paper.translation ? '翻译' : '原文'), paths.sourceIndex)
    }
  }
  const referencesFile = resolveEntry(path.dirname(paths.referencesFile), [path.basename(paths.referencesFile)], 'file')
  if (!referencesFile) throw new LibraryConfigurationError('无法读取 references.json')
  try {
    const references = JSON.parse(fs.readFileSync(referencesFile, 'utf8'))
    if (!references || typeof references !== 'object' || Array.isArray(references)) throw new Error('应为文献编号到引用关系的对象')
    // Accept the old source key for existing reference tables, with canonical entries preferred.
    const key = paths.sourceIndex && slug === '171-003' && !Object.hasOwn(references, slug) ? '144-003' : slug
    const entries = Object.hasOwn(references, key) ? references[key] : undefined
    if (entries === undefined) return {}
    if (!entries || typeof entries !== 'object' || Array.isArray(entries) || Object.values(entries).some(value => typeof value !== 'string')) throw new Error('引用关系应为字符串键值对象')
    return paths.sourceIndex ? Object.fromEntries(Object.entries(entries as Record<string, string>)
      .map(([number, target]) => [number, canonicalSourceSlug(paths, target)])
      .filter(([, target]) => paths.sourceIndex!.has(target))) : entries
  } catch (error) {
    throw new LibraryConfigurationError(`references.json 格式无效：${(error as Error).message}`)
  }
}

const assetTypes: Record<string, string> = {
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.gif': 'image/gif', '.webp': 'image/webp', '.svg': 'image/svg+xml',
  '.avif': 'image/avif', '.pdf': 'application/pdf',
}

/** Only paper image directories are public; unrelated files under the mounted root stay private. */
export function resolveLibraryAsset(segments: string[]): { path: string; contentType: string } | null {
  const paths = getLibraryPaths()
  if (segments.length < 2 || !segments[0].endsWith('-图片')) return null
  const slug = segments[0].slice(0, -'-图片'.length)
  if (!isContentSlug(slug)) return null
  const contentType = assetTypes[path.extname(segments[segments.length - 1]).toLowerCase()]
  if (!contentType) return null
  if (paths.sourceIndex) {
    const paper = paths.sourceIndex.get(canonicalSourceSlug(paths, slug))
    const file = paper ? sourceAsset(paper, segments.slice(1)) : null
    return file ? { path: file, contentType } : null
  }
  const file = resolveEntry(paths.assetsDir, segments, 'file')
  return file ? { path: file, contentType } : null
}
