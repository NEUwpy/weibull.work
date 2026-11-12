'use client'

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

type Phase = 'generate' | 'calculate'
type Run = {
  identity: string; phase: Phase; total: number; received: number; queue: number[]
  waiting: boolean; ended: boolean; interrupted: boolean; motion: number; shown: number
  duration: number; reduced: boolean
}

/** Present actual groups in order without delaying numerical work. */
export function useCardSequence(identity: string, onSelect: (index: number) => void, reduced: boolean) {
  const select = useRef(onSelect)
  const run = useRef<Run>()
  const revision = useRef(0)
  const mounted = useRef(false)
  const [view, setView] = useState({ active: false, phase: 'generate' as Phase,
    motion: 0, duration: .22, shown: 0, total: 0 })
  useLayoutEffect(() => { select.current = onSelect }, [onSelect])
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])

  const advance = useCallback(() => {
    const current = run.current
    if (!mounted.current || !current || current.interrupted || current.waiting) return
    const next = current.queue.shift()
    if (next === undefined) {
      if (current.ended) {
        current.interrupted = true
        setView(previous => ({ ...previous, active: false }))
      }
      return
    }
    current.waiting = true
    current.motion = ++revision.current
    current.shown = Math.min(current.shown + 1, current.total)
    select.current(next)
    setView({ active: true, phase: current.phase, motion: current.motion,
      duration: current.duration, shown: current.shown, total: current.total })
  }, [])

  const cancel = useCallback(() => {
    if (run.current) run.current.interrupted = true
    setView(previous => previous.active ? { ...previous, active: false } : previous)
  }, [])
  useEffect(() => {
    if (run.current && run.current.identity !== identity) cancel()
  }, [identity, cancel])

  const start = useCallback((phase: Phase, total: number, nextIdentity: string) => {
    const duration = reduced ? 0 : Math.max(.035, Math.min(.22, .8 / Math.sqrt(total)))
    run.current = { identity: nextIdentity, phase, total, received: 0, queue: [], waiting: false,
      ended: false, interrupted: false, motion: 0, shown: 0, duration, reduced }
    setView(previous => ({ ...previous, active: !reduced, phase, duration, shown: 0, total }))
  }, [reduced])

  const ready = useCallback((completed: number, phase: Phase) => {
    const current = run.current
    if (!current || current.interrupted || current.phase !== phase) return
    if (current.reduced) {
      if (completed >= current.total) {
        current.interrupted = true
        select.current(0)
        setView(previous => ({ ...previous, active: false, motion: ++revision.current, shown: current.total }))
      }
      return
    }
    const end = Math.min(completed, current.total)
    for (let index = current.received; index < end; index++) current.queue.push(index)
    current.received = end
    if (end === current.total && !current.ended) {
      if (current.total > 1) current.queue.push(0)
      current.ended = true
    }
    advance()
  }, [advance])

  const settled = useCallback((motion: number) => {
    const current = run.current
    if (!mounted.current || !current || current.interrupted || !current.waiting || current.motion !== motion) return
    current.waiting = false
    advance()
  }, [advance])

  return { ...view, start, ready, cancel, settled }
}
