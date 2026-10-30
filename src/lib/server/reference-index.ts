import fs from 'fs'
import path from 'path'
import { createHash } from 'crypto'
import type { SourceIndex, SourcePaper } from './source-library'

export interface ReferenceIndexLocation { root: string; file: string }

const sha256 = (file: string) => createHash('sha256').update(fs.readFileSync(file)).digest('hex')

function loadIndex(location: ReferenceIndexLocation) {
  const root = fs.realpathSync(location.root)
  const file = fs.realpathSync(path.resolve(root, location.file))
  const relative = path.relative(root, file)
  if (relative.startsWith('..') || path.isAbsolute(relative)) throw new Error('引用索引越界')
  const index = JSON.parse(fs.readFileSync(file, 'utf8'))
  if (index.schema_version !== 1 || fs.realpathSync(index.root) !== root) throw new Error('引用索引来源无效')
  return { root, index }
}

/** Only a selected, current public document may contribute its public DOI. */
export function readSourceSearchDois(location: ReferenceIndexLocation, selection: SourceIndex): Map<string, string> {
  const result = new Map<string, string>()
  try {
    const { root, index } = loadIndex(location)
    const conflicts = new Set<string>()
    for (const target of Object.values(index.targets ?? {}) as any[]) {
      const selected = selection.get(target.id)
      if (!selected || typeof target.doi !== 'string' || !target.doi) continue
      if (path.relative(root, selected.directory).split(path.sep).join('/') !== target.directory) continue
      const file = path.resolve(root, target.path)
      if ((file !== selected.original && file !== selected.translation) || sha256(file) !== target.sha256) continue
      if (result.has(selected.id) && result.get(selected.id) !== target.doi) conflicts.add(selected.id)
      result.set(selected.id, target.doi)
    }
    for (const id of Array.from(conflicts)) result.delete(id)
  } catch { return new Map() }
  return result
}

/** A source index is derived local data; only selected papers become public links. */
export function readSourceReferenceIndex(location: ReferenceIndexLocation, paper: SourcePaper,
  type: string, selection: SourceIndex): Record<string, string> {
  try {
    const { root, index } = loadIndex(location)
    const sourceFile = type === '原文' ? paper.original : paper.translation
    if (!sourceFile) return {}
    const relative = path.relative(root, sourceFile).split(path.sep).join('/')
    const document = index.documents?.[relative]
    if (!document || document.sha256 !== sha256(sourceFile)) return {}
    const result: Record<string, string> = {}
    for (const [number, link] of Object.entries(document.links ?? {}) as [string, any][]) {
      if (!/^(?:\d+|entry-\d+)$/.test(number)) continue
      const target = index.targets?.[link.target]
      const selected = target && selection.get(target.id)
      if (!selected || path.relative(root, selected.directory).split(path.sep).join('/') !== target.directory) continue
      const file = path.resolve(root, target.path)
      // The file must be a selected public version, never a private note or neighbour.
      if (file !== selected.original && file !== selected.translation) continue
      if (sha256(file) === target.sha256) result[number] = selected.id
    }
    return result
  } catch { return {} } // An invalid/stale index must never turn into a guessed link.
}
