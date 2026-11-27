import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const imageFavoritesPath = '/app-state/library-favorites'
const sourceId = /^[\w\u3400-\u9fff-]+$/u
const sha = bytes => createHash('sha256').update(bytes).digest('hex')
const json = bytes => JSON.parse(bytes.toString('utf8').replace(/^\uFEFF/, ''))
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value)
const inside = (base, file) => {
  const relative = path.relative(base, file)
  return relative !== '..' && !relative.startsWith('..' + path.sep) && !path.isAbsolute(relative)
}

class CheckError extends Error {}
function check(condition, message) {
  if (!condition) throw new CheckError(message)
}

function containerPath(value) {
  check(typeof value === 'string' && value.startsWith('/') && !value.includes('\\')
    && !value.includes('\0') && !value.split('/').includes('..'), '需要有效的容器内绝对路径')
  return path.posix.normalize(value).replace(/\/$/, '') || '/'
}

function mountFor(volumes, value) {
  const target = containerPath(value)
  return volumes.filter(mount => {
    const prefix = containerPath(mount.target)
    return prefix === '/' || target === prefix || target.startsWith(prefix + '/')
  }).sort((a, b) => b.target.length - a.target.length)[0]
}

export function mappedFile(volumes, value, directory = false) {
  const target = containerPath(value)
  const mount = mountFor(volumes, target)
  check(mount?.type === 'bind' && mount.read_only === true && path.isAbsolute(mount.source),
    '资料路径需要明确的只读宿主挂载')
  const suffix = path.posix.relative(containerPath(mount.target), target)
  const base = fs.realpathSync(mount.source)
  const nominal = path.resolve(base, ...suffix.split('/'))
  const real = fs.realpathSync(nominal)
  check(inside(base, real), '资料路径超出挂载目录')
  check(directory ? fs.statSync(real).isDirectory() : fs.statSync(real).isFile(),
    directory ? '应为资料目录' : '应为资料文件')
  fs.accessSync(real, fs.constants.R_OK)
  return real
}

function selectedBodies(root, selected, omittedPaths) {
  const counts = new Map()
  const skip = new Set(['历史', '_archive', 'archive', 'history', '待回收', '已经移动了', '190_待处理与日志', 'images'])
  function walk(directory) {
    for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
      const itemPath = path.join(directory, item.name)
      if (item.isDirectory() && !item.name.startsWith('.') && !item.name.endsWith('-图片')
        && !skip.has(item.name.toLowerCase()) && !omittedPaths.has(itemPath)) walk(itemPath)
      if (!item.isFile()) continue
      const match = /^(.*)-pdf(原文|翻译)\.md$/u.exec(item.name)
      if (!match || !selected.has(match[1])) continue
      fs.accessSync(itemPath, fs.constants.R_OK)
      const paper = counts.get(match[1]) ?? { directory, versions: new Set() }
      check(paper.directory === directory && !paper.versions.has(match[2]), `选用文献存在多处正文：${match[1]}`)
      paper.versions.add(match[2])
      counts.set(match[1], paper)
    }
  }
  walk(root)
  return counts
}

export function checkReleaseData(frontend, entries, report) {
  const mounts = frontend.volumes ?? []
  const env = frontend.environment ?? {}
  const data = () => containerPath(env.WEIBULL_DATA_ROOT)
  const locate = (file, directory) => mappedFile(mounts, file, directory)
  const read = file => fs.readFileSync(locate(file))
  const scoped = (root, relative) => {
    check(typeof relative === 'string' && relative.split('/').every(part => part && part !== '.' && part !== '..')
      && !relative.includes('\\'), '登记文件的相对路径无效')
    return path.posix.join(root, relative)
  }

  report('外部数据根', () => { locate(data(), true) })
  report('文献书票与正文', () => {
    const root = containerPath(env.WEIBULL_LIBRARY_ROOT)
    const bookplate = json(read(path.posix.join(root, 'library.json')))
    const references = json(read(path.posix.join(root, 'references.json')))
    check(object(references) && Object.values(references).every(links => object(links)
      && Object.values(links).every(id => typeof id === 'string' && sourceId.test(id))), '公开引用文件格式无效')
    const selected = new Set()
    if (bookplate?.schema_version === 1) {
      const content = locate(path.posix.join(root, 'content'), true)
      locate(path.posix.join(root, 'assets'), true)
      for (const file of fs.readdirSync(content, { withFileTypes: true })) {
        if (!file.isFile()) continue
        const match = /^(.*)-pdf(?:原文|翻译)\.md$/u.exec(file.name)
        if (match && sourceId.test(match[1])) {
          locate(path.posix.join(root, 'content', file.name))
          selected.add(match[1])
        }
      }
    } else {
      check(bookplate?.schema_version === 2 && bookplate.mode === 'source'
        && Array.isArray(bookplate.sources) && bookplate.sources.length, '文献书票版本或源目录无效')
      for (const source of bookplate.sources) {
        check(Array.isArray(source?.papers) && (source.layout === undefined || source.layout === 'v1'), '文献选用清单无效')
        const sourceRoot = containerPath(source.root)
        const contentRoot = source.layout === 'v1' ? path.posix.join(sourceRoot, 'content') : sourceRoot
        const hostRoot = locate(contentRoot, true)
        if (source.layout === 'v1') locate(path.posix.join(sourceRoot, 'assets'), true)
        const ids = new Set(source.papers.map(value => {
          const id = typeof value === 'string' ? value : value?.id
          check(typeof id === 'string' && sourceId.test(id) && !selected.has(id), '选用文献编号无效或重复')
          selected.add(id)
          return id
        }))
        // A nested mount hides the covered directory in the container.
        const nested = mounts.map(m => containerPath(m.target)).filter(target => target.startsWith(contentRoot.replace(/\/$/, '') + '/'))
        const skippedChildren = (target, host) => new Set(nested
          .filter(child => child.startsWith(target.replace(/\/$/, '') + '/'))
          .map(child => path.join(host, path.posix.relative(target, child))))
        const bodies = selectedBodies(hostRoot, ids, skippedChildren(contentRoot, hostRoot))
        for (const target of nested) {
          const mountedRoot = locate(target, true)
          for (const [id, paper] of selectedBodies(mountedRoot, ids, skippedChildren(target, mountedRoot))) {
            check(!bodies.has(id), `选用文献存在多处正文：${id}`)
            bodies.set(id, paper)
          }
        }
        const missing = [...ids].filter(id => !bodies.has(id))
        check(!missing.length, `缺少所选正文：${missing.join('、')}`)
      }
      if (bookplate.reference_index !== undefined) {
        const entry = bookplate.reference_index
        check(typeof entry?.root === 'string' && !entry.root.includes('\\') && !/^[a-z]:/i.test(entry.root), '引用索引根配置无效')
        const refRoot = containerPath(path.posix.resolve(root, entry.root))
        locate(refRoot, true)
        const index = json(read(scoped(refRoot, entry.file)))
        check(index?.schema_version === 1 && containerPath(index.root) === refRoot, '引用索引内记录的根目录与 NAS 配置不一致')
      }
    }
    check(selected.size > 0, '书票未选入正文')
    return `${selected.size} 项`
  })

  report('公开案例', () => {
    const root = path.posix.join(data(), 'cases')
    const layout = json(read(path.posix.join(root, 'catalog.json')))
    const index = json(read(path.posix.join(root, 'index.json')))
    check(layout?.schema_version === 1 && Array.isArray(layout.groups)
      && index?.schema_version === 1 && Array.isArray(index.records), '案例目录或索引格式无效')
    const files = new Map(index.records.map(record => [record.id, record.file]))
    const ids = layout.groups.flatMap(group => group.members.map(member => member.id))
    for (const id of ids) {
      check(typeof id === 'string' && sourceId.test(id), '案例成员编号无效')
      const file = typeof files.get(id) === 'string' ? files.get(id).replace(/^records\//, '') : ''
      check(/^[\w\u3400-\u9fff.-]+\.json$/u.test(file), `案例未登记：${id}`)
      const record = json(read(path.posix.join(root, 'records', file)))
      check(record?.id === id, `案例记录身份不一致：${id}`)
    }
    return `${ids.length} 项`
  })

  for (const entry of entries) {
    const id = typeof entry?.id === 'string' && sourceId.test(entry.id) ? entry.id : ''
    report(id ? `工作簿 ${id}` : '工作簿登记', () => {
      check(id && typeof entry.directory === 'string' && entry.directory.startsWith('monte-carlo/'), '工作簿登记格式无效')
      const root = scoped(data(), entry.directory)
      const raw = read(path.posix.join(root, 'manifest.json'))
      check(sha(raw) === entry.manifestSha256, 'manifest.json 哈希不匹配')
      const manifest = json(raw)
      check(manifest?.schemaVersion === 1 && manifest.id === id && object(manifest.files)
        && manifest.files['workbook.json']?.role === 'view'
        && manifest.files['workbook.xlsx']?.role === 'workbook', '工作簿清单身份或文件角色不匹配')
      for (const [filename, expected] of Object.entries(manifest.files)) {
        const bytes = read(scoped(root, filename))
        check(bytes.length === expected?.bytes && sha(bytes) === expected.sha256,
          filename === 'workbook.json' || filename === 'workbook.xlsx' ? `${filename} 哈希或大小不匹配` : '登记附件的哈希或大小不匹配')
        if (filename === 'workbook.json') {
          const view = json(bytes)
          check(view.id === id && view.sha256 === entry.workbookSha256, '工作簿视图与候选索引不匹配')
        }
        if (filename === 'workbook.xlsx') check(sha(bytes) === entry.workbookSha256, '原 Excel 与候选索引不匹配')
      }
      if (entry.mdmProcess) {
        const match = typeof entry.mdmProcess.recordId === 'string' && /^mdm-([a-f0-9]{64})$/.exec(entry.mdmProcess.recordId)
        check(match, '计算记录编号无效')
        const record = read(path.posix.join(data(), 'calculation-records', 'mdm', match[1] + '.json'))
        check(sha(record) === match[1], '计算记录哈希不匹配')
      }
    })
  }
}

function command(bin, args, label) {
  const result = spawnSync(bin, args, {
    encoding: 'utf8', maxBuffer: 16 * 1024 * 1024, timeout: 30_000, windowsHide: true,
    env: { ...process.env, GIT_OPTIONAL_LOCKS: '0' },
  })
  check(result.status === 0, label)
  return result.stdout
}

function argumentsFor(argv) {
  const aliases = { '--compose-file': '-f', '-f': '-f', '--project-name': '-p', '-p': '-p', '--env-file': '--env-file' }
  const compose = []
  let candidate
  let firstInstall = false
  for (let i = 0; i < argv.length; i++) {
    const option = argv[i]
    if (option === '--first-install') { firstInstall = true; continue }
    check(option === '--candidate' || Object.hasOwn(aliases, option), '存在未识别的参数')
    const value = argv[++i]
    check(value && !value.startsWith('-'), '参数缺少值')
    if (option === '--candidate') candidate = value
    else compose.push(aliases[option], value)
  }
  check(candidate && compose.includes('-f'), '需要候选 Git 版本和实际使用的 Compose 文件')
  return { candidate, firstInstall, compose }
}

export function checkFavorites(compose, frontend, firstInstall, docker) {
  const target = containerPath(frontend.environment?.WEIBULL_FAVORITES_DIR ?? imageFavoritesPath)
  const mount = mountFor(frontend.volumes ?? [], target)
  check(mount?.type === 'volume' && !mount.read_only && containerPath(mount.target) === target, '收藏目录缺少直接可写的命名卷')
  const name = compose.volumes?.[mount.source]?.name
  check(typeof name === 'string' && /^[a-zA-Z0-9_.-]+$/.test(name), 'Compose 未解析收藏卷名称')
  const containerName = frontend.container_name ?? `${compose.name}-frontend-1`
  check(typeof containerName === 'string' && /^[a-zA-Z0-9_.-]+$/.test(containerName), '无法确认前端容器名称')
  const containers = docker(['container', 'ls', '-a', '--format', '{{.Names}}'], '无法读取 Docker 容器清单').trim().split(/\s+/)
  if (firstInstall) {
    check(!containers.includes(containerName), '发现已有前端，按更新方式检查原收藏卷')
    const volumes = docker(['volume', 'ls', '--format', '{{.Name}}'], '无法读取 Docker 卷清单').trim().split(/\s+/)
    return volumes.includes(name) ? `已有卷 ${name}，待首次连接` : `计划创建 ${name}`
  }
  check(containers.includes(containerName), '找不到当前前端。新站点可显式使用 --first-install')
  const existing = json(docker(['container', 'inspect', '--format', '{{json .Mounts}}', containerName], '无法读取现有前端挂载'))
  const actual = Array.isArray(existing) && existing.find(item => item.Destination === target)
  check(actual?.Type === 'volume' && actual.Name === name && actual.RW === true, '现有前端与候选配置的收藏卷或可写挂载不一致')
  docker(['volume', 'inspect', '--format', '{{.Name}}', name], '无法读取配置所指的收藏卷')
  return name
}

function main(argv) {
  let args
  try { args = argumentsFor(argv) }
  catch (error) {
    console.error(error.message)
    console.error('用法：node scripts/check-nas-release.mjs --candidate <commit-or-tag> -f <compose> [-f <overlay>] [-p <project>] [--env-file <file>] [--first-install]')
    return 2
  }
  let failed = false
  function report(label, run, planned = false) {
    try {
      const detail = run()
      console.log(`[${planned ? '计划' : '通过'}] ${label}${detail ? ` · ${detail}` : ''}`)
      return true
    } catch (error) {
      failed = true
      const note = error instanceof CheckError ? error.message
        : error?.code === 'ENOENT' ? '缺少所需文件或挂载' : '文件无法读取或格式无效'
      console.error(`[失败] ${label} · ${note}`)
      return false
    }
  }
  const git = (args, label) => command('git', args, label)
  const docker = (args, label) => command('docker', args, label)
  let oid, entries, compose, frontend
  if (!report('候选 Git 版本', () => {
    oid = git(['rev-parse', '--verify', '--end-of-options', args.candidate + '^{commit}'], '无法解析候选提交').trim()
    check(oid === git(['rev-parse', 'HEAD'], '无法读取当前检出').trim(), '当前 HEAD 与候选提交不一致')
    check(!git(['status', '--porcelain'], '无法检查候选工作区').trim(), '候选检出含未提交文件')
    command(process.execPath, ['scripts/update-version.mjs', '--check-commit', oid], '候选版本记录检查未通过')
    const pkg = json(git(['show', oid + ':package.json'], '无法读取候选包版本'))
    const catalog = json(git(['show', oid + ':src/content/monte-carlo/research00.json'], '无法读取候选工作簿索引'))
    check(Array.isArray(catalog?.entries) && catalog.entries.length, '候选工作簿索引为空或格式无效')
    entries = catalog.entries
    return `${oid} · v${/^\d+\.\d+\.\d+-\d{6}$/.test(pkg.version) ? pkg.version : '未知'}`
  })) return 1
  if (!report('Compose 生效配置', () => {
    const endpoint = process.env.DOCKER_CONTEXT || !process.env.DOCKER_HOST
      ? json(docker(['context', 'inspect', '--format', '{{json .Endpoints.docker.Host}}'], '无法确认 Docker 主机'))
      : process.env.DOCKER_HOST
    check(typeof endpoint === 'string' && /^(?:unix|npipe):\/\//.test(endpoint), '请在 Docker 宿主机或本地 Docker 环境运行')
    compose = json(docker(['compose', ...args.compose, 'config', '--format', 'json'], 'Compose 配置解析失败，请在宿主机核对文件和变量'))
    frontend = compose?.services?.frontend
    check(typeof compose?.name === 'string' && /^[a-z0-9_-]+$/.test(compose.name) && object(frontend)
      && object(compose.services?.backend), '配置缺少项目名或前后端服务')
    return compose.name
  })) return 1
  checkReleaseData(frontend, entries, report)
  report('收藏卷', () => checkFavorites(compose, frontend, args.firstInstall, docker), args.firstInstall)
  console.log('[待现场验收] 容器实际运行权限、首次访问、登录及收藏写入')
  return failed ? 1 : 0
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) process.exitCode = main(process.argv.slice(2))
