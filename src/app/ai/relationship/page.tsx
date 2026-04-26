"use client"

import React, { useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, GitBranch, BookOpen, Cpu, Database, Play, BarChart3, FlaskConical, GitCompare } from 'lucide-react'
import { cn } from '@/lib/utils'
import { DataTab } from './components/DataTab'
import { TrainingTab } from './components/TrainingTab'
import { PerformanceTab } from './components/PerformanceTab'
import { PlaygroundTab } from './components/PlaygroundTab'
import { VerificationTab } from './components/VerificationTab'
import { CompareTab } from './components/CompareTab'

const tabs = [
  { id: 'theory', label: '原理说明', icon: BookOpen },
  { id: 'training', label: '训练算法', icon: Cpu },
  { id: 'data', label: '训练数据', icon: Database },
  { id: 'playground', label: '在线使用', icon: Play },
  { id: 'performance', label: '性能展示', icon: BarChart3 },
  { id: 'verification', label: '可信性验证', icon: FlaskConical },
  { id: 'compare', label: '方法对比', icon: GitCompare },
]

export default function RelationshipPage() {
  const [activeTab, setActiveTab] = useState('theory')

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
            <p className="text-sm text-slate-500 font-medium">AI 学习“样本 → 最优偏移量 δ”的映射</p>
          </div>
        </div>
      </div>

      {/* Tab Bar */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="flex border-b border-slate-200 overflow-x-auto scrollbar-hide">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex items-center gap-2 px-5 py-3 text-sm font-bold whitespace-nowrap transition-all border-b-2",
                  activeTab === tab.id
                    ? "text-purple-600 border-purple-600 bg-purple-50/50"
                    : "text-slate-400 border-transparent hover:text-slate-600 hover:bg-slate-50"
                )}
              >
                <Icon size={16} />
                {tab.label}
              </button>
            )
          })}
        </div>

        {/* Tab Content */}
        <div className="p-6 min-h-[400px]">
          {activeTab === 'theory' && <TheoryTab />}
          {activeTab === 'training' && <TrainingTab />}
          {activeTab === 'data' && <DataTab />}
          {activeTab === 'playground' && <PlaygroundTab />}
          {activeTab === 'performance' && <PerformanceTab />}
          {activeTab === 'verification' && <VerificationTab />}
          {activeTab === 'compare' && <CompareTab />}
        </div>
      </div>
    </section>
  )
}

function TheoryTab() {
  return (
    <div className="prose prose-slate max-w-none space-y-4">
      <h2 className="text-lg font-bold text-slate-900">原理说明</h2>
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <p className="text-sm text-purple-800 font-medium">
          核心思路：MDM 方法需要手动选择偏移量 δ，不同样本的最优 δ 不同。
          本模块用两种神经网络方法自动预测最优 δ，替代人工反复尝试。
        </p>
      </div>

      <h3 className="text-base font-bold text-slate-800">为什么需要这个模块？</h3>
      <p className="text-sm text-slate-600 leading-relaxed">
        MDM（最小差异法）中的偏移量 δ 是一个关键的过程参数，它控制梯度偏移判据的阈值。
        不同的 δ 值会导致完全不同的参数估计结果。传统做法是人工尝试多个 δ 值，
        但这既耗时又依赖经验。本模块用 AI 自动化这一过程。
      </p>

      <h3 className="text-base font-bold text-slate-800">两条研究路线</h3>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-purple-700 mb-2">路线 1：直接学习</h4>
          <div className="text-xs text-purple-600 font-mono space-y-1">
            <p>蒙特卡洛模拟（已知真值）</p>
            <p>→ 学习"样本 → 最优 δ"的规律</p>
            <p>→ 推广到实际数据</p>
          </div>
          <p className="text-xs text-purple-500 mt-2">
            神经网络 N₂ 直接从样本预测最优 δ，一步到位。
          </p>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-blue-700 mb-2">路线 2：迭代逼近</h4>
          <div className="text-xs text-blue-600 font-mono space-y-1">
            <p>样本 → δ₀=0.5 → MDM → 预估参数</p>
            <p>→ N₁(真值→最优δ) → δ₁</p>
            <p>→ MDM → 新预估 → ... → 收敛</p>
          </div>
          <p className="text-xs text-blue-500 mt-2">
            用 MDM 自己的估计结果作为真值的近似，迭代逼近。
          </p>
        </div>
      </div>

      <h3 className="text-base font-bold text-slate-800">AI 方法与传统方法的关系</h3>
      <p className="text-sm text-slate-600 leading-relaxed">
        本模块不替代 MDM 方法本身，而是替代“选择 δ”这一步。MDM 算法仍然负责参数估计，
        AI 只是给出一个更好的输入参数。这是一种“关系建立”型的 AI 辅助方式。
      </p>

      <h3 className="text-base font-bold text-slate-800">指标方案（5 种对比）</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-slate-50">
              <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">方案</th>
              <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">公式</th>
              <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">特点</th>
            </tr>
          </thead>
          <tbody>
            <tr><td className="border border-slate-200 px-3 py-2 font-bold">A. MSE 绝对值</td><td className="border border-slate-200 px-3 py-2 font-mono text-xs">(β̂-β)² + (η̂-η)² + (γ̂-γ)²</td><td className="border border-slate-200 px-3 py-2 text-slate-500">简单直接</td></tr>
            <tr><td className="border border-slate-200 px-3 py-2 font-bold">B. 相对 MSE</td><td className="border border-slate-200 px-3 py-2 font-mono text-xs">(β̂-β)²/β² + (η̂-η)²/η² + (γ̂-γ)²/γ²</td><td className="border border-slate-200 px-3 py-2 text-slate-500">消除量纲影响</td></tr>
            <tr><td className="border border-slate-200 px-3 py-2 font-bold">C. 加权 MSE</td><td className="border border-slate-200 px-3 py-2 font-mono text-xs">w₁(β̂-β)² + w₂(η̂-η)² + w₃(γ̂-γ)²</td><td className="border border-slate-200 px-3 py-2 text-slate-500">可调权重</td></tr>
            <tr><td className="border border-slate-200 px-3 py-2 font-bold">D. 仅 β+η</td><td className="border border-slate-200 px-3 py-2 font-mono text-xs">(β̂-β)² + (η̂-η)²</td><td className="border border-slate-200 px-3 py-2 text-slate-500">排除不稳定的 γ</td></tr>
            <tr><td className="border border-slate-200 px-3 py-2 font-bold">E. R²</td><td className="border border-slate-200 px-3 py-2 font-mono text-xs">1 - SS_res/SS_tot</td><td className="border border-slate-200 px-3 py-2 text-slate-500">拟合优度</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
