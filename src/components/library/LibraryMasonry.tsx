'use client'

import React, { Children, useLayoutEffect, useRef, useState } from 'react'

export function LibraryMasonry({ children, minColumnWidth = 320, maxColumns = 4 }: {
  children: React.ReactNode; minColumnWidth?: number; maxColumns?: number
}) {
  const container = useRef<HTMLDivElement>(null)
  const [columnCount, setColumnCount] = useState(1)

  useLayoutEffect(() => {
    const element = container.current
    if (!element) return
    const measure = () => {
      const gap = parseFloat(getComputedStyle(element).columnGap) || 0
      setColumnCount(Math.min(maxColumns, Math.max(1, Math.floor((element.clientWidth + gap) / (minColumnWidth + gap)))))
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [minColumnWidth, maxColumns])

  // Keep each card in its column when its summary expands; do not rebalance by height.
  const columns: React.ReactNode[][] = Array.from({ length: columnCount }, () => [])
  Children.toArray(children).forEach((child, index) => columns[index % columnCount].push(child))

  return <div ref={container} className="library-cards" style={{ gridTemplateColumns: `repeat(${columnCount}, minmax(0, 1fr))` }}>
    {columns.map((cards, index) => <div key={index} className="library-card-column">{cards}</div>)}
  </div>
}
