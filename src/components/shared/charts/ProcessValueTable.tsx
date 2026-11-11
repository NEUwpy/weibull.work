"use client"

import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'

interface ValueColumn { label: string; align?: 'left' | 'right' }

/** Split consecutive rows into balanced columns without changing their order. */
export function ProcessValueTable({ label, columns, rows, minColumnWidth = 260, footer }: {
  label: string; columns: ValueColumn[]; rows: ReactNode[][]; minColumnWidth?: number; footer?: ReactNode
}) {
  const container = useRef<HTMLDivElement>(null)
  const [columnCount, setColumnCount] = useState(1)

  useLayoutEffect(() => {
    const element = container.current
    if (!element) return
    const measure = () => setColumnCount(Math.max(1, Math.min(3, Math.ceil(rows.length / 3),
      Math.floor((element.clientWidth + 24) / (minColumnWidth + 24)))))
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [minColumnWidth, rows.length])

  const groups = Array.from({ length: columnCount }, (_, index) => {
    const start = Math.floor(rows.length / columnCount) * index + Math.min(index, rows.length % columnCount)
    const length = Math.floor(rows.length / columnCount) + (index < rows.length % columnCount ? 1 : 0)
    return { start, rows: rows.slice(start, start + length) }
  })

  return <div ref={container} className="min-w-0" role="group" aria-label={label} data-table-columns={columnCount}>
    <div className="grid items-start gap-6" style={{ gridTemplateColumns: `repeat(${columnCount}, minmax(0, 1fr))` }}>
      {groups.map(group => <div key={group.start} className="min-w-0 overflow-x-auto">
        <table className="w-full text-base tabular-nums text-slate-700"
          aria-label={columnCount > 1 ? `${label}（${group.start + 1}–${group.start + group.rows.length}）` : label}>
          <thead className="text-sm text-slate-500">
            <tr>{columns.map((column, index) => <th key={index} scope="col"
              className={`whitespace-nowrap border-b border-slate-200 px-3 py-2 font-medium ${column.align === 'right' ? 'text-right' : 'text-left'}`}>{column.label}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {group.rows.map((row, index) => <tr key={group.start + index} data-value-row={group.start + index + 1}>
              {row.map((cell, column) => column === 0
                ? <th key={column} scope="row" className="whitespace-nowrap px-3 py-2 text-left font-normal">{cell}</th>
                : <td key={column} className={`whitespace-nowrap px-3 py-2 ${columns[column].align === 'right' ? 'text-right' : 'text-left'}`}>{cell}</td>)}
            </tr>)}
          </tbody>
        </table>
      </div>)}
    </div>
    {footer && <div className="mt-3 flex flex-wrap justify-end gap-x-5 gap-y-1 border-t border-slate-200 px-3 py-3 text-base tabular-nums text-slate-700">{footer}</div>}
  </div>
}
