/**
 * 图表卡片容器 - 统一的图表外框样式
 *
 * 设计原则：
 * - 主 TSX 只负责布局和调用此容器
 * - 图表组件作为 children 传入
 * - 标题从配置读取，不硬编码
 */
import React from 'react'

interface ChartCardProps {
  title: string           // 图表标题，格式如 "图 1: β估计值分布"
  children: React.ReactNode  // 图表内容（由图表组件提供）
}

export function ChartCard({ title, children }: ChartCardProps) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-4">
      {children}
      <p className="text-center text-sm font-semibold text-slate-700 mt-3">
        {title}
      </p>
    </div>
  )
}
