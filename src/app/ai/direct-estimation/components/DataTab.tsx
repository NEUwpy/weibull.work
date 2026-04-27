/**
 * 训练数据 Tab — 直接估计
 *
 * 展示参数空间、数据规模、样本分布
 */
"use client"

import React from 'react'

const SCHEME_INFO: Record<string, { title: string; input: string; modelType: string }> = {
  'a-1': { title: 'A-1 原始样本', input: '[t1, t2, ..., tn]', modelType: '按 n 独立模型' },
  'a-2': { title: 'A-2 除以均值', input: '[t1/t̄, ..., tn/t̄, t̄]', modelType: '按 n 独立模型' },
  'a-3': { title: 'A-3 去位置', input: '[t1-t_min, ..., tn-t_min]', modelType: '按 n 独立模型' },
  'b-1': { title: 'B-1 填充+掩码', input: '[t1,...,tn,0,...,0, mask]', modelType: '统一模型' },
  'b-2': { title: 'B-2 除以均值+掩码', input: '[t1/t̄,...,tn/t̄,0,...,0, t̄, mask]', modelType: '统一模型' },
  'c-1': { title: 'C-1 基础统计量', input: '[mean, std, min, max]', modelType: '按 n 独立模型' },
  'c-2': { title: 'C-2 扩展统计量', input: '[mean, std, min, max, skew, kurt, median]', modelType: '按 n 独立模型' },
  'c-3': { title: 'C-3 最大化统计量', input: 'C-2 + [Q1, Q3, IQR, CV]', modelType: '按 n 独立模型' },
}

export function DataTab({ scheme = 'a-1' }: { scheme?: string }) {
  const info = SCHEME_INFO[scheme] || SCHEME_INFO['a-1']
  return (
    <div className="space-y-6">
      {/* 方案信息 */}
      <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-3 text-sm text-cyan-700">
        <span className="font-bold">{info.title}</span> — {info.modelType} | 输入: <span className="font-mono">{info.input}</span>
      </div>

      {/* 参数空间 */}
      <div>
        <h3 className="text-base font-bold text-slate-800 mb-3">参数空间（V1）</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">参数</th>
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">含义</th>
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">取值</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">取值数</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="border border-slate-200 px-3 py-2 font-mono font-bold">β</td>
                <td className="border border-slate-200 px-3 py-2 text-slate-600">形状参数</td>
                <td className="border border-slate-200 px-3 py-2 font-mono">{'{0.5, 1, 2, 3, 5}'}</td>
                <td className="border border-slate-200 px-3 py-2 text-right font-mono">5</td>
              </tr>
              <tr>
                <td className="border border-slate-200 px-3 py-2 font-mono font-bold">η</td>
                <td className="border border-slate-200 px-3 py-2 text-slate-600">尺度参数</td>
                <td className="border border-slate-200 px-3 py-2 font-mono">{'{100, 500, 1000, 3000, 5000}'}</td>
                <td className="border border-slate-200 px-3 py-2 text-right font-mono">5</td>
              </tr>
              <tr>
                <td className="border border-slate-200 px-3 py-2 font-mono font-bold">γ</td>
                <td className="border border-slate-200 px-3 py-2 text-slate-600">位置参数</td>
                <td className="border border-slate-200 px-3 py-2 font-mono">{'{0}'}</td>
                <td className="border border-slate-200 px-3 py-2 text-right font-mono">1</td>
              </tr>
              <tr>
                <td className="border border-slate-200 px-3 py-2 font-mono font-bold">n</td>
                <td className="border border-slate-200 px-3 py-2 text-slate-600">样本量</td>
                <td className="border border-slate-200 px-3 py-2 font-mono">{'{5, 7, 10, 15}'}</td>
                <td className="border border-slate-200 px-3 py-2 text-right font-mono">4</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* 数据规模 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-3">
          <div className="text-xs text-cyan-500">参数组合数</div>
          <div className="text-lg font-black text-cyan-700">100</div>
          <div className="text-xs text-cyan-400">5×5×1×4</div>
        </div>
        <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-3">
          <div className="text-xs text-cyan-500">每组 MC 次数</div>
          <div className="text-lg font-black text-cyan-700">500</div>
          <div className="text-xs text-cyan-400">蒙特卡洛采样</div>
        </div>
        <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-3">
          <div className="text-xs text-cyan-500">总样本数</div>
          <div className="text-lg font-black text-cyan-700">50,000</div>
          <div className="text-xs text-cyan-400">100 × 500</div>
        </div>
        <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-3">
          <div className="text-xs text-cyan-500">验证集比例</div>
          <div className="text-lg font-black text-cyan-700">20%</div>
          <div className="text-xs text-cyan-400">随机划分</div>
        </div>
      </div>

      {/* 数据生成方式 */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-2">数据生成方式</h4>
        <div className="text-xs text-slate-600 space-y-2">
          <p>1. 给定真值 (β, η, γ)，从三参数 Weibull 分布抽取 n 个样本：</p>
          <p className="font-mono bg-white px-2 py-1 rounded border border-slate-200">
            t = γ + η × (-ln(1-u))^(1/β),  u ~ Uniform(0,1)
          </p>
          <p>2. 对样本排序：t₁ ≤ t₂ ≤ ... ≤ tₙ</p>
          <p>3. 记录：[n, β, η, γ, t₁, t₂, ..., tₙ]</p>
          <p className="text-slate-500 mt-2">
            与模块 1（MDM δ 优化）不同，直接估计不需要调用 MDM 算法，
            数据生成极其简单——只需从 Weibull 分布采样。
          </p>
        </div>
      </div>

      {/* CSV 格式说明 */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-2">CSV 文件格式</h4>
        <div className="font-mono text-xs bg-white px-3 py-2 rounded border border-slate-200">
          <div className="text-slate-400">n,beta,eta,gamma,t1,t2,...,tn</div>
          <div className="text-slate-600">5,1,1000,0,234.5,567.8,890.1,1234.5,1567.8</div>
          <div className="text-slate-600">5,2,1000,0,112.3,245.6,456.7,789.0,1234.5</div>
        </div>
      </div>

      {/* 文件列表 */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-2">输出文件</h4>
        <div className="text-xs text-slate-600 space-y-1 font-mono">
          <p>python/studies/direct_estimation/data/config.json</p>
          <p>python/studies/direct_estimation/data/training_data_n&#123;5,7,10,15&#125;.csv</p>
          <p>python/models/direct_estimation/n&#123;5,7,10,15&#125;_model.pth</p>
        </div>
      </div>
    </div>
  )
}
