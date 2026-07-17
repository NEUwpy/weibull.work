"use client"

import React, { useState, useEffect, Suspense } from 'react'
import AnalysisCard from '@/components/calculator/AnalysisCard'
import { LayoutGrid } from 'lucide-react'
import { useSearchParams } from 'next/navigation'
import {
  DataPoint,
  WeibullResult,
  DataSource,
  MULTI_CURVE_COLORS,
  calculateMedianRanks
} from '@/lib/weibull'
import MethodSelector from '@/components/calculator/MethodSelector'
import DataEditor from '@/components/calculator/DataEditor'
import { calculateWeibull } from '@/hooks/useWeibullCalculation'
import { isCalculatorEnabled, getEnabledMethodIds } from '@/lib/method-status'
import {
  createDefaultParameterResult,
  generateWeibullSample,
  getDefaultParameters,
  getEstimateFailure,
  getEstimationModeFailure,
  toggleParameterMode,
} from '@/lib/calculator-state'

const CHART_COLORS = MULTI_CURVE_COLORS.slice(0, 5)

// Define a simple type for our card data
type CardData = {
  id: string
  type: 'blank' | 'method' | 'params' | 'chart' | 'data'
  sourceId?: string
  data?: DataPoint[]
  result?: WeibullResult
  methodId?: string // 'mle' | 'rrx' | 'rry' etc.
  color: string
  fitMode?: 'fit' | 'manual' // Track mode: fit (sample based) or manual (param based)
  is3P?: boolean // New: Track 2P vs 3P mode
  last3PGamma?: number
  // 多数据源模式
  dataSources?: DataSource[] // 多选案例时的数据源列表
}

function createManualResult(data: DataPoint[], is3P = true): WeibullResult {
  const parameters = getDefaultParameters(is3P)
  return {
    ...parameters,
    rSquared: null,
    points: calculateMedianRanks(data, parameters.gamma),
    converged: true,
  }
}

function preserveParametersForData(card: CardData, nextData: DataPoint[]): CardData {
  const result = card.result || createManualResult(nextData, card.is3P !== false)
  return {
    ...card,
    data: nextData,
    result: {
      ...result,
      points: calculateMedianRanks(nextData, result.gamma),
    },
    fitMode: 'manual',
  }
}

function CalculatorContent() {
  const searchParams = useSearchParams()
  const [cards, setCards] = useState<CardData[]>([])
  const [isMethodSelectorOpen, setIsMethodSelectorOpen] = useState(false)
  const [isDataEditorOpen, setIsDataEditorOpen] = useState(false)
  const [activeCardId, setActiveCardId] = useState<string | null>(null)

  // Global render count to detect infinite loops
  const renderCountRef = React.useRef(0)
  renderCountRef.current += 1
  if (renderCountRef.current % 50 === 0) {
    console.warn('[page.tsx] Render count:', renderCountRef.current)
  }
  if (renderCountRef.current > 200) {
    console.error('[page.tsx] INFINITE LOOP DETECTED!')
  }

  // Initialize cards from URL or default
  useEffect(() => {
    if (cards.length > 0) return // Already initialized

    const init = async () => {
      const caseId = searchParams.get('caseId')
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

      if (caseId) {
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

      // Fallback if no case found or error
      if (initialData.length === 0) {
        initialData = generateWeibullSample(20, getDefaultParameters(true))
      }

      const initialResult: WeibullResult = createDefaultParameterResult(
        initialData,
        calculateMedianRanks,
      )

      setCards([
        {
          id: '1',
          type: 'chart',
          data: initialData,
          result: initialResult,
          color: CHART_COLORS[0],
          fitMode: 'manual',
          is3P: true,
          last3PGamma: initialResult.gamma,
          methodId: selectedMethodId,
        }
      ])
    }

    init()
    // Only run on mount - remove searchParams from deps to avoid infinite loop
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Handle adding new cards
  const handleAddCard = (type: 'method' | 'data' | 'params' | 'chart' | 'blank', sourceId: string) => {
    const sourceCard = cards.find(c => c.id === sourceId)
    
    let newData: DataPoint[] | undefined = undefined
    let newResult: WeibullResult | undefined = undefined
    let newMethodId: string | undefined = undefined
    let newFitMode: 'fit' | 'manual' = 'manual'
    let newIs3P = true
    let newLast3PGamma = getDefaultParameters(true).gamma

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

      if (type === 'data') {
        if (sourceCard.data && sourceCard.data.length > 0) {
          newData = sourceCard.data.map(d => ({ ...d }))
        }
        newResult = undefined
      } else if (type === 'params') {
        newData = undefined
        if (sourceCard.result) {
          newResult = { ...sourceCard.result }
        }
      } else if (type === 'method') {
        newData = undefined
        newResult = undefined
      } else if (type === 'chart') {
        if (sourceCard.data && sourceCard.data.length > 0) {
          newData = sourceCard.data.map(d => ({ ...d }))
        }
        if (sourceCard.result) {
          newResult = { ...sourceCard.result }
        }
      }
    }

    if (!newResult) {
      newResult = createManualResult(newData || [], newIs3P)
      newFitMode = 'manual'
    }

    const nextColorIndex = (cards.length) % CHART_COLORS.length
    const newCard: CardData = {
      id: Date.now().toString(),
      type,
      sourceId: type === 'blank' ? undefined : sourceId,
      data: newData,
      result: newResult,
      methodId: newMethodId,
      color: CHART_COLORS[nextColorIndex],
      fitMode: newFitMode,
      is3P: newIs3P,
      last3PGamma: newLast3PGamma,
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

  const handleMethodSelect = (methodId: string) => {
    console.log('[handleMethodSelect] methodId:', methodId, 'activeCardId:', activeCardId)
    if (activeCardId) {
      setCards(prev => {
        const updated = prev.map(card => {
          if (card.id === activeCardId) {
            console.log('[handleMethodSelect] updating card:', card.id, 'old methodId:', card.methodId, 'new methodId:', methodId)
            return { ...card, methodId }
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
      setCards(prev => prev.map(card => {
        if (card.id === activeCardId) {
          return {
            ...preserveParametersForData(card, newData),
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
          ...preserveParametersForData(card, firstSource.data),
          dataSources: dataSourcesWithResults
        }
      }
      return card
    }))

    setIsDataEditorOpen(false)
    // 不再自动触发批量计算，等用户点击"参数估计"时再计算
  }

  // 批量计算所有数据源
  const handleBatchCalculate = async (cardId: string, sources: DataSource[]) => {
    const card = cards.find(c => c.id === cardId)
    if (!card) return sources

    if (!card.methodId) {
      alert('请先选择方法')
      return sources
    }

    try {
      const results = await Promise.all(sources.map(async source => {
        const { result } = await calculateWeibull({
          methodId: card.methodId!,
          data: source.data,
        })
        const failure = getEstimateFailure(result)
        if (failure) throw new Error(failure)
        return result
      }))

      setCards(prev => prev.map(c => {
        if (c.id !== cardId || !c.dataSources) return c
        return {
          ...c,
          result: results[0],
          dataSources: c.dataSources.map((source, index) => ({
            ...source,
            result: results[index],
          })),
          fitMode: 'fit',
          last3PGamma: results[0].gamma,
        }
      }))
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      console.error('Batch parameter estimation failed:', err)
      alert(`参数估计失败: ${message}`)
    }

    return sources
  }

  const handleDataChange = (cardId: string, newData: DataPoint[]) => {
    setCards(prev => prev.map(card => {
      if (card.id === cardId) {
        return preserveParametersForData(card, newData)
      }
      return card
    }))
  }

  const handleParamsUpdate = (cardId: string, updates: Partial<WeibullResult>, mode?: 'fit' | 'manual') => {
    setCards(prev => prev.map(card => {
      if (card.id === cardId) {
        const baseResult = card.result || createManualResult(card.data || [], card.is3P !== false)
        const newResult = { ...baseResult, ...updates }
        let newPoints = card.result?.points || []
        // Only recalculate points if gamma changed AND points not already provided in updates
        if (updates.gamma !== undefined && !updates.points && card.data) {
           newPoints = calculateMedianRanks(card.data, updates.gamma)
        } else if (updates.points !== undefined) {
          newPoints = updates.points
        }
        const nextLast3PGamma = card.is3P !== false && updates.gamma !== undefined && Number.isFinite(updates.gamma)
          ? updates.gamma
          : card.last3PGamma
        return {
          ...card,
          result: { ...newResult, points: newPoints },
          fitMode: mode || card.fitMode,
          last3PGamma: nextLast3PGamma,
        }
      }
      return card
    }))
  }

  const handleCalculate = async (cardId: string) => {
    const card = cards.find(c => c.id === cardId)
    if (!card) return

    const modeFailure = getEstimationModeFailure(card.is3P !== false)
    if (modeFailure) {
      alert(modeFailure)
      return
    }

    // 如果有多数据源，执行批量计算
    if (card.dataSources && card.dataSources.length > 0) {
      await handleBatchCalculate(cardId, card.dataSources)
      return
    }

    // 单数据源计算
    if (!card.data || card.data.length === 0) {
      alert('请先输入样本')
      return
    }
    if (!card.methodId) {
      alert('请先选择方法')
      return
    }

    try {
      const { result } = await calculateWeibull({
        methodId: card.methodId,
        data: card.data,
      })
      const failure = getEstimateFailure(result)
      if (failure) throw new Error(failure)

      setCards(prev => prev.map(c => c.id === cardId ? {
        ...c,
        result,
        fitMode: 'fit',
        last3PGamma: result.gamma,
      } : c))
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      console.error('Parameter estimation failed:', err)
      alert(`参数估计失败: ${message}`)
    }
  }

  const handleDeleteCard = (cardId: string) => {
    if (cards.length <= 1) {
      alert("请至少保留一张卡片。")
      return
    }
    setCards(prev => prev.filter(c => c.id !== cardId))
  }

  const handleToggle3P = (cardId: string) => {
    setCards(prev => prev.map(card => {
      if (card.id === cardId) {
        const result = card.result || createManualResult(card.data || [], card.is3P !== false)
        const mode = toggleParameterMode({
          is3P: card.is3P !== false,
          currentGamma: result.gamma,
          last3PGamma: card.last3PGamma ?? getDefaultParameters(true).gamma,
        })
        return {
          ...card,
          is3P: mode.is3P,
          last3PGamma: mode.last3PGamma,
          fitMode: 'manual',
          result: {
            ...result,
            gamma: mode.gamma,
            points: calculateMedianRanks(card.data || [], mode.gamma),
          },
        }
      }
      return card
    }))
  }

  const activeCard = cards.find(c => c.id === activeCardId)

  return (
    <>
      <MethodSelector 
        isOpen={isMethodSelectorOpen} 
        onClose={() => setIsMethodSelectorOpen(false)}
        onSelect={handleMethodSelect}
      />
      
      <DataEditor
        isOpen={isDataEditorOpen}
        initialData={activeCard?.data}
        onClose={() => setIsDataEditorOpen(false)}
        onSave={handleDataSave}
        onSaveMulti={handleDataSaveMulti}
      />

      <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12 space-y-8 pb-32">
        {cards.map((card, index) => (
          <AnalysisCard
            key={card.id}
            id={card.id}
            index={index}
            data={card.data}
            result={card.result}
            methodId={card.methodId}
            color={card.color}
            fitMode={card.fitMode || 'manual'}
            is3P={!!card.is3P}
            dataSources={card.dataSources}
            availableLayers={cards
              .map((c, i) => ({ ...c, originalIndex: i }))
              .filter(c => c.id !== card.id && c.result)
              .map(c => ({ id: c.id, name: `卡片 #${c.originalIndex + 1}`, color: c.color, result: c.result! }))
            }
            onAdd={(type, sid) => handleAddCard(type as any, sid)}
            onMethodClick={() => handleMethodClick(card.id)}
            onDataClick={() => handleDataClick(card.id)}
            onDataChange={(newData) => handleDataChange(card.id, newData)}
            onParamsUpdate={(updates, mode) => handleParamsUpdate(card.id, updates, mode)}
            onToggle3P={() => handleToggle3P(card.id)}
            onCalculate={() => handleCalculate(card.id)}
            onDelete={() => handleDeleteCard(card.id)}
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
