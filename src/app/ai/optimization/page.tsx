"use client"

import React from 'react'
import Link from 'next/link'
import { ArrowLeft, Zap, Construction } from 'lucide-react'

export default function OptimizationPage() {
  return (
    <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-8 space-y-6">
      <div className="space-y-3">
        <Link href="/ai" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-600 transition-colors">
          <ArrowLeft size={14} />
          返回 AI 方法总览
        </Link>
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-orange-600 text-white shadow-sm">
            <Zap size={22} />
          </div>
          <div>
            <h1 className="text-xl font-black text-slate-900">优化求解 — AI 辅助数值优化</h1>
            <p className="text-sm text-slate-500 font-medium">AI 辅助传统优化方法（如 MLE 的 Nelder-Mead）</p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-12 text-center">
        <Construction size={48} className="mx-auto text-slate-300 mb-4" />
        <h2 className="text-lg font-bold text-slate-600 mb-2">模块预留</h2>
        <p className="text-sm text-slate-400 max-w-md mx-auto">
          此模块将探索 AI 辅助传统数值优化方法的效果与适用范围。
          仍走传统框架，AI 的角色是辅助选择初始值或调整优化策略。
        </p>
        <p className="text-xs text-slate-300 mt-4">
          实施优先级：模块 1（关系建立）→ 模块 3（直接估计）→ 模块 2（本模块）
        </p>
      </div>
    </section>
  )
}
