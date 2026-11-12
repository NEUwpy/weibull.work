"use client"

import React, { useState, useEffect, Suspense } from 'react'
import AnalysisCard from '@/components/calculator/AnalysisCard'
import { LayoutGrid } from 'lucide-react'
import { useSearchParams } from 'next/navigation'
import {
  DataPoint,
  WeibullResult,
  DataSource,
  MULTI_CURVE_COLORS
} from '@/lib/weibull'
import MethodSelector from '@/components/calculator/MethodSelector'
import DataEditor from '@/components/calculator/DataEditor'
import { CalculationNoticeDialog } from '@/components/calculator/CalculationNoticeDialog'
import { calculateWeibull } from '@/hooks/useWeibullCalculation'
import { CalculationError, getCalculationNotice, type CalculationNotice } from '@/lib/calculation-feedback'
import { isCalculatorEnabled, getEnabledMethodIds } from '@/lib/method-status'
import { createLatestRequestTracker } from '@/lib/latest-request'
import { estimateSampleSources, inheritSampleSources, type BatchProgress } from '@/lib/calculator-batch'
import {
  getDefaultParameters,
  getEstimateFailure,
  getEstimationModeFailure,
  MDM_DEFAULT_OFFSET,
  parseMdmOffsetOption,
  toggleParameterMode,
  type CalculatorParameters,
  type CalculatorCardType,
} from '@/lib/calculator-state'
import {
  MdmOffsetMode,
  MdmProcessOptimizationResult,
  isMdmAiSampleSizeSupported,
  optimizeMdmOffset,
  parseMdmOffsetMode,
} from '@/lib/mdm-process-optimization'

const CHART_COLORS = MULTI_CURVE_COLORS.slice(0, 5)

// Define a simple type for our card data
type CardData = {
  id: string
  type: CalculatorCardType
  sourceId?: string
  data?: DataPoint[]
  result?: WeibullResult
  generationParameters?: CalculatorParameters
  generatedFrom?: CalculatorParameters
  methodId?: string // 'mle' | 'rrx' | 'rry' etc.
  mdmOffset: number
  mdmOffsetMode: MdmOffsetMode
  mdmOptimization?: MdmProcessOptimizationResult
  color: string
  fitMode?: 'fit' | 'manual' // Track mode: fit (sample based) or manual (param based)
  is3P?: boolean // New: Track 2P vs 3P mode
  last3PGamma?: number
  // 多数据源模式
  dataSources?: DataSource[] // 多选案例时的数据源列表
  activeDataSourceIndex?: number
  direction?: 'estimate' | 'generate'
  calculationProgress?: BatchProgress
}

function replaceSampleData(card: CardData, nextData: DataPoint[], generatedFrom?: CalculatorParameters): CardData {
  const failureCount = nextData.filter(point => point.status === 'F').length
  const mdmOffsetMode = card.mdmOffsetMode === 'ai' && !isMdmAiSampleSizeSupported(failureCount)
    ? 'fixed'
    : card.mdmOffsetMode
  return {
    ...card,
    data: nextData,
    result: undefined,
    generatedFrom,
    dataSources: undefined,
    activeDataSourceIndex: 0,
    fitMode: 'fit',
    mdmOffsetMode,
    mdmOptimization: undefined,
    calculationProgress: undefined,
  }
}

function CalculatorContent() {
  const searchParams = useSearchParams()
  const [cards, setCards] = useState<CardData[]>([])
  const [isMethodSelectorOpen, setIsMethodSelectorOpen] = useState(false)
  const [isDataEditorOpen, setIsDataEditorOpen] = useState(false)
  const [activeCardId, setActiveCardId] = useState<string | null>(null)
  const [calculationNotice, setCalculationNotice] = useState<CalculationNotice | null>(null)
  const [mdmOffsetUpdatingCardIds, setMdmOffsetUpdatingCardIds] = useState<Set<string>>(new Set())
  const calculationRequests = React.useRef(createLatestRequestTracker())
  const invalidateCalculation = (cardId: string) => {
    calculationRequests.current.invalidate(cardId)
    setMdmOffsetUpdatingCardIds(prev => {
      const next = new Set(prev)
      next.delete(cardId)
      return next
    })
  }
  useEffect(() => () => calculationRequests.current.clear(), [])

  // Initialize cards from URL or default
  useEffect(() => {
    if (cards.length > 0) return // Already initialized

    const init = async () => {
      const caseId = searchParams.get('caseId')
      const dataParam = searchParams.get('data')
      let initialData: DataPoint[] = []
      let selectedMethodId: string | undefined = undefined

      // Determine selected method from ?method= param, gated by calculatorEnabled
      const requestedMethod = searchParams.get('method')
      if (requestedMethod && isCalculatorEnabled(requestedMethod)) {
        selectedMethodId = requestedMethod
      }
      if (!selectedMethodId) {
        const enabledIds = getEnabledMethodIds()
        if (enabledIds.length > 0) {
          selectedMethodId = enabledIds[0]
        }
      }

      if (dataParam) {
        const parsed = dataParam
          .split(',')
          .map(value => Number(value.trim()))
          .filter(Number.isFinite)
        initialData = parsed.map((value, id) => ({ id, value, status: 'F' }))
      } else if (caseId) {
        try {
          const res = await fetch('/api/cases')
          const allCases = await res.json()
          const selectedCase = allCases.find((c: any) => c.id === caseId)

          if (selectedCase) {
            const dataRaw = selectedCase.data_raw || selectedCase.dataRaw || ''
            const lines = dataRaw.split('\n').filter((l: string) => l.trim())
            initialData = lines.map((line: string, idx: number) => {
              const parts = line.trim().split(/\s+/)
              return { id: idx, value: parseFloat(parts[0]), status: parts[1] === 'S' ? 'S' : 'F' }
            })
          }
        } catch (err) {
          console.error('Failed to load case:', err)
        }
      }

      const requestedMdmOffsetMode = parseMdmOffsetMode(searchParams.get('mdmOffsetMode'))
      const initialFailureCount = initialData.filter(point => point.status === 'F').length
      setCards([
        {
          id: '1',
          type: 'chart',
          data: initialData,
          generationParameters: getDefaultParameters(true),
          color: CHART_COLORS[0],
          fitMode: 'fit',
          is3P: true,
          last3PGamma: getDefaultParameters(true).gamma,
          methodId: selectedMethodId,
          mdmOffset: parseMdmOffsetOption(searchParams.get('offset')),
          mdmOffsetMode: requestedMdmOffsetMode === 'ai' && isMdmAiSampleSizeSupported(initialFailureCount)
            ? 'ai'
            : 'fixed',
        }
      ])
    }

    init()
    // Only run on mount - remove searchParams from deps to avoid infinite loop
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Handle adding new cards
  const handleAddCard = (type: CalculatorCardType, sourceId: string) => {
    const sourceCard = cards.find(c => c.id === sourceId)
    const source = sourceCard?.dataSources?.[sourceCard.activeDataSourceIndex ?? 0]
    const sourceData = source?.data ?? sourceCard?.data
    const sourceResult = source ? source.result : sourceCard?.result
    
    let newData: DataPoint[] | undefined = undefined
    let newResult: WeibullResult | undefined = undefined
    let newMethodId: string | undefined = undefined
    let newFitMode: 'fit' | 'manual' = 'manual'
    let newIs3P = true
    let newLast3PGamma = getDefaultParameters(true).gamma
    let newMdmOffset = MDM_DEFAULT_OFFSET
    let newMdmOffsetMode: MdmOffsetMode = 'fixed'
    let newMdmOptimization: MdmProcessOptimizationResult | undefined
    let generationParameters = getDefaultParameters(true)
    let generatedFrom: CalculatorParameters | undefined
    let inheritedSources: DataSource[] | undefined
    let inheritedIndex = 0
    if (type === 'data-group' && (!sourceCard?.dataSources || sourceCard.dataSources.length < 2)) return

    if (type === 'blank') {
      newData = undefined
      newResult = undefined
      newMethodId = undefined
      newFitMode = 'manual'
      newIs3P = true
    } else if (sourceCard) {
      newMethodId = sourceCard.methodId
      newIs3P = sourceCard.is3P !== false
      newFitMode = sourceCard.fitMode || 'manual'
      newLast3PGamma = sourceCard.last3PGamma ?? sourceCard.result?.gamma ?? newLast3PGamma
      newMdmOffset = sourceCard.mdmOffset
      newMdmOffsetMode = sourceCard.mdmOffsetMode
      newMdmOptimization = type === 'chart' ? sourceCard.mdmOptimization : undefined
      generationParameters = { ...sourceCard.generationParameters ?? getDefaultParameters(newIs3P) }

      if (type === 'data') {
        if (sourceData && sourceData.length > 0) {
          newData = sourceData.map(d => ({ ...d }))
          generatedFrom = source ? source.generatedFrom : sourceCard.generatedFrom
        }
        newResult = undefined
      } else if (type === 'data-group') {
        inheritedSources = inheritSampleSources(sourceCard.dataSources!)
        inheritedIndex = Math.max(0, Math.min(inheritedSources.length - 1, sourceCard.activeDataSourceIndex ?? 0))
        newData = inheritedSources[0].data
        generatedFrom = sourceCard.generatedFrom ? { ...sourceCard.generatedFrom } : undefined
      } else if (type === 'params') {
        newData = undefined
        if (sourceCard.direction !== 'generate' && sourceResult?.beta != null && sourceResult.eta != null && sourceCard.fitMode === 'fit') {
          generationParameters = { beta: sourceResult.beta, eta: sourceResult.eta, gamma: sourceResult.gamma }
        }
      } else if (type === 'method') {
        newData = undefined
        newResult = undefined
      } else if (type === 'chart') {
        if (sourceData && sourceData.length > 0) {
          newData = sourceData.map(d => ({ ...d }))
          generatedFrom = source ? source.generatedFrom : sourceCard.generatedFrom
        }
        if (sourceResult) {
          newResult = { ...sourceResult }
        }
      }
    }

    if (!newResult) newFitMode = 'fit'

    const nextColorIndex = (cards.length) % CHART_COLORS.length
    const newCard: CardData = {
      id: crypto.randomUUID(),
      type,
      sourceId: type === 'blank' ? undefined : sourceId,
      data: newData,
      result: newResult,
      generationParameters,
      generatedFrom,
      direction: type === 'params' ? 'generate' : 'estimate',
      methodId: newMethodId,
      color: CHART_COLORS[nextColorIndex],
      fitMode: newFitMode,
      is3P: newIs3P,
      last3PGamma: newLast3PGamma,
      mdmOffset: newMdmOffset,
      mdmOffsetMode: newMdmOffsetMode,
      mdmOptimization: newMdmOptimization,
      dataSources: inheritedSources,
      activeDataSourceIndex: inheritedIndex,
    }
    
    const sourceIndex = cards.findIndex(c => c.id === sourceId)
    if (sourceIndex !== -1) {
      const newCards = [...cards]
      newCards.splice(sourceIndex + 1, 0, newCard)
      setCards(newCards)
    } else {
      setCards(prev => [...prev, newCard])
    }
  }

  const handleMethodClick = (cardId: string) => {
    setActiveCardId(cardId)
    setIsMethodSelectorOpen(true)
  }

  const handleDataClick = (cardId: string) => {
    setActiveCardId(cardId)
    setIsDataEditorOpen(true)
  }

  const handleMdmOffsetChange = (cardId: string, mdmOffset: number) => {
    const currentCard = cards.find(card => card.id === cardId)
    if (!currentCard || currentCard.mdmOffset === mdmOffset) return
    invalidateCalculation(cardId)
    const nextCard: CardData = {
      ...currentCard,
      mdmOffset,
      mdmOptimization: undefined,
      fitMode: currentCard.fitMode,
    }
    setCards(prev => prev.map(card => {
      if (card.id !== cardId) return card
      return {
        ...card,
        mdmOffset,
        mdmOptimization: undefined,
        fitMode: card.fitMode,
      }
    }))
    if ((currentCard.result && currentCard.fitMode === 'fit') || currentCard.dataSources?.some(source => source.result)) {
      void recalculateMdmCard(nextCard)
    }
  }

  const handleMdmOffsetModeChange = (cardId: string, mdmOffsetMode: MdmOffsetMode) => {
    const currentCard = cards.find(card => card.id === cardId)
    if (!currentCard || currentCard.mdmOffsetMode === mdmOffsetMode) return
    invalidateCalculation(cardId)
    const nextCard: CardData = {
      ...currentCard,
      mdmOffsetMode,
      mdmOptimization: undefined,
      fitMode: currentCard.fitMode,
    }
    setCards(prev => prev.map(card => {
      if (card.id !== cardId) return card
      return {
        ...card,
        mdmOffsetMode,
        mdmOptimization: undefined,
        fitMode: card.fitMode,
      }
    }))
    if ((currentCard.result && currentCard.fitMode === 'fit') || currentCard.dataSources?.some(source => source.result)) {
      void recalculateMdmCard(nextCard)
    }
  }

  const handleMethodSelect = (methodId: string) => {
    console.log('[handleMethodSelect] methodId:', methodId, 'activeCardId:', activeCardId)
    if (activeCardId) {
      invalidateCalculation(activeCardId)
      setCards(prev => {
        const updated = prev.map(card => {
          if (card.id === activeCardId) {
            console.log('[handleMethodSelect] updating card:', card.id, 'old methodId:', card.methodId, 'new methodId:', methodId)
            if (card.methodId === methodId) return card
            return {
              ...card,
              methodId,
              result: undefined,
              dataSources: card.dataSources?.map(source => ({
                ...source,
                result: undefined,
                traceData: undefined,
                calculation: undefined, calculationError: undefined, calculationOffset: undefined,
                mdmOptimization: undefined, fixedComparison: undefined, archive: undefined,
              })),
              fitMode: 'fit' as const,
              mdmOptimization: undefined,
              calculationProgress: undefined,
            }
          }
          return card
        })
        console.log('[handleMethodSelect] cards updated:', updated.length)
        return updated
      })
    }
    setIsMethodSelectorOpen(false)
  }

  const handleDataSave = (newData: DataPoint[]) => {
    if (activeCardId) {
      invalidateCalculation(activeCardId)
      setCards(prev => prev.map(card => {
        if (card.id === activeCardId) {
          return {
            ...replaceSampleData(card, newData),
            dataSources: undefined // 单选时清空多数据源
          }
        }
        return card
      }))
    }
    setIsDataEditorOpen(false)
  }

  // 多选模式：处理多个数据源
  const handleDataSaveMulti = async (sources: DataSource[]) => {
    if (!activeCardId || sources.length === 0) return
    invalidateCalculation(activeCardId)

    // 第一组数据作为主数据
    const firstSource = sources[0]

    // 为每个数据源分配颜色和计算结果
    const dataSourcesWithResults: DataSource[] = sources.map((source, index) => ({
      ...source,
      color: MULTI_CURVE_COLORS[index % MULTI_CURVE_COLORS.length],
      result: undefined as WeibullResult | undefined // 初始为空，批量计算后填充
    }))

    setCards(prev => prev.map(card => {
      if (card.id === activeCardId) {
        return {
          ...replaceSampleData(card, firstSource.data),
          dataSources: dataSourcesWithResults
        }
      }
      return card
    }))

    setIsDataEditorOpen(false)
    // 不再自动触发批量计算，等用户点击"参数估计"时再计算
  }

  // 批量计算所有数据源
  const handleBatchCalculate = async (cardId: string, sources: DataSource[], requestTicket: number, cardOverride?: CardData) => {
    const card = cardOverride ?? cards.find(c => c.id === cardId)
    if (!card) return sources

    if (!card.methodId) {
      setCalculationNotice(getCalculationNotice(new CalculationError('请先选择估计方法。', undefined, undefined, { kind: 'input' })))
      return sources
    }

    return await estimateSampleSources(sources, async source => {
      const failureValues = source.data.filter(point => point.status === 'F').map(point => point.value)
      const optimization = card.methodId!.toLowerCase() === 'mdm' && card.mdmOffsetMode === 'ai'
        ? await optimizeMdmOffset(failureValues) : undefined
      const offset = optimization?.selected_delta ?? card.mdmOffset
      const calculation = await calculateWeibull({
        methodId: card.methodId!, data: source.data, trace: true,
        offset: card.methodId!.toLowerCase() === 'mdm' ? offset : undefined,
      })
      return { ...calculation, calculationOffset: offset, mdmOptimization: optimization }
    }, {
      isCurrent: () => calculationRequests.current.isCurrent(cardId, requestTicket),
      onProgress: (updated, progress) => setCards(previous => previous.map(item =>
        item.id === cardId && calculationRequests.current.isCurrent(cardId, requestTicket) ? {
          ...item, dataSources: updated, result: updated[0].result, fitMode: 'fit',
          mdmOptimization: updated[0].mdmOptimization, calculationProgress: progress,
        } : item)),
    })
  }

  const handleDataChange = (cardId: string, newData: DataPoint[], generatedFrom?: CalculatorParameters) => {
    invalidateCalculation(cardId)
    setCards(prev => prev.map(card => {
      if (card.id === cardId) {
        return replaceSampleData(card, newData, generatedFrom)
      }
      return card
    }))
  }

  const handleDataSourcesChange = (cardId: string, sources: DataSource[], generatedFrom?: CalculatorParameters, activeIndex = 0) => {
    if (!sources.length) return
    invalidateCalculation(cardId)
    setCards(previous => previous.map(card => card.id === cardId ? {
      ...replaceSampleData(card, sources[0].data, generatedFrom), dataSources: sources,
      result: sources[0].result, activeDataSourceIndex: activeIndex,
    } : card))
  }

  const calculateCardSnapshot = async (card: CardData, requestTicket: number) => {
    const modeFailure = getEstimationModeFailure(card.is3P !== false)
    if (modeFailure) {
      setCalculationNotice(getCalculationNotice(new CalculationError(modeFailure, undefined, undefined, { kind: 'input' })))
      return
    }

    // 如果有多数据源，执行批量计算
    if (card.dataSources && card.dataSources.length > 0) {
      await handleBatchCalculate(card.id, card.dataSources, requestTicket, card)
      return
    }

    // 单数据源计算
    if (!card.data || card.data.length === 0) {
      setCalculationNotice(getCalculationNotice(new CalculationError('请先输入样本。', undefined, undefined, { kind: 'input' })))
      return
    }
    if (!card.methodId) {
      setCalculationNotice(getCalculationNotice(new CalculationError('请先选择估计方法。', undefined, undefined, { kind: 'input' })))
      return
    }

    try {
      const failureValues = card.data.filter(point => point.status === 'F').map(point => point.value)
      const optimization = card.methodId.toLowerCase() === 'mdm' && card.mdmOffsetMode === 'ai'
        ? await optimizeMdmOffset(failureValues)
        : undefined
      const selectedOffset = optimization?.selected_delta ?? card.mdmOffset
      const { result } = await calculateWeibull({
        methodId: card.methodId,
        data: card.data,
        offset: card.methodId.toLowerCase() === 'mdm' ? selectedOffset : undefined,
      })
      const failure = getEstimateFailure(result)
      if (failure) throw new CalculationError(failure, undefined, undefined, { kind: 'solver' })

      if (!calculationRequests.current.isCurrent(card.id, requestTicket)) return
      setCards(prev => prev.map(c => c.id === card.id && calculationRequests.current.isCurrent(card.id, requestTicket) ? {
        ...c,
        result,
        mdmOptimization: optimization,
        fitMode: 'fit',
        last3PGamma: result.gamma,
      } : c))
    } catch (err) {
      if (!calculationRequests.current.isCurrent(card.id, requestTicket)) return
      setCalculationNotice(getCalculationNotice(err, card.methodId))
    }
  }

  const recalculateMdmCard = async (card: CardData) => {
    const requestTicket = calculationRequests.current.begin(card.id)
    setMdmOffsetUpdatingCardIds(prev => new Set(prev).add(card.id))
    try {
      await calculateCardSnapshot(card, requestTicket)
    } finally {
      if (!calculationRequests.current.isCurrent(card.id, requestTicket)) return
      setMdmOffsetUpdatingCardIds(prev => {
        const next = new Set(prev)
        next.delete(card.id)
        return next
      })
    }
  }

  const handleCalculate = async (cardId: string) => {
    const card = cards.find(c => c.id === cardId)
    if (!card) return
    await recalculateMdmCard(card)
  }

  const handleDeleteCard = (cardId: string) => {
    if (cards.length <= 1) {
      alert("请至少保留一张卡片。")
      return
    }
    invalidateCalculation(cardId)
    setCards(prev => prev.filter(c => c.id !== cardId))
  }

  const handleToggle3P = (cardId: string) => {
    invalidateCalculation(cardId)
    setCards(prev => prev.map(card => {
      if (card.id === cardId) {
        const mode = toggleParameterMode({
          is3P: card.is3P !== false,
          currentGamma: card.generationParameters?.gamma ?? card.result?.gamma,
          last3PGamma: card.last3PGamma ?? getDefaultParameters(true).gamma,
        })
        return {
          ...card,
          is3P: mode.is3P,
          last3PGamma: mode.last3PGamma,
          fitMode: 'fit',
          result: undefined,
          dataSources: card.dataSources?.map(source => ({ ...source, result: undefined, traceData: undefined,
            calculation: undefined, calculationError: undefined, calculationOffset: undefined,
            mdmOptimization: undefined, fixedComparison: undefined, archive: undefined })),
          mdmOptimization: undefined,
          calculationProgress: undefined,
        }
      }
      return card
    }))
  }

  const activeCard = cards.find(c => c.id === activeCardId)

  return (
    <>
      {calculationNotice && <CalculationNoticeDialog notice={calculationNotice} onClose={() => setCalculationNotice(null)} />}
      <MethodSelector 
        isOpen={isMethodSelectorOpen} 
        onClose={() => setIsMethodSelectorOpen(false)}
        onSelect={handleMethodSelect}
        currentMethodId={activeCard?.methodId}
      />
      
      <DataEditor
        isOpen={isDataEditorOpen}
        initialData={activeCard?.data}
        onClose={() => setIsDataEditorOpen(false)}
        onSave={handleDataSave}
        onSaveMulti={handleDataSaveMulti}
      />

      <section className="page-shell w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12 space-y-8 pb-32">
        {cards.map((card, index) => (
          <AnalysisCard
            key={card.id}
            id={card.id}
            index={index}
            data={card.data}
            initialDirection={card.direction ?? (card.type === 'params' ? 'generate' : 'estimate')}
            onDirectionChange={direction => setCards(previous => previous.map(item =>
              item.id === card.id ? { ...item, direction } : item))}
            generationParameters={card.generationParameters}
            generatedFrom={card.generatedFrom}
            calculationProgress={card.calculationProgress}
            result={card.result}
            methodId={card.methodId}
            mdmOffset={card.mdmOffset}
            mdmOffsetMode={card.mdmOffsetMode}
            mdmOptimization={card.mdmOptimization}
            color={card.color}
            fitMode={card.fitMode || 'manual'}
            is3P={!!card.is3P}
            dataSources={card.dataSources}
            activeDataSourceIndex={card.activeDataSourceIndex ?? 0}
            onActiveDataSourceChange={index => setCards(previous => previous.map(item =>
              item.id === card.id ? { ...item, activeDataSourceIndex: index } : item))}
            availableLayers={cards
              .map((c, i) => ({ ...c, originalIndex: i }))
              .filter(c => c.id !== card.id && c.result && c.fitMode === 'fit')
              .map(c => ({ id: c.id, name: `卡片 #${c.originalIndex + 1}`, color: c.color, result: c.result! }))
            }
            onAdd={handleAddCard}
            onMethodClick={() => handleMethodClick(card.id)}
            onMdmOffsetChange={(offset) => handleMdmOffsetChange(card.id, offset)}
            onMdmOffsetModeChange={(mode) => handleMdmOffsetModeChange(card.id, mode)}
            onDataClick={() => handleDataClick(card.id)}
            onDataChange={(newData, generatedFrom) => handleDataChange(card.id, newData, generatedFrom)}
            onDataSourcesChange={(sources, generatedFrom, activeIndex) => handleDataSourcesChange(card.id, sources, generatedFrom, activeIndex)}
            onGenerationParametersChange={parameters => setCards(previous => previous.map(item =>
              item.id === card.id ? { ...item, generationParameters: parameters } : item))}
            onToggle3P={() => handleToggle3P(card.id)}
            onCalculate={() => handleCalculate(card.id)}
            onDelete={() => handleDeleteCard(card.id)}
            isMdmOffsetUpdating={mdmOffsetUpdatingCardIds.has(card.id)}
          />
        ))}

        {cards.length === 0 && (
           <div className="text-center py-20 text-slate-400">
              暂无分析卡片，请刷新页面重新开始。
           </div>
        )}
      </section>
    </>
  )
}

export default function Home() {
  return (
    <Suspense fallback={<div className="p-20 text-center text-slate-400">加载计算器...</div>}>
      <CalculatorContent />
    </Suspense>
  )
}
