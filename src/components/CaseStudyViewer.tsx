"use client"

import React, { useState, useEffect } from 'react'
import { FlaskConical, Filter, ChevronDown, Check, Info, Settings, Lock, Unlock } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  LineChart,
  Line,
  ComposedChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine
} from 'recharts'

interface CaseStudyViewerProps {
  methodId: string
}

// 参数类型
type ParamType = 'beta' | 'eta' | 'gamma' | 'sampleSize' | 'process'

// 参数状态
type ParamState = 'fixed' | 'range' | 'discrete'

// 参数配置
interface ParamConfig {
  id: ParamType
  name: string
  symbol: string  // 显示符号
  state: ParamState
  fixedValue?: number
  range?: { min: number; max: number }
  discreteValues?: number[]
  isVariable: boolean  // 是否为变量（由数据决定，不可改）
  isDisplayDimension: boolean  // 是否作为展示维度（用户可切换）
}

// 案例配置
interface CaseConfig {
  id: string
  name: string
  description: string
  params: ParamConfig[]  // 5个参数的配置
  processName?: string  // 过程参数的名称（如"偏移量"）
  processSymbol?: string // 过程参数符号（如"δ"）
  csvFile?: string
}

// CSV数据行
interface SimulationRow {
  beta_true: number
  sample_size: number
  offset_value: number
  sim_id: number
  est_beta: number
  est_eta: number
  est_gamma: number
  bias_beta: number
  bias_eta: number
  bias_gamma: number
  r_squared: number
}

// 统计结果
interface StatsResult {
  key: string
  keyLabel: string
  count: number
  // 维度值
  beta_true?: number
  sample_size?: number
  offset_value?: number
  // 统计量
  bias_beta_mean: number
  bias_beta_std: number
  bias_eta_mean: number
  bias_eta_std: number
  bias_gamma_mean: number
  bias_gamma_std: number
  mse_beta: number
  mse_eta: number
  mse_gamma: number
}

// MDM 案例1: 5个参数的配置
const CASE_CONFIGS: Record<string, CaseConfig[]> = {
  mdm: [
    {
      id: 'case-1',
      name: '案例1: 多维度参数影响研究',
      description: '研究形状参数、样本量、偏移量对MDM三参数估计结果的影响。基于100次蒙特卡洛模拟的预设分析结果。',
      processName: '偏移量',
      processSymbol: 'δ',
      csvFile: '/cases/mdm_case1_full.csv',
      params: [
        { id: 'beta', name: '形状参数', symbol: 'β', state: 'discrete', discreteValues: [1.5, 2.0, 3, 5, 7], isVariable: true, isDisplayDimension: false },
        { id: 'eta', name: '尺度参数', symbol: 'η', state: 'fixed', fixedValue: 1000, isVariable: false, isDisplayDimension: false },
        { id: 'gamma', name: '位置参数', symbol: 'γ', state: 'fixed', fixedValue: 1000, isVariable: false, isDisplayDimension: false },
        { id: 'sampleSize', name: '样本量', symbol: 'n', state: 'discrete', discreteValues: [5, 7, 10, 20, 30], isVariable: true, isDisplayDimension: false },
        { id: 'process', name: '偏移量', symbol: 'δ', state: 'discrete', discreteValues: [0, 0.05, 0.1, 0.15, 0.2], isVariable: true, isDisplayDimension: false }
      ]
    }
  ]
}

// 参数卡片颜色
const PARAM_COLORS: Record<ParamType, string> = {
  beta: 'border-blue-200 bg-blue-50',
  eta: 'border-emerald-200 bg-emerald-50',
  gamma: 'border-amber-200 bg-amber-50',
  sampleSize: 'border-purple-200 bg-purple-50',
  process: 'border-rose-200 bg-rose-50'
}

const PARAM_TEXT_COLORS: Record<ParamType, string> = {
  beta: 'text-blue-700',
  eta: 'text-emerald-700',
  gamma: 'text-amber-700',
  sampleSize: 'text-purple-700',
  process: 'text-rose-700'
}

export default function CaseStudyViewer({ methodId }: CaseStudyViewerProps) {
  const [selectedCaseId, setSelectedCaseId] = useState<string>('case-1')
  const [params, setParams] = useState<ParamConfig[]>([])
  const [csvData, setCsvData] = useState<SimulationRow[]>([])
  const [stats, setStats] = useState<StatsResult[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const methodCases = CASE_CONFIGS[methodId.toLowerCase()] || []
  const selectedCase = methodCases.find(c => c.id === selectedCaseId)

  // 初始化参数配置
  useEffect(() => {
    if (selectedCase) {
      setParams([...selectedCase.params])
    }
  }, [selectedCaseId, selectedCase])

  // 切换显示维度
  const toggleDisplayDimension = (paramId: ParamType) => {
    setParams(prev => prev.map(p =>
      p.id === paramId && p.isVariable ? { ...p, isDisplayDimension: !p.isDisplayDimension } : p
    ))
    // 切换维度后清空统计数据，重新计算
    setStats([])
  }

  // 加载CSV数据
  useEffect(() => {
    if (!selectedCase?.csvFile) return

    setIsLoading(true)
    setError(null)

    fetch(selectedCase.csvFile)
      .then(res => {
        if (!res.ok) throw new Error('数据文件加载失败')
        return res.text()
      })
      .then(csvText => {
        const parsedData = parseCSV(csvText)
        setCsvData(parsedData)
      })
      .catch(err => {
        setError(err.message || '数据加载失败')
        console.error(err)
      })
      .finally(() => {
        setIsLoading(false)
      })
  }, [selectedCaseId])

  // 当数据或参数变化时，重新计算统计量
  useEffect(() => {
    if (csvData.length === 0) return

    const displayDimensions = params.filter(p => p.isDisplayDimension)
    if (displayDimensions.length === 0) return

    const statsResult = calculateStats(csvData, displayDimensions)
    setStats(statsResult)
  }, [csvData, params])

  // 解析CSV
  const parseCSV = (csvText: string): SimulationRow[] => {
    const lines = csvText.trim().split('\n')
    const headers = lines[0].split(',')

    return lines.slice(1).map(line => {
      const values = line.split(',')
      const row: any = {}
      headers.forEach((header, idx) => {
        const val = values[idx]
        row[header] = isNaN(Number(val)) ? val : Number(val)
      })
      return row as SimulationRow
    })
  }

  // 计算统计量
  const calculateStats = (data: SimulationRow[], variableParams: ParamConfig[]): StatsResult[] => {
    const groups = new Map<string, SimulationRow[]>()

    data.forEach(row => {
      const keyParts: string[] = []
      variableParams.forEach(p => {
        if (p.id === 'beta') keyParts.push(`β=${row.beta_true}`)
        if (p.id === 'sampleSize') keyParts.push(`n=${row.sample_size}`)
        if (p.id === 'process') keyParts.push(`${selectedCase?.processSymbol || 'δ'}=${row.offset_value}`)
      })

      const key = keyParts.join(', ')
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key)!.push(row)
    })

    return Array.from(groups.entries()).map(([key, rows]) => {
      const count = rows.length
      const mean = (arr: number[]) => arr.reduce((a, b) => a + b, 0) / arr.length
      const variance = (arr: number[]) => {
        const m = mean(arr)
        return arr.reduce((sum, val) => sum + (val - m) ** 2, 0) / arr.length
      }

      const biasBeta = rows.map(r => r.bias_beta)
      const biasEta = rows.map(r => r.bias_eta)
      const biasGamma = rows.map(r => r.bias_gamma)

      return {
        key,
        keyLabel: key,
        beta_true: variableParams.find(p => p.id === 'beta') ? rows[0].beta_true : undefined,
        sample_size: variableParams.find(p => p.id === 'sampleSize') ? rows[0].sample_size : undefined,
        offset_value: variableParams.find(p => p.id === 'process') ? rows[0].offset_value : undefined,
        count,
        bias_beta_mean: mean(biasBeta),
        bias_beta_std: Math.sqrt(variance(biasBeta)),
        bias_eta_mean: mean(biasEta),
        bias_eta_std: Math.sqrt(variance(biasEta)),
        bias_gamma_mean: mean(biasGamma),
        bias_gamma_std: Math.sqrt(variance(biasGamma)),
        mse_beta: mean(biasBeta.map(v => v ** 2)),
        mse_eta: mean(biasEta.map(v => v ** 2)),
        mse_gamma: mean(biasGamma.map(v => v ** 2))
      }
    }).sort((a, b) => {
      const firstVar = variableParams[0].id
      if (firstVar === 'beta') return (a.beta_true || 0) - (b.beta_true || 0)
      if (firstVar === 'sampleSize') return (a.sample_size || 0) - (b.sample_size || 0)
      if (firstVar === 'process') return (a.offset_value || 0) - (b.offset_value || 0)
      return 0
    })
  }

  if (methodCases.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center text-center">
          <FlaskConical className="text-slate-300 mb-4" size={48} />
          <h3 className="text-lg font-bold text-slate-600 mb-2">暂无案例</h3>
          <p className="text-slate-400">该方法的案例展示正在建设中...</p>
        </div>
      </div>
    )
  }

  const variableParams = params.filter(p => p.isVariable)
  const displayDimensions = params.filter(p => p.isDisplayDimension)
  const numCombinations = displayDimensions.reduce((acc, p) => {
    return acc * (p.state === 'discrete' ? (p.discreteValues?.length || 1) : 1)
  }, 1)

  return (
    <div className="space-y-6">
      {/* 顶部控制栏 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-3 mb-6">
          <FlaskConical className="text-purple-600" size={24} />
          <h2 className="text-xl font-bold text-slate-800">案例展示</h2>
          <span className="text-xs text-slate-400 ml-auto">预设分析结果 · 通用参数框架</span>
        </div>

        {/* 案例选择下拉 */}
        <div className="flex items-center gap-4 mb-6">
          <label className="text-sm font-bold text-slate-600 whitespace-nowrap">选择案例：</label>
          <div className="relative flex-1 max-w-md">
            <select
              value={selectedCaseId}
              onChange={(e) => {
                setSelectedCaseId(e.target.value)
                setStats([])
              }}
              className="w-full appearance-none bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent cursor-pointer hover:bg-slate-100 transition-colors"
            >
              {methodCases.map(case_ => (
                <option key={case_.id} value={case_.id}>
                  {case_.name}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={18} />
          </div>
        </div>

        {/* 案例描述 */}
        {selectedCase && (
          <div className="bg-purple-50 rounded-xl p-4 border border-purple-100">
            <p className="text-sm text-purple-800">{selectedCase.description}</p>
          </div>
        )}
      </div>

      {/* 参数卡片框架 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
            <Settings size={20} className="text-slate-600" />
            参数配置
          </h3>
          <div className="text-sm text-slate-500">
            <span className="font-bold text-blue-600">{variableParams.length}</span> 个变量 /
            <span className="font-bold text-slate-600">{params.length - variableParams.length}</span> 个固定
          </div>
        </div>

        {/* 5个参数卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {params.map(param => (
            <ParamCard
              key={param.id}
              param={param}
              onToggleDisplayDimension={() => toggleDisplayDimension(param.id)}
            />
          ))}
        </div>

        {/* 提示信息 */}
        {displayDimensions.length === 0 && (
          <div className="mt-6 bg-slate-50 rounded-xl p-4 border border-slate-200 flex items-center gap-3">
            <Info size={16} className="text-slate-500" />
            <p className="text-sm text-slate-600">请至少选择一个变量作为展示维度</p>
          </div>
        )}

        {displayDimensions.length >= 3 && (
          <div className="mt-6 bg-amber-50 rounded-xl p-4 border border-amber-200 flex items-center gap-3">
            <Info size={16} className="text-amber-600" />
            <p className="text-sm text-amber-700">建议选择1-2个维度，过多维度会使图表难以阅读</p>
          </div>
        )}
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700 text-sm">
          <div className="flex items-center gap-2">
            <Info size={16} />
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* 加载状态 */}
      {isLoading && (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-200 border-t-purple-600 mb-4"></div>
          <p className="text-slate-600 font-bold">加载数据中...</p>
        </div>
      )}

      {/* 结果展示 */}
      {!isLoading && stats.length > 0 && (
        <ResultsVisualization
          stats={stats}
          params={params}
          displayDimensions={displayDimensions}
          selectedCase={selectedCase}
        />
      )}
    </div>
  )
}

// 参数卡片组件
function ParamCard({ param, onToggleDisplayDimension }: { param: ParamConfig; onToggleDisplayDimension: () => void }) {
  return (
    <div className={cn("rounded-xl border-2 p-4 transition-all", PARAM_COLORS[param.id])}>
      {/* 标题行：名称 + 状态标识 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1">
          <span className="text-sm font-bold">{param.name}</span>
          <span className={cn("text-xs font-mono", PARAM_TEXT_COLORS[param.id])}>
            {param.symbol}
          </span>
        </div>
        <div className={cn(
          "px-2 py-0.5 rounded text-xs font-bold",
          param.isVariable ? "bg-white text-purple-700" : "bg-slate-200 text-slate-500"
        )}>
          {param.isVariable ? "变量" : "固定"}
        </div>
      </div>

      {/* 内容 */}
      {param.state === 'fixed' && (
        <div className="text-center">
          <span className="text-xs text-slate-500 mr-1">=</span>
          <span className="text-lg font-black font-mono">{param.fixedValue}</span>
        </div>
      )}

      {param.state === 'range' && param.range && (
        <div className="text-center text-xs">
          <span className="text-slate-500">[</span>
          <span className="font-mono font-bold">{param.range.min}</span>
          <span className="text-slate-400 mx-1">~</span>
          <span className="font-mono font-bold">{param.range.max}</span>
          <span className="text-slate-500">]</span>
        </div>
      )}

      {param.state === 'discrete' && param.discreteValues && (
        <div className="flex flex-wrap gap-1">
          {param.discreteValues.map(v => (
            <span key={v} className="px-1.5 py-0.5 bg-white rounded text-xs font-mono font-bold">
              {typeof v === 'number' && v < 1 && v !== 0 ? v.toFixed(2) : v}
            </span>
          ))}
        </div>
      )}

      {/* 变量参数：显示维度切换 */}
      {param.isVariable && (
        <div className="mt-3 pt-3 border-t border-black/10">
          <button
            onClick={onToggleDisplayDimension}
            className={cn(
              "w-full flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-bold transition-all",
              param.isDisplayDimension
                ? "bg-purple-600 text-white hover:bg-purple-700"
                : "bg-white text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            )}
          >
            <Filter size={12} />
            {param.isDisplayDimension ? "显示维度 ✓" : "设为显示维度"}
          </button>
        </div>
      )}

      {/* 固定参数：状态标签 */}
      {!param.isVariable && (
        <div className="mt-3 pt-3 border-t border-black/10">
          <span className="inline-flex items-center gap-1 text-xs font-bold text-slate-400">
            <Settings size={12} />
            固定参数
          </span>
        </div>
      )}
    </div>
  )
}

// 结果可视化组件
function ResultsVisualization({
  stats,
  params,
  displayDimensions,
  selectedCase
}: {
  stats: StatsResult[]
  params: ParamConfig[]
  displayDimensions: ParamConfig[]
  selectedCase?: CaseConfig
}) {
  const colors = {
    beta: '#3b82f6',
    eta: '#10b981',
    gamma: '#f59e0b'
  }

  // 获取X轴标签
  const getXLabel = () => {
    const firstVar = displayDimensions[0]
    if (firstVar.id === 'process') return selectedCase?.processSymbol || 'δ'
    return firstVar.symbol
  }

  // 计算颜色范围
  const getColorForValue = (value: number, absMax: number): string => {
    const ratio = value / absMax
    if (ratio > 0) {
      const intensity = Math.min(Math.abs(ratio), 1)
      return `rgba(239, 68, 68, ${0.3 + intensity * 0.7})`
    } else {
      const intensity = Math.min(Math.abs(ratio), 1)
      return `rgba(59, 130, 246, ${0.3 + intensity * 0.7})`
    }
  }

  return (
    <div className="space-y-6">
      {/* 固定参数说明 */}
      <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
        <div className="flex items-center gap-2 mb-2">
          <Info className="text-slate-500" size={16} />
          <span className="text-sm font-bold text-slate-600">固定参数：</span>
        </div>
        <div className="flex flex-wrap gap-4 text-sm">
          {params.filter(p => !p.isVariable).map(p => (
            <span key={p.id} className="text-slate-600">
              {p.symbol} = <span className="font-mono font-bold">{p.fixedValue}</span>
            </span>
          ))}
        </div>
      </div>

      {/* 维度说明 */}
      <div className="bg-blue-50 rounded-xl p-4 border border-blue-200">
        <div className="flex items-center gap-2 mb-2">
          <Filter className="text-blue-600" size={16} />
          <span className="text-sm font-bold text-blue-800">展示维度：</span>
        </div>
        <p className="text-sm text-blue-700">
          {displayDimensions.map(p => p.symbol).join(' × ')}
          <span className="ml-2 font-mono">（{stats.length} 种组合）</span>
        </p>
      </div>

      {/* 指标说明卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <div className="text-xs font-bold text-slate-500 mb-1">偏差</div>
          <div className="text-lg font-black text-slate-800">估计均值 - 真值</div>
          <div className="text-xs text-slate-400 mt-1">正值=高估, 负值=低估</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <div className="text-xs font-bold text-slate-500 mb-1">标准差 (SD)</div>
          <div className="text-lg font-black text-slate-800">√方差</div>
          <div className="text-xs text-slate-400 mt-1">100次结果的波动程度</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <div className="text-xs font-bold text-slate-500 mb-1">均方误差 (MSE)</div>
          <div className="text-lg font-black text-slate-800">偏差² + 方差</div>
          <div className="text-xs text-slate-400 mt-1">综合准确性和稳定性</div>
        </div>
      </div>

      {/* 单变量展示：双Y轴趋势图 */}
      {displayDimensions.length === 1 && (
        <>
          {/* 偏差趋势图 */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-lg font-bold text-slate-800 mb-4">偏差随{displayDimensions[0].name}的变化</h3>
            <p className="text-sm text-slate-500 mb-4">
              左轴: β偏差 | 右轴: η/γ偏差
            </p>
            <div className="h-[320px]">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={stats} margin={{ top: 20, right: 60, bottom: 40, left: 60 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis
                    dataKey="keyLabel"
                    tick={{ fontSize: 11 }}
                    label={{ value: displayDimensions[0].symbol, position: 'insideBottom', offset: -5, fontSize: 12, fill: '#64748b' }}
                  />
                  <YAxis
                    yAxisId="left"
                    tick={{ fontSize: 10 }}
                    label={{ value: 'β 偏差', angle: -90, position: 'insideLeft', fontSize: 12, fill: colors.beta }}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tick={{ fontSize: 10 }}
                    label={{ value: 'η/γ 偏差', angle: -90, position: 'insideRight', fontSize: 12, fill: '#64748b' }}
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                    formatter={(value: number, name: string) => {
                      if (name.includes('β')) return [value.toFixed(4), name]
                      return [value.toFixed(2), name]
                    }}
                  />
                  <Legend />
                  <ReferenceLine yAxisId="left" y={0} stroke={colors.beta} strokeDasharray="3 3" strokeWidth={1} />
                  <ReferenceLine yAxisId="right" y={0} stroke="#94a3b8" strokeDasharray="3 3" strokeWidth={1} />
                  <Line yAxisId="left" type="monotone" dataKey="bias_beta_mean" name="β 偏差" stroke={colors.beta} strokeWidth={2} dot={{ r: 4 }} />
                  <Line yAxisId="right" type="monotone" dataKey="bias_eta_mean" name="η 偏差" stroke={colors.eta} strokeWidth={2} dot={{ r: 4 }} />
                  <Line yAxisId="right" type="monotone" dataKey="bias_gamma_mean" name="γ 偏差" stroke={colors.gamma} strokeWidth={2} dot={{ r: 4 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* SD趋势图 */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-lg font-bold text-slate-800 mb-4">标准差 (SD) 随{displayDimensions[0].name}的变化</h3>
            <p className="text-sm text-slate-500 mb-4">
              左轴: β SD | 右轴: η/γ SD
            </p>
            <div className="h-[320px]">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={stats} margin={{ top: 20, right: 60, bottom: 40, left: 60 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis
                    dataKey="keyLabel"
                    tick={{ fontSize: 11 }}
                    label={{ value: displayDimensions[0].symbol, position: 'insideBottom', offset: -5, fontSize: 12, fill: '#64748b' }}
                  />
                  <YAxis
                    yAxisId="left"
                    tick={{ fontSize: 10 }}
                    label={{ value: 'β SD', angle: -90, position: 'insideLeft', fontSize: 12, fill: colors.beta }}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tick={{ fontSize: 10 }}
                    label={{ value: 'η/γ SD', angle: -90, position: 'insideRight', fontSize: 12, fill: '#64748b' }}
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                    formatter={(value: number, name: string) => {
                      if (name.includes('β')) return [value.toFixed(4), name]
                      return [value.toFixed(2), name]
                    }}
                  />
                  <Legend />
                  <Line yAxisId="left" type="monotone" dataKey="bias_beta_std" name="β SD" stroke={colors.beta} strokeWidth={2} dot={{ r: 4 }} />
                  <Line yAxisId="right" type="monotone" dataKey="bias_eta_std" name="η SD" stroke={colors.eta} strokeWidth={2} dot={{ r: 4 }} />
                  <Line yAxisId="right" type="monotone" dataKey="bias_gamma_std" name="γ SD" stroke={colors.gamma} strokeWidth={2} dot={{ r: 4 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* MSE趋势图 */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-lg font-bold text-slate-800 mb-4">均方误差 (MSE) 随{displayDimensions[0].name}的变化</h3>
            <p className="text-sm text-slate-500 mb-4">
              左轴: β MSE | 右轴: η/γ MSE
            </p>
            <div className="h-[320px]">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={stats} margin={{ top: 20, right: 60, bottom: 40, left: 60 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis
                    dataKey="keyLabel"
                    tick={{ fontSize: 11 }}
                    label={{ value: displayDimensions[0].symbol, position: 'insideBottom', offset: -5, fontSize: 12, fill: '#64748b' }}
                  />
                  <YAxis
                    yAxisId="left"
                    tick={{ fontSize: 10 }}
                    label={{ value: 'β MSE', angle: -90, position: 'insideLeft', fontSize: 12, fill: colors.beta }}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tick={{ fontSize: 10 }}
                    label={{ value: 'η/γ MSE', angle: -90, position: 'insideRight', fontSize: 12, fill: '#64748b' }}
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                    formatter={(value: number, name: string) => {
                      if (name.includes('β')) return [value.toFixed(4), name]
                      return [value.toFixed(2), name]
                    }}
                  />
                  <Legend />
                  <Line yAxisId="left" type="monotone" dataKey="mse_beta" name="β MSE" stroke={colors.beta} strokeWidth={2} dot={{ r: 4 }} />
                  <Line yAxisId="right" type="monotone" dataKey="mse_eta" name="η MSE" stroke={colors.eta} strokeWidth={2} dot={{ r: 4 }} />
                  <Line yAxisId="right" type="monotone" dataKey="mse_gamma" name="γ MSE" stroke={colors.gamma} strokeWidth={2} dot={{ r: 4 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}

      {/* 多变量展示：热力图 */}
      {displayDimensions.length >= 2 && (
        <>
          <HeatmapCard
            title={`β 偏差热力图 (${displayDimensions.map(p => p.symbol).join(' × ')})`}
            stats={stats}
            displayDimensions={displayDimensions}
            dataKey="bias_beta_mean"
            color={colors.beta}
            getColorForValue={getColorForValue}
          />
          <HeatmapCard
            title={`η 偏差热力图 (${displayDimensions.map(p => p.symbol).join(' × ')})`}
            stats={stats}
            displayDimensions={displayDimensions}
            dataKey="bias_eta_mean"
            color={colors.eta}
            getColorForValue={getColorForValue}
          />
          <HeatmapCard
            title={`γ 偏差热力图 (${displayDimensions.map(p => p.symbol).join(' × ')})`}
            stats={stats}
            displayDimensions={displayDimensions}
            dataKey="bias_gamma_mean"
            color={colors.gamma}
            getColorForValue={getColorForValue}
          />
        </>
      )}

      {/* 详细统计表 */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h3 className="text-lg font-bold text-slate-800 mb-4">详细统计结果</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-2 px-3 font-bold text-slate-700">参数组合</th>
                <th className="text-right py-2 px-3 font-bold text-slate-700">β 偏差±SD</th>
                <th className="text-right py-2 px-3 font-bold text-slate-700">η 偏差±SD</th>
                <th className="text-right py-2 px-3 font-bold text-slate-700">γ 偏差±SD</th>
              </tr>
            </thead>
            <tbody>
              {stats.map((s, idx) => (
                <tr key={idx} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-2 px-3 font-mono text-xs">{s.keyLabel}</td>
                  <td className="text-right py-2 px-3 font-mono text-xs">
                    {s.bias_beta_mean.toFixed(4)} ± {s.bias_beta_std.toFixed(4)}
                  </td>
                  <td className="text-right py-2 px-3 font-mono text-xs">
                    {s.bias_eta_mean.toFixed(2)} ± {s.bias_eta_std.toFixed(2)}
                  </td>
                  <td className="text-right py-2 px-3 font-mono text-xs">
                    {s.bias_gamma_mean.toFixed(2)} ± {s.bias_gamma_std.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// 热力图卡片组件
interface HeatmapCardProps {
  title: string
  stats: StatsResult[]
  displayDimensions: ParamConfig[]
  dataKey: 'bias_beta_mean' | 'bias_eta_mean' | 'bias_gamma_mean'
  color: string
  getColorForValue: (value: number, absMax: number) => string
}

function HeatmapCard({
  title,
  stats,
  displayDimensions,
  dataKey,
  color,
  getColorForValue
}: HeatmapCardProps) {
  // 计算颜色范围
  const allValues = stats.map(s => s[dataKey])
  const absMax = Math.max(...allValues.map(Math.abs), 0.01)

  // 获取第一维度的所有唯一值
  const getFirstDimensionValues = () => {
    const dim = displayDimensions[0]
    const valueSet = new Set(stats.map(s => {
      if (dim.id === 'beta') return s.beta_true
      if (dim.id === 'sampleSize') return s.sample_size
      if (dim.id === 'process') return s.offset_value
      return 0
    }))
    const values = Array.from(valueSet).filter((v): v is number => v !== undefined) as number[]
    return values.sort((a, b) => a - b)
  }

  // 获取第二维度的所有值
  const getSecondDimensionValues = () => {
    if (displayDimensions.length < 2) return []
    const dim = displayDimensions[1]
    const valueSet = new Set(stats.map(s => {
      if (dim.id === 'beta') return s.beta_true
      if (dim.id === 'sampleSize') return s.sample_size
      if (dim.id === 'process') return s.offset_value
      return 0
    }))
    const values = Array.from(valueSet).filter((v): v is number => v !== undefined) as number[]
    return values.sort((a, b) => a - b)
  }

  const firstDimValues = getFirstDimensionValues()
  const secondDimValues = getSecondDimensionValues()

  // 获取显示标签
  const formatValue = (val: number, param: ParamType) => {
    if (param === 'process' || (typeof val === 'number' && val < 1 && val !== 0)) {
      return val.toFixed(2)
    }
    return val.toString()
  }

  // 构建热力图数据矩阵
  const heatmapData = secondDimValues.map(yVal =>
    firstDimValues.map(xVal => {
      const item = stats.find(s => {
        const matchX = displayDimensions[0].id === 'beta' ? s.beta_true === xVal
                      : displayDimensions[0].id === 'sampleSize' ? s.sample_size === xVal
                      : s.offset_value === xVal
        const matchY = displayDimensions[1].id === 'beta' ? s.beta_true === yVal
                      : displayDimensions[1].id === 'sampleSize' ? s.sample_size === yVal
                      : s.offset_value === yVal
        return matchX && matchY
      })
      return {
        value: item?.[dataKey] ?? 0,
        hasData: !!item
      }
    })
  )

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
      <h3 className="text-lg font-bold text-slate-800 mb-4">{title}</h3>

      {/* 图例 */}
      <div className="flex items-center justify-center gap-4 mb-4">
        <span className="text-xs font-bold text-slate-600">负偏差</span>
        <div className="flex items-center">
          <div className="w-8 h-4 rounded" style={{ backgroundColor: getColorForValue(-absMax, absMax) }}></div>
          <span className="text-xs text-slate-500 mx-1">←</span>
          <div className="w-8 h-4 rounded bg-slate-200"></div>
          <span className="text-xs text-slate-500 mx-1">→</span>
          <div className="w-8 h-4 rounded" style={{ backgroundColor: getColorForValue(absMax, absMax) }}></div>
        </div>
        <span className="text-xs font-bold text-slate-600">正偏差</span>
        <span className="text-xs text-slate-400 ml-4">{absMax.toFixed(4)}</span>
      </div>

      {/* 热力图 */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr>
              <th className="p-2 bg-slate-50"></th>
              {firstDimValues.map(val => (
                <th key={val} className="p-2 bg-slate-50 text-xs font-bold text-slate-600 min-w-[60px]">
                  {formatValue(val, displayDimensions[0].id)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {secondDimValues.map((yVal, yIdx) => (
              <tr key={yVal}>
                <td className="p-2 bg-slate-50 text-xs font-bold text-slate-600 whitespace-nowrap">
                  {formatValue(yVal, displayDimensions[1].id)}
                </td>
                {heatmapData[yIdx].map((cell, xIdx) => (
                  <td
                    key={xIdx}
                    className="p-2 text-center border border-slate-100 min-w-[60px]"
                    style={{
                      backgroundColor: cell.hasData ? getColorForValue(cell.value, absMax) : '#f1f5f9'
                    }}
                  >
                    <span className={cell.hasData ? 'font-mono text-xs font-bold' : 'text-xs text-slate-300'}>
                      {cell.hasData ? cell.value.toFixed(3) : '—'}
                    </span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
