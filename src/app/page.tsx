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
  calculateMedianRanks,
  calculateWeibullParameters
} from '@/lib/weibull'
import MethodSelector from '@/components/calculator/MethodSelector'
import DataEditor from '@/components/calculator/DataEditor'
import { getApiBaseUrl } from '@/lib/config'

const CHART_COLORS = [
  '#3b82f6', // Blue-500
  '#ef4444', // Red-500
  '#10b981', // Emerald-500
  '#f59e0b', // Amber-500
  '#8b5cf6', // Violet-500
]

// Helper to generate random Weibull data
function generateRandomData(n: number, beta: number, eta: number, gamma: number = 0): DataPoint[] {
  return Array.from({ length: n }, (_, i) => {
    // Inverse transform sampling: t = gamma + eta * (-ln(U))^(1/beta)
    const u = Math.random()
    const t = gamma + eta * Math.pow(-Math.log(u), 1 / beta)
    return { id: i, value: t, status: 'F' }
  })
}

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
  // 多数据源模式
  dataSources?: DataSource[] // 多选案例时的数据源列表
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
      let initialResult: WeibullResult | undefined = undefined
      let selectedCaseIdFound = 'mle'

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
            const points = calculateMedianRanks(initialData, 0)
            initialResult = calculateWeibullParameters(points, 0)
          }
        } catch (err) {
          console.error('Failed to load case:', err)
        }
      }

      // Fallback if no case found or error
      if (initialData.length === 0) {
        initialData = generateRandomData(20, 2.5, 100, 0)
        const points = calculateMedianRanks(initialData, 0)
        initialResult = calculateWeibullParameters(points, 0)
      }

      setCards([
        {
          id: '1',
          type: 'chart',
          data: initialData,
          result: initialResult,
          color: CHART_COLORS[0],
          fitMode: 'fit',
          is3P: false,
          methodId: 'mle'
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
    let newFitMode: 'fit' | 'manual' = 'fit'
    let newIs3P = false

    if (type === 'blank') {
      newData = undefined
      newResult = undefined
      newMethodId = undefined
      newFitMode = 'fit'
      newIs3P = false
    } else if (sourceCard) {
      newMethodId = sourceCard.methodId
      newIs3P = sourceCard.is3P || false
      newFitMode = sourceCard.fitMode || 'fit'

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
      is3P: newIs3P
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
      const currentCard = cards.find(c => c.id === activeCardId)
      const currentGamma = currentCard?.result?.gamma || 0
      const points = calculateMedianRanks(newData, currentGamma)
      const result = calculateWeibullParameters(points, currentGamma)

      setCards(prev => prev.map(card => {
        if (card.id === activeCardId) {
          return {
            ...card,
            data: newData,
            result: result,
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
    const firstGamma = 0
    const points = calculateMedianRanks(firstSource.data, firstGamma)
    const result = calculateWeibullParameters(points, firstGamma)

    // 为每个数据源分配颜色和计算结果
    const dataSourcesWithResults: DataSource[] = sources.map((source, index) => ({
      ...source,
      color: MULTI_CURVE_COLORS[index % MULTI_CURVE_COLORS.length],
      result: undefined as WeibullResult | undefined // 初始为空，批量计算后填充
    }))

    setCards(prev => prev.map(card => {
      if (card.id === activeCardId) {
        return {
          ...card,
          data: firstSource.data,
          result: result,
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

    const methodId = card.methodId || 'lre'

    // 逐个计算
    for (let i = 0; i < sources.length; i++) {
      const source = sources[i]
      try {
        // 构建请求体 - MDM 方法需要 offset 参数
        const requestBody: any = {
          method: methodId,
          data: source.data.filter(d => d.status === 'F').map(d => d.value)
        }

        // MDM 方法添加 offset
        if (methodId.toLowerCase() === 'mdm') {
          requestBody.offset = 0.1
        }

        const response = await fetch(`${getApiBaseUrl()}/calculate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestBody)
        })

        if (response.ok) {
          const res = await response.json()
          const gamma = res.gamma || 0
          const points = calculateMedianRanks(source.data, gamma)

          // 更新对应 dataSouce 的 result
          setCards(prev => prev.map(c => {
            if (c.id === cardId && c.dataSources) {
              const updatedSources = c.dataSources.map((ds, idx) => {
                if (idx === i) {
                  return {
                    ...ds,
                    result: {
                      beta: res.beta,
                      eta: res.eta,
                      gamma,
                      rSquared: res.rSquared,
                      points,
                      converged: res.converged
                    }
                  }
                }
                return ds
              })
              return { ...c, dataSources: updatedSources }
            }
            return c
          }))
        }
      } catch (err) {
        console.error(`Failed to calculate source ${i}:`, err)
      }
    }
  }

  const handleDataChange = (cardId: string, newData: DataPoint[]) => {
    const currentCard = cards.find(c => c.id === cardId)
    const currentGamma = currentCard?.result?.gamma || 0
    const points = calculateMedianRanks(newData, currentGamma)

    setCards(prev => prev.map(card => {
      if (card.id === cardId) {
        return { 
          ...card, 
          data: newData,
          result: card.result ? { ...card.result, points: points } : undefined,
          fitMode: 'fit'
        }
      }
      return card
    }))
  }

  const handleParamsUpdate = (cardId: string, updates: Partial<WeibullResult>, mode?: 'fit' | 'manual') => {
    setCards(prev => prev.map(card => {
      if (card.id === cardId) {
        const baseResult = card.result || { beta: 1, eta: 100, gamma: 0, rSquared: 0, points: [] }
        const newResult = { ...baseResult, ...updates }
        let newPoints = card.result?.points || []
        // Only recalculate points if gamma changed AND points not already provided in updates
        if (updates.gamma !== undefined && !updates.points && card.data) {
           newPoints = calculateMedianRanks(card.data, updates.gamma)
        } else if (updates.points !== undefined) {
          newPoints = updates.points
        }
        return {
          ...card,
          result: { ...newResult, points: newPoints },
          fitMode: mode || card.fitMode
        }
      }
      return card
    }))
  }

  const handleCalculate = async (cardId: string) => {
    const card = cards.find(c => c.id === cardId)
    if (!card) return

    // 如果有多数据源，执行批量计算
    if (card.dataSources && card.dataSources.length > 0) {
      await handleBatchCalculate(cardId, card.dataSources)
      return
    }

    // 单数据源计算
    if (!card.data) return

    try {
      // 构建请求体 - MDM 方法需要 offset 参数
      const requestBody: any = {
        method: card.methodId || 'lre',
        data: card.data.filter(d => d.status === 'F').map(d => d.value)
      }

      // MDM 方法添加 offset
      if (card.methodId?.toLowerCase() === 'mdm') {
        requestBody.offset = 0.1
      }

      const response = await fetch(`${getApiBaseUrl()}/calculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      })

      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || '计算失败')
      }

      const res = await response.json()

      // Check convergence (including unbounded)
      if (res.converged === false || res.converged === 'unbounded') {
        // Return result with actual values (0) but marked as not converged
        const newPoints = calculateMedianRanks(card.data, res.gamma || 0)
        const newResult: WeibullResult = {
          beta: res.beta,
          eta: res.eta,
          gamma: res.gamma || 0,
          rSquared: res.rSquared,
          points: newPoints,
          converged: res.converged  // Keep 'unbounded' or false
        }
        setCards(prev => prev.map(c => c.id === cardId ? { ...c, result: newResult, fitMode: 'fit' } : c))
        return
      }

      const newPoints = calculateMedianRanks(card.data, res.gamma || 0)
      const newResult: WeibullResult = {
        beta: res.beta,
        eta: res.eta,
        gamma: res.gamma || 0,
        rSquared: res.rSquared,
        points: newPoints,
        converged: true
      }

      setCards(prev => prev.map(c => c.id === cardId ? { ...c, result: newResult, fitMode: 'fit' } : c))
    } catch (err: any) {
      console.error(err)
      alert(`后端计算错误: ${err.message}\n请确保 Python main.py 已在 8001 端口运行。`)
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
        const nextIs3P = !card.is3P
        let updates: Partial<WeibullResult> = {}
        let newPoints = card.result?.points || []

        if (!nextIs3P) {
          updates = { gamma: 0 }
          if (card.data) {
             newPoints = calculateMedianRanks(card.data, 0)
          }
        }
        const newResult = card.result ? { ...card.result, ...updates, points: newPoints } : undefined
        return { ...card, is3P: nextIs3P, result: newResult }
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
            fitMode={card.fitMode || 'fit'}
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