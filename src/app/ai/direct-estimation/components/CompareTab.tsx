/**
 * 方法对比 Tab — 直接估计
 *
 * 对比维度：
 * 1. 8种方案精度对比
 * 2. M1最优方案 vs M3最优方案精度对比
 * 切换：聚合/三参数 × 绝对/相对
 */
"use client"

import React, { useEffect, useState } from 'react'
import { loadJSON, DirectEstimationMetricsData } from '@/lib/ai-data'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { MultiLineChart } from '@/components/ai/charts/MultiLineChart'

const SAMPLE_SIZES = [5, 7, 10, 15]
const SCHEMES = ['a1', 'a2', 'a3', 'b1', 'b2', 'c1', 'c2', 'c3'] as const
const SCHEME_LABELS: Record<string, string> = {
  a1: 'A-1 原始样本', a2: 'A-2 除以均值', a3: 'A-3 去位置',
  b1: 'B-1 填充+掩码', b2: 'B-2 除以均值+掩码',
  c1: 'C-1 基础统计量', c2: 'C-2 扩展统计量', c3: 'C-3 最大化统计量',
}
const SCHEME_INPUTS: Record<string, string> = {
  a1: '[t1, ..., tn]', a2: '[t1/t̄, ..., tn/t̄, t̄]', a3: '[t1-t_min, ..., tn-t_min]',
  b1: '[t1,...,tn,0,...,0, mask]', b2: '[t1/t̄,...,tn/t̄,0,...,0, t̄, mask]',
  c1: '[mean, std, min, max]', c2: '[mean, std, min, max, skew, kurt, median]',
  c3: 'C-2 + [Q1, Q3, IQR, CV]',
}

interface ParamMetrics { mae: number; mre: number }
interface SchemeEntry {
  per_param: Record<string, ParamMetrics>
  aggregate: { total_relative_mse: number }
}
interface M1vsM3Entry {
  mdm: { label: string; per_param: Record<string, ParamMetrics>; aggregate: { total_relative_mse: number }; success_rate: number; avg_time_ms: number }
  ai_direct: { label: string; per_param: Record<string, ParamMetrics>; aggregate: { total_relative_mse: number }; success_rate: number; avg_time_ms: number }
}

const PARAMS = ['beta', 'eta'] as const
const PARAM_LABELS: Record<string, string> = { beta: 'β', eta: 'η' }

export function CompareTab() {
  const [metrics, setMetrics] = useState<Map<string, DirectEstimationMetricsData>>(new Map())
  const [schemeData, setSchemeData] = useState<Record<string, Record<string, SchemeEntry>>>({})
  const [m1v3Data, setM1v3Data] = useState<Record<string, M1vsM3Entry>>({})
  const [viewMode, setViewMode] = useState<'aggregate' | 'per_param'>('aggregate')
  const [metricMode, setMetricMode] = useState<'absolute' | 'relative'>('absolute')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      const mMap = new Map<string, DirectEstimationMetricsData>()
      for (const scheme of ['a1', 'a2', 'a3', 'c1', 'c2', 'c3']) {
        for (const n of SAMPLE_SIZES) {
          const suffix = scheme === 'a1' ? '' : `_${scheme}`
          try {
            const data = await loadJSON<DirectEstimationMetricsData>(`/ai/data/direct_estimation_n${n}${suffix}_metrics.json`)
            mMap.set(`n${n}_${scheme}`, data)
          } catch {}
        }
      }
      for (const scheme of ['b1', 'b2']) {
        try {
          const data = await loadJSON<DirectEstimationMetricsData>(`/ai/data/direct_estimation_${scheme}_metrics.json`)
          mMap.set(scheme, data)
        } catch {}
      }
      setMetrics(mMap)

      try {
        const sd = await loadJSON<Record<string, Record<string, SchemeEntry>>>('/ai/data/m3_scheme_comparison.json')
        setSchemeData(sd)
      } catch {}

      try {
        const mv = await loadJSON<Record<string, M1vsM3Entry>>('/ai/data/m1_vs_m3_best.json')
        setM1v3Data(mv)
      } catch {}

      setLoading(false)
    }
    load()
  }, [])

  if (loading) return <div className="text-center py-12 text-slate-400">加载对比数据中...</div>

  function getMetric(scheme: string, n: number) {
    if (scheme === 'b1' || scheme === 'b2') return metrics.get(scheme)
    return metrics.get(`n${n}_${scheme}`)
  }

  function formatVal(val: number | null | undefined, mode: string): string {
    if (val == null) return '—'
    return mode === 'absolute' ? val.toFixed(4) : (val * 100).toFixed(1) + '%'
  }

  // 方案总览表
  const renderOverview = () => (
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
            {SCHEMES.map((s, i) => (
              <tr key={s} className={i % 2 === 0 ? 'bg-cyan-50/50' : ''}>
                <td className="border border-slate-200 px-3 py-2 font-mono font-bold">{SCHEME_LABELS[s]}</td>
                <td className="border border-slate-200 px-3 py-2 font-mono text-xs">{SCHEME_INPUTS[s]}</td>
                <td className="border border-slate-200 px-3 py-2 text-slate-600">{['b1','b2'].includes(s) ? '统一模型' : '按 n 独立模型'}</td>
                <td className="border border-slate-200 px-3 py-2 text-center font-bold text-green-600">已完成</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )

  // 切换控件
  const renderToggles = () => (
    <div className="flex items-center gap-3 flex-wrap">
      <div className="flex bg-slate-100 rounded-lg p-0.5">
        <button className={`px-3 py-1 text-xs rounded-md transition-colors ${viewMode === 'aggregate' ? 'bg-white text-slate-800 shadow-sm font-bold' : 'text-slate-500'}`} onClick={() => setViewMode('aggregate')}>聚合精度</button>
        <button className={`px-3 py-1 text-xs rounded-md transition-colors ${viewMode === 'per_param' ? 'bg-white text-slate-800 shadow-sm font-bold' : 'text-slate-500'}`} onClick={() => setViewMode('per_param')}>三参数精度</button>
      </div>
      <div className="flex bg-slate-100 rounded-lg p-0.5">
        <button className={`px-3 py-1 text-xs rounded-md transition-colors ${metricMode === 'absolute' ? 'bg-white text-slate-800 shadow-sm font-bold' : 'text-slate-500'}`} onClick={() => setMetricMode('absolute')}>MAE (绝对)</button>
        <button className={`px-3 py-1 text-xs rounded-md transition-colors ${metricMode === 'relative' ? 'bg-white text-slate-800 shadow-sm font-bold' : 'text-slate-500'}`} onClick={() => setMetricMode('relative')}>MRE (相对)</button>
      </div>
    </div>
  )

  // 8方案精度对比表
  const renderSchemeComparison = () => {
    if (Object.keys(schemeData).length === 0) return null
    const showParams = viewMode === 'per_param'
    const colSpan = showParams ? PARAMS.length + 1 : 1

    return (
      <div className="space-y-3">
        <h3 className="text-base font-bold text-slate-800">8 种方案精度对比</h3>
        {renderToggles()}
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">方案</th>
                {SAMPLE_SIZES.map(n => (
                  <th key={n} className="border border-slate-200 px-3 py-2 text-center font-bold text-slate-600" colSpan={colSpan}>n={n}</th>
                ))}
              </tr>
              {showParams && (
                <tr className="bg-slate-50">
                  <th className="border border-slate-200 px-3 py-2"></th>
                  {SAMPLE_SIZES.map(n => (
                    <React.Fragment key={n}>
                      {PARAMS.map(p => <th key={p} className="border border-slate-200 px-2 py-1 text-right font-bold text-slate-500 text-xs">{PARAM_LABELS[p]}</th>)}
                      <th className="border border-slate-200 px-2 py-1 text-right font-bold text-slate-500 text-xs">聚合</th>
                    </React.Fragment>
                  ))}
                </tr>
              )}
            </thead>
            <tbody>
              {SCHEMES.map((scheme, si) => (
                <tr key={scheme} className={si % 2 === 0 ? 'hover:bg-cyan-50' : 'bg-cyan-50/30 hover:bg-cyan-50'}>
                  <td className="border border-slate-200 px-3 py-2 font-mono font-bold text-xs">{SCHEME_LABELS[scheme]}</td>
                  {SAMPLE_SIZES.map(n => {
                    const entry = schemeData[scheme]?.[`n${n}`]
                    if (!entry) return <td key={n} colSpan={colSpan} className="border border-slate-200 px-2 py-1 text-center text-slate-400">—</td>
                    if (showParams) {
                      return (
                        <React.Fragment key={n}>
                          {PARAMS.map(p => (
                            <td key={p} className="border border-slate-200 px-2 py-1 text-right font-mono text-xs">
                              {formatVal(metricMode === 'absolute' ? entry.per_param[p]?.mae : entry.per_param[p]?.mre, metricMode)}
                            </td>
                          ))}
                          <td className="border border-slate-200 px-2 py-1 text-right font-mono text-xs font-bold">
                            {entry.aggregate.total_relative_mse.toFixed(4)}
                          </td>
                        </React.Fragment>
                      )
                    }
                    return (
                      <td key={n} className="border border-slate-200 px-3 py-2 text-right font-mono font-bold text-sm">
                        {entry.aggregate.total_relative_mse.toFixed(4)}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  // M1最优 vs M3最优
  const renderM1vsM3 = () => {
    if (Object.keys(m1v3Data).length === 0) return null
    const showParams = viewMode === 'per_param'
    const colSpan = showParams ? PARAMS.length + 1 : 1
    const methods = ['mdm', 'ai_direct'] as const

    return (
      <div className="space-y-3">
        <h3 className="text-base font-bold text-slate-800">M1 最优 vs M3 最优</h3>
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-700">
          MDM 在 M3 测试集（β∈{'{0.5,1,2,3,5}'}, η∈{'{100~5000}'}, γ∈{'{0~200}'}）上运行，成功率为 80-84%。
          AI 直接估计无需迭代，成功率 100%。
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">方法</th>
                {SAMPLE_SIZES.map(n => (
                  <th key={n} className="border border-slate-200 px-3 py-2 text-center font-bold text-slate-600" colSpan={colSpan}>n={n}</th>
                ))}
              </tr>
              {showParams && (
                <tr className="bg-slate-50">
                  <th className="border border-slate-200 px-3 py-2"></th>
                  {SAMPLE_SIZES.map(n => (
                    <React.Fragment key={n}>
                      {PARAMS.map(p => <th key={p} className="border border-slate-200 px-2 py-1 text-right font-bold text-slate-500 text-xs">{PARAM_LABELS[p]}</th>)}
                      <th className="border border-slate-200 px-2 py-1 text-right font-bold text-slate-500 text-xs">聚合</th>
                    </React.Fragment>
                  ))}
                </tr>
              )}
            </thead>
            <tbody>
              {methods.map((method, mi) => {
                const first = m1v3Data[`n${SAMPLE_SIZES[0]}`]?.[method]
                if (!first) return null
                const rowClass = mi === 0 ? 'hover:bg-blue-50' : 'bg-blue-50 hover:bg-blue-100'
                return (
                  <tr key={method} className={rowClass}>
                    <td className="border border-slate-200 px-3 py-2 font-bold text-slate-700">{first.label}</td>
                    {SAMPLE_SIZES.map(n => {
                      const entry = m1v3Data[`n${n}`]?.[method]
                      if (!entry) return <td key={n} colSpan={colSpan} className="border border-slate-200 px-2 py-1 text-center text-slate-400">—</td>
                      if (showParams) {
                        return (
                          <React.Fragment key={n}>
                            {PARAMS.map(p => (
                              <td key={p} className="border border-slate-200 px-2 py-1 text-right font-mono text-xs">
                                {formatVal(metricMode === 'absolute' ? entry.per_param[p]?.mae : entry.per_param[p]?.mre, metricMode)}
                              </td>
                            ))}
                            <td className="border border-slate-200 px-2 py-1 text-right font-mono text-xs font-bold">
                              {entry.aggregate.total_relative_mse.toFixed(4)}
                            </td>
                          </React.Fragment>
                        )
                      }
                      return (
                        <td key={n} className="border border-slate-200 px-3 py-2 text-right font-mono font-bold text-sm">
                          {entry.aggregate.total_relative_mse.toFixed(4)}
                        </td>
                      )
                    })}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  // 折线图
  const renderCharts = () => {
    const lineColors: Record<string, string> = {
      a1: '#6366f1', a2: '#8b5cf6', a3: '#a78bfa',
      b1: '#0891b2', b2: '#06b6d4',
      c1: '#f59e0b', c2: '#f97316', c3: '#ef4444',
    }
    const lineData_beta = SAMPLE_SIZES.map(n => {
      const row: Record<string, number> = { n }
      for (const scheme of SCHEMES) { const m = getMetric(scheme, n); if (m) row[scheme] = m.metrics.mae_beta }
      return row
    })
    const lineData_eta = SAMPLE_SIZES.map(n => {
      const row: Record<string, number> = { n }
      for (const scheme of SCHEMES) { const m = getMetric(scheme, n); if (m) row[scheme] = m.metrics.mae_eta }
      return row
    })
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="MAE(β) 随样本量变化">
          <MultiLineChart data={lineData_beta} lines={SCHEMES.map(s => ({ key: s, label: SCHEME_LABELS[s], color: lineColors[s] }))} xKey="n" xLabel="样本量 n" yLabel="MAE(β)" />
        </ChartCard>
        <ChartCard title="MAE(η) 随样本量变化">
          <MultiLineChart data={lineData_eta} lines={SCHEMES.map(s => ({ key: s, label: SCHEME_LABELS[s], color: lineColors[s] }))} xKey="n" xLabel="样本量 n" yLabel="MAE(η)" />
        </ChartCard>
      </div>
    )
  }

  // 结论
  const renderConclusion = () => (
    <>
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-3">实验结论</h4>
        <div className="text-xs text-slate-600 space-y-2">
          <p><strong>1. C-1 ≈ A-1</strong>：4 个统计量 [mean, std, min, max] 已经充分提取了 Weibull 参数信息。</p>
          <p><strong>2. B-1 统一模型可行</strong>：一个模型覆盖所有 n，精度与独立模型几乎相同，实用性最强。</p>
          <p><strong>3. A-2 对 η 变差</strong>：除以均值反而丢失尺度信息，对 η 估计不利。</p>
          <p><strong>4. C-2 无额外优势</strong>：偏度/峰度/中位数未提供超出 C-1 的新信息。</p>
          <p><strong>5. A-3 明显变差</strong>：去位置丢失绝对尺度信息，MAE(β) 几乎翻倍。</p>
          <p><strong>6. B-2 ≈ B-1</strong>：除以均值+掩码与原始+掩码精度相当。</p>
          <p><strong>7. C-3 ≈ C-1</strong>：Q1/Q3/IQR/CV 未提供超出基础统计量的新信息。</p>
        </div>
      </div>

      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-xs text-slate-600 space-y-2">
        <h4 className="text-sm font-bold text-slate-700">测试数据与指标说明</h4>
        <p><strong>测试集</strong>：β∈{'{0.5,1,2,3,5}'}, η∈{'{100,500,1000,3000,5000}'}, γ∈{'{0,50,100,200}'}, n∈{'{5,7,10,15}'}, 每组 100 个参数组合 × 100 次 MC = 10,000 样本</p>
        <p><strong>MAE</strong>：Mean Absolute Error = (1/N)Σ|θ̂-θ|，有量纲（β 无量纲，η 与数据同量纲）</p>
        <p><strong>MRE</strong>：Mean Relative Error = (1/N)Σ|θ̂-θ|/|θ|，无量纲。注意：当 γ=0 时 MRE 无意义，故 γ 的 MRE 不展示</p>
        <p><strong>聚合指标</strong>：相对 MSE = MSE(β)/mean(β)² + MSE(η)/mean(η)² + MSE(γ)/mean(γ)²，其中每个参数的相对 MSE = (1/N)Σ(θ̂-θ)² / mean(θ)²，无量纲</p>
      </div>
    </>
  )

  return (
    <div className="space-y-6">
      <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-3 text-sm text-cyan-700">
        方案对比：在同一参数空间下，比较不同预处理方案的估计精度，以及 AI 直接估计与传统 MDM 方法的精度差异。
      </div>

      {renderSchemeComparison()}
      {renderM1vsM3()}
      {renderOverview()}
      {renderCharts()}
      {renderConclusion()}
    </div>
  )
}
