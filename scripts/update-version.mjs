import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../', import.meta.url))
const changelog = '08-更新日志.md'
const versionFiles = [changelog, 'package.json', 'package-lock.json']
const areas = [
  ['项目文档', /\.md$/i],
  ['图书馆与账号', /library|literature|journal|favorites|sms|\/auth\//i],
  ['案例数据库', /case|dataset/i],
  ['方法与计算', /^python\/|method|calculator|calculation|workflow/i],
  ['构建与维护', /^scripts\/|^package|docker|^\.env|config\./i],
]

function git(args, env = process.env) {
  return execFileSync('git', args, { cwd: root, env, encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 })
}

function readFiles(read) {
  return Object.fromEntries(versionFiles.map(file => [file, read(file)]))
}

function versionHeading(markdown) {
  const heading = markdown.match(/^## v[^\r\n]+/m)?.[0] ?? ''
  const match = /^## v(\d+)\.(\d+)\.(\d+)-(\d{6}) \((\d{4}-\d{2}-\d{2})\)$/.exec(heading)
  if (!match || match[4] !== match[5].slice(2).replaceAll('-', '')) {
    throw new Error(`${changelog} 首个版本标题的编号与日期格式不匹配。`)
  }
  const [, major, minor, patch, suffix] = match
  return { heading, number: `${major}.${minor}.${patch}-${suffix}`, major: +major, minor: +minor, patch: +patch }
}

function parseVersionFiles(files) {
  const version = versionHeading(files[changelog])
  const pkg = JSON.parse(files['package.json'])
  const lock = JSON.parse(files['package-lock.json'])
  if (pkg.version !== version.number || lock.version !== version.number || lock.packages?.['']?.version !== version.number) {
    throw new Error(`${changelog}、package.json 和 package-lock.json 的版本不一致。`)
  }
  return { version, pkg, lock }
}

function describeChanges(files) {
  const counts = new Map()
  for (const file of files) {
    const area = areas.find(([, pattern]) => pattern.test(file))?.[0] ?? '网站与其他代码'
    counts.set(area, (counts.get(area) ?? 0) + 1)
  }
  return [...counts].map(([area, count]) => `${area}（${count} 个文件）`).join('、')
}

function onMain() {
  return git(['branch', '--show-current']).trim() === 'main'
}

function checkCommit(ref) {
  const commit = git(['rev-parse', '--verify', '--end-of-options', `${ref}^{commit}`]).trim()
  const headers = git(['cat-file', 'commit', commit]).split('\n\n', 1)[0]
  const tree = headers.match(/^tree (\S+)$/m)[1]
  const parent = headers.match(/^parent (\S+)$/m)?.[1]
  const currentFiles = readFiles(file => git(['show', `${commit}:${file}`]))
  const current = parseVersionFiles(currentFiles).version
  const label = commit.slice(0, 12)

  if (parent && git(['rev-parse', '--verify', `${parent}^{tree}`]).trim() !== tree) {
    const parentFiles = readFiles(file => git(['show', `${parent}:${file}`]))
    const previous = parseVersionFiles(parentFiles).version
    const patch = current.minor === previous.minor && current.patch === previous.patch + 1
    const minor = current.minor === previous.minor + 1 && current.patch === 0
    if (current.major !== previous.major || (!patch && !minor)) {
      throw new Error(`${label} 的版本未按规则递增：v${previous.number} → v${current.number}。`)
    }
    const previousHeadings = [...parentFiles[changelog].matchAll(/^## (v\S+)/gm)]
    const newLog = currentFiles[changelog]
    const headings = [...newLog.matchAll(/^## (v\S+)/gm)]
    const keptVersions = headings.length === previousHeadings.length + 1
      && previousHeadings.every((heading, index) => heading[1] === headings[index + 1][1])
    const added = newLog.slice(headings[0].index, headings[1]?.index)
    if (!keptVersions || !/^[-*] \S/m.test(added)) {
      throw new Error(`${label} 的更新日志须保留原有记录的版本号，并在顶部新增一份带说明的版本记录。`)
    }
  }
  console.log(`version: ${label} v${current.number}`)
}

function installHooks() {
  const hookDir = path.resolve(root, git(['rev-parse', '--git-path', 'hooks']).trim())
  const repoHooks = path.join(git(['rev-parse', '--path-format=absolute', '--git-common-dir']).trim(), 'hooks')
  if (hookDir !== path.resolve(repoHooks)) {
    throw new Error('本仓配置了其他 Git 钩子目录，请在现有提交钩子中调用 node scripts/update-version.mjs --commit。')
  }

  const hooks = [
    ['pre-commit', '--commit'],
    ['pre-merge-commit', '--merge'],
  ].map(([name, mode]) => ({
    file: path.join(hookDir, name),
    content: `#!/bin/sh\nif [ -f scripts/update-version.mjs ]; then\n  exec node scripts/update-version.mjs ${mode}\nfi\n`,
  }))
  for (const { file, content } of hooks) {
    if (fs.existsSync(file) && fs.readFileSync(file, 'utf8') !== content) {
      throw new Error(`检测到自定义 Git 钩子 ${path.basename(file)}，请将覆盖此位置的更新步骤接入现有钩子。`)
    }
  }
  fs.mkdirSync(hookDir, { recursive: true })
  for (const { file, content } of hooks) {
    if (!fs.existsSync(file)) fs.writeFileSync(file, content, { mode: 0o755, flag: 'wx' })
  }
  console.log('已启用本仓 main 提交的自动版本记录。')
}

function updateForCommit() {
  if (!onMain() || !git(['diff', '--cached', '--name-only', '-z'])) return

  const staged = readFiles(file => git(['show', `:${file}`]))
  const { version, pkg, lock } = parseVersionFiles(staged)
  const parentVersion = versionHeading(git(['show', `HEAD:${changelog}`]))
  if (version.number !== parentVersion.number) {
    if (!staged[changelog].includes(parentVersion.heading)) {
      throw new Error('暂存的版本记录缺少当前 Git 版本的历史条目。')
    }
    console.log(`已同步待提交的版本 v${version.number}。`)
    return
  }

  const configured = git(['config', '--default', 'patch', '--get', 'weibull.versionBump']).trim()
  if (configured !== 'patch' && configured !== 'minor') {
    throw new Error('weibull.versionBump 可设为 patch 或 minor。')
  }

  const working = readFiles(file => fs.readFileSync(path.join(root, file), 'utf8'))
  const partialIndex = process.env.GIT_INDEX_FILE
  // A path-limited git commit prepares both its commit index and index.lock.
  const savedIndexEnv = partialIndex && /^next-index-\d+\.lock$/.test(path.basename(partialIndex))
    ? { ...process.env, GIT_INDEX_FILE: path.join(path.dirname(partialIndex), 'index.lock') }
    : undefined
  for (const file of versionFiles) {
    if (working[file].replace(/\r\n/g, '\n') !== staged[file].replace(/\r\n/g, '\n') ||
        (savedIndexEnv && git(['show', `:${file}`], savedIndexEnv) !== staged[file])) {
      throw new Error(`${file} 的暂存区与工作区不同。请处理该文件的改动后重试。`)
    }
  }

  const minor = configured === 'minor' ? version.minor + 1 : version.minor
  const patch = configured === 'minor' ? 0 : version.patch + 1
  const date = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai', dateStyle: 'short' }).format(new Date())
  const next = `${version.major}.${minor}.${patch}-${date.slice(2).replaceAll('-', '')}`
  const note = git(['config', '--default', '', '--get', 'weibull.versionNote']).trim().replace(/\s+/g, ' ')
  const base = git(['log', '-1', '--format=%H', 'HEAD', '--', changelog]).trim()
  const changed = git(['diff', '--cached', base, '--name-only', '--no-renames', '-z']).split('\0').filter(Boolean)
  const entry = [
    `## v${next} (${date})`,
    '',
    ...(note ? [`- ${note}`] : []),
    `- 变更范围：${describeChanges(changed)}。`,
  ].join('\n')
  pkg.version = lock.version = lock.packages[''].version = next
  const updates = {
    [changelog]: staged[changelog].replace(version.heading, () => `${entry}\n\n${version.heading}`),
    'package.json': `${JSON.stringify(pkg, null, 2)}\n`,
    'package-lock.json': `${JSON.stringify(lock, null, 2)}\n`,
  }

  try {
    for (const file of versionFiles) fs.writeFileSync(path.join(root, file), updates[file])
    git(['add', '--', ...versionFiles])
    if (savedIndexEnv) git(['add', '--', ...versionFiles], savedIndexEnv)
  } catch (error) {
    for (const file of versionFiles) {
      const filename = path.join(root, file)
      if (fs.readFileSync(filename, 'utf8') === updates[file]) fs.writeFileSync(filename, working[file])
    }
    throw error
  }
  console.log(`已生成 v${next} 并暂存版本记录。`)
}

try {
  switch (process.argv[2]) {
    case '--install':
      installHooks()
      break
    case '--commit':
      updateForCommit()
      break
    case '--merge':
      // git merge writes its commit from a tree calculated before pre-merge-commit.
      if (onMain()) throw new Error('合并结果已准备好。执行 git commit 将合并结果和版本记录一并提交。')
      break
    case '--check': {
      const { version } = parseVersionFiles(readFiles(file => fs.readFileSync(path.join(root, file), 'utf8')))
      console.log(`version: v${version.number}`)
      break
    }
    case '--check-main':
      if (fs.existsSync(path.join(root, '.git')) && onMain()) checkCommit('HEAD')
      break
    case '--check-commit':
      checkCommit(process.argv[3] ?? 'HEAD')
      break
    default:
      throw new Error('用法：node scripts/update-version.mjs --check | --check-main | --check-commit [ref] | --install | --commit | --merge')
  }
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error))
  process.exitCode = 1
}
