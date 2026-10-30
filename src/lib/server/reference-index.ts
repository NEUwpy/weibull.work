import fs from 'fs'
import path from 'path'
import { createHash } from 'crypto'
import type { SourceIndex, SourcePaper } from './source-library'

export interface ReferenceIndexLocation { root: string; file: string }

const sha256 = (file: string) => createHash('sha256').update(fs.readFileSync(file)).digest('hex')

/** A source index is derived local data; only selected papers become public links. */
export function readSourceReferenceIndex(location: ReferenceIndexLocation, paper: SourcePaper,
  type: string, selection: SourceIndex): Record<string, string> {
  try {
    const root = fs.realpathSync(location.root)
    const indexFile = fs.realpathSync(path.resolve(root, location.file))
    const relativeIndex = path.relative(root, indexFile)
    if (relativeIndex.startsWith('..') || path.isAbsolute(relativeIndex)) return {}
    const index = JSON.parse(fs.readFileSync(indexFile, 'utf8'))
    if (index.schema_version !== 1 || fs.realpathSync(index.root) !== root) return {}
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
