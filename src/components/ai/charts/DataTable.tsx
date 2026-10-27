/**
 * 数据表格组件 — 用于展示验证案例和测试结果
 *
 * 复用于：V1(验证案例表), V3(边界测试结果)
 * 设计：纯 HTML 表格，支持排序和着色
 */
"use client"

import React from 'react'

interface Column {
  key: string
  label: string
  format?: (value: unknown) => string
  align?: 'left' | 'center' | 'right'
}

interface DataTableProps {
  columns: Column[]
  rows: Record<string, unknown>[]
  highlightColumn?: string    // 需要着色的列（误差列）
  highlightThreshold?: number // 着色阈值
}

export function DataTable({
  columns,
  rows,
  highlightColumn,
  highlightThreshold = 0.05,
}: DataTableProps) {
  if (!rows || rows.length === 0) {
    return (
      <div className="p-8 text-center text-slate-400 text-sm">
        无数据
      </div>
    )
  }

  const getHighlightColor = (value: unknown) => {
    if (typeof value !== 'number') return ''
    const abs = Math.abs(value)
    if (abs < highlightThreshold * 0.5) return 'text-green-600 bg-green-50'
    if (abs < highlightThreshold) return 'text-yellow-600 bg-yellow-50'
    return 'text-red-600 bg-red-50'
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-slate-50">
            {columns.map(col => (
              <th
                key={col.key}
                className={`border border-slate-200 px-3 py-2 font-bold text-slate-600 ${
                  col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'
                }`}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-slate-50/50">
              {columns.map(col => {
                const value = row[col.key]
                const formatted = col.format ? col.format(value) : String(value ?? '—')
                const isHighlight = highlightColumn === col.key

                return (
                  <td
                    key={col.key}
                    className={`border border-slate-200 px-3 py-1.5 font-mono text-xs ${
                      col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'
                    } ${isHighlight ? getHighlightColor(value) : ''}`}
                  >
                    {formatted}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
