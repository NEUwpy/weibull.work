"use client"

import React, { useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, GitBranch, BookOpen, Cpu, Database, Crosshair, Target, Play, FlaskConical, GitCompare } from 'lucide-react'
import { cn } from '@/lib/utils'
import { TheoryTab } from './components/TheoryTab'
import { TrainingTab } from './components/TrainingTab'
import { DataTab } from './components/DataTab'
import { DeltaAccuracyTab } from './components/DeltaAccuracyTab'
import { ParamAccuracyTab } from './components/ParamAccuracyTab'
import { PlaygroundTab } from './components/PlaygroundTab'
import { VerificationTab } from './components/VerificationTab'
import { CompareTab } from './components/CompareTab'

const tabs = [
  { id: 'theory', label: '原理说明', icon: BookOpen },
  { id: 'training', label: '训练算法', icon: Cpu },
  { id: 'data', label: '训练数据', icon: Database },
  { id: 'delta-accuracy', label: '偏移量估计精度', icon: Crosshair },
  { id: 'param-accuracy', label: '三参数估计精度', icon: Target },
  { id: 'playground', label: '在线使用', icon: Play },
  { id: 'verification', label: '可信性验证', icon: FlaskConical },
  { id: 'compare', label: '方法对比', icon: GitCompare },
]

export default function M1R1Page() {
  const [activeTab, setActiveTab] = useState('theory')

  return (
    <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-8 space-y-6">
      {/* Header */}
      <div className="space-y-3">
        <Link href="/ai/relationship" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-600 transition-colors">
          <ArrowLeft size={14} />
          返回关系建立总览
        </Link>
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-purple-600 text-white shadow-sm">
            <GitBranch size={22} />
          </div>
          <div>
            <h1 className="text-xl font-black text-slate-900">M1-R1 直接学习</h1>
            <p className="text-sm text-slate-500 font-medium">神经网络直接从样本预测最优偏移量 δ，一步到位</p>
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
          {activeTab === 'delta-accuracy' && <DeltaAccuracyTab />}
          {activeTab === 'param-accuracy' && <ParamAccuracyTab />}
          {activeTab === 'playground' && <PlaygroundTab />}
          {activeTab === 'verification' && <VerificationTab />}
          {activeTab === 'compare' && <CompareTab />}
        </div>
      </div>
    </section>
  )
}
