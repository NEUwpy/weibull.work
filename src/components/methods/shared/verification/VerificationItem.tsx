/**
 * VerificationItem - 单个验证项组件
 *
 * 布局结构：
 * ┌─────────────────────────────────────────────────────┐
 * │ 参数条件（样本/真实参数/仿真设置）                    │
 * ├──────────────────────┬──────────────────────────────┤
 * │  左栏：论文结果        │  右栏：系统复现               │
 * │  (图片/表格)          │  (图表/表格)                 │
 * └──────────────────────┴──────────────────────────────┘
 */
"use client"

import React from 'react'
import Image from 'next/image'
import { cn } from '@/lib/utils'

// 左栏内容类型
export interface PaperContent {
  type: 'image' | 'table' | 'text'
  // image
  src?: string
  alt?: string
  // table
  data?: Record<string, any>[]
  columns?: { key: string; label: string }[]
  // text
  text?: string
}

// 右栏内容（React 节点）
export interface SystemContent {
  node: React.ReactNode
}

// 样本数据
export interface SampleInfo {
  label: string
  value: string | number
}

export interface VerificationItemProps {
  // 标题
  title?: string
  // 参数条件
  params?: SampleInfo[]
  // 样本数据表格（可选，展示具体的样本值）
  samplesData?: {
    headers: string[]
    rows: (string | number)[][]
  }
  samplesExpandable?: boolean  // 是否可折叠，默认 true
  // 左栏：论文内容
  paperContent: PaperContent
  // 右栏：系统内容
  systemContent: React.ReactNode
  // 样式
  className?: string
  // 图表高度
  chartHeight?: number | string
}

export default function VerificationItem({
  title,
  params,
  samplesData,
  samplesExpandable = true,
  paperContent,
  systemContent,
  className,
  chartHeight = 500
}: VerificationItemProps) {
  const [samplesExpanded, setSamplesExpanded] = React.useState(!samplesExpandable)

  return (
    <div className={cn("bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden", className)}>
      {/* 参数条件 */}
      {params && params.length > 0 && (
        <div className="bg-blue-50 px-6 py-4 border-b border-blue-200">
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            {params.map((p, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <span className="text-sm font-bold text-blue-800">{p.label}:</span>
                <span className="text-sm text-blue-700 font-mono">{p.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 样本数据表格（可折叠） */}
      {samplesData && samplesData.rows.length > 0 && (
        <div className="border-b border-slate-200">
          {samplesExpandable && (
            <button
              onClick={() => setSamplesExpanded(!samplesExpanded)}
              className="w-full px-6 py-3 flex items-center justify-between text-left hover:bg-slate-50 transition-colors"
            >
              <span className="text-sm font-bold text-slate-700">
                样本数据 ({samplesData.rows.length} 个样本)
              </span>
              <span className="text-xs text-slate-500">
                {samplesExpanded ? '收起' : '展开'}
              </span>
            </button>
          )}
          {samplesExpanded && (
            <div className="px-6 py-3 overflow-x-auto max-h-[400px] overflow-y-auto">
              <table className="w-full text-xs border-collapse">
                <thead className="sticky top-0 bg-slate-100">
                  <tr>
                    {samplesData.headers.map((h, idx) => (
                      <th key={idx} className="px-2 py-1.5 text-center font-bold text-slate-700 border border-slate-300 whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {samplesData.rows.map((row, rowIdx) => (
                    <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                      {row.map((cell, cellIdx) => (
                        <td key={cellIdx} className="px-2 py-1 text-center font-mono text-slate-600 border border-slate-200 whitespace-nowrap">
                          {typeof cell === 'number' ? cell.toFixed(1) : cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* 左右对比区域 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-0 divide-y lg:divide-y-0 lg:divide-x divide-slate-200">
        {/* 左栏：论文结果 */}
        <div className="p-4">
          <div className="flex items-center justify-center" style={{ minHeight: typeof chartHeight === 'number' ? chartHeight : chartHeight }}>
            {paperContent.type === 'image' && paperContent.src && (
              <div className="relative w-full h-full flex items-center justify-center">
                <Image
                  src={paperContent.src}
                  alt={paperContent.alt || '论文图片'}
                  width={800}
                  height={600}
                  className="max-w-full max-h-full object-contain"
                  unoptimized
                />
              </div>
            )}
            {paperContent.type === 'table' && paperContent.data && (
              <div className="w-full overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="bg-slate-100">
                      {paperContent.columns?.map((col) => (
                        <th key={col.key} className="px-3 py-2 text-center font-bold text-slate-700 border border-slate-300">
                          {col.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {paperContent.data.map((row, idx) => (
                      <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                        {paperContent.columns?.map((col) => (
                          <td key={col.key} className="px-3 py-2 text-center font-mono text-slate-600 border border-slate-200">
                            {row[col.key]}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {paperContent.type === 'text' && (
              <div className="text-slate-600 whitespace-pre-wrap">{paperContent.text}</div>
            )}
          </div>
        </div>

        {/* 右栏：系统复现 */}
        <div className="p-4">
          <div style={{ minHeight: typeof chartHeight === 'number' ? chartHeight : chartHeight }}>
            {systemContent}
          </div>
        </div>
      </div>
    </div>
  )
}
