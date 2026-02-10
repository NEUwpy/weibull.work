"use client"

import React, { useState, useEffect } from 'react'
import { Filter, Info, Settings, ChevronDown } from 'lucide-react'
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
  defaults?: {  // 默认基准值
    beta?: number
    eta?: number
    gamma?: number
    sampleSize?: number
    process?: number
  }
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

// 从MD文件读取案例配置

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
  const [cases, setCases] = useState<CaseConfig[]>([])
  const [isLoadingConfig, setIsLoadingConfig] = useState(true)

  const selectedCase = cases.find(c => c.id === selectedCaseId)

  // 加载案例配置
  useEffect(() => {
    const loadCases = async () => {
      try {
        const res = await fetch(`/api/cases/${methodId.toLowerCase()}`)
        if (res.ok) {
          const data = await res.json()
          setCases(data.cases || [])
          if (data.cases && data.cases.length > 0) {
            setSelectedCaseId(data.cases[0].id)
          }
        }
      } catch (err) {
        console.error('Failed to load cases:', err)
      } finally {
        setIsLoadingConfig(false)
      }
    }
    loadCases()
  }, [methodId])

  // 初始化参数配置
  useEffect(() => {
    if (selectedCase && selectedCase.params && Array.isArray(selectedCase.params) && selectedCase.params.length > 0) {
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
    if (!selectedCase?.csvFile) {
      console.log('No CSV file path:', selectedCase)
      return
    }

    setIsLoading(true)
    setError(null)

    console.log('Loading CSV from:', selectedCase.csvFile)

    fetch(selectedCase.csvFile)
      .then(res => {
        if (!res.ok) throw new Error('数据文件加载失败')
        return res.text()
      })
      .then(csvText => {
        const parsedData = parseCSV(csvText)
        console.log('CSV parsed, rows:', parsedData.length)
        setCsvData(parsedData)
      })
      .catch(err => {
        setError(err.message || '数据加载失败')
        console.error('CSV load error:', err)
      })
      .finally(() => {
        setIsLoading(false)
      })
  }, [selectedCase])

  // 当数据或参数变化时，重新计算统计量
  useEffect(() => {
    if (csvData.length === 0) return

    const displayDimensions = params.filter(p => p.isDisplayDimension)
    console.log('Display dimensions:', displayDimensions.map(p => p.id))
    if (displayDimensions.length === 0) return

    const statsResult = calculateStats(csvData, displayDimensions)
    console.log('Stats calculated:', statsResult.length)
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
    // 获取默认值
    const defaults = selectedCase?.defaults || {}

    // 先过滤数据：只保留非变量参数符合默认值的数据行
    const filteredData = data.filter(row => {
      // 如果beta不是变量，检查是否等于默认值
      if (!variableParams.find(p => p.id === 'beta')) {
        if (defaults.beta !== undefined && row.beta_true !== defaults.beta) return false
      }
      // 如果sampleSize不是变量，检查是否等于默认值
      if (!variableParams.find(p => p.id === 'sampleSize')) {
        if (defaults.sampleSize !== undefined && row.sample_size !== defaults.sampleSize) return false
      }
      // 如果process不是变量，检查是否等于默认值
      if (!variableParams.find(p => p.id === 'process')) {
        if (defaults.process !== undefined && row.offset_value !== defaults.process) return false
      }
      return true
    })

    const groups = new Map<string, SimulationRow[]>()

    filteredData.forEach(row => {
      const keyParts: string[] = []
      const labelParts: string[] = []
      variableParams.forEach(p => {
        if (p.id === 'beta') {
          keyParts.push(`β=${row.beta_true}`)
          labelParts.push(String(row.beta_true))
        }
        if (p.id === 'sampleSize') {
          keyParts.push(`n=${row.sample_size}`)
          labelParts.push(String(row.sample_size))
        }
        if (p.id === 'process') {
          keyParts.push(`${selectedCase?.processSymbol || 'δ'}=${row.offset_value}`)
          // 对于偏移量，如果是小数则显示2位，否则显示整数
          const val = row.offset_value
          labelParts.push(typeof val === 'number' && val < 1 && val !== 0 ? val.toFixed(2) : String(val))
        }
      })

      const key = keyParts.join(', ')
      const label = labelParts.length === 1 ? labelParts[0] : keyParts.join(', ')
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

      // 生成标签
      const labelParts: string[] = []
      variableParams.forEach(p => {
        if (p.id === 'beta') {
          const val = rows[0].beta_true
          labelParts.push(String(val))
        }
        if (p.id === 'sampleSize') {
          const val = rows[0].sample_size
          labelParts.push(String(val))
        }
        if (p.id === 'process') {
          const val = rows[0].offset_value
          labelParts.push(typeof val === 'number' && val < 1 && val !== 0 ? val.toFixed(2) : String(val))
        }
      })

      return {
        key,
        keyLabel: labelParts.length === 1 ? labelParts[0] : labelParts.join(', '),
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

  if (isLoadingConfig) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-4 border-purple-200 border-t-purple-600 mb-4"></div>
          <p className="text-slate-600 font-bold">加载配置中...</p>
        </div>
      </div>
    )
  }

  if (cases.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center text-center">
          <Settings className="text-slate-300 mb-4" size={48} />
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
      {/* 案例选择 */}
      {cases.length > 0 && (
        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-4">
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
                {cases.map(case_ => (
                  <option key={case_.id} value={case_.id}>
                    {case_.name}
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={18} />
            </div>
            {selectedCase && (
              <span className="text-xs text-slate-500">{selectedCase.description}</span>
            )}
          </div>
        </div>
      )}

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
    beta: '#1e40af',      // 深蓝色
    eta: '#047857',       // 深绿色
    gamma: '#b45309'      // 深橙色
  }

  // 图表编号
  const getFigureNumber = (index: number) => `图 ${index + 1}`

  // 表格编号
  const getTableNumber = (index: number) => `表 ${index + 1}`

  // 获取X轴标签
  const getXLabel = () => {
    const firstVar = displayDimensions[0]
    if (firstVar.id === 'process') return selectedCase?.processSymbol || 'δ'
    return firstVar.symbol
  }

  // 计算颜色范围（热力图用）
  const getColorForValue = (value: number, absMax: number): string => {
    const ratio = value / absMax
    if (ratio > 0) {
      const intensity = Math.min(Math.abs(ratio), 1)
      return `rgba(220, 38, 38, ${0.2 + intensity * 0.6})`  // 红色系，透明度降低
    } else {
      const intensity = Math.min(Math.abs(ratio), 1)
      return `rgba(30, 64, 175, ${0.2 + intensity * 0.6})`  // 蓝色系，透明度降低
    }
  }

  return (
    <div className="space-y-6">
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
        {/* 显示其他变量参数固定在默认值 */}
        {selectedCase?.defaults && displayDimensions.length < params.filter(p => p.isVariable).length && (
          <div className="mt-2 pt-2 border-t border-blue-200">
            <span className="text-xs text-blue-600">其他变量固定在：</span>
            <span className="text-xs text-blue-700 ml-2 font-mono">
              {params.filter(p => p.isVariable && !displayDimensions.some(d => d.id === p.id)).map(p => {
                if (p.id === 'beta') return `β=${selectedCase.defaults?.beta}`
                if (p.id === 'sampleSize') return `n=${selectedCase.defaults?.sampleSize}`
                if (p.id === 'process') return `${selectedCase?.processSymbol || 'δ'}=${selectedCase.defaults?.process}`
                return ''
              }).filter(Boolean).join(', ')}
            </span>
          </div>
        )}
      </div>

      {/* 参数汇总表 - 单变量 */}
      {displayDimensions.length === 1 && (
        <div className="bg-white border border-slate-300 p-4">
          <p className="text-center text-sm font-semibold text-slate-700 mb-3">
            {getTableNumber(0)}: 参数估计汇总统计 (按{displayDimensions[0].name}分组)
          </p>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b-2 border-slate-400">
                <th className="text-center py-2 px-3 font-bold text-slate-800 border-b-2 border-slate-400 w-24">{displayDimensions[0].symbol}</th>
                <th className="text-center py-2 px-3 font-bold text-slate-800 border-b-2 border-slate-400 w-20">参数</th>
                <th className="text-right py-2 px-3 font-bold text-slate-800 border-b-2 border-slate-400">真实值</th>
                <th className="text-right py-2 px-3 font-bold text-slate-800 border-b-2 border-slate-400">估计均值</th>
                <th className="text-right py-2 px-3 font-bold text-slate-800 border-b-2 border-slate-400">偏差</th>
                <th className="text-right py-2 px-3 font-bold text-slate-800 border-b-2 border-slate-400">SD</th>
                <th className="text-right py-2 px-3 font-bold text-slate-800 border-b-2 border-slate-400">MSE</th>
              </tr>
            </thead>
            <tbody>
              {stats.map((s, idx) => {
                // 获取变量值
                const varValue = s.keyLabel

                // 获取固定参数的真实值（从defaults中获取）
                const getFixedTrueValue = (paramType: 'eta' | 'gamma'): number => {
                  return selectedCase?.defaults?.[paramType] ?? 1000
                }

                // β 的真实值
                const betaTrueValue = s.beta_true ?? selectedCase?.defaults?.beta ?? 2.0
                // η 和 γ 是固定的
                const etaTrueValue = getFixedTrueValue('eta')
                const gammaTrueValue = getFixedTrueValue('gamma')

                return (
                  <React.Fragment key={idx}>
                    {/* β 行 */}
                    <tr className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                      <td rowSpan={3} className="py-1.5 px-3 font-mono text-xs text-slate-700 border-b border-slate-200 text-center vertical-align-middle">
                        {varValue}
                      </td>
                      <td className="py-1.5 px-3 font-bold text-slate-800 border-b border-slate-200 text-center">β</td>
                      <td className="text-right py-1.5 px-3 font-mono text-xs text-slate-700 border-b border-slate-200">
                        {displayDimensions[0].id === 'beta' ? '—' : betaTrueValue}
                      </td>
                      <td className="text-right py-1.5 px-3 font-mono text-xs text-slate-700 border-b border-slate-200">
                        {displayDimensions[0].id === 'beta' ? '—' : (betaTrueValue + s.bias_beta_mean).toFixed(4)}
                      </td>
                      <td className="text-right py-1.5 px-3 font-mono text-xs text-slate-700 border-b border-slate-200">{s.bias_beta_mean.toFixed(4)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-xs text-slate-700 border-b border-slate-200">{s.bias_beta_std.toFixed(4)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-xs text-slate-700 border-b border-slate-200">{s.mse_beta.toFixed(4)}</td>
                    </tr>
                    {/* η 行 */}
                    <tr className={idx % 2 === 0 ? 'bg-slate-50' : 'bg-white'}>
                      <td className="py-1.5 px-3 font-bold text-slate-800 border-b border-slate-200 text-center">η</td>
                      <td className="text-right py-1.5 px-3 font-mono text-xs text-slate-700 border-b border-slate-200">{etaTrueValue}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-xs text-slate-700 border-b border-slate-200">{(etaTrueValue + s.bias_eta_mean).toFixed(2)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-xs text-slate-700 border-b border-slate-200">{s.bias_eta_mean.toFixed(2)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-xs text-slate-700 border-b border-slate-200">{s.bias_eta_std.toFixed(2)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-xs text-slate-700 border-b border-slate-200">{s.mse_eta.toFixed(2)}</td>
                    </tr>
                    {/* γ 行 */}
                    <tr className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                      <td className="py-1.5 px-3 font-bold text-slate-800 border-b border-slate-200 text-center">γ</td>
                      <td className="text-right py-1.5 px-3 font-mono text-xs text-slate-700 border-b border-slate-200">{gammaTrueValue}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-xs text-slate-700 border-b border-slate-200">{(gammaTrueValue + s.bias_gamma_mean).toFixed(2)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-xs text-slate-700 border-b border-slate-200">{s.bias_gamma_mean.toFixed(2)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-xs text-slate-700 border-b border-slate-200">{s.bias_gamma_std.toFixed(2)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-xs text-slate-700 border-b border-slate-200">{s.mse_gamma.toFixed(2)}</td>
                    </tr>
                  </React.Fragment>
                )
              })}
            </tbody>
          </table>
          <p className="text-center text-xs text-slate-500 mt-3">
            注: 估计均值 = 真实值 + 偏差, 基于100次蒙特卡洛模拟. 其他参数固定在默认值.
          </p>
        </div>
      )}

      {/* 多变量提示 */}
      {displayDimensions.length >= 2 && (
        <div className="bg-white border border-slate-300 p-4">
          <p className="text-sm text-slate-600 text-center">
            多维度分析：请查看下方的热力图和详细统计表
          </p>
        </div>
      )}

      {/* 单变量展示：双Y轴趋势图 */}
      {displayDimensions.length === 1 && (
        <>
          {/* 图1: 偏差趋势图 */}
          <div className="bg-white border border-slate-300 p-3">
            <div className="h-[400px]">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={stats} margin={{ top: 5, right: 15, bottom: 40, left: 55 }}>
                  <XAxis
                    dataKey="keyLabel"
                    tick={{ fontSize: 15, fill: '#374151' }}
                    tickLine={true}
                    stroke="#000"
                    strokeWidth={1}
                    label={{
                      value: displayDimensions[0].id === 'sampleSize' ? `样本量${displayDimensions[0].symbol}` : displayDimensions[0].symbol,
                      position: 'insideBottom',
                      offset: -23,
                      fontSize: 16,
                      fontWeight: 600,
                      fill: '#1f2937'
                    }}
                    axisLine={{ stroke: '#000', strokeWidth: 1 }}
                  />
                  <YAxis
                    yAxisId="left"
                    tick={{ fontSize: 14, fill: colors.beta }}
                    tickLine={true}
                    stroke={colors.beta}
                    strokeWidth={1}
                    tickSize={4}
                    label={{
                      value: 'β 偏差',
                      angle: -90,
                      position: 'insideLeft',
                      offset: -3,
                      fontSize: 16,
                      fontWeight: 600,
                      fill: colors.beta
                    }}
                    axisLine={{ stroke: colors.beta, strokeWidth: 1 }}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tick={{ fontSize: 14, fill: '#6b7280' }}
                    tickLine={true}
                    stroke="#6b7280"
                    strokeWidth={1}
                    tickSize={4}
                    label={{
                      value: 'η、γ 偏差',
                      angle: -90,
                      position: 'insideRight',
                      offset: -3,
                      dy: -50,
                      fontSize: 16,
                      fontWeight: 600,
                      fill: '#6b7280'
                    }}
                    axisLine={{ stroke: '#6b7280', strokeWidth: 1 }}
                  />
                  <Tooltip
                    contentStyle={{
                      borderRadius: '4px',
                      border: '1px solid #e5e7eb',
                      boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                      fontSize: '13px'
                    }}
                    formatter={(value: number, name: string) => {
                      if (name.includes('β')) return [value.toFixed(4), name]
                      return [value.toFixed(2), name]
                    }}
                  />
                  <Legend
                    verticalAlign="top"
                    align="right"
                    wrapperStyle={{ fontSize: '15px', fontWeight: 500, right: 150, marginTop: 20 }}
                  />
                  <ReferenceLine yAxisId="left" y={0} stroke={colors.beta} strokeDasharray="4 4" strokeWidth={1} />
                  <ReferenceLine yAxisId="right" y={0} stroke="#6b7280" strokeDasharray="4 4" strokeWidth={1} />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="bias_beta_mean"
                    name="β"
                    stroke={colors.beta}
                    strokeWidth={2.5}
                    dot={{ r: 5, strokeWidth: 2 }}
                    connectNulls={false}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="bias_eta_mean"
                    name="η"
                    stroke={colors.eta}
                    strokeWidth={2.5}
                    dot={{ r: 5, strokeWidth: 2 }}
                    connectNulls={false}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="bias_gamma_mean"
                    name="γ"
                    stroke={colors.gamma}
                    strokeWidth={2.5}
                    dot={{ r: 5, strokeWidth: 2 }}
                    connectNulls={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <p className="text-center text-base font-semibold text-slate-700 mt-0.5">
              {getFigureNumber(1)}: {displayDimensions[0].name}对参数估计偏差的影响
            </p>
          </div>

          {/* 图2: SD趋势图 */}
          <div className="bg-white border border-slate-300 p-3">
            <div className="h-[400px]">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={stats} margin={{ top: 5, right: 15, bottom: 40, left: 55 }}>
                  <XAxis
                    dataKey="keyLabel"
                    tick={{ fontSize: 15, fill: '#374151' }}
                    tickLine={true}
                    stroke="#000"
                    strokeWidth={1}
                    label={{
                      value: displayDimensions[0].id === 'sampleSize' ? `样本量${displayDimensions[0].symbol}` : displayDimensions[0].symbol,
                      position: 'insideBottom',
                      offset: -23,
                      fontSize: 16,
                      fontWeight: 600,
                      fill: '#1f2937'
                    }}
                    axisLine={{ stroke: '#000', strokeWidth: 1 }}
                  />
                  <YAxis
                    yAxisId="left"
                    tick={{ fontSize: 14, fill: colors.beta }}
                    tickLine={true}
                    stroke={colors.beta}
                    strokeWidth={1}
                    tickSize={4}
                    label={{
                      value: 'β 标准差',
                      angle: -90,
                      position: 'insideLeft',
                      offset: -3,
                      fontSize: 16,
                      fontWeight: 600,
                      fill: colors.beta
                    }}
                    axisLine={{ stroke: colors.beta, strokeWidth: 1 }}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tick={{ fontSize: 14, fill: '#6b7280' }}
                    tickLine={true}
                    stroke="#6b7280"
                    strokeWidth={1}
                    tickSize={4}
                    label={{
                      value: 'η、γ 标准差',
                      angle: -90,
                      position: 'insideRight',
                      offset: -3,
                      dy: -50,
                      fontSize: 16,
                      fontWeight: 600,
                      fill: '#6b7280'
                    }}
                    axisLine={{ stroke: '#6b7280', strokeWidth: 1 }}
                  />
                  <Tooltip
                    contentStyle={{
                      borderRadius: '4px',
                      border: '1px solid #e5e7eb',
                      boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                      fontSize: '13px'
                    }}
                    formatter={(value: number, name: string) => {
                      if (name.includes('β')) return [value.toFixed(4), name]
                      return [value.toFixed(2), name]
                    }}
                  />
                  <Legend
                    verticalAlign="top"
                    align="right"
                    wrapperStyle={{ fontSize: '15px', fontWeight: 500, right: 150, marginTop: 20 }}
                  />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="bias_beta_std"
                    name="β"
                    stroke={colors.beta}
                    strokeWidth={2.5}
                    dot={{ r: 5, strokeWidth: 2 }}
                    connectNulls={false}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="bias_eta_std"
                    name="η"
                    stroke={colors.eta}
                    strokeWidth={2.5}
                    dot={{ r: 5, strokeWidth: 2 }}
                    connectNulls={false}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="bias_gamma_std"
                    name="γ"
                    stroke={colors.gamma}
                    strokeWidth={2.5}
                    dot={{ r: 5, strokeWidth: 2 }}
                    connectNulls={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <p className="text-center text-base font-semibold text-slate-700 mt-0.5">
              {getFigureNumber(2)}: {displayDimensions[0].name}对参数估计标准差的影响
            </p>
          </div>

          {/* 图3: MSE趋势图 */}
          <div className="bg-white border border-slate-300 p-3">
            <div className="h-[400px]">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={stats} margin={{ top: 5, right: 15, bottom: 40, left: 55 }}>
                  <XAxis
                    dataKey="keyLabel"
                    tick={{ fontSize: 15, fill: '#374151' }}
                    tickLine={true}
                    stroke="#000"
                    strokeWidth={1}
                    label={{
                      value: displayDimensions[0].id === 'sampleSize' ? `样本量${displayDimensions[0].symbol}` : displayDimensions[0].symbol,
                      position: 'insideBottom',
                      offset: -23,
                      fontSize: 16,
                      fontWeight: 600,
                      fill: '#1f2937'
                    }}
                    axisLine={{ stroke: '#000', strokeWidth: 1 }}
                  />
                  <YAxis
                    yAxisId="left"
                    tick={{ fontSize: 14, fill: colors.beta }}
                    tickLine={true}
                    stroke={colors.beta}
                    strokeWidth={1}
                    tickSize={4}
                    label={{
                      value: 'β 均方误差',
                      angle: -90,
                      position: 'insideLeft',
                      offset: -3,
                      fontSize: 16,
                      fontWeight: 600,
                      fill: colors.beta
                    }}
                    axisLine={{ stroke: colors.beta, strokeWidth: 1 }}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tick={{ fontSize: 14, fill: '#6b7280' }}
                    tickLine={true}
                    stroke="#6b7280"
                    strokeWidth={1}
                    tickSize={4}
                    label={{
                      value: 'η、γ 均方误差',
                      angle: -90,
                      position: 'insideRight',
                      offset: -3,
                      dy: -50,
                      fontSize: 16,
                      fontWeight: 600,
                      fill: '#6b7280'
                    }}
                    axisLine={{ stroke: '#6b7280', strokeWidth: 1 }}
                  />
                  <Tooltip
                    contentStyle={{
                      borderRadius: '4px',
                      border: '1px solid #e5e7eb',
                      boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                      fontSize: '13px'
                    }}
                    formatter={(value: number, name: string) => {
                      if (name.includes('β')) return [value.toFixed(4), name]
                      return [value.toFixed(2), name]
                    }}
                  />
                  <Legend
                    verticalAlign="top"
                    align="right"
                    wrapperStyle={{ fontSize: '15px', fontWeight: 500, right: 150, marginTop: 20 }}
                  />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="mse_beta"
                    name="β"
                    stroke={colors.beta}
                    strokeWidth={2.5}
                    dot={{ r: 5, strokeWidth: 2 }}
                    connectNulls={false}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="mse_eta"
                    name="η"
                    stroke={colors.eta}
                    strokeWidth={2.5}
                    dot={{ r: 5, strokeWidth: 2 }}
                    connectNulls={false}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="mse_gamma"
                    name="γ"
                    stroke={colors.gamma}
                    strokeWidth={2.5}
                    dot={{ r: 5, strokeWidth:2 }}
                    connectNulls={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <p className="text-center text-base font-semibold text-slate-700 mt-0.5">
              {getFigureNumber(3)}: {displayDimensions[0].name}对参数估计均方误差的影响
            </p>
          </div>
        </>
      )}

      {/* 多变量展示：热力图 */}
      {displayDimensions.length >= 2 && (
        <>
          <HeatmapCard
            title={`β 参数偏差热力图`}
            stats={stats}
            displayDimensions={displayDimensions}
            dataKey="bias_beta_mean"
            color={colors.beta}
            figureNumber={getFigureNumber(4)}
            getColorForValue={getColorForValue}
          />
          <HeatmapCard
            title={`η 参数偏差热力图`}
            stats={stats}
            displayDimensions={displayDimensions}
            dataKey="bias_eta_mean"
            color={colors.eta}
            figureNumber={getFigureNumber(5)}
            getColorForValue={getColorForValue}
          />
          <HeatmapCard
            title={`γ 参数偏差热力图`}
            stats={stats}
            displayDimensions={displayDimensions}
            dataKey="bias_gamma_mean"
            color={colors.gamma}
            figureNumber={getFigureNumber(6)}
            getColorForValue={getColorForValue}
          />
        </>
      )}
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
  figureNumber: string
  getColorForValue: (value: number, absMax: number) => string
}

function HeatmapCard({
  title,
  stats,
  displayDimensions,
  dataKey,
  color,
  figureNumber,
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
    <div className="bg-white border border-slate-300 p-4">
      {/* 图例 */}
      <div className="flex items-center justify-center gap-3 mb-3">
        <span className="text-xs font-semibold text-slate-700">低估</span>
        <div className="flex items-center">
          <div className="w-10 h-3 rounded-l" style={{ backgroundColor: getColorForValue(-absMax, absMax) }}></div>
          <div className="w-10 h-3 bg-slate-100"></div>
          <div className="w-10 h-3 rounded-r" style={{ backgroundColor: getColorForValue(absMax, absMax) }}></div>
        </div>
        <span className="text-xs font-semibold text-slate-700">高估</span>
        <span className="text-xs text-slate-500 ml-3">
          <span className="font-mono">[{(-absMax).toFixed(3)}, {absMax.toFixed(3)}]</span>
        </span>
      </div>

      {/* 热力图 */}
      <div className="overflow-x-auto">
        <style jsx>{`
          .diagonal-cell {
            position: relative;
            width: 80px;
            height: 60px;
          }
          .diagonal-cell::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(to top right, transparent calc(50% - 0.5px), #64748b calc(50% - 0.5px), #64748b calc(50% + 0.5px), transparent calc(50% + 0.5px));
            pointer-events: none;
          }
          .diagonal-label-top {
            position: absolute;
            top: 4px;
            right: 6px;
            font-size: 11px;
            font-weight: 600;
            color: #374151;
          }
          .diagonal-label-left {
            position: absolute;
            bottom: 4px;
            left: 6px;
            font-size: 11px;
            font-weight: 600;
            color: #374151;
          }
        `}</style>
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr>
              <th className="bg-slate-50 border border-slate-300">
                <div className="diagonal-cell">
                  <span className="diagonal-label-top">{displayDimensions[0].name}</span>
                  <span className="diagonal-label-left">{displayDimensions[1].name}</span>
                </div>
              </th>
              {firstDimValues.map(val => (
                <th key={val} className="p-2 bg-slate-50 border border-slate-300 text-xs font-bold text-slate-800 min-w-[65px]">
                  {formatValue(val, displayDimensions[0].id)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {secondDimValues.map((yVal, yIdx) => (
              <tr key={yVal}>
                <td className="p-2 bg-slate-50 border border-slate-300 text-xs font-bold text-slate-800 whitespace-nowrap">
                  {formatValue(yVal, displayDimensions[1].id)}
                </td>
                {heatmapData[yIdx].map((cell, xIdx) => (
                  <td
                    key={xIdx}
                    className="p-2 text-center border border-slate-200 min-w-[65px]"
                    style={{
                      backgroundColor: cell.hasData ? getColorForValue(cell.value, absMax) : '#f3f4f6'
                    }}
                  >
                    <span
                      className="font-mono text-xs font-semibold"
                      style={{
                        color: cell.hasData ? '#ffffff' : '#9ca3af'
                      }}
                    >
                      {cell.hasData ? cell.value.toFixed(3) : '—'}
                    </span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-center text-sm font-semibold text-slate-700 mt-3">
        {figureNumber}: {title} ({displayDimensions.map(p => p.symbol).join(' × ')})
      </p>
    </div>
  )
}
