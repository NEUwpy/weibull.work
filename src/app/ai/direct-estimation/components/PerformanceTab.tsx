/**
 * 性能展示 Tab — 直接估计
 *
 * 散点图、误差直方图、按维度切换的精度表（支持 validation_type 切换）
 */
"use client"

import React, { useEffect, useState, useMemo } from 'react'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { BoxPlot, BoxPlotPoint } from '@/components/ai/charts/BoxPlot'
import { Histogram } from '@/components/ai/charts/Histogram'
import {
  loadJSON,
  schemeMetricsPath, generalizationMetricsPath,
  DirectEstimationMetricsData,
  GeneralizationMetricsData, GeneralizationMetricsByN,
} from '@/lib/ai-data'

const SAMPLE_SIZES = [5, 7, 10, 15]
const PARAM_NAMES = ['beta', 'eta', 'gamma'] as const
const PARAM_LABELS: Record<string, string> = { beta: 'β', eta: 'η', gamma: 'γ' }

interface PreprocessedData {
  scatter: Record<string, Record<string, Record<string, { x: number[]; y: number[] }>>>
  boxplot: Record<string, Record<string, BoxPlotPoint[]>>
  histograms: Record<string, { bins: { x0: number; x1: number; count: number }[]; mean: number; std: number; count: number }>
  breakdown: {
    by_n: Record<string, { mae_beta: number; mae_eta: number; mae_gamma: number; mre_beta: number; mre_eta: number; mre_gamma: number; count: number }>
    by_beta: Record<string, { mae_beta: number; mae_eta: number; mae_gamma: number; mre_beta: number; mre_eta: number; mre_gamma: number; count: number }>
    by_eta: Record<string, { mae_beta: number; mae_eta: number; mae_gamma: number; mre_beta: number; mre_eta: number; mre_gamma: number; count: number }>
  }
}

type DimensionKey = 'n' | 'beta' | 'eta'
const DIM_OPTIONS: { key: DimensionKey; label: string }[] = [
  { key: 'n', label: '按样本量 n' },
  { key: 'beta', label: '按 β 真值' },
  { key: 'eta', label: '按 η 真值' },
]

const VALIDATION_TYPE_OPTIONS = [
  { key: 'ig', label: '组内' },
  { key: 'ip', label: '插值' },
  { key: 'ex', label: '外推' },
] as const

export function PerformanceTab({ scheme = 'a-1' }: { scheme?: string }) {
  const [preprocessed, setPreprocessed] = useState<PreprocessedData | null>(null)
  const [genMetrics, setGenMetrics] = useState<GeneralizationMetricsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [dim, setDim] = useState<DimensionKey>('n')
  const [validationType, setValidationType] = useState<string>('ig')

  useEffect(() => {
    async function load() {
      try {
        const schemeKey = scheme.replace('-', '')
        const [prepData, genData] = await Promise.all([
          loadJSON<PreprocessedData>(`/ai/data/direct_estimation_${schemeKey}_preprocessed.json`),
          loadJSON<GeneralizationMetricsData>(generalizationMetricsPath()).catch(() => null),
        ])
        setPreprocessed(prepData)
        setGenMetrics(genData)
      } catch {} finally {
        setLoading(false)
      }
    }
    load()
  }, [scheme])

  // 按维度分组计算精度 — 优先用预处理数据
  const dimensionRows = useMemo(() => {
    if (!preprocessed) return []

    // dim=n: 优先用泛化数据，否则用预处理 by_n
    if (dim === 'n') {
      if (genMetrics) {
        const schemeKey = scheme.replace('-', '')
        const typeData = genMetrics.results?.[schemeKey]?.[validationType]
        if (typeData?.by_n) {
          return SAMPLE_SIZES.map(n => {
            const m = typeData.by_n[`n${n}`] as GeneralizationMetricsByN | undefined
            if (!m) return null
            return {
              label: `n=${n}`,
              mae_beta: m.mae_beta, mae_eta: m.mae_eta, mae_gamma: m.mae_gamma,
              mre_beta: m.mre_beta, mre_eta: m.mre_eta, mre_gamma: m.mre_gamma,
              count: m.count,
            }
          }).filter(Boolean) as Array<{
            label: string; mae_beta: number; mae_eta: number; mae_gamma: number
            mre_beta: number; mre_eta: number; mre_gamma: number; count: number
          }>
        }
      }
      return Object.entries(preprocessed.breakdown.by_n)
        .map(([n, m]) => ({
          label: `n=${n}`,
          mae_beta: m.mae_beta, mae_eta: m.mae_eta, mae_gamma: m.mae_gamma,
          mre_beta: m.mre_beta, mre_eta: m.mre_eta, mre_gamma: m.mre_gamma,
          count: m.count,
        }))
    }

    // dim=beta/eta: 直接用预处理 breakdown
    const bd = dim === 'beta' ? preprocessed.breakdown.by_beta : preprocessed.breakdown.by_eta
    return Object.entries(bd)
      .map(([k, m]) => ({
        label: dim === 'beta' ? `β=${k}` : `η=${k}`,
        sortVal: Number(k),
        mae_beta: m.mae_beta, mae_eta: m.mae_eta, mae_gamma: m.mae_gamma,
        mre_beta: m.mre_beta, mre_eta: m.mre_eta, mre_gamma: m.mre_gamma,
        count: m.count,
      }))
      .sort((a, b) => (a as { sortVal: number }).sortVal - (b as { sortVal: number }).sortVal)
  }, [dim, preprocessed, genMetrics, scheme, validationType])

  if (loading) {
    return <div className="text-center py-12 text-slate-400">加载性能数据中...</div>
  }

  const hasData = !!preprocessed

  return (
    <div className="space-y-6">
      {/* 箱型图：预测 vs 真值 — 按真值分组看预测分布，支持 validationType 切换 */}
      {hasData && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-bold text-slate-700">预测分布（箱型图）</h4>
            <div className="flex rounded-lg border border-slate-200 overflow-hidden text-xs">
              {VALIDATION_TYPE_OPTIONS.map(opt => (
                <button
                  key={opt.key}
                  onClick={() => setValidationType(opt.key)}
                  className={`px-3 py-1 font-medium transition-colors ${validationType === opt.key ? 'bg-cyan-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'}`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {(PARAM_NAMES as readonly string[]).map(param => {
              const bpData = preprocessed!.boxplot?.[validationType]?.[param]
              if (!bpData || bpData.length === 0) return null

              // 计算 y 轴范围：包含真值和预测范围
              const allVals = bpData.flatMap(d => [d.true_val, d.min, d.max])
              const vMin = Math.min(...allVals)
              const vMax = Math.max(...allVals)
              const pad = (vMax - vMin) * 0.1 || 1

              return (
                <ChartCard key={param} title={`${PARAM_LABELS[param]}: 预测分布`}>
                  <BoxPlot
                    data={bpData}
                    xLabel={`真值 ${PARAM_LABELS[param]}`}
                    yLabel={`预测 ${PARAM_LABELS[param]}`}
                    color="#0891b2"
                    showDiagonal
                    yAxisDomain={[vMin - pad, vMax + pad]}
                  />
                  <div className="text-center mt-1 text-xs text-slate-400">
                    {VALIDATION_TYPE_OPTIONS.find(o => o.key === validationType)?.label}验证 · 箱子=Q1~Q3 · 线=中位数 · 虚线=须
                  </div>
                </ChartCard>
              )
            })}
          </div>
        </div>
      )}

      {/* 误差分布直方图 — 使用预处理 bin 数据 */}
      {hasData && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {(PARAM_NAMES as readonly string[]).map(param => {
            const h = preprocessed!.histograms[param]
            if (!h || h.count === 0) return null

            return (
              <ChartCard key={param} title={`${PARAM_LABELS[param]}: 相对误差分布 (%)`}>
                <Histogram
                  precomputedBins={h.bins}
                  precomputedMean={h.mean}
                  xLabel="相对误差 (%)"
                  yLabel="频次"
                  color="#0891b2"
                  showMean
                />
                <div className="flex justify-center gap-4 mt-1 text-xs text-slate-400">
                  <span>均值: {h.mean.toFixed(2)}%</span>
                  <span>标准差: {h.std.toFixed(2)}%</span>
                  <span>样本数: {h.count}</span>
                </div>
              </ChartCard>
            )
          })}
        </div>
      )}

      {/* 按维度切换的精度表 */}
      {(dimensionRows.length > 0 || genMetrics) && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-bold text-slate-700">精度分解</h4>
            <div className="flex items-center gap-2">
              {/* 验证类型切换 */}
              {genMetrics && (
                <div className="flex rounded-lg border border-slate-200 overflow-hidden text-xs">
                  {VALIDATION_TYPE_OPTIONS.map(opt => (
                    <button
                      key={opt.key}
                      onClick={() => setValidationType(opt.key)}
                      className={`px-3 py-1 font-medium transition-colors ${validationType === opt.key ? 'bg-cyan-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'}`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              )}
              <div className="flex rounded-lg border border-slate-200 overflow-hidden text-xs">
                {DIM_OPTIONS.map(opt => (
                  <button
                    key={opt.key}
                    onClick={() => setDim(opt.key)}
                    className={`px-3 py-1 font-medium transition-colors ${dim === opt.key ? 'bg-cyan-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'}`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">
                    {dim === 'n' ? '样本量' : dim === 'beta' ? 'β 真值' : 'η 真值'}
                  </th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MAE(β)</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MAE(η)</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MRE(β)</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MRE(η)</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">样本数</th>
                </tr>
              </thead>
              <tbody>
                {dimensionRows.map((row, i) => (
                  <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                    <td className="border border-slate-200 px-3 py-2 font-mono font-bold">{row.label}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{row.mae_beta.toFixed(4)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{row.mae_eta.toFixed(1)}</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{(row.mre_beta * 100).toFixed(1)}%</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono">{(row.mre_eta * 100).toFixed(1)}%</td>
                    <td className="border border-slate-200 px-3 py-2 text-right font-mono text-slate-400">{row.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-slate-400 mt-2">
            MRE = 平均相对误差 = mean(|pred - true| / true) × 100%
            {genMetrics && ` | ${VALIDATION_TYPE_OPTIONS.find(o => o.key === validationType)?.label}验证`}
          </p>
        </div>
      )}

      {/* 无数据提示 */}
      {!hasData && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center">
          <p className="text-sm text-slate-400">性能数据未找到</p>
          <p className="text-xs text-slate-300 mt-1">请先运行 generate_preprocessed_data.py 生成预处理数据</p>
        </div>
      )}
    </div>
  )
}
