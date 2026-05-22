"use client"

import React from 'react'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { cn } from '@/lib/utils'

// ============================================================
// LaTeX 渲染器
// ============================================================

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

// ============================================================
// 数据定义
// ============================================================

interface MetricDef {
  name: string
  nameCn: string
  latex: string
  description: string
  note?: string
}

// 层 1：参数估计视角
const PARAM_METRICS: MetricDef[] = [
  {
    name: 'NE',
    nameCn: '归一化综合误差',
    latex: '\\text{NE} = \\sqrt{ \\left(\\frac{\\hat{\\beta} - \\beta}{\\beta}\\right)^2 + \\left(\\frac{\\hat{\\eta} - \\eta}{\\eta}\\right)^2 + \\left(\\frac{\\hat{\\gamma} - \\gamma}{\\eta}\\right)^2 }',
    description: '核心横向比较指标。将三个参数放到可比较的尺度上，gamma 使用 eta 归一化，避免 gamma=0 时的分母问题。',
    note: 'gamma 用 eta 归一化（非 gamma 自身），这是与旧 TRMSE 的关键区别。',
  },
  {
    name: 'Bias',
    nameCn: '偏差',
    latex: '\\text{Bias}(\\hat{\\theta}) = \\frac{1}{n}\\sum_{i=1}^{n}(\\hat{\\theta}_i - \\theta_i)',
    description: '系统偏差。正值 = 高估，负值 = 低估。按 beta、eta、gamma 分别计算。',
  },
  {
    name: 'MAE',
    nameCn: '平均绝对误差',
    latex: '\\text{MAE}(\\hat{\\theta}) = \\frac{1}{n}\\sum_{i=1}^{n}|\\hat{\\theta}_i - \\theta_i|',
    description: '平均偏差幅度，与原始数据同量纲。按 beta、eta、gamma 分别计算。',
  },
  {
    name: 'RMSE',
    nameCn: '均方根误差',
    latex: '\\text{RMSE}(\\hat{\\theta}) = \\sqrt{\\frac{1}{n}\\sum_{i=1}^{n}(\\hat{\\theta}_i - \\theta_i)^2}',
    description: '对大偏差敏感，适合检测异常估计。按 beta、eta、gamma 分别计算。',
  },
]

// 层 2：工程分位点视角
const QUANTILE_METRICS: MetricDef[] = [
  {
    name: 'x_R',
    nameCn: '可靠度寿命分位点',
    latex: 'x_R = \\gamma + \\eta \\cdot (-\\ln R)^{1/\\beta}',
    description: '给定可靠度 R 下的寿命。三参数威布尔在工程中常以分位点而非原始参数作为输出。',
  },
  {
    name: 'NQE_R',
    nameCn: '归一化分位点误差',
    latex: '\\text{NQE}_R = \\frac{|\\hat{x}_R - x_R|}{\\eta}',
    description: '分位点误差用 eta 归一化。比 RE_R 更稳健，适合 x_R 较小或接近边界时作为主参考。',
  },
  {
    name: 'RE_R',
    nameCn: '相对分位点误差',
    latex: '\\text{RE}_R = \\frac{|\\hat{x}_R - x_R|}{x_R}',
    description: '分位点误差用 x_R 自身归一化。当 R 接近 1 时 x_R 可能很小，此指标会被放大。',
  },
  {
    name: 'Bias_QR',
    nameCn: '分位点偏差',
    latex: '\\text{Bias}_{QR} = \\frac{1}{n}\\sum_{i=1}^{n}(\\hat{x}_{R,i} - x_{R,i})',
    description: '分位点的系统偏差。按 R 水平分别计算。',
  },
  {
    name: 'MAE_QR / RMSE_QR',
    nameCn: '分位点 MAE / RMSE',
    latex: '\\text{MAE}_{QR},\\; \\text{RMSE}_{QR}',
    description: '分位点的平均绝对误差和均方根误差，按 R 水平分别计算。',
  },
]

const R_LEVELS = [
  { R: 0.995, label: '99.5%' },
  { R: 0.990, label: '99.0%' },
  { R: 0.950, label: '95.0%' },
  { R: 0.900, label: '90.0%' },
]

// 层 3：方法可用性视角
const AVAILABILITY_METRICS: MetricDef[] = [
  {
    name: 'Failure Rate',
    nameCn: '失败率',
    latex: '\\text{Failure Rate} = \\frac{n_{\\text{failure}}}{n_{\\text{total}}}',
    description: '方法未能给出可用结果的比例。failure 包括：不收敛、异常中断、无解、输出非有限值、beta_hat/eta_hat <= 0。',
  },
  {
    name: 'Outlier Rate',
    nameCn: '异常估计率',
    latex: '\\text{Outlier Rate} = \\frac{n_{\\text{outlier}}}{n_{\\text{total}}}',
    description: '方法给出结果但 NE > 1.0 的比例。outlier 不含 failure，三态互斥。',
  },
  {
    name: 'Time',
    nameCn: '运行时间',
    latex: '\\bar{t},\\; P_{50}(t),\\; P_{95}(t)',
    description: '仅统计 success 样本的运行时间均值、P50 和 P95。',
  },
  {
    name: 'Success Rate',
    nameCn: '成功率',
    latex: '\\text{Success Rate} = \\frac{n_{\\text{success}}}{n_{\\text{total}}}',
    description: '方法给出有效结果的比例。三态互斥下可由 1 - Failure Rate - Outlier Rate 推出，显式列出便于核对。',
  },
]

// 三态定义
const STATUS_DEFS = [
  { status: 'success', label: '成功', desc: '数值有效、物理可解释、NE <= 1.0', color: 'text-emerald-600 bg-emerald-50 border-emerald-200' },
  { status: 'failure', label: '失败', desc: '未给出可用结果（不收敛、非有限值、beta/eta <= 0）', color: 'text-red-600 bg-red-50 border-red-200' },
  { status: 'outlier', label: '异常', desc: '有结果但 NE > 1.0，不进入精度统计', color: 'text-amber-600 bg-amber-50 border-amber-200' },
]

// 单参数基础指标（旧指标保留）
const SUPPLEMENTARY_METRICS: MetricDef[] = [
  {
    name: 'MSE',
    nameCn: '均方误差',
    latex: '\\text{MSE} = \\frac{1}{n}\\sum_{i=1}^{n} e_i^2',
    description: '单参数均方误差。适用于单参数分析，不适用于跨参数横向比较（beta/eta/gamma 量纲不同）。',
  },
  {
    name: 'MRE',
    nameCn: '平均相对误差',
    latex: '\\text{MRE} = \\frac{1}{n}\\sum_{i=1}^{n}\\frac{|e_i|}{|\\theta_i|}',
    description: '单参数相对误差。注意：gamma=0 时分母为零，不适用于含 gamma=0 的综合比较。',
  },
  {
    name: 'std',
    nameCn: '标准差',
    latex: '\\text{std}(\\hat{\\theta}) = \\sqrt{\\frac{1}{n}\\sum_{i=1}^{n}(\\hat{\\theta}_i - \\bar{\\hat{\\theta}})^2}',
    description: '估计值的离散程度。越小表示方法越稳定。',
  },
  {
    name: 'bias',
    nameCn: '单参数偏差',
    latex: '\\text{bias}(\\hat{\\theta}) = \\hat{\\theta} - \\theta',
    description: '单样本偏差，有正有负。正值 = 高估，负值 = 低估。',
  },
]

// 已废弃指标
const DEPRECATED_METRICS: MetricDef[] = [
  {
    name: 'TRMSE',
    nameCn: '总相对 MSE（已废弃）',
    latex: '\\text{TRMSE} = \\sum_{p \\in \\{\\beta,\\eta,\\gamma\\}} \\left(\\frac{\\hat{p} - p}{p}\\right)^2',
    description: '已被 NE 替代。旧 TRMSE 中 gamma 用 gamma 自身归一化（/gamma），gamma=0 时会除零。NE 改用 eta 归一化（/eta）解决此问题。',
  },
]

// ============================================================
// 指标卡片
// ============================================================

function MetricCard({ metric, accent }: { metric: MetricDef; accent: string }) {
  return (
    <div className="p-5 rounded-2xl bg-slate-50 border border-slate-100">
      <div className="flex items-baseline gap-2 mb-2">
        <span className={cn('font-mono font-bold text-base', accent)}>{metric.name}</span>
        <span className="text-sm text-slate-500">{metric.nameCn}</span>
      </div>
      <div className="bg-white rounded-xl border border-slate-200 px-4 py-3 text-center mb-2">
        <Latex math={metric.latex} block />
      </div>
      <p className="text-sm text-slate-600 leading-relaxed">{metric.description}</p>
      {metric.note && (
        <p className="text-xs text-blue-600 mt-2 leading-relaxed">{metric.note}</p>
      )}
    </div>
  )
}

// ============================================================
// 页面
// ============================================================

export default function MetricsPage() {
  return (
    <div className="bg-white p-10 rounded-3xl border border-slate-200 shadow-sm space-y-10">
      {/* 标题 */}
      <div>
        <h1 className="text-2xl font-black text-slate-900 mb-2">指标规范</h1>
        <p className="text-slate-500">
          定义系统所有评价指标的公式、含义与使用范围。
          前后端共享函数实现同一公式（前端 <code className="bg-slate-100 px-1 rounded text-xs">src/lib/metrics.ts</code>，后端 <code className="bg-slate-100 px-1 rounded text-xs">python/studies/common/metrics.py</code>）。
        </p>
      </div>

      {/* 基础定义 */}
      <section>
        <h2 className="text-lg font-bold text-slate-900 mb-4">基础定义</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="p-5 rounded-2xl bg-slate-50 border border-slate-100">
            <div className="font-mono font-bold text-slate-900 text-base mb-2">误差 error</div>
            <div className="bg-white rounded-xl border border-slate-200 px-4 py-3 text-center mb-2">
              <Latex math="e_i = \hat{\theta}_i - \theta_i" block />
            </div>
            <p className="text-sm text-slate-600">估计值减真值，有正有负。正值 = 高估，负值 = 低估。</p>
          </div>
          <div className="p-5 rounded-2xl bg-slate-50 border border-slate-100">
            <div className="font-mono font-bold text-slate-900 text-base mb-2">绝对误差 absolute error</div>
            <div className="bg-white rounded-xl border border-slate-200 px-4 py-3 text-center mb-2">
              <Latex math="r_i = |\hat{\theta}_i - \theta_i|" block />
            </div>
            <p className="text-sm text-slate-600">误差取绝对值，恒 &ge; 0。反映偏差幅度，不区分高估/低估。</p>
          </div>
        </div>
      </section>

      {/* 层 1：参数估计视角 */}
      <section>
        <h2 className="text-lg font-bold text-slate-900 mb-1">参数估计视角</h2>
        <p className="text-sm text-slate-500 mb-4">回答：beta、eta、gamma 三个参数估得准不准？</p>
        <div className="space-y-4">
          {PARAM_METRICS.map(m => <MetricCard key={m.name} metric={m} accent="text-blue-700" />)}
        </div>
      </section>

      {/* 层 2：工程分位点视角 */}
      <section>
        <h2 className="text-lg font-bold text-slate-900 mb-1">工程分位点视角</h2>
        <p className="text-sm text-slate-500 mb-4">回答：给定可靠度水平下的寿命估得准不准？</p>

        {/* R 水平说明 */}
        <div className="mb-4 p-4 rounded-xl bg-blue-50 border border-blue-100">
          <div className="text-sm font-bold text-blue-800 mb-2">可靠度水平</div>
          <div className="flex flex-wrap gap-2">
            {R_LEVELS.map(r => (
              <span key={r.R} className="px-3 py-1 rounded-lg bg-white border border-blue-200 font-mono text-sm text-blue-700">
                R = {r.R} ({r.label})
              </span>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          {QUANTILE_METRICS.map(m => <MetricCard key={m.name} metric={m} accent="text-purple-700" />)}
        </div>
      </section>

      {/* 层 3：方法可用性视角 */}
      <section>
        <h2 className="text-lg font-bold text-slate-900 mb-1">方法可用性视角</h2>
        <p className="text-sm text-slate-500 mb-4">回答：方法是否可用、是否稳定？</p>

        {/* 三态互斥 */}
        <div className="mb-4 p-4 rounded-xl bg-slate-50 border border-slate-200">
          <div className="text-sm font-bold text-slate-800 mb-3">三态互斥：每个样本恰好属于 success / failure / outlier 之一</div>
          <div className="text-xs text-slate-500 mb-3 font-mono">failure_count + outlier_count + success_count = total_count</div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {STATUS_DEFS.map(s => (
              <div key={s.status} className={cn('p-3 rounded-xl border', s.color)}>
                <div className="font-mono font-bold text-sm mb-1">{s.label} ({s.status})</div>
                <div className="text-xs leading-relaxed">{s.desc}</div>
              </div>
            ))}
          </div>
          <div className="mt-3 text-xs text-slate-500">
            判定顺序：先检查物理约束（beta/eta &gt; 0, gamma finite, converged） &rarr; 再检查 NE &gt; 1.0。
            精度指标（NE、MAE、RMSE、分位点误差等）仅统计 success 样本。
          </div>
        </div>

        <div className="space-y-4">
          {AVAILABILITY_METRICS.map(m => <MetricCard key={m.name} metric={m} accent="text-emerald-700" />)}
        </div>
      </section>

      {/* 单参数基础指标 */}
      <section>
        <h2 className="text-lg font-bold text-slate-900 mb-1">单参数基础指标</h2>
        <p className="text-sm text-slate-500 mb-4">
          用于单参数分析场景。注意：这些指标不适合跨参数横向比较（beta/eta/gamma 量纲和数值范围不同），
          跨方法横向比较应使用 NE。
        </p>
        <div className="space-y-4">
          {SUPPLEMENTARY_METRICS.map(m => <MetricCard key={m.name} metric={m} accent="text-slate-600" />)}
        </div>
      </section>

      {/* 已废弃指标 */}
      <section>
        <h2 className="text-lg font-bold text-slate-900 mb-1">已废弃指标</h2>
        <p className="text-sm text-slate-500 mb-4">以下指标已被新体系替代，保留供历史参考。</p>
        <div className="space-y-4">
          {DEPRECATED_METRICS.map(m => (
            <div key={m.name} className="p-5 rounded-2xl bg-red-50/50 border border-red-200 opacity-75">
              <div className="flex items-baseline gap-2 mb-2">
                <span className="font-mono font-bold text-base text-red-400 line-through">{m.name}</span>
                <span className="text-sm text-red-400">{m.nameCn}</span>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 px-4 py-3 text-center mb-2">
                <Latex math={m.latex} block />
              </div>
              <p className="text-sm text-slate-500 leading-relaxed">{m.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 指标图谱 */}
      <section>
        <h2 className="text-lg font-bold text-slate-900 mb-2">指标图谱</h2>
        <p className="text-sm text-slate-500 mb-4">
          各视角使用的核心指标一览。精度指标仅统计 success 样本。
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr>
                <th className="px-4 py-2 text-xs font-bold text-slate-400 uppercase tracking-wider border-b-2 border-slate-200 bg-slate-50 text-left">
                  指标
                </th>
                <th className="px-3 py-2 text-xs font-bold text-blue-600 uppercase tracking-wider border-b-2 border-slate-200 bg-blue-50/50 text-center">
                  参数视角
                </th>
                <th className="px-3 py-2 text-xs font-bold text-purple-600 uppercase tracking-wider border-b-2 border-slate-200 bg-purple-50/50 text-center">
                  分位点视角
                </th>
                <th className="px-3 py-2 text-xs font-bold text-emerald-600 uppercase tracking-wider border-b-2 border-slate-200 bg-emerald-50/50 text-center">
                  可用性视角
                </th>
                <th className="px-3 py-2 text-xs font-bold text-slate-400 uppercase tracking-wider border-b-2 border-slate-200 bg-slate-50 text-center">
                  横向比较
                </th>
              </tr>
            </thead>
            <tbody>
              {[
                { name: 'NE', param: true, quantile: false, avail: false, compare: true },
                { name: 'Bias / MAE / RMSE', param: true, quantile: false, avail: false, compare: false },
                { name: 'NQE_R', param: false, quantile: true, avail: false, compare: true },
                { name: 'RE_R', param: false, quantile: true, avail: false, compare: false },
                { name: 'Bias_QR / MAE_QR / RMSE_QR', param: false, quantile: true, avail: false, compare: false },
                { name: 'Failure Rate', param: false, quantile: false, avail: true, compare: true },
                { name: 'Outlier Rate', param: false, quantile: false, avail: true, compare: true },
                { name: 'Time', param: false, quantile: false, avail: true, compare: false },
              ].map(row => (
                <tr key={row.name} className="hover:bg-slate-50/50">
                  <td className="px-4 py-2.5 font-mono font-bold text-slate-900 border-b border-slate-100">
                    {row.name}
                  </td>
                  {([row.param, row.quantile, row.avail, row.compare] as const).map((val, i) => (
                    <td key={i} className="px-3 py-2.5 border-b border-slate-100 text-center">
                      {val ? <span className="text-emerald-600 text-sm">&#10003;</span> : <span className="text-slate-200 text-xs">&mdash;</span>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* 开发规范 */}
      <section className="p-5 rounded-2xl bg-blue-50 border border-blue-100">
        <h3 className="text-sm font-bold text-blue-800 mb-2">开发规范</h3>
        <ul className="text-sm text-blue-700 space-y-1.5">
          <li>• 跨方法横向比较 &rarr; 使用 NE + NQE_R + Failure/Outlier Rate，不要只用 MSE 或 MAE</li>
          <li>• 单参数分析 &rarr; 可使用 MSE/MAE/MRE/bias/std，但需注明不适用于跨参数比较</li>
          <li>
            • 使用指标 &rarr; 调用共享函数（前端{' '}
            <code className="bg-blue-100 px-1 rounded">src/lib/metrics.ts</code>，后端{' '}
            <code className="bg-blue-100 px-1 rounded">python/studies/common/metrics.py</code>）
          </li>
          <li>• 禁止在组件或脚本中内联重复实现指标计算</li>
          <li>• 新增指标 &rarr; 必须先更新本页面</li>
          <li>• MRE 不适用于 gamma=0 的综合比较，跨参数场景请用 NE</li>
        </ul>
      </section>
    </div>
  )
}
