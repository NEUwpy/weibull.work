/**
 * M1-R1 三参数估计精度 Tab
 *
 * 对比三种 δ 来源下的参数估计误差：
 * ① δ=0.5（固定值） ② δ=AI 预测值 ③ δ=真值最优 δ
 *
 * 数据来源：需要 param-accuracy 对比数据（待生成）
 */
"use client"

import React from 'react'

export function ParamAccuracyTab() {
  return (
    <div className="space-y-6">
      {/* 说明 */}
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-purple-700 mb-2">三参数估计精度</h4>
        <p className="text-xs text-purple-600">
          对比三种 δ 来源下的参数估计误差：δ=0.5（固定值）、δ=AI 预测值、δ=真值最优 δ。
          展示不同 δ 选择对 β̂、η̂、γ̂ 估计精度的影响。
        </p>
      </div>

      {/* 占位内容 */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-12 text-center">
        <div className="text-4xl mb-4">📊</div>
        <h3 className="text-lg font-bold text-slate-700 mb-2">数据待生成</h3>
        <p className="text-sm text-slate-500 max-w-lg mx-auto">
          需要对同一批验证样本，分别用 δ=0.5、δ=AI、δ=最优 运行 MDM，
          记录 (β̂, η̂, γ̂) 用于对比分析。
        </p>
        <div className="mt-4 bg-slate-100 border border-slate-200 rounded-lg p-3 max-w-md mx-auto">
          <p className="text-xs font-mono text-slate-600">
            python generate_comparison_data.py
          </p>
        </div>
      </div>

      {/* 预期内容说明 */}
      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-3">预期展示内容</h4>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
            <h5 className="text-xs font-bold text-slate-600 mb-1">δ = 0.5（固定值）</h5>
            <p className="text-xs text-slate-500">用户常用的经验值作为基准</p>
          </div>
          <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
            <h5 className="text-xs font-bold text-purple-600 mb-1">δ = AI 预测值</h5>
            <p className="text-xs text-purple-500">M1-R1 模型输出的 δ</p>
          </div>
          <div className="bg-green-50 border border-green-200 rounded-lg p-3">
            <h5 className="text-xs font-bold text-green-600 mb-1">δ = 真值最优</h5>
            <p className="text-xs text-green-500">搜索得到的理论最优 δ（上界）</p>
          </div>
        </div>
      </div>
    </div>
  )
}
