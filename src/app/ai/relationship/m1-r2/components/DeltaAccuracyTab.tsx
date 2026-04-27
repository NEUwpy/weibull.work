/**
 * M1-R2 偏移量估计精度 Tab
 *
 * 展示 M1-R2 迭代逼近后的 δ 预测精度
 */
"use client"

import React from 'react'

export function DeltaAccuracyTab() {
  return (
    <div className="space-y-6">
      {/* 说明 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-blue-700 mb-2">M1-R2 偏移量估计精度</h4>
        <p className="text-xs text-blue-600">
          展示 M1-R2 迭代逼近后最终 δ 与真实最优 δ 的对比。
          需要先运行 evaluate_route2.py 生成评估数据。
        </p>
      </div>

      {/* 占位内容 */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-12 text-center">
        <div className="text-4xl mb-4">🎯</div>
        <h3 className="text-lg font-bold text-slate-700 mb-2">评估数据待生成</h3>
        <p className="text-sm text-slate-500 max-w-lg mx-auto">
          需要运行 evaluate_route2.py 对验证样本进行 M1-R2 迭代评估，
          记录最终 δ 与真实最优 δ 的对比。
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
            <h5 className="text-xs font-bold text-blue-600 mb-1">收敛后 δ vs 最优 δ</h5>
            <p className="text-xs text-blue-500">散点图 + 对角线参考</p>
          </div>
          <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
            <h5 className="text-xs font-bold text-purple-600 mb-1">δ 预测误差分布</h5>
            <p className="text-xs text-purple-500">直方图 + 统计量</p>
          </div>
          <div className="bg-green-50 border border-green-200 rounded-lg p-3">
            <h5 className="text-xs font-bold text-green-600 mb-1">按 n/β 分组精度</h5>
            <p className="text-xs text-green-500">分组对比表格</p>
          </div>
        </div>
      </div>
    </div>
  )
}
