"use client"

import React, { useEffect, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { ArrowUpRight, Loader2, Square } from 'lucide-react'
import { consumeLibraryChatStream } from '@/lib/chat-stream'
import { remarkLibraryAnswerCitations } from '@/lib/library-answer-markdown'
import type { LibraryEvidence } from '@/lib/library-search-types'
import 'katex/dist/katex.min.css'

interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  evidence?: LibraryEvidence[]
  queries?: string[]
  error?: string
  stopped?: boolean
}

function Answer({ message }: { message: Message }) {
  const links = new Set(message.evidence?.map(item => item.href) || [])
  return <>
    {message.content && <div className="chat-answer prose prose-sm prose-slate max-w-none">
      <Markdown remarkPlugins={[remarkGfm, remarkMath, [remarkLibraryAnswerCitations, { evidence: message.evidence || [] }]]} rehypePlugins={[rehypeKatex]}
        components={{
          a: ({ href, children }) => href && links.has(href)
            ? <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
            : <span>{children}</span>,
          img: ({ alt }) => <span>{alt}</span>,
        }}>{message.content}</Markdown>
    </div>}
    {message.stopped && <p className="mt-3 text-xs text-slate-500">已停止生成，已收到的内容和参考资料保留在此。</p>}
    {message.error && <p role="alert" className="mt-3 text-sm text-rose-600">{message.error}</p>}
    {!!message.evidence?.length && <details className="chat-evidence mt-4 border-t border-slate-100 pt-3">
      <summary className="cursor-pointer text-sm font-medium text-blue-700">参考资料 · {message.evidence.length} 段</summary>
      <ol className="mt-3 space-y-3">
        {message.evidence.map(item => <li key={item.id} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <a href={item.href} target="_blank" rel="noopener noreferrer" className="inline-flex items-start gap-2 text-sm font-medium text-blue-700 hover:underline">
            <span className="shrink-0">[{item.citation}]</span><span>{item.title}</span><ArrowUpRight size={14} className="mt-0.5 shrink-0" />
          </a>
          <p className="mt-1 text-xs text-slate-500">{item.slug} · {item.version} · {item.section}</p>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-600">{item.text}</p>
        </li>)}
      </ol>
      {!!message.queries?.length && <p className="mt-3 text-xs leading-5 text-slate-500">本次检索：{message.queries.join('；')}</p>}
    </details>}
  </>
}

export function ChatDialog({ request }: { request: { id: number; question: string } }) {
  const [answer, setAnswer] = useState<Message>({ id: request.id, role: 'assistant', content: '' })
  const [isLoading, setIsLoading] = useState(true)
  const [progress, setProgress] = useState('正在理解问题，准备检索…')
  const [controller, setController] = useState<AbortController | null>(null)
  const [modelLabel, setModelLabel] = useState('DeepSeek V4.1 Flash')

  useEffect(() => {
    const controller = new AbortController()
    setController(controller)
    setAnswer({ id: request.id, role: 'assistant', content: '' })
    setIsLoading(true)
    setProgress('正在理解问题，准备检索…')
    let active = true
    const update = (patch: Partial<Message>) => { if (active) setAnswer(previous => ({ ...previous, ...patch })) }

    fetch('/api/chat', { signal: controller.signal, cache: 'no-store' })
      .then(response => response.ok ? response.json() : null)
      .then(config => { if (active && config?.label) setModelLabel(config.label) })
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
        if (active) { setIsLoading(false); setProgress('') }
      }
    }
    void ask()
    return () => { active = false; controller.abort() }
  }, [request])

  return <section aria-label="AI 问答结果" className="library-chat overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
    <div className="chat-controls flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-3">
      <p className="text-sm font-medium text-slate-700">AI 问答 <span className="ml-2 text-xs font-normal text-slate-400">{modelLabel}</span></p>
      {isLoading && <button type="button" onClick={() => controller?.abort()} className="flex shrink-0 items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 hover:bg-slate-50" aria-label="停止回答"><Square size={13} />停止</button>}
    </div>
    <div className="min-w-0 p-5 sm:p-6">
      <Answer message={answer} />
      {isLoading && <p role="status" className="mt-2 flex items-center gap-2 text-xs leading-5 text-slate-500"><Loader2 size={14} className="shrink-0 animate-spin" />{progress || '正在生成回答…'}</p>}
    </div>
  </section>
}
