"use client"

import React, { useEffect, useState } from 'react'
import { LibraryDocumentLink as Link } from '@/components/library/LibraryDocumentDialog'
import { LibraryMathMarkdown } from '@/components/shared/LibraryMathMarkdown'
import { Loader2, Square } from 'lucide-react'
import { consumeLibraryChatStream } from '@/lib/chat-stream'
import { cacheLibraryChatAnswer, readLibraryChatSession, type LibraryChatAnswer, type LibraryChatRequest } from '@/lib/library-chat-session'

function Answer({ message }: { message: LibraryChatAnswer }) {
  return <>
    {message.content && <div className="chat-answer prose prose-sm prose-slate max-w-none">
      <LibraryMathMarkdown evidence={message.evidence}>{message.content}</LibraryMathMarkdown>
    </div>}
    {message.stopped && <p className="mt-3 text-xs text-slate-500">已停止生成，已收到的内容和参考资料保留在此。</p>}
    {message.error && <p role="alert" className="mt-3 text-sm text-rose-600">{message.error}</p>}
    {!!message.evidence?.length && <details className="chat-evidence mt-4 border-t border-slate-100 pt-3">
      <summary className="cursor-pointer text-sm font-medium text-blue-700">参考资料 · {message.evidence.length} 段</summary>
      <ol className="mt-3 space-y-3">
        {message.evidence.map(item => <li key={item.id} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <Link href={item.href} className="inline-flex items-start gap-2 text-sm font-medium text-blue-700 hover:underline">
            <span className="shrink-0">[{item.citation}]</span><span>{item.title}</span>
          </Link>
          <p className="mt-1 text-xs text-slate-500">{item.slug} · {item.version} · {item.section}</p>
          <LibraryMathMarkdown className="mt-2 text-sm leading-6 text-slate-600 [&_p]:my-2">{item.text}</LibraryMathMarkdown>
        </li>)}
      </ol>
      {!!message.queries?.length && <p className="mt-3 text-xs leading-5 text-slate-500">本次检索：{message.queries.join('；')}</p>}
    </details>}
  </>
}

export function ChatDialog({ request }: { request: LibraryChatRequest }) {
  const [restored] = useState(() => {
    const saved = readLibraryChatSession()
    return saved?.request.id === request.id ? saved : null
  })
  const [answer, setAnswer] = useState<LibraryChatAnswer>(restored?.answer || { id: request.id, content: '' })
  const [isLoading, setIsLoading] = useState(!restored?.answer)
  const [progress, setProgress] = useState('正在理解问题，准备检索…')
  const [controller, setController] = useState<AbortController | null>(null)
  const [modelLabel, setModelLabel] = useState(restored?.modelLabel || 'DeepSeek V4.1 Flash')

  useEffect(() => {
    if (restored?.answer) return
    const controller = new AbortController()
    setController(controller)
    let latest: LibraryChatAnswer = { id: request.id, content: '' }
    let label = restored?.modelLabel || 'DeepSeek V4.1 Flash'
    let active = true
    let finished = false
    const update = (patch: Partial<LibraryChatAnswer>, pending = true) => {
      if (!active) return
      latest = { ...latest, ...patch }
      cacheLibraryChatAnswer(request.id, { ...latest, stopped: pending || latest.stopped }, label)
      if (active) setAnswer(latest)
    }
    setAnswer(latest)
    setIsLoading(true)
    setProgress('正在理解问题，准备检索…')

    fetch('/api/chat', { signal: controller.signal, cache: 'no-store' })
      .then(response => response.ok ? response.json() : null)
      .then(config => { if (active && config?.label) { label = config.label; setModelLabel(label) } })
      .catch(() => {})

    async function ask() {
      try {
        const response = await fetch('/api/chat', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: request.question }), signal: controller.signal,
        })
        if (!response.ok) {
          const data = await response.json().catch(() => null)
          throw new Error(data?.error || '问答服务暂时不可用，请稍后重试。')
        }
        if (!response.body) throw new Error('未收到回答，请重试。')
        let content = ''
        await consumeLibraryChatStream(response.body, event => {
          if (!active || controller.signal.aborted) return
          if (event.message) setProgress(event.message)
          if (event.evidence) update({ evidence: event.evidence, queries: event.queries })
          if (event.content) { content += event.content; update({ content }) }
        }, controller.signal)
      } catch (cause) {
        if (controller.signal.aborted) update({ stopped: true })
        else update({ error: cause instanceof Error ? cause.message : '问答连接失败，请稍后重试。' })
      } finally {
        if (active) { finished = true; update({}, false); setIsLoading(false); setProgress('') }
      }
    }
    void ask()
    return () => {
      if (!finished) cacheLibraryChatAnswer(request.id, { ...latest, stopped: true }, label)
      active = false
      controller.abort()
    }
  }, [request])

  return <section aria-label="AI 问答结果" className="library-chat overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
    <div className="chat-controls flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-3">
      <p className="text-sm font-medium text-slate-700">AI 问答 <span className="ml-2 text-xs font-normal text-slate-400">{modelLabel}</span></p>
      {isLoading && <button type="button" onClick={() => controller?.abort()} className="flex shrink-0 items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 hover:bg-slate-50" aria-label="停止回答"><Square size={13} />停止</button>}
    </div>
    <div className="min-w-0 p-5 sm:p-6">
      <p className="mb-5 border-b border-slate-100 pb-4 text-sm leading-6 text-slate-700">{request.question}</p>
      <Answer message={answer} />
      {isLoading && <p role="status" className="mt-2 flex items-center gap-2 text-xs leading-5 text-slate-500"><Loader2 size={14} className="shrink-0 animate-spin" />{progress || '正在生成回答…'}</p>}
    </div>
  </section>
}
