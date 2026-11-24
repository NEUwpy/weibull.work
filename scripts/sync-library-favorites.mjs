import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { registerHooks } from 'node:module'
import { extname } from 'node:path'
import { parseArgs } from 'node:util'

const source = new URL('../src/lib/', import.meta.url).href
const maxBytes = 16 * 1024 * 1024

// Resolve the application's relative TypeScript imports when running outside Next.js.
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (context.parentURL?.startsWith(source) && specifier.startsWith('.') && !extname(specifier)) {
      return nextResolve(`${specifier}.ts`, context)
    }
    return nextResolve(specifier, context)
  },
})

const { readLibraryFavoriteSync, applyLibraryFavoriteSync, receiveLibraryFavoriteSync } =
  await import('../src/lib/server/library-favorites-sync.ts')

function requireSuccess(result, message) {
  if (result.error) throw result.error
  if (result.status !== 0) throw new Error(message)
}

function send(ssh, container, sudo, snapshot, dryRun) {
  const input = JSON.stringify({ ...snapshot, dryRun })
  if (Buffer.byteLength(input) > maxBytes) throw new Error('收藏快照超过同步大小限制。')
  const remote = `${sudo ? 'sudo -n ' : ''}docker exec -i -w /app ${container} node --experimental-strip-types --disable-warning=MODULE_TYPELESS_PACKAGE_JSON scripts/sync-library-favorites.mjs --receive`
  const result = spawnSync('ssh', ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '--', ssh, remote], {
    input, encoding: 'utf8', maxBuffer: maxBytes, stdio: ['pipe', 'pipe', 'inherit'],
  })
  requireSuccess(result, 'NAS 收藏同步未完成。')
  try { return JSON.parse(result.stdout) }
  catch { throw new Error('无法读取 NAS 收藏同步响应。') }
}

async function receive() {
  const chunks = []
  let length = 0
  for await (const chunk of process.stdin) {
    length += chunk.length
    if (length > maxBytes) throw new Error('收藏快照超过同步大小限制。')
    chunks.push(chunk)
  }
  const result = await receiveLibraryFavoriteSync(JSON.parse(Buffer.concat(chunks).toString('utf8')))
  process.stdout.write(JSON.stringify(result))
}

async function main() {
  const { values } = parseArgs({ options: {
    ssh: { type: 'string' }, container: { type: 'string' }, sudo: { type: 'boolean' },
    'dry-run': { type: 'boolean' }, push: { type: 'boolean' }, receive: { type: 'boolean' },
  } })
  if (values.receive) {
    if (Object.keys(values).length !== 1) throw new Error('接收模式不接受本机参数。')
    return receive()
  }
  const { ssh, container = 'weibull-frontend', sudo, push } = values
  const dryRun = Boolean(values['dry-run'])
  if (!ssh || !/^[a-z0-9_][a-z0-9_.@:\[\]-]*$/i.test(ssh) || !/^[a-z0-9][a-z0-9_.-]*$/i.test(container)) {
    throw new Error('请用 --ssh 指定 NAS 的 SSH 主机或别名，并检查 --container。')
  }
  if (dryRun && push) throw new Error('预览时请省略 --push。')

  for (const file of ['.env.local', '.env']) {
    if (existsSync(file)) process.loadEnvFile(file)
  }
  const peer = `${ssh}/${container}`
  let snapshot = await readLibraryFavoriteSync(peer)
  if (push) {
    send(ssh, container, sudo, snapshot, true)
    requireSuccess(spawnSync('git', ['push'], { stdio: 'inherit' }), 'Git 推送失败。')
    snapshot = await readLibraryFavoriteSync(peer)
  }
  const result = send(ssh, container, sudo, snapshot, dryRun)
  const folders = dryRun ? result.folders : await applyLibraryFavoriteSync(peer, snapshot, result)
  const papers = folders.reduce((sum, folder) => sum + folder.paperIds.length, 0)
  console.log(`${dryRun ? '预览' : '收藏已同步'}，${folders.length} 个文献组，${papers} 条收藏记录。`)
}

main().catch(error => {
  console.error(error.message)
  process.exitCode = 1
})
