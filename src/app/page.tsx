"use client"

import React, { useState, useEffect, Suspense } from 'react'
import AnalysisCard from '@/components/AnalysisCard'
import { LayoutGrid } from 'lucide-react'
import { useSearchParams } from 'next/navigation'
import {
  DataPoint,
  WeibullResult,
  calculateMedianRanks,
  calculateWeibullParameters
} from '@/lib/weibull'
import MethodSelector from '@/components/MethodSelector'
import DataEditor from '@/components/DataEditor'

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
}

function CalculatorContent() {
  const searchParams = useSearchParams()
  const [cards, setCards] = useState<CardData[]>([])
  const [isMethodSelectorOpen, setIsMethodSelectorOpen] = useState(false)
  const [isDataEditorOpen, setIsDataEditorOpen] = useState(false)
  const [activeCardId, setActiveCardId] = useState<string | null>(null)

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
  }, [searchParams, cards.length])

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
    if (activeCardId) {
      setCards(prev => prev.map(card => {
        if (card.id === activeCardId) {
          return { ...card, methodId }
        }
        return card
      }))
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
            result: result 
          }
        }
        return card
      }))
    }
    setIsDataEditorOpen(false)
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
        if (updates.gamma !== undefined && card.data) {
           newPoints = calculateMedianRanks(card.data, updates.gamma)
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
    if (!card || !card.data) return

    try {
      const response = await fetch('http://localhost:8001/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          method: card.methodId || 'lre',
          data: card.data.filter(d => d.status === 'F').map(d => d.value)
        })
      })

      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || '计算失败')
      }

      const res = await response.json()
      const newPoints = calculateMedianRanks(card.data, res.gamma)
      const newResult: WeibullResult = {
        beta: res.beta,
        eta: res.eta,
        gamma: res.gamma,
        rSquared: res.rSquared,
        points: newPoints
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