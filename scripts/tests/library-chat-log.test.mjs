import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { loadServerModule } from './helpers/load-server-module.mjs'

async function withLog(run) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'weibull-chat-log-'))
  const saved = process.env.WEIBULL_CHAT_LOG_DIR
  process.env.WEIBULL_CHAT_LOG_DIR = root
  const errors = []
  const module = loadServerModule('src/lib/server/library-chat-log.ts', {}, { console: { error: value => errors.push(value) } })
  try { await run({ root, ...module, errors }) }
  finally {
    if (saved === undefined) delete process.env.WEIBULL_CHAT_LOG_DIR
    else process.env.WEIBULL_CHAT_LOG_DIR = saved
    fs.rmSync(root, { recursive: true, force: true })
  }
}

test('local request logs preserve concurrent JSON records and redact credential-shaped text', () => withLog(async ({ root, createLibraryChatLog }) => {
  const first = createLibraryChatLog(), second = createLibraryChatLog()
  first.record('start', { question: '比较 MDM 和 MLE。sk-1234567890abcdef' })
  second.record('start', { question: '位置参数是什么意思？' })
  first.record('finish', { outcome: 'completed', answerChars: 200 })
  await first.flush()
  const text = fs.readdirSync(root).map(name => fs.readFileSync(path.join(root, name), 'utf8')).join('')
  const rows = text.trim().split('\n').map(line => JSON.parse(line))
  assert.equal(rows.length, 3)
  assert.equal(new Set(rows.map(row => row.requestId)).size, 2)
  assert.ok(rows.every(row => row.time && row.elapsedMs >= 0))
  assert.match(text, /\[REDACTED\]/)
  assert.doesNotMatch(text, /sk-1234567890abcdef/)
}))

test('logs expire after 30 days, rotate at 5MiB and stay within the 50MiB total cap', () => withLog(async ({ root, createLibraryChatLog }) => {
  const old = path.join(root, '2000-01-01.0001.jsonl')
  fs.writeFileSync(old, 'expired')
  fs.utimesSync(old, new Date(0), new Date(0))
  fs.writeFileSync(path.join(root, 'unrelated.txt'), 'keep')
  const day = new Date().toISOString().slice(0, 10)
  for (let index = 1; index <= 10; index++) {
    const file = path.join(root, `${day}.${String(index).padStart(4, '0')}.jsonl`)
    fs.writeFileSync(file, '')
    fs.truncateSync(file, 5 * 1024 * 1024)
  }
  const log = createLibraryChatLog()
  log.record('start', { question: '测试保留限制' })
  await log.flush()
  assert.equal(fs.existsSync(old), false)
  assert.equal(fs.existsSync(path.join(root, `${day}.0001.jsonl`)), false)
  assert.equal(fs.existsSync(path.join(root, `${day}.0011.jsonl`)), true)
  assert.equal(fs.readFileSync(path.join(root, 'unrelated.txt'), 'utf8'), 'keep')
  const files = fs.readdirSync(root).filter(name => name.endsWith('.jsonl'))
  assert.ok(files.reduce((sum, name) => sum + fs.statSync(path.join(root, name)).size, 0) <= 50 * 1024 * 1024)
}))

test('unwritable logs do not interrupt an answer or expose raw errors', () => withLog(async ({ root, createLibraryChatLog, errors }) => {
  const file = path.join(root, 'occupied')
  fs.writeFileSync(file, '')
  process.env.WEIBULL_CHAT_LOG_DIR = file
  const log = createLibraryChatLog()
  log.record('start')
  await assert.doesNotReject(log.flush())
  assert.equal(errors.length, 1)
  assert.ok(!errors[0].includes(root))
}))
