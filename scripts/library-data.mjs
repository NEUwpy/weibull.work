import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { pathToFileURL } from 'node:url'
import matter from 'gray-matter'

const paperPattern = /^[A-Za-z0-9\u3400-\u9fff][A-Za-z0-9\u3400-\u9fff_-]*-pdf(?:原文|翻译)\.md$/
const assetPattern = /^[A-Za-z0-9\u3400-\u9fff][A-Za-z0-9\u3400-\u9fff_-]*-图片$/
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')

function regularFiles(directory) {
  const files = []
  for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
    const full = path.join(directory, item.name)
    if (item.isSymbolicLink()) throw new Error(`Links are not copied: ${full}`)
    if (item.isDirectory()) files.push(...regularFiles(full))
    else if (item.isFile()) files.push(full)
  }
  return files
}

export function inventory(sourceRoot) {
  const content = path.join(sourceRoot, 'src/content')
  const assets = path.join(sourceRoot, 'public')
  const rows = fs.readdirSync(content).filter(name => paperPattern.test(name)).sort().map(name => ({
    source: path.join(content, name), target: `content/${name}`,
  }))
  for (const name of fs.readdirSync(assets).filter(name => assetPattern.test(name)).sort()) {
    const directory = path.join(assets, name)
    if (fs.lstatSync(directory).isSymbolicLink()) throw new Error(`Links are not copied: ${directory}`)
    if (!fs.statSync(directory).isDirectory()) continue
    for (const file of regularFiles(directory)) {
      rows.push({ source: file, target: `assets/${name}/${path.relative(directory, file).split(path.sep).join('/')}` })
    }
  }
  rows.push({ source: path.join(sourceRoot, 'src/data/references.json'), target: 'references.json' })
  return rows.map(row => ({ ...row, bytes: fs.statSync(row.source).size, sha256: digest(row.source) }))
}

export function exportLibrary(sourceRoot, destination) {
  sourceRoot = path.resolve(sourceRoot)
  if (!path.isAbsolute(destination)) throw new Error('Destination must be an absolute path')
  destination = path.resolve(destination)
  if (fs.existsSync(destination)) throw new Error('Destination exists; export never overwrites a library')
  const rows = inventory(sourceRoot)
  if (!rows.some(row => row.target.startsWith('content/'))) throw new Error('No numbered paper documents found')
  // Complete preflight before creating the destination.
  for (const row of rows) {
    if (!fs.lstatSync(row.source).isFile()) throw new Error(`Source must be a regular file: ${row.source}`)
  }
  fs.mkdirSync(destination)
  fs.mkdirSync(path.join(destination, 'content'))
  fs.mkdirSync(path.join(destination, 'assets'))
  for (const row of rows) {
    const output = path.join(destination, row.target)
    fs.mkdirSync(path.dirname(output), { recursive: true })
    fs.copyFileSync(row.source, output, fs.constants.COPYFILE_EXCL)
    if (digest(output) !== row.sha256) throw new Error(`Copy hash mismatch: ${row.target}`)
  }
  fs.writeFileSync(path.join(destination, 'library.json'), JSON.stringify({ schema_version: 1 }, null, 2) + '\n')
  const manifest = { schema_version: 1, created_at: new Date().toISOString(), source_root: sourceRoot,
    files: rows.map(({ source, ...row }) => row) }
  fs.writeFileSync(path.join(destination, 'export-manifest.json'), JSON.stringify(manifest, null, 2) + '\n')
  return { status: 'passed', root: destination, files: rows.length, bytes: rows.reduce((sum, row) => sum + row.bytes, 0) }
}

export function checkLibrary(root, verifyExport = false) {
  root = path.resolve(root)
  const settings = JSON.parse(fs.readFileSync(path.join(root, 'library.json'), 'utf8'))
  if (settings.schema_version !== 1) throw new Error('Unsupported library schema_version')
  if (!fs.statSync(path.join(root, 'assets')).isDirectory()) throw new Error('Missing assets directory')
  const documents = fs.readdirSync(path.join(root, 'content')).filter(name => paperPattern.test(name))
  const ids = new Set()
  for (const name of documents) {
    const buffer = fs.readFileSync(path.join(root, 'content', name))
    let text
    try { text = new TextDecoder('utf-8', { fatal: true }).decode(buffer) }
    catch { text = new TextDecoder('gbk', { fatal: true }).decode(buffer) }
    const { data } = matter(text)
    if (typeof data.title !== 'string' || !data.title.trim()) throw new Error(`Missing title: ${name}`)
    if (data.tags !== undefined && (!Array.isArray(data.tags) || data.tags.some(tag => typeof tag !== 'string'))) {
      throw new Error(`tags must be a string array: ${name}`)
    }
    ids.add(name.replace(/-pdf(?:原文|翻译)\.md$/, ''))
  }
  const refs = JSON.parse(fs.readFileSync(path.join(root, 'references.json'), 'utf8'))
  if (!refs || Array.isArray(refs) || typeof refs !== 'object') throw new Error('Invalid references map')
  let referenceCount = 0
  for (const [source, entries] of Object.entries(refs)) {
    if (!entries || Array.isArray(entries) || typeof entries !== 'object') throw new Error(`Invalid references: ${source}`)
    for (const target of Object.values(entries)) {
      if (typeof target !== 'string' || !ids.has(target)) throw new Error(`Unknown reference target: ${source} -> ${target}`)
      referenceCount++
    }
  }
  let verifiedFiles = 0
  if (verifyExport) {
    const manifest = JSON.parse(fs.readFileSync(path.join(root, 'export-manifest.json'), 'utf8'))
    for (const row of manifest.files) {
      const file = path.resolve(root, row.target)
      const relative = path.relative(root, file)
      if (relative.startsWith('..') || path.isAbsolute(relative)) throw new Error('Manifest path escapes library')
      if (digest(file) !== row.sha256) throw new Error(`Export hash mismatch: ${row.target}`)
      verifiedFiles++
    }
  }
  return { status: 'passed', root, documents: documents.length, papers: ids.size, referenceCount, verifiedFiles }
}

/** Import a numbered batch without rewriting any existing paper or asset. */
export function importPapers(source, root) {
  source = path.resolve(source)
  root = path.resolve(root)
  checkLibrary(root)
  const rows = []
  for (const name of fs.readdirSync(source).filter(name => paperPattern.test(name)).sort()) {
    const file = path.join(source, name)
    if (!fs.lstatSync(file).isFile()) throw new Error(`Regular documents required: ${file}`)
    const { data } = matter(fs.readFileSync(file, 'utf8'))
    if (typeof data.title !== 'string' || !data.title.trim()) throw new Error(`Missing title: ${name}`)
    if (data.tags !== undefined && (!Array.isArray(data.tags) || data.tags.some(tag => typeof tag !== 'string'))) {
      throw new Error(`tags must be a string array: ${name}`)
    }
    rows.push({ source: file, target: path.join(root, 'content', name) })
  }
  if (!rows.length) throw new Error('No numbered documents in source directory')
  const importedIds = new Set(rows.map(row => path.basename(row.source).replace(/-pdf(?:原文|翻译)\.md$/, '')))
  for (const id of importedIds) {
    const directory = path.join(source, `${id}-图片`)
    if (!fs.existsSync(directory)) continue
    if (fs.lstatSync(directory).isSymbolicLink()) throw new Error(`Links are not copied: ${directory}`)
    for (const file of regularFiles(directory)) {
      rows.push({ source: file, target: path.join(root, 'assets', `${id}-图片`, path.relative(directory, file)) })
    }
  }
  const pending = []
  for (const row of rows) {
    let ancestor = path.dirname(row.target)
    while (!fs.existsSync(ancestor)) ancestor = path.dirname(ancestor)
    const relative = path.relative(fs.realpathSync(root), fs.realpathSync(ancestor))
    if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
      throw new Error(`Target directory escapes library: ${row.target}`)
    }
    if (fs.existsSync(row.target)) {
      if (digest(row.source) !== digest(row.target)) throw new Error(`Conflict; nothing imported: ${row.target}`)
    } else pending.push(row)
  }
  // Conflicts are checked for the entire batch before any writes.
  for (const row of pending) {
    fs.mkdirSync(path.dirname(row.target), { recursive: true })
    fs.copyFileSync(row.source, row.target, fs.constants.COPYFILE_EXCL)
    if (digest(row.source) !== digest(row.target)) throw new Error(`Copy hash mismatch: ${row.target}`)
  }
  return { status: 'passed', root, importedFiles: pending.length, unchangedFiles: rows.length - pending.length }
}

export function main(args) {
  const [command, ...rest] = args
  const value = name => {
    const index = rest.indexOf(name)
    if (index < 0 || !rest[index + 1] || rest[index + 1].startsWith('--')) throw new Error(`Missing ${name}`)
    return rest[index + 1]
  }
  if (command === 'export') return exportLibrary(value('--source-root'), value('--destination'))
  if (command === 'check') return checkLibrary(value('--root'), rest.includes('--verify-export'))
  if (command === 'import') return importPapers(value('--source-dir'), value('--root'))
  throw new Error('Usage: library-data.mjs export --source-root REPO --destination NEW_ABSOLUTE_PATH | check --root LIBRARY [--verify-export] | import --source-dir NUMBERED_BATCH --root LIBRARY')
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  try { console.log(JSON.stringify(main(process.argv.slice(2)), null, 2)) }
  catch (error) { console.error(error.message); process.exitCode = 1 }
}
