"use client"

import React, { useState, useRef, useEffect } from 'react'
import { Send, Minus, Plus, Loader2, CheckCircle, Circle, Bug, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

interface DebugEntry {
  timestamp: number
  stage: string
  action: string
  payload?: any
  response?: string
  result?: string
  error?: string
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  thinking?: string
  debugLogs?: DebugEntry[]
}

interface ChatDialogProps {
  papers: Array<{
    slug: string
    title: string
    title_en?: string
    author: string
    summary: string
    tags: string[]
  }>
}

type ModelKey = 'k2-thinking' | 'k2.5'

type Stage = 'idle' | 'filtering' | 'ranking' | 'generating' | 'done'

const MODEL_LABELS: Record<ModelKey, string> = {
  'k2-thinking': 'Kimi K2 Thinking',
  'k2.5': 'Kimi K2.5'
}

const STAGE_INFO: Record<Stage, { label: string; desc: string }> = {
  idle: { label: '准备中', desc: '' },
  filtering: { label: '筛选文献', desc: '正在分析问题，筛选相关文献...' },
  ranking: { label: '分析章节', desc: '正在深入分析相关章节...' },
  generating: { label: '生成回答', desc: '正在思考并生成回答...' },
  done: { label: '完成', desc: '' }
}

export function ChatDialog({ papers }: ChatDialogProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [streamedContent, setStreamedContent] = useState('')
  const [streamedThinking, setStreamedThinking] = useState('')
  const [debugLogs, setDebugLogs] = useState<DebugEntry[]>([])
  const [currentStage, setCurrentStage] = useState<Stage>('idle')
  const [selectedModel, setSelectedModel] = useState<ModelKey>('k2-thinking')
  const [showThinking, setShowThinking] = useState(true)
  const [showDebug, setShowDebug] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new content arrives
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamedContent])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setIsLoading(true)
    setStreamedContent('')
    setStreamedThinking('')
    setDebugLogs([])
    setCurrentStage('filtering')

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: userMessage,
          history: messages,
          modelKey: selectedModel,
          papers: papers.map(p => ({
            slug: p.slug,
            title: p.title,
            author: p.author,
            summary: p.summary,
            tags: p.tags
          }))
        })
      })

      if (!response.ok) throw new Error('API request failed')

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let fullContent = ''
      let fullThinking = ''
      const currentDebugLogs: DebugEntry[] = []

      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value)
          const lines = chunk.split('\n')

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6)
              if (data === '[DONE]') continue

              try {
                const parsed = JSON.parse(data)

                // Handle debug logs
                if (parsed.debug) {
                  const entry: DebugEntry = {
                    timestamp: Date.now(),
                    stage: parsed.debug.stage,
                    action: parsed.debug.action,
                    payload: parsed.debug.payload,
                    response: parsed.debug.response,
                    result: parsed.debug.result,
                    error: parsed.debug.error
                  }
                  currentDebugLogs.push(entry)
                  setDebugLogs([...currentDebugLogs])
                }

                // Handle stage updates
                if (parsed.stage) {
                  setCurrentStage(parsed.stage)
                }

                // Handle thinking content
                if (parsed.thinking) {
                  fullThinking += parsed.thinking
                  setStreamedThinking(fullThinking)
                }

                // Handle final content
                if (parsed.content) {
                  fullContent += parsed.content
                  setStreamedContent(fullContent)
                }

                // Handle sources
                if (parsed.sources) {
                  setMessages(prev => {
                    const newMessages = [...prev]
                    const lastAssistant = newMessages.findLast(m => m.role === 'assistant')
                    if (lastAssistant) {
                      lastAssistant.sources = parsed.sources
                    }
                    return newMessages
                  })
                }
              } catch (e) {
                // Ignore parse errors for incomplete chunks
              }
            }
          }
        }
      }

      setMessages(prev => [...prev, { role: 'assistant', content: fullContent, thinking: fullThinking, debugLogs: [...currentDebugLogs] }])
      setStreamedContent('')
      setStreamedThinking('')
      setDebugLogs([])
      setCurrentStage('done')
    } catch (error) {
      console.error('Chat error:', error)
      setMessages(prev => [...prev, { role: 'assistant', content: '抱歉，发生了错误，请稍后重试。' }])
      setCurrentStage('done')
    } finally {
      setIsLoading(false)
    }
  }

  // Render markdown-like content (basic implementation)
  const renderContent = (content: string) => {
    // Convert markdown-style code blocks
    content = content.replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    // Convert bold
    content = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    // Convert inline code
    content = content.replace(/`(.*?)`/g, '<code class="bg-blue-50 px-1 rounded text-blue-600">$1</code>')
    // Convert line breaks
    content = content.replace(/\n/g, '<br />')
    return content
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-gradient-to-r from-blue-50 to-emerald-50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <Send size={16} className="text-white" />
          </div>
          <div>
            <h3 className="font-bold text-slate-900">AI 文献助手</h3>
            <p className="text-xs text-slate-500">基于文献库的智能问答</p>
          </div>
        </div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
        >
          {isExpanded ? <Minus size={18} className="text-slate-500" /> : <Plus size={18} className="text-slate-500" />}
        </button>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t border-slate-100">
          {/* Model Selector + Debug Toggle */}
          <div className="px-4 py-3 bg-slate-50 border-b border-slate-100 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="text-sm font-bold text-slate-600">模型：</span>
              <div className="flex bg-slate-100 p-0.5 rounded-lg border border-slate-200">
                {(Object.keys(MODEL_LABELS) as ModelKey[]).map((key) => (
                  <button
                    key={key}
                    onClick={() => setSelectedModel(key)}
                    className={cn(
                      "px-3 py-1 rounded-md text-xs font-bold transition-all",
                      selectedModel === key
                        ? "bg-white text-blue-600 shadow-sm"
                        : "text-slate-400 hover:text-slate-600"
                    )}
                  >
                    {MODEL_LABELS[key]}
                  </button>
                ))}
              </div>
            </div>
            <button
              onClick={() => setShowDebug(!showDebug)}
              className={cn(
                "flex items-center gap-1 px-2 py-1 rounded text-xs font-bold transition-all",
                showDebug ? "bg-orange-100 text-orange-600" : "bg-slate-100 text-slate-400 hover:text-slate-600"
              )}
            >
              <Bug size={14} />
              调试
            </button>
          </div>

          {/* Messages */}
          <div className="h-80 overflow-y-auto p-4 space-y-4 bg-slate-50">
            {messages.length === 0 && (
              <div className="h-full flex items-center justify-center text-slate-400">
                <div className="text-center">
                  <p className="font-medium mb-2">有什么可以帮助你的？</p>
                  <p className="text-sm">比如：极大似然估计的原理和改进方法有哪些？</p>
                </div>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={cn(
                  "flex gap-3",
                  msg.role === 'user' ? "justify-end" : "justify-start"
                )}
              >
                {msg.role === 'assistant' && (
                  <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center shrink-0">
                    <Send size={14} className="text-white" />
                  </div>
                )}
                <div
                  className={cn(
                    "max-w-[80%] rounded-2xl px-4 py-3",
                    msg.role === 'user'
                      ? "bg-blue-600 text-white"
                      : "bg-white border border-slate-200 text-slate-700"
                  )}
                >
                  {msg.role === 'assistant' ? (
                    <>
                      <div
                        className="prose prose-sm max-w-none"
                        dangerouslySetInnerHTML={{ __html: renderContent(msg.content) }}
                      />
                      {msg.thinking && (
                        <details className="mt-3 pt-3 border-t border-slate-100 group">
                          <summary className="text-xs font-bold text-purple-600 cursor-pointer list-none flex items-center gap-2 hover:text-purple-700">
                            <span className="group-open:hidden">查看思考过程</span>
                            <span className="hidden group-open:inline">收起思考过程</span>
                          </summary>
                          <div className="mt-2 text-xs text-slate-600 bg-purple-50 rounded-lg p-3 max-h-48 overflow-y-auto">
                            <pre className="whitespace-pre-wrap font-sans">{msg.thinking}</pre>
                          </div>
                        </details>
                      )}
                      {msg.debugLogs && msg.debugLogs.length > 0 && (
                        <details className="mt-2 pt-2 border-t border-slate-100 group">
                          <summary className="text-xs font-bold text-orange-600 cursor-pointer list-none flex items-center gap-2 hover:text-orange-700">
                            <Bug size={12} />
                            <span className="group-open:hidden">查看调试日志 ({msg.debugLogs.length})</span>
                            <span className="hidden group-open:inline">收起调试日志</span>
                          </summary>
                          <div className="mt-2 text-xs bg-orange-50 rounded-lg p-3 max-h-64 overflow-y-auto space-y-2">
                            {msg.debugLogs.map((log, idx) => (
                              <div key={idx} className="border-l-2 border-orange-200 pl-2">
                                <div className="flex items-center gap-1 text-orange-700 font-bold">
                                  <ChevronRight size={10} />
                                  {log.stage}
                                </div>
                                <div className="text-orange-600 ml-3">{log.action}</div>
                                {log.payload && (
                                  <div className="text-slate-500 ml-3 mt-1 bg-white rounded p-1 text-xs">
                                    {typeof log.payload === 'string' ? log.payload : JSON.stringify(log.payload, null, 2).slice(0, 200)}...
                                  </div>
                                )}
                                {log.response && (
                                  <div className="text-slate-500 ml-3 mt-1 bg-white rounded p-1 text-xs">
                                    {log.response}
                                  </div>
                                )}
                                {log.result && (
                                  <div className="text-green-600 ml-3">✓ {log.result}</div>
                                )}
                                {log.error && (
                                  <div className="text-red-500 ml-3">✗ {log.error}</div>
                                )}
                              </div>
                            ))}
                          </div>
                        </details>
                      )}
                    </>
                  ) : (
                    <p className="text-sm font-medium whitespace-pre-wrap">{msg.content}</p>
                  )}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-slate-100">
                      <p className="text-xs font-bold text-slate-500 mb-2">来源：</p>
                      {msg.sources.map((source, i) => (
                        <p key={i} className="text-xs text-blue-600">{source}</p>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isLoading && streamedContent && (
              <div className="flex gap-3 justify-start">
                <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center shrink-0">
                  <Send size={14} className="text-white" />
                </div>
                <div className="max-w-[80%] bg-white border border-slate-200 rounded-2xl px-4 py-3">
                  <div
                    className="prose prose-sm max-w-none"
                    dangerouslySetInnerHTML={{ __html: renderContent(streamedContent) }}
                  />
                  <Loader2 size={16} className="text-slate-400 animate-spin mt-2" />
                </div>
              </div>
            )}

            {isLoading && !streamedContent && (
              <div className="flex gap-3 justify-start">
                <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center shrink-0">
                  <Send size={14} className="text-white" />
                </div>
                <div className="bg-white border border-slate-200 rounded-2xl px-4 py-3 min-w-[200px]">
                  {/* Stage Progress */}
                  <div className="flex items-center gap-2 mb-2">
                    {currentStage !== 'idle' && currentStage !== 'done' && (
                      <>
                        <Loader2 size={16} className="text-blue-500 animate-spin" />
                        <span className="text-sm font-bold text-slate-700">{STAGE_INFO[currentStage].label}</span>
                      </>
                    )}
                  </div>
                  <p className="text-xs text-slate-500">{STAGE_INFO[currentStage].desc}</p>

                  {/* Debug Logs */}
                  {showDebug && debugLogs.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-slate-100">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-bold text-orange-600">调试日志 ({debugLogs.length})</span>
                      </div>
                      <div className="text-xs bg-orange-50 rounded-lg p-2 max-h-40 overflow-y-auto space-y-1">
                        {debugLogs.map((log, idx) => (
                          <div key={idx} className="border-l-2 border-orange-200 pl-2">
                            <div className="flex items-center gap-1 text-orange-700 font-bold">
                              <ChevronRight size={10} />
                              {log.stage}
                            </div>
                            <div className="text-orange-600 ml-3">{log.action}</div>
                            {log.result && (
                              <div className="text-green-600 ml-3">✓ {log.result}</div>
                            )}
                            {log.error && (
                              <div className="text-red-500 ml-3">✗ {log.error}</div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Thinking Content */}
                  {streamedThinking && showThinking && (
                    <div className="mt-3 pt-3 border-t border-slate-100">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-bold text-purple-600">思考过程</span>
                        <button
                          onClick={() => setShowThinking(false)}
                          className="text-xs text-slate-400 hover:text-slate-600"
                        >
                          收起
                        </button>
                      </div>
                      <div className="text-xs text-slate-600 bg-purple-50 rounded-lg p-2 max-h-32 overflow-y-auto">
                        <pre className="whitespace-pre-wrap font-sans">{streamedThinking}</pre>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <form onSubmit={handleSubmit} className="p-4 border-t border-slate-100 bg-white">
            <div className="flex gap-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="输入你的问题..."
                className="flex-1 px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                className={cn(
                  "px-6 py-3 rounded-xl font-bold transition-all",
                  isLoading || !input.trim()
                    ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                    : "bg-blue-600 text-white hover:bg-blue-700"
                )}
              >
                {isLoading ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <Send size={18} />
                )}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
