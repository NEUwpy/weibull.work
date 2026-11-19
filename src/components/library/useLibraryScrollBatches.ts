'use client'

import { useEffect, useRef, useState } from 'react'

export function useLibraryScrollBatches(total: number, batchSize: number, initialCount = batchSize) {
  const [limit, setLimit] = useState(batchSize)
  const sentinel = useRef<HTMLDivElement>(null)
  const visibleCount = Math.min(total, Math.max(initialCount, limit))
  const hasMore = visibleCount < total

  useEffect(() => {
    const target = sentinel.current
    if (!hasMore || !target) return
    if (typeof IntersectionObserver === 'undefined') {
      setLimit(total)
      return
    }

    // In a preview, the dialog body scrolls independently of the page.
    const root = target.closest('[data-library-dialog-scroll]')
    const observer = new IntersectionObserver(entries => {
      if (!entries.some(entry => entry.isIntersecting)) return
      observer.disconnect()
      setLimit(current => Math.max(current, visibleCount + batchSize))
    }, { root, rootMargin: '0px 0px 240px 0px' })
    observer.observe(target)
    return () => observer.disconnect()
  }, [batchSize, hasMore, total, visibleCount])

  return { visibleCount, hasMore, sentinel }
}
