import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { consumeLibraryChatStream } from '../../src/lib/chat-stream.ts'
import { loadServerModule } from './helpers/load-server-module.mjs'

const request = { id: 101, question: 'MDM 如何选择偏移量？' }
const evidence = [{ id: 'source-1', citation: 1, slug: '182-046', title: 'MDM', version: '翻译',
  section: '参数估计', text: '公开参考片段', href: '/library/182-046?version=%E7%BF%BB%E8%AF%91#passage-59' }]

function sessionHarness({ unavailable = false, raw = null } = {}) {
  const storage = new Map(raw === null ? [] : [['weibull:library-chat:v1', raw]])
  const window = { sessionStorage: {
    getItem: key => { if (unavailable) throw new Error('storage disabled'); return storage.get(key) ?? null },
    setItem: (key, value) => { if (unavailable) throw new Error('storage disabled'); storage.set(key, value) },
  } }
  const load = () => loadServerModule('src/lib/library-chat-session.ts', {}, { window })
  return { session: load(), reload: load }
}

function chatHarness(session, body) {
  const state = []
  let index = 0, mounted = false, effect, cleanup, posts = 0
  const hooks = { ...React,
    useState: initial => {
      const key = index++
      if (!(key in state)) state[key] = typeof initial === 'function' ? initial() : initial
      return [state[key], value => { state[key] = typeof value === 'function' ? value(state[key]) : value }]
    },
    useEffect: callback => { if (!mounted) effect = callback },
  }
  const module = { exports: {} }
  const imports = {
    react: hooks, 'next/link': ({ children, ...props }) => React.createElement('a', props, children),
    '@/components/library/LibraryDocumentDialog': { LibraryDocumentLink: ({ children, ...props }) => React.createElement('a', props, children) },
    'lucide-react': { Loader2: () => null, Square: () => null },
    '@/components/shared/LibraryMathMarkdown': { LibraryMathMarkdown: ({ children }) => React.createElement('div', null, children) },
    '@/lib/chat-stream': { consumeLibraryChatStream }, '@/lib/library-chat-session': session,
  }
  const file = 'src/components/chat/ChatDialog.tsx'
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: {
    jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true,
  } }).outputText, { module, exports: module.exports, AbortController,
    require: name => { if (!(name in imports)) throw new Error('Unexpected import: ' + name); return imports[name] },
    fetch: async (_url, options = {}) => {
      if (options.method !== 'POST') return { ok: true, json: async () => ({ label: 'Test model' }) }
      posts++
      if (options.signal.aborted) throw options.signal.reason
      return { ok: true, body: body() }
    },
  }, { filename: file })
  const render = () => { index = 0; return module.exports.ChatDialog({ request }) }
  render(); mounted = true; cleanup = effect()
  return { html: () => renderToStaticMarkup(render()), posts: () => posts,
    unmount: () => cleanup?.(), replay: () => { cleanup?.(); cleanup = effect() } }
}

function stream(events, complete = true) {
  return new ReadableStream({ start(controller) {
    for (const event of events) controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(event)}\n\n`))
    if (complete) controller.close()
  } })
}
const settle = () => new Promise(resolve => setImmediate(resolve))

test('same-tab reload restores the question, answer, evidence URL and model without losing search-mode choice', () => {
  const { session, reload } = sessionHarness()
  session.startLibraryChat(request)
  session.cacheLibraryChatAnswer(request.id, { id: request.id, content: '回答 [1]', evidence }, 'DeepSeek')
  const saved = reload().readLibraryChatSession()
  assert.equal(saved.request.question, request.question)
  assert.equal(saved.answer.content, '回答 [1]')
  assert.equal(saved.answer.evidence[0].href, evidence[0].href)
  assert.equal(saved.modelLabel, 'DeepSeek')
  assert.equal(saved.active, true)
  session.setLibraryChatActive(false)
  assert.equal(reload().readLibraryChatSession().active, false)
  assert.equal(reload().readLibraryChatSession().answer.content, '回答 [1]')
})

test('an old request cannot overwrite a newer answer; unavailable or corrupt storage does not break navigation', () => {
  const { session } = sessionHarness({ unavailable: true })
  session.startLibraryChat(request)
  session.startLibraryChat({ id: request.id + 1, question: '新问题' })
  session.cacheLibraryChatAnswer(request.id, { id: request.id, content: '旧回答' }, 'model')
  assert.equal(session.readLibraryChatSession().request.question, '新问题')
  assert.equal(session.readLibraryChatSession().answer, null)
  for (const raw of ['{', '{}', '{"request":{"id":1},"active":true}']) {
    assert.equal(sessionHarness({ raw }).session.readLibraryChatSession(), null)
  }
})

test('a completed answer survives leaving and remounting without a second POST or a false stopped message', async () => {
  const { session, reload } = sessionHarness()
  session.startLibraryChat(request)
  const first = chatHarness(session, () => stream([{ content: '已完成的回答 [1]', evidence }, { done: true }]))
  await settle()
  assert.equal(first.posts(), 1)
  assert.match(first.html(), /已完成的回答/)
  first.unmount()
  assert.notEqual(session.readLibraryChatSession().answer.stopped, true)
  const restored = chatHarness(reload(), () => { throw new Error('Restoring must not call the API') })
  await settle()
  assert.equal(restored.posts(), 0)
  assert.match(restored.html(), /已完成的回答/)
  assert.match(restored.html(), /公开参考片段/)
  assert.doesNotMatch(restored.html(), /已停止生成|target="_blank"/)
  restored.unmount()
})

test('leaving during generation retains received content and citations without restarting the request', async () => {
  const { session, reload } = sessionHarness()
  session.startLibraryChat(request)
  const first = chatHarness(session, () => stream([{ content: '已收到的部分回答', evidence }], false))
  await settle()
  first.unmount()
  await settle()
  const restored = chatHarness(reload(), () => { throw new Error('Partial answers must not be regenerated') })
  assert.equal(restored.posts(), 0)
  assert.match(restored.html(), /已收到的部分回答/)
  assert.match(restored.html(), /已停止生成/)
  assert.match(restored.html(), /passage-59/)
  restored.unmount()
})

test('effect setup-cleanup-setup still generates an answer instead of restoring the abandoned first setup', async () => {
  const { session } = sessionHarness()
  session.startLibraryChat(request)
  const chat = chatHarness(session, () => stream([{ content: '重放后的完整回答' }, { done: true }]))
  chat.replay()
  await settle()
  assert.match(chat.html(), /重放后的完整回答/)
  assert.notEqual(session.readLibraryChatSession().answer.stopped, true)
  chat.unmount()
})
