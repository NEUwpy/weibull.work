"use client"

import React from 'react'
import Link from 'next/link'
import { ArrowLeft, GitBranch, Zap, RotateCcw, ChevronRight, BookOpen, Database, Play, BarChart3, FlaskConical } from 'lucide-react'

const routes = [
  {
    id: 'm1-r1',
    title: 'M1-R1 直接学习',
    titleEn: 'Direct Learning',
    icon: Zap,
    color: 'from-purple-50 to-white',
    borderColor: 'border-purple-200 hover:border-purple-400',
    iconBg: 'bg-purple-600',
    accentText: 'text-purple-600',
    accentBg: 'bg-purple-50',
    accentBorder: 'border-purple-100',
    description: '神经网络直接从样本预测最优偏移量 δ，一步到位。按样本量 n 分别训练独立模型（n=5,7,10,15,20）。',
    tabCount: 8,
    status: '可用',
    statusColor: 'bg-green-100 text-green-700',
    features: ['原理说明', '训练算法', '训练数据', '偏移量估计精度', '三参数估计精度', '在线使用', '可信性验证', '方法对比'],
  },
  {
    id: 'm1-r2',
    title: 'M1-R2 迭代逼近',
    titleEn: 'Iterative Approximation',
    icon: RotateCcw,
    color: 'from-blue-50 to-white',
    borderColor: 'border-blue-200 hover:border-blue-400',
    iconBg: 'bg-blue-600',
    accentText: 'text-blue-600',
    accentBg: 'bg-blue-50',
    accentBorder: 'border-blue-100',
    description: '从 δ₀=0.5 开始，用 MDM 估计参数，再用网络预测新 δ，迭代直到收敛（|δ_new-δ_old|<0.001）。',
    tabCount: 9,
    status: '已训练',
    statusColor: 'bg-blue-100 text-blue-700',
    features: ['原理说明', '训练算法', '训练数据', '迭代过程', '偏移量估计精度', '三参数估计精度', '在线使用', '可信性验证', '方法对比'],
  },
]

export default function RelationshipOverviewPage() {
  return (
    <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-8 space-y-6">
      {/* Header */}
      <div className="space-y-3">
        <Link href="/ai" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-600 transition-colors">
          <ArrowLeft size={14} />
          返回 AI 方法总览
        </Link>
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-purple-600 text-white shadow-sm">
            <GitBranch size={22} />
          </div>
          <div>
            <h1 className="text-xl font-black text-slate-900">关系建立 — MDM 偏移量优化</h1>
            <p className="text-sm text-slate-500 font-medium">AI 学习&quot;样本 → 最优偏移量 δ&quot;的映射</p>
          </div>
        </div>
        <p className="text-sm text-slate-500 leading-relaxed max-w-3xl">
          MDM 方法需要手动选择偏移量 δ，不同样本的最优 δ 不同。本模块用两种神经网络方法自动预测最优 δ，替代人工反复尝试。
        </p>
      </div>

      {/* Route Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {routes.map((route) => {
          const Icon = route.icon
          return (
            <Link
              key={route.id}
              href={`/ai/relationship/${route.id}`}
              className="block group"
            >
              <div className={`bg-white rounded-2xl shadow-sm border ${route.borderColor} transition-all overflow-hidden hover:shadow-md h-full`}>
                {/* Header */}
                <div className={`bg-gradient-to-br ${route.color} p-5 border-b border-slate-100`}>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className={`w-8 h-8 ${route.iconBg} rounded-lg text-white shadow-sm shrink-0 flex items-center justify-center`}>
                        <Icon size={18} />
                      </div>
                      <span className={`text-[14px] font-mono font-bold ${route.accentText} ${route.accentBg} px-2 py-1 rounded border ${route.accentBorder} leading-tight`}>
                        {route.titleEn}
                      </span>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-xs font-bold ${route.statusColor}`}>
                      {route.status}
                    </span>
                  </div>
                  <h2 className="text-lg font-black text-slate-900 mb-2">{route.title}</h2>
                  <p className="text-sm text-slate-500 leading-relaxed">{route.description}</p>
                </div>

                {/* Tab List */}
                <div className="p-5">
                  <div className="text-xs text-slate-400 mb-2 font-bold">{route.tabCount} 个功能标签页</div>
                  <div className="flex flex-wrap gap-1.5">
                    {route.features.map((feat, i) => (
                      <span key={i} className="px-2 py-1 bg-slate-50 border border-slate-200 rounded text-xs text-slate-500">
                        {feat}
                      </span>
                    ))}
                  </div>
                  <div className="flex items-center justify-end mt-4 text-sm font-bold text-slate-400 group-hover:text-slate-600 transition-colors">
                    进入 <ChevronRight size={16} className="ml-1" />
                  </div>
                </div>
              </div>
            </Link>
          )
        })}
      </div>

      {/* Quick Comparison */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-lg font-bold text-slate-900 mb-4">两条路线对比</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-2 px-4 font-bold text-slate-600">维度</th>
                <th className="text-center py-2 px-4 font-bold text-purple-600">M1-R1 直接学习</th>
                <th className="text-center py-2 px-4 font-bold text-blue-600">M1-R2 迭代逼近</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-slate-100">
                <td className="py-2 px-4 font-bold text-slate-600">输入</td>
                <td className="text-center py-2 px-4 text-slate-500">样本数据（失效时间）</td>
                <td className="text-center py-2 px-4 text-slate-500">样本数据（失效时间）</td>
              </tr>
              <tr className="border-b border-slate-100">
                <td className="py-2 px-4 font-bold text-slate-600">过程</td>
                <td className="text-center py-2 px-4 text-slate-500">一次前向传播</td>
                <td className="text-center py-2 px-4 text-slate-500">多步迭代（MDM + 网络）</td>
              </tr>
              <tr className="border-b border-slate-100">
                <td className="py-2 px-4 font-bold text-slate-600">模型</td>
                <td className="text-center py-2 px-4 text-slate-500">5 个独立模型（按 n）</td>
                <td className="text-center py-2 px-4 text-slate-500">1 个公共模型</td>
              </tr>
              <tr className="border-b border-slate-100">
                <td className="py-2 px-4 font-bold text-slate-600">速度</td>
                <td className="text-center py-2 px-4 text-green-600 font-bold">极快（&lt;1ms）</td>
                <td className="text-center py-2 px-4 text-yellow-600 font-bold">较慢（多次 MDM）</td>
              </tr>
              <tr>
                <td className="py-2 px-4 font-bold text-slate-600">精度</td>
                <td className="text-center py-2 px-4 text-slate-500">取决于训练数据覆盖</td>
                <td className="text-center py-2 px-4 text-slate-500">依赖收敛性</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
