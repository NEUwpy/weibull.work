'use client'

import { useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { motion, useDragControls, useReducedMotion } from 'framer-motion'
import { useCarouselNavigation } from './useCarouselNavigation'

type Movement = {
  face: string; batch: string; index: number
  kind: 'idle' | 'generate' | 'switch'; direction: number
}

export function SampleCardStack({ face, batch, index, stacked, total, onSelect, playbackMotion = 0,
  playbackActive = false, duration = .22, onSettled, children }: {
  face: string; batch: string; index: number; stacked: boolean; total: number
  onSelect: (index: number) => void; children: ReactNode
  playbackMotion?: number; playbackActive?: boolean; duration?: number; onSettled: (motion: number) => void
}) {
  const reduced = !!useReducedMotion()
  const drag = useDragControls()
  const navigation = useCarouselNavigation({ enabled: stacked, index, total, onSelect })
  const windowRef = useRef<HTMLDivElement | null>(null)
  const [frame, setFrame] = useState({ width: 0, height: 0, step: 8 })
  useLayoutEffect(() => {
    const element = windowRef.current
    if (!element) return
    const measure = () => setFrame(previous => {
      const width = element.offsetWidth, height = element.offsetHeight
      const step = parseFloat(getComputedStyle(element.parentElement!).getPropertyValue('--stack-step')) || 8
      return previous.width === width && previous.height === height && previous.step === step ? previous : { width, height, step }
    })
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  const angle = Math.atan(3 / Math.max(frame.width / 2, frame.height, 1)) * 180 / Math.PI
  const displayedFace = face + ':' + playbackMotion
  const [movement, setMovement] = useState<Movement>({ face: displayedFace, batch, index, kind: 'idle', direction: 0 })
  if (movement.face !== displayedFace || movement.batch !== batch) {
    setMovement({ face: displayedFace, batch, index, kind: movement.batch !== batch ? 'generate' : 'switch',
      direction: playbackActive ? 1 : Math.sign(index - movement.index) })
  }
  const lastFace = useRef(displayedFace)
  const transition = useRef({ direction: movement.direction, duration, step: frame.step, angle, onSettled })
  useLayoutEffect(() => { transition.current = { direction: movement.direction, duration, step: frame.step, angle, onSettled } })
  useLayoutEffect(() => {
    const settings = transition.current
    if (lastFace.current === displayedFace) {
      if (reduced) settings.onSettled(playbackMotion)
      return
    }
    lastFace.current = displayedFace
    const card = windowRef.current
    if (!card || reduced) { settings.onSettled(playbackMotion); return }
    const sign = settings.direction < 0 ? -1 : 1
    const face = card.querySelector<HTMLElement>('.analysis-stack-face')!
    // Move the whole live card together; never fade its controls or recreate them.
    const cardMotion = face.animate([
      { transform: `translateX(${sign * settings.step}px) rotate(${sign * settings.angle}deg)`, transformOrigin: '50% 100%' },
      { transform: 'none', transformOrigin: '50% 100%' },
    ], { duration: settings.duration * 1000, easing: 'cubic-bezier(.22, 1, .36, 1)' })
    const animations = Array.from(card.querySelectorAll<HTMLElement>('[data-stack-content]')).map(element => {
      return element.animate([
        { opacity: .65 },
        { opacity: 1 },
      ], { duration: settings.duration * 1000, easing: 'cubic-bezier(.22, 1, .36, 1)' })
    })
    animations.push(cardMotion)
    let cancelled = false
    Promise.allSettled(animations.map(animation => animation.finished)).then(() => {
      if (!cancelled) transition.current.onSettled(playbackMotion)
    })
    return () => { cancelled = true; animations.forEach(animation => animation.cancel()) }
  }, [displayedFace, playbackMotion, reduced])
  const slots = [-2, -1, 1, 2].filter(offset => index + offset >= 0 && index + offset < total)
  const interactive = 'input, textarea, button, select, a, summary, [contenteditable], [role="slider"], [role="dialog"], svg, .analysis-chart, .analysis-method'
  const move = (direction: number) => {
    const next = index + direction
    if (stacked && next >= 0 && next < total) onSelect(next)
  }
  return <div ref={navigation} className="analysis-stack-stage" data-stacked={stacked || undefined}
    style={{ '--stack-angle': frame.height ? angle + 'deg' : '0deg' } as CSSProperties}
    data-stack-motion={movement.kind} data-stack-direction={movement.direction}
    data-stack-index={index + 1} data-stack-frame={playbackMotion}
    role={stacked ? 'region' : undefined} aria-roledescription={stacked ? '轮播' : undefined}
    aria-label={stacked ? '样本卡片轮播' : undefined} tabIndex={stacked ? 0 : undefined}>
    {stacked && <motion.div key={batch} className="analysis-carousel-edges" aria-hidden="true"
      initial={{ '--stack-reveal': reduced ? 1 : 0, opacity: reduced ? 1 : 0 }}
      animate={{ '--stack-reveal': 1, opacity: 1 }} transition={{ duration: reduced ? 0 : .28, ease: 'easeOut' }}>
      {slots.map(offset => <motion.div key={index + offset} className="analysis-stack-sheet" data-stack-offset={offset}
        initial={false} animate={{ '--stack-offset': offset }}
        transition={{ duration: reduced ? 0 : duration, ease: [.22, 1, .36, 1] }}
        style={{ zIndex: 2 - Math.abs(offset) }} />)}
    </motion.div>}
    <div className="analysis-stack-viewport">
    <motion.div ref={windowRef} className="analysis-stack-window" drag={stacked ? 'x' : false} dragControls={drag}
      dragListener={false} dragConstraints={{ left: 0, right: 0 }} dragElastic={reduced ? 0 : .08} dragMomentum={false}
      dragTransition={{ bounceStiffness: 500, bounceDamping: 35 }}
      onPointerDown={event => {
        if (stacked && !(event.target as HTMLElement).closest(interactive)) drag.start(event)
      }}
      onDragEnd={(_, info) => { if (Math.abs(info.offset.x) >= 48) move(info.offset.x < 0 ? 1 : -1) }}>
      <div className="analysis-stack-face">{children}</div>
    </motion.div>
    </div>
  </div>
}
