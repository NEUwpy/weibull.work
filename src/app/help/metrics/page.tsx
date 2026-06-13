"use client"

/**
 * 统一评价指标规范页面
 *
 * 维护约定：
 * - 本页面是 `src/lib/metrics.ts` 与 `python/studies/common/metrics.py` 的可读规范。
 * - 两个模块是本页面的可执行实现。
 * - 修改本页面任一公式、字段名或判定口径时，必须同步修改上述模块；
 *   反过来，模块变更也必须同步本页面。
 *
 * 当前默认主口径：
 * - 参数视角：Bias、SD、RMSE、MAE；beta/eta 可附相对 Bias/RMSE，gamma 不输出相对指标。
 * - 工程寿命视角：x_R 的 Bias、SD、RMSE、MAE 与相对 Bias/RMSE。
 * - S2R 中位数族与尾部指标保留为 diagnostics，不再作为唯一主口径。
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
    name: 'Bias',
    nameCn: '偏差',
    latex: '\\frac{1}{N}\\sum_i(\\hat\\theta_i-\\theta)',
    description: '主指标。回答估计值平均偏高还是偏低，必须关注符号。',
    role: '方向',
  },
  {
    name: 'SD',
    nameCn: '标准差',
    latex: '\\sqrt{\\frac{1}{N-1}\\sum_i(\\hat\\theta_i-\\bar{\\hat\\theta})^2}',
    description: '主指标。回答重复抽样下估计值自身波动有多大。',
    role: '稳定性',
  },
  {
    name: 'RMSE',
    nameCn: '均方根误差',
    latex: '\\sqrt{\\frac{1}{N}\\sum_i(\\hat\\theta_i-\\theta)^2}',
    description: '主指标。回答总体误差量级，需与 Bias 和 SD 成套阅读。',
    role: '综合',
  },
  {
    name: 'MAE',
    nameCn: '平均绝对误差',
    latex: '\\frac{1}{N}\\sum_i|\\hat\\theta_i-\\theta|',
    description: '补充指标。与 RMSE 对照可提示尾部或极端误差。',
    role: '补充',
  },
]

const PERSPECTIVES = [
  {
    title: '参数视角',
    accent: 'text-blue-700',
    bg: 'bg-blue-50/70',
    border: 'border-blue-100',
    formula: 'e_\\beta=\\hat\\beta-\\beta,\\quad e_\\eta=\\hat\\eta-\\eta,\\quad e_\\gamma=\\hat\\gamma-\\gamma',
    body: '对 beta、eta、gamma 分别报告 Bias、SD、RMSE、MAE。beta 和 eta 可附相对 Bias/RMSE；gamma 不使用相对指标。',
  },
  {
    title: '工程寿命视角',
    accent: 'text-purple-700',
    bg: 'bg-purple-50/70',
    border: 'border-purple-100',
    formula: 'x_R=\\gamma+\\eta(-\\ln R)^{1/\\beta}',
    body: '默认关注 x0.95 与 x0.99。每个 R 单独报告 Bias、SD、RMSE、MAE 与相对 RMSE，不用参数排序替代寿命排序。',
  },
  {
    title: '诊断视角',
    accent: 'text-emerald-700',
    bg: 'bg-emerald-50/70',
    border: 'border-emerald-100',
    formula: 'MdAPE,\\;MedRel,\\;[P_5,P_{95}],\\;P_{95}(|e|),\\;Valid\\ Rate',
    body: 'S2R 中位数族和尾部分位保留为风险诊断，用于发现 RMSE 表格可能掩盖的异常尾部和有效率问题。',
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
        <div className="mb-2 text-xs font-black uppercase tracking-wider text-blue-600">Evaluation Metrics</div>
        <h1 className="mb-2 text-2xl font-black text-slate-900">指标规范</h1>
        <p className="max-w-4xl text-sm leading-relaxed text-slate-500">
          当前系统默认采用第七轮报告的常用指标：参数视角报告 Bias、SD、RMSE、MAE；
          工程寿命视角报告 x_R 的 Bias、SD、RMSE、MAE 与相对 RMSE。
          S2R 的 MdAPE、方向、IQR、P95/P99 与有效估计率保留为诊断指标，用于识别尾部风险和异常解。
          前后端共享实现位于
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
          <li>• 横向比较默认主口径：Bias、SD、RMSE、MAE；工程寿命视角额外关注 x0.95 / x0.99 的相对 RMSE。S2R 的 MdAPE、方向、IQR、P95/P99 与有效估计率仅作诊断参考。</li>
          <li>• 新增实验必须调用共享指标函数，禁止在组件或脚本中内联重复实现。</li>
          <li>• 页面规范和共享模块必须双向同步；任何一方变更都要同时更新另一方。</li>
          <li>• 真实工程数据没有真值时，只能评价拟合优度；准确性指标仅用于蒙特卡洛或仿真标签已知场景。</li>
        </ul>
      </section>
    </div>
  )
}
