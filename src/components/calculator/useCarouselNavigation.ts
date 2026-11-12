'use client'

import { useEffect, useLayoutEffect, useRef } from 'react'

let hoveredCard: HTMLElement | null = null
const nativeControls = 'input, textarea, select, [contenteditable], [role="slider"], [role="combobox"], [role="menu"], [role="listbox"], [role="dialog"], button[aria-haspopup]'

function scrollableWithin(target: Element, card: HTMLElement) {
  for (let element: Element | null = target; element && element !== card; element = element.parentElement) {
    const style = getComputedStyle(element)
    if (/(auto|scroll)/.test(style.overflowY) && element.scrollHeight > element.clientHeight + 1
      || /(auto|scroll)/.test(style.overflowX) && element.scrollWidth > element.clientWidth + 1) return true
  }
  return false
}

export function useCarouselNavigation({ enabled, index, total, onSelect }: {
  enabled: boolean; index: number; total: number; onSelect: (index: number, direction: number) => void
}) {
  const region = useRef<HTMLDivElement | null>(null)
  const latest = useRef({ index, total, onSelect })
  useLayoutEffect(() => { latest.current = { index, total, onSelect } }, [index, total, onSelect])

  useEffect(() => {
    if (!enabled || !region.current) return
    const card = region.current.closest<HTMLElement>('.analysis-card') ?? region.current
    const wheel = { delta: 0, lastEvent: 0, lastChange: -Infinity, direction: 0 }
    let lastKey = -Infinity
    const enter = (event: PointerEvent) => { if (event.pointerType !== 'touch') hoveredCard = card }
    const leave = () => { if (hoveredCard === card) hoveredCard = null; wheel.delta = 0 }
    if (card.matches(':hover')) hoveredCard = card

    const destination = (direction: number) => {
      return latest.current.total > 1 ? latest.current.index + direction : null
    }
    const roll = (event: WheelEvent) => {
      const target = event.target instanceof Element ? event.target : null
      if (event.defaultPrevented || event.ctrlKey || event.metaKey || !target || target.closest(nativeControls)
        || scrollableWithin(target, card)) return
      const delta = (Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY)
        * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? card.clientHeight : 1)
      if (!delta) return
      const direction = Math.sign(delta), next = destination(direction)
      if (next === null) { wheel.delta = 0; return }
      event.preventDefault()
      const now = performance.now()
      if (now - wheel.lastEvent > 180 || direction !== wheel.direction) wheel.delta = 0
      wheel.lastEvent = now
      wheel.direction = direction
      if (now - wheel.lastChange < 300) return
      wheel.delta += delta
      if (Math.abs(wheel.delta) < 40) return
      wheel.delta = 0
      wheel.lastChange = now
      latest.current.onSelect(next, direction)
    }
    const key = (event: KeyboardEvent) => {
      const direction = ['ArrowLeft', 'ArrowUp'].includes(event.key) ? -1
        : ['ArrowRight', 'ArrowDown'].includes(event.key) ? 1 : 0
      if (!direction || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return
      const target = event.target instanceof Element ? event.target : null
      if (target?.closest(nativeControls) || document.querySelector('dialog[open], [role="dialog"][aria-modal="true"]')) return
      if (hoveredCard && (!hoveredCard.isConnected || !hoveredCard.getClientRects().length)) hoveredCard = null
      if (!card.getClientRects().length) return
      const owner = hoveredCard ?? document.querySelector<HTMLElement>('.analysis-card:hover:has(.analysis-stack-stage[data-stacked])')
      if (owner ? owner !== card : !region.current?.contains(document.activeElement)) return
      event.preventDefault()
      const now = performance.now()
      if (event.repeat && now - lastKey < 300) return
      const next = destination(direction)
      if (next === null) return
      lastKey = now
      latest.current.onSelect(next, direction)
    }

    card.addEventListener('pointerenter', enter)
    card.addEventListener('pointermove', enter)
    card.addEventListener('pointerleave', leave)
    card.addEventListener('wheel', roll, { passive: false })
    document.addEventListener('keydown', key)
    window.addEventListener('blur', leave)
    return () => {
      leave()
      card.removeEventListener('pointerenter', enter)
      card.removeEventListener('pointermove', enter)
      card.removeEventListener('pointerleave', leave)
      card.removeEventListener('wheel', roll)
      document.removeEventListener('keydown', key)
      window.removeEventListener('blur', leave)
    }
  }, [enabled])
  return region
}
