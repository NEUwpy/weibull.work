"use client"

import React, { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { useCallback } from 'react'
import MethodNavigation from '@/components/methods/MethodNavigation'
import { methodTabFromPath, methodHref, MethodTab } from '@/lib/method-navigation'
import { notFound } from 'next/navigation'
import { INITIAL_METHOD_TREE, MethodNode } from '@/lib/methods'
import { ArrowLeft, ExternalLink, Info, Sigma, BookOpen, Microscope, FileText, BarChart3, GitBranch, FlaskConical, FileCheck, Gauge, Scale, Play } from 'lucide-react'
import { cn } from '@/lib/utils'
import { AlgorithmDetail } from '@/components/methods/AlgorithmDetail'
import AnalysisCard from '@/components/calculator/AnalysisCard'
import ResultAnalysisLab from '@/components/methods/ResultAnalysisLab'
import DataEditor from '@/components/calculator/DataEditor'
import dynamic from 'next/dynamic'
import { DataPoint, WeibullResult, DataSource, MULTI_CURVE_COLORS } from '@/lib/weibull'
import { calculateWeibull, CalculationError } from '@/hooks/useWeibullCalculation'
import { CalculationProcessViewer } from '@/components/shared/charts/CalculationProcessViewer'
import { CalculationOverview } from '@/components/methods/CalculationSteps'
import { CalculationStageProvider } from '@/components/methods/CalculationSource'
import { CalculationInputCard } from '@/components/methods/CalculationInputCard'
import mmleProcessExample from '@/data/method-process-examples/mmle.json'
import { getMethodCapability } from '@/lib/method-status'
import { MDM_DEFAULT_OFFSET, parseMdmOffsetOption, getDefaultParameters, type CalculatorParameters } from '@/lib/calculator-state'
import MethodBuildStatus from '@/components/methods/MethodBuildStatus'
import { estimateSampleSources, readCalculationBatch, type BatchProgress } from '@/lib/calculator-batch'
import { CalculationBatch } from './CalculationBatch'
import { MDMBatchWorkspace } from './mdm/MDMBatchWorkspace'
import type { MDMProcessBatch } from '@/lib/calculation-records'

// Dynamic imports for heavy visualizers
const MDMVisualizer = dynamic(() => import('@/components/methods/mdm/visualizers/MDMVisualizer'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
const MLEVisualizer = dynamic(() => import('@/components/methods/mle/visualizers/MLEVisualizer'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
const CaseStudyViewer = dynamic(() => import('@/components/methods/CaseStudyViewer'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
const MonteCarloWorkbookViewer = dynamic(() => import('@/components/methods/shared/studies/MonteCarloWorkbookViewer'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
const MethodCompareViewer = dynamic(() => import('@/components/methods/shared/compare/MethodCompareViewer'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
import 'katex/dist/katex.min.css'
import katex from 'katex'

// KaTeX Renderer
const LatexRenderer = ({ math, block = false }: { math: string, block?: boolean }) => {
  try {
    const html = katex.renderToString(math, {
      throwOnError: false,
      displayMode: block,
      trust: true,
      strict: false
    })
    return <div className={cn("overflow-x-auto", block ? "py-2" : "inline")} dangerouslySetInnerHTML={{ __html: html }} />
  } catch (e) {
    return <span className="text-red-500 font-mono text-xs">LaTeX Error</span>
  }
}

// Finder Helper
function findMethodById(methodId: string): { category: MethodNode; method?: MethodNode } | null {
  for (const category of INITIAL_METHOD_TREE) {
    if (category.id === methodId) return { category }
    if (category.children) {
      const method = category.children.find(m => m.id === methodId)
      if (method) return { category, method }
    }
  }
  return null
}

interface MethodDetailPageProps {
  params: { methodId: string }
}

export default function MethodDetailPage({ params }: MethodDetailPageProps) {
  const { methodId } = params
  const result = findMethodById(methodId)

  if (!result) return notFound()

  const { category, method } = result

  if (!method) return <CategoryOverview category={category} />

  return <MethodDetail key={method.id} category={category} method={method} />
}

function CategoryOverview({ category }: { category: MethodNode }) {
  return (
    <section className="page-shell w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-3">
          <span className="px-3 py-1 bg-amber-600 text-white text-xs font-bold rounded-full">{category.shortName}</span>
        </div>
        <h1 className="text-3xl font-black text-slate-900 mb-2">{category.name}</h1>
      </div>
      <div className="mb-8 bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Info className="text-amber-500" size={18} />
          <span className="font-bold text-slate-900">类别概述</span>
        </div>
        <p className="text-slate-600 leading-relaxed">{category.description}</p>
      </div>
      <div className="mb-8 p-6 bg-slate-900 rounded-2xl overflow-x-auto">
        <div className="flex items-center gap-2 mb-4">
          <Sigma className="text-amber-400" size={20} />
          <span className="text-sm font-bold text-slate-300 uppercase tracking-wider">核心公式</span>
        </div>
        <div className="text-white"><LatexRenderer math={category.formula} block /></div>
      </div>
      <div>
        <h2 className="text-xl font-bold text-slate-900 mb-4">该类别下的具体算法</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {category.children?.map((child) => (
            <Link key={child.id} href={`/methods/${child.id}`} className="p-5 bg-white rounded-2xl border border-slate-200 hover:border-amber-300 hover:shadow-md transition-all">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-mono text-amber-600 bg-amber-50 px-2 py-0.5 rounded border border-amber-100">{child.shortName}</span>
              </div>
              <h3 className="font-bold text-slate-800 mb-2">{child.name}</h3>
              <p className="text-sm text-slate-500 line-clamp-2">{child.description}</p>
            </Link>
          ))}
        </div>
      </div>
    </section>
  )
}

function MethodDetail({ category, method }: { category: MethodNode; method: MethodNode }) {
  const searchParams = useSearchParams()
  const pathname = usePathname()
  const router = useRouter()
  const activeTab = methodTabFromPath(pathname)
  const setActiveTab = useCallback((tab: MethodTab) => {
    const href = methodHref(method.id, tab, searchParams)
    if (href.split('?')[0] !== pathname) router.push(href, { scroll: false })
  }, [method.id, pathname, router, searchParams])
  const capability = getMethodCapability(method.id)
  const sourceAvailable = capability?.layer1.process.status === 'done'

  const [data, setData] = useState<DataPoint[]>([])
  const [result, setResult] = useState<WeibullResult | undefined>(undefined)
  const [fitMode, setFitMode] = useState<'fit' | 'manual'>('fit')
  const [generationParameters, setGenerationParameters] = useState<CalculatorParameters>(() => getDefaultParameters(true))
  const [generatedFrom, setGeneratedFrom] = useState<CalculatorParameters>()
  const [calculationProgress, setCalculationProgress] = useState<BatchProgress>()
  const [archivedBatch, setArchivedBatch] = useState<MDMProcessBatch | null>(null)
  const [is3P, setIs3P] = useState(true)
  const [dataSources, setDataSources] = useState<DataSource[] | undefined>(undefined)
  const [traceData, setTraceData] = useState<any>(null)
  const [calculation, setCalculation] = useState<unknown>(null)
  const [calculationError, setCalculationError] = useState<string | null>(null)
  const [isCalculating, setIsCalculating] = useState(false)
  const [isDataEditorOpen, setIsDataEditorOpen] = useState(false)
  const [activeSourceIndex, setActiveSourceIndex] = useState(0)
  const [mdmOffset, setMdmOffset] = useState(() => (
    method.id.toLowerCase() === 'mdm'
      ? parseMdmOffsetOption(searchParams.get('offset'))
      : MDM_DEFAULT_OFFSET
  ))
  const handledDataParamRef = useRef<string | null>(null)
  const handledBatchRef = useRef<string | null>(null)
  const offsetRecalculationTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const offsetRecalculationRequestRef = useRef(0)
  const showCalculation = !!(calculation || dataSources?.some(source => source.calculation)) && (!isCalculating || method.id === 'mdm')
  const activeCalculationError = dataSources?.[activeSourceIndex]?.calculationError ?? calculationError
  const invalidateCalculation = () => {
    setArchivedBatch(null)
    setCalculationProgress(undefined)
    offsetRecalculationRequestRef.current += 1
    if (offsetRecalculationTimerRef.current) clearTimeout(offsetRecalculationTimerRef.current)
    setTraceData(null)
    setCalculation(null)
    setCalculationError(null)
    setIsCalculating(false)
    setDataSources(previous => previous?.map(source => ({ ...source, result: undefined, traceData: undefined, calculation: undefined,
      calculationError: undefined, calculationOffset: undefined, mdmOptimization: undefined, fixedComparison: undefined, archive: undefined })))
  }
  const recordFailure = (error: unknown) => {
    setResult({ beta: null, eta: null, gamma: 0, rSquared: null, points: [], converged: false,
      failureReason: error instanceof Error ? error.message : String(error) })
    setTraceData(error instanceof CalculationError ? error.traceData ?? null : null)
    setCalculation(error instanceof CalculationError ? error.calculation ?? null : null)
    setCalculationError(error instanceof Error ? error.message : String(error))
  }

  useEffect(() => () => {
    offsetRecalculationRequestRef.current += 1
    handledBatchRef.current = null
    handledDataParamRef.current = null
    if (offsetRecalculationTimerRef.current) {
      clearTimeout(offsetRecalculationTimerRef.current)
    }
  }, [])

  useEffect(() => {
    const betaParam = searchParams.get('trueBeta')
    const etaParam = searchParams.get('trueEta')
    const gammaParam = searchParams.get('trueGamma')
    if (activeTab === null || activeTab === 'analysis') setIs3P(searchParams.get('model') !== '2p')

    if (betaParam && etaParam && gammaParam && (activeTab === null || activeTab === 'analysis')) {
      const beta = parseFloat(betaParam)
      const eta = parseFloat(etaParam)
      const gamma = parseFloat(gammaParam)
      setGenerationParameters({ beta, eta, gamma })

      setActiveTab('analysis')
    }
  }, [searchParams])

  useEffect(() => {
    const dataParam = searchParams.get('data')
    const requestKey = `${method.id}|${dataParam ?? ''}|${searchParams.get('offset') ?? ''}|${searchParams.get('model') ?? '3p'}`
    if (!dataParam || handledDataParamRef.current === requestKey || (activeTab !== null && activeTab !== 'lab')) return
    handledDataParamRef.current = requestKey

    const parsed = dataParam.split(',').map(Number).filter(n => Number.isFinite(n))
    const points: DataPoint[] = parsed.map((value, index) => ({ id: index, value, status: 'F' }))
    if (points.length === 0) return

    const requestedOffset = method.id.toLowerCase() === 'mdm'
      ? parseMdmOffsetOption(searchParams.get('offset'))
      : MDM_DEFAULT_OFFSET

    setActiveTab('lab')
    setData(points)
    const samplingValues = ['trueBeta', 'trueEta', 'trueGamma'].map(name => searchParams.get(name))
    const [beta, eta, gamma] = samplingValues.map(Number)
    const origin = samplingValues.every(value => value !== null) && [beta, eta, gamma].every(Number.isFinite) && beta > 0 && eta > 0
      ? { beta, eta, gamma } : undefined
    setGeneratedFrom(origin)
    if (origin) setGenerationParameters(origin)
    const requestedIs3P = searchParams.get('model') !== '2p'
    setIs3P(requestedIs3P)
    setMdmOffset(requestedOffset)
    setCalculation(null)
    setCalculationError(null)
    const requestId = ++offsetRecalculationRequestRef.current
    if (!requestedIs3P) {
      setResult(undefined)
      setTraceData(null)
      setIsCalculating(false)
      return
    }
    setIsCalculating(true)

    calculateWeibull({
      methodId: method.id,
      data: points,
      trace: true,
      offset: method.id.toLowerCase() === 'mdm' ? requestedOffset : undefined,
    }).then(({ result: calculatedResult, traceData: calculatedTrace, calculation: calculatedRecord }) => {
      if (requestId !== offsetRecalculationRequestRef.current) return
      setResult(calculatedResult)
      setTraceData(calculatedTrace ?? null)
      setCalculation(calculatedRecord ?? null)
      setFitMode('fit')
    }).catch((error) => {
      if (requestId === offsetRecalculationRequestRef.current) recordFailure(error)
    }).finally(() => {
      if (requestId === offsetRecalculationRequestRef.current) setIsCalculating(false)
    })
  }, [method.id, searchParams])

  const handleDataClick = () => {
    setIsDataEditorOpen(true)
  }

  const handleDataSave = (newData: DataPoint[]) => {
    invalidateCalculation()
    setData(newData)
    setGeneratedFrom(undefined)
    setResult(undefined)
    setFitMode('fit')
    setDataSources(undefined)
    setIsDataEditorOpen(false)
  }

  const handleDataSaveMulti = (sources: DataSource[]) => {
    if (sources.length === 0) return
    invalidateCalculation()

    const firstSource = sources[0]

    const dataSourcesWithResults: DataSource[] = sources.map((source, index) => ({
      ...source,
      color: MULTI_CURVE_COLORS[index % MULTI_CURVE_COLORS.length],
      result: undefined as WeibullResult | undefined
    }))

    setData(firstSource.data)
    setGeneratedFrom(undefined)
    setResult(undefined)
    setFitMode('fit')
    setDataSources(dataSourcesWithResults)
    setActiveSourceIndex(0)
    setIsDataEditorOpen(false)
  }

  const handleBatchCalculate = async (dataSourcesParam?: DataSource[], offset = mdmOffset) => {
    const sourcesToCalculate = dataSourcesParam || dataSources
    if (!sourcesToCalculate || sourcesToCalculate.length === 0) return

    setIsCalculating(true)
    setArchivedBatch(null)
    setCalculation(null)
    setCalculationError(null)
    const requestId = ++offsetRecalculationRequestRef.current
    try {
      const updated = await estimateSampleSources(sourcesToCalculate, async source => {
        const calculation = await calculateWeibull({
          methodId: method.id, data: source.data, trace: true,
          offset: method.id.toLowerCase() === 'mdm' ? offset : undefined,
        })
        return { ...calculation, calculationOffset: offset }
      }, {
        isCurrent: () => requestId === offsetRecalculationRequestRef.current,
        onProgress: (updated, progress) => {
          if (requestId !== offsetRecalculationRequestRef.current) return
          setDataSources(updated)
          setCalculationProgress(progress)
          setResult(updated[0].result)
          setTraceData(updated[0].traceData)
          setCalculation(updated[0].calculation ?? null)
          setFitMode('fit')
        },
      })
      return updated
    } finally {
      if (requestId === offsetRecalculationRequestRef.current) setIsCalculating(false)
    }
  }

  const handleDataSourcesChange = (sources: DataSource[], origin?: CalculatorParameters, activeIndex = 0) => {
    if (!sources.length) return
    invalidateCalculation()
    setData(sources[0].data)
    setDataSources(sources)
    setGeneratedFrom(origin)
    setResult(sources[0].result)
    setActiveSourceIndex(activeIndex)
    setCalculationProgress(undefined)
    setFitMode('fit')
  }

  const loadArchivedSources = async (sources: DataSource[], origin: CalculatorParameters | undefined, offset: number) => {
    handleDataSourcesChange(sources, origin)
    setMdmOffset(offset)
    setIs3P(true)
    const archive = sources[0]?.archive
    if (!archive || method.id !== 'mdm') return
    const requestId = offsetRecalculationRequestRef.current
    try {
      const query = new URLSearchParams({ n: String(archive.n), delta: String(archive.delta) })
      const response = await fetch('/api/monte-carlo/' + encodeURIComponent(archive.id) + '/process?' + query)
      if (requestId !== offsetRecalculationRequestRef.current) return
      if (!response.ok) {
        setCalculationError('这批归档保留了样本和估计值，尚无完整计算记录；点击参数估计可按当前算法复算。')
        return
      }
      const process: MDMProcessBatch = await response.json()
      if (requestId !== offsetRecalculationRequestRef.current) return
      setArchivedBatch(process)
      const restored = sources.map(source => {
        const run = process.runs.find(run => run.id === source.archive?.runId)
        return !run ? source : { ...source, result: { beta: run.beta, eta: run.eta, gamma: run.gamma,
          rSquared: run.rSquared, points: [], converged: true } }
      })
      setDataSources(restored)
      setResult(restored[0]?.result)
    } catch {
      if (requestId === offsetRecalculationRequestRef.current) setCalculationError('归档计算记录读取失败，可重新载入。')
    }
  }

  useEffect(() => {
    const id = searchParams.get('sampleBatch')
    const key = method.id + '|' + id
    if (!id || handledBatchRef.current === key || activeTab !== 'lab') return
    handledBatchRef.current = key
    let batch: ReturnType<typeof readCalculationBatch>
    try { batch = readCalculationBatch(id, method.id, true) } catch { batch = null }
    if (!batch) {
      setCalculationError('这批样本在当前会话中不可用，请从原卡片重新打开。')
      return
    }
    setIs3P(searchParams.get('model') !== '2p')
    if (batch.sources[0]?.archive) {
      void loadArchivedSources(batch.sources, batch.generatedFrom, batch.offset)
      setActiveSourceIndex(batch.activeIndex)
    } else {
      handleDataSourcesChange(batch.sources, batch.generatedFrom, batch.activeIndex)
      setMdmOffset(batch.offset)
      if (searchParams.get('model') !== '2p' && !batch.sources.every(source => source.calculation || source.calculationError)) {
        void handleBatchCalculate(batch.sources, batch.offset)
      }
    }
  }, [searchParams, method.id, activeTab])

  const handleDataChange = (newData: DataPoint[], generatedFrom?: CalculatorParameters) => {
    invalidateCalculation()
    setData(newData)
    setGeneratedFrom(generatedFrom)
    setDataSources(undefined)
    setActiveSourceIndex(0)
    setResult(undefined)
    setFitMode('fit')
  }

  const handleMdmOffsetChange = (offset: number) => {
    if (offset === mdmOffset) return
    setMdmOffset(offset)
    if ((!result || fitMode !== 'fit') && !dataSources?.some(source => source.result)) return
    setIs3P(true)
    setCalculationError(null)
    setIsCalculating(true)

    const requestId = ++offsetRecalculationRequestRef.current
    if (offsetRecalculationTimerRef.current) {
      clearTimeout(offsetRecalculationTimerRef.current)
    }

    if ((!dataSources || dataSources.length === 0) && data.length === 0) {
      setIsCalculating(false)
      return
    }

    offsetRecalculationTimerRef.current = setTimeout(async () => {
      try {
        if (dataSources && dataSources.length > 0) {
          if (requestId !== offsetRecalculationRequestRef.current) return
          await handleBatchCalculate(dataSources, offset)
        } else if (data.length > 0) {
          const calculation = await calculateWeibull({
            methodId: method.id,
            data,
            trace: true,
            offset,
          })

          if (requestId !== offsetRecalculationRequestRef.current) return
          setResult(calculation.result)
          setTraceData(calculation.traceData ?? null)
          setCalculation(calculation.calculation ?? null)
        }

        if (requestId === offsetRecalculationRequestRef.current) {
          setFitMode('fit')
        }
      } catch (error) {
        if (requestId === offsetRecalculationRequestRef.current) {
          recordFailure(error)
        }
      } finally {
        if (requestId === offsetRecalculationRequestRef.current) {
          setIsCalculating(false)
        }
      }
    }, 180)
  }

  const handleCalculate = async () => {
    setIs3P(true)
    offsetRecalculationRequestRef.current += 1
    if (offsetRecalculationTimerRef.current) {
      clearTimeout(offsetRecalculationTimerRef.current)
      offsetRecalculationTimerRef.current = null
    }

    if (dataSources && dataSources.length > 0) {
      await handleBatchCalculate(dataSources)
      return
    }

    if (!data || data.length === 0) return

    setIsCalculating(true)
    setCalculation(null)
    setTraceData(null)
    setCalculationError(null)
    const requestId = ++offsetRecalculationRequestRef.current
    try {
      const { result: newResult, traceData, calculation } = await calculateWeibull({
        methodId: method.id,
        data,
        trace: true,
        offset: method.id.toLowerCase() === 'mdm' ? mdmOffset : undefined,
      })

      if (requestId !== offsetRecalculationRequestRef.current) return
      setResult(newResult)
      setCalculation(calculation ?? null)
      setFitMode('fit')

      if (traceData) {
        setTraceData(traceData)
      }
    } catch (err: any) {
      if (requestId === offsetRecalculationRequestRef.current) recordFailure(err)
    } finally {
      if (requestId === offsetRecalculationRequestRef.current) setIsCalculating(false)
    }
  }

  const handleToggle3P = () => {
    invalidateCalculation()
    setResult(undefined)
    setFitMode('fit')
    setIs3P(previous => !previous)
  }

  return (
    <>
      <DataEditor
        isOpen={isDataEditorOpen}
        initialData={data}
        onClose={() => setIsDataEditorOpen(false)}
        onSave={handleDataSave}
        onSaveMulti={handleDataSaveMulti}
      />

      <section className="page-shell w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12">
        <MethodNavigation method={method} activeTab={activeTab} />

      {/* Content Area */}
      <div className={cn("min-h-[500px] min-w-0", activeTab !== "examples" && "max-[1279px]:[&_table]:block max-[1279px]:[&_table]:max-w-full max-[1279px]:[&_table]:overflow-x-auto max-[1279px]:[&_pre]:max-w-full max-[1279px]:[&_pre]:overflow-x-auto")}>
        {activeTab === null ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
             {capability && capability.layer1.theory.status === 'done' ? (
               'slug' in method && method.slug ? (
                 <AlgorithmDetail slug={method.slug} />
               ) : (
                 <div className="p-12 text-center text-slate-400 bg-white rounded-3xl border border-slate-200">
                   暂无详细文档
                 </div>
               )
             ) : (
               <MethodBuildStatus
                 label="原理文档"
                 status={capability?.layer1.theory.status ?? 'todo'}
                 reason={capability?.layer1.theory.reason}
                 evidence={capability?.layer1.theory.evidence}
               />
             )}
          </div>
        ) : activeTab === 'lab' ? (
          <CalculationStageProvider key={method.id} method={method.id} sourceAvailable={sourceAvailable}>
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            {method.id.toLowerCase() === 'mmle' ? <div className="space-y-6" data-method-calculation-example="mmle">
              <section className="rounded-2xl border border-slate-200 bg-white px-4 py-4 sm:px-5">
                <h2 className="text-lg font-semibold text-slate-800">计算示例 · n = {mmleProcessExample.sample.length}</h2>
                <details className="mt-2 text-base text-slate-600">
                  <summary className="cursor-pointer">查看本次样本</summary>
                  <p className="mt-3 break-words tabular-nums">{mmleProcessExample.sample.join('，')}</p>
                </details>
              </section>
              <CalculationProcessViewer calculation={mmleProcessExample.calculation} methodId="mmle" />
            </div> : capability && ['done', 'in_progress'].includes(capability.layer2.calculation.status) ? (
              <div className="space-y-8">
            <CalculationInputCard allowArchive={method.id === 'mdm'} onLoadSources={loadArchivedSources} sampleCard={
            <AnalysisCard
              id="lab"
              initialDirection="estimate"
              generationParameters={generationParameters}
              generatedFrom={generatedFrom}
              calculationProgress={calculationProgress}
              onDataSourcesChange={handleDataSourcesChange}
              onGenerationParametersChange={setGenerationParameters}
              index={0}
              calculationActionLabel="计算并展示过程"
              data={data}
              result={result}
              methodId={method.id}
              mdmOffset={mdmOffset}
              color="#4f46e5"
              fitMode={fitMode}
              is3P={is3P}
              dataSources={dataSources}
              activeDataSourceIndex={activeSourceIndex}
              onActiveDataSourceChange={setActiveSourceIndex}
              availableLayers={[]}
              onAdd={() => {}}
              onDelete={() => {}}
              onDataChange={handleDataChange}
              onToggle3P={handleToggle3P}
              onCalculate={handleCalculate}
              onMdmOffsetChange={handleMdmOffsetChange}
              onMethodClick={undefined}
              onDataClick={handleDataClick}
              hideCalculationProcessButton={true}
              isMdmOffsetUpdating={isCalculating && method.id.toLowerCase() === 'mdm'}
            />}>

            {!(dataSources?.length ? dataSources[activeSourceIndex]?.calculation : calculation) &&
              activeCalculationError &&
              <p role="alert" className="rounded-xl bg-amber-50 px-4 py-3 text-base leading-relaxed text-amber-900">{activeCalculationError}</p>}
            <CalculationBatch methodId={method.id} sources={dataSources} activeIndex={activeSourceIndex}
              onSelect={setActiveSourceIndex} origin={generatedFrom}>
            {archivedBatch ? <MDMBatchWorkspace process={archivedBatch}
              selectedRun={dataSources?.[activeSourceIndex]?.archive?.runId ?? null}
              onSelect={id => { const index = dataSources?.findIndex(source => source.archive?.runId === id); if (index != null && index >= 0) setActiveSourceIndex(index) }} /> : method.id === 'mdm' ? <MDMVisualizer
                traceData={dataSources?.length ? dataSources[activeSourceIndex]?.traceData : traceData}
                calculation={dataSources?.length ? dataSources[activeSourceIndex]?.calculation : calculation}
                rSquared={(dataSources?.length ? dataSources[activeSourceIndex]?.result : result)?.rSquared}
                mdmOffset={mdmOffset}
                onMdmOffsetChange={handleMdmOffsetChange}
                offsetStale={isCalculating}
                isOffsetUpdating={isCalculating}
              /> : method.id === 'mle' ? <MLEVisualizer
                traceData={dataSources?.length ? dataSources[activeSourceIndex]?.traceData : traceData}
                calculation={dataSources?.length ? dataSources[activeSourceIndex]?.calculation : calculation}
                rSquared={(dataSources?.length ? dataSources[activeSourceIndex]?.result : result)?.rSquared}
                isUpdating={isCalculating}
              /> : showCalculation ? <CalculationProcessViewer
                calculation={dataSources?.length ? dataSources[activeSourceIndex]?.calculation : calculation}
                methodId={method.id}
              /> : sourceAvailable && <CalculationOverview method={method.id} />}
            </CalculationBatch>
            </CalculationInputCard>

              </div>
            ) : <div className="space-y-4">
              {sourceAvailable && <CalculationOverview method={method.id} />}
              <MethodBuildStatus
                label="计算过程"
                status={capability?.layer2.calculation.status ?? 'todo'}
                reason={capability?.layer2.calculation.reason}
                evidence={capability?.layer2.calculation.evidence}
              />
            </div>}
            </div>
          </CalculationStageProvider>
        ) : activeTab === 'analysis' ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            {capability && capability.layer2.analysis.status === 'done' ? (
              <div className="space-y-8">
            <AnalysisCard
              id="analysis"
              initialDirection="generate"
              generationParameters={generationParameters}
              generatedFrom={generatedFrom}
              calculationProgress={calculationProgress}
              onDataSourcesChange={handleDataSourcesChange}
              onGenerationParametersChange={setGenerationParameters}
              index={0}
              data={data}
              result={result}
              methodId={method.id}
              mdmOffset={mdmOffset}
              color="#10b981"
              fitMode={fitMode}
              is3P={is3P}
              dataSources={dataSources}
              activeDataSourceIndex={activeSourceIndex}
              onActiveDataSourceChange={setActiveSourceIndex}
              availableLayers={[]}
              onAdd={() => {}}
              onDelete={() => {}}
              onDataChange={handleDataChange}
              onToggle3P={handleToggle3P}
              onCalculate={handleCalculate}
              onMdmOffsetChange={handleMdmOffsetChange}
              onMethodClick={undefined}
              onDataClick={handleDataClick}
              hideCalculationProcessButton={true}
              isMdmOffsetUpdating={isCalculating && method.id.toLowerCase() === 'mdm'}
            />

            {generationParameters.beta > 0 && generationParameters.eta > 0 && (
              <div className="bg-slate-50 rounded-3xl p-8 max-[767px]:p-4 border border-slate-200">
                <ResultAnalysisLab
                  methodId={method.id}
                  trueBeta={generationParameters.beta}
                  trueEta={generationParameters.eta}
                  trueGamma={is3P ? generationParameters.gamma : 0}
                />
              </div>
            )}
              </div>
            ) : (
              <MethodBuildStatus
                label="结果分析"
                status={capability?.layer2.analysis.status ?? 'todo'}
                reason={capability?.layer2.analysis.reason}
                evidence={capability?.layer2.analysis.evidence}
              />
            )}
          </div>
        ) : activeTab === 'examples' ? (
          <MonteCarloWorkbookViewer methodId={method.id} />
        ) : activeTab === 'cases' ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            {capability && capability.layer3.verification.status === 'done' ? (
              <CaseStudyViewer methodId={method.id} />
            ) : (
              <MethodBuildStatus
                label="可信性验证"
                status={capability?.layer3.verification.status ?? 'todo'}
                reason={capability?.layer3.verification.reason}
                evidence={capability?.layer3.verification.evidence}
              />
            )}
          </div>
        ) : activeTab === 'compare' ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            <MethodCompareViewer currentMethodId={method.id} />
          </div>
        ) : null}
      </div>
    </section>
    </>
  )
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
      <div className="text-xs font-bold text-slate-400">{label}</div>
      <div className="text-lg font-black text-slate-800 mt-1">{value}</div>
    </div>
  )
}
