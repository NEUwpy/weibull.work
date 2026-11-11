"use client"

import { useEffect, useState } from 'react'
import type { MethodFlow } from '@/lib/method-flow'

export function useMethodFlow(methodId: string | null) {
  const [flow, setFlow] = useState<MethodFlow | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!methodId) return
    const controller = new AbortController()
    setLoading(true)
    setFlow(null)
    setError('')
    async function read() {
      try {
        const response = await fetch(`/api/method-flow/${methodId}`, { signal: controller.signal, cache: 'no-store' })
        if (response.status === 404) return
        if (!response.ok) throw new Error('程序流程读取或源码定位失败，请重试。')
        const data: MethodFlow = await response.json()
        if (data.schemaVersion !== 2 || data.methodId !== methodId || !data.steps?.length || !data.sources?.length || data.steps.some(item => !item.sources.length)) throw new Error('程序流程不完整，无法展示。')
        if (!controller.signal.aborted) {
          setFlow(data)
        }
      } catch (cause) {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : '程序流程读取失败。')
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    void read()
    return () => controller.abort()
  }, [methodId, attempt])

  const matchingFlow = flow?.methodId === methodId ? flow : null
  return { flow: matchingFlow, loading: loading || (flow !== null && !matchingFlow), error, retry: () => setAttempt(value => value + 1) }
}
