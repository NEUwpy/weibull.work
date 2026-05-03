"use client"

import React, { useEffect, useState, useCallback } from 'react'
import dynamic from 'next/dynamic'
import { cn } from '@/lib/utils'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { loadCSV, loadJSON } from '@/lib/ai-data'
import { chartRegistry, ChartUsage } from './chart-registry'

// AI Charts
import { ScatterPlot } from '@/components/ai/charts/ScatterPlot'
import { BoxPlot } from '@/components/ai/charts/BoxPlot'
import { Histogram } from '@/components/ai/charts/Histogram'
import { AIChartLine } from '@/components/ai/charts/LineChart'
import { MultiLineChart } from '@/components/ai/charts/MultiLineChart'
import { BarChart } from '@/components/ai/charts/BarChart'
import { GroupedBar } from '@/components/ai/charts/GroupedBar'
import { ScatterWithLine } from '@/components/ai/charts/ScatterWithLine'
import { DistributionMark } from '@/components/ai/charts/DistributionMark'

// Shared Charts (Plotly — 动态导入)
const ContourChart = dynamic(() => import('@/components/shared/charts/ContourChart').then(m => m.ContourChart), { ssr: false, loading: () => <Placeholder label="ContourChart" /> })
const ObjectiveSurface3D = dynamic(() => import('@/components/shared/charts/ObjectiveSurface3D').then(m => m.ObjectiveSurface3D), { ssr: false, loading: () => <Placeholder label="ObjectiveSurface3D" /> })

// Shared Charts (SVG/Recharts)
import { HeatmapChart } from '@/components/shared/charts/HeatmapChart'
import { DensityChart } from '@/components/shared/charts/DensityChart'
import { BoxPlotChart } from '@/components/shared/charts/BoxPlotChart'
import { ConvergenceChart } from '@/components/shared/charts/ConvergenceChart'

// ============================================================
// 占位组件
// ============================================================

function Placeholder({ label }: { label: string }) {
  return (
    <div className="h-[220px] flex items-center justify-center bg-slate-50 rounded-xl border border-dashed border-slate-300">
      <span className="text-sm text-slate-400 font-mono">{label} 加载中...</span>
    </div>
  )
}

// ============================================================
// 模拟数据（模板示例用）
// ============================================================

const scatterData = Array.from({ length: 30 }, (_, i) => {
  const x = 0.5 + Math.random() * 4.5
  return { x, y: x + (Math.random() - 0.5) * 0.6 }
})

const boxPlotData = [
  { label: 'n=5', true_val: 2.0, min: 1.2, q1: 1.7, median: 2.05, q3: 2.3, max: 2.8, mean: 2.02, count: 100, outlier_count: 3 },
  { label: 'n=10', true_val: 2.0, min: 1.5, q1: 1.85, median: 2.0, q3: 2.15, max: 2.5, mean: 2.01, count: 100, outlier_count: 1 },
  { label: 'n=15', true_val: 2.0, min: 1.6, q1: 1.9, median: 2.0, q3: 2.1, max: 2.4, mean: 2.0, count: 100, outlier_count: 0 },
  { label: 'n=20', true_val: 2.0, min: 1.7, q1: 1.92, median: 2.0, q3: 2.08, max: 2.3, mean: 2.0, count: 100, outlier_count: 0 },
]

const histValues = Array.from({ length: 200 }, () => (Math.random() - 0.5) * 0.4 + (Math.random() - 0.5) * 0.1)

const lineData = Array.from({ length: 20 }, (_, i) => {
  const x = 0.01 + i * 0.025
  return { x, y: 0.05 / (x + 0.1) + Math.random() * 0.005 }
})

const multiLineData = Array.from({ length: 10 }, (_, i) => ({
  n: [5, 7, 10, 12, 15, 17, 20, 22, 25, 30][i],
  'A-1': 0.03 + Math.random() * 0.02,
  'B-1': 0.025 + Math.random() * 0.015,
  'C-1': 0.035 + Math.random() * 0.02,
}))

const barData = [
  { label: 'A-1', value: 0.032, color: '#3b82f6' },
  { label: 'A-2', value: 0.045, color: '#6366f1' },
  { label: 'B-1', value: 0.028, color: '#10b981' },
  { label: 'C-1', value: 0.034, color: '#f59e0b' },
]

const groupedBarData = [
  { n: 'n=5', MAE_β: 0.12, MAE_η: 1.5 },
  { n: 'n=10', MAE_β: 0.08, MAE_η: 1.0 },
  { n: 'n=15', MAE_β: 0.06, MAE_η: 0.8 },
  { n: 'n=20', MAE_β: 0.05, MAE_η: 0.6 },
]

const swlScatter = Array.from({ length: 20 }, (_, i) => ({ x: i * 0.5, y: i * 0.48 + (Math.random() - 0.5) * 1.5 }))
const swlLine = Array.from({ length: 20 }, (_, i) => ({ x: i * 0.5, y: i * 0.48 }))

const distValues = Array.from({ length: 300 }, () => 0.3 + Math.random() * 0.4)

const heatmapStats = [
  { beta_true: '0.5', eta_true: '1.0', bias_beta: -0.05 },
  { beta_true: '0.5', eta_true: '2.0', bias_beta: 0.02 },
  { beta_true: '0.5', eta_true: '5.0', bias_beta: 0.08 },
  { beta_true: '1.0', eta_true: '1.0', bias_beta: -0.02 },
  { beta_true: '1.0', eta_true: '2.0', bias_beta: 0.01 },
  { beta_true: '1.0', eta_true: '5.0', bias_beta: 0.04 },
  { beta_true: '2.0', eta_true: '1.0', bias_beta: -0.08 },
  { beta_true: '2.0', eta_true: '2.0', bias_beta: -0.01 },
  { beta_true: '2.0', eta_true: '5.0', bias_beta: 0.03 },
  { beta_true: '5.0', eta_true: '1.0', bias_beta: -0.12 },
  { beta_true: '5.0', eta_true: '2.0', bias_beta: -0.04 },
  { beta_true: '5.0', eta_true: '5.0', bias_beta: 0.01 },
]

const densityRawData = Array.from({ length: 100 }, () => ({
  beta: 2.0 + (Math.random() - 0.5) * 0.6,
  eta: 10 + (Math.random() - 0.5) * 3,
  gamma: 0.5 + (Math.random() - 0.5) * 0.2,
  sample_size: 10,
}))

const bpChartData = [
  { keyLabel: 'n=5', est_beta_min: 1.2, est_beta_max: 2.8, est_beta_p01: 1.3, est_beta_p99: 2.7, est_beta_median: 2.0 },
  { keyLabel: 'n=10', est_beta_min: 1.5, est_beta_max: 2.5, est_beta_p01: 1.6, est_beta_p99: 2.4, est_beta_median: 2.0 },
  { keyLabel: 'n=15', est_beta_min: 1.6, est_beta_max: 2.4, est_beta_p01: 1.7, est_beta_p99: 2.3, est_beta_median: 2.0 },
  { keyLabel: 'n=20', est_beta_min: 1.7, est_beta_max: 2.3, est_beta_p01: 1.75, est_beta_p99: 2.25, est_beta_median: 2.0 },
]

const convCurves = [
  {
    id: 'n5', label: 'n=5', color: '#3b82f6',
    data: Array.from({ length: 20 }, (_, i) => ({ mcRuns: (i + 1) * 50, value: 2.0 + 0.3 / Math.sqrt((i + 1) * 50) * (Math.random() - 0.3) })),
  },
  {
    id: 'n10', label: 'n=10', color: '#10b981',
    data: Array.from({ length: 20 }, (_, i) => ({ mcRuns: (i + 1) * 50, value: 2.0 + 0.2 / Math.sqrt((i + 1) * 50) * (Math.random() - 0.3) })),
  },
  {
    id: 'n20', label: 'n=20', color: '#f59e0b',
    data: Array.from({ length: 20 }, (_, i) => ({ mcRuns: (i + 1) * 50, value: 2.0 + 0.1 / Math.sqrt((i + 1) * 50) * (Math.random() - 0.3) })),
  },
]

const contourData = {
  x: Array.from({ length: 20 }, (_, i) => 0.5 + i * 0.2),
  y: Array.from({ length: 20 }, (_, i) => 5 + i * 1),
  z: Array.from({ length: 20 }, () =>
    Array.from({ length: 20 }, () => Math.random() * 2)
  ),
}

const surfaceData = {
  betas: Array.from({ length: 15 }, (_, i) => 0.5 + i * 0.3),
  gammas: Array.from({ length: 15 }, (_, i) => 0 + i * 0.5),
  values: Array.from({ length: 15 }, () =>
    Array.from({ length: 15 }, () => Math.random() * 3)
  ),
}

// ============================================================
// 模板卡片组件
// ============================================================

interface TemplateCardProps {
  name: string
  nameCn: string
  path: string
  purpose: string
  children: React.ReactNode
}

// ============================================================
// 展开实例卡片
// ============================================================

function InstanceCard({ usage, chartType }: { usage: ChartUsage; chartType: string }) {
  const [data, setData] = useState<unknown>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const loadData = useCallback(async () => {
    if (usage.dataSource.type === 'api') return
    setLoading(true)
    setError('')
    try {
      if (usage.dataSource.type === 'csv') {
        const rows = await loadCSV(usage.dataSource.path)
        setData(rows)
      } else {
        const json = await loadJSON(usage.dataSource.path)
        setData(json)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [usage.dataSource])

  useEffect(() => { loadData() }, [loadData])

  return (
    <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200 h-full flex flex-col">
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="font-mono font-bold text-slate-900 text-sm">{usage.label}</div>
          <div className="font-mono text-xs text-slate-500 mt-0.5">{usage.location}</div>
        </div>
        <DataSourceBadge source={usage.dataSource} />
      </div>
      <p className="text-xs text-slate-500 mb-3">{usage.description}</p>
      <div className="bg-white rounded-xl border border-slate-200 p-4 flex-1 min-h-[280px] flex items-center justify-center overflow-hidden">
        {usage.dataSource.type === 'api' ? (
          <div className="text-center">
            <div className="text-2xl mb-2">🔗</div>
            <div className="text-xs text-slate-500">来源：{usage.dataSource.endpoint}</div>
            <div className="text-xs text-slate-400 mt-1">API 调用，无静态数据</div>
          </div>
        ) : loading ? (
          <div className="text-xs text-slate-400">加载数据中...</div>
        ) : error ? (
          <div className="text-xs text-red-400">{error}</div>
        ) : data ? (
          <div className="w-full h-[240px]">
            <InstanceChart chartType={chartType} data={data} usage={usage} />
          </div>
        ) : null}
      </div>
    </div>
  )
}

function DataSourceBadge({ source }: { source: ChartUsage['dataSource'] }) {
  if (source.type === 'api') {
    return <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-50 text-amber-600 border border-amber-200">API</span>
  }
  return (
    <span className={cn(
      'text-[10px] font-mono px-2 py-0.5 rounded border',
      source.type === 'csv' ? 'bg-emerald-50 text-emerald-600 border-emerald-200' : 'bg-blue-50 text-blue-600 border-blue-200'
    )}>
      {source.type.toUpperCase()}
    </span>
  )
}

// ============================================================
// 实例图表渲染
// ============================================================

function InstanceChart({ chartType, data, usage }: { chartType: string; data: unknown; usage: ChartUsage }) {
  const toNum = (v: unknown): number => typeof v === 'number' ? v : parseFloat(v as string) || 0
  const props = usage.props as Record<string, unknown>

  // ScatterPlot: 自动找 {x,y} 列
  if (chartType === 'ScatterPlot' && Array.isArray(data) && data.length > 0) {
    const row = data[0] as Record<string, unknown>
    const keys = Object.keys(row)
    const numKeys = keys.filter(k => typeof row[k] === 'number' || !isNaN(parseFloat(row[k] as string)))
    const xKey = keys.find(k => k === 'true_delta' || k === 'beta' || k === 'true_beta') || numKeys[0]
    const yKey = keys.find(k => k === 'predicted_delta' || k === 'ai_delta' || k === 'est_beta' || k === 'pred_beta') || numKeys[1]
    const scatterPoints = (data as Record<string, unknown>[]).map(r => ({ x: toNum(r[xKey]), y: toNum(r[yKey]) }))
    return <ScatterPlot data={scatterPoints} xLabel={(props.xLabel as string) || xKey} yLabel={(props.yLabel as string) || yKey} color={(props.color as string) || '#8b5cf6'} showDiagonal={!!props.showDiagonal} />
  }

  // Histogram: 自动找误差列
  if (chartType === 'Histogram' && Array.isArray(data) && data.length > 0) {
    const row = data[0] as Record<string, unknown>
    const keys = Object.keys(row)
    const valKey = keys.find(k => k === 'error' || k === 'beta_error' || k === 'best_relative_mse') || keys.find(k => typeof row[k] === 'number' && k !== 'n' && k !== 'seed' && k !== 'step') || keys[0]
    const values = (data as Record<string, unknown>[]).map(r => toNum(r[valKey])).filter(v => !isNaN(v))
    return <Histogram values={values} xLabel={(props.xLabel as string) || valKey} yLabel={(props.yLabel as string) || '频数'} color={(props.color as string) || '#8b5cf6'} showMean={!!props.showMean} />
  }

  // LineChart: JSON metrics → history
  if (chartType === 'LineChart' && data && typeof data === 'object' && 'history' in (data as Record<string, unknown>)) {
    const metrics = data as { history: { train_loss: number[]; val_loss: number[] } }
    const lines = [
      { id: 'train', label: '训练损失', data: metrics.history.train_loss.map((v, i) => ({ x: i, y: v })), color: '#8b5cf6' },
      { id: 'val', label: '验证损失', data: metrics.history.val_loss.map((v, i) => ({ x: i, y: v })), color: '#10b981' },
    ]
    return <AIChartLine lines={lines} xLabel="Epoch" yLabel="Loss" />
  }

  // LineChart: CSV sweep data
  if (chartType === 'LineChart' && Array.isArray(data) && data.length > 0) {
    const row = data[0] as Record<string, unknown>
    const keys = Object.keys(row)
    if (keys.includes('delta') && keys.includes('mean_mse')) {
      const xKey = 'delta'
      const yKey = 'mean_mse'
      const lineData = (data as Record<string, unknown>[]).map(r => ({ x: toNum(r[xKey]), y: toNum(r[yKey]) }))
      return <AIChartLine data={lineData} xLabel={(props.xLabel as string) || 'δ'} yLabel={(props.yLabel as string) || 'MSE'} color={(props.color as string) || '#8b5cf6'} />
    }
    // 通用: 用前两列
    const xKey = keys[0]
    const yKey = keys.find(k => k !== xKey && (typeof row[k] === 'number' || !isNaN(parseFloat(row[k] as string)))) || keys[1]
    const lineData = (data as Record<string, unknown>[]).map(r => ({ x: toNum(r[xKey]), y: toNum(r[yKey]) }))
    return <AIChartLine data={lineData} xLabel={(props.xLabel as string) || xKey} yLabel={(props.yLabel as string) || yKey} color={(props.color as string) || '#8b5cf6'} />
  }

  // BoxPlot: JSON preprocessed → boxplot data
  if (chartType === 'BoxPlot' && data && typeof data === 'object' && 'boxplot' in (data as Record<string, unknown>)) {
    const prep = data as { boxplot: Record<string, Record<string, Array<{ label: string; true_val: number; min: number; q1: number; median: number; q3: number; max: number; mean: number; count: number; outlier_count: number }>>> }
    const firstType = Object.keys(prep.boxplot)[0]
    const firstN = Object.keys(prep.boxplot[firstType])[0]
    const bpData = prep.boxplot[firstType][firstN]
    return <BoxPlot data={bpData} xLabel={(props.xLabel as string) || '样本量'} yLabel={(props.yLabel as string) || 'β̂'} color={(props.color as string) || '#10b981'} />
  }

  // MultiLineChart: JSON scheme comparison
  if (chartType === 'MultiLineChart' && data && typeof data === 'object' && !Array.isArray(data)) {
    const json = data as Record<string, Record<string, { aggregate: { total_relative_mse: number } }>>
    const ns = Object.keys(json)
    if (ns.length > 0) {
      const schemes = Object.keys(json[ns[0]])
      const mlData = ns.map(n => {
        const row: Record<string, number> = { n: Number(n) }
        for (const s of schemes) {
          row[s] = json[n][s]?.aggregate?.total_relative_mse ?? 0
        }
        return row
      })
      const lines = schemes.map((s, i) => ({
        key: s, label: s, color: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#6366f1', '#ec4899', '#14b8a6'][i % 8],
      }))
      return <MultiLineChart data={mlData} xKey="n" lines={lines} xLabel="样本量" yLabel="total_relative_mse" />
    }
  }

  // BarChart: CSV with no-solution rate
  if (chartType === 'BarChart' && Array.isArray(data) && data.length > 0) {
    const row = data[0] as Record<string, unknown>
    const keys = Object.keys(row)
    const valKey = keys.find(k => k === 'best_relative_mse' || k === 'mse') || keys[keys.length - 1]
    // Group by beta and compute mean
    const groups = new Map<string, number[]>()
    for (const r of data as Record<string, unknown>[]) {
      const label = String(r.beta || r.n || 'unknown')
      if (!groups.has(label)) groups.set(label, [])
      groups.get(label)!.push(toNum(r[valKey]))
    }
    const barD = Array.from(groups.entries()).slice(0, 8).map(([label, vals]) => ({
      label: `β=${label}`,
      value: vals.reduce((a, b) => a + b, 0) / vals.length,
      color: '#3b82f6',
    }))
    return <BarChart data={barD} xLabel={(props.xLabel as string) || ''} yLabel={(props.yLabel as string) || valKey} showValue />
  }

  // Fallback: 数据预览
  return <DataPreview data={data} />
}

// 数据预览（兜底）
function DataPreview({ data }: { data: unknown }) {
  if (!data) return <div className="text-xs text-slate-400">无数据</div>
  if (Array.isArray(data) && data.length > 0) {
    const rows = data.slice(0, 5) as Record<string, unknown>[]
    const keys = Object.keys(rows[0]).slice(0, 6)
    return (
      <div className="overflow-auto text-[10px] w-full">
        <table className="w-full border-collapse">
          <thead>
            <tr>{keys.map(k => <th key={k} className="text-left px-1 py-0.5 bg-slate-100 border-b font-mono text-slate-500">{k}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>{keys.map(k => <td key={k} className="px-1 py-0.5 border-b border-slate-50 font-mono text-slate-700">{typeof r[k] === 'number' ? (r[k] as number).toFixed(4) : String(r[k] ?? '')}</td>)}</tr>
            ))}
          </tbody>
        </table>
        <div className="text-[10px] text-slate-400 mt-1">共 {data.length} 行，显示前 5 行</div>
      </div>
    )
  }
  return <div className="text-xs text-slate-400 font-mono">{JSON.stringify(data).slice(0, 200)}</div>
}

// ============================================================
// 可展开的图表卡片
// ============================================================

function ChartExpandable({ name, nameCn, path, purpose, children }: TemplateCardProps) {
  const [expanded, setExpanded] = useState(false)
  const usages = chartRegistry[name] || []

  // 内部：模板卡片（始终显示）
  const templateCard = (
    <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200 h-full flex flex-col">
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="font-mono font-bold text-slate-900 text-base">{name} <span className="text-slate-500 font-sans font-normal">{nameCn}</span></div>
          <div className="font-mono text-xs text-blue-600 mt-0.5">{path}</div>
          <div className="text-sm text-slate-500 mt-1">{purpose}</div>
        </div>
        {usages.length > 0 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="shrink-0 ml-3 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors cursor-pointer
              bg-white text-slate-600 border-slate-200 hover:bg-slate-50 hover:border-slate-300"
          >
            <span>{expanded ? '收起' : `展开 (${usages.length})`}</span>
            <svg className={cn('w-3.5 h-3.5 transition-transform', expanded && 'rotate-180')} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        )}
      </div>
      <div className="bg-white rounded-xl border border-slate-200 p-4 flex-1 min-h-[280px] flex items-center justify-center overflow-hidden">
        <div className="w-full h-[240px]">
          {children}
        </div>
      </div>
    </div>
  )

  // 未展开：只显示模板卡片
  if (!expanded || usages.length === 0) {
    return templateCard
  }

  // 展开：模板卡片 + 实例卡片，外层统一分组背景
  return (
    <div className="xl:col-span-2 p-4 rounded-2xl bg-slate-100/70 border border-slate-200 border-dashed">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {templateCard}
        {usages.map(u => (
          <InstanceCard key={u.id} usage={u} chartType={name} />
        ))}
      </div>
    </div>
  )
}

// ============================================================
// 图表分组定义
// ============================================================

const chartGroups = [
  {
    title: '关系展示',
    description: '两个变量之间的对应关系',
    charts: [
      {
        name: 'ScatterPlot', nameCn: '散点图', path: 'ai/charts', purpose: '真实值 vs 估计值，带对角线参考线',
        render: () => <ScatterPlot data={scatterData} xLabel="真实值" yLabel="估计值" color="#8b5cf6" showDiagonal />,
      },
      {
        name: 'ScatterWithLine', nameCn: '散点+拟合线', path: 'ai/charts', purpose: '散点数据 + 拟合曲线',
        render: () => <ScatterWithLine scatterData={swlScatter} lineData={swlLine} xLabel="真实值" yLabel="估计值" scatterColor="#3b82f6" lineColor="#ef4444" />,
      },
    ],
  },
  {
    title: '分布展示',
    description: '数据的频率分布与统计特征',
    charts: [
      {
        name: 'Histogram', nameCn: '直方图', path: 'ai/charts', purpose: '误差分布或估计值频率分布',
        render: () => <Histogram values={histValues} xLabel="误差" yLabel="频数" color="#6366f1" showMean />,
      },
      {
        name: 'DistributionMark', nameCn: '分布标记', path: 'ai/charts', purpose: '直方图 + 垂直标记线（预测值在分布中的位置）',
        render: () => <DistributionMark distributionValues={distValues} markValue={0.52} color="#8b5cf6" markColor="#ef4444" />,
      },
      {
        name: 'BoxPlot', nameCn: '箱型图（AI）', path: 'ai/charts', purpose: '按分组展示估计值分布（中位数、四分位、异常值）',
        render: () => <BoxPlot data={boxPlotData} xLabel="样本量" yLabel="β̂" color="#3b82f6" showDiagonal />,
      },
      {
        name: 'BoxPlotChart', nameCn: '箱型图（Methods）', path: 'shared/charts', purpose: '适配适用范围数据格式：min/max/P1/P99/median',
        render: () => <BoxPlotChart data={bpChartData} dataKeyMin="est_beta_min" dataKeyMax="est_beta_max" dataKeyP01="est_beta_p01" dataKeyP99="est_beta_p99" dataKeyMedian="est_beta_median" color="#3b82f6" yLabel="β̂" xLabel="样本量" trueValue={2.0} />,
      },
      {
        name: 'DensityChart', nameCn: '密度图', path: 'shared/charts', purpose: '估计值的概率密度分布（KDE 核密度估计）',
        render: () => <DensityChart rawData={densityRawData} paramId="beta" displayDimension={{ id: 'sample_size', name: '样本量', symbol: 'n' }} trueValue={2.0} color="#3b82f6" />,
      },
    ],
  },
  {
    title: '趋势与对比',
    description: '随变量变化的趋势或方案间对比',
    charts: [
      {
        name: 'LineChart', nameCn: '折线图', path: 'ai/charts', purpose: '单系列趋势（如 δ sweep MSE 曲线）',
        render: () => <AIChartLine data={lineData} xLabel="δ" yLabel="MSE" color="#8b5cf6" />,
      },
      {
        name: 'MultiLineChart', nameCn: '多系列折线图', path: 'ai/charts', purpose: '多方案精度对比曲线',
        render: () => <MultiLineChart data={multiLineData} xKey="n" lines={[{ key: 'A-1', label: 'A-1', color: '#3b82f6' }, { key: 'B-1', label: 'B-1', color: '#10b981' }, { key: 'C-1', label: 'C-1', color: '#f59e0b' }]} xLabel="样本量" yLabel="MAE(β)" />,
      },
      {
        name: 'ConvergenceChart', nameCn: '收敛图', path: 'shared/charts', purpose: '统计量随蒙特卡洛仿真次数的收敛趋势',
        render: () => <ConvergenceChart curves={convCurves} statType="mean" trueValue={2.0} yLabel="β̂ 均值" />,
      },
      {
        name: 'BarChart', nameCn: '柱状图', path: 'ai/charts', purpose: '分类数据对比',
        render: () => <BarChart data={barData} xLabel="方案" yLabel="MAE(β)" showValue />,
      },
      {
        name: 'GroupedBar', nameCn: '分组柱状图', path: 'ai/charts', purpose: '多指标并列对比',
        render: () => <GroupedBar data={groupedBarData} xKey="n" groups={[{ key: 'MAE_β', label: 'MAE(β)', color: '#3b82f6' }, { key: 'MAE_η', label: 'MAE(η)', color: '#6366f1' }]} xLabel="样本量" yLabel="MAE" />,
      },
    ],
  },
  {
    title: '空间展示',
    description: '参数空间或目标函数可视化',
    charts: [
      {
        name: 'HeatmapChart', nameCn: '热力图', path: 'shared/charts', purpose: '二维参数空间的偏差/精度（蓝色=低估，红色=高估）',
        render: () => <HeatmapChart stats={heatmapStats} displayDimensions={[{ id: 'beta', name: 'β', symbol: 'β' }, { id: 'eta', name: 'η', symbol: 'η' }]} dataKey="bias_beta" maxAbs={0.15} />,
      },
      {
        name: 'ContourChart', nameCn: '等高线图', path: 'shared/charts', purpose: '目标函数在参数空间的等值线 + 优化路径',
        render: () => <ContourChart contourData={contourData} xLabel="β" yLabel="γ" title="目标函数等高线" height={260} />,
      },
      {
        name: 'ObjectiveSurface3D', nameCn: '3D 曲面图', path: 'shared/charts', purpose: '目标函数的三维可视化',
        render: () => <ObjectiveSurface3D surfaceData={surfaceData} height={260} />,
      },
    ],
  },
  {
    title: '容器',
    description: '布局与包装组件',
    charts: [
      {
        name: 'ChartCard', nameCn: '图表容器', path: 'shared/charts', purpose: '统一标题、边框、间距的容器组件',
        render: () => (
          <ChartCard title="示例图表标题">
            <div className="h-full flex items-center justify-center text-slate-400 text-sm">
              图表内容区域 — 由 ChartCard 提供统一外框
            </div>
          </ChartCard>
        ),
      },
    ],
  },
]

// ============================================================
// 页面
// ============================================================

export default function ChartsPage() {
  return (
    <div className="bg-white p-10 rounded-3xl border border-slate-200 shadow-sm space-y-10">
      {/* 标题 */}
      <div>
        <h1 className="text-2xl font-black text-slate-900 mb-2">图表规范</h1>
        <p className="text-slate-500">
          统一系统所有图表的使用标准。使用或新建图表前，请先查阅本页面。点击「展开」可查看该图表在系统中的所有使用实例。
        </p>
      </div>

      {/* 图表分组 */}
      {chartGroups.map(group => (
        <section key={group.title} className="space-y-5">
          <div>
            <h2 className="text-lg font-bold text-slate-900">{group.title}</h2>
            <p className="text-sm text-slate-500">{group.description}</p>
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            {group.charts.map(chart => (
              <ChartExpandable
                key={chart.name}
                name={chart.name}
                nameCn={chart.nameCn}
                path={chart.path}
                purpose={chart.purpose}
              >
                {chart.render()}
              </ChartExpandable>
            ))}
          </div>
        </section>
      ))}

      {/* 图谱 */}
      <section className="space-y-6">
        <h2 className="text-lg font-bold text-slate-900">图表图谱</h2>
        <p className="text-sm text-slate-500 -mt-3">
          各模块 / Tab 使用的图表一览。
        </p>

        {[
          { title: '参数估计方法（Methods）', accent: 'text-blue-700', rows: [
            { tab: '计算过程', chart: '直方图', data: 'β/η/γ 估计值分布', src: 'Recharts BarChart' },
            { tab: '计算过程', chart: '折线图', data: 'MSE/Std 随偏移量变化', src: 'Recharts LineChart' },
            { tab: '计算过程', chart: '散点图', data: '估计值 vs 真实值', src: 'Recharts ScatterChart' },
            { tab: '适用范围', chart: '箱型图', data: '各参数组合下估计值分布', src: 'shared BoxPlotChart' },
            { tab: '适用范围', chart: '热力图', data: 'β-η 参数空间偏差', src: 'shared HeatmapChart' },
            { tab: '适用范围', chart: '密度图', data: '估计值概率密度', src: 'shared DensityChart' },
            { tab: '可信性验证', chart: '折线图', data: '梯度曲线（MDM）', src: 'mdm GradientGammaChart' },
            { tab: '方法对比', chart: '折线图', data: '多方法精度对比', src: 'Recharts LineChart' },
          ]},
          { title: 'M1 关系建立', accent: 'text-purple-700', rows: [
            { tab: '偏移量精度 (R1)', chart: '散点图', data: 'AI δ vs 最优 δ', src: 'ai ScatterPlot' },
            { tab: '偏移量精度 (R1)', chart: '直方图', data: 'δ 误差分布', src: 'ai Histogram' },
            { tab: '三参数精度', chart: '散点图', data: 'β/η 估计 vs 真实', src: 'ai ScatterPlot' },
            { tab: '三参数精度', chart: '直方图', data: '三参数 MSE 分布', src: 'ai Histogram' },
            { tab: '迭代过程 (R2)', chart: '折线图', data: '迭代收敛轨迹', src: 'ai AIChartLine' },
            { tab: '方法对比 (R1)', chart: '折线图', data: 'δ Sweep MSE 曲线', src: 'ai AIChartLine' },
            { tab: '方法对比 (R1)', chart: '热力图', data: '改善率（β vs n）', src: '内联渲染' },
          ]},
          { title: 'M3 直接估计', accent: 'text-emerald-700', rows: [
            { tab: '性能展示', chart: '散点图', data: '真实 vs 预测', src: 'ai ScatterPlot' },
            { tab: '性能展示', chart: '箱型图', data: '误差分布', src: 'ai BoxPlot' },
            { tab: '性能展示', chart: '直方图', data: '误差频率分布', src: 'ai Histogram' },
            { tab: '可信性验证', chart: '表格', data: '精度汇总表', src: 'HTML table' },
            { tab: '方法对比（方案间）', chart: '折线图', data: '8 方案精度对比', src: 'ai MultiLineChart' },
            { tab: '方法对比（M1 vs M3）', chart: '折线图', data: '跨模块对比', src: 'ai MultiLineChart' },
          ]},
        ].map(group => (
          <div key={group.title}>
            <h3 className={cn('text-sm font-bold mb-3', group.accent)}>{group.title}</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr>
                    <th className="text-left px-3 py-2 text-xs font-bold text-slate-400 uppercase tracking-wider border-b-2 border-slate-200 bg-slate-50">Tab</th>
                    <th className="text-left px-3 py-2 text-xs font-bold text-slate-400 uppercase tracking-wider border-b-2 border-slate-200 bg-slate-50">图表</th>
                    <th className="text-left px-3 py-2 text-xs font-bold text-slate-400 uppercase tracking-wider border-b-2 border-slate-200 bg-slate-50">数据含义</th>
                    <th className="text-left px-3 py-2 text-xs font-bold text-slate-400 uppercase tracking-wider border-b-2 border-slate-200 bg-slate-50">组件来源</th>
                  </tr>
                </thead>
                <tbody>
                  {group.rows.map((r, i) => (
                    <tr key={i} className="hover:bg-slate-50/50">
                      <td className="px-3 py-2 font-medium text-slate-900 border-b border-slate-100 whitespace-nowrap">{r.tab}</td>
                      <td className="px-3 py-2 text-slate-700 border-b border-slate-100 whitespace-nowrap">{r.chart}</td>
                      <td className="px-3 py-2 text-slate-600 border-b border-slate-100">{r.data}</td>
                      <td className="px-3 py-2 font-mono text-xs text-slate-500 border-b border-slate-100 whitespace-nowrap">{r.src}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </section>

      {/* 配色规范 */}
      <section>
        <h2 className="text-lg font-bold text-slate-900 mb-4">配色规范</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[
            { usage: 'β 参数（形状参数）', color: '#3b82f6', name: 'blue-500' },
            { usage: 'η 参数（尺度参数）', color: '#6366f1', name: 'indigo-500' },
            { usage: 'γ 参数（位置参数）', color: '#a855f7', name: 'purple-500' },
            { usage: 'AI 预测结果', color: '#8b5cf6', name: 'violet-500' },
            { usage: '固定值基线', color: '#f59e0b', name: 'amber-500' },
            { usage: '最优值参考', color: '#10b981', name: 'emerald-500' },
            { usage: '误差正值（高估）', color: '#ef4444', name: 'red-500' },
            { usage: '误差负值（低估）', color: '#3b82f6', name: 'blue-500' },
          ].map(c => (
            <div key={c.usage} className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 border border-slate-100">
              <div className="w-8 h-8 rounded-lg shrink-0" style={{ backgroundColor: c.color }} />
              <div>
                <div className="text-sm font-medium text-slate-900">{c.usage}</div>
                <div className="text-xs font-mono text-slate-400">{c.color} ({c.name})</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 使用说明 */}
      <section className="p-5 rounded-2xl bg-blue-50 border border-blue-100">
        <h3 className="text-sm font-bold text-blue-800 mb-2">开发规范</h3>
        <ul className="text-sm text-blue-700 space-y-1.5">
          <li>• 新增图表 → 必须先更新本页面，定义用途和适用数据类型</li>
          <li>• 使用图表 → 优先复用已有组件，用 props 控制差异</li>
          <li>• 相同数据含义的图表必须使用相同组件，禁止为不同场景创建功能重复的图表</li>
          <li>• 配色必须遵循本页规范，保持全系统视觉一致</li>
          <li>• 新增图表使用位置 → 必须同步更新 <code className="bg-blue-100 px-1 rounded">chart-registry.ts</code></li>
        </ul>
      </section>
    </div>
  )
}
