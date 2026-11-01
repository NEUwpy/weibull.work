import fs from 'fs'
import path from 'path'
import { DataConfigurationError, getDataRoot, resolveRootEntry } from './data-root'

/** Public result files only; source documents, models and private experiments stay inaccessible. */
export function isRuntimeDataPath(segments: string[]): boolean {
  if (segments.some(part => typeof part !== 'string' || !part || part === '.' || part === '..' || /[/\\:\x00-\x1f\x7f]/.test(part))) return false
  const allowed = (segments[0] === 'studies' && segments.length >= 3)
    || (segments[0] === 'case-studies' && segments.length >= 3)
    || (segments[0] === 'ai' && segments[1] === 'data' && segments.length >= 3)
  return allowed && ['.csv', '.json'].includes(path.extname(segments[segments.length - 1] || ''))
}

export function requireRuntimeDataRoot(): void {
  if (!resolveRootEntry(getDataRoot(), ['public'], 'directory')) {
    throw new DataConfigurationError('网站结果目录缺失，请配置 WEIBULL_DATA_ROOT 并提供 public 数据目录')
  }
}

function resolvePublicDataEntry(segments: string[], kind: 'file' | 'directory' = 'file'): string | null {
  const root = path.join(getDataRoot(), 'public')
  const entry = resolveRootEntry(root, segments, kind)
  if (!entry) return null
  // Links must remain in the same public namespace; never expose sibling models or private data.
  const actual = path.relative(fs.realpathSync(root), entry).split(path.sep)
  const prefixLength = segments[0] === 'ai' ? 2 : 1
  return segments.slice(0, prefixLength).every((part, index) => actual[index] === part) ? entry : null
}

export function resolveRuntimeDataFile(segments: string[]): string | null {
  if (!isRuntimeDataPath(segments)) return null
  requireRuntimeDataRoot()
  return resolvePublicDataEntry(segments)
}

export function resolveStudyChunks(methodId: string, studyId?: string): string {
  if (![methodId, ...(studyId === undefined ? [] : [studyId])].every(part => /^[A-Za-z0-9_-]+$/.test(part))) {
    throw new TypeError('方法或示例编号无效')
  }
  requireRuntimeDataRoot()
  const segments = ['studies', methodId.toLowerCase(), ...(studyId === undefined ? [] : [studyId]), 'chunks']
  const directory = resolvePublicDataEntry(segments, 'directory')
  if (!directory) throw new DataConfigurationError('该方法或示例的外部预计算分片目录缺失')
  return directory
}
