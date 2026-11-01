import fs from 'fs'
import path from 'path'

export class DataConfigurationError extends Error {
  constructor(message: string) {
    super(`外部数据配置错误：${message}`)
    this.name = 'DataConfigurationError'
  }
}

/** Resolve relative to the software working directory, including a relocated release. */
export function getDataRoot(): string {
  return path.resolve(process.cwd(), process.env.WEIBULL_DATA_ROOT?.trim() || '../weibull-data')
}

function contained(root: string, file: string): boolean {
  const relative = path.relative(root, file)
  return relative !== '..' && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative)
}

/** Inventory-based lookup: retain exact names and reject escape through links. */
export function resolveRootEntry(root: string, segments: string[], kind: 'file' | 'directory' = 'file'): string | null {
  if (!segments.length || segments.some(part => !part || part === '.' || part === '..' || /[/\\:\x00-\x1f\x7f]/.test(part))) return null
  try {
    const realRoot = fs.realpathSync(root)
    let current = realRoot
    for (const part of segments) {
      if (!fs.readdirSync(current).includes(part)) return null
      current = fs.realpathSync(path.join(current, part))
      if (!contained(realRoot, current)) return null
    }
    const stat = fs.statSync(current)
    return (kind === 'file' ? stat.isFile() : stat.isDirectory()) ? current : null
  } catch (error) {
    if (['ENOENT', 'ENOTDIR', 'ELOOP'].includes((error as NodeJS.ErrnoException).code || '')) return null
    throw error
  }
}

export function resolveDataEntry(segments: string[], kind: 'file' | 'directory' = 'file'): string | null {
  return resolveRootEntry(getDataRoot(), segments, kind)
}
