import type { LibraryEvidence } from './library-search-types'

export interface LibraryChatEvent {
  stage?: 'expanding' | 'searching' | 'screening' | 'answering'
  message?: string
  content?: string
  evidence?: LibraryEvidence[]
  queries?: string[]
  error?: string
  done?: boolean
}

/** Decode SSE frames across network and UTF-8 boundaries, including a final undelimited frame. */
export async function consumeLibraryChatStream(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: LibraryChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let completed = false
  const abort = () => { void reader.cancel().catch(() => {}) }
  signal?.addEventListener('abort', abort, { once: true })

  function dispatch(frame: string) {
    const data = frame.split(/\r?\n/).filter(line => line.startsWith('data:'))
      .map(line => line.slice(5).replace(/^ /, '')).join('\n')
    if (!data) return
    if (data === '[DONE]') { completed = true; return }
    let event: LibraryChatEvent
    try { event = JSON.parse(data) } catch { throw new Error('回答数据不完整，请重试。') }
    if (!event || typeof event !== 'object' || Array.isArray(event)) throw new Error('回答数据格式异常，请重试。')
    if (event.error) throw new Error(event.error)
    onEvent(event)
    if (event.done) completed = true
  }

  try {
    while (!completed) {
      signal?.throwIfAborted()
      const { value, done } = await reader.read()
      signal?.throwIfAborted()
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
      let boundary: RegExpExecArray | null
      while (!completed && (boundary = /\r?\n\r?\n/.exec(buffer))) {
        dispatch(buffer.slice(0, boundary.index))
        buffer = buffer.slice(boundary.index + boundary[0].length)
      }
      if (done) {
        if (!completed && buffer.trim()) dispatch(buffer)
        if (!completed) throw new Error('回答连接中断，已保留收到的内容，可重试。')
        break
      }
    }
  } finally {
    signal?.removeEventListener('abort', abort)
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}
