'use client'

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { ArrowUp, CornerDownRight, Loader2, Quote, Square, X } from 'lucide-react'
import { LibraryChatAnswerView } from '@/components/chat'
import { consumeLibraryChatStream } from '@/lib/chat-stream'
import { MAX_ARTICLE_CHAT_HISTORY, MAX_ARTICLE_QUOTES, MAX_ARTICLE_QUOTE_CHARS, type LibraryArticleQuote } from '@/lib/library-article-chat'
import type { LibraryChatAnswer } from '@/lib/library-chat-session'
import { libraryAuthClient } from '@/lib/library-auth-client'
import type { LibraryVersion } from '@/lib/library-search-types'
import articleQuestions from '@/content/prompts/article-questions.json'
import './article-chat.css'

interface Turn {
  question: string
  quotes: LibraryArticleQuote[]
  answer: LibraryChatAnswer
}

export function LibraryArticleChat({ slug, version, onLogin, onCitation, contents, controlsId, leftOpen, rightOpen, setRightOpen, children }: {
  slug: string
  version: LibraryVersion
  onLogin: () => void
  onCitation: (href: string) => void
  contents?: ReactNode
  controlsId: string
  leftOpen: boolean
  rightOpen: boolean
  setRightOpen: (open: boolean) => void
  children: ReactNode
}) {
  const panelId = controlsId + '-chat'
  const tocId = controlsId + '-toc'
  const shell = useRef<HTMLDivElement>(null)
  const composer = useRef<HTMLTextAreaElement>(null)
  const messages = useRef<HTMLDivElement>(null)
  const chatPanel = useRef<HTMLElement>(null)
  const active = useRef<AbortController | null>(null)
  const lastSelection = useRef<LibraryArticleQuote | null>(null)
  const nextId = useRef(0)
  const [selection, setSelection] = useState<{ quote: LibraryArticleQuote; left: number; top: number } | null>(null)
  const [quotes, setQuotes] = useState<LibraryArticleQuote[]>([])
  const [question, setQuestion] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [progress, setProgress] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => () => active.current?.abort(), [])
  useEffect(() => {
    if (!rightOpen) return
    let frame = 0
    const fitPanel = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const panel = chatPanel.current
        if (!panel) return
        if (window.matchMedia('(max-width: 900px)').matches) {
          panel.style.removeProperty('--article-chat-height')
          return
        }
        const scroller = shell.current?.closest('[data-library-dialog-scroll]')
        const bottom = Math.min(window.innerHeight, scroller?.getBoundingClientRect().bottom ?? window.innerHeight)
        const available = bottom - panel.getBoundingClientRect().top - 16
        panel.style.setProperty('--article-chat-height', Math.max(0, available) + 'px')
      })
    }
    const observer = new ResizeObserver(fitPanel)
    if (shell.current) observer.observe(shell.current)
    const intro = shell.current?.closest('.library-reader')?.querySelector('.library-article-intro')
    if (intro) observer.observe(intro)
    fitPanel()
    window.addEventListener('scroll', fitPanel, true)
    window.addEventListener('resize', fitPanel)
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      window.removeEventListener('scroll', fitPanel, true)
      window.removeEventListener('resize', fitPanel)
    }
  }, [rightOpen])
  useEffect(() => {
    let frame = 0
    function refresh() {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const selected = window.getSelection()
        const root = shell.current?.querySelector('[data-library-selection]')
        if (!root || !selected?.rangeCount || selected.isCollapsed || !root.contains(selected.anchorNode) || !root.contains(selected.focusNode)) {
          setSelection(null)
          return
        }
        const range = selected.getRangeAt(0)
        const rect = range.getBoundingClientRect()
        const parent = root.closest('[data-library-dialog-scroll]')?.getBoundingClientRect()
        const top = parent?.top || 0
        const bottom = Math.min(window.innerHeight, parent?.bottom || window.innerHeight)
        const text = selected.toString().trim()
        if (!text || rect.bottom < top || rect.top > bottom) { setSelection(null); return }
        const start = range.startContainer
        const element = start instanceof Element ? start : start.parentElement
        const anchor = element?.closest('[id^="passage-"], [id^="ref-"]')?.id
        const quote = { text, version, anchor: anchor && /^(passage-|ref-)\d+$/.test(anchor) ? anchor : undefined }
        lastSelection.current = quote
        setSelection({ quote, left: Math.max(8, Math.min(rect.left, window.innerWidth - 144)),
          top: rect.bottom + 48 < bottom ? rect.bottom + 6 : Math.max(top + 6, rect.top - 45) })
      })
    }
    document.addEventListener('selectionchange', refresh)
    window.addEventListener('resize', refresh)
    window.addEventListener('scroll', refresh, true)
    return () => {
      cancelAnimationFrame(frame)
      document.removeEventListener('selectionchange', refresh)
      window.removeEventListener('resize', refresh)
      window.removeEventListener('scroll', refresh, true)
    }
  }, [version])

  function attach(quote: LibraryArticleQuote) {
    setRightOpen(true)
    setNotice('')
    if (quote.text.length > MAX_ARTICLE_QUOTE_CHARS) {
      setNotice('选段过长，请缩小选中范围，或直接对本篇提问。')
      return
    }
    if (quotes.length >= MAX_ARTICLE_QUOTES && !quotes.some(item => item.text === quote.text)) {
      setNotice(`最多可附上 ${MAX_ARTICLE_QUOTES} 段，请先移除一段。`)
      return
    }
    setQuotes(current => current.some(item => item.text === quote.text) ? current : [...current, quote])
    window.getSelection()?.removeAllRanges()
    setSelection(null)
    requestAnimationFrame(() => composer.current?.focus({ preventScroll: true }))
  }

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const prompt = question.trim()
    if (!prompt || active.current) return
    const controller = new AbortController()
    active.current = controller
    setBusy(true)
    const id = ++nextId.current
    const turn: Turn = { question: prompt, quotes, answer: { id, content: '' } }
    const history = turns.filter(item => item.answer.content && !item.answer.error && !item.answer.stopped)
      .slice(-MAX_ARTICLE_CHAT_HISTORY).map(item => ({ question: item.question, answer: item.answer.content.slice(0, 4000) }))
    setTurns(current => [...current, turn])
    setQuestion('')
    setQuotes([])
    setNotice('')
    setProgress('正在准备本篇资料…')
    function update(patch: Partial<LibraryChatAnswer>) {
      setTurns(current => current.map(item => item.answer.id === id ? { ...item, answer: { ...item.answer, ...patch } } : item))
      requestAnimationFrame(() => {
        const box = messages.current
        if (box && box.scrollHeight - box.scrollTop - box.clientHeight < 180) box.scrollTop = box.scrollHeight
      })
    }
    requestAnimationFrame(() => { if (messages.current) messages.current.scrollTop = messages.current.scrollHeight })
    try {
      const response = await fetch('/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ question: prompt, article: { slug, quotes, history } }),
      })
      if (!response.ok) {
        const data = await response.json().catch(() => null)
        if (data?.code === 'AUTH_REQUIRED') { libraryAuthClient.invalidate(); onLogin(); return }
        throw new Error(data?.error || '文章问答暂时不可用，请重试。')
      }
      if (!response.body) throw new Error('未收到回答，请重试。')
      let content = ''
      await consumeLibraryChatStream(response.body, event => {
        if (event.message) setProgress(event.message)
        if (event.evidence) update({ evidence: event.evidence, coverage: event.coverage, sections: event.sections })
        if (event.content) { content += event.content; update({ content }) }
      }, controller.signal)
    } catch (cause) {
      if (controller.signal.aborted) update({ stopped: true })
      else update({ error: cause instanceof Error ? cause.message : '文章问答连接失败，请重试。' })
    } finally {
      active.current = null
      setProgress('')
      setBusy(false)
    }
  }

  return <div ref={shell} className="library-article-chat-shell"
    data-left-open={Boolean(contents) && leftOpen} data-right-open={rightOpen}>
    <div className="library-article-workspace library-entry-shell" data-left-open={Boolean(contents) && leftOpen} data-right-open={rightOpen}>
      {contents && <aside id={tocId} hidden={!leftOpen} className="library-article-toc" aria-label="目录">
        <h2>目录</h2>
        {contents}
      </aside>}
      <div className="library-article-reading">{children}</div>
      <aside ref={chatPanel} id={panelId} aria-label="单篇 AI 问答" hidden={!rightOpen} className="library-article-chat">
        <header className="library-article-chat-header">
          <h2>AI 问答</h2>
          <button type="button" className="library-article-chat-close" onClick={() => setRightOpen(false)} aria-label="收起问答"><X size={19} /></button>
        </header>
          <div ref={messages} className="library-article-chat-messages" onClickCapture={event => {
            if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return
            const href = (event.target as Element).closest('a')?.getAttribute('href')
            if (!href?.startsWith(`/library/${encodeURIComponent(slug)}?`)) return
            event.preventDefault()
            if (window.matchMedia('(max-width: 900px)').matches) setRightOpen(false)
            onCitation(href)
          }}>
            {!turns.length && <p className="library-article-chat-empty">直接提问，或划选正文后加入问答。</p>}
            {turns.map(turn => <div className="library-article-chat-turn" key={turn.answer.id}>
              <div className="library-article-chat-user">
                {turn.quotes.map(item => <blockquote key={item.text}><Quote size={13} />
                  {item.anchor && item.version ? <a href={`/library/${encodeURIComponent(slug)}?version=${encodeURIComponent(item.version)}#${item.anchor}`}
                    className="hover:underline" title="跳到选段出处"><span>{item.text}</span></a> : <span>{item.text}</span>}
                </blockquote>)}
                <p>{turn.question}</p>
              </div>
              <LibraryChatAnswerView message={turn.answer} />
            </div>)}
            {progress && <p role="status" className="flex items-center gap-2 text-xs text-slate-500"><Loader2 size={14} className="animate-spin" />{progress}</p>}
          </div>
          <div className="library-article-chat-suggestions" aria-label="推荐问题">
            {articleQuestions.map(item => <button type="button" key={item.label} onClick={() => {
              setQuestion(item.question)
              requestAnimationFrame(() => composer.current?.focus({ preventScroll: true }))
            }}><CornerDownRight size={15} aria-hidden="true" /><span>{item.question}</span></button>)}
          </div>
          <form className="library-article-chat-form" onSubmit={ask}>
            {notice && <p role="alert" className="text-xs text-rose-700">{notice}</p>}
            {!!quotes.length && <div className="library-article-chat-quotes" aria-label="已附选段">
              {quotes.map(item => <div key={item.text} className="library-article-chat-quote">
                <Quote size={14} aria-hidden="true" />
                <details><summary>{item.text}</summary><p>{item.text}</p></details>
                <button type="button" onClick={() => setQuotes(current => current.filter(quote => quote !== item))} aria-label="移除选段"><X size={15} /></button>
              </div>)}
            </div>}
            <textarea ref={composer} value={question} maxLength={2000} rows={2} aria-label="关于本篇的问题"
              placeholder="关于这篇文献，你想问什么？" onChange={event => setQuestion(event.target.value)} />
            <div className="library-article-chat-form-footer">
              {busy ? <button type="button" className="library-article-chat-send" onClick={() => active.current?.abort()} aria-label="停止回答"><Square size={15} /></button>
                : <button type="submit" className="library-article-chat-send" disabled={!question.trim()} aria-label="发送问题"><ArrowUp size={19} /></button>}
            </div>
          </form>
      </aside>
    </div>
      {selection?.quote.version === version && <button type="button" className="library-article-selection" style={{ left: selection.left, top: selection.top }}
        onPointerDown={event => { lastSelection.current = selection.quote; event.preventDefault() }}
        onClick={() => attach(lastSelection.current || selection.quote)}><Quote size={15} />加入问答</button>}
  </div>
}
