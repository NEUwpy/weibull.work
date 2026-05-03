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
  latex: string       // KaTeX 公式
  description: string
  usage: {
    methods_analysis: boolean
    methods_studies: boolean
    methods_verification: boolean
    m1_delta: boolean
    m1_param: boolean
    m3_performance: boolean
    m3_verification: boolean
    m3_compare: boolean
  }
}

const METRICS: MetricDef[] = [
  {
    name: 'MSE',
    latex: '\\text{MSE} = \\frac{1}{n}\\sum_{i=1}^{n} e_i^2',
    description: '均方误差，衡量估计值与真值的偏差平方均值。对大偏差敏感，适合检测异常估计。',
    usage: { methods_analysis: true, methods_studies: false, methods_verification: false, m1_delta: true, m1_param: true, m3_performance: false, m3_verification: false, m3_compare: false },
  },
  {
    name: 'MAE',
    latex: '\\text{MAE} = \\frac{1}{n}\\sum_{i=1}^{n} r_i',
    description: '平均绝对误差，直观反映估计偏差幅度。与原始数据同量纲，易于解释。',
    usage: { methods_analysis: true, methods_studies: false, methods_verification: false, m1_delta: true, m1_param: true, m3_performance: true, m3_verification: true, m3_compare: true },
  },
  {
    name: 'MRE',
    latex: '\\text{MRE} = \\frac{1}{n}\\sum_{i=1}^{n}\\frac{r_i}{|y_i|}',
    description: '平均相对误差，消除量纲影响，便于跨参数（β vs η）比较。',
    usage: { methods_analysis: false, methods_studies: false, methods_verification: false, m1_delta: false, m1_param: true, m3_performance: true, m3_verification: true, m3_compare: true },
  },
  {
    name: 'total_relative_mse',
    latex: '\\text{TRMSE} = \\sum_{p \\in \\{\\beta,\\eta,\\gamma\\}} \\left(\\frac{\\hat{p} - p}{p}\\right)^2',
    description: '相对 MSE 三参数求和，聚合指标。用于跨方案横向对比的单一排序依据。',
    usage: { methods_analysis: false, methods_studies: false, methods_verification: false, m1_delta: false, m1_param: false, m3_performance: true, m3_verification: false, m3_compare: true },
  },
  {
    name: 'bias',
    latex: '\\text{bias}(\\hat{y}) = \\frac{1}{n}\\sum_{i=1}^{n} e_i',
    description: '系统偏差。正值 = 高估，负值 = 低估。接近 0 表示无系统性偏移。',
    usage: { methods_analysis: true, methods_studies: true, methods_verification: false, m1_delta: true, m1_param: true, m3_performance: false, m3_verification: false, m3_compare: false },
  },
  {
    name: 'std',
    latex: '\\text{std}(\\hat{y}) = \\sqrt{\\frac{1}{n}\\sum_{i=1}^{n}(\\hat{y}_i - \\bar{\\hat{y}})^2}',
    description: '标准差，衡量估计的离散程度。越小表示方法越稳定。',
    usage: { methods_analysis: true, methods_studies: true, methods_verification: false, m1_delta: true, m1_param: true, m3_performance: false, m3_verification: false, m3_compare: false },
  },
  {
    name: 'CI99',
    latex: '\\text{CI}_{99} = [P_{0.5}(e_i),\\; P_{99.5}(e_i)]',
    description: '对误差序列取第 0.5 和 99.5 百分位数作为区间端点。',
    usage: { methods_analysis: false, methods_studies: true, methods_verification: false, m1_delta: false, m1_param: false, m3_performance: false, m3_verification: false, m3_compare: false },
  },
  {
    name: 'P95',
    latex: '\\text{P}_{95} = P_{95}(r_i)',
    description: '对绝对误差序列取第 95 百分位数。',
    usage: { methods_analysis: true, methods_studies: false, methods_verification: false, m1_delta: false, m1_param: false, m3_performance: false, m3_verification: false, m3_compare: false },
  },
  {
    name: '改善率',
    latex: '\\text{改善率} = \\frac{\\text{MSE}_{\\text{fixed}} - \\text{MSE}_{\\text{ai}}}{\\text{MSE}_{\\text{fixed}}} \\times 100\\%',
    description: 'AI 相对固定值基线的改善百分比。> 0 表示 AI 优于基线。',
    usage: { methods_analysis: false, methods_studies: false, methods_verification: false, m1_delta: false, m1_param: true, m3_performance: false, m3_verification: false, m3_compare: true },
  },
  {
    name: '成功率',
    latex: '\\text{成功率} = \\frac{n_{\\text{success}}}{n_{\\text{total}}} \\times 100\\%',
    description: '方法求解成功的比例。失败样本不计入精度统计。',
    usage: { methods_analysis: false, methods_studies: false, methods_verification: false, m1_delta: false, m1_param: false, m3_performance: false, m3_verification: false, m3_compare: true },
  },
]

const USAGE_COLUMNS = [
  { key: 'methods_analysis' as const, label: '结果分析', group: 'Methods' },
  { key: 'methods_studies' as const, label: '适用范围', group: 'Methods' },
  { key: 'methods_verification' as const, label: '可信性验证', group: 'Methods' },
  { key: 'm1_delta' as const, label: '偏移量精度', group: 'M1' },
  { key: 'm1_param' as const, label: '三参数精度', group: 'M1' },
  { key: 'm3_performance' as const, label: '性能展示', group: 'M3' },
  { key: 'm3_verification' as const, label: '可信性验证', group: 'M3' },
  { key: 'm3_compare' as const, label: '方法对比', group: 'M3' },
]

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
          定义系统所有评价指标的公式、含义与使用范围。本页面是指标的唯一定义源（single source of truth）。
        </p>
      </div>

      {/* 基础定义 */}
      <section>
        <h2 className="text-lg font-bold text-slate-900 mb-4">基础定义</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="p-5 rounded-2xl bg-slate-50 border border-slate-100">
            <div className="font-mono font-bold text-slate-900 text-base mb-2">误差 error</div>
            <div className="bg-white rounded-xl border border-slate-200 px-4 py-3 text-center mb-2">
              <Latex math="e_i = \hat{y}_i - y_i" block />
            </div>
            <p className="text-sm text-slate-600">估计值减真值，有正有负。正值 = 高估，负值 = 低估。</p>
          </div>
          <div className="p-5 rounded-2xl bg-slate-50 border border-slate-100">
            <div className="font-mono font-bold text-slate-900 text-base mb-2">绝对误差 absolute error</div>
            <div className="bg-white rounded-xl border border-slate-200 px-4 py-3 text-center mb-2">
              <Latex math="r_i = |\hat{y}_i - y_i|" block />
            </div>
            <p className="text-sm text-slate-600">误差取绝对值，恒 ≥ 0。反映偏差幅度，不区分高估/低估。</p>
          </div>
        </div>
      </section>

      {/* 指标定义表 */}
      <section>
        <h2 className="text-lg font-bold text-slate-900 mb-4">指标定义</h2>
        <div className="space-y-4">
          {METRICS.map(m => (
            <div
              key={m.name}
              className="flex flex-col lg:flex-row gap-4 p-5 rounded-2xl bg-slate-50 border border-slate-100"
            >
              {/* 左侧：名称 + 公式 */}
              <div className="lg:w-[320px] shrink-0">
                <div className="font-mono font-bold text-slate-900 text-base mb-2">{m.name}</div>
                <div className="bg-white rounded-xl border border-slate-200 px-4 py-3 text-center">
                  <Latex math={m.latex} block />
                </div>
              </div>
              {/* 右侧：含义 */}
              <div className="flex-1 flex items-center">
                <p className="text-sm text-slate-600 leading-relaxed">{m.description}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 指标图谱 */}
      <section>
        <h2 className="text-lg font-bold text-slate-900 mb-2">指标图谱</h2>
        <p className="text-sm text-slate-500 mb-4">
          各模块 / Tab 使用的指标一览。✅ 表示该模块使用此指标。
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              {/* 第一行：模块分组 */}
              <tr>
                <th
                  className="px-4 py-2 text-xs font-bold text-slate-400 uppercase tracking-wider border-b-2 border-slate-200 bg-slate-50 w-[160px]"
                  rowSpan={2}
                >
                  指标
                </th>
                <th colSpan={3} className="px-2 py-2 text-xs font-bold text-blue-600 uppercase tracking-wider border-b border-slate-200 bg-blue-50/50 text-center">
                  Methods
                </th>
                <th colSpan={2} className="px-2 py-2 text-xs font-bold text-purple-600 uppercase tracking-wider border-b border-slate-200 bg-purple-50/50 text-center">
                  M1 关系建立
                </th>
                <th colSpan={3} className="px-2 py-2 text-xs font-bold text-emerald-600 uppercase tracking-wider border-b border-slate-200 bg-emerald-50/50 text-center">
                  M3 直接估计
                </th>
              </tr>
              {/* 第二行：Tab 名称 */}
              <tr>
                {USAGE_COLUMNS.map(col => (
                  <th
                    key={col.key}
                    className="px-2 py-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider border-b-2 border-slate-200 bg-slate-50/50 text-center whitespace-nowrap"
                  >
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {METRICS.map(m => (
                <tr key={m.name} className="hover:bg-slate-50/50">
                  <td className="px-4 py-2.5 font-mono font-bold text-slate-900 border-b border-slate-100">
                    {m.name}
                  </td>
                  {USAGE_COLUMNS.map(col => (
                    <td key={col.key} className="px-2 py-2.5 border-b border-slate-100 text-center">
                      {m.usage[col.key] ? (
                        <span className="text-emerald-600 text-sm">✅</span>
                      ) : (
                        <span className="text-slate-200 text-xs">—</span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* 使用说明 */}
      <section className="p-5 rounded-2xl bg-blue-50 border border-blue-100">
        <h3 className="text-sm font-bold text-blue-800 mb-2">开发规范</h3>
        <ul className="text-sm text-blue-700 space-y-1.5">
          <li>• 新增指标 → 必须先更新本页面</li>
          <li>
            • 使用指标 → 调用共享函数（前端{' '}
            <code className="bg-blue-100 px-1 rounded">src/lib/metrics.ts</code>，后端{' '}
            <code className="bg-blue-100 px-1 rounded">python/studies/common/metrics.py</code>）
          </li>
          <li>• 禁止在组件或脚本中内联重复实现指标计算</li>
        </ul>
      </section>
    </div>
  )
}
