import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import GithubSlugger from 'github-slugger'
import matter from 'gray-matter'
import remarkGfm from 'remark-gfm'
import remarkParse from 'remark-parse'
import { unified } from 'unified'
import { parseUserManualFeatures } from '../src/lib/markdown.ts'
import { METHOD_SECTIONS } from '../src/lib/method-navigation.ts'
import { parseUpdatePlan } from '../src/lib/update-plan.ts'

const root = fileURLToPath(new URL('../', import.meta.url))
const parser = unified().use(remarkParse).use(remarkGfm)
const markdownFiles = new Map()
const localScheme = /^[a-z][a-z\d+.-]*:|^\/\//i
const currentDirs = ['docs/建设规范', 'docs/development', 'docs/data', 'docs/library']
const diagnostics = []

function read(file) {
  return fs.readFileSync(path.resolve(root, file), 'utf8')
}

function walk(node, visit) {
  visit(node)
  for (const child of node.children ?? []) walk(child, visit)
}

function headingText(node) {
  return node.value ?? (node.children ?? []).map(headingText).join('')
}

function parseMarkdown(file) {
  if (!markdownFiles.has(file)) {
    const tree = parser.parse(read(file))
    const slugger = new GithubSlugger()
    const anchors = new Set()
    walk(tree, node => {
      if (node.type === 'heading') anchors.add(slugger.slug(headingText(node)))
    })
    markdownFiles.set(file, { tree, anchors })
  }
  return markdownFiles.get(file)
}

function indexMarkdownFiles(dir) {
  return fs.readdirSync(path.join(root, dir), { withFileTypes: true }).flatMap(entry => {
    const file = path.posix.join(dir, entry.name)
    if (entry.isDirectory()) return indexMarkdownFiles(file)
    return entry.isFile() && entry.name.endsWith('.md') ? [file] : []
  })
}

function checkLinks(file) {
  const { tree } = parseMarkdown(file)
  walk(tree, node => {
    if (!['link', 'image', 'definition'].includes(node.type)) return
    if (localScheme.test(node.url) || node.url.startsWith('/')) return
    const [location, fragment] = node.url.split('#', 2)
    const line = node.position.start.line
    try {
      const target = location
        ? path.resolve(root, path.dirname(file), decodeURIComponent(location.split('?', 1)[0]))
        : path.resolve(root, file)
      const relative = path.relative(root, target)
      if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
        diagnostics.push({ file, line, message: `相对链接超出项目：${node.url}` })
      } else if (!fs.existsSync(target)) {
        diagnostics.push({ file, line, message: `链接目标不存在：${node.url}` })
      } else if (fragment && target.endsWith('.md') && !parseMarkdown(relative).anchors.has(decodeURIComponent(fragment))) {
        diagnostics.push({ file, line, message: `链接对应的标题不存在：${node.url}` })
      }
    } catch (error) {
      diagnostics.push({ file, line, message: `无法检查链接 ${node.url}（${error.message}）` })
    }
  })
}

try {
  const files = [
    'AGENTS.md',
    'README.md',
    ...fs.readdirSync(root).filter(file => /^0[1-7]-.*\.md$/.test(file)),
    'docs/文档索引.md',
    'docs/AI辅助三参数威布尔参数估计重构当前路线图.md',
    'coworker/README.md',
    'python/studies/common/README.md',
    'scripts/README.md',
    'src/app/help/README.md',
    'src/components/calculator/README.md',
    ...currentDirs.flatMap(indexMarkdownFiles),
  ]
  for (const file of files) checkLinks(file)

  const planFile = '04-目标与待办.md'
  const plan = parseUpdatePlan(read(planFile))
  diagnostics.push(...plan.diagnostics.map(issue => ({ file: planFile, ...issue })))

  const manualFile = '07-用户手册.md'
  const manual = parseUserManualFeatures(matter(read(manualFile)).content)
  diagnostics.push(...manual.diagnostics.map(issue => ({ file: manualFile, ...issue })))

  // These routes use section keys in URLs and distinct tab values in the UI.
  const methods = JSON.parse(read('src/data/methods.json'))
  const methodIds = new Set(methods.flatMap(category => (category.children ?? []).map(method => method.id)))
  walk(parser.parse(manual.body), node => {
    if (node.type !== 'link' && node.type !== 'definition') return
    const pathname = node.url.split(/[?#]/, 1)[0]
    const match = /^\/methods\/([^/]+)(?:\/([^/]+))?\/?$/.exec(pathname)
    if (!match) return
    const [, methodId, section] = match
    const knownSection = !section || section === 'applicability' || Object.hasOwn(METHOD_SECTIONS, section)
    if (!methodIds.has(methodId) || !knownSection) {
      diagnostics.push({ file: manualFile, message: `公开手册中的方法链接不存在：${node.url}` })
    }
  })

  for (const issue of diagnostics) {
    console.error(`${issue.file}${issue.line ? `:${issue.line}` : ''} ${issue.message}`)
  }
  if (diagnostics.length) process.exitCode = 1
  else console.log(`docs: 已检查 ${files.length} 份现行文档、${plan.groups.reduce((n, group) => n + group.tasks.length, 0)} 条更新计划和公开用户手册。`)
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error))
  process.exitCode = 1
}
