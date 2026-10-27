"use client"

import React, { useMemo } from 'react'
import { Loader2, AlertTriangle, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'

// ============ Helper Functions ============

// 方法颜色映射
const METHOD_DENSITY_COLORS: Record<string, string> = {
  mle: '#3b82f6',    // blue
  wmle: '#10b981',   // emerald
  mdm: '#8b5cf6',    // purple
  lse: '#f59e0b',    // amber
  lre: '#ec4899',    // pink
  mmle: '#06b6d4',   // cyan
  mps: '#f43f5e',    // rose
  mm: '#84cc16',     // lime
  pwm: '#a855f7',    // violet
  grey: '#6b7280',   // gray
}

// 获取方法颜色
function getMethodColor(methodId: string, index: number): string {
  if (METHOD_DENSITY_COLORS[methodId]) {
    return METHOD_DENSITY_COLORS[methodId]
  }
  // 备用颜色
  const fallbackColors = ['#3b82f6', '#10b981', '#8b5cf6', '#f59e0b', '#ec4899', '#06b6d4']
  return fallbackColors[index % fallbackColors.length]
}

// ============ Types ============

interface SimulationRow {
  beta_true: number
  eta_true: number
  gamma?: number
  sample_size: number
  offset_value?: number
  sim_id: number
  est_beta: number | null
  est_eta: number | null
  est_gamma: number | null
  bias_beta: number | null
  bias_eta: number | null
  bias_gamma: number | null
  r_squared: number | null
}

interface MethodData {
  methodId: string
  chunkInfo: any
  csvData: SimulationRow[]
  isLoading: boolean
  needsSimulation: boolean
  isSimulating: boolean
  simulationProgress: number
  errorMessage?: string
  loadedFilename?: string  // 加载成功的文件名
}

interface StatsResult {
  key: string
  keyLabel: string
  count: number
  valid_count: number
  beta_true: number
  eta_true: number
  gamma: number
  est_beta_mean: number | null
  est_eta_mean: number | null
  est_gamma_mean: number | null
  bias_beta_mean: number | null
  bias_eta_mean: number | null
  bias_gamma_mean: number | null
  est_beta_std: number | null
  est_eta_std: number | null
  est_gamma_std: number | null
  est_beta_min: number | null
  est_beta_max: number | null
  est_eta_min: number | null
  est_eta_max: number | null
  est_gamma_min: number | null
  est_gamma_max: number | null
  est_beta_p005: number | null
  est_beta_p995: number | null
  est_eta_p005: number | null
  est_eta_p995: number | null
  est_gamma_p005: number | null
  est_gamma_p995: number | null
  [key: string]: number | string | null | undefined
}

// ============ Constants ============

const EST_PARAM_COLORS = {
  beta: { bg: 'bg-blue-100', text: 'text-blue-700', border: 'border-blue-300', color: '#1e40af' },
  eta: { bg: 'bg-emerald-100', text: 'text-emerald-700', border: 'border-emerald-300', color: '#047857' },
  gamma: { bg: 'bg-amber-100', text: 'text-amber-700', border: 'border-amber-300', color: '#b45309' }
}

const METHOD_COLORS: Record<string, string> = {
  mle: 'border-blue-400',
  wmle: 'border-emerald-400',
  mdm: 'border-purple-400'
}

// ============ Utility Functions ============

function calcStats(data: SimulationRow[]): StatsResult | null {
  if (data.length === 0) return null

  const validRows = data.filter(r => r.est_beta !== null && r.est_eta !== null)
  const betaTrue = data[0].beta_true
  const etaTrue = data[0].eta_true
  const gamma = data[0].gamma ?? 1000

  const calc = (values: (number | null)[]) => {
    const nums = values.filter((v): v is number => v !== null)
    if (nums.length === 0) return { mean: null, std: null, min: null, max: null, p005: null, p995: null }

    const sorted = [...nums].sort((a, b) => a - b)
    const n = sorted.length
    const mean = nums.reduce((a, b) => a + b, 0) / n
    const std = Math.sqrt(nums.reduce((s, v) => s + (v - mean) ** 2, 0) / n)

    const quantile = (q: number) => {
      const pos = (n - 1) * q
      const base = Math.floor(pos)
      return sorted[base + 1] !== undefined
        ? sorted[base] + (pos - base) * (sorted[base + 1] - sorted[base])
        : sorted[base]
    }

    return { mean, std, min: sorted[0], max: sorted[n - 1], p005: quantile(0.005), p995: quantile(0.995) }
  }

  const betaStats = calc(validRows.map(r => r.est_beta))
  const etaStats = calc(validRows.map(r => r.est_eta))
  const gammaStats = calc(validRows.map(r => r.est_gamma))

  return {
    key: 'all',
    keyLabel: '全部',
    count: data.length,
    valid_count: validRows.length,
    beta_true: betaTrue,
    eta_true: etaTrue,
    gamma,
    est_beta_mean: betaStats.mean,
    est_eta_mean: etaStats.mean,
    est_gamma_mean: gammaStats.mean,
    bias_beta_mean: betaStats.mean !== null ? betaStats.mean - betaTrue : null,
    bias_eta_mean: etaStats.mean !== null ? etaStats.mean - etaTrue : null,
    bias_gamma_mean: gammaStats.mean !== null ? gammaStats.mean - gamma : null,
    est_beta_std: betaStats.std,
    est_eta_std: etaStats.std,
    est_gamma_std: gammaStats.std,
    est_beta_min: betaStats.min,
    est_beta_max: betaStats.max,
    est_eta_min: etaStats.min,
    est_eta_max: etaStats.max,
    est_gamma_min: gammaStats.min,
    est_gamma_max: gammaStats.max,
    est_beta_p005: betaStats.p005,
    est_beta_p995: betaStats.p995,
    est_eta_p005: etaStats.p005,
    est_eta_p995: etaStats.p995,
    est_gamma_p005: gammaStats.p005,
    est_gamma_p995: gammaStats.p995
  }
}

const fmt = (v: number | null | undefined, d = 2) => {
  if (v === null || v === undefined) return '—'
  return v.toFixed(d)
}

// 高斯核密度估计
function computeKDE(values: number[], bandwidth?: number, minX?: number) {
  const n = values.length
  if (n === 0) return { points: [], bandwidth: 0 }

  const mean = values.reduce((a, b) => a + b, 0) / n
  const std = Math.sqrt(values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / n)
  const iqr = (() => {
    const sorted = [...values].sort((a, b) => a - b)
    const q1 = sorted[Math.floor(n * 0.25)]
    const q3 = sorted[Math.floor(n * 0.75)]
    return q3 - q1
  })()
  const defaultBandwidth = 0.9 * Math.min(std, iqr / 1.34) / Math.pow(n, 0.2)
  const h = bandwidth ?? Math.max(defaultBandwidth, 0.001)

  const dataMin = Math.min(...values)
  const dataMax = Math.max(...values)
  const range = dataMax - dataMin || 1
  const numPoints = 200

  const plotMin = minX !== undefined ? Math.max(dataMin - range * 0.1, minX) : dataMin - range * 0.1
  const plotMax = dataMax + range * 0.1

  const points = Array.from({ length: numPoints }, (_, i) => {
    const x = plotMin + (i / (numPoints - 1)) * (plotMax - plotMin)
    let density = 0
    for (const v of values) {
      const u = (x - v) / h
      density += Math.exp(-0.5 * u * u)
    }
    density /= (n * h * Math.sqrt(2 * Math.PI))
    return { x, y: density }
  })

  return { points, bandwidth: h }
}

// 多方法对比密度图组件
function CompareDensityChart({
  methodsData,
  selectedMethods,
  paramId,
  trueValue,
  fixedValues
}: {
  methodsData: Record<string, MethodData>
  selectedMethods: string[]
  paramId: 'beta' | 'eta' | 'gamma'
  trueValue: number
  fixedValues: Record<string, number>
}) {
  const estKey = `est_${paramId}`

  // 计算每个方法的 KDE 数据
  const kdeResults = useMemo(() => {
    const results: Array<{
      methodId: string
      methodName: string
      color: string
      kdePoints: Array<{ x: number; y: number }>
      validCount: number
    }> = []

    selectedMethods.forEach((methodId, index) => {
      const methodData = methodsData[methodId]
      if (!methodData?.csvData || methodData.csvData.length === 0) return

      const values = methodData.csvData
        .map(row => row[estKey as keyof SimulationRow] as number | null)
        .filter((v): v is number => v !== null && v !== undefined)

      if (values.length === 0) return

      const kdePoints = computeKDE(values, undefined, paramId === 'gamma' ? 0 : undefined).points
      const methodInfo = {
        mle: { name: 'MLE' },
        wmle: { name: 'WMLE' },
        mdm: { name: 'MDM' },
        lse: { name: 'LSE' },
        lre: { name: 'LRE' },
        mmle: { name: 'MMLE' },
        mps: { name: 'MPS' },
        mm: { name: 'MM' },
        pwm: { name: 'PWM' },
        grey: { name: 'GM(1,1)' },
      }[methodId] || { name: methodId.toUpperCase() }

      results.push({
        methodId,
        methodName: methodInfo.name,
        color: getMethodColor(methodId, index),
        kdePoints,
        validCount: values.length
      })
    })

    return results
  }, [methodsData, selectedMethods, estKey, paramId])

  // 找出所有 x 轴范围的并集
  const xDomain = useMemo(() => {
    if (kdeResults.length === 0) return [0, 1]
    let min = Infinity
    let max = -Infinity
    kdeResults.forEach(r => {
      r.kdePoints.forEach(p => {
        if (p.x < min) min = p.x
        if (p.x > max) max = p.x
      })
    })
    return [min, max]
  }, [kdeResults])

  if (kdeResults.length === 0) {
    return (
      <div className="h-[300px] flex items-center justify-center text-slate-400">
        无有效数据，请先运行模拟
      </div>
    )
  }

  const formatX = (val: number) => {
    if (paramId === 'beta') return val.toFixed(2)
    return val.toFixed(0)
  }

  const paramSymbol = paramId === 'beta' ? 'β' : paramId === 'eta' ? 'η' : 'γ'

  return (
    <>
      {/* 图例 */}
      <div className="flex flex-wrap gap-4 mb-3 text-xs justify-center">
        {kdeResults.map(r => (
          <span key={r.methodId} className="flex items-center gap-1.5">
            <span
              className="w-4 h-1 rounded"
              style={{ backgroundColor: r.color }}
            ></span>
            <span className="text-slate-700 font-medium">{r.methodName}</span>
            <span className="text-slate-400">({r.validCount})</span>
          </span>
        ))}
        <span className="flex items-center gap-1.5 ml-2 border-l pl-4 border-slate-200">
          <span className="w-4 h-0.5 bg-red-500 inline-block" style={{ borderStyle: 'dashed' }}></span>
          <span className="text-slate-600">真实值 ({trueValue})</span>
        </span>
      </div>

      {/* 图表 */}
      <div className="h-[320px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart margin={{ top: 10, right: 20, bottom: 35, left: 50 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
            <XAxis
              dataKey="x"
              type="number"
              domain={xDomain}
              tick={{ fontSize: 11 }}
              tickFormatter={formatX}
              label={{ value: `${paramSymbol} 估计值`, position: 'bottom', offset: 10, fontSize: 12, fill: '#64748b' }}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              label={{ value: '概率密度', angle: -90, position: 'insideLeft', offset: 10, fontSize: 12, fill: '#64748b' }}
            />
            <Tooltip
              contentStyle={{ borderRadius: '6px', border: '1px solid #e5e7eb', fontSize: '12px', backgroundColor: 'rgba(255,255,255,0.95)' }}
              formatter={(v: number) => v.toFixed(4)}
              labelFormatter={(l) => `${paramSymbol}: ${Number(l).toFixed(paramId === 'beta' ? 3 : 1)}`}
            />
            <ReferenceLine
              x={trueValue}
              stroke="#ef4444"
              strokeDasharray="6 4"
              strokeWidth={2}
            />
            {kdeResults.map(r => (
              <Line
                key={r.methodId}
                type="monotone"
                dataKey="y"
                data={r.kdePoints}
                stroke={r.color}
                strokeWidth={2.5}
                dot={false}
                name={r.methodName}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 说明 */}
      <p className="text-center text-xs text-slate-500 mt-3">
        使用高斯核密度估计 (KDE) 展示各方法 {paramSymbol} 估计值的分布。
        <span className="text-red-500 font-medium ml-1">红色虚线</span>为真实参数值。
      </p>
    </>
  )
}

// ============ Sub Components ============

function MethodColumn({
  methodId,
  methodData,
  stats,
  displayOptions,
  paramSelection,
  fixedValues
}: {
  methodId: string
  methodData: MethodData
  stats: StatsResult | null
  displayOptions: { mean: boolean; biasMean: boolean; std: boolean; ci99: boolean }
  paramSelection: { beta: boolean; eta: boolean; gamma: boolean }
  fixedValues: Record<string, number>
}) {
  const methodInfo = {
    mle: { name: '极大似然估计', shortName: 'MLE' },
    wmle: { name: '加权极大似然', shortName: 'WMLE' },
    mdm: { name: '最小差异法', shortName: 'MDM' }
  }[methodId] || { name: methodId.toUpperCase(), shortName: methodId.toUpperCase() }

  const borderColor = METHOD_COLORS[methodId] || 'border-slate-300'

  // 需要现场计算或正在计算
  if (methodData.needsSimulation || methodData.isSimulating) {
    const hasError = !!methodData.errorMessage

    return (
      <div className={cn(
        "bg-white rounded-2xl border-2 p-6 flex flex-col items-center justify-center min-h-[300px]",
        borderColor
      )}>
        {methodData.isSimulating ? (
          <>
            <Loader2 className="h-8 w-8 animate-spin text-purple-500 mb-3" />
            <p className="text-sm text-slate-600 mb-3">正在运行蒙特卡洛模拟...</p>
            <p className="text-xs text-slate-400">请稍候，这可能需要几秒钟</p>
          </>
        ) : hasError ? (
          <>
            <AlertTriangle className="h-8 w-8 text-red-500 mb-3" />
            <p className="text-sm text-red-600 font-bold mb-2">计算失败</p>
            <p className="text-xs text-red-500 mb-4 max-w-xs text-center">{methodData.errorMessage}</p>
          </>
        ) : (
          <>
            <Clock className="h-8 w-8 text-amber-500 mb-3" />
            <p className="text-sm text-slate-600 mb-2">无预计算数据</p>
            <p className="text-xs text-slate-400">请点击上方"开始模拟"按钮</p>
          </>
        )}
      </div>
    )
  }

  // 无数据
  if (!stats || stats.count === 0) {
    return (
      <div className={cn(
        "bg-white rounded-2xl border-2 p-6 flex flex-col items-center justify-center min-h-[300px]",
        borderColor
      )}>
        <p className="text-sm text-slate-400">暂无数据</p>
      </div>
    )
  }

  const selectedParams = Object.entries(paramSelection)
    .filter(([_, s]) => s)
    .map(([k]) => k as 'beta' | 'eta' | 'gamma')

  return (
    <div className={cn("bg-white rounded-2xl border-2 overflow-hidden", borderColor)}>
      {/* 标题 */}
      <div className="px-4 py-3 bg-slate-50 border-b">
        <div className="flex items-center justify-between">
          <h4 className="font-bold text-slate-800">{methodInfo.name}</h4>
          <span className="text-xs font-mono text-slate-500">{methodInfo.shortName}</span>
        </div>
        <p className="text-xs text-slate-400 mt-1">
          {stats.valid_count} / {stats.count} 有效结果
        </p>
      </div>

      {/* 统计表格 */}
      <div className="p-4">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b-2 border-slate-300">
              <th className="py-1.5 px-2 font-bold text-slate-700 text-left">参数</th>
              <th className="py-1.5 px-2 font-bold text-slate-700 text-right">真实值</th>
              {displayOptions.mean && <th className="py-1.5 px-2 font-bold text-slate-700 text-right">均值</th>}
              {displayOptions.biasMean && <th className="py-1.5 px-2 font-bold text-slate-700 text-right">偏差</th>}
              {displayOptions.std && <th className="py-1.5 px-2 font-bold text-slate-700 text-right">SD</th>}
            </tr>
          </thead>
          <tbody>
            {selectedParams.includes('beta') && (
              <tr className="border-b border-slate-100">
                <td className={cn("py-1.5 px-2 font-bold text-center", EST_PARAM_COLORS.beta.text)}>β</td>
                <td className="py-1.5 px-2 font-mono text-slate-700 text-right">{stats.beta_true}</td>
                {displayOptions.mean && <td className="py-1.5 px-2 font-mono text-slate-700 text-right">{fmt(stats.est_beta_mean, 4)}</td>}
                {displayOptions.biasMean && (
                  <td className={cn(
                    "py-1.5 px-2 font-mono text-right",
                    (stats.bias_beta_mean ?? 0) > 0 ? 'text-red-600' : 'text-blue-600'
                  )}>{fmt(stats.bias_beta_mean, 4)}</td>
                )}
                {displayOptions.std && <td className="py-1.5 px-2 font-mono text-slate-700 text-right">{fmt(stats.est_beta_std, 4)}</td>}
              </tr>
            )}
            {selectedParams.includes('eta') && (
              <tr className="border-b border-slate-100">
                <td className={cn("py-1.5 px-2 font-bold text-center", EST_PARAM_COLORS.eta.text)}>η</td>
                <td className="py-1.5 px-2 font-mono text-slate-700 text-right">{stats.eta_true}</td>
                {displayOptions.mean && <td className="py-1.5 px-2 font-mono text-slate-700 text-right">{fmt(stats.est_eta_mean, 2)}</td>}
                {displayOptions.biasMean && (
                  <td className={cn(
                    "py-1.5 px-2 font-mono text-right",
                    (stats.bias_eta_mean ?? 0) > 0 ? 'text-red-600' : 'text-blue-600'
                  )}>{fmt(stats.bias_eta_mean, 2)}</td>
                )}
                {displayOptions.std && <td className="py-1.5 px-2 font-mono text-slate-700 text-right">{fmt(stats.est_eta_std, 2)}</td>}
              </tr>
            )}
            {selectedParams.includes('gamma') && (
              <tr className="border-b border-slate-100">
                <td className={cn("py-1.5 px-2 font-bold text-center", EST_PARAM_COLORS.gamma.text)}>γ</td>
                <td className="py-1.5 px-2 font-mono text-slate-700 text-right">{stats.gamma}</td>
                {displayOptions.mean && <td className="py-1.5 px-2 font-mono text-slate-700 text-right">{fmt(stats.est_gamma_mean, 2)}</td>}
                {displayOptions.biasMean && (
                  <td className={cn(
                    "py-1.5 px-2 font-mono text-right",
                    (stats.bias_gamma_mean ?? 0) > 0 ? 'text-red-600' : 'text-blue-600'
                  )}>{fmt(stats.bias_gamma_mean, 2)}</td>
                )}
                {displayOptions.std && <td className="py-1.5 px-2 font-mono text-slate-700 text-right">{fmt(stats.est_gamma_std, 2)}</td>}
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ============ Main Component ============

interface CompareResultsViewProps {
  selectedMethods: string[]
  methodsData: Record<string, MethodData>
  variableDimensions: string[]
  displayOptions: { mean: boolean; biasMean: boolean; std: boolean; ci99: boolean }
  paramSelection: { beta: boolean; eta: boolean; gamma: boolean }
  setParamSelection: (v: { beta: boolean; eta: boolean; gamma: boolean }) => void
  densityTab: 'beta' | 'eta' | 'gamma'
  setDensityTab: (v: 'beta' | 'eta' | 'gamma') => void
  fixedValues: Record<string, number>
}

export default function CompareResultsView({
  selectedMethods,
  methodsData,
  variableDimensions,
  displayOptions,
  paramSelection,
  setParamSelection,
  densityTab,
  setDensityTab,
  fixedValues
}: CompareResultsViewProps) {
  // 计算各方法统计
  const statsMap = useMemo(() => {
    const map: Record<string, StatsResult | null> = {}
    for (const methodId of selectedMethods) {
      const data = methodsData[methodId]
      map[methodId] = data?.csvData ? calcStats(data.csvData) : null
    }
    return map
  }, [selectedMethods, methodsData])

  // 检查是否有有效数据
  const hasValidData = selectedMethods.some(methodId => {
    const data = methodsData[methodId]
    return data?.csvData && data.csvData.length > 0 && !data.needsSimulation && !data.isSimulating
  })

  // 选中的参数列表
  const selectedParams = Object.entries(paramSelection)
    .filter(([_, s]) => s)
    .map(([k]) => k as 'beta' | 'eta' | 'gamma')

  return (
    <div className="space-y-6">
      {/* 参数选择器 */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 flex items-center gap-4">
        <span className="text-sm font-bold text-slate-600">显示参数:</span>
        <div className="flex gap-2">
          {(['beta', 'eta', 'gamma'] as const).map(p => (
            <button
              key={p}
              onClick={() => setParamSelection({ ...paramSelection, [p]: !paramSelection[p] })}
              className={cn(
                "px-3 py-1.5 rounded text-xs font-bold transition-all",
                paramSelection[p]
                  ? cn(EST_PARAM_COLORS[p].bg, EST_PARAM_COLORS[p].text, EST_PARAM_COLORS[p].border, "border")
                  : "bg-slate-100 text-slate-400"
              )}
            >
              {p === 'beta' ? 'β' : p === 'eta' ? 'η' : 'γ'}
            </button>
          ))}
        </div>
      </div>

      {/* 多栏对比布局 - 统计表格 */}
      <div className={cn(
        "grid gap-6",
        selectedMethods.length === 1 && "grid-cols-1 max-w-xl mx-auto",
        selectedMethods.length === 2 && "grid-cols-1 md:grid-cols-2",
        selectedMethods.length >= 3 && "grid-cols-1 md:grid-cols-2 lg:grid-cols-3"
      )}>
        {selectedMethods.map(methodId => (
          <MethodColumn
            key={methodId}
            methodId={methodId}
            methodData={methodsData[methodId] || { methodId, chunkInfo: null, csvData: [], isLoading: false, needsSimulation: false, isSimulating: false, simulationProgress: 0 }}
            stats={statsMap[methodId]}
            displayOptions={displayOptions}
            paramSelection={paramSelection}
            fixedValues={fixedValues}
          />
        ))}
      </div>

      {/* 概率密度分布图 - 多方法对比 */}
      {hasValidData && selectedParams.length > 0 && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-slate-800">参数估计值概率密度分布对比</h3>
            <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
              {selectedParams.map(param => (
                <button
                  key={param}
                  onClick={() => setDensityTab(param)}
                  className={cn(
                    "px-4 py-1.5 rounded-md text-sm font-bold transition-all",
                    densityTab === param
                      ? "bg-white shadow-sm"
                      : "text-slate-500 hover:text-slate-700"
                  )}
                  style={densityTab === param ? { color: EST_PARAM_COLORS[param].color } : {}}
                >
                  {param === 'beta' ? 'β' : param === 'eta' ? 'η' : 'γ'}
                </button>
              ))}
            </div>
          </div>

          <CompareDensityChart
            methodsData={methodsData}
            selectedMethods={selectedMethods}
            paramId={densityTab}
            trueValue={fixedValues[densityTab] ?? (densityTab === 'beta' ? 2.0 : densityTab === 'eta' ? 1000 : 1000)}
            fixedValues={fixedValues}
          />
        </div>
      )}

      {/* 数据来源表格 */}
      {hasValidData && (
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <p className="text-base font-semibold text-slate-700">数据来源</p>
            <p className="text-xs text-slate-500">
              共 {selectedMethods.length} 个方法
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b-2 border-slate-300">
                  <th className="py-2 px-3 font-bold text-slate-700 text-left w-12">#</th>
                  <th className="py-2 px-3 font-bold text-slate-700 text-left">方法</th>
                  <th className="py-2 px-3 font-bold text-slate-700 text-left">数据文件</th>
                  <th className="py-2 px-3 font-bold text-slate-700 text-right w-28">数据规模</th>
                </tr>
              </thead>
              <tbody>
                {selectedMethods.map((methodId, idx) => {
                  const methodData = methodsData[methodId]
                  const methodInfo = {
                    mle: { name: '极大似然估计', shortName: 'MLE' },
                    wmle: { name: '加权极大似然', shortName: 'WMLE' },
                    mdm: { name: '最小差异法', shortName: 'MDM' },
                    lse: { name: '最小二乘估计', shortName: 'LSE' },
                    lre: { name: '线性回归', shortName: 'LRE' },
                    mmle: { name: '修正极大似然', shortName: 'MMLE' },
                    mps: { name: '最大乘积间距', shortName: 'MPS' },
                    mm: { name: '矩估计', shortName: 'MM' },
                    pwm: { name: '概率加权矩', shortName: 'PWM' },
                    grey: { name: '灰色模型', shortName: 'GM(1,1)' },
                  }[methodId] || { name: methodId.toUpperCase(), shortName: methodId.toUpperCase() }

                  const hasData = methodData?.csvData && methodData.csvData.length > 0
                  const filename = methodData?.loadedFilename

                  return (
                    <tr key={methodId} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                      <td className="py-1.5 px-3 text-slate-500 font-mono">{idx + 1}</td>
                      <td className="py-1.5 px-3">
                        <div className="flex items-center gap-2">
                          <span
                            className="w-3 h-3 rounded-full"
                            style={{ backgroundColor: getMethodColor(methodId, idx) }}
                          ></span>
                          <span className="font-medium text-slate-700">{methodInfo.name}</span>
                          <span className="text-xs text-slate-400 font-mono">({methodInfo.shortName})</span>
                        </div>
                      </td>
                      <td className="py-1.5 px-3 font-mono text-xs">
                        {hasData && filename ? (
                          <span className="text-slate-600">{filename}</span>
                        ) : methodData?.needsSimulation ? (
                          <span className="text-amber-600">现场计算</span>
                        ) : methodData?.isSimulating ? (
                          <span className="text-purple-600 flex items-center gap-1">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            计算中...
                          </span>
                        ) : (
                          <span className="text-slate-400">--</span>
                        )}
                      </td>
                      <td className={cn(
                        "py-1.5 px-3 text-right font-mono",
                        hasData ? "text-slate-700" : "text-slate-400"
                      )}>
                        {hasData ? `${methodData.csvData.length} 行` : '--'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-slate-300 bg-slate-100">
                  <td className="py-2 px-3 font-bold text-slate-700" colSpan={3}>合计</td>
                  <td className="py-2 px-3 text-right font-bold font-mono text-slate-700">
                    {selectedMethods.reduce((sum, methodId) => sum + (methodsData[methodId]?.csvData?.length || 0), 0)} 行
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
