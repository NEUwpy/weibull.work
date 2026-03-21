"use client"

import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { FlaskConical, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ChartCard, BoxPlotChart, HeatmapChart, DensityChart } from '@/components/shared/charts'

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
  rep: number | null
  step: number | null
  sample_size?: number
  offset_value?: number
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
  { id: 'gamma', name: '位置参数', symbol: 'γ', chunkKey: 'gamma', isVariable: false },
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
  gamma: 'border-amber-200 bg-amber-50',
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
  red: 'border border-red-400 bg-red-50 text-red-700',
  green: 'border border-green-300 bg-green-50 text-green-700 cursor-pointer hover:bg-green-100',
  white: 'border border-slate-200 bg-white text-slate-400'
}

const DEFAULT_DISPLAY_OPTIONS = { mean: true, biasMean: true, std: true, ci99: true }
const DEFAULT_PARAM_SELECTION = { beta: true, eta: true, gamma: true }

// 预设的"推荐"默认值（用于初始化和找不到 chunk 时的回退）
const PRESET_DEFAULTS = {
  beta: 2.0,
  eta: 1000,
  gamma: 1000,
  n: 7,
  d: 0.1,
  rep: 1000,
  seed: 42,
  step: 60
}

// 各 Tab 的推荐配置（用于变量选择后的固定值推断）
const TAB_PRESET_CONFIGS: Record<string, Partial<typeof PRESET_DEFAULTS>> = {
  demo1: { beta: 2.0, eta: 1000, n: 7, d: 0.1, rep: 1000 },
  demo2: { beta: 2.0, eta: 1000, d: 0.1, rep: 5000 },  // 示例2重点看 rep 影响
  demo3: { beta: 2.0, eta: 1000, d: 0.1, step: 60 }
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

  // Chunk 加载信息（用于底部表格显示）
  const [loadedChunks, setLoadedChunks] = useState<Array<{ filename: string; rowCount: number; success: boolean }>>([])

  // UI 状态
  const [displayOptions] = useState(DEFAULT_DISPLAY_OPTIONS)
  const [paramSelection, setParamSelection] = useState(DEFAULT_PARAM_SELECTION)
  const [densityTab, setDensityTab] = useState<'beta' | 'eta' | 'gamma'>('beta')

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
    if (!chunkInfo?.parsedParams || !chunkInfo?.chunks) return

    const pp = chunkInfo.parsedParams

    // 获取 Tab 特定的预设配置
    const presetConfig = TAB_PRESET_CONFIGS[currentTab.id] || {}

    // 根据 Tab 设置默认变量维度
    const paramVarDims = [...currentTab.defaultVariables.slice(0, 1)]
    const simVarDims = currentTab.defaultVariables.includes('rep') ? ['rep'] : []
    const calcVarDims = currentTab.defaultVariables.includes('step') ? ['step'] : []

    setParamVariableDimensions(paramVarDims)
    setSimVariableDimensions(simVarDims)
    setCalcVariableDimensions(calcVarDims)

    // 解析所有 chunk 文件名，获取参数组合
    const parseChunk = (filename: string): Record<string, number> | null => {
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

    const allChunks = chunkInfo.chunks.map(parseChunk).filter(Boolean) as Record<string, number>[]

    // 计算各参数在所有 chunks 中的可用值（用于非变量维度）
    const getAvailableValues = (key: string): number[] => {
      const values = new Set<number>()
      for (const chunk of allChunks) {
        if (chunk[key] !== undefined) values.add(chunk[key])
      }
      return Array.from(values).sort((a, b) => a - b)
    }

    // 对于变量维度，计算与预设配置兼容的值
    const getCompatibleValues = (paramKey: string, excludeKeys: string[] = []): number[] => {
      const compatible: number[] = []
      const values = getAvailableValues(paramKey)
      for (const v of values) {
        // 检查是否存在包含该值的 chunk，且该 chunk 的其他参数与预设兼容
        const hasCompatible = allChunks.some(chunk => {
          if (chunk[paramKey] !== v) return false
          // 检查预设的其他固定值（排除其他变量维度）
          for (const [key, val] of Object.entries(presetConfig)) {
            if (key === paramKey || excludeKeys.includes(key)) continue
            if (chunk[key] !== undefined && chunk[key] !== val) return false
          }
          return true
        })
        if (hasCompatible) compatible.push(v)
      }
      return compatible
    }

    // 计算多个变量维度的交集（用于初始化）
    // 先计算每个变量维度的兼容值，然后取交集
    const computeVariableIntersections = () => {
      // 1. 先计算 rep 变量的兼容值
      let repCompatible: number[] = []
      if (simVarDims.includes('rep')) {
        repCompatible = getCompatibleValues('rep', [])
      }

      // 2. 计算其他参数变量的兼容值（基于 rep 兼容值）
      const paramCompatible: Record<string, number[]> = {}
      for (const param of PARAM_DEFINITIONS) {
        if (!paramVarDims.includes(param.id)) continue
        const key = param.chunkKey
        // 如果 rep 是变量，需要计算与 repCompatible 的交集
        if (repCompatible.length > 0) {
          const intersection: number[] = []
          for (const v of getAvailableValues(key)) {
            // 检查该值是否与所有 rep 兼容值都有对应的 chunk
            const compatibleWithAllRep = repCompatible.every(r =>
              allChunks.some(chunk =>
                chunk[key] === v &&
                chunk.rep === r &&
                Object.entries(presetConfig).every(([k, val]) =>
                  k === key || k === 'rep' || chunk[k] === val
                )
              )
            )
            if (compatibleWithAllRep) intersection.push(v)
          }
          paramCompatible[param.id] = intersection
        } else {
          paramCompatible[param.id] = getCompatibleValues(key, ['rep'])
        }
      }

      // 3. 如果 sampleSize 也是变量，重新计算 rep 的交集
      if (paramCompatible.sampleSize && paramCompatible.sampleSize.length > 0) {
        const nValues = paramCompatible.sampleSize
        repCompatible = repCompatible.filter(r =>
          nValues.every(n =>
            allChunks.some(chunk =>
              chunk.rep === r &&
              chunk.n === n &&
              Object.entries(presetConfig).every(([k, val]) =>
                k === 'rep' || k === 'n' || chunk[k] === val
              )
            )
          )
        )
      }

      return { repCompatible, paramCompatible }
    }

    const { repCompatible, paramCompatible } = computeVariableIntersections()

    // 计算非变量维度的兼容值（与所有变量维度的交集兼容）
    const getNonVarCompatibleValues = (paramKey: string): number[] => {
      const allValues = getAvailableValues(paramKey)
      const compatible: number[] = []

      // 获取所有变量维度的选中值组合
      const varCombos: Array<Record<string, number>> = []

      // 生成 rep 变量的值组合
      const repValues = repCompatible.length > 0 ? repCompatible : getAvailableValues('rep')
      // 生成 sampleSize 变量的值组合
      const nValues = paramCompatible.sampleSize || getAvailableValues('n')

      // 如果 rep 和 sampleSize 都是变量，生成笛卡尔积
      for (const r of repValues) {
        for (const n of nValues) {
          varCombos.push({ rep: r, n })
        }
      }

      // 如果没有变量组合，只检查与 presetConfig 的兼容性
      if (varCombos.length === 0) {
        return allValues.filter(v => {
          return allChunks.some(chunk =>
            chunk[paramKey] === v &&
            Object.entries(presetConfig).every(([k, val]) =>
              k === paramKey || chunk[k] === val
            )
          )
        })
      }

      // 对于每个值，检查是否与所有变量组合都兼容
      for (const v of allValues) {
        const isCompatibleWithAll = varCombos.every(combo => {
          return allChunks.some(chunk =>
            chunk[paramKey] === v &&
            chunk.rep === combo.rep &&
            chunk.n === combo.n &&
            // 检查与 presetConfig 的兼容性（排除 rep 和 n）
            Object.entries(presetConfig).every(([k, val]) =>
              k === paramKey || k === 'rep' || k === 'n' || chunk[k] === val
            )
          )
        })
        if (isCompatibleWithAll) compatible.push(v)
      }

      return compatible
    }

    // 初始化参数选中值
    const newSelectedParamValues: Record<string, number[]> = {}
    for (const param of PARAM_DEFINITIONS) {
      const key = param.chunkKey
      const isVar = paramVarDims.includes(param.id)
      const presetVal = presetConfig[key as keyof typeof presetConfig]

      if (isVar) {
        // 变量维度：使用计算出的交集
        newSelectedParamValues[param.id] = paramCompatible[param.id] || getAvailableValues(key)
      } else {
        // 非变量维度：使用与变量兼容的值，优先使用预设值
        const compatible = getNonVarCompatibleValues(key)
        if (presetVal !== undefined && compatible.includes(presetVal)) {
          newSelectedParamValues[param.id] = [presetVal]
        } else if (compatible.length > 0) {
          newSelectedParamValues[param.id] = [compatible[0]]
        } else {
          // 如果没有兼容值，使用预设值或第一个可用值
          const available = getAvailableValues(key)
          if (presetVal !== undefined && available.includes(presetVal)) {
            newSelectedParamValues[param.id] = [presetVal]
          } else {
            newSelectedParamValues[param.id] = available.length > 0 ? [available[0]] : []
          }
        }
      }
    }
    setSelectedParamValues(newSelectedParamValues)

    // 初始化仿真配置选中值
    const repAvailable = getAvailableValues('rep')
    const repPreset = presetConfig.rep
    const repIsVar = simVarDims.includes('rep')

    let repValues: number[]
    if (repIsVar) {
      // 变量维度：使用计算出的交集
      repValues = repCompatible.length > 0 ? repCompatible : repAvailable
    } else {
      repValues = repPreset !== undefined && repAvailable.includes(repPreset) ? [repPreset] : repAvailable
    }

    setSelectedSimValues({
      rep: repValues,
      seed: [PRESET_DEFAULTS.seed]
    })

    // 初始化计算配置选中值
    const stepAvailable = getAvailableValues('step')
    const stepPreset = presetConfig.step
    setSelectedCalcValues({
      step: stepPreset !== undefined && stepAvailable.includes(stepPreset) ? [stepPreset] : stepAvailable
    })

    // 初始化固定值（使用预设配置中的第一个兼容 chunk 的值）
    const firstCompatible = allChunks.find(chunk =>
      Object.entries(presetConfig).every(([k, v]) => chunk[k] === v)
    ) || allChunks[0]

    if (firstCompatible) {
      setFixedValues({
        beta: firstCompatible.beta ?? presetConfig.beta ?? PRESET_DEFAULTS.beta,
        eta: firstCompatible.eta ?? presetConfig.eta ?? PRESET_DEFAULTS.eta,
        gamma: firstCompatible.gamma ?? PRESET_DEFAULTS.gamma,
        n: firstCompatible.n ?? presetConfig.n ?? PRESET_DEFAULTS.n,
        d: firstCompatible.d ?? presetConfig.d ?? PRESET_DEFAULTS.d,
        rep: firstCompatible.rep ?? presetConfig.rep ?? PRESET_DEFAULTS.rep,
        seed: firstCompatible.seed ?? PRESET_DEFAULTS.seed,
        step: firstCompatible.step ?? presetConfig.step ?? PRESET_DEFAULTS.step
      })
    }
  }, [chunkInfo, currentTab])

  // 当变量选择变化时，推断并更新固定值（从匹配的 chunks 中提取）
  useEffect(() => {
    if (!chunkInfo?.chunks || !chunkInfo?.parsedParams) return

    // 获取当前 Tab 的预设配置
    const presetConfig = TAB_PRESET_CONFIGS[currentTab.id] || {}

    // 解析所有 chunk 文件名，获取参数组合
    const parseChunk = (filename: string): Record<string, number> | null => {
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

    const allChunks = chunkInfo.chunks.map(parseChunk).filter(Boolean) as Record<string, number>[]

    // 根据当前变量选择，筛选匹配的 chunks
    const matchingChunks = allChunks.filter(chunk => {
      // 检查参数变量
      for (const dim of paramVariableDimensions) {
        const param = PARAM_DEFINITIONS.find(p => p.id === dim)
        if (!param) continue
        const key = param.chunkKey
        const selected = selectedParamValues[dim] || []
        if (selected.length > 0 && !selected.includes(chunk[key])) return false
      }
      // 检查仿真配置变量
      for (const dim of simVariableDimensions) {
        const selected = selectedSimValues[dim] || []
        if (selected.length > 0 && !selected.includes(chunk[dim])) return false
      }
      // 检查计算配置变量
      for (const dim of calcVariableDimensions) {
        const selected = selectedCalcValues[dim] || []
        if (selected.length > 0 && !selected.includes(chunk[dim])) return false
      }
      return true
    })

    if (matchingChunks.length === 0) return

    // 优先选择与 presetConfig 匹配的 chunk
    const presetMatch = matchingChunks.find(chunk =>
      Object.entries(presetConfig).every(([k, v]) => chunk[k] === v)
    )
    const firstMatch = presetMatch || matchingChunks[0]

    // 从匹配的 chunks 中提取固定值（取第一个匹配的 chunk 的值）
    const newFixedValues: Record<string, number> = {}

    // 对于非变量维度，使用匹配 chunk 中的值
    const isParamVar = (id: string) => paramVariableDimensions.includes(id)
    const isSimVar = (id: string) => simVariableDimensions.includes(id)
    const isCalcVar = (id: string) => calcVariableDimensions.includes(id)

    // 参数固定值（优先使用匹配 chunk 的值，回退到预设默认值）
    for (const param of PARAM_DEFINITIONS) {
      if (!isParamVar(param.id)) {
        newFixedValues[param.chunkKey] = firstMatch[param.chunkKey] ?? PRESET_DEFAULTS[param.chunkKey as keyof typeof PRESET_DEFAULTS]
      }
    }

    // 仿真配置固定值
    if (!isSimVar('rep')) newFixedValues.rep = firstMatch.rep ?? PRESET_DEFAULTS.rep
    if (!isSimVar('seed')) newFixedValues.seed = firstMatch.seed ?? PRESET_DEFAULTS.seed

    // 计算配置固定值
    if (!isCalcVar('step')) newFixedValues.step = firstMatch.step ?? PRESET_DEFAULTS.step

    // gamma 总是固定
    newFixedValues.gamma = firstMatch.gamma ?? PRESET_DEFAULTS.gamma

    setFixedValues(prev => ({ ...prev, ...newFixedValues }))
  }, [chunkInfo, currentTab, paramVariableDimensions, simVariableDimensions, calcVariableDimensions,
      selectedParamValues, selectedSimValues, selectedCalcValues])

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
      const successCount = chunkInfoList.filter(c => c.success).length
      console.log(`[DataLoader] Loaded ${allData.length} rows from ${successCount}/${chunks.length} chunks`)
      setCsvData(allData)
      setLoadedChunks(chunkInfoList)
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

  // 解析 chunk 文件名获取参数值
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

  const getParamBorderState = useCallback((paramId: string, value: number): 'red' | 'green' | 'white' => {
    const param = PARAM_DEFINITIONS.find(p => p.id === paramId)
    if (!param || !chunkInfo?.chunks) return 'white'

    const isVariable = paramVariableDimensions.includes(paramId)
    const selectedVals = selectedParamValues[paramId] || []
    const fixedVal = fixedValues[param.chunkKey]

    // 红色：当前选中
    const isSelected = isVariable
      ? selectedVals.includes(value)
      : fixedVal === value
    if (isSelected) return 'red'

    // 绿色检查：必须在**所有**当前变量选择下都有对应的 chunk
    const chunkKey = param.chunkKey

    // 收集所有其他变量维度的选中值组合
    // 如果有多个变量维度，需要检查每个组合是否都有 chunk

    // 获取其他变量维度的选中值
    const otherVars: Array<{
      dim: string
      values: number[]
      key: string
    }> = []

    // 参数变量维度
    for (const dim of paramVariableDimensions) {
      if (dim === paramId) continue
      const p = PARAM_DEFINITIONS.find(x => x.id === dim)
      if (p) {
        const selected = selectedParamValues[dim] || []
        if (selected.length > 0) {
          otherVars.push({ dim, values: selected, key: p.chunkKey })
        }
      }
    }

    // 仿真配置变量维度
    for (const dim of simVariableDimensions) {
      const selected = selectedSimValues[dim] || []
      if (selected.length > 0) {
        otherVars.push({ dim, values: selected, key: dim })
      }
    }

    // 计算配置变量维度
    for (const dim of calcVariableDimensions) {
      const selected = selectedCalcValues[dim] || []
      if (selected.length > 0) {
        otherVars.push({ dim, values: selected, key: dim })
      }
    }

    // 如果没有其他变量维度，只需检查是否存在一个 chunk
    if (otherVars.length === 0) {
      return chunkInfo.chunks.some(chunkName => {
        const chunkParams = parseChunkParams(chunkName)
        return chunkParams && chunkParams[chunkKey] === value
      }) ? 'green' : 'white'
    }

    // 生成所有其他变量的值组合
    const generateCombinations = (vars: typeof otherVars): Array<Record<string, number>> => {
      if (vars.length === 0) return [{}]
      const [first, ...rest] = vars
      const restCombinations = generateCombinations(rest)
      const result: Array<Record<string, number>> = []
      for (const v of first.values) {
        for (const restComb of restCombinations) {
          result.push({ ...restComb, [first.key]: v })
        }
      }
      return result
    }

    const combinations = generateCombinations(otherVars)

    // 检查每个组合是否都有对应的 chunk
    for (const combo of combinations) {
      const hasChunk = chunkInfo.chunks.some(chunkName => {
        const chunkParams = parseChunkParams(chunkName)
        if (!chunkParams) return false
        if (chunkParams[chunkKey] !== value) return false
        // 检查组合中的所有变量值是否匹配
        for (const [key, val] of Object.entries(combo)) {
          if (chunkParams[key] !== val) return false
        }
        return true
      })
      if (!hasChunk) return 'white'  // 任何一个组合没有 chunk，就是白色
    }

    return 'green'  // 所有组合都有 chunk
  }, [paramVariableDimensions, simVariableDimensions, calcVariableDimensions,
      selectedParamValues, selectedSimValues, selectedCalcValues, fixedValues, chunkInfo, parseChunkParams])

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

    // 红色：当前选中
    const isSelected = isVariable
      ? selectedVals.includes(value)
      : fixedVal === value
    if (isSelected) return 'red'

    // 绿色检查：遍历所有 chunks，检查兼容性
    for (const chunkName of chunkInfo.chunks) {
      const chunkParams = parseChunkParams(chunkName)
      if (!chunkParams) continue

      // 当前测试的配置值必须匹配
      if (chunkParams[configId] !== value) continue

      // 检查其他变量维度是否兼容
      let isCompatible = true

      // 检查参数变量维度
      for (const dim of paramVariableDimensions) {
        const p = PARAM_DEFINITIONS.find(x => x.id === dim)
        if (!p) continue
        const selected = selectedParamValues[dim] || []
        if (selected.length > 0 && !selected.includes(chunkParams[p.chunkKey])) {
          isCompatible = false
          break
        }
      }
      if (!isCompatible) continue

      // 检查仿真配置变量维度（跳过当前测试的维度）
      for (const dim of simVariableDimensions) {
        if (dim === configId) continue
        const selected = selectedSimValues[dim] || []
        if (selected.length > 0 && !selected.includes(chunkParams[dim])) {
          isCompatible = false
          break
        }
      }
      if (!isCompatible) continue

      // 检查计算配置变量维度（跳过当前测试的维度）
      for (const dim of calcVariableDimensions) {
        if (dim === configId) continue
        const selected = selectedCalcValues[dim] || []
        if (selected.length > 0 && !selected.includes(chunkParams[dim])) {
          isCompatible = false
          break
        }
      }
      if (!isCompatible) continue

      // 找到一个兼容的 chunk
      return 'green'
    }

    return 'white'
  }, [simVariableDimensions, calcVariableDimensions, selectedSimValues, selectedCalcValues,
      fixedValues, chunkInfo, parseChunkParams, paramVariableDimensions, selectedParamValues])

  // 带参数信息的数据行（用于统计分组）
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

  // === 统计计算 ===

  const stats = useMemo(() => {
    if (enrichedCsvData.length === 0) return []

    const groups = new Map<string, EnrichedRow[]>()

    enrichedCsvData.forEach(enrichedRow => {
      const row = enrichedRow.row
      const keyParts: string[] = []
      // 参数变量
      paramVariableDimensions.forEach(dim => {
        if (dim === 'beta') keyParts.push(`β=${row.beta_true}`)
        if (dim === 'eta') keyParts.push(`η=${row.eta_true}`)
        if (dim === 'sampleSize') keyParts.push(`n=${row.sample_size}`)
        if (dim === 'process') keyParts.push(`δ=${row.offset_value}`)
      })
      // 仿真变量
      simVariableDimensions.forEach(dim => {
        if (dim === 'rep' && enrichedRow.rep !== null) keyParts.push(`rep=${enrichedRow.rep}`)
      })
      // 计算变量
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

      // 提取非参数变量值
      const repValue = rows[0].rep
      const stepValue = rows[0].step

      return {
        key, keyLabel: key,
        beta_true: betaTrue, eta_true: etaTrue, gamma_true: gammaTrue,
        rep: repValue,
        step: stepValue,
        sample_size: dataRows[0].sample_size,
        offset_value: dataRows[0].offset_value,
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
  }, [enrichedCsvData, paramVariableDimensions, simVariableDimensions, calcVariableDimensions, fixedValues])

  // === 渲染 ===

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
          {PARAM_DEFINITIONS.map(param => {
            const chunkValues = chunkInfo?.parsedParams?.[param.chunkKey] || []
            // gamma 只有一个值，占用较小空间
            const isSingleValue = chunkValues.length <= 1
            return (
              <div key={param.id} className={cn("flex flex-col", isSingleValue ? "flex-shrink-0 min-w-[100px]" : "flex-1 min-w-[140px]")}>
                <ConfigCard
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

      {/* 按钮区域 - 统一高度 */}
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
          <div className="flex-1" /> // 占位，保持高度统一
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
            const dimSymbols: Record<string, string> = { sampleSize: 'n', beta: 'β', eta: 'η', process: 'δ', rep: 'rep', step: 'step' }
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
