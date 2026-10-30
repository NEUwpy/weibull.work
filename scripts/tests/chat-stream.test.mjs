import test from 'node:test'
import assert from 'node:assert/strict'
import { consumeLibraryChatStream } from '../../src/lib/chat-stream.ts'

function bytesStream(text, size = 1) {
  const bytes = new TextEncoder().encode(text)
  return new ReadableStream({
    start(controller) {
      for (let offset = 0; offset < bytes.length; offset += size) controller.enqueue(bytes.slice(offset, offset + size))
      controller.close()
    },
  })
}

test('chat SSE preserves Chinese UTF-8, CRLF frames, multiline data and final source evidence', async () => {
  const frames = ': keepalive\r\n\r\ndata: {"content":\r\ndata: "位置参数"}\r\n\r\n'
    + 'data: {"content":"估计。"}\n\n'
    + 'data: {"evidence":[{"id":"source-1","citation":1}],"queries":["位置参数"]}\n\n'
    + 'data: {"done":true}\n\n'
  const events = []
  await consumeLibraryChatStream(bytesStream(frames), event => events.push(event))
  assert.equal(events.map(event => event.content || '').join(''), '位置参数估计。')
  assert.equal(events.find(event => event.evidence).evidence[0].citation, 1)
  assert.deepEqual(events.find(event => event.queries).queries, ['位置参数'])
})

test('chat SSE accepts a final undelimited completion marker', async () => {
  const events = []
  await consumeLibraryChatStream(bytesStream('data: {"content":"answer"}\n\ndata: [DONE]', 7), event => events.push(event))
  assert.equal(events[0].content, 'answer')
})

test('an interrupted response raises an error after delivering its partial answer', async () => {
  const events = []
  await assert.rejects(consumeLibraryChatStream(bytesStream('data: {"content":"保留这段回答"}\n\n'), event => events.push(event)), /连接中断/)
  assert.equal(events[0].content, '保留这段回答')
})

test('malformed frames and server errors are surfaced instead of silently losing content', async () => {
  await assert.rejects(consumeLibraryChatStream(bytesStream('data: {broken}\n\n'), () => {}), /数据不完整/)
  await assert.rejects(consumeLibraryChatStream(bytesStream('data: {"error":"额度不足"}\n\n'), () => {}), /额度不足/)
})

test('cancel stops a pending stream while retaining already delivered evidence', async () => {
  const abort = new AbortController()
  let cancelled = false
  const events = []
  const stream = new ReadableStream({
    start(controller) { controller.enqueue(new TextEncoder().encode('data: {"evidence":[{"id":"source-2","citation":2}]}\n\n')) },
    cancel() { cancelled = true },
  })
  await assert.rejects(consumeLibraryChatStream(stream, event => { events.push(event); abort.abort() }, abort.signal), error => error.name === 'AbortError')
  assert.equal(cancelled, true)
  assert.equal(events[0].evidence[0].citation, 2)
})
