"use client"

import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { Loader2, Play, AlertTriangle, ChevronLeft, ChevronRight, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import MethodSelector, { AVAILABLE_METHODS } from './MethodSelector'
import CompareConfigPanel from './CompareConfigPanel'
import CompareResultsView from './CompareResultsView'

// ============ Types ============

interface SimulationRow {
  beta_true: number
  eta_true: number
  gamma?: number
  sample_size: number
  offset_value?: number
  sim_id: number
  est_beta: number | null
  est_eta: number | null
  est_gamma: number | null
  bias_beta: number | null
  bias_eta: number | null
  bias_gamma: number | null
  r_squared: number | null
}

interface ChunkInfo {
  chunks: string[]
  parsedParams: Record<string, number[]>
  total: number
}

interface MethodData {
  methodId: string
  chunkInfo: ChunkInfo | null
  csvData: SimulationRow[]
  isLoading: boolean
  needsSimulation: boolean
  isSimulating: boolean
  simulationProgress: number  // 0-100
  errorMessage?: string  // 错误信息
  loadedFilename?: string  // 加载成功的文件名
}

// ============ Constants ============

const DEFAULT_VALUES = {
  beta: 1.5,
  eta: 1000,
  gamma: 1000,
  n: 7,
  rep: 1000,
  seed: 42,
  step: 60,
  offset: 0.1  // MDM 偏移量
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
      const idx = headers.indexOf(key)
      if (idx === -1) return null
      const v = values[idx]
      if (!v || v === 'NaN' || v === 'nan') return null
      const n = parseFloat(v)
      return isNaN(n) ? null : n
    }

    rows.push({
      beta_true: parseVal('beta_true') || 0,
      eta_true: parseVal('eta_true') || 0,
      gamma: parseVal('gamma') ?? undefined,
      sample_size: parseInt(values[headers.indexOf('sample_size')] || '0'),
      offset_value: parseVal('offset_value') ?? undefined,
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

function generateChunkFilename(params: Record<string, number | undefined>, isMDM: boolean = false): string {
  const parts: string[] = []

  if (params.beta !== undefined) parts.push(`b${params.beta}`)
  if (params.eta !== undefined) parts.push(`e${params.eta}`)
  if (params.gamma !== undefined) parts.push(`g${params.gamma}`)
  if (params.n !== undefined) parts.push(`n${params.n}`)
  // 只有 MDM 才添加 offset 参数（在文件名中用 'd' 表示）
  if (isMDM && params.offset !== undefined) parts.push(`d${params.offset}`)
  if (params.rep !== undefined) parts.push(`rep${params.rep}`)
  if (params.seed !== undefined) parts.push(`seed${params.seed}`)
  if (params.step !== undefined) parts.push(`step${params.step}`)

  return `${parts.join('_')}.csv`
}

// 计算参数交集
function calculateIntersection(
  chunkInfos: Record<string, ChunkInfo | null>,
  paramKey: string
): number[] {
  const methodIds = Object.keys(chunkInfos).filter(id => chunkInfos[id]?.parsedParams?.[paramKey])

  if (methodIds.length === 0) return []

  // 取所有方法的交集
  let intersection = new Set(chunkInfos[methodIds[0]]!.parsedParams[paramKey])

  for (let i = 1; i < methodIds.length; i++) {
    const currentSet = new Set(chunkInfos[methodIds[i]]!.parsedParams[paramKey])
    intersection = new Set(Array.from(intersection).filter(x => currentSet.has(x)))
  }

  return Array.from(intersection).sort((a, b) => a - b)
}

// ============ Main Component ============

interface MethodCompareViewerProps {
  currentMethodId: string
}

export default function MethodCompareViewer({ currentMethodId }: MethodCompareViewerProps) {
  // ========== State ==========

  // 方法选择
  const [selectedMethods, setSelectedMethods] = useState<string[]>([currentMethodId])

  // 各方法的数据
  const [methodsData, setMethodsData] = useState<Record<string, MethodData>>({})

  // 参数选择
  const [variableDimensions, setVariableDimensions] = useState<string[]>([])
  const [selectedParams, setSelectedParams] = useState<{ beta: number[]; eta: number[]; gamma: number[]; n: number[]; rep: number[]; seed: number[]; step: number[]; offset: number[] }>({
    beta: [DEFAULT_VALUES.beta],
    eta: [DEFAULT_VALUES.eta],
    gamma: [DEFAULT_VALUES.gamma],
    n: [DEFAULT_VALUES.n],
    rep: [DEFAULT_VALUES.rep],
    seed: [DEFAULT_VALUES.seed],
    step: [DEFAULT_VALUES.step],
    offset: [DEFAULT_VALUES.offset]
  })
  const [fixedValues, setFixedValues] = useState<Record<string, number>>({ ...DEFAULT_VALUES })

  // 固定参数组合索引（多选模式用）
  const [fixedComboIndex, setFixedComboIndex] = useState(0)

  // 参数交集
  const [paramIntersection, setParamIntersection] = useState<{ beta: number[]; eta: number[]; gamma: number[]; n: number[]; rep: number[]; seed: number[]; step: number[]; offset: number[] }>({
    beta: [],
    eta: [],
    gamma: [],
    n: [],
    rep: [],
    seed: [],
    step: [],
    offset: []
  })

  // 展示选项
  const [displayOptions] = useState({ mean: true, biasMean: true, std: true, ci99: true })
  const [paramSelection, setParamSelection] = useState({ beta: true, eta: true, gamma: true })
  const [densityTab, setDensityTab] = useState<'beta' | 'eta' | 'gamma'>('beta')

  // 参数是否已根据实际 chunk 初始化（避免使用默认值导致找不到 chunk）
  const [paramsInitialized, setParamsInitialized] = useState(false)

  // ========== Computed ==========

  const isMultiSelectMode = variableDimensions.length > 0
  const allVariableDimensions = variableDimensions

  // 检查是否所有参数都已选择完成
  const requiredParams = ['beta', 'eta', 'gamma', 'n', 'rep', 'seed', 'step'] as const

  const isConfigComplete = useMemo(() => {
    // 检查每个参数是否都有选择
    for (const param of requiredParams) {
      if (variableDimensions.includes(param)) {
        // 变量模式：需要至少选择一个值
        if (!selectedParams[param] || selectedParams[param].length === 0) {
          return false
        }
      } else {
        // 固定模式：需要有固定值
        if (fixedValues[param] === undefined || fixedValues[param] === null) {
          return false
        }
      }
    }
    return true
  }, [variableDimensions, selectedParams, fixedValues])

  // 是否有任何方法需要模拟
  const needsSimulation = useMemo(() => {
    return selectedMethods.some(methodId => {
      const data = methodsData[methodId]
      return data?.needsSimulation && !data?.isSimulating
    })
  }, [selectedMethods, methodsData])

  // 是否正在模拟中
  const isSimulating = useMemo(() => {
    return selectedMethods.some(methodId => methodsData[methodId]?.isSimulating)
  }, [selectedMethods, methodsData])

  // 获取所有可用参数值（并集）
  const availableParams = useMemo((): { beta: number[]; eta: number[]; gamma: number[]; n: number[]; rep: number[]; seed: number[]; step: number[]; offset: number[] } => {
    const result: Record<string, Set<number>> = {
      beta: new Set(),
      eta: new Set(),
      gamma: new Set(),
      n: new Set(),
      rep: new Set(),
      seed: new Set(),
      step: new Set(),
      offset: new Set()
    }

    for (const methodId of selectedMethods) {
      const info = methodsData[methodId]?.chunkInfo
      if (info?.parsedParams) {
        for (const key of Object.keys(result)) {
          // API 返回的 key 映射
          const chunkKey = key === 'n' ? 'n' : key === 'offset' ? 'd' : key
          if (info.parsedParams[chunkKey]) {
            info.parsedParams[chunkKey].forEach(v => result[key].add(v))
          }
        }
      }
    }

    return {
      beta: Array.from(result.beta).sort((a, b) => a - b),
      eta: Array.from(result.eta).sort((a, b) => a - b),
      gamma: Array.from(result.gamma).sort((a, b) => a - b),
      n: Array.from(result.n).sort((a, b) => a - b),
      rep: Array.from(result.rep).sort((a, b) => a - b),
      seed: Array.from(result.seed).sort((a, b) => a - b),
      step: Array.from(result.step).sort((a, b) => a - b),
      offset: Array.from(result.offset).sort((a, b) => a - b)
    }
  }, [selectedMethods, methodsData])

  // ========== Effects ==========

  // 解析 chunk 文件名获取参数
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

  // 查找有效的初始 chunk 参数
  const findInitialChunkParams = useCallback((chunkInfo: ChunkInfo | null): Record<string, number> | null => {
    if (!chunkInfo?.chunks?.length) return null

    // 优先找 beta=2, eta=1000, d=0.1 的文件
    for (const chunk of chunkInfo.chunks) {
      const params = parseChunkParams(chunk)
      if (params && params.beta === 2 && params.eta === 1000 && (params.d === undefined || params.d === 0.1)) {
        return params
      }
    }
    // 其次找 beta=2, eta=1000 的文件
    for (const chunk of chunkInfo.chunks) {
      const params = parseChunkParams(chunk)
      if (params && params.beta === 2 && params.eta === 1000) {
        return params
      }
    }
    // 找不到则用第一个
    return parseChunkParams(chunkInfo.chunks[0])
  }, [parseChunkParams])

  // 加载选中方法的 chunkInfo 并立即加载初始数据
  useEffect(() => {
    let isMounted = true
    let hasInitializedParams = false
    let initialParamsCache: Record<string, number> | null = null

    const loadChunkInfoAndData = async () => {
      for (const methodId of selectedMethods) {
        // 如果已经有 chunkInfo 且有数据，跳过
        if (methodsData[methodId]?.chunkInfo && methodsData[methodId]?.csvData?.length > 0) continue

        if (!isMounted) return

        // 设置加载状态
        setMethodsData(prev => ({
          ...prev,
          [methodId]: {
            methodId,
            chunkInfo: null,
            csvData: [],
            isLoading: true,
            needsSimulation: false,
            isSimulating: false,
            simulationProgress: 0
          }
        }))

        try {
          // 1. 加载 chunkInfo
          const res = await fetch(`/api/studies/${methodId.toLowerCase()}/chunks`)
          if (!isMounted) return

          if (res.ok) {
            const chunkInfo = await res.json()

            // 2. 初始化参数（只初始化一次）
            if (!hasInitializedParams && !paramsInitialized) {
              initialParamsCache = findInitialChunkParams(chunkInfo)
              if (initialParamsCache) {
                console.log('[MethodCompare] 使用初始 chunk 参数:', initialParamsCache)
                setFixedValues(prev => ({
                  ...prev,
                  beta: initialParamsCache!.beta ?? prev.beta,
                  eta: initialParamsCache!.eta ?? prev.eta,
                  gamma: initialParamsCache!.gamma ?? prev.gamma,
                  n: initialParamsCache!.n ?? prev.n,
                  rep: initialParamsCache!.rep ?? prev.rep,
                  seed: initialParamsCache!.seed ?? prev.seed,
                  step: initialParamsCache!.step ?? prev.step,
                  offset: initialParamsCache!.d ?? prev.offset
                }))
                setSelectedParams(prev => ({
                  ...prev,
                  beta: [initialParamsCache!.beta ?? DEFAULT_VALUES.beta],
                  eta: [initialParamsCache!.eta ?? DEFAULT_VALUES.eta],
                  gamma: [initialParamsCache!.gamma ?? DEFAULT_VALUES.gamma],
                  n: [initialParamsCache!.n ?? DEFAULT_VALUES.n],
                  rep: [initialParamsCache!.rep ?? DEFAULT_VALUES.rep],
                  seed: [initialParamsCache!.seed ?? DEFAULT_VALUES.seed],
                  step: [initialParamsCache!.step ?? DEFAULT_VALUES.step]
                }))
                hasInitializedParams = true
              }
              setParamsInitialized(true)
            }

            // 3. 保存 chunkInfo
            setMethodsData(prev => ({
              ...prev,
              [methodId]: {
                ...prev[methodId],
                chunkInfo,
                isLoading: false
              }
            }))

            // 4. 立即用初始参数加载数据
            const params = initialParamsCache || {
              beta: DEFAULT_VALUES.beta,
              eta: DEFAULT_VALUES.eta,
              gamma: DEFAULT_VALUES.gamma,
              n: DEFAULT_VALUES.n,
              rep: DEFAULT_VALUES.rep,
              seed: DEFAULT_VALUES.seed,
              step: DEFAULT_VALUES.step,
              d: DEFAULT_VALUES.offset
            }
            const isMDM = methodId.toLowerCase() === 'mdm'
            const filename = generateChunkFilename({
              beta: params.beta,
              eta: params.eta,
              gamma: params.gamma,
              n: params.n,
              offset: isMDM ? params.d : undefined,
              rep: params.rep,
              seed: params.seed,
              step: params.step
            }, isMDM)

            const chunkExists = chunkInfo.chunks.includes(filename)
            console.log(`[MethodCompare] ${methodId} - 初始加载: ${filename}, exists: ${chunkExists}`)

            if (chunkExists) {
              try {
                const dataRes = await fetch(`/studies/${methodId.toLowerCase()}/chunks/${filename}`)
                if (!isMounted) return

                if (dataRes.ok) {
                  const text = await dataRes.text()
                  const data = parseCsv(text)
                  console.log(`[MethodCompare] ${methodId} - 加载成功: ${data.length} 行`)
                  setMethodsData(prev => ({
                    ...prev,
                    [methodId]: {
                      ...prev[methodId],
                      csvData: data,
                      needsSimulation: false,
                      loadedFilename: filename
                    }
                  }))
                }
              } catch (dataErr) {
                console.error(`[MethodCompare] ${methodId} - 加载数据失败:`, dataErr)
              }
            } else {
              // 没有预计算数据，标记需要模拟
              setMethodsData(prev => ({
                ...prev,
                [methodId]: {
                  ...prev[methodId],
                  csvData: [],
                  needsSimulation: true,
                  loadedFilename: undefined
                }
              }))
            }
          } else {
            setMethodsData(prev => ({
              ...prev,
              [methodId]: {
                ...prev[methodId],
                isLoading: false
              }
            }))
          }
        } catch (err) {
          console.error(`Failed to load chunkInfo for ${methodId}:`, err)
          if (!isMounted) return
          setMethodsData(prev => ({
            ...prev,
            [methodId]: {
              ...prev[methodId],
              isLoading: false
            }
          }))
        }
      }
    }

    loadChunkInfoAndData()

    return () => {
      isMounted = false
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedMethods, findInitialChunkParams, paramsInitialized])

  // 计算参数交集
  useEffect(() => {
    const chunkInfos: Record<string, ChunkInfo | null> = {}
    for (const methodId of selectedMethods) {
      chunkInfos[methodId] = methodsData[methodId]?.chunkInfo || null
    }

    setParamIntersection({
      beta: calculateIntersection(chunkInfos, 'beta'),
      eta: calculateIntersection(chunkInfos, 'eta'),
      gamma: calculateIntersection(chunkInfos, 'gamma'),
      n: calculateIntersection(chunkInfos, 'n'),
      rep: calculateIntersection(chunkInfos, 'rep'),
      seed: calculateIntersection(chunkInfos, 'seed'),
      step: calculateIntersection(chunkInfos, 'step'),
      offset: calculateIntersection(chunkInfos, 'd')  // API 返回的是 'd'
    })
  }, [selectedMethods, methodsData])

  // 生成当前参数组合的唯一键
  const currentParamKey = useMemo(() => {
    return JSON.stringify({
      beta: variableDimensions.includes('beta')
        ? (selectedParams.beta[0] ?? DEFAULT_VALUES.beta)
        : (fixedValues.beta ?? DEFAULT_VALUES.beta),
      eta: variableDimensions.includes('eta')
        ? (selectedParams.eta[0] ?? DEFAULT_VALUES.eta)
        : (fixedValues.eta ?? DEFAULT_VALUES.eta),
      gamma: variableDimensions.includes('gamma')
        ? (selectedParams.gamma[0] ?? DEFAULT_VALUES.gamma)
        : (fixedValues.gamma ?? DEFAULT_VALUES.gamma),
      n: variableDimensions.includes('n')
        ? (selectedParams.n[0] ?? DEFAULT_VALUES.n)
        : (fixedValues.n ?? DEFAULT_VALUES.n),
      rep: variableDimensions.includes('rep')
        ? (selectedParams.rep[0] ?? DEFAULT_VALUES.rep)
        : (fixedValues.rep ?? DEFAULT_VALUES.rep),
      seed: variableDimensions.includes('seed')
        ? (selectedParams.seed[0] ?? DEFAULT_VALUES.seed)
        : (fixedValues.seed ?? DEFAULT_VALUES.seed),
      step: fixedValues.step ?? DEFAULT_VALUES.step,
      offset: fixedValues.offset ?? DEFAULT_VALUES.offset
    })
  }, [variableDimensions, selectedParams, fixedValues])

  // 检查所有 chunkInfo 是否已加载完成
  const allChunkInfoLoaded = useMemo(() => {
    return selectedMethods.every(methodId => methodsData[methodId]?.chunkInfo)
  }, [selectedMethods, methodsData])

  // 跟踪上次加载的参数键，用于检测参数变化（初始加载后）
  const lastLoadedParamKeyRef = React.useRef<string>('')

  // 参数变化时重新加载数据（仅在初始加载完成后触发）
  useEffect(() => {
    // 等待初始加载完成
    if (!allChunkInfoLoaded || !paramsInitialized) return

    // 检测参数是否变化
    const paramChanged = lastLoadedParamKeyRef.current !== currentParamKey
    if (!paramChanged) return

    // 记录新的参数键
    lastLoadedParamKeyRef.current = currentParamKey
    console.log(`[MethodCompare] 参数变化，重新加载: ${currentParamKey}`)

    // 当前参数
    const currentParams = {
      beta: variableDimensions.includes('beta')
        ? (selectedParams.beta[0] ?? DEFAULT_VALUES.beta)
        : (fixedValues.beta ?? DEFAULT_VALUES.beta),
      eta: variableDimensions.includes('eta')
        ? (selectedParams.eta[0] ?? DEFAULT_VALUES.eta)
        : (fixedValues.eta ?? DEFAULT_VALUES.eta),
      gamma: variableDimensions.includes('gamma')
        ? (selectedParams.gamma[0] ?? DEFAULT_VALUES.gamma)
        : (fixedValues.gamma ?? DEFAULT_VALUES.gamma),
      n: variableDimensions.includes('n')
        ? (selectedParams.n[0] ?? DEFAULT_VALUES.n)
        : (fixedValues.n ?? DEFAULT_VALUES.n),
      rep: variableDimensions.includes('rep')
        ? (selectedParams.rep[0] ?? DEFAULT_VALUES.rep)
        : (fixedValues.rep ?? DEFAULT_VALUES.rep),
      seed: variableDimensions.includes('seed')
        ? (selectedParams.seed[0] ?? DEFAULT_VALUES.seed)
        : (fixedValues.seed ?? DEFAULT_VALUES.seed),
      step: fixedValues.step ?? DEFAULT_VALUES.step,
      offset: fixedValues.offset ?? DEFAULT_VALUES.offset
    }

    // 异步加载所有方法的数据
    selectedMethods.forEach(methodId => {
      const chunkInfo = methodsData[methodId]?.chunkInfo
      if (!chunkInfo) return

      // 先重置状态
      setMethodsData(prev => ({
        ...prev,
        [methodId]: {
          ...prev[methodId],
          csvData: [],
          needsSimulation: false,
          errorMessage: undefined,
          loadedFilename: undefined
        }
      }))

      const isMDM = methodId.toLowerCase() === 'mdm'
      const filename = generateChunkFilename(currentParams, isMDM)
      const chunkExists = chunkInfo.chunks.includes(filename)

      if (chunkExists) {
        fetch(`/studies/${methodId.toLowerCase()}/chunks/${filename}`)
          .then(res => {
            if (res.ok) return res.text()
            throw new Error(`HTTP ${res.status}`)
          })
          .then(text => {
            const data = parseCsv(text)
            setMethodsData(prev => ({
              ...prev,
              [methodId]: {
                ...prev[methodId],
                csvData: data,
                needsSimulation: false,
                loadedFilename: filename
              }
            }))
          })
          .catch(err => {
            console.error(`[MethodCompare] ${methodId} - 加载失败:`, err)
          })
      } else {
        setMethodsData(prev => ({
          ...prev,
          [methodId]: {
            ...prev[methodId],
            csvData: [],
            needsSimulation: !isMultiSelectMode,
            loadedFilename: undefined
          }
        }))
      }
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentParamKey, allChunkInfoLoaded, isMultiSelectMode, paramsInitialized])

  // 当有方法需要模拟时，自动触发模拟
  useEffect(() => {
    // 等待所有 chunkInfo 加载完成
    const allChunkInfoLoaded = selectedMethods.every(methodId => methodsData[methodId]?.chunkInfo)
    if (!allChunkInfoLoaded) return

    // 检查是否有需要模拟的方法（且没有正在模拟的）
    const methodsNeedingSimulation = selectedMethods.filter(methodId => {
      const data = methodsData[methodId]
      return data?.needsSimulation && !data?.isSimulating && data?.chunkInfo
    })

    // 如果有需要模拟的方法且配置完成，自动触发模拟
    if (methodsNeedingSimulation.length > 0 && isConfigComplete && !isSimulating) {
      console.log(`[MethodCompare] 自动触发模拟: ${methodsNeedingSimulation.length} 个方法`)
      // 延迟一点触发，让 UI 先更新
      const timer = setTimeout(() => {
        handleRunAllSimulations()
      }, 300)
      return () => clearTimeout(timer)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [methodsData, isConfigComplete, isSimulating, selectedMethods])

  // ========== Handlers ==========

  const handleToggleValue = useCallback((paramId: string, value: number) => {
    const key = paramId as keyof typeof selectedParams
    if (variableDimensions.includes(paramId)) {
      setSelectedParams(prev => {
        const current = prev[key] || []
        const isSelected = current.includes(value)
        return { ...prev, [paramId]: isSelected ? current.filter((v: number) => v !== value) : [...current, value] }
      })
    } else {
      setFixedValues(prev => ({ ...prev, [paramId]: value }))
    }
  }, [variableDimensions, selectedParams])

  const handleSelectAll = useCallback((paramId: string) => {
    // 多选模式下，只选择交集内的值
    const key = paramId as keyof typeof paramIntersection
    const valuesToSelect = isMultiSelectMode
      ? (paramIntersection[key] || [])
      : (availableParams[key] || [])

    setSelectedParams(prev => ({ ...prev, [paramId]: valuesToSelect }))
  }, [isMultiSelectMode, paramIntersection, availableParams])

  const handleToggleVariable = useCallback((paramId: string) => {
    const key = paramId as keyof typeof paramIntersection
    if (variableDimensions.includes(paramId)) {
      setVariableDimensions(prev => prev.filter(id => id !== paramId))
      // 重置该参数为默认值
      setSelectedParams(prev => ({ ...prev, [paramId]: [DEFAULT_VALUES[paramId as keyof typeof DEFAULT_VALUES]] }))
    } else if (variableDimensions.length < 2) {
      setVariableDimensions(prev => [...prev, paramId])
      // 设置为变量时，默认选择交集内的所有值（多选模式）或第一个值（单选模式）
      const values = isMultiSelectMode
        ? (paramIntersection[key] || [])
        : [(availableParams[key]?.[0] ?? DEFAULT_VALUES[paramId as keyof typeof DEFAULT_VALUES])]
      setSelectedParams(prev => ({ ...prev, [paramId]: values }))
    }
  }, [variableDimensions, isMultiSelectMode, paramIntersection, availableParams])

  const handleRunSimulation = useCallback(async (methodId: string) => {
    // 开始模拟
    setMethodsData(prev => ({
      ...prev,
      [methodId]: { ...prev[methodId], isSimulating: true, simulationProgress: 0, errorMessage: undefined }
    }))

    console.log(`[MethodCompare] 开始模拟: methodId=${methodId}, params=`, {
      beta: fixedValues.beta ?? DEFAULT_VALUES.beta,
      eta: fixedValues.eta ?? DEFAULT_VALUES.eta,
      gamma: fixedValues.gamma ?? DEFAULT_VALUES.gamma,
      n: fixedValues.n ?? DEFAULT_VALUES.n,
      rep: fixedValues.rep ?? DEFAULT_VALUES.rep,
      seed: fixedValues.seed ?? DEFAULT_VALUES.seed
    })

    try {
      const res = await fetch('/api/studies/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          methodId,
          params: {
            beta: fixedValues.beta ?? DEFAULT_VALUES.beta,
            eta: fixedValues.eta ?? DEFAULT_VALUES.eta,
            gamma: fixedValues.gamma ?? DEFAULT_VALUES.gamma,
            n: fixedValues.n ?? DEFAULT_VALUES.n,
            rep: fixedValues.rep ?? DEFAULT_VALUES.rep,
            seed: fixedValues.seed ?? DEFAULT_VALUES.seed
          }
        })
      })

      if (res.ok) {
        const data = await res.json()
        console.log(`[MethodCompare] 模拟成功: methodId=${methodId}, rows=${data.rows?.length || 0}`)
        setMethodsData(prev => ({
          ...prev,
          [methodId]: {
            ...prev[methodId],
            csvData: data.rows || [],
            needsSimulation: false,
            isSimulating: false,
            simulationProgress: 100
          }
        }))
      } else {
        const errorData = await res.json().catch(() => ({}))
        const errorMsg = errorData.error || errorData.detail || `HTTP ${res.status}: ${res.statusText}`
        console.error(`[MethodCompare] 模拟失败: methodId=${methodId}`, errorMsg)
        setMethodsData(prev => ({
          ...prev,
          [methodId]: { ...prev[methodId], isSimulating: false, simulationProgress: 0, errorMessage: errorMsg }
        }))
      }
    } catch (err: any) {
      const errorMsg = err.message || String(err)
      console.error(`[MethodCompare] 模拟异常: methodId=${methodId}`, errorMsg)
      setMethodsData(prev => ({
        ...prev,
        [methodId]: { ...prev[methodId], isSimulating: false, simulationProgress: 0, errorMessage: errorMsg }
      }))
    }
  }, [fixedValues])

  // 批量模拟所有需要模拟的方法
  const handleRunAllSimulations = useCallback(async () => {
    if (!isConfigComplete) return

    // 并行模拟所有需要模拟的方法
    const methodsToSimulate = selectedMethods.filter(methodId => {
      const data = methodsData[methodId]
      return data?.needsSimulation && !data?.isSimulating
    })

    console.log(`[MethodCompare] 批量模拟 ${methodsToSimulate.length} 个方法`)

    // 并行执行所有模拟
    await Promise.all(methodsToSimulate.map(methodId => handleRunSimulation(methodId)))
  }, [isConfigComplete, selectedMethods, methodsData, handleRunSimulation])

  // ========== Render ==========

  const isLoading = selectedMethods.some(id => methodsData[id]?.isLoading)

  if (isLoading) {
    return (
      <div className="flex justify-center items-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-orange-500" />
        <span className="ml-3 text-slate-600">加载数据...</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 方法选择器 */}
      <MethodSelector
        currentMethodId={currentMethodId}
        selectedMethods={selectedMethods}
        onSelectionChange={setSelectedMethods}
      />

      {/* 参数配置面板 */}
      <CompareConfigPanel
        availableParams={availableParams}
        paramIntersection={paramIntersection}
        selectedParams={selectedParams}
        fixedValues={fixedValues}
        variableDimensions={variableDimensions}
        selectedMethods={selectedMethods}
        onToggleValue={handleToggleValue}
        onSelectAll={handleSelectAll}
        onToggleVariable={handleToggleVariable}
        isMultiSelectMode={isMultiSelectMode}
      />

      {/* 多选模式：固定参数组合切换 */}
      {isMultiSelectMode && (
        <div className="bg-white p-4 rounded-xl border border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-sm font-bold text-slate-600">固定参数组合</span>
            <button
              onClick={() => setFixedComboIndex(prev => Math.max(0, prev - 1))}
              disabled={fixedComboIndex === 0}
              className="p-1 rounded hover:bg-slate-100 disabled:opacity-30"
            >
              <ChevronLeft size={18} />
            </button>
            <span className="text-sm text-slate-500">{fixedComboIndex + 1}/1</span>
            <button
              onClick={() => setFixedComboIndex(prev => prev + 1)}
              className="p-1 rounded hover:bg-slate-100 disabled:opacity-30"
              disabled
            >
              <ChevronRight size={18} />
            </button>
          </div>
          <div className="text-xs text-slate-400">
            rep={fixedValues.rep}, seed={fixedValues.seed}
          </div>
        </div>
      )}

      {/* 统一的开始模拟按钮 */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-600">
            已选 <span className="font-bold text-purple-600">{selectedMethods.length}</span> 个方法
            {needsSimulation && <span className="text-amber-600 ml-2">({selectedMethods.filter(id => methodsData[id]?.needsSimulation).length} 个需要模拟)</span>}
          </span>
        </div>
        <button
          onClick={handleRunAllSimulations}
          disabled={!isConfigComplete || !needsSimulation || isSimulating}
          className={cn(
            "flex items-center gap-2 px-5 py-2.5 rounded-lg font-bold text-sm transition-all",
            isConfigComplete && needsSimulation && !isSimulating
              ? "bg-purple-600 text-white hover:bg-purple-700 shadow-md hover:shadow-lg"
              : "bg-slate-100 text-slate-400 cursor-not-allowed"
          )}
        >
          {isSimulating ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              模拟中...
            </>
          ) : !isConfigComplete ? (
            <>
              <Zap className="h-4 w-4" />
              请完成参数配置
            </>
          ) : (
            <>
              <Play className="h-4 w-4" />
              开始模拟
            </>
          )}
        </button>
      </div>

      {/* 结果展示 */}
      <CompareResultsView
        selectedMethods={selectedMethods}
        methodsData={methodsData}
        variableDimensions={variableDimensions}
        displayOptions={displayOptions}
        paramSelection={paramSelection}
        setParamSelection={setParamSelection}
        densityTab={densityTab}
        setDensityTab={setDensityTab}
        fixedValues={fixedValues}
      />
    </div>
  )
}
