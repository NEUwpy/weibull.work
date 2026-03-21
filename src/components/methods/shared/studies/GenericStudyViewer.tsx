"use client"

import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { FlaskConical, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ChartCard, BoxPlotChart, HeatmapChart, DensityChart } from '@/components/shared/charts'

// ============ Types ============

interface SimulationRow {
  [key: string]: number | string | null | undefined
  beta_true: number
  eta_true: number
  gamma?: number          // 统一使用 gamma
  sample_size: number
  offset_value?: number    // MDM 有此列
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
  gamma?: number
  offset_value?: number   // MDM 额外参数
  rep: number | null
  step: number | null
  sample_size?: number
  count: number
  valid_count: number
  [key: string]: number | string | null | undefined
}

interface ChunkInfo {
  chunks: string[]
  parsedParams: Record<string, number[]>
  total: number
}

// 参数定义接口
interface ParamDefinition {
  id: string
  name: string
  symbol: string
  chunkKey: string
  isVariable: boolean  // 是否可以作为变量维度
  isFixed?: boolean    // 是否固定（如gamma）
}

// ============ 默认参数定义 ============

// 标准参数：β, η, γ（固定）, n
const DEFAULT_PARAM_DEFINITIONS: ParamDefinition[] = [
  { id: 'beta', name: '形状参数', symbol: 'β', chunkKey: 'beta', isVariable: true },
  { id: 'eta', name: '尺度参数', symbol: 'η', chunkKey: 'eta', isVariable: true },
  { id: 'gamma', name: '位置参数', symbol: 'γ', chunkKey: 'gamma', isVariable: false, isFixed: true },
  { id: 'sampleSize', name: '样本量', symbol: 'n', chunkKey: 'n', isVariable: true }
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
  gamma: 'border-amber-200 bg-amber-50',
  sampleSize: 'border-purple-200 bg-purple-50',
  offset: 'border-rose-200 bg-rose-50',
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
  red: 'border border-red-400 bg-red-50 text-red-700',
  green: 'border border-green-300 bg-green-50 text-green-700 cursor-pointer hover:bg-green-100',
  white: 'border border-slate-200 bg-white text-slate-400'
}

const DEFAULT_DISPLAY_OPTIONS = { mean: true, biasMean: true, std: true, ci99: true }
const DEFAULT_PARAM_SELECTION = { beta: true, eta: true, gamma: true }

// 默认值
const PRESET_DEFAULTS = {
  beta: 2.0,
  eta: 1000,
  gamma: 1000,
  n: 7,
  d: 0.1,     // MDM 偏移量默认值
  rep: 1000,
  seed: 42,
  step: 60
}

// Tab配置
const STUDY_TABS = [
  {
    id: 'demo1',
    name: '示例1: 参数研究',
    description: '研究不同形状参数、尺度参数、样本量对估计结果的影响',
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

// ============ Utility Functions ============

function parseCsv(text: string): SimulationRow[] {
  const lines = text.trim().split('\n')
  if (lines.length < 2) return []

  const headers = lines[0].split(',')
  const rows: SimulationRow[] = []

  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',')
    const parseVal = (key: string) => {
      const idx = headers.indexOf(key)
      if (idx === -1) return null
      const v = values[idx]
      if (!v || v === 'NaN' || v === 'nan') return null
      const n = parseFloat(v)
      return isNaN(n) ? null : n
    }

    const parseValWithDefault = (key: string, defaultVal: number): number => {
      const idx = headers.indexOf(key)
      if (idx === -1) return defaultVal
      const v = values[idx]
      if (!v || v === 'NaN' || v === 'nan') return defaultVal
      const n = parseFloat(v)
      return isNaN(n) ? defaultVal : n
    }

    const row: SimulationRow = {
      beta_true: parseValWithDefault('beta_true', 0),
      eta_true: parseValWithDefault('eta_true', 0),
      sample_size: parseInt(values[headers.indexOf('sample_size')] || '0'),
      sim_id: parseInt(values[headers.indexOf('sim_id')] || '0'),
      est_beta: parseVal('est_beta'),
      est_eta: parseVal('est_eta'),
      est_gamma: parseVal('est_gamma'),
      bias_beta: parseVal('bias_beta'),
      bias_eta: parseVal('bias_eta'),
      bias_gamma: parseVal('bias_gamma'),
      r_squared: parseVal('r_squared')
    }

    // 可选列：gamma (MLE/WMLE) 或 offset_value (MDM)
    const gammaVal = parseVal('gamma')
    if (gammaVal !== null) row.gamma = gammaVal

    const offsetValue = parseVal('offset_value')
    if (offsetValue !== null) row.offset_value = offsetValue

    rows.push(row)
  }
  return rows
}

// 生成chunk文件名
function generateChunkFilename(params: Record<string, number>, extraKeys: string[] = []): string {
  const parts: string[] = []

  // 固定顺序：b, e, g, n, 然后是额外参数, 然后是 rep, seed, step
  if (params.beta !== undefined) parts.push(`b${params.beta}`)
  if (params.eta !== undefined) parts.push(`e${params.eta}`)
  if (params.gamma !== undefined) parts.push(`g${params.gamma}`)
  if (params.n !== undefined) parts.push(`n${params.n}`)

  // 额外参数（如MDM的d）
  for (const key of extraKeys) {
    if (params[key] !== undefined) {
      parts.push(`${key}${params[key]}`)
    }
  }

  if (params.rep !== undefined) parts.push(`rep${params.rep}`)
  if (params.seed !== undefined) parts.push(`seed${params.seed}`)
  if (params.step !== undefined) parts.push(`step${params.step}`)

  return `${parts.join('_')}.csv`
}

// ============ Main Component ============

interface GenericStudyViewerProps {
  methodId: string
  extraParamDefs?: ParamDefinition[]  // 额外参数定义（如MDM的偏移量）
  extraChunkKeys?: string[]           // 额外参数在chunk文件名中的key
}

export default function GenericStudyViewer({
  methodId,
  extraParamDefs: rawExtraParamDefs,
  extraChunkKeys: rawExtraChunkKeys
}: GenericStudyViewerProps) {
  // 稳定化 props，避免每次渲染创建新数组导致 useMemo 失效
  const extraParamDefs = rawExtraParamDefs ?? []
  const extraChunkKeys = rawExtraChunkKeys ?? []

  // 使用 JSON.stringify 来稳定化依赖
  const extraParamDefsKey = JSON.stringify(extraParamDefs)
  const extraChunkKeysKey = JSON.stringify(extraChunkKeys)

  // 合并参数定义
  const paramDefinitions = useMemo(() => {
    // 在sampleSize后面插入额外参数
    const base = [...DEFAULT_PARAM_DEFINITIONS]
    const insertIdx = base.findIndex(p => p.id === 'sampleSize') + 1
    base.splice(insertIdx, 0, ...extraParamDefs)
    return base
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extraParamDefsKey])

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

  // 固定值
  const [fixedValues, setFixedValues] = useState<Record<string, number>>({})

  // CSV 数据
  const [csvData, setCsvData] = useState<SimulationRow[]>([])
  const [isLoadingData, setIsLoadingData] = useState(false)

  // Chunk 加载信息
  const [loadedChunks, setLoadedChunks] = useState<Array<{ filename: string; rowCount: number; success: boolean }>>([])

  // UI 状态
  const [displayOptions] = useState(DEFAULT_DISPLAY_OPTIONS)
  const [paramSelection, setParamSelection] = useState(DEFAULT_PARAM_SELECTION)
  const [densityTab, setDensityTab] = useState<'beta' | 'eta' | 'gamma'>('beta')

  const currentTab = STUDY_TABS.find(t => t.id === activeTab)!

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
        }
      } catch (err) {
        console.error('Failed to load chunk info:', err)
      }
      setIsLoadingChunks(false)
    }
    loadChunkInfo()
  }, [methodId])

  // 初始化选中值
  useEffect(() => {
    if (!chunkInfo?.parsedParams) return

    const pp = chunkInfo.parsedParams

    // 根据 Tab 设置默认变量维度
    setParamVariableDimensions(currentTab.defaultVariables.filter(v => ['beta', 'eta', 'sampleSize', ...extraParamDefs.map(p => p.id)].includes(v)))
    setSimVariableDimensions(currentTab.defaultVariables.includes('rep') ? ['rep'] : [])
    setCalcVariableDimensions(currentTab.defaultVariables.includes('step') ? ['step'] : [])

    // 查找一个合理的初始 chunk：优先选择 beta=2, eta=1000 的组合（标准参数，数据覆盖完整）
    // 如果找不到，则使用第一个 chunk
    const findInitialChunk = (): Record<string, number> | null => {
      // 解析函数（内联定义，避免依赖外部 useCallback）
      const parseFn = (filename: string): Record<string, number> | null => {
        const name = filename.replace('.csv', '')
        const parts = name.split('_')
        const params: Record<string, number> = {}
        for (const part of parts) {
          if (part.match(/^b[\d.]+$/)) params.beta = parseFloat(part.slice(1))
          else if (part.match(/^e[\d.]+$/)) params.eta = parseFloat(part.slice(1))
          else if (part.match(/^g[\d.]+$/)) params.gamma = parseFloat(part.slice(1))
          else if (part.match(/^n\d+$/)) params.n = parseInt(part.slice(1))
          else if (part.match(/^d[\d.]+$/)) params.d = parseFloat(part.slice(1))
          else if (part.match(/^rep\d+$/)) params.rep = parseInt(part.slice(3))
          else if (part.match(/^seed\d+$/)) params.seed = parseInt(part.slice(4))
          else if (part.match(/^step\d+$/)) params.step = parseInt(part.slice(4))
        }
        return Object.keys(params).length > 0 ? params : null
      }

      // 优先找 beta=2, eta=1000 的文件
      for (const chunk of chunkInfo.chunks) {
        const params = parseFn(chunk)
        if (params && params.beta === 2 && params.eta === 1000) {
          return params
        }
      }
      // 找不到则用第一个
      return chunkInfo.chunks.length > 0 ? parseFn(chunkInfo.chunks[0]) : null
    }

    const initialChunkParams = findInitialChunk()

    // 初始化选中值 - 优先使用找到的 chunk 的参数
    const newSelected: Record<string, number[]> = {}
    for (const param of paramDefinitions) {
      const values = pp[param.chunkKey] || []
      const chunkValue = initialChunkParams?.[param.chunkKey]
      if (chunkValue !== undefined && values.includes(chunkValue)) {
        newSelected[param.id] = [chunkValue]
      } else {
        newSelected[param.id] = values.length > 0 ? [values[0]] : []
      }
    }
    setSelectedParamValues(newSelected)

    setSelectedSimValues({
      rep: initialChunkParams?.rep ? [initialChunkParams.rep] : (pp.rep || [PRESET_DEFAULTS.rep]),
      seed: initialChunkParams?.seed ? [initialChunkParams.seed] : (pp.seed || [PRESET_DEFAULTS.seed])
    })

    setSelectedCalcValues({
      step: initialChunkParams?.step ? [initialChunkParams.step] : (pp.step || [PRESET_DEFAULTS.step])
    })

    // 初始化 fixedValues - 优先使用找到的 chunk 的参数
    const initialFixed: Record<string, number> = {
      beta: initialChunkParams?.beta ?? pp.beta?.[0] ?? PRESET_DEFAULTS.beta,
      eta: initialChunkParams?.eta ?? pp.eta?.[0] ?? PRESET_DEFAULTS.eta,
      gamma: initialChunkParams?.gamma ?? pp.gamma?.[0] ?? PRESET_DEFAULTS.gamma,
      n: initialChunkParams?.n ?? pp.n?.[0] ?? PRESET_DEFAULTS.n,
      rep: initialChunkParams?.rep ?? pp.rep?.[0] ?? PRESET_DEFAULTS.rep,
      seed: initialChunkParams?.seed ?? pp.seed?.[0] ?? PRESET_DEFAULTS.seed,
      step: initialChunkParams?.step ?? pp.step?.[0] ?? PRESET_DEFAULTS.step
    }
    // 添加额外参数的初始值（如MDM的d/offset）
    for (const param of extraParamDefs) {
      initialFixed[param.chunkKey] = initialChunkParams?.[param.chunkKey] ?? pp[param.chunkKey]?.[0] ?? (PRESET_DEFAULTS as Record<string, number>)[param.chunkKey] ?? 0
    }
    setFixedValues(initialFixed)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chunkInfo, currentTab, paramDefinitions, extraParamDefsKey])

  // 生成需要加载的 chunk 列表
  const getRequiredChunks = useCallback((): string[] => {
    if (!chunkInfo?.parsedParams) return []

    const getValue = (paramId: string, isVariable: boolean, selected: Record<string, number[]>, chunkKey: string): number[] => {
      if (isVariable) return selected[paramId] || [fixedValues[chunkKey] ?? 0]
      return [fixedValues[chunkKey] ?? 0]
    }

    const isParamVar = (id: string) => paramVariableDimensions.includes(id)
    const isSimVar = (id: string) => simVariableDimensions.includes(id)
    const isCalcVar = (id: string) => calcVariableDimensions.includes(id)

    const chunks: string[] = []
    const betaValues = getValue('beta', isParamVar('beta'), selectedParamValues, 'beta')
    const etaValues = getValue('eta', isParamVar('eta'), selectedParamValues, 'eta')
    const nValues = getValue('sampleSize', isParamVar('sampleSize'), selectedParamValues, 'n')
    const repValues = getValue('rep', isSimVar('rep'), selectedSimValues, 'rep')
    const seedValues = getValue('seed', isSimVar('seed'), selectedSimValues, 'seed')
    const stepValues = getValue('step', isCalcVar('step'), selectedCalcValues, 'step')
    const gammaValue = fixedValues.gamma ?? 1000

    // 获取额外参数的值
    const extraParamValues: Record<string, number[]> = {}
    for (const param of extraParamDefs) {
      extraParamValues[param.chunkKey] = getValue(param.id, isParamVar(param.id), selectedParamValues, param.chunkKey)
    }

    for (const beta of betaValues) {
      for (const eta of etaValues) {
        for (const n of nValues) {
          for (const rep of repValues) {
            for (const seed of seedValues) {
              for (const step of stepValues) {
                const params: Record<string, number> = { beta, eta, gamma: gammaValue, n, rep, seed, step }

                // 添加额外参数（先处理第一个额外参数的多值情况）
                for (const param of extraParamDefs) {
                  const vals = extraParamValues[param.chunkKey]
                  if (vals && vals.length > 0) {
                    params[param.chunkKey] = vals[0]
                  }
                }

                chunks.push(generateChunkFilename(params, extraChunkKeys))
              }
            }
          }
        }
      }
    }
    return chunks
  }, [chunkInfo, paramVariableDimensions, simVariableDimensions, calcVariableDimensions,
      selectedParamValues, selectedSimValues, selectedCalcValues, fixedValues, extraParamDefsKey, extraChunkKeysKey])

  // 解析chunk文件名
  const parseChunkParams = useCallback((filename: string): Record<string, number> | null => {
    const name = filename.replace('.csv', '')
    const parts = name.split('_')
    const params: Record<string, number> = {}
    for (const part of parts) {
      if (part.match(/^b[\d.]+$/)) params.beta = parseFloat(part.slice(1))
      else if (part.match(/^e[\d.]+$/)) params.eta = parseFloat(part.slice(1))
      else if (part.match(/^g[\d.]+$/)) params.gamma = parseFloat(part.slice(1))
      else if (part.match(/^n\d+$/)) params.n = parseInt(part.slice(1))
      else if (part.match(/^d[\d.]+$/)) params.d = parseFloat(part.slice(1))
      else if (part.match(/^rep\d+$/)) params.rep = parseInt(part.slice(3))
      else if (part.match(/^seed\d+$/)) params.seed = parseInt(part.slice(4))
      else if (part.match(/^step\d+$/)) params.step = parseInt(part.slice(4))
    }
    return Object.keys(params).length > 0 ? params : null
  }, [])

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

      const basePath = `/studies/${methodId.toLowerCase()}/chunks`
      const results = await Promise.all(
        chunks.map(async (name) => {
          try {
            const res = await fetch(`${basePath}/${name}`)
            if (!res.ok) return { data: [], filename: name, success: false }
            const text = await res.text()
            const data = parseCsv(text)
            return { data, filename: name, success: data.length > 0 }
          } catch {
            return { data: [], filename: name, success: false }
          }
        })
      )

      const allData = results.flatMap(r => r.data)
      const chunkInfoList = results.map(r => ({ filename: r.filename, rowCount: r.data.length, success: r.success }))
      setCsvData(allData)
      setLoadedChunks(chunkInfoList)
      setIsLoadingData(false)
    }

    loadData()
  }, [chunkInfo, getRequiredChunks, methodId])

  // 参数操作函数
  const handleToggleParamValue = useCallback((paramId: string, value: number) => {
    if (paramVariableDimensions.includes(paramId)) {
      setSelectedParamValues(prev => {
        const current = prev[paramId] || []
        const isSelected = current.includes(value)
        return { ...prev, [paramId]: isSelected ? current.filter(v => v !== value) : [...current, value] }
      })
    } else {
      const param = paramDefinitions.find(p => p.id === paramId)
      if (param) {
        setFixedValues(prev => ({ ...prev, [param.chunkKey]: value }))
      }
    }
  }, [paramVariableDimensions, paramDefinitions])

  const handleSelectAllParam = useCallback((paramId: string) => {
    const param = paramDefinitions.find(p => p.id === paramId)
    if (param && chunkInfo?.parsedParams) {
      const allValues = chunkInfo.parsedParams[param.chunkKey] || []
      setSelectedParamValues(prev => ({ ...prev, [paramId]: allValues }))
    }
  }, [chunkInfo, paramDefinitions])

  const handleToggleParamVariableMode = useCallback((paramId: string) => {
    if (paramVariableDimensions.includes(paramId)) {
      setParamVariableDimensions(prev => prev.filter(id => id !== paramId))
      setSelectedParamValues(prev => {
        const { [paramId]: _, ...rest } = prev
        return rest
      })
    } else if (allVariableDimensions.length < 2) {
      setParamVariableDimensions(prev => [...prev, paramId])
      const param = paramDefinitions.find(p => p.id === paramId)
      if (param && chunkInfo?.chunks) {
        // 只选择在当前约束下有对应算例的值
        const availableValues = new Set<number>()
        for (const chunkName of chunkInfo.chunks) {
          const chunkParams = parseChunkParams(chunkName)
          if (!chunkParams || chunkParams[param.chunkKey] === undefined) continue

          // 检查其他参数约束
          let matches = true
          for (const p of paramDefinitions) {
            if (p.id === paramId) continue // 跳过当前参数
            if (paramVariableDimensions.includes(p.id)) {
              const selected = selectedParamValues[p.id] || []
              if (selected.length > 0 && !selected.includes(chunkParams[p.chunkKey]!)) {
                matches = false
                break
              }
            } else if (p.id !== paramId) {
              const fixed = fixedValues[p.chunkKey]
              if (fixed !== undefined && chunkParams[p.chunkKey] !== fixed) {
                matches = false
                break
              }
            }
          }
          if (matches) {
            availableValues.add(chunkParams[param.chunkKey]!)
          }
        }
        setSelectedParamValues(prev => ({ ...prev, [paramId]: Array.from(availableValues).sort((a, b) => a - b) }))
      }
    }
  }, [paramVariableDimensions, allVariableDimensions, chunkInfo, paramDefinitions, parseChunkParams, selectedParamValues, fixedValues])

  // 仿真配置操作函数
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

  const handleToggleSimVariableMode = useCallback((configId: string) => {
    if (simVariableDimensions.includes(configId)) {
      setSimVariableDimensions(prev => prev.filter(id => id !== configId))
      setSelectedSimValues(prev => {
        const { [configId]: _, ...rest } = prev
        return rest
      })
    } else if (allVariableDimensions.length < 2) {
      setSimVariableDimensions(prev => [...prev, configId])
      if (chunkInfo?.chunks) {
        // 只选择在当前约束下有对应算例的值
        const availableValues = new Set<number>()
        for (const chunkName of chunkInfo.chunks) {
          const chunkParams = parseChunkParams(chunkName)
          if (!chunkParams || chunkParams[configId] === undefined) continue

          // 检查参数约束
          let matches = true
          for (const p of paramDefinitions) {
            if (paramVariableDimensions.includes(p.id)) {
              const selected = selectedParamValues[p.id] || []
              if (selected.length > 0 && !selected.includes(chunkParams[p.chunkKey]!)) {
                matches = false
                break
              }
            } else {
              const fixed = fixedValues[p.chunkKey]
              if (fixed !== undefined && chunkParams[p.chunkKey] !== fixed) {
                matches = false
                break
              }
            }
          }
          if (matches) {
            availableValues.add(chunkParams[configId]!)
          }
        }
        setSelectedSimValues(prev => ({ ...prev, [configId]: Array.from(availableValues).sort((a, b) => a - b) }))
      }
    }
  }, [simVariableDimensions, allVariableDimensions, chunkInfo, parseChunkParams, paramDefinitions, paramVariableDimensions, selectedParamValues, fixedValues])

  // 计算配置操作函数
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

  const handleToggleCalcVariableMode = useCallback((configId: string) => {
    if (calcVariableDimensions.includes(configId)) {
      setCalcVariableDimensions(prev => prev.filter(id => id !== configId))
      setSelectedCalcValues(prev => {
        const { [configId]: _, ...rest } = prev
        return rest
      })
    } else if (allVariableDimensions.length < 2) {
      setCalcVariableDimensions(prev => [...prev, configId])
      if (chunkInfo?.chunks) {
        // 只选择在当前约束下有对应算例的值
        const availableValues = new Set<number>()
        for (const chunkName of chunkInfo.chunks) {
          const chunkParams = parseChunkParams(chunkName)
          if (!chunkParams || chunkParams[configId] === undefined) continue

          // 检查参数约束
          let matches = true
          for (const p of paramDefinitions) {
            if (paramVariableDimensions.includes(p.id)) {
              const selected = selectedParamValues[p.id] || []
              if (selected.length > 0 && !selected.includes(chunkParams[p.chunkKey]!)) {
                matches = false
                break
              }
            } else {
              const fixed = fixedValues[p.chunkKey]
              if (fixed !== undefined && chunkParams[p.chunkKey] !== fixed) {
                matches = false
                break
              }
            }
          }
          if (matches) {
            availableValues.add(chunkParams[configId]!)
          }
        }
        setSelectedCalcValues(prev => ({ ...prev, [configId]: Array.from(availableValues).sort((a, b) => a - b) }))
      }
    }
  }, [calcVariableDimensions, allVariableDimensions, chunkInfo, parseChunkParams, paramDefinitions, paramVariableDimensions, selectedParamValues, fixedValues])

  // 三色边框逻辑
  const getParamBorderState = useCallback((paramId: string, value: number): 'red' | 'green' | 'white' => {
    const param = paramDefinitions.find(p => p.id === paramId)
    if (!param || !chunkInfo?.chunks) return 'white'

    const isVariable = paramVariableDimensions.includes(paramId)
    const selectedVals = selectedParamValues[paramId] || []
    const fixedVal = fixedValues[param.chunkKey]

    const isSelected = isVariable ? selectedVals.includes(value) : fixedVal === value
    if (isSelected) return 'red'

    // 绿色检查：需要结合已选参数的约束
    const chunkKey = param.chunkKey
    return chunkInfo.chunks.some(chunkName => {
      const chunkParams = parseChunkParams(chunkName)
      if (!chunkParams || chunkParams[chunkKey] !== value) return false

      // 检查所有固定值是否匹配
      for (const p of paramDefinitions) {
        if (p.id === paramId) continue // 跳过当前检查的参数
        if (paramVariableDimensions.includes(p.id)) {
          // 变量维度：chunkParams 需要在已选值中
          const selected = selectedParamValues[p.id] || []
          if (selected.length > 0 && !selected.includes(chunkParams[p.chunkKey]!)) {
            return false
          }
        } else {
          // 固定维度：chunkParams 需要等于 fixedValue
          const fixed = fixedValues[p.chunkKey]
          if (fixed !== undefined && chunkParams[p.chunkKey] !== fixed) {
            return false
          }
        }
      }
      return true
    }) ? 'green' : 'white'
  }, [paramVariableDimensions, selectedParamValues, fixedValues, chunkInfo, parseChunkParams, paramDefinitions])

  const getConfigBorderState = useCallback((
    configId: string, value: number, type: 'sim' | 'calc'
  ): 'red' | 'green' | 'white' => {
    if (!chunkInfo?.chunks) return 'white'

    const isVariable = type === 'sim'
      ? simVariableDimensions.includes(configId)
      : calcVariableDimensions.includes(configId)

    const selectedVals = type === 'sim'
      ? selectedSimValues[configId] || []
      : selectedCalcValues[configId] || []
    const fixedVal = fixedValues[configId]

    const isSelected = isVariable ? selectedVals.includes(value) : fixedVal === value
    if (isSelected) return 'red'

    // 绿色检查：需要结合已选参数的约束
    return chunkInfo.chunks.some(chunkName => {
      const chunkParams = parseChunkParams(chunkName)
      if (!chunkParams || chunkParams[configId] !== value) return false

      // 检查所有参数维度的约束
      for (const p of paramDefinitions) {
        if (paramVariableDimensions.includes(p.id)) {
          const selected = selectedParamValues[p.id] || []
          if (selected.length > 0 && !selected.includes(chunkParams[p.chunkKey]!)) {
            return false
          }
        } else {
          const fixed = fixedValues[p.chunkKey]
          if (fixed !== undefined && chunkParams[p.chunkKey] !== fixed) {
            return false
          }
        }
      }

      // 检查其他仿真/计算配置的约束
      if (type === 'sim') {
        // 检查其他仿真配置（变量维度）
        for (const dim of simVariableDimensions) {
          if (dim === configId) continue
          const selected = selectedSimValues[dim] || []
          if (selected.length > 0 && !selected.includes(chunkParams[dim]!)) {
            return false
          }
        }
        // 检查计算配置（固定维度用fixedValue，变量维度用已选值）
        // rep, seed, step 这些配置不一定是变量，需要根据当前状态判断
        if (!calcVariableDimensions.includes('step')) {
          const fixed = fixedValues['step']
          if (fixed !== undefined && chunkParams['step'] !== fixed) {
            return false
          }
        } else if (configId !== 'step') {
          const selected = selectedCalcValues['step'] || []
          if (selected.length > 0 && !selected.includes(chunkParams['step']!)) {
            return false
          }
        }
      } else {
        // 检查其他计算配置（变量维度）
        for (const dim of calcVariableDimensions) {
          if (dim === configId) continue
          const selected = selectedCalcValues[dim] || []
          if (selected.length > 0 && !selected.includes(chunkParams[dim]!)) {
            return false
          }
        }
        // 检查仿真配置（固定维度用fixedValue，变量维度用已选值）
        for (const dim of ['rep', 'seed'] as const) {
          if (configId === dim) continue
          if (!simVariableDimensions.includes(dim)) {
            const fixed = fixedValues[dim]
            if (fixed !== undefined && chunkParams[dim] !== fixed) {
              return false
            }
          } else {
            const selected = selectedSimValues[dim] || []
            if (selected.length > 0 && !selected.includes(chunkParams[dim]!)) {
              return false
            }
          }
        }
      }

      return true
    }) ? 'green' : 'white'
  }, [simVariableDimensions, calcVariableDimensions, selectedSimValues, selectedCalcValues, fixedValues, chunkInfo, parseChunkParams, paramDefinitions, selectedParamValues, paramVariableDimensions])

  // 带参数信息的数据行
  interface EnrichedRow {
    row: SimulationRow
    rep: number | null
    step: number | null
  }

  const enrichedCsvData = useMemo((): EnrichedRow[] => {
    if (!loadedChunks.length || csvData.length === 0) {
      return csvData.map(row => ({ row, rep: null, step: null }))
    }

    const result: EnrichedRow[] = []
    let rowIndex = 0

    for (const chunk of loadedChunks) {
      if (!chunk.success) continue
      const params = parseChunkParams(chunk.filename)
      const rowCount = chunk.rowCount

      for (let i = 0; i < rowCount && rowIndex < csvData.length; i++) {
        result.push({
          row: csvData[rowIndex],
          rep: params?.rep ?? null,
          step: params?.step ?? null
        })
        rowIndex++
      }
    }
    return result
  }, [csvData, loadedChunks, parseChunkParams])

  // 统计计算
  const stats = useMemo(() => {
    if (enrichedCsvData.length === 0) return []

    const groups = new Map<string, EnrichedRow[]>()

    enrichedCsvData.forEach(enrichedRow => {
      const row = enrichedRow.row
      const keyParts: string[] = []
      paramVariableDimensions.forEach(dim => {
        if (dim === 'beta') keyParts.push(`β=${row.beta_true}`)
        if (dim === 'eta') keyParts.push(`η=${row.eta_true}`)
        if (dim === 'sampleSize') keyParts.push(`n=${row.sample_size}`)
        // 处理额外参数（如MDM的offset）
        const extraParam = extraParamDefs.find(p => p.id === dim)
        if (extraParam && extraParam.chunkKey === 'd' && row.offset_value !== undefined) {
          keyParts.push(`δ=${row.offset_value}`)
        }
      })
      simVariableDimensions.forEach(dim => {
        if (dim === 'rep' && enrichedRow.rep !== null) keyParts.push(`rep=${enrichedRow.rep}`)
      })
      calcVariableDimensions.forEach(dim => {
        if (dim === 'step' && enrichedRow.step !== null) keyParts.push(`step=${enrichedRow.step}`)
      })
      const key = keyParts.join(', ') || 'all'
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key)!.push(enrichedRow)
    })

    return Array.from(groups.entries()).map(([key, rows]): StatsResult => {
      const dataRows = rows.map(r => r.row)
      const validRows = dataRows.filter(r => r.est_beta !== null && r.est_eta !== null && r.est_gamma !== null)
      const betaTrue = dataRows[0].beta_true ?? 2.0
      const etaTrue = dataRows[0].eta_true ?? 1000
      // gamma 优先从CSV获取，否则使用 fixedValues
      const gammaVal = dataRows[0].gamma ?? fixedValues.gamma ?? 1000
      // 获取额外参数值（如MDM的offset_value）
      const offsetValue = dataRows[0].offset_value

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

      const repValue = rows[0].rep
      const stepValue = rows[0].step

      return {
        key, keyLabel: key,
        beta_true: betaTrue, eta_true: etaTrue, gamma: gammaVal,
        offset_value: offsetValue,
        rep: repValue, step: stepValue,
        sample_size: dataRows[0].sample_size,
        count: rows.length, valid_count: validRows.length,
        est_beta_mean: betaStats.mean, bias_beta_mean: betaStats.mean !== null ? betaStats.mean - betaTrue : null,
        est_beta_std: betaStats.std, est_beta_min: betaStats.min, est_beta_max: betaStats.max,
        est_beta_p005: betaStats.p005, est_beta_p995: betaStats.p995,
        est_eta_mean: etaStats.mean, bias_eta_mean: etaStats.mean !== null ? etaStats.mean - etaTrue : null,
        est_eta_std: etaStats.std, est_eta_min: etaStats.min, est_eta_max: etaStats.max,
        est_eta_p005: etaStats.p005, est_eta_p995: etaStats.p995,
        est_gamma_mean: gammaStats.mean, bias_gamma_mean: gammaStats.mean !== null ? gammaStats.mean - gammaVal : null,
        est_gamma_std: gammaStats.std, est_gamma_min: gammaStats.min, est_gamma_max: gammaStats.max,
        est_gamma_p005: gammaStats.p005, est_gamma_p995: gammaStats.p995
      }
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enrichedCsvData, paramVariableDimensions, simVariableDimensions, calcVariableDimensions, fixedValues, extraParamDefsKey])

  // 渲染
  if (isLoadingChunks) {
    return <div className="flex justify-center items-center p-12"><div className="animate-spin rounded-full h-8 w-8 border-2 border-orange-500 border-t-transparent"></div></div>
  }

  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-r from-slate-50 to-white p-1 rounded-2xl shadow-sm">
        <div className="flex gap-1">
          {STUDY_TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex-1 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200",
                activeTab === tab.id
                  ? "bg-white text-slate-800 shadow-md ring-1 ring-slate-200"
                  : "text-slate-500 hover:text-slate-700 hover:bg-white/50"
              )}
            >
              {tab.name}
            </button>
          ))}
        </div>
        <p className="text-xs text-slate-400 text-center mt-3 mb-1">{currentTab.description}</p>
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

        <div className="flex flex-wrap gap-3">
          {paramDefinitions.map(param => {
            const chunkValues = chunkInfo?.parsedParams?.[param.chunkKey] || []
            const isSingleValue = chunkValues.length <= 1
            return (
              <div key={param.id} className={cn("flex flex-col", isSingleValue ? "flex-shrink-0 min-w-[100px]" : "flex-1 min-w-[140px]")}>
                <ConfigCard
                  id={param.id}
                  name={param.name}
                  symbol={param.symbol}
                  values={chunkValues}
                  isVariable={param.isVariable && !param.isFixed}
                  isVariableDimension={paramVariableDimensions.includes(param.id)}
                  canAddVariable={allVariableDimensions.length < 2}
                  getBorderState={(v) => getParamBorderState(param.id, v as number)}
                  onToggleValue={(v) => handleToggleParamValue(param.id, v as number)}
                  onSelectAll={() => handleSelectAllParam(param.id)}
                  onToggleVariableMode={() => handleToggleParamVariableMode(param.id)}
                />
              </div>
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
                onSelectAll={() => {}}
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
                onSelectAll={() => {}}
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
          allVariableDimensions={allVariableDimensions}
          displayOptions={displayOptions}
          paramSelection={paramSelection}
          setParamSelection={setParamSelection}
          fixedValues={fixedValues}
          csvData={csvData}
          densityTab={densityTab}
          setDensityTab={setDensityTab}
        />
      )}

      {/* 无数据提示 */}
      {!isLoadingData && stats.length === 0 && csvData.length === 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 text-center">
          <p className="text-amber-700">当前配置没有对应的数据文件</p>
          <p className="text-sm text-amber-600 mt-1">请调整参数或生成对应的数据</p>
        </div>
      )}

      {/* Chunk 数据来源信息 */}
      {loadedChunks.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <p className="text-base font-semibold text-slate-700">数据来源</p>
            <p className="text-xs text-slate-500">
              共 {loadedChunks.length} 个分片，{loadedChunks.filter(c => c.success).length} 个加载成功
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b-2 border-slate-300">
                  <th className="py-2 px-3 font-bold text-slate-700 text-left w-12">#</th>
                  <th className="py-2 px-3 font-bold text-slate-700 text-left">文件名</th>
                  <th className="py-2 px-3 font-bold text-slate-700 text-right w-28">数据规模</th>
                </tr>
              </thead>
              <tbody>
                {loadedChunks.map((chunk, idx) => (
                  <tr key={chunk.filename} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                    <td className="py-1.5 px-3 text-slate-500 font-mono">{idx + 1}</td>
                    <td className="py-1.5 px-3 font-mono text-xs text-slate-600">{chunk.filename}</td>
                    <td className={cn(
                      "py-1.5 px-3 text-right font-mono",
                      chunk.success ? "text-slate-700" : "text-red-500"
                    )}>
                      {chunk.success ? `${chunk.rowCount} 行` : '加载失败'}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-slate-300 bg-slate-100">
                  <td className="py-2 px-3 font-bold text-slate-700" colSpan={2}>合计</td>
                  <td className="py-2 px-3 text-right font-bold font-mono text-slate-700">
                    {loadedChunks.reduce((sum, c) => sum + c.rowCount, 0)} 行
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
    <div className={cn("rounded-xl border-2 p-3 transition-all h-full flex flex-col", PARAM_COLORS[id] || 'border-slate-200 bg-slate-50')}>
      <div className="flex items-center justify-between mb-2 min-h-[28px]">
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

      <div className="flex flex-wrap gap-1 flex-1 content-start">
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

      <div className="mt-auto pt-2 border-t border-slate-200/50 flex gap-2 min-h-[36px]">
        {isVariable ? (
          <>
            {isVariableDimension && (
              <button onClick={onSelectAll} className="flex-1 text-xs font-bold text-slate-500 hover:text-slate-700 py-1.5 rounded hover:bg-slate-100">
                全选
              </button>
            )}
            <button
              onClick={onToggleVariableMode}
              disabled={!isVariableDimension && !canAddVariable}
              className={cn(
                "flex-1 text-xs font-bold py-1.5 rounded transition-all",
                isVariableDimension ? "bg-purple-600 text-white hover:bg-purple-700" :
                canAddVariable ? "text-slate-500 hover:text-slate-700 hover:bg-slate-100" :
                "text-slate-300 cursor-not-allowed"
              )}
            >
              {isVariableDimension ? "取消变量" : "设为变量"}
            </button>
          </>
        ) : (
          <div className="flex-1" />
        )}
      </div>
    </div>
  )
}

function ResultsSection({
  stats, variableDimensions, allVariableDimensions, displayOptions, paramSelection, setParamSelection, fixedValues,
  csvData, densityTab, setDensityTab
}: {
  stats: StatsResult[]
  variableDimensions: string[]
  allVariableDimensions: string[]
  displayOptions: { mean: boolean; biasMean: boolean; std: boolean; ci99: boolean }
  paramSelection: { beta: boolean; eta: boolean; gamma: boolean }
  setParamSelection: (v: { beta: boolean; eta: boolean; gamma: boolean }) => void
  fixedValues: Record<string, number>
  csvData: SimulationRow[]
  densityTab: 'beta' | 'eta' | 'gamma'
  setDensityTab: (v: 'beta' | 'eta' | 'gamma') => void
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
                      <td className="py-1.5 px-2 font-mono text-slate-700 text-right border-b border-slate-200">{s.gamma}</td>
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
      {allVariableDimensions.length === 1 && (
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
                  xLabel={allVariableDimensions[0] === 'sampleSize' ? 'n' : allVariableDimensions[0]}
                  trueValue={fixedValues[trueKey] ?? (param === 'beta' ? 2.0 : param === 'eta' ? 1000 : 1000)}
                />
              </ChartCard>
            )
          })}
        </div>
      )}

      {/* 双变量：热力图 */}
      {allVariableDimensions.length === 2 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {selectedParams.map((param, idx) => {
            const allValues = stats.map(s => s[`bias_${param}_mean` as keyof StatsResult]).filter((v): v is number => v !== null)
            const maxAbs = Math.max(...allValues.map(Math.abs), 0.01)
            const dimSymbols: Record<string, string> = { sampleSize: 'n', beta: 'β', eta: 'η', rep: 'rep', step: 'step' }
            return (
              <ChartCard key={param} title={`图 ${idx + 1}: ${param}偏差热力图`}>
                <HeatmapChart
                  stats={stats}
                  displayDimensions={allVariableDimensions.map(v => ({ id: v, name: v, symbol: dimSymbols[v] || v }))}
                  dataKey={`bias_${param}_mean`}
                  maxAbs={maxAbs}
                />
              </ChartCard>
            )
          })}
        </div>
      )}

      {/* 概率密度分布图 */}
      {csvData.length > 0 && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-slate-800">参数估计值概率密度分布</h3>
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
          <DensityChart
            rawData={csvData}
            paramId={densityTab}
            displayDimension={{
              id: variableDimensions[0] || 'sampleSize',
              name: variableDimensions[0] === 'sampleSize' ? '样本量' : variableDimensions[0],
              symbol: variableDimensions[0] === 'sampleSize' ? 'n' : variableDimensions[0]
            }}
            trueValue={fixedValues[densityTab] ?? (densityTab === 'beta' ? 2.0 : densityTab === 'eta' ? 1000 : 1000)}
            color={densityTab === 'beta' ? 'blue' : densityTab === 'eta' ? 'emerald' : 'amber'}
          />
        </div>
      )}
    </div>
  )
}
