"use client"

import React, { useState, useMemo, useRef, useEffect } from 'react'
import './analysis-responsive.css'
import { GenerationButton } from './GenerationButton'
import { BatchResultTable } from './BatchResultTable'
import { SampleCardStack } from './SampleCardStack'
import { useCardSequence } from './useCardSequence'
import { generateSampleSources, storeCalculationBatch, type BatchProgress } from '@/lib/calculator-batch'
import { CalculationNoticeDialog } from './CalculationNoticeDialog'
import { CalculationError, getCalculationNotice, type CalculationNotice } from '@/lib/calculation-feedback'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import { 
  Settings2, 
  FileText, 
  BarChart3, 
  Plus, 
  Copy, 
  MousePointer2,
  Layers,
  Check,
  ArrowRight,
  ArrowRightLeft,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Edit3,
  Sliders,
  Trash2,
  Eraser,
  BookOpen,
  RefreshCw,
  Play,
  LineChart as LineChartIcon,
  Calculator,
  Sparkles,
  AreaChart as AreaChartIcon,
  FilePlus2
} from 'lucide-react'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts'
import { ZoomIn } from 'lucide-react'
import {
  DataPoint,
  WeibullResult,
  DataSource,
  MULTI_CURVE_COLORS,
  generatePDFPoints,
  generateCDFPoints
} from '@/lib/weibull'
import { getMethodInfo } from '@/lib/methods'
import {
  getDefaultParameters,
  getEstimationModeFailure,
  type CalculatorParameters,
  type CalculatorCardType,
  MDM_DEFAULT_OFFSET,
  MDM_OFFSET_GRID,
} from '@/lib/calculator-state'
import {
  buildMdmOptimizationDetailsHref,
  isMdmAiSampleSizeSupported,
  MdmOffsetMode,
  MdmProcessOptimizationResult,
} from '@/lib/mdm-process-optimization'

const cn = (...classes: (string | undefined | null | false)[]) => classes.filter(Boolean).join(' ')

export interface LayerInfo {
  id: string
  name: string
  color: string
  result: WeibullResult
}

interface AnalysisCardProps {
  id: string
  index: number
  data?: DataPoint[]
  result?: WeibullResult
  methodId?: string
  mdmOffset?: number
  mdmOffsetMode?: MdmOffsetMode
  mdmOptimization?: MdmProcessOptimizationResult
  color: string
  fitMode: 'fit' | 'manual'
  generationParameters?: CalculatorParameters
  generatedFrom?: CalculatorParameters
  initialDirection?: 'estimate' | 'generate'
  onDirectionChange?: (direction: 'estimate' | 'generate') => void
  is3P: boolean
  availableLayers: LayerInfo[]
  // 多数据源模式
  dataSources?: DataSource[]
  activeDataSourceIndex?: number
  onActiveDataSourceChange?: (index: number) => void
  onAdd: (type: CalculatorCardType, sourceId: string, currentData?: DataPoint[]) => void
  onMethodClick?: () => void
  onMdmOffsetChange?: (offset: number) => void | Promise<void>
  onMdmOffsetModeChange?: (mode: MdmOffsetMode) => void | Promise<void>
  onToggle3P?: () => void
  onDataClick?: () => void
  onDataChange?: (newData: DataPoint[], generatedFrom?: CalculatorParameters) => void
  onDataSourcesChange?: (sources: DataSource[], generatedFrom?: CalculatorParameters, activeIndex?: number) => void
  calculationProgress?: BatchProgress
  onGenerationParametersChange?: (parameters: CalculatorParameters) => void
  onCalculate?: () => Promise<void>
  calculationActionLabel?: string
  onDelete?: () => void
  hideCalculationProcessButton?: boolean
  hideMdmOptimizationDetailsLink?: boolean
  lockParameterMode?: boolean
  isMdmOffsetUpdating?: boolean
}

export default function AnalysisCard({
  id,
  index,
  data,
  result,
  methodId,
  mdmOffset = MDM_DEFAULT_OFFSET,
  mdmOffsetMode = 'fixed',
  mdmOptimization,
  color,
  fitMode,
  generationParameters,
  generatedFrom,
  initialDirection,
  onDirectionChange,
  is3P,
  availableLayers,
  dataSources,
  activeDataSourceIndex,
  onActiveDataSourceChange,
  onAdd,
  onMethodClick,
  onMdmOffsetChange,
  onMdmOffsetModeChange,
  onToggle3P,
  onDataClick,
  onDataChange,
  onDataSourcesChange,
  calculationProgress,
  onGenerationParametersChange,
  onCalculate,
  calculationActionLabel = '参数估计',
  onDelete,
  hideCalculationProcessButton,
  hideMdmOptimizationDetailsLink = false,
  lockParameterMode = false,
  isMdmOffsetUpdating = false
}: AnalysisCardProps) {
  const [isHovered, setIsHovered] = useState(false)
  const [isAddMenuOpen, setIsAddMenuOpen] = useState(false)
  const [isOverlayMenuOpen, setIsOverlayMenuOpen] = useState(false)
  const [selectedOverlayIds, setSelectedOverlayIds] = useState<string[]>([])
  const [isCalculating, setIsCalculating] = useState(false)
  const [chartMode, setChartMode] = useState<'pdf' | 'cdf'>('pdf')
  const [xAxisRange, setXAxisRange] = useState<{ min: number; max: number; isAuto: boolean }>({ min: 0, max: 0, isAuto: true })
  const [localSourceIndex, setLocalSourceIndex] = useState(0)
  const activeSourceIndex = activeDataSourceIndex ?? localSourceIndex
  const applySourceIndex = (sourceIndex: number) => {
    setLocalSourceIndex(sourceIndex)
    onActiveDataSourceChange?.(sourceIndex)
  }
  const batchIdentity = dataSources?.[0]?.groupId ?? dataSources?.[0]?.id ?? id
  const sequenceIdentity = `${methodId}|${is3P}|${batchIdentity}`
  const reducedMotion = !!useReducedMotion()
  const playback = useCardSequence(sequenceIdentity, applySourceIndex, reducedMotion)
  const [navigationDirection, setNavigationDirection] = useState(0)
  const setActiveSourceIndex = (sourceIndex: number, direction = 0) => {
    const total = dataSources?.length ?? 1
    playback.cancel()
    setNavigationDirection(direction)
    applySourceIndex((sourceIndex % total + total) % total)
  }
  const progressRun = useRef<string>()
  const { start: startSequence, ready: readySequence } = playback
  useEffect(() => {
    if (!calculationProgress) { progressRun.current = undefined; return }
    const key = calculationProgress.runId ?? 'current'
    if (progressRun.current !== key) {
      progressRun.current = key
      setShowBatchTable(false)
      startSequence('calculate', calculationProgress.total, sequenceIdentity)
    }
    readySequence(calculationProgress.completed, 'calculate')
  }, [calculationProgress, sequenceIdentity, startSequence, readySequence])
  const selectedSource = dataSources?.[activeSourceIndex]
  const activeOptimization = selectedSource ? selectedSource.mdmOptimization : mdmOptimization
  const currentData = selectedSource?.data ?? data
  const sourceOrigin = selectedSource ? selectedSource.generatedFrom : generatedFrom
  const stacked = !!dataSources && dataSources.length > 1
  const [showBatchTable, setShowBatchTable] = useState(false)
  const [generationCount, setGenerationCount] = useState(1)
  useEffect(() => {
    if (dataSources && dataSources.length > 1) setGenerationCount(dataSources.length)
    setShowBatchTable(false)
  }, [dataSources?.[0]?.groupId, dataSources?.length])
  const failureValues = useMemo(
    () => (selectedSource?.data ?? data ?? []).filter(point => point.status === 'F').map(point => point.value),
    [data, selectedSource?.data],
  )
  const isMdmAiSupported = isMdmAiSampleSizeSupported(failureValues.length)

  const [sampleText, setSampleText] = useState("")
  const [simN, setSimN] = useState(20)
  const [direction, setDirection] = useState<'estimate' | 'generate'>(() =>
    initialDirection ?? (fitMode === 'manual' && result && !data?.length ? 'generate' : 'estimate'))
  const generating = direction === 'generate'
  const changeDirection = (next: 'estimate' | 'generate') => {
    setDirection(next)
    onDirectionChange?.(next)
  }
  const [localParameters, setLocalParameters] = useState<CalculatorParameters>(() =>
    generationParameters ?? (fitMode === 'manual' && result?.beta && result.eta
      ? { beta: result.beta, eta: result.eta, gamma: result.gamma } : getDefaultParameters(is3P)))
  const draft = generationParameters ?? localParameters
  const samplingParameters = useMemo(() => ({ ...draft, gamma: is3P ? draft.gamma : 0 }), [draft, is3P])
  const [generationError, setGenerationError] = useState('')
  const [notice, setNotice] = useState<CalculationNotice | null>(null)
  const savedSampleText = useRef('')
  const busy = isCalculating || isMdmOffsetUpdating || playback.active
  const showSequenceProgress = playback.active || !!calculationProgress && calculationProgress.completed < calculationProgress.total
  const estimate = selectedSource ? selectedSource.result : fitMode === 'fit' ? result : undefined
  const displayResult = generating ? samplingParameters
    : estimate?.converged === false || estimate?.converged === 'unbounded' ? undefined : estimate
  const chartResult = displayResult
  const referenceParameters = !generating ? sourceOrigin : undefined
  const currentSampleMatches = sourceOrigin && sourceOrigin.beta === samplingParameters.beta
    && sourceOrigin.eta === samplingParameters.eta && sourceOrigin.gamma === samplingParameters.gamma
    && currentData?.length === simN

  const menuRef = useRef<HTMLDivElement>(null)
  const addMenuRef = useRef<HTMLDivElement>(null)
  // Use useMemo to prevent object reference changes on every render
  const methodInfo = React.useMemo(() => getMethodInfo(methodId), [methodId])
  const router = useRouter()
  useEffect(() => {
    if (currentData) {
      const text = currentData.map(d => `${d.value}${d.status === 'S' ? ' S' : ''}`).join('\n')
      setSampleText(text)
      savedSampleText.current = text
      if (currentData.length > 0) setSimN(currentData.length)
    } else {
      setSampleText('')
      savedSampleText.current = ''
    }
  }, [currentData])

  // 计算样本统计信息
  const sampleStats = useMemo(() => {
    if (dataSources && dataSources.length > 0) {
      const groupSize = dataSources[0].data.length
      const groupCount = dataSources.length
      return { groupSize, groupCount, total: groupSize * groupCount }
    } else if (data) {
      return { groupSize: data.length, groupCount: 1, total: data.length }
    }
    return { groupSize: 0, groupCount: 0, total: 0 }
  }, [data, dataSources])

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOverlayMenuOpen(false)
      }
      if (addMenuRef.current && !addMenuRef.current.contains(event.target as Node)) {
        setIsAddMenuOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const groupCurveParameters = useMemo(() => {
    if (generating || !dataSources || dataSources.length < 2) return []
    const candidates = dataSources.flatMap(source => [
      source.result?.converged === false || source.result?.converged === 'unbounded' ? undefined : source.result,
      source.generatedFrom,
    ]).filter((value): value is CalculatorParameters => !!value && value.beta !== null && value.eta !== null
      && Number.isFinite(value.beta) && Number.isFinite(value.eta) && Number.isFinite(value.gamma) && value.beta > 0 && value.eta > 0)
    return Array.from(new Map(candidates.map(value => [[value.beta, value.eta, value.gamma].join(','), value])).values())
  }, [generating, dataSources])

  // Every group uses the same union as an overlaid comparison.
  const unifiedXRange = useMemo(() => {
    const parameters = [
      chartResult,
      referenceParameters,
      ...groupCurveParameters,
      ...selectedOverlayIds.map(id => availableLayers.find(layer => layer.id === id)?.result),
    ].filter((value): value is CalculatorParameters => !!value && value.beta !== null && value.eta !== null
      && Number.isFinite(value.beta) && Number.isFinite(value.eta) && Number.isFinite(value.gamma) && value.beta > 0 && value.eta > 0)
    if (!parameters.length) return null
    return { min: Math.min(...parameters.map(value => value.gamma)),
      max: Math.max(...parameters.map(value => value.gamma + value.eta * 2.5)) }
  }, [chartResult, referenceParameters, groupCurveParameters, selectedOverlayIds, availableLayers])

  const chartData = useMemo(() => {
    if (!chartResult || chartResult.beta === null || chartResult.eta === null || !(chartResult.beta > 0) || !(chartResult.eta > 0) || !unifiedXRange) return []

    // Use auto range (union of all) or custom range
    const minT = xAxisRange.isAuto ? unifiedXRange.min : xAxisRange.min
    const maxT = xAxisRange.isAuto ? unifiedXRange.max : xAxisRange.max

    if (chartMode === 'pdf') {
      return generatePDFPoints(chartResult.beta, chartResult.eta, chartResult.gamma, minT, maxT, 100)
    } else {
      return generateCDFPoints(chartResult.beta, chartResult.eta, chartResult.gamma, minT, maxT, 100)
    }
  }, [chartResult, chartMode, xAxisRange, unifiedXRange])

  // A shared range changes only when the batch or comparison extent changes.
  // Flipping between groups keeps a manually selected viewport.
  useEffect(() => {
    if (unifiedXRange) {
      setXAxisRange({ min: unifiedXRange.min, max: unifiedXRange.max, isAuto: true })
    }
  }, [unifiedXRange?.min, unifiedXRange?.max])

  const overlayCurves = useMemo(() => {
    if (!unifiedXRange) return []

    return selectedOverlayIds.map(overlayId => {
      const layer = availableLayers.find(l => l.id === overlayId)
      if (!layer || !layer.result || layer.result.beta === null || layer.result.eta === null) return null
      const res = layer.result
      const beta = res.beta!
      const eta = res.eta!
      const gamma = res.gamma

      // Use unified range
      const minT = xAxisRange.isAuto ? unifiedXRange.min : xAxisRange.min
      const maxT = xAxisRange.isAuto ? unifiedXRange.max : xAxisRange.max

      const points = chartMode === 'pdf'
        ? generatePDFPoints(beta, eta, gamma, minT, maxT, 100)
        : generateCDFPoints(beta, eta, gamma, minT, maxT, 100)

      return { id: layer.id, name: layer.name, color: layer.color, points }
    }).filter(Boolean)
  }, [selectedOverlayIds, availableLayers, chartMode, unifiedXRange, xAxisRange])

  const referencePoints = useMemo(() => {
    if (!referenceParameters || !unifiedXRange) return []
    const min = xAxisRange.isAuto ? unifiedXRange.min : xAxisRange.min
    const max = xAxisRange.isAuto ? unifiedXRange.max : xAxisRange.max
    return (chartMode === 'pdf' ? generatePDFPoints : generateCDFPoints)(
      referenceParameters.beta, referenceParameters.eta, referenceParameters.gamma, min, max, 100)
  }, [referenceParameters, unifiedXRange, xAxisRange, chartMode])

  const sourceCurves = useMemo(() => {
    if (generating || !unifiedXRange) return []
    const min = xAxisRange.isAuto ? unifiedXRange.min : xAxisRange.min
    const max = xAxisRange.isAuto ? unifiedXRange.max : xAxisRange.max
    return (selectedSource ? [selectedSource] : []).filter(source => source.visible !== false && source.result?.beta != null && source.result.eta != null)
      .map(source => ({ ...source, points: (chartMode === 'pdf' ? generatePDFPoints : generateCDFPoints)(
        source.result!.beta!, source.result!.eta!, source.result!.gamma, min, max, 100) }))
  }, [generating, selectedSource, unifiedXRange, xAxisRange, chartMode])
  const primaryCurveColor = sourceCurves[0]?.color ?? color

  const plotMin = xAxisRange.isAuto ? unifiedXRange?.min : xAxisRange.min
  const plotMax = xAxisRange.isAuto ? unifiedXRange?.max : xAxisRange.max
  // Cache the group extent; paging does not redraw every background curve.
  const groupYRange = useMemo(() => {
    if (plotMin === undefined || plotMax === undefined) return null
    let min = Infinity, max = -Infinity
    const draw = chartMode === 'pdf' ? generatePDFPoints : generateCDFPoints
    for (const parameters of groupCurveParameters) {
      for (const point of draw(parameters.beta, parameters.eta, parameters.gamma, plotMin, plotMax, 100)) {
        if (!Number.isFinite(point.y)) continue
        min = Math.min(min, point.y)
        max = Math.max(max, point.y)
      }
    }
    return min === Infinity ? null : { min, max }
  }, [groupCurveParameters, plotMin, plotMax, chartMode])

  // Include the whole group even though only the selected curve is drawn.
  const unifiedYRange = useMemo(() => {
    const points = [...chartData, ...referencePoints, ...sourceCurves.flatMap(curve => curve.points),
      ...overlayCurves.flatMap(curve => curve?.points ?? [])]
    if (!points.length && !groupYRange) return null

    let minY = groupYRange?.min ?? Infinity
    let maxY = groupYRange?.max ?? -Infinity

    points.forEach(point => {
      if (!Number.isFinite(point.y)) return
      if (point.y < minY) minY = point.y
      if (point.y > maxY) maxY = point.y
    })
    if (minY === Infinity) return null

    // Add some padding (10% on each side)
    const padding = (maxY - minY) * 0.1
    return { min: Math.max(0, minY - padding), max: maxY + padding }
  }, [chartData, overlayCurves, referencePoints, sourceCurves, groupYRange])

  const updateSamplingParameters = (parameters: CalculatorParameters) => {
    setLocalParameters(parameters)
    onGenerationParametersChange?.(parameters)
    setGenerationError('')
  }
  const handleParamChange = (key: 'beta' | 'eta' | 'gamma', value: string) => {
    const val = parseFloat(value)
    if (Number.isFinite(val)) updateSamplingParameters({ ...draft, [key]: val })
  }

  const commitSample = (newData: DataPoint[]) => {
    if (dataSources && onDataSourcesChange) {
      onDataSourcesChange(dataSources.map((source, index) => index === activeSourceIndex ? {
        ...source, data: newData, generatedFrom: undefined, result: undefined, traceData: undefined,
        calculation: undefined, calculationError: undefined, calculationOffset: undefined, archive: undefined,
      } : source), generatedFrom, activeSourceIndex)
    } else onDataChange?.(newData)
  }

  const handleSampleTextBlur = () => {
    if (!onDataChange || generating || sampleText === savedSampleText.current) return
    const lines = sampleText.split('\n').filter(line => line.trim())
    const newData: DataPoint[] = []
    lines.forEach((line, idx) => {
      const parts = line.trim().split(/\s+/)
      const val = parseFloat(parts[0])
      if (!isNaN(val)) {
        const status = parts.length > 1 && parts[1].toUpperCase().startsWith('S') ? 'S' : 'F'
        newData.push({ id: idx, value: val, status })
      }
    })
    savedSampleText.current = sampleText
    commitSample(newData)
  }

  const handleGenerateSample = () => {
    if (!onDataChange) return
    const parameters = generating ? samplingParameters : displayResult
    if (!parameters || parameters.beta === null || parameters.eta === null) return
    const source = { beta: parameters.beta, eta: parameters.eta, gamma: parameters.gamma }
    const count = generating ? simN : selectedSource?.data.length ?? data?.length ?? simN
    try {
      if (generationCount > 1 && !onDataSourcesChange) throw new Error('当前页面尚未接入多组样本')
      const sources = generateSampleSources(generationCount, count, source)
      setGenerationError('')
      if (!generating) {
        updateSamplingParameters(source)
        changeDirection('generate')
      }
      if (generationCount > 1) onDataSourcesChange!(sources, source, 0)
      else onDataChange(sources[0].data, source)
      startSequence('generate', sources.length, `${methodId}|${is3P}|${sources.length > 1 ? sources[0].groupId ?? sources[0].id : id}`)
      readySequence(sources.length, 'generate')
    } catch (error) {
      setGenerationError(error instanceof Error ? error.message : '抽样设置无效')
    }
  }

  const handleResetToDefault = () => {
    const defaults = getDefaultParameters(is3P)
    updateSamplingParameters({ ...defaults, gamma: is3P ? defaults.gamma : draft.gamma })
  }

  const handleParameterModeChange = (nextIs3P: boolean) => {
    if (nextIs3P === is3P || !onToggle3P) return
    if (is3P && displayResult?.beta != null && displayResult.eta != null) {
      updateSamplingParameters({ beta: displayResult.beta, eta: displayResult.eta, gamma: displayResult.gamma })
    }
    onToggle3P()
  }

  const handleEstimation = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!onCalculate) return
    const modeFailure = getEstimationModeFailure(is3P)
    if (modeFailure) {
      setNotice(getCalculationNotice(new CalculationError(modeFailure, undefined, undefined, { kind: 'input' })))
      return
    }
    if (generating) changeDirection('estimate')
    setIsCalculating(true)
    const singleSample = !dataSources?.length && !!currentData?.length
    try {
      if (singleSample) startSequence('calculate', 1, sequenceIdentity)
      await onCalculate()
      if (singleSample) readySequence(1, 'calculate')
    } finally {
      setIsCalculating(false)
    }
  }

  const handleDirectionSwitch = () => {
    if (!generating && displayResult?.beta != null && displayResult.eta != null) {
      updateSamplingParameters({ beta: displayResult.beta, eta: displayResult.eta, gamma: displayResult.gamma })
      if (currentData?.length) setSimN(currentData.length)
    }
    changeDirection(generating ? 'estimate' : 'generate')
    setGenerationError('')
  }

  const directionSwitch = <button type="button" className="analysis-direction-switch" disabled={busy}
    aria-label={generating ? '切换为参数估计' : '切换为生成样本'}
    title={generating ? '切换为参数估计' : '切换为生成样本'}
    onClick={handleDirectionSwitch}>
    <ArrowRightLeft size={16} aria-hidden="true" />
  </button>

  const samplePanel = <div key="sample" className="analysis-sample relative w-1/4 flex flex-col bg-white h-full">
    {!generating && directionSwitch}
    <div className="h-12 flex items-center justify-between px-4 text-slate-500 border-b border-slate-100/50">
      <div className="flex items-center gap-2">
        <div className="p-1 bg-emerald-50 text-emerald-600 rounded"><FileText size={16} /></div>
        <span className="text-base font-black tracking-wider">样本</span>
      </div>
      {!generating && <button onClick={onDataClick} disabled={busy}
        className="h-7 px-2 text-slate-400 hover:text-emerald-600 rounded flex items-center gap-1">
        <BookOpen size={14} /><span className="text-sm font-black">案例库</span>
      </button>}
    </div>
    <div className="flex-1 min-h-0 p-4 flex flex-col overflow-hidden">
      {generating && sampleStats.total > 0 && !currentSampleMatches &&
        <p className="mb-2 shrink-0 text-xs text-slate-500">点击生成样本可按当前设置更新</p>}
      <div className="relative w-full flex-1 min-h-0" data-stack-content>
        <textarea disabled={busy} readOnly={generating} aria-label="样本数据"
          className="w-full h-full text-xs font-mono p-3 bg-slate-50 border border-slate-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-emerald-400/50 focus:border-emerald-400 text-slate-600 leading-relaxed"
          placeholder={generating ? '点击生成样本' : '输入或导入样本'}
          value={sampleText} onChange={event => setSampleText(event.target.value)} onBlur={handleSampleTextBlur} />
        <div className="absolute bottom-2 right-2 text-xs font-black text-slate-400 bg-white/90 px-1.5 py-0.5 rounded border border-slate-100">
          N={currentData?.length ?? 0}
        </div>
      </div>
    </div>
    <div className="analysis-card-footer h-12 flex items-center gap-2 px-4">
      <button type="button" disabled={busy} onClick={handleEstimation}
        className="flex-1 h-full bg-emerald-600 hover:bg-emerald-700 text-white rounded-md flex items-center justify-center gap-1.5 text-sm font-bold disabled:opacity-50">
        {busy ? <Loader2 size={14} className="animate-spin" /> : <Calculator size={14} />}
        <span>{playback.active && playback.phase === 'generate' ? '生成中…' : busy ? '计算中…' : calculationActionLabel}</span>
      </button>
      <button type="button" disabled={busy} onClick={() => { setSampleText(''); commitSample([]) }}
        className="h-full px-3 bg-slate-50 hover:bg-red-50 text-slate-500 hover:text-red-600 border border-slate-200 rounded-md flex items-center gap-1.5 text-sm font-bold">
        <Trash2 size={14} /><span>清除样本</span>
      </button>
    </div>
  </div>

  const parameterPanel = <div key="parameters" className="analysis-parameters relative w-1/4 flex flex-col bg-white h-full">
    {generating && directionSwitch}
    <div className="h-12 flex items-center justify-between px-4 text-slate-500 border-b border-slate-100/50">
      <div className="flex items-center gap-2">
        <div className="p-1 bg-indigo-50 text-indigo-600 rounded"><Sliders size={16} /></div>
        <span className="text-base font-black tracking-wider">参数</span>
      </div>
      <div className="flex bg-slate-100 p-0.5 rounded-full border border-slate-200 h-8">
        <button type="button" disabled={lockParameterMode || busy} onClick={() => handleParameterModeChange(false)}
          className={cn('px-2.5 h-full rounded-full text-sm font-black', !is3P ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-400')}>2P</button>
        <button type="button" disabled={lockParameterMode || busy} onClick={() => handleParameterModeChange(true)}
          className={cn('px-2.5 h-full rounded-full text-sm font-black', is3P ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-400')}>3P</button>
      </div>
    </div>
    <div className="flex-1 p-4 flex flex-col overflow-y-auto">
      <div className="space-y-3">
        <ParamInput label="β 形状" value={displayResult?.beta ?? null}
          onChange={value => handleParamChange('beta', value)} readOnly={!generating || busy} showControls={generating} color="text-indigo-600" decimals={3} />
        <ParamInput label="η 尺度" value={displayResult?.eta ?? null}
          onChange={value => handleParamChange('eta', value)} readOnly={!generating || busy} showControls={generating} color="text-indigo-600" decimals={3} />
        <ParamInput label="γ 位置" value={is3P ? displayResult?.gamma ?? null : 0}
          onChange={value => handleParamChange('gamma', value)} readOnly={!generating || !is3P || busy} showControls={generating} color="text-blue-600" decimals={3} />
        {!stacked && !generating && dataSources && dataSources.length > 1 && <div className="flex flex-wrap justify-center items-center gap-2">
          {dataSources.map((source, index) => <button key={source.id} type="button" disabled={busy}
            aria-label={'查看' + source.name + '估计结果'} aria-pressed={index === activeSourceIndex}
            onClick={() => setActiveSourceIndex(index)}
            className={cn('w-3 h-3 rounded-full', index === activeSourceIndex ? 'bg-indigo-500' : 'bg-slate-300')}
            title={source.name} />)}
          <span className="text-xs text-slate-400">({activeSourceIndex + 1}/{dataSources.length}) {selectedSource?.name}</span>
        </div>}
        <div className="pt-2 border-t border-slate-100">
          <ParamInput label="N 样本数" value={generating ? simN : selectedSource?.data.length ?? data?.length ?? 0}
            onChange={value => setSimN(Number(value))} readOnly={!generating || busy} showControls={generating}
            color="text-slate-500" step={1} decimals={0} />
        </div>
        {!generating && estimate?.converged === false && <p className="text-sm text-orange-700" role="status">
          {estimate.failureReason || '未得到可采纳结果'}</p>}
        {!generating && estimate?.converged === 'unbounded' && <p className="text-sm text-orange-700" role="status">未找到有限极大值</p>}
        {generating && generationError && <p role="alert" className="text-sm text-orange-700">{generationError}</p>}
      </div>
    </div>
    <div className="analysis-card-footer h-12 flex items-center gap-2 px-4">
      {generating ? <>
        <GenerationButton count={generationCount} onCountChange={setGenerationCount} onGenerate={handleGenerateSample}
          disabled={busy} />
        <button type="button" onClick={handleResetToDefault} disabled={busy}
          className="analysis-reset-parameters h-full px-3 bg-slate-50 text-slate-500 border border-slate-200 rounded-md flex items-center gap-1.5 text-sm font-bold">
          <Eraser size={14} /><span>重置参数</span>
        </button>
      </> : <button type="button" onClick={handleDirectionSwitch}
        disabled={busy}
        className="flex-1 h-full bg-indigo-50 hover:bg-indigo-100 text-indigo-600 border border-indigo-200 rounded-md flex items-center justify-center gap-1.5 text-sm font-bold disabled:opacity-50 disabled:cursor-not-allowed">
        <RefreshCw size={14} /><span>用参数生成样本</span>
      </button>}
    </div>
  </div>

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="analysis-card w-full relative group/card pb-4 mb-4 mt-4"
      data-calculation-direction={direction}
      data-stacked={stacked || undefined}
      data-card-playback={playback.active ? playback.phase : undefined}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {stacked && <div className="analysis-stack-controls" role="group" aria-label="切换样本组">
        <div className={cn('analysis-icon-button', showSequenceProgress ? 'analysis-stack-progress' : 'analysis-stack-counter')}
          data-running={showSequenceProgress || undefined}>
        <AnimatePresence initial={false}>
        {showSequenceProgress ? <motion.span key="progress" role="status" className="absolute inset-0 grid place-items-center"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: reducedMotion ? 0 : .16 }}>
          <span className="sr-only">{playback.active && playback.phase === 'generate' ? `生成 ${playback.shown}/${playback.total}`
            : `已完成 ${calculationProgress?.completed ?? 0}/${calculationProgress?.total ?? playback.total}`}</span>
          <StackCount label={playback.active && playback.phase === 'generate' ? '生成中' : '已完成'}
            value={playback.active && playback.phase === 'generate' ? playback.shown : calculationProgress?.completed ?? 0}
            total={calculationProgress?.total ?? playback.total} />
        </motion.span> : <motion.button key="counter" type="button" aria-label={showBatchTable ? '返回样本卡片' : '查看整组结果'}
          aria-expanded={showBatchTable} onClick={() => setShowBatchTable(value => !value)}
          className="absolute inset-0 grid place-items-center rounded-xl" title={`当前第 ${activeSourceIndex + 1} 组，共 ${dataSources.length} 组`}
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: reducedMotion ? 0 : .16 }}>
          <StackCount label="当前组" value={activeSourceIndex + 1} total={dataSources.length} /></motion.button>}
        </AnimatePresence>
        </div>
        <button type="button" className="analysis-icon-button analysis-stack-arrow" data-side="previous" aria-label="上一组样本"
          onClick={() => setActiveSourceIndex(activeSourceIndex - 1, -1)}><ChevronLeft size={18} /></button>
        <button type="button" className="analysis-icon-button analysis-stack-arrow" data-side="next" aria-label="下一组样本"
          onClick={() => setActiveSourceIndex(activeSourceIndex + 1, 1)}><ChevronRight size={18} /></button>
      </div>}
      {notice && <CalculationNoticeDialog notice={notice} onClose={() => setNotice(null)} />}
      {/* Action Buttons (Moved Outside - Right Side) */}
      <div className="analysis-actions absolute top-0 -right-10 flex flex-col gap-2 z-30">
         <button aria-label="删除分析卡片" onClick={onDelete} data-variant="delete"
           className="analysis-icon-button opacity-0 group-hover/card:opacity-100">
            <Trash2 size={18} />
         </button>
         
         <div className="relative" ref={addMenuRef}>
           <button 
             aria-label="添加分析卡片"
             aria-expanded={isAddMenuOpen}
             aria-haspopup="menu"
             onClick={() => { playback.cancel(); setIsAddMenuOpen(!isAddMenuOpen) }}
             data-active={isAddMenuOpen || undefined}
             className="analysis-icon-button opacity-0 group-hover/card:opacity-100"
           >
              <Plus size={18} />
           </button>
           <AnimatePresence>
             {isAddMenuOpen && (
               <motion.div
                 initial={{ opacity: 0, x: 10, scale: 0.9 }}
                 animate={{ opacity: 1, x: 0, scale: 1 }}
                 exit={{ opacity: 0, x: 10, scale: 0.9 }}
                 role="menu" aria-label="添加分析卡片选项"
                 className="absolute right-full top-0 mr-2 w-36 bg-white rounded-xl shadow-xl border border-slate-100 p-1.5 z-50 flex flex-col gap-1"
               >
                 <button onClick={() => { onAdd('method', id); setIsAddMenuOpen(false); }} className="flex items-center gap-2 px-3 py-2 hover:bg-blue-50 rounded-lg text-xs font-black text-slate-600 hover:text-blue-600 transition-colors text-left group">
                   <Copy size={12} className="text-blue-400 group-hover:text-blue-600" /> 
                   <span>继承方法</span>
                 </button>
                 <button onClick={() => { onAdd('data', id); setIsAddMenuOpen(false); }} className="flex items-center gap-2 px-3 py-2 hover:bg-indigo-50 rounded-lg text-xs font-black text-slate-600 hover:text-indigo-600 transition-colors text-left group">
                   <Copy size={12} className="text-indigo-400 group-hover:text-indigo-600" />
                   <span>继承样本</span>
                 </button>
                 <button disabled={!dataSources || dataSources.length < 2}
                   onClick={() => { onAdd('data-group', id); setIsAddMenuOpen(false); }}
                   className="flex items-center gap-2 px-3 py-2 enabled:hover:bg-indigo-50 rounded-lg text-xs font-black text-slate-600 enabled:hover:text-indigo-600 transition-colors text-left group disabled:opacity-40 disabled:cursor-not-allowed">
                   <Layers size={12} className="text-indigo-400" />
                   <span>继承样本组</span>
                 </button>
                 <button onClick={() => { onAdd('params', id); setIsAddMenuOpen(false); }} className="flex items-center gap-2 px-3 py-2 hover:bg-indigo-50 rounded-lg text-xs font-black text-slate-600 hover:text-indigo-600 transition-colors text-left group">
                   <Copy size={12} className="text-indigo-400 group-hover:text-indigo-600" />
                   <span>继承参数</span>
                 </button>
                 <button onClick={() => { onAdd('chart', id); setIsAddMenuOpen(false); }} className="flex items-center gap-2 px-3 py-2 hover:bg-emerald-50 rounded-lg text-xs font-black text-slate-600 hover:text-emerald-600 transition-colors text-left group">
                   <MousePointer2 size={12} className="text-emerald-400 group-hover:text-emerald-600" />
                   <span>继承图表</span>
                 </button>
                 <div className="h-[1px] bg-slate-100 my-0.5"></div>
                 <button onClick={() => { onAdd('blank', id); setIsAddMenuOpen(false); }} className="flex items-center gap-2 px-3 py-2 hover:bg-slate-50 rounded-lg text-xs font-black text-slate-600 hover:text-slate-800 transition-colors text-left group">
                   <FilePlus2 size={12} className="text-slate-400 group-hover:text-slate-600" />
                   <span>新建空白</span>
                 </button>
               </motion.div>
             )}
           </AnimatePresence>
         </div>
      </div>

      {/* Main Card Container */}
      <SampleCardStack face={selectedSource?.id ?? id} batch={dataSources?.[0]?.groupId ?? dataSources?.[0]?.id ?? id}
        index={activeSourceIndex} stacked={stacked} total={dataSources?.length ?? 1} onSelect={setActiveSourceIndex}
        playbackMotion={playback.motion} playbackActive={playback.active} navigationDirection={navigationDirection}
        duration={playback.active ? playback.duration : .22} onSettled={playback.settled}>
      <div data-show-table={showBatchTable && stacked || undefined} className={cn(
        "analysis-surface relative bg-white rounded-xl border transition-all duration-300 shadow-sm h-[340px]",
        isHovered ? "border-blue-400 shadow-md ring-1 ring-blue-100" : "border-slate-200"
      )}>

        {showBatchTable && stacked ? <BatchResultTable sources={dataSources} activeIndex={activeSourceIndex}
          onSelect={index => { setActiveSourceIndex(index); setShowBatchTable(false) }} />
          : <div className="analysis-grid flex h-full divide-x divide-slate-100 relative z-10 bg-white pt-2 pb-2 rounded-xl">
          
          {/* Column 1: 方法栏 */}
          <div className="analysis-method w-[12.5%] bg-slate-50/30 flex flex-col group/col cursor-pointer hover:bg-blue-50/30 transition-colors h-full" onClick={onMethodClick}>
            {/* 标题栏 */}
            <div className="h-12 flex items-center gap-2 px-3 text-slate-500 border-b border-slate-100/50">
              <Settings2 size={16} className="text-blue-600" />
              <button type="button" className="text-base font-black uppercase tracking-wider" onClick={event => { event.stopPropagation(); onMethodClick?.() }}>方法选择</button>
            </div>
            {/* 内容栏 */}
            <div className="flex-1 flex flex-col items-center justify-center text-center px-3">
              {methodId ? (
                 <div className="flex w-full flex-col items-center gap-2">
                   <div className="font-black text-slate-700 text-sm sm:text-base leading-tight break-words max-w-full">
                     {methodInfo.name}
                   </div>
                   <div className="px-2 py-0.5 text-xs text-blue-600 bg-blue-50 rounded-full border border-blue-100 font-black tracking-tighter">
                     {methodInfo.short}
                   </div>
                   {methodId.toLowerCase() === 'mdm' && (
                     <div
                       className="mt-2 w-full rounded-lg border border-emerald-200 bg-emerald-50/80 p-2 text-left"
                       onClick={(event) => event.stopPropagation()}
                     >
                       <div className="mb-1 text-[10px] font-black text-emerald-700">偏移量 δ</div>
                       <div className="mb-1.5 grid grid-cols-2 rounded-md border border-emerald-200 bg-white p-0.5">
                         <button
                           type="button"
                           disabled={isMdmOffsetUpdating}
                           onClick={() => { void onMdmOffsetModeChange?.('fixed') }}
                           className={cn(
                             'h-6 rounded text-[9px] font-black transition-colors',
                             mdmOffsetMode === 'fixed'
                               ? 'bg-emerald-600 text-white'
                               : 'text-slate-500 hover:bg-emerald-50',
                           )}
                         >
                           固定值
                         </button>
                         <button
                           type="button"
                           disabled={!isMdmAiSupported || isMdmOffsetUpdating}
                           onClick={() => { void onMdmOffsetModeChange?.('ai') }}
                           className={cn(
                             'h-6 rounded text-[9px] font-black transition-colors disabled:cursor-not-allowed disabled:opacity-40',
                             mdmOffsetMode === 'ai'
                               ? 'bg-violet-600 text-white'
                               : 'text-slate-500 hover:bg-violet-50',
                           )}
                         >
                           AI优化
                         </button>
                       </div>

                       {mdmOffsetMode === 'fixed' ? (
                         <select
                           id={`mdm-offset-${id}`}
                           value={mdmOffset}
                           disabled={isMdmOffsetUpdating}
                           onChange={(event) => { void onMdmOffsetChange?.(Number(event.target.value)) }}
                           className="h-8 w-full rounded-md border border-emerald-200 bg-white px-2 text-xs font-black text-emerald-700 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
                           aria-label="MDM 固定偏移量"
                         >
                           {MDM_OFFSET_GRID.map(offset => (
                             <option key={offset} value={offset}>{offset.toFixed(2)}</option>
                           ))}
                         </select>
                       ) : (
                         <div className="rounded-md border border-violet-200 bg-white px-2 py-1.5">
                           <div className="flex items-center gap-1 text-[9px] font-black text-violet-600">
                             <Sparkles size={10} />
                             {activeOptimization
                               ? `AI建议 δ=${activeOptimization.selected_delta.toFixed(2)}`
                               : '估计时自动选择'}
                           </div>
                           {!hideMdmOptimizationDetailsLink && (
                             <button
                               type="button"
                               onClick={() => router.push(buildMdmOptimizationDetailsHref(failureValues))}
                               className="mt-1 text-[9px] font-bold text-violet-500 underline underline-offset-2 hover:text-violet-700"
                             >
                               查看AI选择过程
                             </button>
                           )}
                         </div>
                       )}
                       {!isMdmAiSupported && (
                         <div className="mt-1 text-[9px] font-bold text-slate-400">
                           AI当前支持 n=7、10、15、20
                         </div>
                       )}
                        {fitMode !== 'fit' && (
                          <div className="mt-1 text-[9px] font-bold text-amber-600">
                            {isCalculating || isMdmOffsetUpdating
                              ? (mdmOffsetMode === 'ai' ? '正在选择并估计' : '正在自动更新')
                              : '重新估计后生效'}
                          </div>
                        )}
                     </div>
                   )}
                 </div>
              ) : (
                <div className="w-full border-2 border-dashed border-slate-200 rounded-lg flex items-center justify-center text-slate-400 text-xs py-8">选择</div>
              )}
            </div>
            {/* 底栏 - 计算过程按钮 */}
            {!hideCalculationProcessButton && methodId && data && data.length > 0 && (
               <div className="analysis-card-footer h-12 flex items-end justify-center px-4 opacity-0 group-hover/col:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!methodId || !data) return;
                      if (stacked) {
                        try {
                          const batch = storeCalculationBatch(dataSources, methodId, activeSourceIndex, mdmOffset, generatedFrom)
                          router.push('/methods/' + methodId + '/calculation?' + new URLSearchParams({ sampleBatch: batch, model: is3P ? '3p' : '2p' }))
                        } catch {
                          setNotice(getCalculationNotice(new CalculationError('这批样本暂时无法传入计算过程。', undefined, undefined, { kind: 'input' })))
                        }
                        return
                      }
                      const selectedData = dataSources?.[activeSourceIndex]?.data ?? data;
                      const params = new URLSearchParams({
                        data: selectedData.filter(d => d.status === 'F').map(d => d.value).join(','),
                        model: is3P ? '3p' : '2p',
                      });
                      if (methodId.toLowerCase() === 'mdm') {
                        const selectedSource = dataSources?.[activeSourceIndex];
                        const usedOffset = selectedSource?.calculationOffset ?? (mdmOffsetMode === 'ai' ? activeOptimization?.selected_delta ?? mdmOffset : mdmOffset);
                        params.set('offset', usedOffset.toFixed(2));
                      }
                      if (generatedFrom && !dataSources?.length) {
                        params.set('trueBeta', String(generatedFrom.beta))
                        params.set('trueEta', String(generatedFrom.eta))
                        params.set('trueGamma', String(generatedFrom.gamma))
                      }
                      router.push(`/methods/${methodId}/calculation?${params.toString()}`);
                    }}
                    className="flex-1 h-full bg-blue-50 hover:bg-blue-100 text-blue-600 border border-blue-200 rounded-md flex items-center justify-center gap-1.5 text-[12px] font-bold transition-all active:scale-95 shadow-sm"
                  >
                    <ArrowRight size={14} />
                    计算过程
                  </button>
               </div>
            )}
          </div>

          {generating ? <>{parameterPanel}{samplePanel}</> : <>{samplePanel}{parameterPanel}</>}

                              {/* Column 4: 图像 */}
          
                              <div className="analysis-chart w-[37.5%] flex flex-col bg-white h-full relative group/chart">
          
                                 {/* 标题栏 */}
          
                                 <div className="h-12 flex items-center justify-between px-4 text-slate-500 border-b border-slate-100/50">
          
                                    <div className="flex items-center gap-2">
          
                                       <div className="p-1 bg-blue-50 text-blue-600 rounded"><BarChart3 size={16} /></div>
          
                                       <span className="text-base font-black uppercase tracking-wider">图像</span>
          
                                    </div>
          
                                    <div className="flex items-center gap-2">

                                      {/* X-axis Range Slider */}
                                      {unifiedXRange && (
                                        <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-lg px-2 py-1">
                                          <button
                                            onClick={() => setXAxisRange(prev => ({ ...prev, isAuto: true }))}
                                            className={cn(
                                              "text-[12px] font-black px-1.5 py-0.5 rounded transition-all",
                                              xAxisRange.isAuto ? "bg-blue-100 text-blue-600" : "text-slate-400 hover:text-slate-600 hover:bg-slate-100"
                                            )}
                                          >
                                            自动
                                          </button>
                                          <DualSlider
                                            min={unifiedXRange.min}
                                            max={unifiedXRange.max}
                                            valueMin={xAxisRange.isAuto ? unifiedXRange.min : xAxisRange.min}
                                            valueMax={xAxisRange.isAuto ? unifiedXRange.max : xAxisRange.max}
                                            onChange={(min, max) => setXAxisRange({ min, max, isAuto: false })}
                                            width={100}
                                          />
                                        </div>
                                      )}

                                      <div className="flex bg-slate-100 p-0.5 rounded-full border border-slate-200 h-8">

                                        <button onClick={() => setChartMode('pdf')} className={cn("px-3 h-full rounded-full text-sm font-black transition-all flex items-center", chartMode === 'pdf' ? "bg-white text-blue-600 shadow-sm" : "text-slate-400 hover:text-slate-500")}>PDF</button>
          
                                        <button onClick={() => setChartMode('cdf')} className={cn("px-3 h-full rounded-full text-sm font-black transition-all flex items-center", chartMode === 'cdf' ? "bg-white text-blue-600 shadow-sm" : "text-slate-400 hover:text-slate-500")}>CDF</button>
          
                                      </div>
          
                                      <div ref={menuRef} className="relative h-8">
          
                                        <button aria-label="叠加图层" aria-expanded={isOverlayMenuOpen} onClick={() => setIsOverlayMenuOpen(!isOverlayMenuOpen)} className={cn("h-full aspect-square flex items-center justify-center rounded-md transition-colors border", isOverlayMenuOpen ? "bg-blue-100 text-blue-600 border-blue-200" : "text-slate-400 hover:text-blue-600 hover:bg-blue-50 border-slate-200 hover:border-blue-100")}>
          
                                          <Layers size={16} />
          
                                        </button>
                    <AnimatePresence>
                      {isOverlayMenuOpen && (
                        <motion.div initial={{ opacity: 0, scale: 0.95, y: 5 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95, y: 5 }} className="absolute right-0 top-full mt-2 w-48 bg-white rounded-lg shadow-xl border border-slate-100 p-2 z-30">
                          <div className="text-[10px] font-black text-slate-400 px-2 py-1 mb-1 uppercase tracking-widest">叠加对比</div>
                          {availableLayers.length > 0 ? availableLayers.map(layer => (
                            <div key={layer.id} onClick={() => setSelectedOverlayIds(prev => prev.includes(layer.id) ? prev.filter(id => id !== layer.id) : [...prev, layer.id])} className="flex items-center gap-2 px-2 py-1.5 hover:bg-slate-50 rounded cursor-pointer text-xs text-slate-600">
                              <div className={cn("w-2 h-2 rounded-full", !selectedOverlayIds.includes(layer.id) && "opacity-30")} style={{ backgroundColor: layer.color }} />
                              <span className="flex-1 truncate font-bold">{layer.name}</span>
                              {selectedOverlayIds.includes(layer.id) && <Check size={12} className="text-blue-600" />}
                            </div>
                          )) : <div className="px-2 py-2 text-[10px] text-slate-400 italic text-center">无图层</div>}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>
             </div>
             {/* 内容栏 */}
             <div className="analysis-plot relative flex-1 px-4 pt-4 pb-2" data-stack-content>
             {(sourceCurves.length > 1 || overlayCurves.length > 0 || (chartData.length > 0 && referencePoints.length > 0)) &&
             <div className="analysis-chart-legend">
               {(generating || !dataSources?.length) && chartResult && <CurveLegend
                 label={generating ? '抽样分布' : '估计分布'} color={color} />}
               {referenceParameters && <CurveLegend label="抽样分布" color="#94a3b8" />}
               {sourceCurves.map(source =>
                 <CurveLegend key={source.id} label={source.name} color={source.color} />)}
               {overlayCurves.map(layer => layer && <CurveLegend key={layer.id} label={layer.name} color={layer.color} />)}
             </div>}
               {unifiedXRange ? (
                 <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
                      <defs>
                        <linearGradient id={`color-${id}`} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={primaryCurveColor} stopOpacity={0.1}/>
                          <stop offset="95%" stopColor={primaryCurveColor} stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                      <XAxis
                        dataKey="x"
                        type="number"
                        allowDataOverflow
                        domain={xAxisRange.isAuto ? [unifiedXRange.min, unifiedXRange.max] : [xAxisRange.min, xAxisRange.max]}
                        tick={{ fontSize: 9, fill: '#94a3b8' }}
                        tickFormatter={(v) => v.toFixed(0)}
                      />
                      <YAxis
                        allowDataOverflow
                        domain={unifiedYRange ? [unifiedYRange.min, unifiedYRange.max] : ['auto', 'auto']}
                        tick={{ fontSize: 9, fill: '#94a3b8' }}
                        width={30}
                      />
                      <Tooltip content={({ active, payload }) => {
                          if (active && payload && payload.length) {
                            return (
                              <div className="bg-white/95 backdrop-blur border border-slate-200 p-2 rounded-lg shadow-xl text-lg z-50">
                                <p className="font-black text-slate-800">t: {payload[0].payload.x.toFixed(2)}</p>
                                <p className="font-black" style={{ color }}>{chartMode.toUpperCase()}: {(payload[0].value as number)?.toFixed(4)}</p>
                              </div>
                            );
                          }
                          return null;
                        }}
                      />
                      {/* 主曲线 - 仅在没有多数据源时渲染 */}
                      {(generating || !dataSources?.length) && (
                        <Area type="monotone" dataKey="y" stroke={color} strokeWidth={2} fillOpacity={1} fill={`url(#color-${id})`} isAnimationActive={false} />
                      )}
                      {!!referencePoints.length && <Area type="monotone" data={referencePoints} dataKey="y"
                        name="抽样分布" stroke="#94a3b8" strokeWidth={1.5} strokeDasharray="4 4" fill="none" isAnimationActive={false} />}
                      {overlayCurves.map(layer => layer && (
                         <Area key={layer.id} type="monotone" data={layer.points} dataKey="y" stroke={layer.color} strokeWidth={1.5} strokeDasharray="4 4" fill="none" isAnimationActive={false} />
                      ))}
                      {sourceCurves.map(source => <Area key={source.id} type="monotone" data={source.points}
                        dataKey="y" stroke={source.color} strokeWidth={2} fillOpacity={1} fill={`url(#color-${id})`} isAnimationActive={false} />)}
                    </AreaChart>
                 </ResponsiveContainer>
               ) : (
                 <div className="flex-1 h-full flex flex-col items-center justify-center text-slate-300">
                    <BarChart3 size={48} strokeWidth={1} />
                 </div>
               )}
             </div>

             {/* 底栏 - Result Analysis Button */}
                <div className="analysis-card-footer h-12 flex items-end justify-center px-4">
                   <button
                     disabled={!methodId}
                     onClick={(e) => {
                       e.stopPropagation();
                       if (!methodId) return;
                       const parameters = referenceParameters ?? chartResult
                       const params = new URLSearchParams({ model: is3P ? '3p' : '2p' });
                       if (parameters && parameters.beta !== null && parameters.eta !== null) {
                         params.set('trueBeta', parameters.beta.toString());
                         params.set('trueEta', parameters.eta.toString());
                         params.set('trueGamma', parameters.gamma.toString());
                       }
                       router.push(`/methods/${methodId}/analysis?${params.toString()}`);
                     }}
                     className="flex-1 h-full bg-emerald-50 hover:bg-emerald-100 text-emerald-600 border border-emerald-200 rounded-md flex items-center justify-center gap-1.5 text-[12px] font-bold transition-all active:scale-95 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                   >
                     <BarChart3 size={14} />
                     结果分析
                   </button>
                </div>
          </div>
        </div>}
      </div>
      </SampleCardStack>
    </motion.div>
  )
}

function StackCount({ label, value, total }: { label: string; value: number; total: number }) {
  return <span className="analysis-stack-count" aria-hidden="true">
    <span className="analysis-stack-count-label">{label}</span>
    <span className="analysis-stack-count-value">{value}</span>
    <span className="analysis-stack-count-divider" />
    <span className="analysis-stack-count-total">{total}</span>
  </span>
}

function CurveLegend({ label, color }: {
  label: string; color: string
}) {
  return <p className="flex flex-wrap items-center gap-x-2" data-curve-label={label}>
    <span className="inline-block h-0.5 w-3" style={{ backgroundColor: color }} />
    <span>{label}</span>
  </p>
}

function ParamInput({ label, value, onChange, readOnly, showControls, color, step = 0.1, decimals = 2 }: { label: string, value: number | null, onChange: (v: string) => void, readOnly: boolean, showControls: boolean, color: string, step?: number, decimals?: number }) {
  // Define available magnitudes based on decimal precision
  const allSteps = [10, 1, 0.1, 0.01, 0.001]
  const availableSteps = allSteps.filter(s => {
    if (decimals === 0) return s >= 1
    const sDecimals = s.toString().includes('.') ? s.toString().split('.')[1].length : 0
    return sDecimals <= decimals
  })

  // Initialize or fallback to a valid step
  const [currentStep, setCurrentStep] = useState(() => {
    return availableSteps.includes(step) ? step : (availableSteps[availableSteps.length - 1] || 1)
  })

  const cycleStep = () => {
    if (readOnly) return
    const currentIndex = availableSteps.indexOf(currentStep)
    const nextIndex = (currentIndex + 1) % availableSteps.length
    setCurrentStep(availableSteps[nextIndex])
  }

  return (
    <div className="analysis-param-input flex items-center justify-center gap-2 text-sm h-8">
      <span className={cn("font-black w-20 shrink-0 truncate text-left", color)}>{label}</span>

      {showControls && <button
        onClick={cycleStep}
        disabled={readOnly}
        className={cn(
          "min-w-[42px] px-1.5 py-0.5 rounded-md text-base font-mono font-black border transition-all active:scale-90 shadow-sm",
          "bg-white border-blue-200 text-blue-600 hover:border-blue-400 hover:bg-blue-50"
        )}
        title="点击切换步进位数"
      >
        <span className="opacity-50 mr-0.5">±</span>
        {currentStep >= 1 ? currentStep : currentStep.toString().replace('0.', '.')}
      </button>}

      <div className="w-28 shrink-0">
        <StepperInput
          label={label}
          value={value}
          onChange={(v) => onChange(v.toString())}
          step={currentStep}
          readOnly={readOnly}
          showControls={showControls}
          color={color}
          decimals={decimals}
        />
      </div>
    </div>
  )
}

function StepperInput({ label, value, onChange, step = 1, readOnly, showControls, color, decimals = 0 }: { label: string, value: number | null, onChange: (val: number) => void, step?: number, readOnly?: boolean, showControls: boolean, color?: string, decimals?: number }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [inputValue, setInputValue] = useState(value?.toFixed(decimals) ?? '')

  // Sync with external value changes, but only if not currently focused (to avoid conflict)
  // Or better: only update if the numeric value is significantly different to avoid formatting loops
  useEffect(() => {
    if (value === null) {
      setInputValue('')
      return
    }
    // Check if the current input value parses to the same number
    const currentNum = parseFloat(inputValue)
    if (Math.abs(currentNum - value) > 1e-10 || isNaN(currentNum)) {
       setInputValue(value.toFixed(decimals))
    }
  }, [value, decimals])

  const handleIncrement = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (readOnly) return
    const newValue = parseFloat(((value ?? 0) + step).toFixed(decimals))
    onChange(newValue)
    setInputValue(newValue.toFixed(decimals))
  }

  const handleDecrement = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (readOnly) return
    const newValue = parseFloat(((value ?? 0) - step).toFixed(decimals))
    onChange(newValue)
    setInputValue(newValue.toFixed(decimals))
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const rawVal = e.target.value
    setInputValue(rawVal)
    
    // Attempt to parse and notify parent
    const val = parseFloat(rawVal)
    if (!isNaN(val)) {
      onChange(val)
    }
  }

  const handleBlur = () => {
    // On blur, force format to standard precision
    setInputValue(value?.toFixed(decimals) ?? '')
  }

  return (
    <div className={cn(
      "flex items-stretch border rounded-lg overflow-hidden h-8 transition-all",
      "bg-white border-slate-200 hover:border-blue-300"
    )}>
      <input 
        ref={inputRef}
        data-stack-content
        type="text" 
        aria-label={label}
        inputMode="decimal"
        className={cn(
          "w-full bg-transparent text-left text-sm font-black focus:outline-none pl-3 pr-1",
          "text-slate-700"
        )} 
        value={inputValue} 
        readOnly={readOnly}
        onChange={handleInputChange}
        onBlur={handleBlur}
        onClick={(e) => e.stopPropagation()}
      />
        {showControls && <div className="flex flex-col border-l border-slate-100 w-5 bg-slate-50">
          <button 
            disabled={readOnly}
            aria-label={`增加${label}`}
            onClick={handleIncrement} 
            className="flex-1 flex items-center justify-center text-slate-400 hover:text-blue-600 hover:bg-blue-50 border-b border-slate-100 transition-colors"
          >
            <Plus size={10} strokeWidth={4} />
          </button>
          <button 
            disabled={readOnly}
            aria-label={`减少${label}`}
            onClick={handleDecrement} 
            className="flex-1 flex items-center justify-center text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
          >
            <div className="w-1.5 h-[2px] bg-current rounded-full" />
          </button>
        </div>}
    </div>
  )
}

// Dual Range Slider Component with Pan
function DualSlider({
  min,
  max,
  valueMin,
  valueMax,
  onChange,
  width = 100
}: {
  min: number
  max: number
  valueMin: number
  valueMax: number
  onChange: (min: number, max: number) => void
  width?: number
}) {
  const sliderRef = useRef<HTMLDivElement>(null)
  const [isDraggingMin, setIsDraggingMin] = useState(false)
  const [isDraggingMax, setIsDraggingMax] = useState(false)
  const [isPanning, setIsPanning] = useState(false)
  const [panStartX, setPanStartX] = useState(0)
  const [panStartMin, setPanStartMin] = useState(0)
  const [panStartMax, setPanStartMax] = useState(0)

  const range = max - min
  const minPercent = ((valueMin - min) / range) * 100
  const maxPercent = ((valueMax - min) / range) * 100
  const span = valueMax - valueMin

  const handleMouseMove = (e: PointerEvent) => {
    if (!sliderRef.current) return
    const rect = sliderRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const percent = Math.max(0, Math.min(100, (x / rect.width) * 100))
    const newValue = min + (percent / 100) * range

    if (isDraggingMin) {
      onChange(Math.min(newValue, valueMax - range * 0.05), valueMax)
    } else if (isDraggingMax) {
      onChange(valueMin, Math.max(newValue, valueMin + range * 0.05))
    } else if (isPanning) {
      const deltaX = e.clientX - panStartX
      const deltaPercent = (deltaX / rect.width) * 100
      const deltaValue = (deltaPercent / 100) * range

      let newMin = panStartMin + deltaValue
      let newMax = panStartMax + deltaValue

      // Clamp to bounds
      if (newMin < min) {
        newMin = min
        newMax = min + span
      }
      if (newMax > max) {
        newMax = max
        newMin = max - span
      }

      onChange(newMin, newMax)
    }
  }

  const handleMouseUp = () => {
    setIsDraggingMin(false)
    setIsDraggingMax(false)
    setIsPanning(false)
  }

  const handleTrackMouseDown = (e: React.PointerEvent) => {
    // Only pan if clicking on the selected range area
    const rect = sliderRef.current!.getBoundingClientRect()
    const x = e.clientX - rect.left
    const clickPercent = (x / rect.width) * 100
    const clickValue = min + (clickPercent / 100) * range

    // Check if click is within the selected range
    if (clickValue >= valueMin && clickValue <= valueMax) {
      setIsPanning(true)
      setPanStartX(e.clientX)
      setPanStartMin(valueMin)
      setPanStartMax(valueMax)
      e.stopPropagation()
    }
  }

  useEffect(() => {
    if (isDraggingMin || isDraggingMax || isPanning) {
      document.addEventListener('pointermove', handleMouseMove)
      document.addEventListener('pointerup', handleMouseUp)
      document.addEventListener('pointercancel', handleMouseUp)
      return () => {
        document.removeEventListener('pointermove', handleMouseMove)
        document.removeEventListener('pointerup', handleMouseUp)
        document.removeEventListener('pointercancel', handleMouseUp)
      }
    }
  }, [isDraggingMin, isDraggingMax, isPanning, valueMin, valueMax, panStartX, panStartMin, panStartMax])

  return (
    <div
      ref={sliderRef}
      className="relative h-5 bg-slate-200 rounded touch-none"
      style={{ width }}
    >
      {/* Track - draggable for panning */}
      <div
        className={cn(
          "absolute h-full rounded transition-colors",
          isPanning ? "bg-blue-500 cursor-grabbing" : "bg-blue-400 cursor-grab"
        )}
        style={{ left: `${minPercent}%`, width: `${maxPercent - minPercent}%` }}
        onPointerDown={handleTrackMouseDown}
      />
      {/* Left Handle */}
      <div
        className={cn(
          "absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white border-2 rounded-full cursor-ew-resize shadow-sm z-10",
          isDraggingMin ? "border-blue-600 scale-125" : "border-blue-400 hover:scale-110"
        )}
        style={{ left: `${minPercent}%`, marginLeft: '-6px' }}
        onPointerDown={(e) => { e.stopPropagation(); setIsDraggingMin(true) }}
      />
      {/* Right Handle */}
      <div
        className={cn(
          "absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white border-2 rounded-full cursor-ew-resize shadow-sm z-10",
          isDraggingMax ? "border-blue-600 scale-125" : "border-blue-400 hover:scale-110"
        )}
        style={{ left: `${maxPercent}%`, marginLeft: '-6px' }}
        onPointerDown={(e) => { e.stopPropagation(); setIsDraggingMax(true) }}
      />
      {/* Tooltip */}
      {(isDraggingMin || isDraggingMax || isPanning) && (
        <div className="absolute -top-6 left-1/2 -translate-x-1/2 text-[9px] font-mono bg-slate-800 text-white px-1.5 py-0.5 rounded whitespace-nowrap z-20">
          {valueMin.toFixed(0)} - {valueMax.toFixed(0)}
        </div>
      )}
    </div>
  )
}
