"use client"

import React, { useState, useEffect, useMemo, useRef } from 'react'
import { ChevronDown, FlaskConical, Filter, Settings, Layers, BookOpen, Info, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import matter from 'gray-matter'
// 导入独立图表组件
import { ChartCard } from './charts/ChartCard'
import { BoxPlotChart } from './charts/BoxPlotChart'
import { HeatmapChart } from './charts/HeatmapChart'

// 参数配置类型
interface ParamConfig {
  id: string
  name: string
  symbol: string
  state: 'fixed' | 'range' | 'discrete'
  fixedValue?: number
  range?: { min: number; max: number }
  discreteValues?: number[]
  isVariable: boolean
  isDisplayDimension: boolean
}

// 仿真设置类型
interface SimulationConfig {
  mcRuns?: number
  totalCombinations?: number
  totalRuns?: number
  seedFormula?: string
}

// 计算设置类型
interface CalculationConfig {
  gammaSteps?: number
  betaBounds?: [number, number]
  gammaRangeRound1?: [number, number]
  gammaRangeRound2?: [number, number]
  defaultOffset?: number
}

// 图表配置类型
interface ChartItemConfig {
  param: 'beta' | 'eta' | 'gamma'
  title: string
}

interface ChartsConfig {
  univariate?: ChartItemConfig[]
  bivariate?: ChartItemConfig[]
}

// 配置类型
interface StudyConfig {
  id: string
  name: string
  description: string
  method: string
  dirName: string
  params?: ParamConfig[]
  defaults?: Record<string, number>
  processSymbol?: string
  simulation?: SimulationConfig
  calculation?: CalculationConfig
  charts?: ChartsConfig
}

// CSV 数据行
interface SimulationRow {
  beta_true: number
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

// 统计结果
interface StatsResult {
  key: string
  keyLabel: string
  beta_true?: number
  sample_size?: number
  offset_value?: number
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
}

// 表格显示选项
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

// 参数选择
interface ParamSelection {
  beta: boolean
  eta: boolean
  gamma: boolean
}

const DEFAULT_PARAM_SELECTION: ParamSelection = {
  beta: true,
  eta: true,
  gamma: true
}

interface UniversalStudyViewerProps {
  methodId: string
}

// 参数卡片颜色
const PARAM_COLORS: Record<string, string> = {
  beta: 'border-blue-200 bg-blue-50',
  eta: 'border-emerald-200 bg-emerald-50',
  gamma: 'border-amber-200 bg-amber-50',
  sampleSize: 'border-purple-200 bg-purple-50',
  process: 'border-rose-200 bg-rose-50'
}

const PARAM_TEXT_COLORS: Record<string, string> = {
  beta: 'text-blue-700',
  eta: 'text-emerald-700',
  gamma: 'text-amber-700',
  sampleSize: 'text-purple-700',
  process: 'text-rose-700'
}

// 估计参数颜色
const EST_PARAM_COLORS = {
  beta: { bg: 'bg-blue-100', text: 'text-blue-700', border: 'border-blue-300', color: '#1e40af' },
  eta: { bg: 'bg-emerald-100', text: 'text-emerald-700', border: 'border-emerald-300', color: '#047857' },
  gamma: { bg: 'bg-amber-100', text: 'text-amber-700', border: 'border-amber-300', color: '#b45309' }
}

// 示例列表 Hook
function useStudyList(methodId: string) {
  const [studies, setStudies] = useState<StudyConfig[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const loadStudies = async () => {
      try {
        const res = await fetch(`/api/studies/${methodId.toLowerCase()}`)
        if (res.ok) {
          const data = await res.json()
          setStudies(data.studies || [])
        }
      } catch (err) {
        console.error('Failed to load studies:', err)
      } finally {
        setIsLoading(false)
      }
    }
    loadStudies()
  }, [methodId])

  return { studies, isLoading }
}

export default function UniversalStudyViewer({ methodId }: UniversalStudyViewerProps) {
  const { studies, isLoading: isLoadingList } = useStudyList(methodId)
  const [selectedStudyId, setSelectedStudyId] = useState<string>('')

  const [config, setConfig] = useState<StudyConfig | null>(null)
  const [csvData, setCsvData] = useState<SimulationRow[]>([])
  const [params, setParams] = useState<ParamConfig[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [displayOptions, setDisplayOptions] = useState<TableDisplayOptions>(DEFAULT_DISPLAY_OPTIONS)
  const [paramSelection, setParamSelection] = useState<ParamSelection>(DEFAULT_PARAM_SELECTION)
  const [showFilterDropdown, setShowFilterDropdown] = useState(false)
  const filterRef = useRef<HTMLDivElement>(null)

  // 点击外部关闭下拉
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (filterRef.current && !filterRef.current.contains(e.target as Node)) {
        setShowFilterDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // 默认选择第一个示例
  useEffect(() => {
    if (studies.length > 0 && !selectedStudyId) {
      setSelectedStudyId(studies[0].id)
    }
  }, [studies, selectedStudyId])

  // 加载配置和数据
  useEffect(() => {
    if (!selectedStudyId) return

    const selectedStudy = studies.find(s => s.id === selectedStudyId)
    if (!selectedStudy) return

    const basePath = `/studies/${methodId.toLowerCase()}/${selectedStudy.dirName}`

    const loadData = async () => {
      try {
        setIsLoading(true)
        setError(null)

        const [configRes, csvRes] = await Promise.all([
          fetch(`${basePath}/config.md`),
          fetch(`${basePath}/data.csv`)
        ])

        if (!configRes.ok) throw new Error('配置文件加载失败')
        if (!csvRes.ok) throw new Error('数据文件加载失败')

        const configText = await configRes.text()
        const csvText = await csvRes.text()

        const parsedConfig = parseConfigMd(configText)
        const parsedCsv = parseCsv(csvText)

        setConfig({ ...parsedConfig, dirName: selectedStudy.dirName })
        setCsvData(parsedCsv)

        if (parsedConfig.params && parsedConfig.params.length > 0) {
          const initializedParams = parsedConfig.params.map((p, idx) => ({
            ...p,
            isDisplayDimension: p.isVariable && idx === 0
          }))
          setParams(initializedParams)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : '加载失败')
        console.error('Load error:', err)
      } finally {
        setIsLoading(false)
      }
    }

    loadData()
  }, [methodId, selectedStudyId, studies])

  const parseConfigMd = (text: string): StudyConfig => {
    try {
      const { data } = matter(text)
      return {
        id: data.id || 'unknown',
        name: data.name || '未命名示例',
        description: data.description || '',
        method: data.method || methodId,
        dirName: '',
        params: data.params || [],
        defaults: data.defaults || {},
        processSymbol: data.processSymbol || 'δ',
        simulation: data.simulation || {},
        calculation: data.calculation || {},
        charts: data.charts || {}
      }
    } catch (e) {
      throw new Error('配置文件格式错误')
    }
  }

  const parseCsv = (text: string): SimulationRow[] => {
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

  const toggleDisplayDimension = (paramId: string) => {
    setParams(prev => prev.map(p =>
      p.id === paramId && p.isVariable ? { ...p, isDisplayDimension: !p.isDisplayDimension } : p
    ))
  }

  const toggleDisplayOption = (key: keyof TableDisplayOptions) => {
    setDisplayOptions(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const toggleParamSelection = (key: keyof ParamSelection) => {
    setParamSelection(prev => ({ ...prev, [key]: !prev[key] }))
  }

  // 计算统计量
  const stats = useMemo(() => {
    const displayDimensions = params.filter(p => p.isDisplayDimension)
    if (displayDimensions.length === 0 || csvData.length === 0) return []

    const variableParams = params.filter(p => p.isVariable)
    const defaults = config?.defaults || {}

    const filteredData = csvData.filter(row => {
      if (!variableParams.find(p => p.id === 'beta')) {
        if (defaults.beta !== undefined && row.beta_true !== defaults.beta) return false
      }
      if (!variableParams.find(p => p.id === 'sampleSize')) {
        if (defaults.sampleSize !== undefined && row.sample_size !== defaults.sampleSize) return false
      }
      if (!variableParams.find(p => p.id === 'process')) {
        if (defaults.process !== undefined && row.offset_value !== defaults.process) return false
      }
      return true
    })

    const groups = new Map<string, SimulationRow[]>()
    filteredData.forEach(row => {
      const keyParts: string[] = []
      displayDimensions.forEach(p => {
        if (p.id === 'beta') keyParts.push(`β=${row.beta_true}`)
        if (p.id === 'sampleSize') keyParts.push(`n=${row.sample_size}`)
        if (p.id === 'process') keyParts.push(`${config?.processSymbol || 'δ'}=${row.offset_value}`)
      })
      const key = keyParts.join(', ')
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key)!.push(row)
    })

    const calcStats = (values: number[], trueValue: number) => {
      if (values.length === 0) return { mean: null, std: null, median: null, biasMean: null, biasMedian: null, min: null, max: null, p025: null, p975: null, p005: null, p995: null, p0001: null, p001: null, p01: null, p10: null }

      const sorted = [...values].sort((a, b) => a - b)
      const n = sorted.length
      const mean = values.reduce((a, b) => a + b, 0) / n
      const std = Math.sqrt(values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / n)

      const quantile = (q: number) => {
        const pos = (n - 1) * q
        const base = Math.floor(pos)
        const rest = pos - base
        return sorted[base + 1] !== undefined ? sorted[base] + rest * (sorted[base + 1] - sorted[base]) : sorted[base]
      }

      const median = quantile(0.5)
      const biasMean = mean - trueValue
      const biasMedian = median - trueValue

      return {
        mean, std, median, biasMean, biasMedian,
        min: sorted[0], max: sorted[n - 1],
        p025: quantile(0.025), p975: quantile(0.975),
        p005: quantile(0.005), p995: quantile(0.995),
        p0001: quantile(0.001), p001: quantile(0.01), p01: quantile(0.1), p10: quantile(0.9)
      }
    }

    return Array.from(groups.entries()).map(([key, rows]): StatsResult => {
      const validRows = rows.filter(r => r.est_beta !== null && r.est_eta !== null && r.est_gamma !== null)

      if (validRows.length === 0) {
        return {
          key, keyLabel: key,
          beta_true: displayDimensions.some(d => d.id === 'beta') ? rows[0].beta_true : undefined,
          sample_size: displayDimensions.some(d => d.id === 'sampleSize') ? rows[0].sample_size : undefined,
          offset_value: displayDimensions.some(d => d.id === 'process') ? rows[0].offset_value : undefined,
          count: rows.length, valid_count: 0,
          est_beta_mean: null, bias_beta_mean: null, est_beta_median: null, bias_beta_median: null, est_beta_std: null,
          est_beta_min: null, est_beta_max: null, est_beta_p025: null, est_beta_p975: null, est_beta_p005: null, est_beta_p995: null,
          est_beta_p0001: null, est_beta_p001: null, est_beta_p01: null, est_beta_p10: null,
          est_eta_mean: null, bias_eta_mean: null, est_eta_median: null, bias_eta_median: null, est_eta_std: null,
          est_eta_min: null, est_eta_max: null, est_eta_p025: null, est_eta_p975: null, est_eta_p005: null, est_eta_p995: null,
          est_eta_p0001: null, est_eta_p001: null, est_eta_p01: null, est_eta_p10: null,
          est_gamma_mean: null, bias_gamma_mean: null, est_gamma_median: null, bias_gamma_median: null, est_gamma_std: null,
          est_gamma_min: null, est_gamma_max: null, est_gamma_p025: null, est_gamma_p975: null, est_gamma_p005: null, est_gamma_p995: null,
          est_gamma_p0001: null, est_gamma_p001: null, est_gamma_p01: null, est_gamma_p10: null
        }
      }

      const betaTrue = rows[0].beta_true ?? config?.defaults?.beta ?? 2.0
      const etaTrue = config?.defaults?.eta ?? 1000
      const gammaTrue = config?.defaults?.gamma ?? 1000

      const betaStats = calcStats(validRows.map(r => r.est_beta!), betaTrue)
      const etaStats = calcStats(validRows.map(r => r.est_eta!), etaTrue)
      const gammaStats = calcStats(validRows.map(r => r.est_gamma!), gammaTrue)

      const labelParts: string[] = []
      displayDimensions.forEach(p => {
        if (p.id === 'beta') labelParts.push(String(rows[0].beta_true))
        if (p.id === 'sampleSize') labelParts.push(String(rows[0].sample_size))
        if (p.id === 'process') {
          const val = rows[0].offset_value
          labelParts.push(typeof val === 'number' && val < 1 && val !== 0 ? val.toFixed(2) : String(val))
        }
      })

      return {
        key, keyLabel: labelParts.length === 1 ? labelParts[0] : labelParts.join(', '),
        beta_true: displayDimensions.some(d => d.id === 'beta') ? rows[0].beta_true : undefined,
        sample_size: displayDimensions.some(d => d.id === 'sampleSize') ? rows[0].sample_size : undefined,
        offset_value: displayDimensions.some(d => d.id === 'process') ? rows[0].offset_value : undefined,
        count: rows.length, valid_count: validRows.length,
        est_beta_mean: betaStats.mean, bias_beta_mean: betaStats.biasMean,
        est_beta_median: betaStats.median, bias_beta_median: betaStats.biasMedian, est_beta_std: betaStats.std,
        est_beta_min: betaStats.min, est_beta_max: betaStats.max,
        est_beta_p025: betaStats.p025, est_beta_p975: betaStats.p975,
        est_beta_p005: betaStats.p005, est_beta_p995: betaStats.p995,
        est_beta_p0001: betaStats.p0001, est_beta_p001: betaStats.p001, est_beta_p01: betaStats.p01, est_beta_p10: betaStats.p10,
        est_eta_mean: etaStats.mean, bias_eta_mean: etaStats.biasMean,
        est_eta_median: etaStats.median, bias_eta_median: etaStats.biasMedian, est_eta_std: etaStats.std,
        est_eta_min: etaStats.min, est_eta_max: etaStats.max,
        est_eta_p025: etaStats.p025, est_eta_p975: etaStats.p975,
        est_eta_p005: etaStats.p005, est_eta_p995: etaStats.p995,
        est_eta_p0001: etaStats.p0001, est_eta_p001: etaStats.p001, est_eta_p01: etaStats.p01, est_eta_p10: etaStats.p10,
        est_gamma_mean: gammaStats.mean, bias_gamma_mean: gammaStats.biasMean,
        est_gamma_median: gammaStats.median, bias_gamma_median: gammaStats.biasMedian, est_gamma_std: gammaStats.std,
        est_gamma_min: gammaStats.min, est_gamma_max: gammaStats.max,
        est_gamma_p025: gammaStats.p025, est_gamma_p975: gammaStats.p975,
        est_gamma_p005: gammaStats.p005, est_gamma_p995: gammaStats.p995,
        est_gamma_p0001: gammaStats.p0001, est_gamma_p001: gammaStats.p001, est_gamma_p01: gammaStats.p01, est_gamma_p10: gammaStats.p10
      }
    }).sort((a, b) => {
      const firstVar = params.find(p => p.isDisplayDimension)
      if (!firstVar) return 0
      if (firstVar.id === 'beta') return (a.beta_true || 0) - (b.beta_true || 0)
      if (firstVar.id === 'sampleSize') return (a.sample_size || 0) - (b.sample_size || 0)
      if (firstVar.id === 'process') return (a.offset_value || 0) - (b.offset_value || 0)
      return 0
    })
  }, [params, csvData, config])

  const variableParams = params.filter(p => p.isVariable)
  const displayDimensions = params.filter(p => p.isDisplayDimension)

  if (isLoadingList) return <LoadingSpinner message="加载示例列表..." />
  if (studies.length === 0) return <EmptyState methodId={methodId} />

  return (
    <div className="space-y-6">
      {/* 下拉选择框 */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-4">
          <BookOpen className="text-orange-600" size={20} />
          <label className="text-sm font-bold text-slate-600 whitespace-nowrap">选择示例：</label>
          <div className="relative flex-1 max-w-md">
            <select
              value={selectedStudyId}
              onChange={(e) => setSelectedStudyId(e.target.value)}
              className="w-full appearance-none bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-orange-500 cursor-pointer hover:bg-slate-100 transition-colors"
            >
              {studies.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={18} />
          </div>
        </div>
      </div>

      {isLoading && <LoadingSpinner message="加载数据中..." />}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-2xl p-4 text-red-700 text-sm">
          <div className="flex items-center gap-2"><Info size={16} /><span>{error}</span></div>
        </div>
      )}

      {!isLoading && !error && config && (
        <>
          {/* 参数面板 */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Settings className="text-slate-600" size={20} />
                <h3 className="text-lg font-bold text-slate-800">参数配置</h3>
              </div>
              <div className="text-sm text-slate-500">
                <span className="font-bold text-blue-600">{variableParams.length}</span> 个变量 /
                <span className="font-bold text-slate-600">{params.length - variableParams.length}</span> 个固定
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              {params.map(param => (
                <ParamCard key={param.id} param={param} processSymbol={config.processSymbol} onToggleDisplayDimension={() => toggleDisplayDimension(param.id)} />
              ))}
            </div>

            {displayDimensions.length === 0 && (
              <div className="mt-4 bg-slate-50 rounded-xl p-4 border border-slate-200 flex items-center gap-3">
                <Info size={16} className="text-slate-500" />
                <p className="text-sm text-slate-600">请至少选择一个变量作为展示维度</p>
              </div>
            )}
          </div>

          {/* 仿真设置面板 */}
          <SimulationSettingsPanel config={config} />

          {/* 统计结果 */}
          {stats.length > 0 && (
            <ResultsVisualization
              stats={stats}
              params={params}
              displayDimensions={displayDimensions}
              config={config}
              displayOptions={displayOptions}
              onToggleDisplayOption={toggleDisplayOption}
              paramSelection={paramSelection}
              onToggleParamSelection={toggleParamSelection}
              showFilterDropdown={showFilterDropdown}
              setShowFilterDropdown={setShowFilterDropdown}
              filterRef={filterRef}
            />
          )}
        </>
      )}
    </div>
  )
}

// 参数卡片组件
function ParamCard({ param, processSymbol, onToggleDisplayDimension }: { param: ParamConfig; processSymbol?: string; onToggleDisplayDimension: () => void }) {
  return (
    <div className={cn("rounded-xl border-2 p-4 transition-all", PARAM_COLORS[param.id] || 'border-slate-200 bg-slate-50')}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1">
          <span className="text-sm font-bold">{param.name}</span>
          <span className={cn("text-xs font-mono", PARAM_TEXT_COLORS[param.id] || 'text-slate-600')}>
            {param.id === 'process' ? processSymbol : param.symbol}
          </span>
        </div>
        <div className={cn("px-2 py-0.5 rounded text-xs font-bold", param.isVariable ? "bg-white text-purple-700" : "bg-slate-200 text-slate-500")}>
          {param.isVariable ? "变量" : "固定"}
        </div>
      </div>

      {param.state === 'fixed' && <div className="text-center"><span className="text-lg font-black font-mono">{param.fixedValue}</span></div>}
      {param.state === 'discrete' && param.discreteValues && (
        <div className="flex flex-wrap gap-1">
          {param.discreteValues.map(v => (
            <span key={v} className="px-1.5 py-0.5 bg-white rounded text-xs font-mono font-bold">
              {typeof v === 'number' && v < 1 && v !== 0 ? v.toFixed(2) : v}
            </span>
          ))}
        </div>
      )}

      {param.isVariable && (
        <div className="mt-3 pt-3 border-t border-black/10">
          <button onClick={onToggleDisplayDimension} className={cn("w-full flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-bold transition-all", param.isDisplayDimension ? "bg-purple-600 text-white hover:bg-purple-700" : "bg-white text-slate-400 hover:bg-slate-100 hover:text-slate-600")}>
            <Filter size={12} />
            {param.isDisplayDimension ? "显示维度 ✓" : "设为显示维度"}
          </button>
        </div>
      )}
    </div>
  )
}

// 结果可视化组件
function ResultsVisualization({
  stats, displayDimensions, config, displayOptions, onToggleDisplayOption, paramSelection, onToggleParamSelection, showFilterDropdown, setShowFilterDropdown, filterRef
}: {
  stats: StatsResult[]
  params: ParamConfig[]
  displayDimensions: ParamConfig[]
  config: StudyConfig
  displayOptions: TableDisplayOptions
  onToggleDisplayOption: (key: keyof TableDisplayOptions) => void
  paramSelection: ParamSelection
  onToggleParamSelection: (key: keyof ParamSelection) => void
  showFilterDropdown: boolean
  setShowFilterDropdown: (v: boolean) => void
  filterRef: React.RefObject<HTMLDivElement>
}) {
  const fmt = (val: number | null, decimals = 2) => val === null ? '—' : val.toFixed(decimals)

  // 获取选中的参数列表
  const selectedParams = Object.entries(paramSelection).filter(([_, selected]) => selected).map(([key]) => key as 'beta' | 'eta' | 'gamma')

  return (
    <div className="space-y-6">
      {/* 控制栏：参数选择 + 筛选显示 */}
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

      {/* 单变量表格 */}
      {displayDimensions.length === 1 && (
        <StatsTable
          stats={stats}
          displayDimensions={displayDimensions}
          config={config}
          displayOptions={displayOptions}
          selectedParams={selectedParams}
        />
      )}

      {/* 单变量箱型图 */}
      {displayDimensions.length === 1 && selectedParams.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {config.charts?.univariate?.filter(c => selectedParams.includes(c.param)).map((chartConfig, idx) => {
            const paramConfig: Record<string, {
              dataKeyMin: keyof StatsResult
              dataKeyMax: keyof StatsResult
              dataKeyP01: keyof StatsResult
              dataKeyP99: keyof StatsResult
              dataKeyMedian: keyof StatsResult
              color: string
              yLabel: string
              trueValue: number
            }> = {
              beta: {
                dataKeyMin: 'est_beta_min',
                dataKeyMax: 'est_beta_max',
                dataKeyP01: 'est_beta_p005',
                dataKeyP99: 'est_beta_p995',
                dataKeyMedian: 'est_beta_median',
                color: EST_PARAM_COLORS.beta.color,
                yLabel: 'β估计值',
                trueValue: config.defaults?.beta ?? 2.0
              },
              eta: {
                dataKeyMin: 'est_eta_min',
                dataKeyMax: 'est_eta_max',
                dataKeyP01: 'est_eta_p005',
                dataKeyP99: 'est_eta_p995',
                dataKeyMedian: 'est_eta_median',
                color: EST_PARAM_COLORS.eta.color,
                yLabel: 'η估计值',
                trueValue: config.defaults?.eta ?? 1000
              },
              gamma: {
                dataKeyMin: 'est_gamma_min',
                dataKeyMax: 'est_gamma_max',
                dataKeyP01: 'est_gamma_p005',
                dataKeyP99: 'est_gamma_p995',
                dataKeyMedian: 'est_gamma_median',
                color: EST_PARAM_COLORS.gamma.color,
                yLabel: 'γ估计值',
                trueValue: config.defaults?.gamma ?? 1000
              }
            }
            const pc = paramConfig[chartConfig.param]
            if (!pc) return null
            return (
              <ChartCard key={chartConfig.param} title={`图 ${idx + 1}: ${chartConfig.title}`}>
                <BoxPlotChart
                  data={stats}
                  dataKeyMin={pc.dataKeyMin}
                  dataKeyMax={pc.dataKeyMax}
                  dataKeyP01={pc.dataKeyP01}
                  dataKeyP99={pc.dataKeyP99}
                  dataKeyMedian={pc.dataKeyMedian}
                  color={pc.color}
                  yLabel={pc.yLabel}
                  xLabel={displayDimensions[0].symbol}
                  trueValue={pc.trueValue}
                />
              </ChartCard>
            )
          })}
        </div>
      )}

      {/* 双变量 */}
      {displayDimensions.length === 2 && (
        <DualVarSection
          stats={stats}
          displayDimensions={displayDimensions}
          config={config}
          displayOptions={displayOptions}
          selectedParams={selectedParams}
        />
      )}
    </div>
  )
}

// 统计表格组件
function StatsTable({
  stats, displayDimensions, config, displayOptions, selectedParams
}: {
  stats: StatsResult[]
  displayDimensions: ParamConfig[]
  config: StudyConfig
  displayOptions: TableDisplayOptions
  selectedParams: ('beta' | 'eta' | 'gamma')[]
}) {
  const fmt = (val: number | null | undefined, decimals = 2) => val === null || val === undefined ? '—' : val.toFixed(decimals)

  const renderParamRows = (param: 'beta' | 'eta' | 'gamma', trueVal: number, decimals: number, s: StatsResult, idx: number, rowSpan: number) => {
    const getVal = (key: string): number | null => {
      const v = s[`${key}_${param}_mean` as keyof StatsResult]
      return (v === null || v === undefined || typeof v !== 'number') ? null : v
    }

    return (
      <tr key={param} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
        {param === selectedParams[0] && (
          <td rowSpan={rowSpan} className="py-1.5 px-2 font-mono text-slate-700 text-center align-middle border-b border-slate-200 sticky left-0 bg-inherit min-w-[60px]">
            {s.keyLabel}
          </td>
        )}
        <td className={cn("py-1.5 px-2 font-bold text-center border-b border-slate-200", EST_PARAM_COLORS[param].text)}>{param}</td>
        <td className="text-right py-1.5 px-2 font-mono text-slate-700 border-b border-slate-200">{trueVal}</td>
        {displayOptions.mean && <td className="text-right py-1.5 px-2 font-mono text-slate-700 border-b border-slate-200">{fmt(getVal('est')?.toFixed ? getVal('est') : s[`est_${param}_mean` as keyof StatsResult] as number | null, decimals)}</td>}
        {displayOptions.biasMean && <td className={cn("text-right py-1.5 px-2 font-mono border-b border-slate-200", (getVal('bias') || 0) > 0 ? 'text-red-600' : 'text-blue-600')}>{fmt(getVal('bias'), decimals)}</td>}
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
    <div className="bg-white border border-slate-300 rounded-xl p-4 overflow-hidden">
      <p className="text-center text-base font-semibold text-slate-700 mb-3">
        表: 参数估计汇总统计 (按{displayDimensions[0].name}分组)
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse min-w-[800px]">
          <thead>
            <tr className="border-b-2 border-slate-400">
              <th className="text-center py-2 px-2 font-bold text-slate-800 sticky left-0 bg-white min-w-[60px]">{displayDimensions[0].symbol}</th>
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
              const betaTrue = s.beta_true ?? config.defaults?.beta ?? 2.0
              const etaTrue = config.defaults?.eta ?? 1000
              const gammaTrue = config.defaults?.gamma ?? 1000

              return (
                <React.Fragment key={idx}>
                  {selectedParams.includes('beta') && renderParamRows('beta', betaTrue, 4, s, idx, selectedParams.length)}
                  {selectedParams.includes('eta') && renderParamRows('eta', etaTrue, 2, s, idx, selectedParams.length)}
                  {selectedParams.includes('gamma') && renderParamRows('gamma', gammaTrue, 2, s, idx, selectedParams.length)}
                </React.Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// 双变量区块
function DualVarSection({
  stats, displayDimensions, config, displayOptions, selectedParams
}: {
  stats: StatsResult[]
  displayDimensions: ParamConfig[]
  config: StudyConfig
  displayOptions: TableDisplayOptions
  selectedParams: ('beta' | 'eta' | 'gamma')[]
}) {
  const fmt = (v: number | null, d = 2) => v === null ? '—' : v.toFixed(d)

  // 获取两个变量的值
  const var1Key = displayDimensions[0].id === 'beta' ? 'beta_true' : displayDimensions[0].id === 'sampleSize' ? 'sample_size' : 'offset_value'
  const var2Key = displayDimensions[1].id === 'beta' ? 'beta_true' : displayDimensions[1].id === 'sampleSize' ? 'sample_size' : 'offset_value'

  const var1Values = Array.from(new Set(stats.map(s => s[var1Key as keyof StatsResult]))).sort((a, b) => (a as number) - (b as number))
  const var2Values = Array.from(new Set(stats.map(s => s[var2Key as keyof StatsResult]))).sort((a, b) => (a as number) - (b as number))

  // 获取参数统计值的辅助函数
  const getStatValue = (s: StatsResult, param: 'beta' | 'eta' | 'gamma', statType: string): number | null => {
    const key = `${statType}_${param}` as keyof StatsResult
    const val = s[key]
    return typeof val === 'number' ? val : null
  }

  // 渲染单个参数的统计列
  const renderParamCells = (s: StatsResult, param: 'beta' | 'eta' | 'gamma', decimals: number) => {
    const cells: React.ReactNode[] = []

    if (displayOptions.mean) {
      const val = getStatValue(s, param, 'est_mean')
      cells.push(<td key={`mean-${param}`} className="text-right py-1.5 px-2 font-mono text-slate-700 border-b border-slate-200">{fmt(val, decimals)}</td>)
    }
    if (displayOptions.biasMean) {
      const val = getStatValue(s, param, 'bias_mean')
      cells.push(<td key={`biasMean-${param}`} className={cn("text-right py-1.5 px-2 font-mono border-b border-slate-200", (val || 0) > 0 ? 'text-red-600' : 'text-blue-600')}>{fmt(val, decimals)}</td>)
    }
    if (displayOptions.median) {
      const val = getStatValue(s, param, 'est_median')
      cells.push(<td key={`median-${param}`} className="text-right py-1.5 px-2 font-mono text-slate-700 border-b border-slate-200">{fmt(val, decimals)}</td>)
    }
    if (displayOptions.biasMedian) {
      const val = getStatValue(s, param, 'bias_median')
      cells.push(<td key={`biasMedian-${param}`} className={cn("text-right py-1.5 px-2 font-mono border-b border-slate-200", (val || 0) > 0 ? 'text-red-600' : 'text-blue-600')}>{fmt(val, decimals)}</td>)
    }
    if (displayOptions.std) {
      const val = getStatValue(s, param, 'est_std')
      cells.push(<td key={`std-${param}`} className="text-right py-1.5 px-2 font-mono text-slate-700 border-b border-slate-200">{fmt(val, decimals)}</td>)
    }
    if (displayOptions.ci95) {
      const p025 = getStatValue(s, param, 'est_p025')
      const p975 = getStatValue(s, param, 'est_p975')
      cells.push(<td key={`ci95-${param}`} className="text-right py-1.5 px-2 font-mono text-slate-700 border-b border-slate-200 text-xs">[{fmt(p025, decimals)}, {fmt(p975, decimals)}]</td>)
    }
    if (displayOptions.ci99) {
      const p005 = getStatValue(s, param, 'est_p005')
      const p995 = getStatValue(s, param, 'est_p995')
      cells.push(<td key={`ci99-${param}`} className="text-right py-1.5 px-2 font-mono text-slate-700 border-b border-slate-200 text-xs">[{fmt(p005, decimals)}, {fmt(p995, decimals)}]</td>)
    }
    if (displayOptions.fullRange) {
      const min = getStatValue(s, param, 'est_min')
      const max = getStatValue(s, param, 'est_max')
      cells.push(<td key={`range-${param}`} className="text-right py-1.5 px-2 font-mono text-slate-700 border-b border-slate-200 text-xs">[{fmt(min, decimals)}, {fmt(max, decimals)}]</td>)
    }
    if (displayOptions.quantileBias) {
      const trueVal = param === 'beta' ? (s.beta_true ?? config.defaults?.beta ?? 2.0) :
                      param === 'eta' ? (config.defaults?.eta ?? 1000) :
                      (config.defaults?.gamma ?? 1000)
      const p0001 = getStatValue(s, param, 'est_p0001')
      const p001 = getStatValue(s, param, 'est_p001')
      const p01 = getStatValue(s, param, 'est_p01')
      const p10 = getStatValue(s, param, 'est_p10')
      cells.push(<td key={`qb1-${param}`} className="text-right py-1.5 px-2 font-mono text-slate-600 border-b border-slate-200 text-xs">{fmt(p0001 !== null ? p0001 - trueVal : null, decimals)}</td>)
      cells.push(<td key={`qb2-${param}`} className="text-right py-1.5 px-2 font-mono text-slate-600 border-b border-slate-200 text-xs">{fmt(p001 !== null ? p001 - trueVal : null, decimals)}</td>)
      cells.push(<td key={`qb3-${param}`} className="text-right py-1.5 px-2 font-mono text-slate-600 border-b border-slate-200 text-xs">{fmt(p01 !== null ? p01 - trueVal : null, decimals)}</td>)
      cells.push(<td key={`qb4-${param}`} className="text-right py-1.5 px-2 font-mono text-slate-600 border-b border-slate-200 text-xs">{fmt(p10 !== null ? p10 - trueVal : null, decimals)}</td>)
    }
    return cells
  }

  // 渲染表头
  const renderParamHeaders = (param: 'beta' | 'eta' | 'gamma', label: string) => {
    const headers: React.ReactNode[] = []
    if (displayOptions.mean) headers.push(<th key="mean" className="text-right py-2 px-2 font-bold text-slate-800 border-b border-slate-300 min-w-[70px]">{label}均值</th>)
    if (displayOptions.biasMean) headers.push(<th key="biasMean" className="text-right py-2 px-2 font-bold text-slate-800 border-b border-slate-300 min-w-[70px]">{label}偏差</th>)
    if (displayOptions.median) headers.push(<th key="median" className="text-right py-2 px-2 font-bold text-slate-800 border-b border-slate-300 min-w-[70px]">{label}中位</th>)
    if (displayOptions.biasMedian) headers.push(<th key="biasMedian" className="text-right py-2 px-2 font-bold text-slate-800 border-b border-slate-300 min-w-[80px]">{label}中位偏</th>)
    if (displayOptions.std) headers.push(<th key="std" className="text-right py-2 px-2 font-bold text-slate-800 border-b border-slate-300 min-w-[60px]">{label}SD</th>)
    if (displayOptions.ci95) headers.push(<th key="ci95" className="text-right py-2 px-2 font-bold text-slate-800 border-b border-slate-300 min-w-[100px]">{label}95%CI</th>)
    if (displayOptions.ci99) headers.push(<th key="ci99" className="text-right py-2 px-2 font-bold text-slate-800 border-b border-slate-300 min-w-[100px]">{label}99%CI</th>)
    if (displayOptions.fullRange) headers.push(<th key="range" className="text-right py-2 px-2 font-bold text-slate-800 border-b border-slate-300 min-w-[100px]">{label}范围</th>)
    if (displayOptions.quantileBias) {
      headers.push(<th key="qb1" className="text-right py-2 px-2 font-bold text-slate-800 border-b border-slate-300 text-xs">{label}.01%</th>)
      headers.push(<th key="qb2" className="text-right py-2 px-2 font-bold text-slate-800 border-b border-slate-300 text-xs">{label}.1%</th>)
      headers.push(<th key="qb3" className="text-right py-2 px-2 font-bold text-slate-800 border-b border-slate-300 text-xs">{label}1%</th>)
      headers.push(<th key="qb4" className="text-right py-2 px-2 font-bold text-slate-800 border-b border-slate-300 text-xs">{label}10%</th>)
    }
    return headers
  }

  // 双变量表格
  return (
    <div className="space-y-6">
      {/* 双变量表格 */}
      <div className="bg-white border border-slate-300 rounded-xl p-4">
        <p className="text-center text-base font-semibold text-slate-700 mb-3">
          表: 双变量参数估计统计
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse min-w-[600px]">
            <thead>
              <tr className="border-b-2 border-slate-400">
                <th className="text-center py-2 px-3 font-bold text-slate-800 sticky left-0 bg-white min-w-[60px]">{displayDimensions[0].symbol}</th>
                <th className="text-center py-2 px-3 font-bold text-slate-800 min-w-[60px]">{displayDimensions[1].symbol}</th>
                <th className="text-right py-2 px-3 font-bold text-slate-800 min-w-[60px]">有效数</th>
                {selectedParams.includes('beta') && renderParamHeaders('beta', 'β')}
                {selectedParams.includes('eta') && renderParamHeaders('eta', 'η')}
                {selectedParams.includes('gamma') && renderParamHeaders('gamma', 'γ')}
              </tr>
            </thead>
            <tbody>
              {stats.map((s, idx) => (
                <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                  <td className="py-1.5 px-3 font-mono text-slate-700 text-center border-b border-slate-200 sticky left-0 bg-inherit">{s.keyLabel.split(',')[0]}</td>
                  <td className="py-1.5 px-3 font-mono text-slate-700 text-center border-b border-slate-200">{s.keyLabel.split(',')[1]}</td>
                  <td className="text-right py-1.5 px-3 font-mono text-slate-700 border-b border-slate-200">{s.valid_count}/{s.count}</td>
                  {selectedParams.includes('beta') && renderParamCells(s, 'beta', 4)}
                  {selectedParams.includes('eta') && renderParamCells(s, 'eta', 2)}
                  {selectedParams.includes('gamma') && renderParamCells(s, 'gamma', 2)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 热力图 - 统一网格布局 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {config.charts?.bivariate?.filter(c => selectedParams.includes(c.param)).map((chartConfig, idx) => {
          const param = chartConfig.param
          const allValues = stats.map(s => s[`bias_${param}_mean` as keyof StatsResult]).filter((v): v is number => v !== null)
          const maxAbs = Math.max(...allValues.map(Math.abs), 0.01)

          return (
            <ChartCard key={param} title={`图 ${idx + 1}: ${chartConfig.title}`}>
              <HeatmapChart
                stats={stats}
                displayDimensions={displayDimensions}
                dataKey={`bias_${param}_mean` as keyof StatsResult}
                maxAbs={maxAbs}
              />
            </ChartCard>
          )
        })}
      </div>
    </div>
  )
}

// 仿真设置面板组件
function SimulationSettingsPanel({ config }: { config: StudyConfig }) {
  const { simulation, calculation } = config

  // 如果没有仿真和计算设置，不显示面板
  if (!simulation && !calculation) return null

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <FlaskConical className="text-purple-600" size={20} />
        <h3 className="text-lg font-bold text-slate-800">仿真与计算设置</h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 仿真设置 */}
        {simulation && (
          <div className="bg-purple-50 rounded-xl p-4 border border-purple-200">
            <h4 className="text-sm font-bold text-purple-800 mb-3">蒙特卡洛仿真</h4>
            <div className="space-y-2 text-sm">
              {simulation.mcRuns && (
                <div className="flex justify-between">
                  <span className="text-slate-600">每组重复次数</span>
                  <span className="font-mono font-bold text-purple-700">{simulation.mcRuns.toLocaleString()}</span>
                </div>
              )}
              {simulation.totalCombinations && (
                <div className="flex justify-between">
                  <span className="text-slate-600">参数组合数</span>
                  <span className="font-mono font-bold text-purple-700">{simulation.totalCombinations}</span>
                </div>
              )}
              {simulation.totalRuns && (
                <div className="flex justify-between">
                  <span className="text-slate-600">总模拟次数</span>
                  <span className="font-mono font-bold text-purple-700">{simulation.totalRuns.toLocaleString()}</span>
                </div>
              )}
              {simulation.seedFormula && (
                <div className="mt-2 pt-2 border-t border-purple-200">
                  <span className="text-slate-500 text-xs">随机种子公式:</span>
                  <code className="block text-xs text-purple-600 mt-1 bg-white p-1.5 rounded font-mono">{simulation.seedFormula}</code>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 计算设置 */}
        {calculation && (
          <div className="bg-blue-50 rounded-xl p-4 border border-blue-200">
            <h4 className="text-sm font-bold text-blue-800 mb-3">MDM 算法参数</h4>
            <div className="space-y-2 text-sm">
              {calculation.gammaSteps && (
                <div className="flex justify-between">
                  <span className="text-slate-600">梯度计算步数</span>
                  <span className="font-mono font-bold text-blue-700">{calculation.gammaSteps}</span>
                </div>
              )}
              {calculation.betaBounds && (
                <div className="flex justify-between">
                  <span className="text-slate-600">β 搜索范围</span>
                  <span className="font-mono font-bold text-blue-700">[{calculation.betaBounds[0]}, {calculation.betaBounds[1]}]</span>
                </div>
              )}
              {calculation.gammaRangeRound1 && (
                <div className="flex justify-between">
                  <span className="text-slate-600">γ 搜索 R1</span>
                  <span className="font-mono font-bold text-blue-700">[0, {calculation.gammaRangeRound1[1]}×t<sub>min</sub>]</span>
                </div>
              )}
              {calculation.gammaRangeRound2 && (
                <div className="flex justify-between">
                  <span className="text-slate-600">γ 搜索 R2</span>
                  <span className="font-mono font-bold text-blue-700">[{calculation.gammaRangeRound2[0]}, {calculation.gammaRangeRound2[1]}]×t<sub>min</sub></span>
                </div>
              )}
              {calculation.defaultOffset && (
                <div className="flex justify-between">
                  <span className="text-slate-600">默认偏移量 δ</span>
                  <span className="font-mono font-bold text-blue-700">{calculation.defaultOffset}</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function LoadingSpinner({ message }: { message: string }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-12">
      <div className="flex flex-col items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-orange-200 border-t-orange-600 mb-4"></div>
        <p className="text-slate-600 font-bold">{message}</p>
      </div>
    </div>
  )
}

function EmptyState({ methodId }: { methodId: string }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-12">
      <div className="flex flex-col items-center justify-center text-slate-400">
        <FlaskConical size={48} className="mb-4 opacity-50" />
        <p className="font-bold">暂无方法示例</p>
        <p className="text-sm mt-2">路径: public/studies/{methodId.toLowerCase()}/</p>
      </div>
    </div>
  )
}
