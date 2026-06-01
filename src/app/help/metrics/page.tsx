"use client"

/**
 * S2R 指标规范页面
 *
 * 维护约定：
 * - 本页面是 `src/lib/metrics.ts` 与 `python/studies/common/metrics.py` 的可读规范。
 * - 两个模块是本页面的可执行实现。
 * - 修改本页面任一公式、字段名或判定口径时，必须同步修改上述模块；
 *   反过来，模块变更也必须同步本页面。
 *
 * 当前唯一指标体系：
 * - 只展示 MdAPE、带符号中位误差、[P25,P75]、[P5,P95]、P95/P99(|e|)、有效估计率。
 * - NE、NQE_R、RE_R、Outlier Rate 等旧体系指标已废止，不在当前规范中继续使用。
 */

import React from 'react'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { cn } from '@/lib/utils'

function Latex({ math, block = false }: { math: string; block?: boolean }) {
  try {
    const html = katex.renderToString(math, {
      throwOnError: false,
      displayMode: block,
      trust: true,
      strict: false,
    })
    return (
      <span
        className={cn(block && 'block py-1')}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    )
  } catch {
    return <span className="text-red-500 font-mono text-xs">{math}</span>
  }
}

interface MetricDef {
  name: string
  nameCn: string
  latex: string
  description: string
  role: string
}

const CORE_METRICS: MetricDef[] = [
  {
    name: 'MdAPE',
    nameCn: '中位绝对百分比误差',
    latex: '\\operatorname{median}_j\\left|e_j\\right|',
    description: '主准确性指标。回答典型一次估计的误差幅度，稳健于少量边界解或离谱解。',
    role: '主指标',
  },
  {
    name: 'MedRel',
    nameCn: '中位带符号相对误差',
    latex: '\\operatorname{median}_j(e_j)',
    description: '方向指标。正值表示系统高估，负值表示系统低估；与 MdAPE 并列报告。',
    role: '方向',
  },
  {
    name: '[P25, P75]',
    nameCn: '内 50% 区间 / RelIQR',
    latex: '[P_{25}(e),\\;P_{75}(e)]',
    description: '稳定性指标。展示重复实验中间一半估计落在哪，避免只看一个平均值。',
    role: '稳定性',
  },
  {
    name: '[P5, P95] / P95',
    nameCn: '尾部风险',
    latex: '[P_5(e),\\;P_{95}(e)],\\quad P_{95}(|e|)',
    description: '尾部指标。保留“有效但很差”的解，让高分位风险被看见。',
    role: '尾部',
  },
  {
    name: 'Valid Rate',
    nameCn: '有效估计率',
    latex: 'r_{valid}=\\frac{n_{valid}}{n_{total}}',
    description: '门槛指标。只剔除不收敛、数值非法、物理非法或边界病态解。',
    role: '门槛',
  },
]

const PERSPECTIVES = [
  {
    title: '参数视角',
    accent: 'text-blue-700',
    bg: 'bg-blue-50/70',
    border: 'border-blue-100',
    formula: 'e_\\beta=\\frac{\\hat\\beta-\\beta}{\\beta},\\quad e_\\eta=\\frac{\\hat\\eta-\\eta}{\\eta},\\quad e_\\gamma=\\frac{\\hat\\gamma-\\gamma}{\\eta}',
    body: 'beta 和 eta 用自身归一化；gamma 可能为 0，因此统一用 eta 归一化。',
  },
  {
    title: '工程应用视角',
    accent: 'text-purple-700',
    bg: 'bg-purple-50/70',
    border: 'border-purple-100',
    formula: 'x_R=\\gamma+\\eta(-\\ln R)^{1/\\beta},\\quad e_R=\\frac{\\hat x_R-x_R}{x_R}',
    body: '对每个 R 使用同一套分布指标。默认 R = 0.50, 0.90, 0.95, 0.99, 0.999；深尾分位必须由样本量支撑。',
  },
  {
    title: '训练损失',
    accent: 'text-emerald-700',
    bg: 'bg-emerald-50/70',
    border: 'border-emerald-100',
    formula: 'L_{param}=(\\ln\\hat\\beta-\\ln\\beta)^2+(\\ln\\hat\\eta-\\ln\\eta)^2+\\left(\\frac{\\hat\\gamma-\\gamma}{\\eta}\\right)^2',
    body: '损失不是独立评价指标，而是所选评价视角在相对/对数空间里的可微版本。',
  },
]

function MetricCard({ metric }: { metric: MetricDef }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-2 flex flex-wrap items-baseline gap-2">
        <span className="font-mono text-sm font-black text-slate-900">{metric.name}</span>
        <span className="text-sm text-slate-500">{metric.nameCn}</span>
        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-bold text-slate-500">{metric.role}</span>
      </div>
      <div className="mb-2 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-center">
        <Latex math={metric.latex} block />
      </div>
      <p className="text-sm leading-relaxed text-slate-600">{metric.description}</p>
    </div>
  )
}

export default function MetricsPage() {
  return (
    <div className="space-y-8 rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
      <div>
        <div className="mb-2 text-xs font-black uppercase tracking-wider text-blue-600">S2R Metric System</div>
        <h1 className="mb-2 text-2xl font-black text-slate-900">指标规范</h1>
        <p className="max-w-4xl text-sm leading-relaxed text-slate-500">
          评价准确性时，所有点估计指标本质上都在描述相对误差分布。
          当前系统只保留 MdAPE + 方向 + 稳定性 + 尾部 + 有效估计率这一套口径；
          NE、NQE_R、RE_R、Outlier Rate 等旧指标已废止。前后端共享实现位于
          <code className="mx-1 rounded bg-slate-100 px-1 text-xs">src/lib/metrics.ts</code>
          和
          <code className="mx-1 rounded bg-slate-100 px-1 text-xs">python/studies/common/metrics.py</code>。
        </p>
      </div>

      <section>
        <h2 className="mb-4 text-lg font-bold text-slate-900">核心指标族</h2>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {CORE_METRICS.map(metric => <MetricCard key={metric.name} metric={metric} />)}
        </div>
      </section>

      <section>
        <h2 className="mb-4 text-lg font-bold text-slate-900">三种视角</h2>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {PERSPECTIVES.map(item => (
            <div key={item.title} className={cn('rounded-lg border p-4', item.bg, item.border)}>
              <h3 className={cn('mb-2 text-sm font-black', item.accent)}>{item.title}</h3>
              <div className="mb-3 rounded-lg border border-white/70 bg-white px-3 py-2 text-center">
                <Latex math={item.formula} block />
              </div>
              <p className="text-sm leading-relaxed text-slate-600">{item.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-amber-200 bg-amber-50 p-5">
        <h2 className="mb-3 text-sm font-black text-amber-900">状态判定口径</h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="rounded-lg border border-emerald-200 bg-white p-3">
            <div className="mb-1 font-mono text-sm font-bold text-emerald-700">success / valid</div>
            <p className="text-xs leading-relaxed text-slate-600">数值有限、beta/eta 为正、方法收敛、未触发边界病态。误差很大但有效的解仍进入尾部统计。</p>
          </div>
          <div className="rounded-lg border border-red-200 bg-white p-3">
            <div className="mb-1 font-mono text-sm font-bold text-red-700">failure</div>
            <p className="text-xs leading-relaxed text-slate-600">不收敛、非有限值、beta/eta 非正，或 gamma 贴到样本最小值等边界病态。</p>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-slate-50 p-5">
        <h2 className="mb-3 text-sm font-black text-slate-900">已废止旧指标</h2>
        <p className="text-sm leading-relaxed text-slate-600">
          NE、NQE_R、RE_R、Outlier Rate、TRMSE 以及旧的均值型主排序口径不再属于当前评价体系。
          历史实验结果如包含这些字段，只作为旧版本资料，不再用于新研究结论。
        </p>
      </section>

      <section className="rounded-lg border border-blue-100 bg-blue-50 p-5">
        <h2 className="mb-3 text-sm font-black text-blue-900">开发规范</h2>
        <ul className="space-y-2 text-sm leading-relaxed text-blue-800">
          <li>• 横向比较先看 MdAPE、MedRel、[P25,P75]、[P5,P95]、P95(|e|)、Valid Rate。</li>
          <li>• 新增实验必须调用共享指标函数，禁止在组件或脚本中内联重复实现。</li>
          <li>• 页面规范和共享模块必须双向同步；任何一方变更都要同时更新另一方。</li>
          <li>• 真实工程数据没有真值时，只能评价拟合优度；准确性指标仅用于蒙特卡洛或仿真标签已知场景。</li>
        </ul>
      </section>
    </div>
  )
}
