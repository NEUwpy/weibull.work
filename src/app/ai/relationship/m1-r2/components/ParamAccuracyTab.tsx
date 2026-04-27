/**
 * M1-R2 三参数估计精度 Tab
 *
 * 对比 M1-R2 迭代逼近后的参数估计精度
 */
"use client"

import React from 'react'

export function ParamAccuracyTab() {
  return (
    <div className="space-y-6">
      {/* 说明 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-blue-700 mb-2">M1-R2 三参数估计精度</h4>
        <p className="text-xs text-blue-600">
          对比 M1-R2 迭代逼近后的参数估计误差。
          需要先运行 evaluate_route2.py 生成评估数据。
        </p>
      </div>

      {/* 占位内容 */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-12 text-center">
        <div className="text-4xl mb-4">📊</div>
        <h3 className="text-lg font-bold text-slate-700 mb-2">评估数据待生成</h3>
        <p className="text-sm text-slate-500 max-w-lg mx-auto">
          需要运行 evaluate_route2.py 对验证样本进行 M1-R2 迭代评估，
          记录 (β̂, η̂, γ̂) 与真值的对比。
        </p>
        <div className="mt-4 bg-slate-100 border border-slate-200 rounded-lg p-3 max-w-md mx-auto">
          <p className="text-xs font-mono text-slate-600">
            python evaluate_route2.py --test-samples 100 --betas 1,2,5
          </p>
        </div>
      </div>

      {/* 预期内容说明 */}
      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-3">预期展示内容</h4>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <h5 className="text-xs font-bold text-blue-600 mb-1">参数估计散点图</h5>
            <p className="text-xs text-blue-500">真实 vs 估计（β, η, γ）</p>
          </div>
          <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
            <h5 className="text-xs font-bold text-purple-600 mb-1">误差分布</h5>
            <p className="text-xs text-purple-500">绝对误差 / 相对误差</p>
          </div>
          <div className="bg-green-50 border border-green-200 rounded-lg p-3">
            <h5 className="text-xs font-bold text-green-600 mb-1">与 M1-R1 对比</h5>
            <p className="text-xs text-green-500">两种方法的参数精度对比</p>
          </div>
        </div>
      </div>
    </div>
  )
}
