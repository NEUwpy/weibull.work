'use client'

import { useEffect, useRef, type MouseEvent, type SyntheticEvent } from 'react'

let openDialogs = 0
let pageLock: { overflow: string; paddingRight: string; left: number; top: number } | null = null

/** Shared behavior for a temporary reading surface above a mounted page. */
export function usePreviewDialog(onClose: () => void) {
  const ref = useRef<HTMLDialogElement>(null)
  const closeButton = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const panel = ref.current!
    const previousFocus = document.activeElement as HTMLElement | null
    if (openDialogs === 0) {
      const { overflow, paddingRight } = document.body.style
      pageLock = { overflow, paddingRight, left: window.scrollX, top: window.scrollY }
      const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth
      if (scrollbarWidth > 0) document.body.style.paddingRight = `${parseFloat(window.getComputedStyle(document.body).paddingRight) + scrollbarWidth}px`
      document.body.style.overflow = 'hidden'
    }
    openDialogs++
    panel.showModal()
    closeButton.current?.focus({ preventScroll: true })
    if (pageLock) window.scrollTo(pageLock)
    return () => {
      panel.close()
      openDialogs--
      if (openDialogs === 0 && pageLock) {
        document.body.style.overflow = pageLock.overflow
        document.body.style.paddingRight = pageLock.paddingRight
        window.scrollTo(pageLock)
        pageLock = null
      }
      if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true })
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
