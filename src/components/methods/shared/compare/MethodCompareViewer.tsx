"use client"

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Loader2, Play, ChevronLeft, ChevronRight, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { MethodComparisonParams } from '@/lib/method-comparison'
import {
  createMethodComparisonLoader, initialMethodComparisonParams, methodComparisonSelectionKey,
  type MethodComparisonSelection, type MethodComparisonState
} from '@/lib/method-comparison-loader'
import MethodSelector from './MethodSelector'
import CompareConfigPanel from './CompareConfigPanel'
import CompareResultsView from './CompareResultsView'

const DEFAULT_VALUES: MethodComparisonParams = {
  beta: 1.5, eta: 1000, gamma: 1000, n: 7, rep: 1000, seed: 42, step: 60, offset: 0.1
}

type Parameter = keyof MethodComparisonParams
type ParameterOptions = Record<Parameter, number[]>
const PARAMETERS = Object.keys(DEFAULT_VALUES) as Parameter[]

function parameterOptions(values: (key: Parameter) => number[]): ParameterOptions {
  return Object.fromEntries(PARAMETERS.map(key => [key, values(key)])) as ParameterOptions
}

interface MethodCompareViewerProps {
  currentMethodId: string
}

export default function MethodCompareViewer(props: MethodCompareViewerProps) {
  return <CurrentMethodComparison key={props.currentMethodId} {...props} />
}

function CurrentMethodComparison({ currentMethodId }: MethodCompareViewerProps) {
  const [selectedMethods, setSelectedMethods] = useState([currentMethodId])
  const [methodStates, setMethodStates] = useState<Record<string, MethodComparisonState>>({})
  const [variableDimensions, setVariableDimensions] = useState<string[]>([])
  const [selectedParams, setSelectedParams] = useState(() => parameterOptions(key => [DEFAULT_VALUES[key]]))
  const [fixedValues, setFixedValues] = useState(DEFAULT_VALUES)
  const [fixedComboIndex, setFixedComboIndex] = useState(0)
  const [displayOptions] = useState({ mean: true, biasMean: true, std: true, ci99: true })
  const [paramSelection, setParamSelection] = useState({ beta: true, eta: true, gamma: true })
  const [densityTab, setDensityTab] = useState<'beta' | 'eta' | 'gamma'>('beta')
  const [paramsInitialized, setParamsInitialized] = useState(false)
  const loader = useRef<ReturnType<typeof createMethodComparisonLoader> | null>(null)
  const isMultiSelectMode = variableDimensions.length > 0

  const selection = useMemo<MethodComparisonSelection>(() => {
    const params = { ...fixedValues }
    for (const key of PARAMETERS) {
      if (variableDimensions.includes(key)) params[key] = selectedParams[key][0]
    }
    return { params, complete: PARAMETERS.every(key => Number.isFinite(params[key])), multiple: isMultiSelectMode }
  }, [fixedValues, selectedParams, variableDimensions, isMultiSelectMode])
  const isConfigComplete = selection.complete

  useEffect(() => {
    const instance = createMethodComparisonLoader((methodId, state) => {
      setMethodStates(previous => ({ ...previous, [methodId]: state }))
    })
    loader.current = instance
    // The first method's archived defaults seed the controls. The loader reuses its catalog.
    instance.catalog(currentMethodId).then(catalog => {
      if (loader.current !== instance) return
      const params = { ...DEFAULT_VALUES, ...initialMethodComparisonParams(catalog) }
      setFixedValues(params)
      setSelectedParams(parameterOptions(key => [params[key]]))
      setParamsInitialized(true)
    }, () => {
      if (loader.current === instance) setParamsInitialized(true)
    })

    return () => {
      loader.current = null
      instance.dispose()
    }
  }, [currentMethodId])

  useEffect(() => {
    if (paramsInitialized) loader.current?.select(selectedMethods, selection)
  }, [paramsInitialized, selectedMethods, selection])

  // Suppress the previous result even in the render before React runs the loading effect.
  const methodsData = Object.fromEntries(selectedMethods.map(methodId => {
    const state = methodStates[methodId]
    const selectionKey = methodComparisonSelectionKey(methodId, selection)
    const current: MethodComparisonState = state?.selectionKey === selectionKey
      ? state
      : { selectionKey, catalog: state?.catalog ?? null, result: { status: 'loading', stage: 'catalog' } }
    return [methodId, current]
  }))

  const availableParams = useMemo(() => parameterOptions(key => {
    const values = selectedMethods.flatMap(id => methodStates[id]?.catalog?.parsedParams[key === 'offset' ? 'd' : key] ?? [])
    return Array.from(new Set(values)).sort((a, b) => a - b)
  }), [selectedMethods, methodStates])

  const paramIntersection = useMemo(() => parameterOptions(key => {
    const groups = selectedMethods.flatMap(id => {
      const values = methodStates[id]?.catalog?.parsedParams[key === 'offset' ? 'd' : key]
      return values ? [values] : []
    })
    return (groups[0] ?? []).filter(value => groups.every(group => group.includes(value))).sort((a, b) => a - b)
  }), [selectedMethods, methodStates])

  const handleToggleValue = (paramId: string, value: number) => {
    if (variableDimensions.includes(paramId)) {
      const key = paramId as Parameter
      setSelectedParams(previous => ({
        ...previous,
        [key]: previous[key].includes(value) ? previous[key].filter(item => item !== value) : [...previous[key], value]
      }))
    } else {
      setFixedValues(previous => ({ ...previous, [paramId]: value }))
    }
  }

  const handleSelectAll = (paramId: string) => {
    const key = paramId as Parameter
    setSelectedParams(previous => ({ ...previous, [key]: (isMultiSelectMode ? paramIntersection : availableParams)[key] }))
  }

  const handleToggleVariable = (paramId: string) => {
    const key = paramId as Parameter
    if (variableDimensions.includes(paramId)) {
      setVariableDimensions(previous => previous.filter(id => id !== paramId))
      setSelectedParams(previous => ({ ...previous, [key]: [DEFAULT_VALUES[key]] }))
    } else if (variableDimensions.length < 2) {
      setVariableDimensions(previous => [...previous, paramId])
      const values = isMultiSelectMode ? paramIntersection[key] : [availableParams[key][0] ?? DEFAULT_VALUES[key]]
      setSelectedParams(previous => ({ ...previous, [key]: values }))
    }
  }

  const pendingMethods = selectedMethods.filter(id => {
    const result = methodsData[id].result
    return result.status === 'waiting-for-simulation' || (result.status === 'error' && result.stage === 'simulation')
  })
  const needsSimulation = pendingMethods.length > 0
  const isSimulating = selectedMethods.some(id => methodsData[id].result.status === 'simulating')
  const canStartSimulation = isConfigComplete && !isMultiSelectMode && needsSimulation && !isSimulating
  const handleRetry = useCallback((methodId: string) => {
    loader.current?.retry(methodId)
  }, [])
  const handleRunAllSimulations = () => {
    if (canStartSimulation) pendingMethods.forEach(handleRetry)
  }

  if (!paramsInitialized) {
    return (
      <div className="flex justify-center items-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-orange-500" />
        <span className="ml-3 text-slate-600">加载分片目录...</span>
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
            {needsSimulation && <span className="text-amber-600 ml-2">({pendingMethods.length} 个需要模拟)</span>}
          </span>
        </div>
        <button
          onClick={handleRunAllSimulations}
          disabled={!canStartSimulation}
          className={cn(
            "flex items-center gap-2 px-5 py-2.5 rounded-lg font-bold text-sm transition-all",
            canStartSimulation
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
        fixedValues={selection.params}
        onRetry={handleRetry}
      />
    </div>
  )
}
