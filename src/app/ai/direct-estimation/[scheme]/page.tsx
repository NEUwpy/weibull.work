"use client"

import React, { useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { ArrowLeft, Target, BookOpen, Cpu, Database, Play, BarChart3, FlaskConical, GitCompare } from 'lucide-react'
import { cn } from '@/lib/utils'
import { TheoryTab } from '../components/TheoryTab'
import { TrainingTab } from '../components/TrainingTab'
import { DataTab } from '../components/DataTab'
import { PlaygroundTab } from '../components/PlaygroundTab'
import { PerformanceTab } from '../components/PerformanceTab'
import { VerificationTab } from '../components/VerificationTab'
import { CompareTab } from '../components/CompareTab'

const SCHEME_INFO: Record<string, { label: string; title: string; input: string; desc: string }> = {
  'a-1': { label: 'A-1', title: '原始样本', input: '[t1, t2, ..., tn]', desc: '按 n 独立模型，原始样本输入' },
  'a-2': { label: 'A-2', title: '除以均值', input: '[t1/t̄, ..., tn/t̄, t̄]', desc: '按 n 独立模型，除以均值+拼接t̄' },
  'a-3': { label: 'A-3', title: '去位置', input: '[t1-t_min, ..., tn-t_min]', desc: '按 n 独立模型，消 γ 影响' },
  'b-1': { label: 'B-1', title: '填充+掩码', input: '[t1,...,tn,0,...,0, mask]', desc: '统一模型，填充到 n_max=15' },
  'b-2': { label: 'B-2', title: '除以均值+掩码', input: '[t1/t̄,...,tn/t̄,0,...,0, t̄, mask]', desc: '统一模型，消 η + 掩码' },
  'c-1': { label: 'C-1', title: '基础统计量', input: '[mean, std, min, max]', desc: '按 n 独立模型，4 个统计量' },
  'c-2': { label: 'C-2', title: '扩展统计量', input: '[mean, std, min, max, skew, kurt, median]', desc: '按 n 独立模型，7 个统计量' },
  'c-3': { label: 'C-3', title: '最大化统计量', input: 'C-2 + [Q1, Q3, IQR, CV]', desc: '按 n 独立模型，11 个统计量' },
}

const tabs = [
  { id: 'theory', label: '原理说明', icon: BookOpen },
  { id: 'training', label: '训练算法', icon: Cpu },
  { id: 'data', label: '训练数据', icon: Database },
  { id: 'playground', label: '在线使用', icon: Play },
  { id: 'performance', label: '性能展示', icon: BarChart3 },
  { id: 'verification', label: '可信性验证', icon: FlaskConical },
  { id: 'compare', label: '方法对比', icon: GitCompare },
]

export default function SchemePage() {
  const params = useParams()
  const scheme = params.scheme as string
  const [activeTab, setActiveTab] = useState('theory')

  const info = SCHEME_INFO[scheme]
  if (!info) {
    return (
      <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-8">
        <div className="text-center py-12">
          <p className="text-slate-500">未知方案: {scheme}</p>
          <Link href="/ai/direct-estimation" className="text-cyan-600 hover:underline text-sm mt-2 inline-block">
            返回方案选择
          </Link>
        </div>
      </section>
    )
  }

  return (
    <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-8 space-y-6">
      {/* Header */}
      <div className="space-y-3">
        <Link href="/ai/direct-estimation" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-600 transition-colors">
          <ArrowLeft size={14} />
          返回方案选择
        </Link>
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-cyan-600 text-white shadow-sm">
            <Target size={22} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-black text-slate-900">直接估计 — {info.label}</h1>
              <span className="font-mono text-sm text-cyan-600 bg-cyan-50 px-2 py-0.5 rounded border border-cyan-200">
                {info.title}
              </span>
            </div>
            <p className="text-sm text-slate-500 font-medium">{info.desc} | 输入: {info.input}</p>
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
                    ? "text-cyan-600 border-cyan-600 bg-cyan-50/50"
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
          {activeTab === 'theory' && <TheoryTab scheme={scheme} />}
          {activeTab === 'training' && <TrainingTab scheme={scheme} />}
          {activeTab === 'data' && <DataTab scheme={scheme} />}
          {activeTab === 'playground' && <PlaygroundTab scheme={scheme} />}
          {activeTab === 'performance' && <PerformanceTab scheme={scheme} />}
          {activeTab === 'verification' && <VerificationTab scheme={scheme} />}
          {activeTab === 'compare' && <CompareTab />}
        </div>
      </div>
    </section>
  )
}
