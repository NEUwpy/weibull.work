"use client"

import React from 'react'
import Link from 'next/link'
import { ArrowLeft, Target, ChevronRight, Layers, BarChart3, Database } from 'lucide-react'

const schemes = [
  {
    group: 'A',
    groupTitle: '方案 A：独立模型',
    groupDesc: '按样本量 n 分别训练独立 MLP，每个网络专注一种输入维度',
    icon: Layers,
    color: 'from-cyan-50 to-white',
    borderColor: 'border-cyan-200',
    iconBg: 'bg-cyan-600',
    items: [
      {
        id: 'a-1',
        label: 'A-1',
        title: '原始样本',
        input: '[t1, t2, ..., tn]',
        desc: '最简单，网络自己学尺度不变性',
        status: '已完成',
      },
      {
        id: 'a-2',
        label: 'A-2',
        title: '除以均值',
        input: '[t1/t̄, ..., tn/t̄, t̄]',
        desc: '消 η 影响，t̄ 保留尺度信息',
        status: '已完成',
      },
      {
        id: 'a-3',
        label: 'A-3',
        title: '去位置',
        input: '[t1-t_min, t2-t_min, ..., tn-t_min]',
        desc: '消 γ 影响，网络只用学 β 和 η',
        status: '已完成',
      },
    ],
  },
  {
    group: 'B',
    groupTitle: '方案 B：填充 + 掩码',
    groupDesc: '固定最大长度，短样本补零加掩码，一个模型覆盖所有 n',
    icon: Database,
    color: 'from-emerald-50 to-white',
    borderColor: 'border-emerald-200',
    iconBg: 'bg-emerald-600',
    items: [
      {
        id: 'b-1',
        label: 'B-1',
        title: '原始 + 掩码',
        input: '[t1,...,tn,0,...,0, mask]',
        desc: '统一模型，精度与独立模型几乎相同',
        status: '已完成',
      },
      {
        id: 'b-2',
        label: 'B-2',
        title: '除以均值 + 掩码',
        input: '[t1/t̄,...,tn/t̄,0,...,0, t̄, mask]',
        desc: '消 η + 掩码，结合 A-2 与 B-1',
        status: '已完成',
      },
    ],
  },
  {
    group: 'C',
    groupTitle: '方案 C：统计量输入',
    groupDesc: '不输入原始样本，只输入预计算的统计量，维度固定与 n 无关',
    icon: BarChart3,
    color: 'from-violet-50 to-white',
    borderColor: 'border-violet-200',
    iconBg: 'bg-violet-600',
    items: [
      {
        id: 'c-1',
        label: 'C-1',
        title: '基础统计量',
        input: '[mean, std, min, max]',
        desc: '4 个特征，与 A-1 精度几乎相同',
        status: '已完成',
      },
      {
        id: 'c-2',
        label: 'C-2',
        title: '扩展统计量',
        input: '[mean, std, min, max, skew, kurt, median]',
        desc: '7 个特征，无额外优势',
        status: '已完成',
      },
      {
        id: 'c-3',
        label: 'C-3',
        title: '最大化统计量',
        input: 'C-2 + [Q1, Q3, IQR, CV]',
        desc: '11 个特征，更多分位数信息',
        status: '已完成',
      },
    ],
  },
]

export default function DirectEstimationPage() {
  return (
    <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-8 space-y-6">
      {/* Header */}
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

      {/* 方案选择 */}
      <div className="space-y-4">
        {schemes.map((scheme) => {
          const Icon = scheme.icon
          return (
            <div key={scheme.group} className={`bg-white rounded-2xl shadow-sm border ${scheme.borderColor} overflow-hidden`}>
              {/* 方案组标题 */}
              <div className={`bg-gradient-to-r ${scheme.color} px-6 py-4 border-b ${scheme.borderColor}`}>
                <div className="flex items-center gap-3">
                  <div className={`w-9 h-9 ${scheme.iconBg} rounded-lg text-white shadow-sm flex items-center justify-center`}>
                    <Icon size={18} />
                  </div>
                  <div>
                    <h2 className="text-base font-black text-slate-900">{scheme.groupTitle}</h2>
                    <p className="text-xs text-slate-500">{scheme.groupDesc}</p>
                  </div>
                </div>
              </div>

              {/* 子选项列表 */}
              <div className="divide-y divide-slate-100">
                {scheme.items.map((item) => (
                  <Link
                    key={item.id}
                    href={`/ai/direct-estimation/${item.id}`}
                    className="flex items-center px-6 py-4 hover:bg-slate-50 transition-colors group"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-1">
                        <span className="font-mono font-bold text-sm text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
                          {item.label}
                        </span>
                        <span className="font-bold text-slate-800">{item.title}</span>
                        <span className={`text-xs font-bold px-2 py-0.5 rounded ${item.status === '已完成' ? 'text-green-600 bg-green-50' : 'text-amber-600 bg-amber-50'}`}>
                          {item.status}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-slate-500">
                        <span className="font-mono">{item.input}</span>
                        <span>{item.desc}</span>
                      </div>
                    </div>
                    <ChevronRight size={18} className="text-slate-300 group-hover:text-slate-500 transition-colors ml-4 shrink-0" />
                  </Link>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {/* 实验结论摘要 */}
      <div className="bg-slate-50 border border-slate-200 rounded-xl p-5">
        <h3 className="text-sm font-bold text-slate-700 mb-3">实验结论摘要</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs text-slate-600">
          <div className="bg-white rounded-lg p-3 border border-slate-200">
            <span className="font-bold text-slate-700">C-1 ≈ A-1</span> — 4 个统计量已充分提取 Weibull 参数信息
          </div>
          <div className="bg-white rounded-lg p-3 border border-slate-200">
            <span className="font-bold text-slate-700">B-1 统一模型可行</span> — 一个模型覆盖所有 n，精度几乎相同
          </div>
          <div className="bg-white rounded-lg p-3 border border-slate-200">
            <span className="font-bold text-slate-700">A-2 对 η 变差</span> — 除以均值反而丢失尺度信息
          </div>
          <div className="bg-white rounded-lg p-3 border border-slate-200">
            <span className="font-bold text-slate-700">C-2 无额外优势</span> — 偏度/峰度/中位数未提供新信息
          </div>
          <div className="bg-white rounded-lg p-3 border border-slate-200">
            <span className="font-bold text-slate-700">A-3 明显变差</span> — 去位置丢失绝对尺度，MAE(β) 几乎翻倍
          </div>
          <div className="bg-white rounded-lg p-3 border border-slate-200">
            <span className="font-bold text-slate-700">B-2 ≈ B-1</span> — 除以均值+掩码与原始+掩码精度相当
          </div>
          <div className="bg-white rounded-lg p-3 border border-slate-200">
            <span className="font-bold text-slate-700">C-3 ≈ C-1</span> — Q1/Q3/IQR/CV 未提供超出基础统计量的新信息
          </div>
        </div>
      </div>
    </section>
  )
}
