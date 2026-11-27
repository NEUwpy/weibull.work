"use client"

import React, { useMemo } from 'react'
import { Loader2, AlertTriangle, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { summarizeMethodComparison, type MethodComparisonStatistics } from '@/lib/method-comparison-statistics'
import type { MethodComparisonResult, MethodComparisonState } from '@/lib/method-comparison-loader'
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
  statsMap,
  selectedMethods,
  paramId,
  trueValue
}: {
  statsMap: Record<string, MethodComparisonStatistics | null>
  selectedMethods: string[]
  paramId: 'beta' | 'eta' | 'gamma'
  trueValue: number | null
}) {
  // 计算每个方法的 KDE 数据
  const kdeResults = useMemo(() => {
    const results: Array<{
      methodId: string
      methodName: string
      color: string
      kdePoints: Array<{ x: number; y: number }>
      count: number
    }> = []

    selectedMethods.forEach((methodId, index) => {
      const values = statsMap[methodId]?.parameters[paramId].values
      if (!values?.length) return

      const nonnegativeGamma = paramId === 'gamma' && values.every(value => value >= 0)
      const kdePoints = computeKDE(values, undefined, nonnegativeGamma ? 0 : undefined).points
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
        count: values.length
      })
    })

    return results
  }, [statsMap, selectedMethods, paramId])

  // 找出所有 x 轴范围的并集
  const xDomain = useMemo(() => {
    if (kdeResults.length === 0) return [0, 1]
    let min = trueValue ?? Infinity
    let max = trueValue ?? -Infinity
    kdeResults.forEach(r => {
      r.kdePoints.forEach(p => {
        if (p.x < min) min = p.x
        if (p.x > max) max = p.x
      })
    })
    return [min, max]
  }, [kdeResults, trueValue])

  if (kdeResults.length === 0) {
    return (
      <div className="h-[300px] flex items-center justify-center text-slate-400">
        没有可绘制的估计值
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
            <span className="text-slate-400">({r.count})</span>
          </span>
        ))}
        {trueValue !== null && <span className="flex items-center gap-1.5 ml-2 border-l pl-4 border-slate-200">
          <span className="w-4 h-0.5 bg-red-500 inline-block" style={{ borderStyle: 'dashed' }}></span>
          <span className="text-slate-600">真实值 ({trueValue})</span>
        </span>}
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
            {trueValue !== null && <ReferenceLine
              x={trueValue}
              stroke="#ef4444"
              strokeDasharray="6 4"
              strokeWidth={2}
            />}
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
        {trueValue !== null && <span className="ml-1">红色虚线为各批次共有的真值。</span>}
      </p>
    </>
  )
}

// ============ Sub Components ============

function MethodColumn({
  methodId,
  result,
  stats,
  displayOptions,
  paramSelection,
  onRetry
}: {
  methodId: string
  result: MethodComparisonResult
  stats: MethodComparisonStatistics | null
  displayOptions: { mean: boolean; biasMean: boolean; std: boolean; ci99: boolean }
  paramSelection: { beta: boolean; eta: boolean; gamma: boolean }
  onRetry: (methodId: string) => void
}) {
  const methodInfo = {
    mle: { name: '极大似然估计', shortName: 'MLE' },
    wmle: { name: '加权极大似然', shortName: 'WMLE' },
    mdm: { name: '最小差异法', shortName: 'MDM' }
  }[methodId] || { name: methodId.toUpperCase(), shortName: methodId.toUpperCase() }

  const borderColor = METHOD_COLORS[methodId] || 'border-slate-300'

  if (result.status !== 'ready') {
    return (
      <div className={cn(
        "bg-white rounded-2xl border-2 p-6 flex flex-col items-center justify-center min-h-[300px]",
        borderColor
      )}>
        <h4 className="font-bold text-slate-800 mb-3">{methodInfo.name}</h4>
        {result.status === 'loading' || result.status === 'simulating' ? (
          <>
            <Loader2 className="h-8 w-8 animate-spin text-purple-500 mb-3" />
            <p className="text-sm text-slate-600">{result.status === 'simulating' ? '正在运行蒙特卡洛模拟' : '正在查找所选组合的历史结果'}</p>
          </>
        ) : result.status === 'error' ? (
          <>
            <AlertTriangle className="h-8 w-8 text-red-500 mb-3" />
            <p className="text-sm text-red-600 font-bold mb-2">{result.stage === 'simulation' ? '计算失败' : '历史数据读取失败'}</p>
            <p className="text-xs text-red-500 mb-4 max-w-xs text-center">{result.message}</p>
            <button type="button" onClick={() => onRetry(methodId)} className="text-sm font-medium text-purple-700 underline">重试</button>
          </>
        ) : (
          <>
            <Clock className="h-8 w-8 text-amber-500 mb-3" />
            <p className="text-sm text-slate-600 mb-2">
              {result.status === 'waiting-for-parameters' ? '请完成参数配置' : '所选组合没有历史结果'}
            </p>
            {result.status === 'waiting-for-simulation' && <p className="text-xs text-slate-400">即将开始现场模拟</p>}
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
          {stats.failures === null
            ? <>{stats.includedCount} / {stats.count} 条记录有完整估计值 · 有效率未核验</>
            : <>{stats.includedCount} / {stats.count} 有效 · 失败 {stats.failures} 次（{(100 * stats.failures / stats.count).toFixed(1)}%）</>}
        </p>
        <p className="text-xs text-slate-500 mt-1" title={result.source === 'archive' ? result.filename : undefined}>
          {result.source === 'archive' ? '历史分片' : '现场模拟'}
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
            {selectedParams.map(key => {
              const summary = stats.parameters[key]
              const digits = key === 'beta' ? 4 : 2
              const label = { beta: 'β', eta: 'η', gamma: 'γ' }[key]
              return (
                <tr key={key} className="border-b border-slate-100">
                  <td className={cn("py-1.5 px-2 font-bold text-center", EST_PARAM_COLORS[key].text)}>{label}</td>
                  <td className="py-1.5 px-2 font-mono text-slate-700 text-right">{summary.truth ?? '—'}</td>
                  {displayOptions.mean && <td className="py-1.5 px-2 font-mono text-slate-700 text-right">{fmt(summary.mean, digits)}</td>}
                  {displayOptions.biasMean && (
                    <td className={cn(
                      "py-1.5 px-2 font-mono text-right",
                      (summary.bias ?? 0) > 0 ? 'text-red-600' : 'text-blue-600'
                    )}>{fmt(summary.bias, digits)}</td>
                  )}
                  {displayOptions.std && <td className="py-1.5 px-2 font-mono text-slate-700 text-right">{fmt(summary.sd, digits)}</td>}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ============ Main Component ============

interface CompareResultsViewProps {
  selectedMethods: string[]
  methodsData: Record<string, MethodComparisonState>
  displayOptions: { mean: boolean; biasMean: boolean; std: boolean; ci99: boolean }
  paramSelection: { beta: boolean; eta: boolean; gamma: boolean }
  setParamSelection: (v: { beta: boolean; eta: boolean; gamma: boolean }) => void
  densityTab: 'beta' | 'eta' | 'gamma'
  setDensityTab: (v: 'beta' | 'eta' | 'gamma') => void
  onRetry: (methodId: string) => void
}

export default function CompareResultsView({
  selectedMethods,
  methodsData,
  displayOptions,
  paramSelection,
  setParamSelection,
  densityTab,
  setDensityTab,
  onRetry
}: CompareResultsViewProps) {
  // 计算各方法统计
  const statsMap = useMemo(() => {
    const map: Record<string, MethodComparisonStatistics | null> = {}
    for (const methodId of selectedMethods) {
      const result = methodsData[methodId]?.result
      map[methodId] = result?.status === 'ready' ? summarizeMethodComparison(result) : null
    }
    return map
  }, [selectedMethods, methodsData])

  const shownStats = Object.values(statsMap).filter(stats => stats !== null)
  const hasResults = shownStats.length > 0
  const firstTruth = shownStats[0]?.parameters[densityTab].truth ?? null
  const commonTruth = shownStats.every(stats => stats.parameters[densityTab].truth === firstTruth) ? firstTruth : null

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
            result={methodsData[methodId].result}
            stats={statsMap[methodId]}
            displayOptions={displayOptions}
            paramSelection={paramSelection}
            onRetry={onRetry}
          />
        ))}
      </div>

      {/* 概率密度分布图 - 多方法对比 */}
      {hasResults && selectedParams.length > 0 && (
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
            statsMap={statsMap}
            selectedMethods={selectedMethods}
            paramId={densityTab}
            trueValue={commonTruth}
          />
        </div>
      )}

      {/* 数据来源表格 */}
      {hasResults && (
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
                  <th className="py-2 px-3 font-bold text-slate-700 text-left">数据来源</th>
                  <th className="py-2 px-3 font-bold text-slate-700 text-right w-28">数据规模</th>
                </tr>
              </thead>
              <tbody>
                {selectedMethods.map((methodId, idx) => {
                  const result = methodsData[methodId].result
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

                  const hasData = result.status === 'ready'

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
                        {hasData ? (
                          <span className="text-slate-600">{result.source === 'archive' ? result.filename : '现场模拟'}</span>
                        ) : result.status === 'simulating' ? (
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
                        {hasData ? `${result.rows.length} 行` : '--'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-slate-300 bg-slate-100">
                  <td className="py-2 px-3 font-bold text-slate-700" colSpan={3}>合计</td>
                  <td className="py-2 px-3 text-right font-bold font-mono text-slate-700">
                    {selectedMethods.reduce((sum, methodId) => {
                      const result = methodsData[methodId].result
                      return sum + (result.status === 'ready' ? result.rows.length : 0)
                    }, 0)} 行
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
