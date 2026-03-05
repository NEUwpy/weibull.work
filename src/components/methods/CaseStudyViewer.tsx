"use client"

import React, { useState, useEffect } from 'react'
import { Filter, Info, Settings, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import rehypeRaw from 'rehype-raw'
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
  ReferenceLine,
  ReferenceArea,
  ScatterChart,
  Scatter,
  BarChart,
  Area,
  Bar,
  Cell
} from 'recharts'
import dynamic from 'next/dynamic'

// 动态导入特殊架构组件，避免SSR问题
const Case3Viewer = dynamic(() => import('./mdm/case-studies/case3/Case3Viewer'), {
  ssr: false,
  loading: () => (
    <div className="bg-white rounded-2xl border border-slate-200 p-12">
      <div className="flex flex-col items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-red-200 border-t-red-600 mb-4"></div>
        <p className="text-slate-600 font-bold">加载无交点分析中...</p>
      </div>
    </div>
  )
})

const Case5Viewer = dynamic(() => import('./mdm/case-studies/case5/Case5Viewer'), {
  ssr: false,
  loading: () => (
    <div className="bg-white rounded-2xl border border-slate-200 p-12">
      <div className="flex flex-col items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-200 border-t-purple-600 mb-4"></div>
        <p className="text-slate-600 font-bold">加载案例5分析中...</p>
      </div>
    </div>
  )
})

const Case6Viewer = dynamic(() => import('./mdm/case-studies/case6/Case6Viewer'), {
  ssr: false,
  loading: () => (
    <div className="bg-white rounded-2xl border border-slate-200 p-12">
      <div className="flex flex-col items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-indigo-200 border-t-indigo-600 mb-4"></div>
        <p className="text-slate-600 font-bold">加载案例6分析中...</p>
      </div>
    </div>
  )
})

const Case7Viewer = dynamic(() => import('./mdm/case-studies/case7/Case7Viewer'), {
  ssr: false,
  loading: () => (
    <div className="bg-white rounded-2xl border border-slate-200 p-12">
      <div className="flex flex-col items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-teal-200 border-t-teal-600 mb-4"></div>
        <p className="text-slate-600 font-bold">加载案例7分析中...</p>
      </div>
    </div>
  )
})

const Case8Viewer = dynamic(() => import('./mdm/case-studies/case8/Case8Viewer'), {
  ssr: false,
  loading: () => (
    <div className="bg-white rounded-2xl border border-slate-200 p-12">
      <div className="flex flex-col items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-cyan-200 border-t-cyan-600 mb-4"></div>
        <p className="text-slate-600 font-bold">加载案例8分析中...</p>
      </div>
    </div>
  )
})

const Case9Viewer = dynamic(() => import('./mdm/case-studies/case9/Case9Viewer'), {
  ssr: false,
  loading: () => (
    <div className="bg-white rounded-2xl border border-slate-200 p-12">
      <div className="flex flex-col items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-rose-200 border-t-rose-600 mb-4"></div>
        <p className="text-slate-600 font-bold">加载案例9分析中...</p>
      </div>
    </div>
  )
})

const Case13Viewer = dynamic(() => import('./mdm/case-studies/case13/Case13Viewer'), {
  ssr: false,
  loading: () => (
    <div className="bg-white rounded-2xl border border-slate-200 p-12">
      <div className="flex flex-col items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-indigo-200 border-t-indigo-600 mb-4"></div>
        <p className="text-slate-600 font-bold">加载案例13分析中...</p>
      </div>
    </div>
  )
})

const Case14Viewer = dynamic(() => import('./mdm/case-studies/case14/Case14Viewer'), {
  ssr: false,
  loading: () => (
    <div className="bg-white rounded-2xl border border-slate-200 p-12">
      <div className="flex flex-col items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-teal-200 border-t-teal-600 mb-4"></div>
        <p className="text-slate-600 font-bold">加载案例14分析中...</p>
      </div>
    </div>
  )
})

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
  params?: ParamConfig[]  // 5个参数的配置（普通架构）
  processName?: string  // 过程参数的名称（如"偏移量"）
  processSymbol?: string // 过程参数符号（如"δ"）
  csvFile?: string
    architecture?: 'normal' | 'no_intersection' | 'case5' | 'case6' | 'case7' | 'case8' | 'case9' | 'case13' | 'case14' | 'markdown'  // 架构类型
  content?: string  // Markdown内容（仅用于markdown架构）
  defaults?: {  // 默认基准值
    beta?: number
    eta?: number
    gamma?: number
    sampleSize?: number
    process?: number
  }
  true_params?: {  // 真实参数（特殊架构用）
    beta?: number
    eta?: number
    gamma?: number
    sampleSize?: number
    process?: number
  }
  research_type?: string  // 研究类型（特殊架构用）
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
  count: number          // 总行数
  valid_count: number    // 有效行数（排除无解）
  // 维度值
  beta_true?: number
  sample_size?: number
  offset_value?: number
  // 统计量（可能为null，如果全部无解）
  bias_beta_mean: number | null
  bias_beta_std: number | null
  bias_eta_mean: number | null
  bias_eta_std: number | null
  bias_gamma_mean: number | null
  bias_gamma_std: number | null
  mse_beta: number | null
  mse_eta: number | null
  mse_gamma: number | null
  // 分布统计量
  est_beta_min: number | null
  est_beta_max: number | null
  est_beta_p01: number | null
  est_beta_p99: number | null
  est_beta_median: number | null
  est_beta_q1: number | null
  est_beta_q3: number | null
  est_eta_min: number | null
  est_eta_max: number | null
  est_eta_p01: number | null
  est_eta_p99: number | null
  est_eta_median: number | null
  est_eta_q1: number | null
  est_eta_q3: number | null
  est_gamma_min: number | null
  est_gamma_max: number | null
  est_gamma_p01: number | null
  est_gamma_p99: number | null
  est_gamma_median: number | null
  est_gamma_q1: number | null
  est_gamma_q3: number | null
  // 原始估计值数组（用于散点图），已过滤null值
  est_beta_values: number[]
  est_eta_values: number[]
  est_gamma_values: number[]
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
  const [showBandType, setShowBandType] = useState<'99percentile' | 'minmax'>('99percentile')

  const selectedCase = cases.find(c => c.id === selectedCaseId)

  // 加载案例配置 - 使用新的 API 路径
  useEffect(() => {
    const loadCases = async () => {
      try {
        const res = await fetch(`/api/case-studies/${methodId.toLowerCase()}`)
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
        const val = values[idx]?.trim()
        // 处理NaN字符串和无效数字
        if (val === 'NaN' || val === '' || val === undefined) {
          row[header] = null  // 用null标记NaN值
        } else {
          const num = Number(val)
          row[header] = isNaN(num) ? val : num
        }
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
      variableParams.forEach(p => {
        if (p.id === 'beta') {
          keyParts.push(`β=${row.beta_true}`)
        }
        if (p.id === 'sampleSize') {
          keyParts.push(`n=${row.sample_size}`)
        }
        if (p.id === 'process') {
          keyParts.push(`${selectedCase?.processSymbol || 'δ'}=${row.offset_value}`)
        }
      })

      const key = keyParts.join(', ')
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key)!.push(row)
    })

    return Array.from(groups.entries()).map(([key, rows]) => {
      // 过滤掉无解的行（est_beta为null表示MDM无解）
      const validRows = rows.filter(r => r.est_beta !== null && r.est_eta !== null && r.est_gamma !== null)

      // 如果全部无解，返回null标记的统计结果
      if (validRows.length === 0) {
        return {
          key,
          keyLabel: Array.from(groups.keys()).find(k => k.startsWith(key)) || key,
          count: rows.length,
          valid_count: 0,
          bias_beta_mean: null,
          bias_beta_std: null,
          bias_eta_mean: null,
          bias_eta_std: null,
          bias_gamma_mean: null,
          bias_gamma_std: null,
          mse_beta: null,
          mse_eta: null,
          mse_gamma: null,
          // 分布统计量
          est_beta_min: null,
          est_beta_max: null,
          est_beta_p01: null,
          est_beta_p99: null,
          est_beta_median: null,
          est_beta_q1: null,
          est_beta_q3: null,
          est_eta_min: null,
          est_eta_max: null,
          est_eta_p01: null,
          est_eta_p99: null,
          est_eta_median: null,
          est_eta_q1: null,
          est_eta_q3: null,
          est_gamma_min: null,
          est_gamma_max: null,
          est_gamma_p01: null,
          est_gamma_p99: null,
          est_gamma_median: null,
          est_gamma_q1: null,
          est_gamma_q3: null,
          // 原始估计值数组（空数组）
          est_beta_values: [],
          est_eta_values: [],
          est_gamma_values: [],
        }
      }

      const count = validRows.length
      const mean = (arr: (number | null)[]) => {
        const filtered = arr.filter((v): v is number => v !== null)
        if (filtered.length === 0) return 0
        return filtered.reduce((a, b) => a + b, 0) / filtered.length
      }
      const variance = (arr: (number | null)[]) => {
        const filtered = arr.filter((v): v is number => v !== null)
        if (filtered.length === 0) return 0
        const m = mean(arr)
        return filtered.reduce((sum, val) => sum + (val - m) ** 2, 0) / filtered.length
      }

      const biasBeta = validRows.map(r => r.bias_beta)
      const biasEta = validRows.map(r => r.bias_eta)
      const biasGamma = validRows.map(r => r.bias_gamma)

      // 估计值数组
      const estBeta = validRows.map(r => r.est_beta)
      const estEta = validRows.map(r => r.est_eta)
      const estGamma = validRows.map(r => r.est_gamma)

      // 计算分布统计量
      const quantile = (arr: number[], q: number) => {
        const sorted = [...arr].sort((a, b) => a - b)
        const pos = (sorted.length - 1) * q
        const base = Math.floor(pos)
        const rest = pos - base
        if (sorted[base + 1] !== undefined) {
          return sorted[base] + rest * (sorted[base + 1] - sorted[base])
        }
        return sorted[base]
      }

      const calcStats = (arr: number[]) => ({
        min: Math.min(...arr),
        max: Math.max(...arr),
        p01: quantile(arr, 0.01),
        p99: quantile(arr, 0.99),
        median: quantile(arr, 0.5),
        q1: quantile(arr, 0.25),
        q3: quantile(arr, 0.75)
      })

      const betaStats = calcStats(estBeta)
      const etaStats = calcStats(estEta)
      const gammaStats = calcStats(estGamma)

      // 生成标签（使用rows获取维度值，因为即使无解，维度值也是有效的）
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
        count: rows.length,        // 总行数（包括无解）
        valid_count: count,          // 有效行数（仅无解的）
        bias_beta_mean: mean(biasBeta),
        bias_beta_std: Math.sqrt(variance(biasBeta)),
        bias_eta_mean: mean(biasEta),
        bias_eta_std: Math.sqrt(variance(biasEta)),
        bias_gamma_mean: mean(biasGamma),
        bias_gamma_std: Math.sqrt(variance(biasGamma)),
        mse_beta: mean(biasBeta.map(v => v ** 2)),
        mse_eta: mean(biasEta.map(v => v ** 2)),
        mse_gamma: mean(biasGamma.map(v => v ** 2)),
        // 分布统计量
        est_beta_min: betaStats.min,
        est_beta_max: betaStats.max,
        est_beta_p01: betaStats.p01,
        est_beta_p99: betaStats.p99,
        est_beta_median: betaStats.median,
        est_beta_q1: betaStats.q1,
        est_beta_q3: betaStats.q3,
        est_eta_min: etaStats.min,
        est_eta_max: etaStats.max,
        est_eta_p01: etaStats.p01,
        est_eta_p99: etaStats.p99,
        est_eta_median: etaStats.median,
        est_eta_q1: etaStats.q1,
        est_eta_q3: etaStats.q3,
        est_gamma_min: gammaStats.min,
        est_gamma_max: gammaStats.max,
        est_gamma_p01: gammaStats.p01,
        est_gamma_p99: gammaStats.p99,
        est_gamma_median: gammaStats.median,
        est_gamma_q1: gammaStats.q1,
        est_gamma_q3: gammaStats.q3,
        // 原始估计值数组
        est_beta_values: estBeta,
        est_eta_values: estEta,
        est_gamma_values: estGamma
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

  // 案例切换处理函数
  const handleCaseChange = (newCaseId: string) => {
    setSelectedCaseId(newCaseId)
    setStats([])
  }

  // 检查是否为无交点架构
  if (selectedCase?.architecture === 'no_intersection') {
    return <Case3Viewer caseId={selectedCase.id} onCaseChange={handleCaseChange} />
  }

  // 检查是否为markdown架构（纯文档展示，如案例5）
  if (selectedCase?.architecture === 'markdown') {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8">
        <div className="prose prose-slate max-w-none prose-headings:font-bold prose-h2:text-xl prose-h2:mt-8 prose-h2:mb-4 prose-h3:text-lg prose-h3:mt-6 prose-h3:mb-3 prose-p:text-sm prose-p:leading-relaxed prose-table:text-sm prose-td:py-1 prose-td:px-2 prose-th:py-2 prose-th:px-2">
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeKatex, rehypeRaw]}
          >
            {selectedCase.content || ''}
          </ReactMarkdown>
        </div>
      </div>
    )
  }

  // 使用注册表检查特殊案例组件
  // 添加新案例时，只需在 caseRegistry.tsx 中添加即可
  const SpecialCaseComponent = selectedCase?.architecture
    ? (() => {
        // 动态获取组件
        const caseNum = selectedCase.architecture.replace('case', '')
        const componentMap: Record<string, React.ComponentType<{caseId: string, onCaseChange?: (caseId: string) => void}>> = {
          '5': Case5Viewer,
          '6': Case6Viewer,
          '7': Case7Viewer,
          '8': Case8Viewer,
          '9': Case9Viewer,
          '13': Case13Viewer,
          '14': Case14Viewer,
        }
        return componentMap[caseNum]
      })()
    : null

  if (SpecialCaseComponent && selectedCase) {
    return <SpecialCaseComponent caseId={selectedCase.id} onCaseChange={handleCaseChange} />
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
  // 辅助函数：格式化可能为null的数字
  const fmt = (val: number | null, decimals = 2) => {
    if (val === null || val === undefined) return '—'
    return val.toFixed(decimals)
  }

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

  // 箱型图组件 - 使用SVG直接绘制
  const BoxPlotChart = ({
    data,
    dataKeyMin,
    dataKeyMax,
    dataKeyP01,
    dataKeyP99,
    dataKeyMedian,
    color,
    yLabel,
    yTickFormatter
  }: {
    data: StatsResult[]
    dataKeyMin: keyof StatsResult
    dataKeyMax: keyof StatsResult
    dataKeyP01: keyof StatsResult
    dataKeyP99: keyof StatsResult
    dataKeyMedian: keyof StatsResult
    color: string
    yLabel: string
    yTickFormatter: (v: number) => string
  }) => {
    // 计算Y轴范围
    const allYValues = data.flatMap(d => [
      d[dataKeyMin] as number | null,
      d[dataKeyMax] as number | null,
      d[dataKeyP01] as number | null,
      d[dataKeyP99] as number | null
    ].filter((v): v is number => v !== null))

    const yMin = Math.min(...allYValues) * 0.98
    const yMax = Math.max(...allYValues) * 1.02
    const yRange = yMax - yMin

    // SVG尺寸配置
    const svgHeight = 220
    const svgWidth = 600
    const margin = { top: 10, right: 30, bottom: 40, left: 60 }
    const plotWidth = svgWidth - margin.left - margin.right
    const plotHeight = svgHeight - margin.top - margin.bottom

    // 将数据值转换为Y坐标
    const yToPixel = (y: number) => {
      return margin.top + plotHeight - ((y - yMin) / yRange) * plotHeight
    }

    // 将索引转换为X坐标
    const xToPixel = (index: number) => {
      return margin.left + (index + 0.5) * (plotWidth / data.length)
    }

    // 生成Y轴刻度
    const yTicks = []
    const tickCount = 5
    for (let i = 0; i <= tickCount; i++) {
      const value = yMin + (yRange * i) / tickCount
      yTicks.push(value)
    }

    return (
      <div className="w-full" style={{ height: `${svgHeight}px` }}>
        <svg width="100%" height="100%" viewBox={`0 0 ${svgWidth} ${svgHeight}`} style={{ overflow: 'visible' }}>
          {/* 网格线 */}
          {yTicks.map(tick => (
            <line
              key={`grid-${tick}`}
              x1={margin.left}
              y1={yToPixel(tick)}
              x2={svgWidth - margin.right}
              y2={yToPixel(tick)}
              stroke="#e5e7eb"
              strokeDasharray="3 3"
              strokeWidth={1}
            />
          ))}

          {/* Y轴 */}
          <line
            x1={margin.left}
            y1={margin.top}
            x2={margin.left}
            y2={svgHeight - margin.bottom}
            stroke={color}
            strokeWidth={1.5}
          />

          {/* X轴 */}
          <line
            x1={margin.left}
            y1={svgHeight - margin.bottom}
            x2={svgWidth - margin.right}
            y2={svgHeight - margin.bottom}
            stroke="#000"
            strokeWidth={1}
          />

          {/* Y轴刻度 */}
          {yTicks.map(tick => (
            <g key={`tick-${tick}`}>
              <line
                x1={margin.left - 5}
                y1={yToPixel(tick)}
                x2={margin.left}
                y2={yToPixel(tick)}
                stroke={color}
                strokeWidth={1}
              />
              <text
                x={margin.left - 8}
                y={yToPixel(tick)}
                textAnchor="end"
                dominantBaseline="middle"
                fontSize={12}
                fill={color}
              >
                {yTickFormatter(tick)}
              </text>
            </g>
          ))}

          {/* Y轴标签 */}
          <text
            x={margin.left - 45}
            y={(svgHeight / 2)}
            textAnchor="middle"
            transform={`rotate(-90, ${margin.left - 45}, ${svgHeight / 2})`}
            fontSize={14}
            fontWeight={600}
            fill={color}
          >
            {yLabel}
          </text>

          {/* X轴刻度和标签 */}
          {data.map((d, i) => {
            const x = xToPixel(i)
            return (
              <g key={`x-tick-${i}`}>
                <line
                  x1={x}
                  y1={svgHeight - margin.bottom}
                  x2={x}
                  y2={svgHeight - margin.bottom + 5}
                  stroke="#000"
                  strokeWidth={1}
                />
                <text
                  x={x}
                  y={svgHeight - margin.bottom + 18}
                  textAnchor="middle"
                  fontSize={12}
                  fill="#374151"
                >
                  {d.keyLabel}
                </text>
              </g>
            )
          })}

          {/* X轴标签 */}
          <text
            x={margin.left + plotWidth / 2}
            y={svgHeight - 5}
            textAnchor="middle"
            fontSize={14}
            fontWeight={600}
            fill="#1f2937"
          >
            {displayDimensions[0].id === 'sampleSize' ? `样本量${displayDimensions[0].symbol}` : displayDimensions[0].symbol}
          </text>

          {/* 箱型图 */}
          {data.map((d, i) => {
            const min = d[dataKeyMin] as number | null
            const max = d[dataKeyMax] as number | null
            const p01 = d[dataKeyP01] as number | null
            const p99 = d[dataKeyP99] as number | null
            const median = d[dataKeyMedian] as number | null

            if (min === null || max === null) return null

            const x = xToPixel(i)
            const boxWidth = Math.min(40, plotWidth / data.length * 0.7)
            const boxTop = p99 !== null ? p99 : max
            const boxBottom = p01 !== null ? p01 : min

            return (
              <g key={`boxplot-${i}`}>
                {/* 须线 - 下 */}
                <line
                  x1={x}
                  y1={yToPixel(min)}
                  x2={x}
                  y2={yToPixel(boxBottom)}
                  stroke={color}
                  strokeWidth={2}
                  strokeDasharray="4 2"
                />

                {/* 须线 - 上 */}
                <line
                  x1={x}
                  y1={yToPixel(boxTop)}
                  x2={x}
                  y2={yToPixel(max)}
                  stroke={color}
                  strokeWidth={2}
                  strokeDasharray="4 2"
                />

                {/* 须线端点 - 下 */}
                <line
                  x1={x - boxWidth / 3}
                  y1={yToPixel(min)}
                  x2={x + boxWidth / 3}
                  y2={yToPixel(min)}
                  stroke={color}
                  strokeWidth={2}
                />

                {/* 须线端点 - 上 */}
                <line
                  x1={x - boxWidth / 3}
                  y1={yToPixel(max)}
                  x2={x + boxWidth / 3}
                  y2={yToPixel(max)}
                  stroke={color}
                  strokeWidth={2}
                />

                {/* 箱体 */}
                {p01 !== null && p99 !== null && (
                  <rect
                    x={x - boxWidth / 2}
                    y={yToPixel(p99)}
                    width={boxWidth}
                    height={yToPixel(p01) - yToPixel(p99)}
                    fill={color}
                    fillOpacity={0.25}
                    stroke={color}
                    strokeWidth={2}
                  />
                )}

                {/* 中位数点 */}
                {median !== null && (
                  <circle
                    cx={x}
                    cy={yToPixel(median)}
                    r={4}
                    fill={color}
                  />
                )}
              </g>
            )
          })}
        </svg>
      </div>
    )
  }

  // 计算颜色范围（热力图用）
  const getColorForValue = (value: number, absMax: number): string => {
    const ratio = value / absMax
    if (ratio > 0) {
      const intensity = Math.min(Math.abs(ratio), 1)
      return `rgba(220, 38, 38, ${0.08 + intensity * 0.25})`  // 红色系，更浅的透明度
    } else {
      const intensity = Math.min(Math.abs(ratio), 1)
      return `rgba(30, 64, 175, ${0.08 + intensity * 0.25})`  // 蓝色系，更浅的透明度
    }
  }

  // 核密度估计 (KDE) - 计算平滑的概率密度曲线
  const computeKDE = (values: number[], bandwidth?: number) => {
    const n = values.length
    if (n === 0) return { points: [], bandwidth: 0 }

    // 使用 Silverman 规则自动选择带宽
    const std = Math.sqrt(values.reduce((sum, v) => sum + (v - values.reduce((a, b) => a + b, 0) / n) ** 2, 0) / n)
    const iqr = () => {
      const sorted = [...values].sort((a, b) => a - b)
      const q1 = sorted[Math.floor(n * 0.25)]
      const q3 = sorted[Math.floor(n * 0.75)]
      return q3 - q1
    }
    const defaultBandwidth = 0.9 * Math.min(std, iqr() / 1.34) / Math.pow(n, 0.2)
    const h = bandwidth ?? defaultBandwidth

    // 生成KDE曲线点
    const min = Math.min(...values)
    const max = Math.max(...values)
    const range = max - min
    const numPoints = 200

    const points = Array.from({ length: numPoints }, (_, i) => {
      const x = min - range * 0.1 + (i / (numPoints - 1)) * range * 1.2
      // 高斯核密度估计
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

  // 按变量分组计算分布曲线
  const computeDistributionCurves = (
    stats: StatsResult[],
    getValueFunc: (s: StatsResult) => number | undefined,
    labelFunc: (s: StatsResult) => string
  ) => {
    // 按变量值分组
    const groups = new Map<number, number[]>()
    stats.forEach(s => {
      const key = getValueFunc(s)
      if (key !== undefined) {
        if (!groups.has(key)) groups.set(key, [])
        groups.get(key)!.push(...s.est_beta_values)
      }
    })

    // 为每组计算KDE
    return Array.from(groups.entries()).map(([key, values]) => ({
      key,
      label: labelFunc(stats.find(s => getValueFunc(s) === key)!),
      kde: computeKDE(values)
    })).sort((a, b) => a.key - b.key)
  }

  // 计算β分组的分布曲线（当展示维度包含β时）
  const betaDistributionCurves = displayDimensions.some(d => d.id === 'beta')
    ? computeDistributionCurves(
        stats,
        s => s.beta_true,
        s => `β=${s.beta_true}`
      )
    : []

  // 计算n分组的分布曲线（当展示维度包含样本量时）
  const nDistributionCurves = displayDimensions.some(d => d.id === 'sampleSize')
    ? computeDistributionCurves(
        stats,
        s => s.sample_size,
        s => `n=${s.sample_size}`
      )
    : []

  // 计算δ分组的分布曲线（当展示维度包含偏移量时）
  const deltaDistributionCurves = displayDimensions.some(d => d.id === 'process')
    ? computeDistributionCurves(
        stats,
        s => s.offset_value,
        s => `δ=${s.offset_value}`
      )
    : []

  // 曲线颜色（按变量值数量分配）
  const getCurveColor = (index: number, total: number) => {
    const colors = [
      '#3b82f6', // blue-500
      '#ef4444', // red-500
      '#10b981', // emerald-500
      '#f59e0b', // amber-500
      '#8b5cf6', // violet-500
    ]
    return colors[index % colors.length]
  }

  // 确定当前的主要分组变量（用于分布曲线）
  const primaryGroupingVar = displayDimensions[0]?.id
  const getGroupingCurves = () => {
    if (primaryGroupingVar === 'beta') return betaDistributionCurves
    if (primaryGroupingVar === 'sampleSize') return nDistributionCurves
    if (primaryGroupingVar === 'process') return deltaDistributionCurves
    return []
  }
  const groupingCurves = getGroupingCurves()

  // 根据分组变量过滤数据
  const getFilteredValues = (valuesAccessor: (s: StatsResult) => number[], groupKey?: number) => {
    if (groupKey === undefined) {
      // 没有分组，返回所有值
      return stats.flatMap(valuesAccessor)
    }
    // 按分组键过滤
    return stats
      .filter(s => {
        if (primaryGroupingVar === 'beta') return s.beta_true === groupKey
        if (primaryGroupingVar === 'sampleSize') return s.sample_size === groupKey
        if (primaryGroupingVar === 'process') return s.offset_value === groupKey
        return true
      })
      .flatMap(valuesAccessor)
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
          <p className="text-center text-base font-semibold text-slate-700 mb-3">
            {getTableNumber(0)}: 参数估计汇总统计 (按{displayDimensions[0].name}分组)
          </p>
          <table className="w-full text-lg border-collapse">
            <thead>
              <tr className="border-b-2 border-slate-400">
                <th className="text-center py-2 px-3 font-bold text-slate-800 border-b-2 border-slate-400 w-24">{displayDimensions[0].symbol}</th>
                <th className="text-center py-2 px-3 font-bold text-slate-800 border-b-2 border-slate-400 w-20">参数</th>
                <th className="text-right py-2 px-3 font-bold text-slate-800 border-b-2 border-slate-400">真实值</th>
                <th className="text-right py-2 px-3 font-bold text-slate-800 border-b-2 border-slate-400">估计均值</th>
                <th className="text-right py-2 px-3 font-bold text-slate-800 border-b-2 border-slate-400">偏差</th>
                <th className="text-right py-2 px-3 font-bold text-slate-800 border-b-2 border-slate-400">SD</th>
                <th className="text-right py-2 px-3 font-bold text-slate-800 border-b-2 border-slate-400">MSE</th>
                <th className="text-right py-2 px-3 font-bold text-slate-800 border-b-2 border-slate-400">99%范围</th>
                <th className="text-right py-2 px-3 font-bold text-slate-800 border-b-2 border-slate-400">全范围</th>
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

                // β 的真实值：当β是变量时，使用当前行的beta_true；否则使用默认值
                const betaTrueValue = displayDimensions[0].id === 'beta' ? (s.beta_true ?? 2.0) : (selectedCase?.defaults?.beta ?? 2.0)
                // η 和 γ 是固定的
                const etaTrueValue = getFixedTrueValue('eta')
                const gammaTrueValue = getFixedTrueValue('gamma')

                return (
                  <React.Fragment key={idx}>
                    {/* β 行 */}
                    <tr className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                      <td rowSpan={3} className="py-1.5 px-3 font-mono text-lg text-slate-700 border-b border-slate-200 text-center vertical-align-middle">
                        {varValue}
                      </td>
                      <td className="py-1.5 px-3 font-bold text-slate-800 border-b border-slate-200 text-center">β</td>
                      <td className="text-right py-1.5 px-3 font-mono text-lg text-slate-700 border-b border-slate-200">
                        {betaTrueValue}
                      </td>
                      <td className="text-right py-1.5 px-3 font-mono text-lg text-slate-700 border-b border-slate-200">
                        {s.bias_beta_mean === null ? '—' : (betaTrueValue + s.bias_beta_mean).toFixed(4)}
                      </td>
                      <td className="text-right py-1.5 px-3 font-mono text-lg text-slate-700 border-b border-slate-200">{fmt(s.bias_beta_mean, 4)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-lg text-slate-700 border-b border-slate-200">{fmt(s.bias_beta_std, 4)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-lg text-slate-700 border-b border-slate-200">{fmt(s.mse_beta, 4)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-base text-slate-700 border-b border-slate-200">[{fmt(s.est_beta_p01, 4)}, {fmt(s.est_beta_p99, 4)}]</td>
                      <td className="text-right py-1.5 px-3 font-mono text-base text-slate-700 border-b border-slate-200">[{fmt(s.est_beta_min, 4)}, {fmt(s.est_beta_max, 4)}]</td>
                    </tr>
                    {/* η 行 */}
                    <tr className={idx % 2 === 0 ? 'bg-slate-50' : 'bg-white'}>
                      <td className="py-1.5 px-3 font-bold text-slate-800 border-b border-slate-200 text-center">η</td>
                      <td className="text-right py-1.5 px-3 font-mono text-lg text-slate-700 border-b border-slate-200">{etaTrueValue}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-lg text-slate-700 border-b border-slate-200">{s.bias_eta_mean === null ? '—' : (etaTrueValue + s.bias_eta_mean).toFixed(2)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-lg text-slate-700 border-b border-slate-200">{fmt(s.bias_eta_mean, 2)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-lg text-slate-700 border-b border-slate-200">{fmt(s.bias_eta_std, 2)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-lg text-slate-700 border-b border-slate-200">{fmt(s.mse_eta, 2)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-base text-slate-700 border-b border-slate-200">[{fmt(s.est_eta_p01, 2)}, {fmt(s.est_eta_p99, 2)}]</td>
                      <td className="text-right py-1.5 px-3 font-mono text-base text-slate-700 border-b border-slate-200">[{fmt(s.est_eta_min, 2)}, {fmt(s.est_eta_max, 2)}]</td>
                    </tr>
                    {/* γ 行 */}
                    <tr className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                      <td className="py-1.5 px-3 font-bold text-slate-800 border-b border-slate-200 text-center">γ</td>
                      <td className="text-right py-1.5 px-3 font-mono text-lg text-slate-700 border-b border-slate-200">{gammaTrueValue}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-lg text-slate-700 border-b border-slate-200">{s.bias_gamma_mean === null ? '—' : (gammaTrueValue + s.bias_gamma_mean).toFixed(2)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-lg text-slate-700 border-b border-slate-200">{fmt(s.bias_gamma_mean, 2)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-lg text-slate-700 border-b border-slate-200">{fmt(s.bias_gamma_std, 2)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-lg text-slate-700 border-b border-slate-200">{fmt(s.mse_gamma, 2)}</td>
                      <td className="text-right py-1.5 px-3 font-mono text-base text-slate-700 border-b border-slate-200">[{fmt(s.est_gamma_p01, 2)}, {fmt(s.est_gamma_p99, 2)}]</td>
                      <td className="text-right py-1.5 px-3 font-mono text-base text-slate-700 border-b border-slate-200">[{fmt(s.est_gamma_min, 2)}, {fmt(s.est_gamma_max, 2)}]</td>
                    </tr>
                  </React.Fragment>
                )
              })}
            </tbody>
          </table>
          <p className="text-center text-sm text-slate-500 mt-3">
            注: 估计均值 = 真实值 + 偏差. 99%范围 = [1%分位数, 99%分位数]. 全范围 = [最小值, 最大值]. 其他参数固定在默认值.
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
                    wrapperStyle={{ fontSize: '15px', fontWeight: 500, right: 150, marginTop: 0 }}
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
                    wrapperStyle={{ fontSize: '15px', fontWeight: 500, right: 150, marginTop: 0 }}
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
                    wrapperStyle={{ fontSize: '15px', fontWeight: 500, right: 150, marginTop: 0 }}
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

          {/* 图4: 箱型图 - 箱体=99%分位数, 须线=最大最小值 */}
          <div className="bg-white border border-slate-300 p-3">
            <p className="text-center text-sm font-bold text-slate-700 mb-3">
              箱体 = 99%分位数区间 | 须线 = 最大最小值范围 | 圆点 = 中位数
            </p>

            {/* 三个子图垂直排列 */}
            <div className="space-y-5">
              {/* β 子图 */}
              <div>
                <BoxPlotChart
                  data={stats}
                  dataKeyMin="est_beta_min"
                  dataKeyMax="est_beta_max"
                  dataKeyP01="est_beta_p01"
                  dataKeyP99="est_beta_p99"
                  dataKeyMedian="est_beta_median"
                  color={colors.beta}
                  yLabel="β 估计值"
                  yTickFormatter={(v) => v.toFixed(3)}
                />
              </div>

              {/* η 子图 */}
              <div>
                <BoxPlotChart
                  data={stats}
                  dataKeyMin="est_eta_min"
                  dataKeyMax="est_eta_max"
                  dataKeyP01="est_eta_p01"
                  dataKeyP99="est_eta_p99"
                  dataKeyMedian="est_eta_median"
                  color={colors.eta}
                  yLabel="η 估计值"
                  yTickFormatter={(v) => v.toFixed(0)}
                />
              </div>

              {/* γ 子图 */}
              <div>
                <BoxPlotChart
                  data={stats}
                  dataKeyMin="est_gamma_min"
                  dataKeyMax="est_gamma_max"
                  dataKeyP01="est_gamma_p01"
                  dataKeyP99="est_gamma_p99"
                  dataKeyMedian="est_gamma_median"
                  color={colors.gamma}
                  yLabel="γ 估计值"
                  yTickFormatter={(v) => v.toFixed(0)}
                />
              </div>
            </div>

            <p className="text-center text-base font-semibold text-slate-700 mt-4">
              {getFigureNumber(4)}: 参数估计箱型图
            </p>
          </div>

          {/* 图5: 三参数估计值分布曲线 (按变量分组) */}
          <div className="bg-white border border-slate-300 p-3">
            {/* 选择要查看的变量分组 */}
            {groupingCurves.length > 0 && (
              <div className="mb-4 flex items-center justify-center gap-4">
                <span className="text-sm font-bold text-slate-600">按变量分组显示：</span>
                {primaryGroupingVar === 'beta' && (
                  <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-bold">β (形状参数)</span>
                )}
                {primaryGroupingVar === 'sampleSize' && (
                  <span className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm font-bold">n (样本量)</span>
                )}
                {primaryGroupingVar === 'process' && (
                  <span className="px-3 py-1 bg-rose-100 text-rose-700 rounded-full text-sm font-bold">δ (偏移量)</span>
                )}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* β 分布曲线 */}
              <div>
                <p className="text-center text-sm font-semibold mb-2" style={{ color: colors.beta }}>β 参数估计分布</p>
                <div className="h-[280px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart margin={{ top: 10, right: 15, bottom: 30, left: 45 }}>
                      <XAxis
                        dataKey="x"
                        tick={{ fontSize: 10 }}
                        tickLine={true}
                        stroke="#000"
                        strokeWidth={1}
                        type="number"
                        domain={['auto', 'auto']}
                        axisLine={{ stroke: '#000', strokeWidth: 1 }}
                      />
                      <YAxis
                        tick={{ fontSize: 10 }}
                        tickLine={true}
                        stroke="#000"
                        strokeWidth={1}
                        axisLine={{ stroke: '#000', strokeWidth: 1 }}
                      />
                      <Tooltip
                        contentStyle={{
                          borderRadius: '4px',
                          border: '1px solid #e5e7eb',
                          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                          fontSize: '12px'
                        }}
                        formatter={(value: number) => value.toFixed(4)}
                        labelFormatter={(label) => `β估计值: ${label.toFixed(3)}`}
                      />
                      <Legend
                        verticalAlign="top"
                        align="center"
                        wrapperStyle={{ fontSize: '11px', fontWeight: 500 }}
                      />
                      {groupingCurves.map((curve, idx) => (
                        <Line
                          key={curve.key}
                          type="monotone"
                          dataKey="y"
                          data={computeKDE(getFilteredValues(s => s.est_beta_values, curve.key)).points}
                          name={curve.label}
                          stroke={getCurveColor(idx, groupingCurves.length)}
                          strokeWidth={2}
                          dot={false}
                          connectNulls={false}
                        />
                      ))}
                      {groupingCurves.length === 0 && (
                        <Line
                          type="monotone"
                          dataKey="y"
                          data={computeKDE(getFilteredValues(s => s.est_beta_values)).points}
                          name="整体分布"
                          stroke={colors.beta}
                          strokeWidth={2}
                          dot={false}
                        />
                      )}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
              {/* η 分布曲线 */}
              <div>
                <p className="text-center text-sm font-semibold mb-2" style={{ color: colors.eta }}>η 参数估计分布</p>
                <div className="h-[280px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart margin={{ top: 10, right: 15, bottom: 30, left: 45 }}>
                      <XAxis
                        dataKey="x"
                        tick={{ fontSize: 10 }}
                        tickLine={true}
                        stroke="#000"
                        strokeWidth={1}
                        type="number"
                        domain={['auto', 'auto']}
                        axisLine={{ stroke: '#000', strokeWidth: 1 }}
                      />
                      <YAxis
                        tick={{ fontSize: 10 }}
                        tickLine={true}
                        stroke="#000"
                        strokeWidth={1}
                        axisLine={{ stroke: '#000', strokeWidth: 1 }}
                      />
                      <Tooltip
                        contentStyle={{
                          borderRadius: '4px',
                          border: '1px solid #e5e7eb',
                          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                          fontSize: '12px'
                        }}
                        formatter={(value: number) => value.toFixed(5)}
                        labelFormatter={(label) => `η估计值: ${label.toFixed(1)}`}
                      />
                      <Legend
                        verticalAlign="top"
                        align="center"
                        wrapperStyle={{ fontSize: '11px', fontWeight: 500 }}
                      />
                      {groupingCurves.map((curve, idx) => (
                        <Line
                          key={curve.key}
                          type="monotone"
                          dataKey="y"
                          data={computeKDE(getFilteredValues(s => s.est_eta_values, curve.key)).points}
                          name={curve.label}
                          stroke={getCurveColor(idx, groupingCurves.length)}
                          strokeWidth={2}
                          dot={false}
                          connectNulls={false}
                        />
                      ))}
                      {groupingCurves.length === 0 && (
                        <Line
                          type="monotone"
                          dataKey="y"
                          data={computeKDE(getFilteredValues(s => s.est_eta_values)).points}
                          name="整体分布"
                          stroke={colors.eta}
                          strokeWidth={2}
                          dot={false}
                        />
                      )}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
              {/* γ 分布曲线 */}
              <div>
                <p className="text-center text-sm font-semibold mb-2" style={{ color: colors.gamma }}>γ 参数估计分布</p>
                <div className="h-[280px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart margin={{ top: 10, right: 15, bottom: 30, left: 45 }}>
                      <XAxis
                        dataKey="x"
                        tick={{ fontSize: 10 }}
                        tickLine={true}
                        stroke="#000"
                        strokeWidth={1}
                        type="number"
                        domain={['auto', 'auto']}
                        axisLine={{ stroke: '#000', strokeWidth: 1 }}
                      />
                      <YAxis
                        tick={{ fontSize: 10 }}
                        tickLine={true}
                        stroke="#000"
                        strokeWidth={1}
                        axisLine={{ stroke: '#000', strokeWidth: 1 }}
                      />
                      <Tooltip
                        contentStyle={{
                          borderRadius: '4px',
                          border: '1px solid #e5e7eb',
                          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                          fontSize: '12px'
                        }}
                        formatter={(value: number) => value.toFixed(5)}
                        labelFormatter={(label) => `γ估计值: ${label.toFixed(1)}`}
                      />
                      <Legend
                        verticalAlign="top"
                        align="center"
                        wrapperStyle={{ fontSize: '11px', fontWeight: 500 }}
                      />
                      {groupingCurves.map((curve, idx) => (
                        <Line
                          key={curve.key}
                          type="monotone"
                          dataKey="y"
                          data={computeKDE(getFilteredValues(s => s.est_gamma_values, curve.key)).points}
                          name={curve.label}
                          stroke={getCurveColor(idx, groupingCurves.length)}
                          strokeWidth={2}
                          dot={false}
                          connectNulls={false}
                        />
                      ))}
                      {groupingCurves.length === 0 && (
                        <Line
                          type="monotone"
                          dataKey="y"
                          data={computeKDE(getFilteredValues(s => s.est_gamma_values)).points}
                          name="整体分布"
                          stroke={colors.gamma}
                          strokeWidth={2}
                          dot={false}
                        />
                      )}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
            <p className="text-center text-base font-semibold text-slate-700 mt-3">
              {getFigureNumber(4)}: 参数估计值概率密度分布 (核密度估计)
            </p>
            <p className="text-center text-xs text-slate-500 mt-1">
              使用高斯核密度估计 (KDE) 平滑曲线，带宽采用 Silverman 规则自动选择。按 <span className="font-bold">{displayDimensions[0]?.name || '-'}</span> 分组显示
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
            figureNumber={getFigureNumber(5)}
            getColorForValue={getColorForValue}
          />
          <HeatmapCard
            title={`η 参数偏差热力图`}
            stats={stats}
            displayDimensions={displayDimensions}
            dataKey="bias_eta_mean"
            color={colors.eta}
            figureNumber={getFigureNumber(6)}
            getColorForValue={getColorForValue}
          />
          <HeatmapCard
            title={`γ 参数偏差热力图`}
            stats={stats}
            displayDimensions={displayDimensions}
            dataKey="bias_gamma_mean"
            color={colors.gamma}
            figureNumber={getFigureNumber(7)}
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
  // 计算颜色范围（过滤null值）
  const allValues = stats.map(s => s[dataKey]).filter((v): v is number => v !== null)
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
    <div className="bg-white border border-slate-300 p-4" style={{ maxWidth: '50%', margin: '0 auto' }}>
      {/* 图例 */}
      <div className="flex items-center justify-center gap-3 mb-3">
        <span className="text-sm font-semibold text-slate-700">低估</span>
        <div className="flex items-center">
          <div className="w-10 h-3 rounded-l" style={{ backgroundColor: getColorForValue(-absMax, absMax) }}></div>
          <div className="w-10 h-3 bg-slate-100"></div>
          <div className="w-10 h-3 rounded-r" style={{ backgroundColor: getColorForValue(absMax, absMax) }}></div>
        </div>
        <span className="text-sm font-semibold text-slate-700">高估</span>
        <span className="text-sm text-slate-500 ml-3">
          <span className="font-mono">[{(-absMax).toFixed(3)}, {absMax.toFixed(3)}]</span>
        </span>
      </div>

      {/* 热力图 */}
      <div className="overflow-x-auto">
        <table className="w-full text-base border-collapse" style={{ tableLayout: 'auto' }}>
          <thead>
            <tr>
              <th className="bg-slate-50 border border-slate-300" style={{ width: '80px', padding: '0' }}>
                <div style={{
                  position: 'relative',
                  width: '80px',
                  height: '60px',
                  background: 'linear-gradient(to top right, transparent calc(50% - 0.5px), #64748b calc(50% - 0.5px), #64748b calc(50% + 0.5px), transparent calc(50% + 0.5px))'
                }}>
                  <span style={{
                    position: 'absolute',
                    top: '4px',
                    right: displayDimensions[0].id === 'sampleSize' ? '1px' : displayDimensions[0].id === 'beta' ? '11px' : '6px',
                    fontSize: '19px',
                    fontWeight: 600,
                    color: '#374151'
                  }}>{displayDimensions[0].symbol}</span>
                  <span style={{
                    position: 'absolute',
                    bottom: '4px',
                    left: displayDimensions[1].id === 'sampleSize' ? '1px' : displayDimensions[1].id === 'beta' ? '11px' : '6px',
                    fontSize: '19px',
                    fontWeight: 600,
                    color: '#374151'
                  }}>{displayDimensions[1].symbol}</span>
                </div>
              </th>
              {firstDimValues.map(val => (
                <th key={val} className="p-2.5 bg-slate-50 border border-slate-300 text-xl font-bold text-slate-800">
                  {formatValue(val, displayDimensions[0].id)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {secondDimValues.map((yVal, yIdx) => (
              <tr key={yVal}>
                <td className="p-2.5 bg-slate-50 border border-slate-300 text-xl font-bold text-slate-800 text-center" style={{ width: '80px' }}>
                  {formatValue(yVal, displayDimensions[1].id)}
                </td>
                {heatmapData[yIdx].map((cell, xIdx) => (
                  <td
                    key={xIdx}
                    className="p-2.5 text-center border border-slate-200"
                    style={{
                      backgroundColor: cell.hasData ? getColorForValue(cell.value, absMax) : '#f3f4f6'
                    }}
                  >
                    <span
                      className="font-mono text-xl font-semibold"
                      style={{
                        color: cell.hasData ? '#000000' : '#9ca3af'
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
      <p className="text-center text-base font-semibold text-slate-700 mt-3">
        {figureNumber}: {title} ({displayDimensions.map(p => p.symbol).join(' × ')})
      </p>
    </div>
  )
}
