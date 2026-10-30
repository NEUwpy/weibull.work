"use client"

import React, { useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { ArrowUpRight, BookOpen, Loader2, Minus, Plus, Send, Square } from 'lucide-react'
import { consumeLibraryChatStream } from '@/lib/chat-stream'
import { remarkLibraryAnswerCitations } from '@/lib/library-answer-markdown'
import type { LibraryEvidence } from '@/lib/library-search-types'
import { cn } from '@/lib/utils'
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

export function ChatDialog() {
  const [isExpanded, setIsExpanded] = useState(false)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [progress, setProgress] = useState('')
  const [configured, setConfigured] = useState<boolean | null>(null)
  const [modelLabel, setModelLabel] = useState('DeepSeek V4.1 Flash')
  const nextId = useRef(0)
  const request = useRef<AbortController | null>(null)
  const messagesEnd = useRef<HTMLDivElement>(null)

  useEffect(() => () => request.current?.abort(), [])
  useEffect(() => {
    if (!isExpanded) return
    const controller = new AbortController()
    fetch('/api/chat', { signal: controller.signal, cache: 'no-store' })
      .then(response => response.ok ? response.json() : null)
      .then(config => { if (config && !controller.signal.aborted) { setConfigured(config.configured); setModelLabel(config.label || 'DeepSeek V4.1 Flash') } })
      .catch(() => {})
    return () => controller.abort()
  }, [isExpanded])

  useEffect(() => {
    const container = messagesEnd.current?.parentElement
    if (container && container.scrollHeight - container.scrollTop - container.clientHeight < 180) {
      container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' })
    }
  }, [messages, progress])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const question = input.trim()
    if (!question || isLoading || question.length > 2000) return
    const answerId = ++nextId.current
    const controller = new AbortController()
    request.current = controller
    setMessages(previous => [...previous, { id: -answerId, role: 'user', content: question }, { id: answerId, role: 'assistant', content: '' }])
    setInput('')
    setIsLoading(true)
    setProgress('正在理解问题，准备检索…')
    const update = (patch: Partial<Message>) => setMessages(previous => previous.map(message => message.id === answerId ? { ...message, ...patch } : message))
    try {
      const response = await fetch('/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }), signal: controller.signal,
      })
      if (!response.ok) {
        const data = await response.json().catch(() => null)
        throw new Error(data?.error || '问答服务暂时不可用，请稍后重试。')
      }
      if (!response.body) throw new Error('未收到回答，请重试。')
      let content = ''
      await consumeLibraryChatStream(response.body, event => {
        if (controller.signal.aborted) return
        if (event.message) setProgress(event.message)
        if (event.evidence) update({ evidence: event.evidence, queries: event.queries })
        if (event.content) { content += event.content; update({ content }) }
      }, controller.signal)
    } catch (cause) {
      if (controller.signal.aborted) update({ stopped: true })
      else update({ error: cause instanceof Error ? cause.message : '问答连接失败，请稍后重试。' })
    } finally {
      if (request.current === controller) {
        request.current = null
        setIsLoading(false)
        setProgress('')
      }
    }
  }

  return <section className="library-chat overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
    <button type="button" onClick={() => setIsExpanded(value => !value)} aria-label={isExpanded ? '收起 AI 文献助手' : '展开 AI 文献助手'} aria-expanded={isExpanded}
      className="flex w-full items-center justify-between gap-4 bg-gradient-to-r from-blue-50 to-emerald-50 px-5 py-5 text-left">
      <span className="flex min-w-0 items-center gap-3">
        <span className="rounded-xl bg-blue-600 p-2.5 text-white"><BookOpen size={19} /></span>
        <span><span className="block font-semibold text-slate-900">AI 文献助手</span><span className="mt-1 block text-xs leading-5 text-slate-500">检索库内资料，带来源回答</span></span>
      </span>
      {isExpanded ? <Minus size={18} className="shrink-0 text-slate-500" /> : <Plus size={18} className="shrink-0 text-slate-500" />}
    </button>
    {isExpanded && <div>
      <div className="chat-controls flex flex-wrap items-center justify-between gap-2 border-y border-slate-100 px-5 py-3 text-xs text-slate-500">
        <span>{modelLabel}</span><span>依据当前图书馆的已上架资料</span>
      </div>
      <div className="chat-messages max-h-[640px] min-h-[180px] overflow-y-auto bg-slate-50 p-4 sm:p-5">
        {!messages.length && <div className="py-7 text-center text-slate-500">
          <p className="text-sm">输入一个问题，先查找相关段落，再结合资料回答。</p>
          <p className="mt-2 text-xs leading-6 text-slate-400">例如：三参数 Weibull 分布的位置参数估计有哪些困难？</p>
        </div>}
        <div className="space-y-5">{messages.map(message => <div key={message.id} className={cn('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}>
          <div className={cn('min-w-0 rounded-2xl px-4 py-3', message.role === 'user' ? 'max-w-[90%] bg-blue-600 text-white' : 'w-full border border-slate-200 bg-white text-slate-700')}>
            {message.role === 'user' ? <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p> : <Answer message={message} />}
            {isLoading && message.id === nextId.current && <p role="status" className="mt-2 flex items-center gap-2 text-xs leading-5 text-slate-500"><Loader2 size={14} className="shrink-0 animate-spin" />{progress || '正在生成回答…'}</p>}
          </div>
        </div>)}</div>
        <div ref={messagesEnd} />
      </div>
      {configured === false && <p className="border-t border-slate-100 px-5 py-3 text-sm text-amber-700">AI 问答暂未配置，正文检索仍可使用。</p>}
      <form onSubmit={submit} className="flex items-end gap-3 border-t border-slate-100 bg-white p-4 sm:p-5">
        <textarea aria-label="向文献助手提问" placeholder="输入问题，可粘贴一小段话…" rows={2} maxLength={2000} value={input}
          onChange={event => setInput(event.target.value)} disabled={isLoading}
          className="min-w-0 flex-1 resize-y rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 disabled:opacity-60" />
        {isLoading ? <button type="button" onClick={() => request.current?.abort()} className="flex shrink-0 items-center gap-2 rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-600 hover:bg-slate-50" aria-label="停止回答"><Square size={15} />停止</button>
          : <button type="submit" disabled={!input.trim() || configured === false} className="flex shrink-0 items-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400" aria-label="发送问题"><Send size={16} /><span className="hidden sm:inline">提问</span></button>}
      </form>
    </div>}
  </section>
}
