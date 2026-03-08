"use client"

import React, { useState, useEffect, useMemo, useRef } from 'react'
import { Settings, FlaskConical, Filter, Info } from 'lucide-react'
import { cn } from '@/lib/utils'
import matter from 'gray-matter'
import {
  ChartCard, BoxPlotChart, DensityChart, ConvergenceChart
} from '@/components/shared/charts'
import type { CurveData } from '@/components/shared/charts/ConvergenceChart'

// ============ Types ============

interface ParamConfig {
  id: string
  name: string
  symbol: string
  state: 'fixed' | 'range' | 'discrete'
  fixedValue?: number
  discreteValues?: (number | string)[]
  isVariable: boolean
  isDisplayDimension: boolean
}

interface SimulationConfig {
  mcRunsList?: number[]
  maxMcRuns?: number
  seedFormula?: string
  totalCombinations?: number
}

interface CalculationConfig {
  gammaSteps?: number
  betaBounds?: [number, number]
  rankMethod?: string
  gammaRangeRound1?: [number, number]
  gammaRangeRound2?: [number, number]
}

interface StudyConfig {
  id: string
  name: string
  description: string
  method: string
  params?: ParamConfig[]
  defaults?: Record<string, number>
  simulation?: SimulationConfig
  calculation?: CalculationConfig
}

interface SimulationRow {
  [key: string]: number | string | null
  beta_true: number
  eta_true: number
  sample_size: number
  offset_value: number
  sim_id: number
  est_beta: number | null
  est_eta: number | null
  est_gamma: number | null
  bias_beta: number | null
  bias_eta: number | null
  bias_gamma: number | null
  r_squared: number | null
}

interface StatsResult {
  key: string
  keyLabel: string
  sample_size: number
  count: number
  valid_count: number
  // β
  est_beta_mean: number | null
  bias_beta_mean: number | null
  est_beta_median: number | null
  bias_beta_median: number | null
  est_beta_std: number | null
  est_beta_min: number | null
  est_beta_max: number | null
  est_beta_p025: number | null
  est_beta_p975: number | null
  est_beta_p005: number | null
  est_beta_p995: number | null
  est_beta_p0001: number | null
  est_beta_p001: number | null
  est_beta_p01: number | null
  est_beta_p10: number | null
  // η
  est_eta_mean: number | null
  bias_eta_mean: number | null
  est_eta_median: number | null
  bias_eta_median: number | null
  est_eta_std: number | null
  est_eta_min: number | null
  est_eta_max: number | null
  est_eta_p025: number | null
  est_eta_p975: number | null
  est_eta_p005: number | null
  est_eta_p995: number | null
  est_eta_p0001: number | null
  est_eta_p001: number | null
  est_eta_p01: number | null
  est_eta_p10: number | null
  // γ
  est_gamma_mean: number | null
  bias_gamma_mean: number | null
  est_gamma_median: number | null
  bias_gamma_median: number | null
  est_gamma_std: number | null
  est_gamma_min: number | null
  est_gamma_max: number | null
  est_gamma_p025: number | null
  est_gamma_p975: number | null
  est_gamma_p005: number | null
  est_gamma_p995: number | null
  est_gamma_p0001: number | null
  est_gamma_p001: number | null
  est_gamma_p01: number | null
  est_gamma_p10: number | null
  [key: string]: number | string | null | undefined
}

interface TableDisplayOptions {
  mean: boolean
  biasMean: boolean
  median: boolean
  biasMedian: boolean
  std: boolean
  ci95: boolean
  ci99: boolean
  fullRange: boolean
  quantileBias: boolean
}

const DEFAULT_DISPLAY_OPTIONS: TableDisplayOptions = {
  mean: true,
  biasMean: true,
  median: false,
  biasMedian: false,
  std: true,
  ci95: false,
  ci99: true,
  fullRange: false,
  quantileBias: false
}

// ============ Constants ============

const PARAM_COLORS: Record<string, string> = {
  beta: 'border-blue-200 bg-blue-50',
  eta: 'border-emerald-200 bg-emerald-50',
  gamma: 'border-amber-200 bg-amber-50',
  sampleSize: 'border-purple-200 bg-purple-50',
  process: 'border-rose-200 bg-rose-50'
}

const EST_PARAM_COLORS = {
  beta: { bg: 'bg-blue-100', text: 'text-blue-700', border: 'border-blue-300', color: '#1e40af' },
  eta: { bg: 'bg-emerald-100', text: 'text-emerald-700', border: 'border-emerald-300', color: '#047857' },
  gamma: { bg: 'bg-amber-100', text: 'text-amber-700', border: 'border-amber-300', color: '#b45309' }
}

// ============ Utility Functions ============

function parseCsv(text: string): SimulationRow[] {
  const lines = text.trim().split('\n')
  if (lines.length < 2) return []

  const headers = lines[0].split(',')
  const rows: SimulationRow[] = []

  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',')
    const parseVal = (key: string) => {
      const v = values[headers.indexOf(key)]
      if (!v || v === 'NaN' || v === 'nan') return null
      const n = parseFloat(v)
      return isNaN(n) ? null : n
    }

    rows.push({
      beta_true: parseFloat(values[headers.indexOf('beta_true')] || '0'),
      eta_true: parseFloat(values[headers.indexOf('eta_true')] || '0'),
      sample_size: parseInt(values[headers.indexOf('sample_size')] || '0'),
      offset_value: parseFloat(values[headers.indexOf('offset_value')] || '0'),
      sim_id: parseInt(values[headers.indexOf('sim_id')] || '0'),
      est_beta: parseVal('est_beta'),
      est_eta: parseVal('est_eta'),
      est_gamma: parseVal('est_gamma'),
      bias_beta: parseVal('bias_beta'),
      bias_eta: parseVal('bias_eta'),
      bias_gamma: parseVal('bias_gamma'),
      r_squared: parseVal('r_squared')
    })
  }
  return rows
}

function parseConfigMd(text: string): StudyConfig {
  try {
    const { data } = matter(text)
    return {
      id: data.id || 'unknown',
      name: data.name || '未命名示例',
      description: data.description || '',
      method: data.method || 'mdm',
      params: data.params || [],
      defaults: data.defaults || {},
      simulation: data.simulation || {},
      calculation: data.calculation || {}
    }
  } catch (e) {
    throw new Error('配置文件格式错误')
  }
}

// ============ Main Component ============

export default function Demo2Viewer() {
  const [config, setConfig] = useState<StudyConfig | null>(null)
  const [csvData, setCsvData] = useState<SimulationRow[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // UI State
  const [selectedSampleSizes, setSelectedSampleSizes] = useState<number[]>([])
  const [selectedMcRuns, setSelectedMcRuns] = useState<number>(5000)
  const [displayOptions, setDisplayOptions] = useState<TableDisplayOptions>(DEFAULT_DISPLAY_OPTIONS)
  const [paramSelection, setParamSelection] = useState({ beta: true, eta: true, gamma: true })
  const [densityTab, setDensityTab] = useState<'beta' | 'eta' | 'gamma'>('beta')
  const [convergenceStatTab, setConvergenceStatTab] = useState<'mean' | 'median' | 'std'>('median')
  const [convergenceParamTab, setConvergenceParamTab] = useState<'beta' | 'eta' | 'gamma'>('beta')

  // 收敛曲线样本量选择（独立于参数设置面板）
  const [convergenceSampleSizes, setConvergenceSampleSizes] = useState<number[]>([3, 5, 7, 10, 20, 30])

  // 收敛曲线预计算数据
  const [convergenceData, setConvergenceData] = useState<{sample_size: number, mc_runs: number, beta_mean: number, beta_median: number, beta_std: number, eta_mean: number, eta_median: number, eta_std: number, gamma_mean: number, gamma_median: number, gamma_std: number}[]>([])

  // Load config
  useEffect(() => {
    const loadConfig = async () => {
      try {
        setIsLoading(true)
        const res = await fetch('/studies/mdm/demo2/config.md')
        if (!res.ok) throw new Error('配置文件加载失败')
        const text = await res.text()
        const cfg = parseConfigMd(text)
        setConfig(cfg)

        // Initialize selected sample sizes from config
        const sampleSizeParam = cfg.params?.find(p => p.id === 'sampleSize')
        if (sampleSizeParam?.discreteValues) {
          // Default select all
          setSelectedSampleSizes(sampleSizeParam.discreteValues.map(v => Number(v)))
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : '加载失败')
      }
    }
    loadConfig()
  }, [])

  // Load convergence data
  useEffect(() => {
    const loadConvergenceData = async () => {
      try {
        const res = await fetch('/studies/mdm/demo2/convergence.csv')
        if (!res.ok) return
        const text = await res.text()
        const lines = text.trim().split('\n')
        if (lines.length < 2) return

        const headers = lines[0].split(',')
        const data = lines.slice(1).map(line => {
          const values = line.split(',')
          const row: Record<string, number> = {}
          headers.forEach((h, i) => {
            const v = values[i]
            row[h] = v && v !== 'nan' && v !== 'NaN' ? parseFloat(v) : NaN
          })
          return row as any
        })
        setConvergenceData(data)
      } catch (err) {
        console.error('Failed to load convergence data:', err)
      }
    }
    loadConvergenceData()
  }, [])

  // Load CSV data
  useEffect(() => {
    if (!config) return

    const loadData = async () => {
      try {
        // Load chunk files for each selected sample size
        const dataPromises = selectedSampleSizes.map(async (n) => {
          const res = await fetch(`/studies/mdm/demo2/chunks/n${n}.csv`)
          if (!res.ok) return []
          const text = await res.text()
          return parseCsv(text)
        })

        const results = await Promise.all(dataPromises)
        setCsvData(results.flat())
        setIsLoading(false)
      } catch (err) {
        setError('数据加载失败')
        setIsLoading(false)
      }
    }

    if (selectedSampleSizes.length > 0) {
      loadData()
    } else {
      setCsvData([])
      setIsLoading(false)
    }
  }, [config, selectedSampleSizes])

  // Toggle sample size selection
  const toggleSampleSize = (n: number) => {
    setSelectedSampleSizes(prev =>
      prev.includes(n)
        ? prev.filter(x => x !== n)
        : [...prev, n].sort((a, b) => a - b)
    )
  }

  // Select all sample sizes
  const selectAllSampleSizes = () => {
    const sampleSizeParam = config?.params?.find(p => p.id === 'sampleSize')
    if (sampleSizeParam?.discreteValues) {
      setSelectedSampleSizes(sampleSizeParam.discreteValues.map(v => Number(v)))
    }
  }

  // Toggle convergence sample size selection
  const toggleConvergenceSampleSize = (n: number) => {
    setConvergenceSampleSizes(prev =>
      prev.includes(n)
        ? prev.filter(x => x !== n)
        : [...prev, n].sort((a, b) => a - b)
    )
  }

  // Select all convergence sample sizes
  const selectAllConvergenceSampleSizes = () => {
    const sampleSizeParam = config?.params?.find(p => p.id === 'sampleSize')
    if (sampleSizeParam?.discreteValues) {
      setConvergenceSampleSizes(sampleSizeParam.discreteValues.map(v => Number(v)))
    }
  }

  // Calculate stats filtered by MC runs
  const filteredData = useMemo(() => {
    return csvData.filter(row => row.sim_id <= selectedMcRuns)
  }, [csvData, selectedMcRuns])

  // Calculate statistics grouped by sample size
  const stats = useMemo(() => {
    if (filteredData.length === 0) return []

    const groups = new Map<number, SimulationRow[]>()
    filteredData.forEach(row => {
      if (!groups.has(row.sample_size)) {
        groups.set(row.sample_size, [])
      }
      groups.get(row.sample_size)!.push(row)
    })

    const calcStats = (values: number[], trueValue: number) => {
      if (values.length === 0) return {
        mean: null, biasMean: null, median: null, biasMedian: null,
        std: null, min: null, max: null,
        p025: null, p975: null, p005: null, p995: null,
        p0001: null, p001: null, p01: null, p10: null
      }
      const sorted = [...values].sort((a, b) => a - b)
      const n = sorted.length
      const mean = values.reduce((a, b) => a + b, 0) / n
      const biasMean = mean - trueValue
      const std = Math.sqrt(values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / n)
      const quantile = (q: number) => {
        const pos = (n - 1) * q
        const base = Math.floor(pos)
        const rest = pos - base
        return sorted[base + 1] !== undefined ? sorted[base] + rest * (sorted[base + 1] - sorted[base]) : sorted[base]
      }
      const median = quantile(0.5)
      const biasMedian = median - trueValue
      return {
        mean, biasMean, median, biasMedian, std,
        min: sorted[0], max: sorted[n - 1],
        p025: quantile(0.025), p975: quantile(0.975),
        p005: quantile(0.005), p995: quantile(0.995),
        p0001: quantile(0.001), p001: quantile(0.01),
        p01: quantile(0.1), p10: quantile(0.9)
      }
    }

    const trueBeta = config?.defaults?.beta ?? 2.0
    const trueEta = config?.defaults?.eta ?? 1000
    const trueGamma = config?.defaults?.gamma ?? 1000

    return Array.from(groups.entries())
      .filter(([n]) => selectedSampleSizes.includes(n))
      .map(([n, rows]): StatsResult => {
        const validRows = rows.filter(r => r.est_beta !== null && r.est_eta !== null && r.est_gamma !== null)
        const betaStats = calcStats(validRows.map(r => r.est_beta!), trueBeta)
        const etaStats = calcStats(validRows.map(r => r.est_eta!), trueEta)
        const gammaStats = calcStats(validRows.map(r => r.est_gamma!), trueGamma)

        return {
          key: String(n),
          keyLabel: String(n),
          sample_size: n,
          count: rows.length,
          valid_count: validRows.length,
          // β
          est_beta_mean: betaStats.mean,
          bias_beta_mean: betaStats.biasMean,
          est_beta_median: betaStats.median,
          bias_beta_median: betaStats.biasMedian,
          est_beta_std: betaStats.std,
          est_beta_min: betaStats.min,
          est_beta_max: betaStats.max,
          est_beta_p025: betaStats.p025,
          est_beta_p975: betaStats.p975,
          est_beta_p005: betaStats.p005,
          est_beta_p995: betaStats.p995,
          est_beta_p0001: betaStats.p0001,
          est_beta_p001: betaStats.p001,
          est_beta_p01: betaStats.p01,
          est_beta_p10: betaStats.p10,
          // η
          est_eta_mean: etaStats.mean,
          bias_eta_mean: etaStats.biasMean,
          est_eta_median: etaStats.median,
          bias_eta_median: etaStats.biasMedian,
          est_eta_std: etaStats.std,
          est_eta_min: etaStats.min,
          est_eta_max: etaStats.max,
          est_eta_p025: etaStats.p025,
          est_eta_p975: etaStats.p975,
          est_eta_p005: etaStats.p005,
          est_eta_p995: etaStats.p995,
          est_eta_p0001: etaStats.p0001,
          est_eta_p001: etaStats.p001,
          est_eta_p01: etaStats.p01,
          est_eta_p10: etaStats.p10,
          // γ
          est_gamma_mean: gammaStats.mean,
          bias_gamma_mean: gammaStats.biasMean,
          est_gamma_median: gammaStats.median,
          bias_gamma_median: gammaStats.biasMedian,
          est_gamma_std: gammaStats.std,
          est_gamma_min: gammaStats.min,
          est_gamma_max: gammaStats.max,
          est_gamma_p025: gammaStats.p025,
          est_gamma_p975: gammaStats.p975,
          est_gamma_p005: gammaStats.p005,
          est_gamma_p995: gammaStats.p995,
          est_gamma_p0001: gammaStats.p0001,
          est_gamma_p001: gammaStats.p001,
          est_gamma_p01: gammaStats.p01,
          est_gamma_p10: gammaStats.p10
        }
      })
      .sort((a, b) => a.sample_size - b.sample_size)
  }, [filteredData, selectedSampleSizes, config])

  // Convergence chart data - 使用预计算数据
  const convergenceCurves = useMemo((): CurveData[] => {
    if (convergenceData.length === 0 || convergenceSampleSizes.length === 0) return []

    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#6366f1']

    // 获取统计量字段的键名
    const getStatKey = (param: 'beta' | 'eta' | 'gamma', stat: 'mean' | 'median' | 'std') => {
      return `${param}_${stat}` as keyof typeof convergenceData[0]
    }

    return convergenceSampleSizes.map((n, idx) => {
      // 筛选该样本量的数据
      const rows = convergenceData.filter(d => d.sample_size === n)

      // 构建曲线数据
      const data = rows.map(row => {
        const statKey = getStatKey(convergenceParamTab, convergenceStatTab)
        const value = row[statKey]
        return {
          mcRuns: row.mc_runs,
          value: typeof value === 'number' && !isNaN(value) ? value : 0
        }
      })

      return {
        id: `n${n}`,
        label: `n=${n}`,
        data,
        color: colors[idx % colors.length]
      }
    })
  }, [convergenceData, convergenceSampleSizes, convergenceStatTab, convergenceParamTab])

  // Loading state
  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-orange-200 border-t-orange-600 mb-4"></div>
          <p className="text-slate-600 font-bold">加载中...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-2xl p-4 text-red-700 text-sm">
        <div className="flex items-center gap-2"><Info size={16} /><span>{error}</span></div>
      </div>
    )
  }

  if (!config) return null

  const sampleSizeParam = config.params?.find(p => p.id === 'sampleSize')
  const mcRunsList = config.simulation?.mcRunsList || [1000, 2000, 3000, 4000, 5000]
  const trueValues = {
    beta: config.defaults?.beta ?? 2.0,
    eta: config.defaults?.eta ?? 1000,
    gamma: config.defaults?.gamma ?? 1000
  }

  return (
    <div className="space-y-6">
      {/* 参数配置面板 - 与方法示例1结构一致 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Settings className="text-slate-600" size={20} />
            <h3 className="text-lg font-bold text-slate-800">参数配置</h3>
          </div>
          <div className="text-sm text-slate-500">
            <span className="font-bold text-blue-600">1</span> 个变量 /
            <span className="font-bold text-slate-600">4</span> 个固定
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {config.params?.map(param => (
            <ParamCard2
              key={param.id}
              param={param}
              selectedSampleSizes={selectedSampleSizes}
              onToggleSampleSize={toggleSampleSize}
              onSelectAll={selectAllSampleSizes}
            />
          ))}
        </div>
      </div>

      {/* 仿真与计算设置面板 - 与方法示例1结构一致 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <FlaskConical className="text-purple-600" size={20} />
          <h3 className="text-lg font-bold text-slate-800">仿真与计算设置</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* 蒙特卡洛仿真 */}
          <div className="bg-purple-50 rounded-xl p-4 border border-purple-200">
            <h4 className="text-sm font-bold text-purple-800 mb-3">蒙特卡洛仿真</h4>
            <div className="space-y-2 text-sm">
              {/* 每组重复次数 - 用小方块显示变量 */}
              <div className="flex justify-between items-center">
                <span className="text-slate-600">每组重复次数</span>
                <div className="flex flex-wrap gap-1 justify-end">
                  {mcRunsList.map(mc => (
                    <span
                      key={mc}
                      onClick={() => setSelectedMcRuns(mc)}
                      className={cn(
                        "px-1.5 py-0.5 rounded text-xs font-mono font-bold transition-all bg-white cursor-pointer border",
                        selectedMcRuns === mc
                          ? "border-2 text-red-500 bg-gradient-to-r from-red-100 to-orange-50"
                          : "border-slate-200 text-slate-600 hover:border-slate-300"
                      )}
                      style={selectedMcRuns === mc ? { borderColor: '#f87171' } : {}}
                    >
                      {mc / 1000}k
                    </span>
                  ))}
                </div>
              </div>

              {/* 参数组合数 */}
              <div className="flex justify-between">
                <span className="text-slate-600">参数组合数</span>
                <span className="font-mono font-bold text-purple-700">{config.simulation?.totalCombinations || selectedSampleSizes.length}</span>
              </div>

              {/* 总模拟次数 */}
              <div className="flex justify-between">
                <span className="text-slate-600">总模拟次数</span>
                <span className="font-mono font-bold text-purple-700">{(selectedMcRuns * selectedSampleSizes.length).toLocaleString()}</span>
              </div>

              {/* 随机种子公式 */}
              {config.simulation?.seedFormula && (
                <div className="mt-2 pt-2 border-t border-purple-200">
                  <span className="text-slate-500 text-xs">随机种子公式:</span>
                  <code className="block text-xs text-purple-600 mt-1 bg-white p-1.5 rounded font-mono">{config.simulation.seedFormula}</code>
                </div>
              )}
            </div>
          </div>

          {/* 计算设置 */}
          <div className="bg-blue-50 rounded-xl p-4 border border-blue-200">
            <h4 className="text-sm font-bold text-blue-800 mb-3">MDM 算法参数</h4>
            <div className="space-y-2 text-sm">
              {config.calculation?.gammaSteps && (
                <div className="flex justify-between">
                  <span className="text-slate-600">梯度计算步数</span>
                  <span className="font-mono font-bold text-blue-700">{config.calculation.gammaSteps}</span>
                </div>
              )}
              {config.calculation?.betaBounds && (
                <div className="flex justify-between">
                  <span className="text-slate-600">β 搜索范围</span>
                  <span className="font-mono font-bold text-blue-700">[{config.calculation.betaBounds[0]}, {config.calculation.betaBounds[1]}]</span>
                </div>
              )}
              {config.calculation?.gammaRangeRound1 && (
                <div className="flex justify-between">
                  <span className="text-slate-600">γ 搜索 R1</span>
                  <span className="font-mono font-bold text-blue-700">[0, {config.calculation.gammaRangeRound1[1]}×t<sub>min</sub>]</span>
                </div>
              )}
              {config.calculation?.gammaRangeRound2 && (
                <div className="flex justify-between">
                  <span className="text-slate-600">γ 搜索 R2</span>
                  <span className="font-mono font-bold text-blue-700">[{config.calculation.gammaRangeRound2[0]}, {config.calculation.gammaRangeRound2[1]}]×t<sub>min</sub></span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Statistics Table */}
      {stats.length > 0 && (
        <StatsTable
          stats={stats}
          displayOptions={displayOptions}
          paramSelection={paramSelection}
          trueValues={trueValues}
          onToggleDisplayOption={(key) => setDisplayOptions(prev => ({ ...prev, [key]: !prev[key] }))}
          onToggleParamSelection={(key) => setParamSelection(prev => ({ ...prev, [key]: !prev[key] }))}
        />
      )}

      {/* Charts - Only show when sample sizes are selected */}
      {selectedSampleSizes.length > 0 && stats.length > 0 && (
        <>
          {/* Boxplot Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {(['beta', 'eta', 'gamma'] as const).filter(p => paramSelection[p]).map((param, idx) => {
              const config = {
                beta: { color: EST_PARAM_COLORS.beta.color, yLabel: 'β估计值', trueValue: trueValues.beta },
                eta: { color: EST_PARAM_COLORS.eta.color, yLabel: 'η估计值', trueValue: trueValues.eta },
                gamma: { color: EST_PARAM_COLORS.gamma.color, yLabel: 'γ估计值', trueValue: trueValues.gamma }
              }[param]

              return (
                <ChartCard key={param} title={`图 ${idx + 1}: ${param}估计值分布`}>
                  <BoxPlotChart
                    data={stats}
                    dataKeyMin={`est_${param}_min`}
                    dataKeyMax={`est_${param}_max`}
                    dataKeyP01={`est_${param}_p005`}
                    dataKeyP99={`est_${param}_p995`}
                    dataKeyMedian={`est_${param}_median`}
                    color={config.color}
                    yLabel={config.yLabel}
                    xLabel="n"
                    trueValue={config.trueValue}
                  />
                </ChartCard>
              )
            })}
          </div>

          {/* Density Chart with Tabs */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-800">概率密度分布</h3>
              <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
                {(['beta', 'eta', 'gamma'] as const).filter(p => paramSelection[p]).map(param => (
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
            <DensityChart
              rawData={filteredData}
              paramId={densityTab}
              displayDimension={{ id: 'sampleSize', name: '样本量', symbol: 'n' }}
              trueValue={trueValues[densityTab]}
              color={densityTab === 'beta' ? 'blue' : densityTab === 'eta' ? 'emerald' : 'amber'}
            />
          </div>

          {/* Convergence Chart */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-800">收敛曲线</h3>
              <div className="flex gap-4">
                {/* Stat Type Tabs */}
                <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
                  {(['median', 'mean', 'std'] as const).map(stat => (
                    <button
                      key={stat}
                      onClick={() => setConvergenceStatTab(stat)}
                      className={cn(
                        "px-3 py-1 rounded-md text-xs font-bold transition-all",
                        convergenceStatTab === stat
                          ? "bg-white shadow-sm text-slate-700"
                          : "text-slate-500 hover:text-slate-700"
                      )}
                    >
                      {stat === 'median' ? '中位数' : stat === 'mean' ? '均值' : '标准差'}
                    </button>
                  ))}
                </div>
                {/* Param Tabs */}
                <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
                  {(['beta', 'eta', 'gamma'] as const).filter(p => paramSelection[p]).map(param => (
                    <button
                      key={param}
                      onClick={() => setConvergenceParamTab(param)}
                      className={cn(
                        "px-3 py-1 rounded-md text-xs font-bold transition-all",
                        convergenceParamTab === param
                          ? "bg-white shadow-sm"
                          : "text-slate-500 hover:text-slate-700"
                      )}
                      style={convergenceParamTab === param ? { color: EST_PARAM_COLORS[param].color } : {}}
                    >
                      {param === 'beta' ? 'β' : param === 'eta' ? 'η' : 'γ'}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* 样本量选择 */}
            <div className="flex items-center justify-between mb-4 pb-4 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-slate-600">显示曲线：</span>
                <div className="flex flex-wrap gap-1">
                  {sampleSizeParam?.discreteValues?.map(v => {
                    const n = Number(v)
                    const isSelected = convergenceSampleSizes.includes(n)
                    return (
                      <span
                        key={v}
                        onClick={() => toggleConvergenceSampleSize(n)}
                        className={cn(
                          "px-1.5 py-0.5 rounded text-xs font-mono font-bold transition-all bg-white cursor-pointer border",
                          isSelected
                            ? "border-2 text-red-500 bg-gradient-to-r from-red-100 to-orange-50"
                            : "border-slate-200 text-slate-400 hover:border-slate-300"
                        )}
                        style={isSelected ? { borderColor: '#f87171' } : {}}
                      >
                        n={n}
                      </span>
                    )
                  })}
                </div>
                {/* 全选/全不选按钮 */}
                <div className="flex gap-1 ml-2">
                  <button
                    onClick={selectAllConvergenceSampleSizes}
                    className="px-2 py-0.5 text-xs font-bold text-purple-600 hover:text-purple-800 hover:bg-purple-50 rounded transition-all"
                  >
                    全选
                  </button>
                  <button
                    onClick={() => setConvergenceSampleSizes([])}
                    className="px-2 py-0.5 text-xs font-bold text-slate-400 hover:text-slate-600 hover:bg-slate-50 rounded transition-all"
                  >
                    全不选
                  </button>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">
                  真实值: {convergenceParamTab === 'beta' ? 'β' : convergenceParamTab === 'eta' ? 'η' : 'γ'} = {trueValues[convergenceParamTab]}
                </span>
              </div>
            </div>

            <ConvergenceChart
              curves={convergenceCurves}
              statType={convergenceStatTab}
              trueValue={trueValues[convergenceParamTab]}
              yLabel={`${convergenceParamTab === 'beta' ? 'β' : convergenceParamTab === 'eta' ? 'η' : 'γ'}估计${convergenceStatTab === 'median' ? '中位数' : convergenceStatTab === 'mean' ? '均值' : '标准差'}`}
            />
          </div>
        </>
      )}
    </div>
  )
}

// ============ Sub Components ============

function StatsTable({
  stats,
  displayOptions,
  paramSelection,
  trueValues,
  onToggleDisplayOption,
  onToggleParamSelection
}: {
  stats: StatsResult[]
  displayOptions: TableDisplayOptions
  paramSelection: { beta: boolean; eta: boolean; gamma: boolean }
  trueValues: { beta: number; eta: number; gamma: number }
  onToggleDisplayOption: (key: keyof TableDisplayOptions) => void
  onToggleParamSelection: (key: keyof typeof paramSelection) => void
}) {
  const fmt = (val: number | null | undefined, decimals = 2) =>
    val === null || val === undefined ? '—' : val.toFixed(decimals)

  const selectedParams = Object.entries(paramSelection)
    .filter(([_, selected]) => selected)
    .map(([key]) => key as 'beta' | 'eta' | 'gamma')

  const [showFilterDropdown, setShowFilterDropdown] = useState(false)
  const filterRef = useRef<HTMLDivElement>(null)

  // 渲染单个参数的行
  const renderParamRows = (
    param: 'beta' | 'eta' | 'gamma',
    trueVal: number,
    decimals: number,
    s: StatsResult,
    idx: number,
    rowSpan: number
  ) => {
    return (
      <tr key={param} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
        {param === selectedParams[0] && (
          <td rowSpan={rowSpan} className="py-1.5 px-2 font-mono text-slate-700 text-center align-middle border-b border-slate-200 sticky left-0 bg-inherit min-w-[50px]">
            {s.keyLabel}
          </td>
        )}
        <td className={cn("py-1.5 px-2 font-bold text-center border-b border-slate-200", EST_PARAM_COLORS[param].text)}>
          {param === 'beta' ? 'β' : param === 'eta' ? 'η' : 'γ'}
        </td>
        <td className="text-right py-1.5 px-2 font-mono text-slate-700 border-b border-slate-200">{trueVal}</td>
        {displayOptions.mean && <td className="text-right py-1.5 px-2 font-mono text-slate-700 border-b border-slate-200">{fmt(s[`est_${param}_mean` as keyof StatsResult] as number | null, decimals)}</td>}
        {displayOptions.biasMean && <td className={cn("text-right py-1.5 px-2 font-mono border-b border-slate-200", (s[`bias_${param}_mean` as keyof StatsResult] as number || 0) > 0 ? 'text-red-600' : 'text-blue-600')}>{fmt(s[`bias_${param}_mean` as keyof StatsResult] as number | null, decimals)}</td>}
        {displayOptions.median && <td className="text-right py-1.5 px-2 font-mono text-slate-700 border-b border-slate-200">{fmt(s[`est_${param}_median` as keyof StatsResult] as number | null, decimals)}</td>}
        {displayOptions.biasMedian && <td className={cn("text-right py-1.5 px-2 font-mono border-b border-slate-200", (s[`bias_${param}_median` as keyof StatsResult] as number || 0) > 0 ? 'text-red-600' : 'text-blue-600')}>{fmt(s[`bias_${param}_median` as keyof StatsResult] as number | null, decimals)}</td>}
        {displayOptions.std && <td className="text-right py-1.5 px-2 font-mono text-slate-700 border-b border-slate-200">{fmt(s[`est_${param}_std` as keyof StatsResult] as number | null, decimals)}</td>}
        {displayOptions.ci95 && <td className="text-right py-1.5 px-2 font-mono text-slate-700 border-b border-slate-200 text-xs">[{fmt(s[`est_${param}_p025` as keyof StatsResult] as number | null, decimals)}, {fmt(s[`est_${param}_p975` as keyof StatsResult] as number | null, decimals)}]</td>}
        {displayOptions.ci99 && <td className="text-right py-1.5 px-2 font-mono text-slate-700 border-b border-slate-200 text-xs">[{fmt(s[`est_${param}_p005` as keyof StatsResult] as number | null, decimals)}, {fmt(s[`est_${param}_p995` as keyof StatsResult] as number | null, decimals)}]</td>}
        {displayOptions.fullRange && <td className="text-right py-1.5 px-2 font-mono text-slate-700 border-b border-slate-200 text-xs">[{fmt(s[`est_${param}_min` as keyof StatsResult] as number | null, decimals)}, {fmt(s[`est_${param}_max` as keyof StatsResult] as number | null, decimals)}]</td>}
        {displayOptions.quantileBias && (
          <>
            <td className="text-right py-1.5 px-2 font-mono text-slate-600 border-b border-slate-200 text-xs">{fmt((s[`est_${param}_p0001` as keyof StatsResult] as number | null ?? 0) - trueVal, decimals)}</td>
            <td className="text-right py-1.5 px-2 font-mono text-slate-600 border-b border-slate-200 text-xs">{fmt((s[`est_${param}_p001` as keyof StatsResult] as number | null ?? 0) - trueVal, decimals)}</td>
            <td className="text-right py-1.5 px-2 font-mono text-slate-600 border-b border-slate-200 text-xs">{fmt((s[`est_${param}_p01` as keyof StatsResult] as number | null ?? 0) - trueVal, decimals)}</td>
            <td className="text-right py-1.5 px-2 font-mono text-slate-600 border-b border-slate-200 text-xs">{fmt((s[`est_${param}_p10` as keyof StatsResult] as number | null ?? 0) - trueVal, decimals)}</td>
          </>
        )}
      </tr>
    )
  }

  return (
    <div className="space-y-4">
      {/* Control Bar */}
      <div className="bg-white rounded-xl p-4 border border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-slate-600">显示参数：</span>
          {(['beta', 'eta', 'gamma'] as const).map(param => (
            <button
              key={param}
              onClick={() => onToggleParamSelection(param)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-sm font-bold transition-all border",
                paramSelection[param]
                  ? `${EST_PARAM_COLORS[param].bg} ${EST_PARAM_COLORS[param].text} ${EST_PARAM_COLORS[param].border}`
                  : "bg-slate-100 text-slate-400 border-slate-200 hover:bg-slate-200"
              )}
            >
              {param === 'beta' ? 'β' : param === 'eta' ? 'η' : 'γ'}
            </button>
          ))}
        </div>

        {/* 筛选显示按钮 */}
        <div ref={filterRef} className="relative">
          <button
            onClick={() => setShowFilterDropdown(!showFilterDropdown)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-bold transition-all border",
              showFilterDropdown ? "bg-purple-100 text-purple-700 border-purple-300" : "bg-white text-slate-600 border-slate-300 hover:bg-slate-50"
            )}
          >
            <Filter size={14} />
            筛选显示
          </button>

          {showFilterDropdown && (
            <div className="absolute right-0 top-full mt-2 w-64 bg-white rounded-xl shadow-lg border border-slate-200 p-3 z-50">
              <div className="text-xs font-bold text-slate-500 mb-2">选择显示的统计量</div>
              <div className="space-y-1.5">
                {[
                  { key: 'mean', label: '均值' },
                  { key: 'biasMean', label: '均值偏差' },
                  { key: 'median', label: '中位数' },
                  { key: 'biasMedian', label: '中位数偏差' },
                  { key: 'std', label: '标准差' },
                  { key: 'ci95', label: '95% CI [P2.5, P97.5]' },
                  { key: 'ci99', label: '99% CI [P0.5, P99.5]' },
                  { key: 'fullRange', label: '全范围 [min, max]' },
                  { key: 'quantileBias', label: '分位数偏差 (F=0.01%~10%)' }
                ].map(opt => (
                  <label key={opt.key} className="flex items-center gap-2 cursor-pointer hover:bg-slate-50 p-1 rounded">
                    <input
                      type="checkbox"
                      checked={displayOptions[opt.key as keyof TableDisplayOptions]}
                      onChange={() => onToggleDisplayOption(opt.key as keyof TableDisplayOptions)}
                      className="w-4 h-4 rounded border-slate-300 text-purple-600 focus:ring-purple-500"
                    />
                    <span className="text-sm text-slate-700">{opt.label}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white border border-slate-300 rounded-xl p-4 overflow-hidden">
        <p className="text-center text-base font-semibold text-slate-700 mb-3">
          表: 参数估计汇总统计 (按样本量分组)
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse min-w-[800px]">
            <thead>
              <tr className="border-b-2 border-slate-400">
                <th className="text-center py-2 px-2 font-bold text-slate-800 sticky left-0 bg-white min-w-[50px]">n</th>
                <th className="text-center py-2 px-2 font-bold text-slate-800 min-w-[40px]">参数</th>
                <th className="text-right py-2 px-2 font-bold text-slate-800 min-w-[60px]">真实值</th>
                {displayOptions.mean && <th className="text-right py-2 px-2 font-bold text-slate-800 min-w-[70px]">均值</th>}
                {displayOptions.biasMean && <th className="text-right py-2 px-2 font-bold text-slate-800 min-w-[70px]">均值偏差</th>}
                {displayOptions.median && <th className="text-right py-2 px-2 font-bold text-slate-800 min-w-[70px]">中位数</th>}
                {displayOptions.biasMedian && <th className="text-right py-2 px-2 font-bold text-slate-800 min-w-[80px]">中位数偏差</th>}
                {displayOptions.std && <th className="text-right py-2 px-2 font-bold text-slate-800 min-w-[60px]">SD</th>}
                {displayOptions.ci95 && <th className="text-right py-2 px-2 font-bold text-slate-800 min-w-[100px]">95% CI</th>}
                {displayOptions.ci99 && <th className="text-right py-2 px-2 font-bold text-slate-800 min-w-[100px]">99% CI</th>}
                {displayOptions.fullRange && <th className="text-right py-2 px-2 font-bold text-slate-800 min-w-[100px]">全范围</th>}
                {displayOptions.quantileBias && (
                  <>
                    <th className="text-right py-2 px-2 font-bold text-slate-800 text-xs">F=0.01%</th>
                    <th className="text-right py-2 px-2 font-bold text-slate-800 text-xs">F=0.1%</th>
                    <th className="text-right py-2 px-2 font-bold text-slate-800 text-xs">F=1%</th>
                    <th className="text-right py-2 px-2 font-bold text-slate-800 text-xs">F=10%</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {stats.map((s, idx) => {
                return (
                  <React.Fragment key={idx}>
                    {selectedParams.includes('beta') && renderParamRows('beta', trueValues.beta, 4, s, idx, selectedParams.length)}
                    {selectedParams.includes('eta') && renderParamRows('eta', trueValues.eta, 2, s, idx, selectedParams.length)}
                    {selectedParams.includes('gamma') && renderParamRows('gamma', trueValues.gamma, 2, s, idx, selectedParams.length)}
                  </React.Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// 参数卡片组件 - 与方法示例1结构一致
function ParamCard2({
  param,
  selectedSampleSizes,
  onToggleSampleSize,
  onSelectAll
}: {
  param: ParamConfig
  selectedSampleSizes: number[]
  onToggleSampleSize: (n: number) => void
  onSelectAll: () => void
}) {
  const isVariable = param.isVariable

  // 格式化显示值
  const formatValue = (v: number | string) => {
    if (typeof v === 'string') return v
    if (typeof v === 'number' && v < 1 && v !== 0) return v.toFixed(2)
    if (Number.isInteger(v)) return String(v)
    return String(v)
  }

  // 获取要显示的值列表
  const getDisplayValues = (): (number | string)[] => {
    if (param.state === 'fixed' && param.fixedValue !== undefined) {
      return [param.fixedValue]
    }
    if (param.state === 'discrete' && param.discreteValues) {
      return param.discreteValues
    }
    return []
  }

  const values = getDisplayValues()

  // 判断某个值是否应该高亮
  const isActiveValue = (value: number | string): boolean => {
    if (!isVariable) {
      return param.state === 'fixed' && String(param.fixedValue) === String(value)
    }
    // 变量参数：高亮已选中的值
    return selectedSampleSizes.includes(Number(value))
  }

  return (
    <div className={cn("rounded-xl border-2 p-4 transition-all", PARAM_COLORS[param.id] || 'border-slate-200 bg-slate-50')}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1">
          <span className="text-sm font-bold">{param.name}</span>
          <span className="text-xs font-mono text-slate-500">{param.symbol}</span>
        </div>
        <div className={cn("px-2 py-0.5 rounded text-xs font-bold", isVariable ? "bg-white text-purple-700" : "bg-slate-200 text-slate-500")}>
          {isVariable ? "变量" : "固定"}
        </div>
      </div>

      {/* 统一布局：所有参数都用白色块显示值 */}
      <div className="flex flex-wrap gap-1">
        {values.map(v => (
          <span
            key={v}
            onClick={() => isVariable && onToggleSampleSize(Number(v))}
            className={cn(
              "px-1.5 py-0.5 rounded text-xs font-mono font-bold transition-all bg-white",
              isActiveValue(v)
                ? "border-2 text-red-500 bg-gradient-to-r from-red-100 to-orange-50"
                : "border border-slate-200 text-slate-600",
              isVariable && "cursor-pointer hover:border-slate-300"
            )}
            style={isActiveValue(v) ? { borderColor: '#f87171' } : {}}
          >
            {formatValue(v)}
          </span>
        ))}
      </div>

      {/* 变量参数显示全选按钮 */}
      {isVariable && (
        <div className="mt-3 pt-3 border-t border-black/10">
          <button
            onClick={onSelectAll}
            className="w-full flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-bold transition-all bg-white text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <Filter size={12} />
            全选
          </button>
        </div>
      )}
    </div>
  )
}
