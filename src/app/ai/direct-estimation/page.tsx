"use client"

import React from 'react'
import Link from 'next/link'
import { ArrowLeft, Target, Construction } from 'lucide-react'

export default function DirectEstimationPage() {
  return (
    <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-8 space-y-6">
      <div className="space-y-3">
        <Link href="/ai" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-600 transition-colors">
          <ArrowLeft size={14} />
          返回 AI 方法总览
        </Link>
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-cyan-600 text-white shadow-sm">
            <Target size={22} />
          </div>
          <div>
            <h1 className="text-xl font-black text-slate-900">直接估计 — 端到端参数预测</h1>
            <p className="text-sm text-slate-500 font-medium">神经网络直接输出 β、η、γ，绕过优化过程</p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-12 text-center">
        <Construction size={48} className="mx-auto text-slate-300 mb-4" />
        <h2 className="text-lg font-bold text-slate-600 mb-2">模块预留</h2>
        <p className="text-sm text-slate-400 max-w-md mx-auto">
          此模块将探索神经网络端到端直接输出参数估计值的效果与适用范围。
          输入样本数据，直接输出 β（形状）、η（尺度）、γ（位置），无迭代优化。
        </p>
        <p className="text-xs text-slate-300 mt-4">
          实施优先级：模块 1（关系建立）→ 模块 3（本模块）→ 模块 2（优化求解）
        </p>
      </div>
    </section>
  )
}
