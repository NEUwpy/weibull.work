/**
 * 方法对比 Tab — 直接估计
 *
 * 不同方案/方法的对比
 */
"use client"

import React, { useEffect, useState } from 'react'
import { loadJSON, directEstimationMetricsPath, DirectEstimationMetricsData } from '@/lib/ai-data'

const SAMPLE_SIZES = [5, 7, 10, 15]
const SCHEMES = ['a1', 'a2', 'a3', 'b1', 'b2', 'c1', 'c2', 'c3'] as const
const SCHEME_LABELS: Record<string, string> = {
  a1: 'A-1 原始样本',
  a2: 'A-2 除以均值',
  a3: 'A-3 去位置',
  b1: 'B-1 填充+掩码',
  b2: 'B-2 除以均值+掩码',
  c1: 'C-1 基础统计量',
  c2: 'C-2 扩展统计量',
  c3: 'C-3 最大化统计量',
}
const SCHEME_INPUTS: Record<string, string> = {
  a1: '[t1, ..., tn]',
  a2: '[t1/t̄, ..., tn/t̄, t̄]',
  a3: '[t1-t_min, ..., tn-t_min]',
  b1: '[t1,...,tn,0,...,0, mask]',
  b2: '[t1/t̄,...,tn/t̄,0,...,0, t̄, mask]',
  c1: '[mean, std, min, max]',
  c2: '[mean, std, min, max, skew, kurt, median]',
  c3: 'C-2 + [Q1, Q3, IQR, CV]',
}

export function CompareTab() {
  const [metrics, setMetrics] = useState<Map<string, DirectEstimationMetricsData>>(new Map())
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      const mMap = new Map<string, DirectEstimationMetricsData>()

      // 加载按 n 独立模型的方案 (A-1, A-2, A-3, C-1, C-2, C-3)
      for (const scheme of ['a1', 'a2', 'a3', 'c1', 'c2', 'c3']) {
        for (const n of SAMPLE_SIZES) {
          const suffix = scheme === 'a1' ? '' : `_${scheme}`
          const key = `n${n}_${scheme}`
          try {
            const path = `/ai/data/direct_estimation_n${n}${suffix}_metrics.json`
            const data = await loadJSON<DirectEstimationMetricsData>(path)
            mMap.set(key, data)
          } catch {}
        }
      }

      // 加载统一模型的方案 (B-1, B-2)
      for (const scheme of ['b1', 'b2']) {
        try {
          const data = await loadJSON<DirectEstimationMetricsData>(`/ai/data/direct_estimation_${scheme}_metrics.json`)
          mMap.set(scheme, data)
        } catch {}
      }

      setMetrics(mMap)
      setLoading(false)
    }
    load()
  }, [])

  if (loading) {
    return <div className="text-center py-12 text-slate-400">加载对比数据中...</div>
  }

  // 获取某个方案某个 n 的指标
  function getMetric(scheme: string, n: number): DirectEstimationMetricsData | undefined {
    if (scheme === 'b1' || scheme === 'b2') {
      // 统一模型
      return metrics.get(scheme)
    }
    return metrics.get(`n${n}_${scheme}`)
  }

  return (
    <div className="space-y-6">
      <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-3 text-sm text-cyan-700">
        方案对比：在同一参数空间下，比较不同预处理方案的估计精度。
      </div>

      {/* 方案总览 */}
      <div>
        <h3 className="text-base font-bold text-slate-800 mb-3">方案总览</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">方案</th>
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">输入形式</th>
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">模型类型</th>
                <th className="border border-slate-200 px-3 py-2 text-center font-bold text-slate-600">状态</th>
              </tr>
            </thead>
            <tbody>
              {[
                { id: 'a1', label: 'A-1', model: '按 n 独立模型', done: true },
                { id: 'a2', label: 'A-2', model: '按 n 独立模型', done: true },
                { id: 'a3', label: 'A-3', model: '按 n 独立模型', done: false },
                { id: 'b1', label: 'B-1', model: '统一模型', done: true },
                { id: 'b2', label: 'B-2', model: '统一模型', done: false },
                { id: 'c1', label: 'C-1', model: '按 n 独立模型', done: true },
                { id: 'c2', label: 'C-2', model: '按 n 独立模型', done: true },
                { id: 'c3', label: 'C-3', model: '按 n 独立模型', done: false },
              ].map((s, i) => (
                <tr key={s.id} className={i % 2 === 0 ? 'bg-cyan-50/50' : ''}>
                  <td className="border border-slate-200 px-3 py-2 font-mono font-bold">{s.label}</td>
                  <td className="border border-slate-200 px-3 py-2 font-mono text-xs">{SCHEME_INPUTS[s.id]}</td>
                  <td className="border border-slate-200 px-3 py-2 text-slate-600">{s.model}</td>
                  <td className={`border border-slate-200 px-3 py-2 text-center font-bold ${s.done ? 'text-green-600' : 'text-amber-500'}`}>
                    {s.done ? '已完成' : '待实验'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* MAE(β) 对比表 */}
      <div>
        <h3 className="text-base font-bold text-slate-800 mb-3">MAE(β) 对比</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">方案</th>
                {SAMPLE_SIZES.map(n => (
                  <th key={n} className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">n={n}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {SCHEMES.map(scheme => (
                <tr key={scheme} className={scheme === 'a1' ? 'bg-cyan-50' : ''}>
                  <td className="border border-slate-200 px-3 py-2 font-mono font-bold">{SCHEME_LABELS[scheme]}</td>
                  {SAMPLE_SIZES.map(n => {
                    const m = getMetric(scheme, n)
                    return (
                      <td key={n} className="border border-slate-200 px-3 py-2 text-right font-mono">
                        {m ? m.metrics.mae_beta?.toFixed(4) : '—'}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* MAE(η) 对比表 */}
      <div>
        <h3 className="text-base font-bold text-slate-800 mb-3">MAE(η) 对比</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">方案</th>
                {SAMPLE_SIZES.map(n => (
                  <th key={n} className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">n={n}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {SCHEMES.map(scheme => (
                <tr key={scheme} className={scheme === 'a1' ? 'bg-cyan-50' : ''}>
                  <td className="border border-slate-200 px-3 py-2 font-mono font-bold">{SCHEME_LABELS[scheme]}</td>
                  {SAMPLE_SIZES.map(n => {
                    const m = getMetric(scheme, n)
                    return (
                      <td key={n} className="border border-slate-200 px-3 py-2 text-right font-mono">
                        {m ? m.metrics.mae_eta?.toFixed(1) : '—'}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 结论 */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-3">实验结论</h4>
        <div className="text-xs text-slate-600 space-y-2">
          <p><strong>1. C-1 与 A-1 几乎相同</strong>：4 个统计量 [mean, std, min, max] 已经充分提取了 Weibull 参数信息。</p>
          <p><strong>2. A-2 对 η 变差</strong>：除以均值的预处理没有帮助，反而丢失了尺度信息。</p>
          <p><strong>3. C-2 无额外优势</strong>：偏度/峰度/中位数没有提供超出 C-1 的信息。</p>
          <p><strong>4. B-1 统一模型可行</strong>：一个模型覆盖所有 n，精度与独立模型几乎相同，实用性最强。</p>
        </div>
      </div>

      {/* AI vs 传统方法（待对比） */}
      <div>
        <h3 className="text-base font-bold text-slate-800 mb-3">AI vs 传统方法对比（待实现）</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">方法</th>
                <th className="border border-slate-200 px-3 py-2 text-center font-bold text-slate-600">类型</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MAE(β)</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MAE(η)</th>
                <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">推理时间</th>
                <th className="border border-slate-200 px-3 py-2 text-center font-bold text-slate-600">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr className="bg-cyan-50">
                <td className="border border-slate-200 px-3 py-2 font-bold text-cyan-700">AI 直接估计 (A-1)</td>
                <td className="border border-slate-200 px-3 py-2 text-center text-cyan-600">神经网络</td>
                <td className="border border-slate-200 px-3 py-2 text-right font-mono text-cyan-600">
                  {getMetric('a1', 10)?.metrics.mae_beta?.toFixed(4) ?? '—'}
                </td>
                <td className="border border-slate-200 px-3 py-2 text-right font-mono text-cyan-600">
                  {getMetric('a1', 10)?.metrics.mae_eta?.toFixed(1) ?? '—'}
                </td>
                <td className="border border-slate-200 px-3 py-2 text-right font-mono text-cyan-600">&lt;1ms</td>
                <td className="border border-slate-200 px-3 py-2 text-center text-green-600 font-bold">已完成</td>
              </tr>
              <tr>
                <td className="border border-slate-200 px-3 py-2 font-bold text-slate-700">MLE</td>
                <td className="border border-slate-200 px-3 py-2 text-center text-slate-600">迭代优化</td>
                <td className="border border-slate-200 px-3 py-2 text-right font-mono text-slate-400">—</td>
                <td className="border border-slate-200 px-3 py-2 text-right font-mono text-slate-400">—</td>
                <td className="border border-slate-200 px-3 py-2 text-right font-mono text-slate-400">—</td>
                <td className="border border-slate-200 px-3 py-2 text-center text-slate-400">待对比</td>
              </tr>
              <tr>
                <td className="border border-slate-200 px-3 py-2 font-bold text-slate-700">MDM</td>
                <td className="border border-slate-200 px-3 py-2 text-center text-slate-600">矩估计</td>
                <td className="border border-slate-200 px-3 py-2 text-right font-mono text-slate-400">—</td>
                <td className="border border-slate-200 px-3 py-2 text-right font-mono text-slate-400">—</td>
                <td className="border border-slate-200 px-3 py-2 text-right font-mono text-slate-400">—</td>
                <td className="border border-slate-200 px-3 py-2 text-center text-slate-400">待对比</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
