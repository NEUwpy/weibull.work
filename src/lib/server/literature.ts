import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'
import { isContentSlug, resolveContentFile } from './content-files'

export class LibraryConfigurationError extends Error {
  constructor(message: string) {
    super(`文献库配置错误：${message}`)
    this.name = 'LibraryConfigurationError'
  }
}

export interface LibraryPaths {
  mode: 'embedded' | 'external'
  root: string
  contentDir: string
  assetsDir: string
  referencesFile: string
}

export interface PaperMetadata {
  slug: string
  title: string
  title_en?: string
  author: string
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

/** Resolve on every call: a running server can see a replaced library or newly imported paper. */
export function getLibraryPaths(): LibraryPaths {
  const configured = process.env.WEIBULL_LIBRARY_ROOT
  if (configured === undefined || configured === '') {
    const root = process.cwd()
    return {
      mode: 'embedded', root,
      contentDir: path.join(root, 'src/content'),
      assetsDir: path.join(root, 'public'),
      referencesFile: path.join(root, 'src/data/references.json'),
    }
  }
  if (!path.isAbsolute(configured)) throw new LibraryConfigurationError('WEIBULL_LIBRARY_ROOT 必须是绝对路径')
  try {
    const root = fs.realpathSync(configured)
    if (!fs.statSync(root).isDirectory()) throw new Error('指定位置不是文件夹')
    const manifest = resolveEntry(root, ['library.json'], 'file')
    if (!manifest) throw new Error('缺少库内的 library.json')
    const descriptor = JSON.parse(fs.readFileSync(manifest, 'utf8'))
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

function readFrom(paths: LibraryPaths, slug: string, type: string): string | null {
  if (!isContentSlug(slug) || (type !== '原文' && type !== '翻译')) return null
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

export function listPapers(): PaperMetadata[] {
  const paths = getLibraryPaths()
  if (!fs.existsSync(paths.contentDir)) return []
  const slugs = new Set<string>()
  for (const file of fs.readdirSync(paths.contentDir)) {
    const match = /^(.*)-pdf(?:原文|翻译)\.md$/.exec(file)
    if (match && isContentSlug(match[1])) slugs.add(match[1])
  }
  const papers: PaperMetadata[] = []
  for (const slug of Array.from(slugs)) {
    const paper = preferredFrom(paths, slug)
    if (!paper?.metadata.title) continue
    const data = paper.metadata
    papers.push({
      slug, title: data.title, title_en: data.title_en,
      author: data.author || 'Unknown', affiliation: data.affiliation,
      publication: data.publication, short_publication: data.short_publication,
      type: data.type || '文献', year: data.year || new Date().getFullYear(),
      tags: data.tags || [], summary: data.summary || '', related_method_id: data.related_method_id,
    })
  }
  return papers
}

export function readReferences(slug: string): Record<string, string> {
  const paths = getLibraryPaths()
  if (!isContentSlug(slug)) return {}
  const referencesFile = resolveEntry(path.dirname(paths.referencesFile), [path.basename(paths.referencesFile)], 'file')
  if (!referencesFile) {
    if (paths.mode === 'external') throw new LibraryConfigurationError('无法读取 references.json')
    return {}
  }
  try {
    const references = JSON.parse(fs.readFileSync(referencesFile, 'utf8'))
    if (!references || typeof references !== 'object' || Array.isArray(references)) throw new Error('应为文献编号到引用关系的对象')
    const entries = Object.hasOwn(references, slug) ? references[slug] : undefined
    if (entries === undefined) return {}
    if (!entries || typeof entries !== 'object' || Array.isArray(entries) || Object.values(entries).some(value => typeof value !== 'string')) throw new Error('引用关系应为字符串键值对象')
    return entries
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
  const file = resolveEntry(paths.assetsDir, segments, 'file')
  return file ? { path: file, contentType } : null
}
