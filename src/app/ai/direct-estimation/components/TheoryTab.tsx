/**
 * 原理说明 Tab — 直接估计
 */
"use client"

import React from 'react'

export function TheoryTab() {
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h3 className="text-lg font-bold text-slate-800 mb-3">什么是直接估计？</h3>
        <p className="text-sm text-slate-600 leading-relaxed">
          直接估计是一种端到端的参数估计方法：输入一组失效时间样本 [t₁, t₂, ..., tₙ]，
          神经网络直接输出三参数 Weibull 分布的参数估计值 β̂（形状参数）、η̂（尺度参数）、γ̂（位置参数）。
          整个过程无迭代优化，纯前向传播，计算速度极快。
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-cyan-700 mb-2">与传统方法的区别</h4>
          <ul className="text-xs text-cyan-600 space-y-1.5">
            <li><span className="font-bold">MLE（极大似然估计）</span>：需要迭代优化似然函数，可能陷入局部最优</li>
            <li><span className="font-bold">MDM（矩估计法）</span>：需要选择偏移量 δ，依赖过程参数</li>
            <li><span className="font-bold">直接估计</span>：无迭代、无过程参数，一步到位</li>
          </ul>
        </div>

        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-slate-700 mb-2">方法原理</h4>
          <ul className="text-xs text-slate-600 space-y-1.5">
            <li>基于万能近似定理：足够大的神经网络可以逼近任意连续函数</li>
            <li>从 Weibull 分布采样大量已知参数的样本作为训练数据</li>
            <li>网络学习"样本分布 → 分布参数"的隐式映射</li>
            <li>训练完成后，前向传播即可完成估计</li>
          </ul>
        </div>
      </div>

      <div>
        <h4 className="text-sm font-bold text-slate-700 mb-2">三参数 Weibull 分布</h4>
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-xs text-slate-600 space-y-2">
          <p className="font-mono">F(t) = 1 - exp(-((t-γ)/η)^β),  t ≥ γ</p>
          <div className="grid grid-cols-3 gap-3 mt-2">
            <div>
              <span className="font-bold text-slate-700">β（形状参数）</span>
              <p className="mt-1">控制分布形状。β&lt;1 递减失效率，β=1 指数分布，β&gt;1 递增失效率。</p>
            </div>
            <div>
              <span className="font-bold text-slate-700">η（尺度参数）</span>
              <p className="mt-1">特征寿命。63.2% 的样本会失效于此时间之前。</p>
            </div>
            <div>
              <span className="font-bold text-slate-700">γ（位置参数）</span>
              <p className="mt-1">最小保证寿命。分布的起始点，γ=0 时退化为两参数 Weibull。</p>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-amber-700 mb-2">当前版本（V0）</h4>
        <p className="text-xs text-amber-600">
          当前为 V0 原型，参数空间较小：β∈&#123;1,2&#125;，η=1000，γ=0，n∈&#123;5,10&#125;。
          目的是验证端到端流程的可行性。后续版本将扩展参数空间、增加样本量范围。
        </p>
      </div>
    </div>
  )
}
