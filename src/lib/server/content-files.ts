import fs from 'fs'
import path from 'path'

/** Resolve a known Markdown file without allowing paths or external symlinks. */
export function resolveContentFile(directory: string, fileName: string): string | null {
  if (!/^[A-Za-z0-9\u3400-\u9fff][A-Za-z0-9\u3400-\u9fff_-]*\.md$/.test(fileName)) return null
  if (!fs.existsSync(directory)) return null
  if (!fs.readdirSync(directory).includes(fileName)) return null

  const root = fs.realpathSync(directory)
  const candidate = fs.realpathSync(path.join(root, fileName))
  const relative = path.relative(root, candidate)
  if (relative.startsWith(`..${path.sep}`) || relative === '..' || path.isAbsolute(relative)) return null
  return fs.statSync(candidate).isFile() ? candidate : null
}

export function isContentSlug(slug: string): boolean {
  return /^[A-Za-z0-9\u3400-\u9fff][A-Za-z0-9\u3400-\u9fff_-]*$/.test(slug)
}
