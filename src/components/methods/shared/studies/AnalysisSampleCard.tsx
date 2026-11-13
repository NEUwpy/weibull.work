'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import AnalysisCard from '@/components/calculator/AnalysisCard'
import { calculateSampleEstimate } from '@/hooks/useWeibullCalculation'
import { sampleBatchWorkbook, samplingTruth } from '@/lib/analysis-workbook'
import { estimateSampleSources, readCalculationBatch, type BatchProgress } from '@/lib/calculator-batch'
import { getDefaultParameters, MDM_DEFAULT_OFFSET, type CalculatorParameters } from '@/lib/calculator-state'
import { isMdmAiSampleSizeSupported, type MdmOffsetMode } from '@/lib/mdm-process-optimization'
import type { DataPoint, DataSource } from '@/lib/weibull'
import { SimulationWorkbook } from './SimulationWorkbook'

const cardId = 'method-result-analysis'
const color = '#10b981'

interface Props {
  methodId: string
  batchId: string | null
  initialTruth?: CalculatorParameters
  initialSize?: number
  initialOffset: number
  initialIs3P: boolean
}

export default function AnalysisSampleCard({ methodId, batchId, initialTruth, initialSize, initialOffset, initialIs3P }: Props) {
  const [parameters, setParameters] = useState(() => initialTruth ?? getDefaultParameters(initialIs3P))
  const [sources, setSources] = useState<DataSource[]>([])
  const [activeIndex, setActiveIndex] = useState(0)
  const [offset, setOffset] = useState(initialOffset)
  const [offsetMode, setOffsetMode] = useState<MdmOffsetMode>('fixed')
  const [is3P, setIs3P] = useState(initialIs3P)
  const [progress, setProgress] = useState<BatchProgress>()
  const [running, setRunning] = useState(false)
  const [handoffLoaded, setHandoffLoaded] = useState(!batchId)
  const [handoffError, setHandoffError] = useState('')
  const request = useRef(0)
  const isMdm = methodId === 'mdm'

  useEffect(() => {
    if (batchId) {
      const batch = readCalculationBatch(batchId, methodId, true)
      const truth = samplingTruth(batch?.sources)
      if (batch && truth) {
        setParameters(truth)
        setSources(batch.sources)
        setActiveIndex(batch.activeIndex)
        setOffset(isMdm ? batch.offset : MDM_DEFAULT_OFFSET)
        setOffsetMode(isMdm ? batch.analysis?.offsetMode ?? 'fixed' : 'fixed')
      } else {
        setHandoffError('原抽样批次在当前会话中不可用。可以在卡片上重新生成样本。')
      }
      setHandoffLoaded(true)
    }
    return () => { request.current += 1 }
  }, [batchId, methodId, isMdm])

  const truth = useMemo(() => samplingTruth(sources), [sources])
  const workbook = useMemo(() => {
    if (running || !truth || !sources.some(source => source.result || source.calculationError)) return
    return sampleBatchWorkbook(methodId, sources, truth, isMdm && offsetMode === 'fixed' ? offset : undefined)
  }, [running, truth, sources, methodId, isMdm, offsetMode, offset])

  function replaceSamples(next: DataSource[]) {
    setSources(next)
    setActiveIndex(0)
    setProgress(undefined)
    setHandoffError('')
    if (offsetMode === 'ai' && !isMdmAiSampleSizeSupported(next[0]?.data.length ?? 0)) setOffsetMode('fixed')
  }

  function replaceSingleSample(data: DataPoint[], generatedFrom?: CalculatorParameters) {
    replaceSamples(data.length && generatedFrom ? [{ id: cardId, name: '第 1 组', color, sourceType: 'custom', data, generatedFrom }] : [])
  }

  function updateMdmSettings(nextOffset: number, nextMode: MdmOffsetMode) {
    if (nextOffset === offset && nextMode === offsetMode) return
    setOffset(nextOffset)
    setOffsetMode(nextMode)
    setProgress(undefined)
    setSources(previous => previous.map(source => ({
      ...source, result: undefined, calculationError: undefined, calculationOffset: undefined, mdmOptimization: undefined,
    })))
  }

  async function estimate() {
    if (!truth || !is3P || running) return
    const pending = sources.filter(source => !source.result && !source.calculationError)
    const targets = pending.length ? pending : sources
    const targetIndices = new Map(targets.map((source, index) => [source.id, index]))
    const id = ++request.current
    setRunning(true)
    try {
      await estimateSampleSources(targets, source => calculateSampleEstimate(
        { methodId, data: source.data, offset: isMdm ? offset : undefined }, offsetMode,
      ), {
        isCurrent: () => request.current === id,
        onProgress: (updated, batchProgress) => {
          setSources(sources.map(source => updated[targetIndices.get(source.id) ?? -1] ?? source))
          setProgress(batchProgress)
        },
      })
    } finally {
      if (request.current === id) setRunning(false)
    }
  }

  const n = sources[0]?.data.length ?? 0
  if (!handoffLoaded) return <p role="status" className="text-sm text-slate-600">正在读取抽样批次…</p>
  return <section className="space-y-4" aria-label="现场抽样与估计">
    <AnalysisCard id={cardId} index={0} methodId={methodId} color={color} fitMode="fit"
      initialDirection={batchId && !handoffError ? 'estimate' : 'generate'} initialSampleSize={initialSize}
      initialGenerationCount={50} is3P={is3P} onToggle3P={() => setIs3P(value => !value)}
      generationParameters={parameters} onGenerationParametersChange={setParameters} generatedFrom={truth}
      data={sources[0]?.data} dataSources={sources.length ? sources : undefined}
      activeDataSourceIndex={activeIndex} onActiveDataSourceChange={setActiveIndex}
      onDataChange={replaceSingleSample} onDataSourcesChange={replaceSamples}
      onCalculate={estimate} canCalculate={!!truth} calculationActionLabel="参数估计"
      calculationProgress={progress} availableLayers={[]}
      mdmOffset={offset} mdmOffsetMode={offsetMode}
      onMdmOffsetChange={next => updateMdmSettings(next, 'fixed')}
      onMdmOffsetModeChange={next => updateMdmSettings(offset, next)}
      lockSampleEditing hideCalculationProcessButton hideResultAnalysisButton hideMdmOptimizationDetailsLink />
    {handoffError && <p role="status" className="text-sm text-slate-600">{handoffError}</p>}
    {workbook && truth && <SimulationWorkbook key={sources[0].groupId ?? n} n={n} truth={truth}
      group={workbook.group} runs={workbook.runs} filename={`${methodId}-n${n}-sample-batch`} />}
  </section>
}
