"use client"

import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { FlaskConical, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ChartCard, BoxPlotChart, HeatmapChart } from '@/components/shared/charts'

// ============ Types ============

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
  beta_true?: number
  eta_true?: number
  gamma_true?: number
  count: number
  valid_count: number
  [key: string]: number | string | null | undefined
}

interface ChunkInfo {
  chunks: string[]
  parsedParams: Record<string, number[]>
  total: number
}

// ============ 硬编码配置 ============

// Tab 配置
const STUDY_TABS: Array<{
  id: string
  name: string
  description: string
  defaultVariables: string[]
}> = [
  {
    id: 'demo1',
    name: '示例1: 参数研究',
    description: '研究不同形状参数、尺度参数、样本量、偏移量对估计结果的影响',
    defaultVariables: ['beta', 'sampleSize']
  },
  {
    id: 'demo2',
    name: '示例2: 仿真研究',
    description: '研究不同蒙特卡洛重复次数下估计值的收敛特性',
    defaultVariables: ['sampleSize', 'rep']
  },
  {
    id: 'demo3',
    name: '示例3: 计算研究',
    description: '研究不同迭代步长对计算精度和收敛的影响',
    defaultVariables: ['sampleSize', 'step']
  }
]

// 参数定义（硬编码）
const PARAM_DEFINITIONS = [
  { id: 'beta', name: '形状参数', symbol: 'β', chunkKey: 'beta', isVariable: true },
  { id: 'eta', name: '尺度参数', symbol: 'η', chunkKey: 'eta', isVariable: true },
  { id: 'sampleSize', name: '样本量', symbol: 'n', chunkKey: 'n', isVariable: true },
  { id: 'process', name: '偏移量', symbol: 'δ', chunkKey: 'd', isVariable: true }
]

const SIM_CONFIG_DEFINITIONS = [
  { id: 'rep', name: '重复次数', symbol: 'rep', chunkKey: 'rep' },
  { id: 'seed', name: '随机种子', symbol: 'seed', chunkKey: 'seed' }
]

const CALC_CONFIG_DEFINITIONS = [
  { id: 'step', name: '迭代步长', symbol: 'step', chunkKey: 'step' }
]

// 样式常量
const PARAM_COLORS: Record<string, string> = {
  beta: 'border-blue-200 bg-blue-50',
  eta: 'border-emerald-200 bg-emerald-50',
  sampleSize: 'border-purple-200 bg-purple-50',
  process: 'border-rose-200 bg-rose-50',
  rep: 'border-violet-200 bg-violet-50',
  seed: 'border-indigo-200 bg-indigo-50',
  step: 'border-cyan-200 bg-cyan-50'
}

const EST_PARAM_COLORS = {
  beta: { bg: 'bg-blue-100', text: 'text-blue-700', border: 'border-blue-300', color: '#1e40af' },
  eta: { bg: 'bg-emerald-100', text: 'text-emerald-700', border: 'border-emerald-300', color: '#047857' },
  gamma: { bg: 'bg-amber-100', text: 'text-amber-700', border: 'border-amber-300', color: '#b45309' }
}

const BORDER_STYLES = {
  red: 'border-2 border-red-400 bg-red-50 text-red-700',
  green: 'border border-green-300 bg-green-50 text-green-700 cursor-pointer hover:bg-green-100',
  white: 'border border-slate-200 bg-white text-slate-400'
}

const DEFAULT_DISPLAY_OPTIONS = { mean: true, biasMean: true, std: true, ci99: true }
const DEFAULT_PARAM_SELECTION = { beta: true, eta: true, gamma: true }

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

function generateChunkFilename(params: {
  beta: number; eta: number; gamma: number; n: number; d: number; rep: number; seed: number; step: number
}): string {
  const formatBeta = (v: number) => v === Math.floor(v) ? String(v) : String(v)
  const formatOffset = (v: number) => v === 0 ? '0' : String(v)
  return `b${formatBeta(params.beta)}_e${params.eta}_g${params.gamma}_n${params.n}_d${formatOffset(params.d)}_rep${params.rep}_seed${params.seed}_step${params.step}.csv`
}

// ============ Main Component ============

interface MDMStudyViewerProps {
  methodId: string
}

export default function MDMStudyViewer({ methodId }: MDMStudyViewerProps) {
  // Tab 状态
  const [activeTab, setActiveTab] = useState('demo1')

  // Chunk 信息
  const [chunkInfo, setChunkInfo] = useState<ChunkInfo | null>(null)
  const [isLoadingChunks, setIsLoadingChunks] = useState(true)

  // 参数选择状态
  const [paramVariableDimensions, setParamVariableDimensions] = useState<string[]>(['beta', 'sampleSize'])
  const [selectedParamValues, setSelectedParamValues] = useState<Record<string, number[]>>({})

  // 仿真配置状态
  const [simVariableDimensions, setSimVariableDimensions] = useState<string[]>([])
  const [selectedSimValues, setSelectedSimValues] = useState<Record<string, number[]>>({})

  // 计算配置状态
  const [calcVariableDimensions, setCalcVariableDimensions] = useState<string[]>([])
  const [selectedCalcValues, setSelectedCalcValues] = useState<Record<string, number[]>>({})

  // 固定值（非变量维度的值）
  const [fixedValues, setFixedValues] = useState<Record<string, number>>({})

  // CSV 数据
  const [csvData, setCsvData] = useState<SimulationRow[]>([])
  const [isLoadingData, setIsLoadingData] = useState(false)

  // UI 状态
  const [displayOptions] = useState(DEFAULT_DISPLAY_OPTIONS)
  const [paramSelection, setParamSelection] = useState(DEFAULT_PARAM_SELECTION)

  // 当前 Tab
  const currentTab = STUDY_TABS.find(t => t.id === activeTab)!

  // 所有变量维度
  const allVariableDimensions = useMemo(() =>
    [...paramVariableDimensions, ...simVariableDimensions, ...calcVariableDimensions],
    [paramVariableDimensions, simVariableDimensions, calcVariableDimensions]
  )

  // 加载 Chunk 信息
  useEffect(() => {
    const loadChunkInfo = async () => {
      setIsLoadingChunks(true)
      try {
        const res = await fetch(`/api/studies/${methodId.toLowerCase()}/chunks`)
        if (res.ok) {
          const data = await res.json()
          setChunkInfo(data)
          console.log(`[ChunkInfo] ${methodId}: ${data.total} chunks`)
        }
      } catch (err) {
        console.error('Failed to load chunk info:', err)
      }
      setIsLoadingChunks(false)
    }
    loadChunkInfo()
  }, [methodId])

  // 初始化选中值（基于 chunkInfo）
  useEffect(() => {
    if (!chunkInfo?.parsedParams) return

    const pp = chunkInfo.parsedParams

    // 获取第一个可用值作为默认值
    const getFirst = (key: string): number => pp[key]?.[0] ?? 0

    // 根据 Tab 设置默认变量维度
    setParamVariableDimensions([...currentTab.defaultVariables.slice(0, 1)])
    setSimVariableDimensions(currentTab.defaultVariables.includes('rep') ? ['rep'] : [])
    setCalcVariableDimensions(currentTab.defaultVariables.includes('step') ? ['step'] : [])

    // 初始化参数选中值（全选）
    const newSelectedParamValues: Record<string, number[]> = {}
    for (const param of PARAM_DEFINITIONS) {
      const values = pp[param.chunkKey] || []
      if (values.length > 0) {
        newSelectedParamValues[param.id] = values
      }
    }
    setSelectedParamValues(newSelectedParamValues)

    // 初始化仿真配置选中值
    setSelectedSimValues({
      rep: pp.rep || [getFirst('rep')],
      seed: pp.seed || [42]
    })

    // 初始化计算配置选中值
    setSelectedCalcValues({
      step: pp.step || [getFirst('step')]
    })

    // 初始化固定值
    setFixedValues({
      beta: getFirst('beta'),
      eta: getFirst('eta'),
      gamma: getFirst('gamma'),
      n: getFirst('n'),
      d: getFirst('d'),
      rep: getFirst('rep'),
      seed: pp.seed?.[0] ?? 42,
      step: getFirst('step')
    })
  }, [chunkInfo, currentTab])

  // 生成需要加载的 chunk 列表
  const getRequiredChunks = useCallback((): string[] => {
    if (!chunkInfo?.parsedParams) return []

    const getValue = (paramId: string, isVariable: boolean, selectedValues: Record<string, number[]>, chunkKey: string): number[] => {
      if (isVariable) return selectedValues[paramId] || [fixedValues[chunkKey] ?? 0]
      return [fixedValues[chunkKey] ?? 0]
    }

    const isParamVar = (id: string) => paramVariableDimensions.includes(id)
    const isSimVar = (id: string) => simVariableDimensions.includes(id)
    const isCalcVar = (id: string) => calcVariableDimensions.includes(id)

    const betaValues = getValue('beta', isParamVar('beta'), selectedParamValues, 'beta')
    const etaValues = getValue('eta', isParamVar('eta'), selectedParamValues, 'eta')
    const nValues = getValue('sampleSize', isParamVar('sampleSize'), selectedParamValues, 'n')
    const dValues = getValue('process', isParamVar('process'), selectedParamValues, 'd')
    const repValues = getValue('rep', isSimVar('rep'), selectedSimValues, 'rep')
    const seedValues = getValue('seed', isSimVar('seed'), selectedSimValues, 'seed')
    const stepValues = getValue('step', isCalcVar('step'), selectedCalcValues, 'step')
    const gammaValue = fixedValues.gamma ?? 1000

    const chunks: string[] = []
    for (const beta of betaValues) {
      for (const eta of etaValues) {
        for (const n of nValues) {
          for (const d of dValues) {
            for (const rep of repValues) {
              for (const seed of seedValues) {
                for (const step of stepValues) {
                  chunks.push(generateChunkFilename({ beta, eta, gamma: gammaValue, n, d, rep, seed, step }))
                }
              }
            }
          }
        }
      }
    }
    return chunks
  }, [chunkInfo, paramVariableDimensions, simVariableDimensions, calcVariableDimensions,
      selectedParamValues, selectedSimValues, selectedCalcValues, fixedValues])

  // 加载数据
  useEffect(() => {
    if (!chunkInfo) return

    const loadData = async () => {
      setIsLoadingData(true)
      const chunks = getRequiredChunks()

      if (chunks.length === 0) {
        setCsvData([])
        setIsLoadingData(false)
        return
      }

      console.log(`[DataLoader] Loading ${chunks.length} chunks`)

      const basePath = `/studies/${methodId.toLowerCase()}/chunks`
      const results = await Promise.all(
        chunks.map(async (name) => {
          try {
            const res = await fetch(`${basePath}/${name}`)
            if (!res.ok) return []
            const text = await res.text()
            return parseCsv(text)
          } catch {
            return []
          }
        })
      )

      const allData = results.flat()
      console.log(`[DataLoader] Loaded ${allData.length} rows`)
      setCsvData(allData)
      setIsLoadingData(false)
    }

    loadData()
  }, [chunkInfo, getRequiredChunks, methodId])

  // === 参数操作函数 ===

  const handleToggleParamValue = useCallback((paramId: string, value: number) => {
    if (paramVariableDimensions.includes(paramId)) {
      setSelectedParamValues(prev => {
        const current = prev[paramId] || []
        const isSelected = current.includes(value)
        return { ...prev, [paramId]: isSelected ? current.filter(v => v !== value) : [...current, value] }
      })
    } else {
      const param = PARAM_DEFINITIONS.find(p => p.id === paramId)
      if (param) {
        setFixedValues(prev => ({ ...prev, [param.chunkKey]: value }))
      }
    }
  }, [paramVariableDimensions])

  const handleSelectAllParam = useCallback((paramId: string) => {
    const param = PARAM_DEFINITIONS.find(p => p.id === paramId)
    if (param && chunkInfo?.parsedParams) {
      const allValues = chunkInfo.parsedParams[param.chunkKey] || []
      setSelectedParamValues(prev => ({ ...prev, [paramId]: allValues }))
    }
  }, [chunkInfo])

  const handleToggleParamVariableMode = useCallback((paramId: string) => {
    if (paramVariableDimensions.includes(paramId)) {
      setParamVariableDimensions(prev => prev.filter(id => id !== paramId))
      setSelectedParamValues(prev => {
        const { [paramId]: _, ...rest } = prev
        return rest
      })
    } else if (allVariableDimensions.length < 2) {
      setParamVariableDimensions(prev => [...prev, paramId])
      const param = PARAM_DEFINITIONS.find(p => p.id === paramId)
      if (param && chunkInfo?.parsedParams) {
        const allValues = chunkInfo.parsedParams[param.chunkKey] || []
        setSelectedParamValues(prev => ({ ...prev, [paramId]: allValues }))
      }
    }
  }, [paramVariableDimensions, allVariableDimensions, chunkInfo])

  // === 仿真配置操作函数 ===

  const handleToggleSimValue = useCallback((configId: string, value: number) => {
    if (simVariableDimensions.includes(configId)) {
      setSelectedSimValues(prev => {
        const current = prev[configId] || []
        const isSelected = current.includes(value)
        return { ...prev, [configId]: isSelected ? current.filter(v => v !== value) : [...current, value] }
      })
    } else {
      setFixedValues(prev => ({ ...prev, [configId]: value }))
    }
  }, [simVariableDimensions])

  const handleSelectAllSim = useCallback((configId: string) => {
    if (chunkInfo?.parsedParams) {
      const allValues = chunkInfo.parsedParams[configId] || []
      setSelectedSimValues(prev => ({ ...prev, [configId]: allValues }))
    }
  }, [chunkInfo])

  const handleToggleSimVariableMode = useCallback((configId: string) => {
    if (simVariableDimensions.includes(configId)) {
      setSimVariableDimensions(prev => prev.filter(id => id !== configId))
    } else if (allVariableDimensions.length < 2) {
      setSimVariableDimensions(prev => [...prev, configId])
      if (chunkInfo?.parsedParams) {
        const allValues = chunkInfo.parsedParams[configId] || []
        setSelectedSimValues(prev => ({ ...prev, [configId]: allValues }))
      }
    }
  }, [simVariableDimensions, allVariableDimensions, chunkInfo])

  // === 计算配置操作函数 ===

  const handleToggleCalcValue = useCallback((configId: string, value: number) => {
    if (calcVariableDimensions.includes(configId)) {
      setSelectedCalcValues(prev => {
        const current = prev[configId] || []
        const isSelected = current.includes(value)
        return { ...prev, [configId]: isSelected ? current.filter(v => v !== value) : [...current, value] }
      })
    } else {
      setFixedValues(prev => ({ ...prev, [configId]: value }))
    }
  }, [calcVariableDimensions])

  const handleSelectAllCalc = useCallback((configId: string) => {
    if (chunkInfo?.parsedParams) {
      const allValues = chunkInfo.parsedParams[configId] || []
      setSelectedCalcValues(prev => ({ ...prev, [configId]: allValues }))
    }
  }, [chunkInfo])

  const handleToggleCalcVariableMode = useCallback((configId: string) => {
    if (calcVariableDimensions.includes(configId)) {
      setCalcVariableDimensions(prev => prev.filter(id => id !== configId))
    } else if (allVariableDimensions.length < 2) {
      setCalcVariableDimensions(prev => [...prev, configId])
      if (chunkInfo?.parsedParams) {
        const allValues = chunkInfo.parsedParams[configId] || []
        setSelectedCalcValues(prev => ({ ...prev, [configId]: allValues }))
      }
    }
  }, [calcVariableDimensions, allVariableDimensions, chunkInfo])

  // === 三色边框逻辑 ===

  const getParamBorderState = useCallback((paramId: string, value: number): 'red' | 'green' | 'white' => {
    const param = PARAM_DEFINITIONS.find(p => p.id === paramId)
    if (!param || !chunkInfo?.chunks) return 'white'

    const isVariable = paramVariableDimensions.includes(paramId)
    const selectedVals = selectedParamValues[paramId] || []
    const fixedVal = fixedValues[param.chunkKey]

    const isSelected = isVariable
      ? selectedVals.includes(value)
      : fixedVal === value

    if (isSelected) return 'red'

    // 检查兼容性
    const getVal = (pId: string, testValue?: number): number => {
      const p = PARAM_DEFINITIONS.find(x => x.id === pId)
      if (!p) return 0
      if (pId === paramId && testValue !== undefined) return testValue
      if (paramVariableDimensions.includes(pId)) {
        const vals = selectedParamValues[pId]
        if (vals && vals.length > 0) return vals[0]
      }
      return fixedValues[p.chunkKey] ?? 0
    }

    const testParams = {
      beta: getVal('beta', value),
      eta: getVal('eta', value),
      gamma: fixedValues.gamma ?? 1000,
      n: getVal('sampleSize', value),
      d: getVal('process', value),
      rep: fixedValues.rep ?? 1000,
      seed: fixedValues.seed ?? 42,
      step: fixedValues.step ?? 60
    }

    const chunkName = generateChunkFilename(testParams)
    return chunkInfo.chunks.includes(chunkName) ? 'green' : 'white'
  }, [paramVariableDimensions, selectedParamValues, fixedValues, chunkInfo])

  const getConfigBorderState = useCallback((
    configId: string, value: number, type: 'sim' | 'calc'
  ): 'red' | 'green' | 'white' => {
    const isVariable = type === 'sim'
      ? simVariableDimensions.includes(configId)
      : calcVariableDimensions.includes(configId)

    const selectedVals = type === 'sim'
      ? selectedSimValues[configId] || []
      : selectedCalcValues[configId] || []
    const fixedVal = fixedValues[configId]

    const isSelected = isVariable
      ? selectedVals.includes(value)
      : fixedVal === value

    if (isSelected) return 'red'

    const availableValues = chunkInfo?.parsedParams?.[configId] || []
    if (availableValues.length <= 1) return 'white'

    return availableValues.includes(value) ? 'green' : 'white'
  }, [simVariableDimensions, calcVariableDimensions, selectedSimValues, selectedCalcValues, fixedValues, chunkInfo])

  // === 统计计算 ===

  const stats = useMemo(() => {
    if (csvData.length === 0) return []

    const groups = new Map<string, SimulationRow[]>()

    csvData.forEach(row => {
      const keyParts: string[] = []
      paramVariableDimensions.forEach(dim => {
        if (dim === 'beta') keyParts.push(`β=${row.beta_true}`)
        if (dim === 'eta') keyParts.push(`η=${row.eta_true}`)
        if (dim === 'sampleSize') keyParts.push(`n=${row.sample_size}`)
        if (dim === 'process') keyParts.push(`δ=${row.offset_value}`)
      })
      const key = keyParts.join(', ') || 'all'
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key)!.push(row)
    })

    return Array.from(groups.entries()).map(([key, rows]): StatsResult => {
      const validRows = rows.filter(r => r.est_beta !== null && r.est_eta !== null && r.est_gamma !== null)
      const betaTrue = rows[0].beta_true ?? 2.0
      const etaTrue = rows[0].eta_true ?? 1000
      const gammaTrue = fixedValues.gamma ?? 1000

      const calcStats = (values: number[]) => {
        if (values.length === 0) return { mean: null, std: null, min: null, max: null, p005: null, p995: null }
        const sorted = [...values].sort((a, b) => a - b)
        const n = sorted.length
        const mean = values.reduce((a, b) => a + b, 0) / n
        const std = Math.sqrt(values.reduce((s, v) => s + (v - mean) ** 2, 0) / n)
        const quantile = (q: number) => {
          const pos = (n - 1) * q
          const base = Math.floor(pos)
          return sorted[base + 1] !== undefined ? sorted[base] + (pos - base) * (sorted[base + 1] - sorted[base]) : sorted[base]
        }
        return { mean, std, min: sorted[0], max: sorted[n - 1], p005: quantile(0.005), p995: quantile(0.995) }
      }

      const betaStats = calcStats(validRows.map(r => r.est_beta!))
      const etaStats = calcStats(validRows.map(r => r.est_eta!))
      const gammaStats = calcStats(validRows.map(r => r.est_gamma!))

      return {
        key, keyLabel: key,
        beta_true: betaTrue, eta_true: etaTrue, gamma_true: gammaTrue,
        count: rows.length, valid_count: validRows.length,
        est_beta_mean: betaStats.mean, bias_beta_mean: betaStats.mean !== null ? betaStats.mean - betaTrue : null,
        est_beta_std: betaStats.std, est_beta_min: betaStats.min, est_beta_max: betaStats.max,
        est_beta_p005: betaStats.p005, est_beta_p995: betaStats.p995,
        est_eta_mean: etaStats.mean, bias_eta_mean: etaStats.mean !== null ? etaStats.mean - etaTrue : null,
        est_eta_std: etaStats.std, est_eta_min: etaStats.min, est_eta_max: etaStats.max,
        est_eta_p005: etaStats.p005, est_eta_p995: etaStats.p995,
        est_gamma_mean: gammaStats.mean, bias_gamma_mean: gammaStats.mean !== null ? gammaStats.mean - gammaTrue : null,
        est_gamma_std: gammaStats.std, est_gamma_min: gammaStats.min, est_gamma_max: gammaStats.max,
        est_gamma_p005: gammaStats.p005, est_gamma_p995: gammaStats.p995
      }
    })
  }, [csvData, paramVariableDimensions, fixedValues])

  // === 渲染 ===

  if (isLoadingChunks) {
    return <div className="flex justify-center items-center p-12"><div className="animate-spin rounded-full h-8 w-8 border-2 border-orange-500 border-t-transparent"></div></div>
  }

  return (
    <div className="space-y-6">
      {/* Tab 导航 */}
      <div className="bg-white p-2 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex gap-1">
          {STUDY_TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex-1 px-4 py-2.5 rounded-xl text-sm font-bold transition-all",
                activeTab === tab.id
                  ? "bg-orange-500 text-white shadow-sm"
                  : "text-slate-600 hover:bg-slate-100"
              )}
            >
              {tab.name}
            </button>
          ))}
        </div>
        <p className="text-xs text-slate-500 text-center mt-2">{currentTab.description}</p>
      </div>

      {/* 参数配置 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Settings className="text-slate-600" size={20} />
            <h3 className="text-lg font-bold text-slate-800">参数配置</h3>
          </div>
          <div className="text-sm text-slate-500">
            变量: <span className="font-bold text-purple-600">{allVariableDimensions.length}</span>/2
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {PARAM_DEFINITIONS.map(param => {
            const chunkValues = chunkInfo?.parsedParams?.[param.chunkKey] || []
            return (
              <ConfigCard
                key={param.id}
                id={param.id}
                name={param.name}
                symbol={param.symbol}
                values={chunkValues}
                isVariable={param.isVariable}
                isVariableDimension={paramVariableDimensions.includes(param.id)}
                canAddVariable={allVariableDimensions.length < 2}
                getBorderState={(v) => getParamBorderState(param.id, v as number)}
                onToggleValue={(v) => handleToggleParamValue(param.id, v as number)}
                onSelectAll={() => handleSelectAllParam(param.id)}
                onToggleVariableMode={() => handleToggleParamVariableMode(param.id)}
              />
            )
          })}
        </div>
      </div>

      {/* 仿真与计算配置 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 仿真配置 */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <FlaskConical className="text-violet-600" size={20} />
            <h3 className="text-lg font-bold text-slate-800">仿真配置</h3>
          </div>
          <div className="grid grid-cols-2 gap-4">
            {SIM_CONFIG_DEFINITIONS.map(config => (
              <ConfigCard
                key={config.id}
                id={config.id}
                name={config.name}
                symbol={config.symbol}
                values={chunkInfo?.parsedParams?.[config.chunkKey] || [fixedValues[config.id] ?? 0]}
                isVariable={true}
                isVariableDimension={simVariableDimensions.includes(config.id)}
                canAddVariable={allVariableDimensions.length < 2}
                getBorderState={(v) => getConfigBorderState(config.id, v as number, 'sim')}
                onToggleValue={(v) => handleToggleSimValue(config.id, v as number)}
                onSelectAll={() => handleSelectAllSim(config.id)}
                onToggleVariableMode={() => handleToggleSimVariableMode(config.id)}
              />
            ))}
          </div>
        </div>

        {/* 计算配置 */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <Settings className="text-cyan-600" size={20} />
            <h3 className="text-lg font-bold text-slate-800">计算配置</h3>
          </div>
          <div className="grid grid-cols-1 gap-4">
            {CALC_CONFIG_DEFINITIONS.map(config => (
              <ConfigCard
                key={config.id}
                id={config.id}
                name={config.name}
                symbol={config.symbol}
                values={chunkInfo?.parsedParams?.[config.chunkKey] || [fixedValues[config.id] ?? 0]}
                isVariable={true}
                isVariableDimension={calcVariableDimensions.includes(config.id)}
                canAddVariable={allVariableDimensions.length < 2}
                getBorderState={(v) => getConfigBorderState(config.id, v as number, 'calc')}
                onToggleValue={(v) => handleToggleCalcValue(config.id, v as number)}
                onSelectAll={() => handleSelectAllCalc(config.id)}
                onToggleVariableMode={() => handleToggleCalcVariableMode(config.id)}
              />
            ))}
          </div>
        </div>
      </div>

      {/* 加载状态 */}
      {isLoadingData && (
        <div className="flex justify-center items-center p-8">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-orange-500 border-t-transparent"></div>
          <span className="ml-3 text-slate-600">加载数据...</span>
        </div>
      )}

      {/* 统计结果 */}
      {!isLoadingData && stats.length > 0 && (
        <ResultsSection
          stats={stats}
          variableDimensions={paramVariableDimensions}
          displayOptions={displayOptions}
          paramSelection={paramSelection}
          setParamSelection={setParamSelection}
          fixedValues={fixedValues}
        />
      )}

      {/* 无数据提示 */}
      {!isLoadingData && stats.length === 0 && csvData.length === 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 text-center">
          <p className="text-amber-700">当前配置没有对应的数据文件</p>
          <p className="text-sm text-amber-600 mt-1">请调整参数或生成对应的数据</p>
        </div>
      )}
    </div>
  )
}

// ============ Sub Components ============

function ConfigCard({
  id, name, symbol, values, isVariable, isVariableDimension, canAddVariable,
  getBorderState, onToggleValue, onSelectAll, onToggleVariableMode
}: {
  id: string
  name: string
  symbol: string
  values: number[]
  isVariable: boolean
  isVariableDimension: boolean
  canAddVariable: boolean
  getBorderState: (value: number | string) => 'red' | 'green' | 'white'
  onToggleValue: (value: number | string) => void
  onSelectAll: () => void
  onToggleVariableMode: () => void
}) {
  const formatValue = (v: number | string) => {
    if (typeof v === 'string') return v
    if (typeof v === 'number' && v < 1 && v !== 0) return v.toFixed(2)
    if (v >= 1000) return `${v/1000}k`
    if (Number.isInteger(v)) return String(v)
    return String(v)
  }

  return (
    <div className={cn("rounded-xl border-2 p-3 transition-all", PARAM_COLORS[id] || 'border-slate-200 bg-slate-50')}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1">
          <span className="text-sm font-bold">{name}</span>
          <span className="text-xs font-mono text-slate-500">{symbol}</span>
        </div>
        <div className={cn(
          "px-2 py-0.5 rounded text-xs font-bold",
          isVariableDimension ? "bg-purple-600 text-white" :
          isVariable ? "bg-white text-purple-700 border border-purple-200" : "bg-slate-200 text-slate-500"
        )}>
          {isVariableDimension ? "变量" : isVariable ? "可选" : "固定"}
        </div>
      </div>

      <div className="flex flex-wrap gap-1">
        {values.map(v => {
          const state = getBorderState(v)
          const isClickable = state !== 'white'
          return (
            <span
              key={v}
              onClick={() => isClickable && onToggleValue(v)}
              className={cn(
                "px-1.5 py-0.5 rounded text-xs font-mono font-bold transition-all",
                BORDER_STYLES[state],
                isClickable && "cursor-pointer"
              )}
            >
              {formatValue(v)}
            </span>
          )
        })}
      </div>

      {isVariable && (
        <div className="mt-2 pt-2 border-t border-slate-200 flex gap-2">
          {isVariableDimension && (
            <button onClick={onSelectAll} className="flex-1 text-xs font-bold text-slate-500 hover:text-slate-700 py-1 rounded hover:bg-slate-100">
              全选
            </button>
          )}
          <button
            onClick={onToggleVariableMode}
            disabled={!isVariableDimension && !canAddVariable}
            className={cn(
              "flex-1 text-xs font-bold py-1 rounded transition-all",
              isVariableDimension ? "bg-purple-600 text-white hover:bg-purple-700" :
              canAddVariable ? "text-slate-500 hover:text-slate-700 hover:bg-slate-100" :
              "text-slate-300 cursor-not-allowed"
            )}
          >
            {isVariableDimension ? "取消变量" : "设为变量"}
          </button>
        </div>
      )}
    </div>
  )
}

function ResultsSection({
  stats, variableDimensions, displayOptions, paramSelection, setParamSelection, fixedValues
}: {
  stats: StatsResult[]
  variableDimensions: string[]
  displayOptions: { mean: boolean; biasMean: boolean; std: boolean; ci99: boolean }
  paramSelection: { beta: boolean; eta: boolean; gamma: boolean }
  setParamSelection: (v: { beta: boolean; eta: boolean; gamma: boolean }) => void
  fixedValues: Record<string, number>
}) {
  const fmt = (v: number | string | null | undefined, d = 2) => {
    if (v === null || v === undefined) return '—'
    if (typeof v === 'string') return v
    return v.toFixed(d)
  }
  const selectedParams = Object.entries(paramSelection).filter(([_, s]) => s).map(([k]) => k as 'beta' | 'eta' | 'gamma')

  return (
    <div className="space-y-6">
      {/* 表格 */}
      <div className="bg-white border border-slate-300 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-base font-semibold text-slate-700">表: 参数估计汇总统计</p>
          <div className="flex gap-2">
            {(['beta', 'eta', 'gamma'] as const).map(p => (
              <button
                key={p}
                onClick={() => setParamSelection({ ...paramSelection, [p]: !paramSelection[p] })}
                className={cn(
                  "px-2 py-1 rounded text-xs font-bold transition-all",
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
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse min-w-[600px]">
            <thead>
              <tr className="border-b-2 border-slate-400">
                <th className="py-2 px-2 font-bold text-slate-800 sticky left-0 bg-white">配置</th>
                <th className="py-2 px-2 font-bold text-slate-800">参数</th>
                <th className="py-2 px-2 font-bold text-slate-800 text-right">真实值</th>
                {displayOptions.mean && <th className="py-2 px-2 font-bold text-slate-800 text-right">均值</th>}
                {displayOptions.biasMean && <th className="py-2 px-2 font-bold text-slate-800 text-right">偏差</th>}
                {displayOptions.std && <th className="py-2 px-2 font-bold text-slate-800 text-right">SD</th>}
                {displayOptions.ci99 && <th className="py-2 px-2 font-bold text-slate-800 text-right">99% CI</th>}
              </tr>
            </thead>
            <tbody>
              {stats.map((s, idx) => (
                <React.Fragment key={idx}>
                  {selectedParams.includes('beta') && (
                    <tr className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                      <td className="py-1.5 px-2 font-mono text-slate-700 border-b border-slate-200" rowSpan={selectedParams.length}>{s.keyLabel}</td>
                      <td className={cn("py-1.5 px-2 font-bold text-center border-b border-slate-200", EST_PARAM_COLORS.beta.text)}>β</td>
                      <td className="py-1.5 px-2 font-mono text-slate-700 text-right border-b border-slate-200">{s.beta_true}</td>
                      {displayOptions.mean && <td className="py-1.5 px-2 font-mono text-slate-700 text-right border-b border-slate-200">{fmt(s.est_beta_mean, 4)}</td>}
                      {displayOptions.biasMean && <td className={cn("py-1.5 px-2 font-mono text-right border-b border-slate-200", (typeof s.bias_beta_mean === 'number' ? s.bias_beta_mean : 0) > 0 ? 'text-red-600' : 'text-blue-600')}>{fmt(s.bias_beta_mean, 4)}</td>}
                      {displayOptions.std && <td className="py-1.5 px-2 font-mono text-slate-700 text-right border-b border-slate-200">{fmt(s.est_beta_std, 4)}</td>}
                      {displayOptions.ci99 && <td className="py-1.5 px-2 font-mono text-slate-700 text-right border-b border-slate-200 text-xs">[{fmt(s.est_beta_p005)}, {fmt(s.est_beta_p995)}]</td>}
                    </tr>
                  )}
                  {selectedParams.includes('eta') && (
                    <tr className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                      <td className={cn("py-1.5 px-2 font-bold text-center border-b border-slate-200", EST_PARAM_COLORS.eta.text)}>η</td>
                      <td className="py-1.5 px-2 font-mono text-slate-700 text-right border-b border-slate-200">{s.eta_true}</td>
                      {displayOptions.mean && <td className="py-1.5 px-2 font-mono text-slate-700 text-right border-b border-slate-200">{fmt(s.est_eta_mean, 2)}</td>}
                      {displayOptions.biasMean && <td className={cn("py-1.5 px-2 font-mono text-right border-b border-slate-200", (typeof s.bias_eta_mean === 'number' ? s.bias_eta_mean : 0) > 0 ? 'text-red-600' : 'text-blue-600')}>{fmt(s.bias_eta_mean, 2)}</td>}
                      {displayOptions.std && <td className="py-1.5 px-2 font-mono text-slate-700 text-right border-b border-slate-200">{fmt(s.est_eta_std, 2)}</td>}
                      {displayOptions.ci99 && <td className="py-1.5 px-2 font-mono text-slate-700 text-right border-b border-slate-200 text-xs">[{fmt(s.est_eta_p005)}, {fmt(s.est_eta_p995)}]</td>}
                    </tr>
                  )}
                  {selectedParams.includes('gamma') && (
                    <tr className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                      <td className={cn("py-1.5 px-2 font-bold text-center border-b border-slate-200", EST_PARAM_COLORS.gamma.text)}>γ</td>
                      <td className="py-1.5 px-2 font-mono text-slate-700 text-right border-b border-slate-200">{s.gamma_true}</td>
                      {displayOptions.mean && <td className="py-1.5 px-2 font-mono text-slate-700 text-right border-b border-slate-200">{fmt(s.est_gamma_mean, 2)}</td>}
                      {displayOptions.biasMean && <td className={cn("py-1.5 px-2 font-mono text-right border-b border-slate-200", (typeof s.bias_gamma_mean === 'number' ? s.bias_gamma_mean : 0) > 0 ? 'text-red-600' : 'text-blue-600')}>{fmt(s.bias_gamma_mean, 2)}</td>}
                      {displayOptions.std && <td className="py-1.5 px-2 font-mono text-slate-700 text-right border-b border-slate-200">{fmt(s.est_gamma_std, 2)}</td>}
                      {displayOptions.ci99 && <td className="py-1.5 px-2 font-mono text-slate-700 text-right border-b border-slate-200 text-xs">[{fmt(s.est_gamma_p005)}, {fmt(s.est_gamma_p995)}]</td>}
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 单变量：箱型图 */}
      {variableDimensions.length === 1 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {selectedParams.map((param, idx) => {
            const minKey = `est_${param}_min` as keyof StatsResult
            const maxKey = `est_${param}_max` as keyof StatsResult
            const p01Key = `est_${param}_p005` as keyof StatsResult
            const p99Key = `est_${param}_p995` as keyof StatsResult
            const medianKey = `est_${param}_mean` as keyof StatsResult
            const trueKey = `${param}_true` as keyof typeof fixedValues
            return (
              <ChartCard key={param} title={`图 ${idx + 1}: ${param}估计值分布`}>
                <BoxPlotChart
                  data={stats}
                  dataKeyMin={minKey as string}
                  dataKeyMax={maxKey as string}
                  dataKeyP01={p01Key as string}
                  dataKeyP99={p99Key as string}
                  dataKeyMedian={medianKey as string}
                  color={EST_PARAM_COLORS[param].color}
                  yLabel={`${param}估计值`}
                  xLabel={variableDimensions[0] === 'sampleSize' ? 'n' : variableDimensions[0]}
                  trueValue={fixedValues[trueKey] ?? (param === 'beta' ? 2.0 : param === 'eta' ? 1000 : 1000)}
                />
              </ChartCard>
            )
          })}
        </div>
      )}

      {/* 双变量：热力图 */}
      {variableDimensions.length === 2 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {selectedParams.map((param, idx) => {
            const allValues = stats.map(s => s[`bias_${param}_mean` as keyof StatsResult]).filter((v): v is number => v !== null)
            const maxAbs = Math.max(...allValues.map(Math.abs), 0.01)
            return (
              <ChartCard key={param} title={`图 ${idx + 1}: ${param}偏差热力图`}>
                <HeatmapChart
                  stats={stats}
                  displayDimensions={variableDimensions.map(v => ({ id: v, name: v, symbol: v === 'sampleSize' ? 'n' : v }))}
                  dataKey={`bias_${param}_mean`}
                  maxAbs={maxAbs}
                />
              </ChartCard>
            )
          })}
        </div>
      )}
    </div>
  )
}
