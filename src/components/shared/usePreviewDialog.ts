'use client'

import { useEffect, useRef, type MouseEvent, type SyntheticEvent } from 'react'

/** Shared behavior for a temporary reading surface above a mounted page. */
export function usePreviewDialog(onClose: () => void) {
  const ref = useRef<HTMLDialogElement>(null)
  const closeButton = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const panel = ref.current!
    const previousFocus = document.activeElement as HTMLElement | null
    const { overflow, paddingRight } = document.body.style
    const previousScroll = { left: window.scrollX, top: window.scrollY }
    const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth
    if (scrollbarWidth > 0) document.body.style.paddingRight = `${parseFloat(window.getComputedStyle(document.body).paddingRight) + scrollbarWidth}px`
    document.body.style.overflow = 'hidden'
    panel.showModal()
    closeButton.current?.focus({ preventScroll: true })
    window.scrollTo(previousScroll)
    return () => {
      panel.close()
      document.body.style.overflow = overflow
      document.body.style.paddingRight = paddingRight
      previousFocus?.focus({ preventScroll: true })
      window.scrollTo(previousScroll)
    }
  }, [])

  return {
    closeButton,
    dialog: {
      ref,
      onCancel(event: SyntheticEvent<HTMLDialogElement>) {
        event.preventDefault()
        onClose()
      },
      onClick(event: MouseEvent<HTMLDialogElement>) {
        if (event.target !== event.currentTarget) return
        const { left, right, top, bottom } = event.currentTarget.getBoundingClientRect()
        if (event.clientX < left || event.clientX > right || event.clientY < top || event.clientY > bottom) onClose()
      },
    },
  }
}
