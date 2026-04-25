import React from 'react'
import Link from 'next/link'
import { Brain, GitBranch, Zap, Target, ChevronRight } from 'lucide-react'

const modules = [
  {
    id: 'relationship',
    title: '关系建立',
    titleEn: 'Relationship',
    icon: GitBranch,
    color: 'from-purple-50 to-white',
    borderColor: 'border-purple-200 hover:border-purple-400',
    iconBg: 'bg-purple-600',
    accentText: 'text-purple-600',
    accentBg: 'bg-purple-50',
    accentBorder: 'border-purple-100',
    description: 'AI 学习"样本 → 过程参数"的映射关系。当前实现：MDM 偏移量 δ 优化——给定一组失效数据，AI 直接给出最佳偏移量。',
    status: '进行中',
    statusColor: 'bg-green-100 text-green-700',
  },
  {
    id: 'optimization',
    title: '优化求解',
    titleEn: 'Optimization',
    icon: Zap,
    color: 'from-orange-50 to-white',
    borderColor: 'border-orange-200 hover:border-orange-400',
    iconBg: 'bg-orange-600',
    accentText: 'text-orange-600',
    accentBg: 'bg-orange-50',
    accentBorder: 'border-orange-100',
    description: 'AI 辅助传统数值优化方法。仍走传统框架（如 MLE 的 Nelder-Mead），AI 辅助选择初始值或调整优化策略。',
    status: '待开发',
    statusColor: 'bg-slate-100 text-slate-500',
  },
  {
    id: 'direct-estimation',
    title: '直接估计',
    titleEn: 'Direct Estimation',
    icon: Target,
    color: 'from-cyan-50 to-white',
    borderColor: 'border-cyan-200 hover:border-cyan-400',
    iconBg: 'bg-cyan-600',
    accentText: 'text-cyan-600',
    accentBg: 'bg-cyan-50',
    accentBorder: 'border-cyan-100',
    description: '神经网络端到端直接输出参数估计值（β、η、γ），完全绕过优化过程，纯前向传播。',
    status: '待开发',
    statusColor: 'bg-slate-100 text-slate-500',
  },
]

export default function AIPage() {
  return (
    <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12 space-y-8">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-violet-600 text-white shadow-sm">
            <Brain size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-black text-slate-900">人工智能方法</h1>
            <p className="text-sm text-slate-500 font-medium">AI-Assisted Parameter Estimation</p>
          </div>
        </div>
        <p className="text-slate-600 leading-relaxed max-w-3xl">
          探索 AI 如何辅助/替代传统参数估计方法。按 AI 介入方式划分为三类：
          关系建立（学习映射）、优化求解（辅助优化）、直接估计（端到端输出）。
        </p>
      </div>

      {/* Module Cards */}
      <div className="space-y-4">
        {modules.map((mod) => {
          const Icon = mod.icon
          return (
            <Link
              key={mod.id}
              href={`/ai/${mod.id}`}
              className="block group"
            >
              <div className={`bg-white rounded-2xl shadow-sm border ${mod.borderColor} transition-all overflow-hidden hover:shadow-md`}>
                <div className="flex h-[140px]">
                  {/* Left: Module Info */}
                  <div className={`w-[40%] min-w-[320px] flex bg-gradient-to-br ${mod.color} border-r border-slate-100`}>
                    <div className="w-[40%] p-5 pr-4 pl-[60px] flex flex-col justify-center shrink-0">
                      <div className="flex items-center gap-2 mb-3">
                        <div className={`w-8 h-8 ${mod.iconBg} rounded-lg text-white shadow-sm shrink-0 flex items-center justify-center`}>
                          <Icon size={18} />
                        </div>
                        <span className={`text-[14px] font-mono font-bold ${mod.accentText} ${mod.accentBg} px-2 py-1 rounded border ${mod.accentBorder} leading-tight`}>
                          {mod.titleEn}
                        </span>
                      </div>
                      <div className="text-lg font-black text-slate-900 leading-tight">
                        {mod.title}
                      </div>
                    </div>
                    <div className="flex-none w-px bg-slate-200/50 my-5"></div>
                    <div className="flex-1 p-5 pr-6 flex items-center">
                      <div className="text-sm text-slate-500 leading-relaxed">
                        {mod.description}
                      </div>
                    </div>
                  </div>

                  {/* Right: Status + CTA */}
                  <div className="flex-1 p-6 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className={`px-3 py-1 rounded-full text-xs font-bold ${mod.statusColor}`}>
                        {mod.status}
                      </span>
                    </div>
                    <ChevronRight size={20} className="text-slate-300 group-hover:text-slate-500 transition-colors" />
                  </div>
                </div>
              </div>
            </Link>
          )
        })}
      </div>

      {/* Cross Matrix */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-lg font-bold text-slate-900 mb-4">AI × 传统方法 交叉矩阵</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-2 px-4 font-bold text-slate-600"></th>
                <th className="text-center py-2 px-4 font-bold text-slate-600">MDM</th>
                <th className="text-center py-2 px-4 font-bold text-slate-600">MLE</th>
                <th className="text-center py-2 px-4 font-bold text-slate-600">MMLE</th>
                <th className="text-center py-2 px-4 font-bold text-slate-400">...</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-slate-100">
                <td className="py-2 px-4 font-bold text-purple-600">关系建立</td>
                <td className="text-center py-2 px-4"><span className="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs font-bold">δ 优化 ✓</span></td>
                <td className="text-center py-2 px-4 text-slate-300">—</td>
                <td className="text-center py-2 px-4 text-slate-300">—</td>
                <td className="text-center py-2 px-4 text-slate-300">待扩展</td>
              </tr>
              <tr className="border-b border-slate-100">
                <td className="py-2 px-4 font-bold text-orange-600">优化求解</td>
                <td className="text-center py-2 px-4 text-slate-300">—</td>
                <td className="text-center py-2 px-4 text-slate-300">—</td>
                <td className="text-center py-2 px-4 text-slate-300">—</td>
                <td className="text-center py-2 px-4 text-slate-300">待扩展</td>
              </tr>
              <tr>
                <td className="py-2 px-4 font-bold text-cyan-600">直接估计</td>
                <td className="text-center py-2 px-4 text-slate-300">—</td>
                <td className="text-center py-2 px-4 text-slate-300">—</td>
                <td className="text-center py-2 px-4 text-slate-300">—</td>
                <td className="text-center py-2 px-4 text-slate-300">待扩展</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
