import fs from 'node:fs/promises'
import path from 'node:path'
import { randomUUID } from 'node:crypto'

const MAX_TOTAL_BYTES = 50 * 1024 * 1024
const MAX_FILE_BYTES = 5 * 1024 * 1024
const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000
let writes = Promise.resolve()

export function libraryChatLogDirectory(): string {
  return process.env.WEIBULL_CHAT_LOG_DIR?.trim() || path.join(
    process.env.WEIBULL_DATA_ROOT?.trim() || path.resolve(process.cwd(), '../weibull-data'), 'logs', 'library-chat')
}

async function appendRecord(directory: string, record: Record<string, unknown>) {
  let line = JSON.stringify(record).replace(/sk-[a-z0-9_-]{8,}/gi, '[REDACTED]') + '\n'
  const key = process.env.DEEPSEEK_API_KEY?.trim()
  if (key) line = line.replaceAll(key, '[REDACTED]')
  const bytes = Buffer.byteLength(line)
  if (bytes > MAX_FILE_BYTES) return
  await fs.mkdir(directory, { recursive: true })
  const names = (await fs.readdir(directory)).filter(name => /^\d{4}-\d{2}-\d{2}\.\d{4}\.jsonl$/.test(name)).sort()
  const files = []
  for (const name of names) {
    const file = path.join(directory, name)
    const stat = await fs.stat(file)
    if (Date.now() - stat.mtimeMs > MAX_AGE_MS) await fs.unlink(file)
    else files.push({ name, file, size: stat.size })
  }
  const day = new Date().toISOString().slice(0, 10)
  const last = files.filter(file => file.name.startsWith(day + '.')).at(-1)
  const sequence = last ? +last.name.slice(11, 15) : 0
  const filename = last && last.size + bytes <= MAX_FILE_BYTES ? last.name
    : `${day}.${String(sequence + 1).padStart(4, '0')}.jsonl`
  let total = files.reduce((sum, file) => sum + file.size, 0)
  while (files.length && total + bytes > MAX_TOTAL_BYTES) {
    const oldest = files.shift()!
    await fs.unlink(oldest.file)
    total -= oldest.size
  }
  await fs.appendFile(path.join(directory, filename), line, 'utf8')
}

/** Compact, local-only records. Callers pass classifications and source IDs, never API payloads. */
export function createLibraryChatLog() {
  const requestId = randomUUID()
  const started = Date.now()
  const directory = libraryChatLogDirectory()
  return {
    record(event: string, details: Record<string, unknown> = {}) {
      const record = { ...details, requestId, event, time: new Date().toISOString(), elapsedMs: Date.now() - started }
      writes = writes.then(() => appendRecord(directory, record)).catch(() => {
        console.error('[library-chat-log] Unable to write local diagnostic log')
      })
    },
    flush: () => writes,
  }
}
