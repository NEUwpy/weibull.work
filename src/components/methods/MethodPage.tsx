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
import { DataPoint, WeibullResult, DataSource, MULTI_CURVE_COLORS, calculateMedianRanks, calculateWeibullParameters } from '@/lib/weibull'
import { calculateWeibull, CalculationError } from '@/hooks/useWeibullCalculation'
import { CalculationProcessViewer } from '@/components/shared/charts/CalculationProcessViewer'
import { getMethodCapability } from '@/lib/method-status'
import { MDM_DEFAULT_OFFSET, parseMdmOffsetOption } from '@/lib/calculator-state'
import MethodBuildStatus from '@/components/methods/MethodBuildStatus'

// Dynamic imports for heavy visualizers
const VariableFlowViewer = dynamic(() => import('@/components/methods/VariableFlowViewer'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
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

  const [data, setData] = useState<DataPoint[]>([])
  const [result, setResult] = useState<WeibullResult | undefined>(undefined)
  const [fitMode, setFitMode] = useState<'fit' | 'manual'>('fit')
  const [is3P, setIs3P] = useState(false)
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
  const offsetRecalculationTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const offsetRecalculationRequestRef = useRef(0)
  const invalidateCalculation = () => {
    offsetRecalculationRequestRef.current += 1
    if (offsetRecalculationTimerRef.current) clearTimeout(offsetRecalculationTimerRef.current)
    setTraceData(null)
    setCalculation(null)
    setCalculationError(null)
    setIsCalculating(false)
    setDataSources(previous => previous?.map(source => ({ ...source, result: undefined, traceData: undefined, calculation: undefined })))
  }
  const recordFailure = (error: unknown) => {
    setResult({ beta: null, eta: null, gamma: 0, rSquared: null, points: [], converged: false,
      failureReason: error instanceof Error ? error.message : String(error) })
    setTraceData(error instanceof CalculationError ? error.traceData ?? null : null)
    setCalculation(error instanceof CalculationError ? error.calculation ?? null : null)
    setCalculationError(error instanceof Error ? error.message : String(error))
  }

  useEffect(() => () => {
    if (offsetRecalculationTimerRef.current) {
      clearTimeout(offsetRecalculationTimerRef.current)
    }
  }, [])

  useEffect(() => {
    const betaParam = searchParams.get('trueBeta')
    const etaParam = searchParams.get('trueEta')
    const gammaParam = searchParams.get('trueGamma')

    if (betaParam && etaParam && gammaParam && (activeTab === null || activeTab === 'analysis')) {
      const beta = parseFloat(betaParam)
      const eta = parseFloat(etaParam)
      const gamma = parseFloat(gammaParam)

      setResult({
        beta,
        eta,
        gamma,
        rSquared: null,
        points: [],
        converged: true
      })
      setFitMode('manual')
      setIs3P(gamma !== 0)
      setActiveTab('analysis')
    }
  }, [searchParams])

  useEffect(() => {
    if (activeTab === 'analysis' && !result) {
      setResult({
        beta: 2,
        eta: 1000,
        gamma: 1000,
        rSquared: null,
        points: [],
        converged: true
      })
      setFitMode('manual')
      setIs3P(true)
    }
  }, [activeTab, result])

  useEffect(() => {
    const dataParam = searchParams.get('data')
    const requestKey = `${method.id}|${dataParam ?? ''}|${searchParams.get('offset') ?? ''}`
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
    setIs3P(true)
    setMdmOffset(requestedOffset)
    setIsCalculating(true)
    setCalculation(null)
    setCalculationError(null)
    const requestId = ++offsetRecalculationRequestRef.current

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
    setResult(undefined)
    setFitMode('fit')
    setDataSources(dataSourcesWithResults)
    setActiveSourceIndex(0)
    setIsDataEditorOpen(false)
  }

  const handleBatchCalculate = async (dataSourcesParam?: DataSource[]) => {
    const sourcesToCalculate = dataSourcesParam || dataSources
    if (!sourcesToCalculate || sourcesToCalculate.length === 0) return

    setIsCalculating(true)
    setCalculation(null)
    setCalculationError(null)
    const requestId = ++offsetRecalculationRequestRef.current
    let updatedSources = [...sourcesToCalculate]
    setResult(undefined)
    setTraceData(null)

    try {
      for (let i = 0; i < updatedSources.length; i++) {
        if (requestId !== offsetRecalculationRequestRef.current) return
        const source = updatedSources[i]
        try {
          const { result, traceData, calculation } = await calculateWeibull({
            methodId: method.id,
            data: source.data,
            trace: true,
            offset: method.id.toLowerCase() === 'mdm' ? mdmOffset : undefined,
          })

          updatedSources[i] = {
            ...updatedSources[i],
            result,
            traceData,
            calculation,
            calculationError: undefined,
          }
        } catch (err) {
          updatedSources[i] = { ...source, result: { beta: null, eta: null, gamma: 0, rSquared: null, points: [], converged: false,
              failureReason: err instanceof Error ? err.message : String(err) },
            calculation: err instanceof CalculationError ? err.calculation : undefined,
            traceData: err instanceof CalculationError ? err.traceData : undefined,
            calculationError: err instanceof Error ? err.message : String(err) }
        }
      }

      if (requestId !== offsetRecalculationRequestRef.current) return
      setDataSources(updatedSources)
      setActiveSourceIndex(0)
      setCalculation(updatedSources[0]?.calculation ?? null)

      if (updatedSources.length > 0 && updatedSources[0].traceData) {
        setTraceData(updatedSources[0].traceData)
      }

      if (updatedSources.length > 0 && updatedSources[0].result) {
        setResult(updatedSources[0].result)
        setFitMode('fit')
      }

    } catch (err: any) {
      console.error(err)
      alert(`后端计算错误: ${err.message}`)
    } finally {
      if (requestId === offsetRecalculationRequestRef.current) setIsCalculating(false)
    }
  }

  const handleDataChange = (newData: DataPoint[]) => {
    invalidateCalculation()
    setData(newData)
    setDataSources(undefined)
    setActiveSourceIndex(0)
    setResult(undefined)
    setFitMode('fit')
  }

  const handleParamsUpdate = (updates: Partial<WeibullResult>, mode?: 'fit' | 'manual') => {
    const selectedSource = dataSources?.[activeSourceIndex]
    const selectedData = selectedSource?.data ?? data
    const selectedResult = selectedSource?.result ?? result
    invalidateCalculation()
    setData(selectedData)
    setDataSources(undefined)
    setActiveSourceIndex(0)
    const baseResult = selectedResult || { beta: 1, eta: 100, gamma: 0, rSquared: 0, points: [] }
    const newResult = { ...baseResult, ...updates }
    let newPoints = selectedResult?.points || []
    if (updates.gamma !== undefined && !updates.points) {
      newPoints = calculateMedianRanks(selectedData, updates.gamma, method.id)
    } else if (updates.points !== undefined) {
      newPoints = updates.points
    }
    setResult({ ...newResult, points: newPoints })
    if (mode) setFitMode(mode)
  }

  const handleMdmOffsetChange = (offset: number) => {
    if (offset === mdmOffset) return
    setMdmOffset(offset)
    setIs3P(true)
    setCalculation(null)
    setTraceData(null)
    setCalculationError(null)
    setDataSources(previous => previous?.map(source => ({ ...source, calculation: undefined, traceData: undefined, result: undefined })))
    setResult(undefined)
    setFitMode('manual')
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
          const updatedSources = await Promise.all(dataSources.map(async source => {
            const calculation = await calculateWeibull({
              methodId: method.id,
              data: source.data,
              trace: true,
              offset,
            })
            return {
              ...source,
              result: calculation.result,
              traceData: calculation.traceData,
              calculation: calculation.calculation,
            }
          }))

          if (requestId !== offsetRecalculationRequestRef.current) return
          setDataSources(updatedSources)
          if (updatedSources[0]?.result) setResult(updatedSources[0].result)
          if (updatedSources[0]?.traceData) setTraceData(updatedSources[0].traceData)
          setCalculation(updatedSources[0]?.calculation ?? null)
          setActiveSourceIndex(0)
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
    const selectedSource = dataSources?.[activeSourceIndex]
    const selectedData = selectedSource?.data ?? data
    const selectedResult = selectedSource?.result ?? result
    invalidateCalculation()
    setData(selectedData)
    setDataSources(undefined)
    setActiveSourceIndex(0)
    const nextIs3P = !is3P
    let updates: Partial<WeibullResult> = {}
    let newPoints = selectedResult?.points || []

    if (!nextIs3P) {
      updates = { gamma: 0 }
      if (selectedData) {
        newPoints = calculateMedianRanks(selectedData, 0, method.id)
      }
    }
    setResult(selectedResult ? { ...selectedResult, ...updates, points: newPoints } : undefined)
    setIs3P(nextIs3P)
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
        ) : activeTab === 'flow' ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            {capability && capability.layer1.process.status === 'done' ? (
              <VariableFlowViewer methodId={method.id} />
            ) : (
              <MethodBuildStatus
                label="程序流程"
                status={capability?.layer1.process.status ?? 'todo'}
                reason={capability?.layer1.process.reason}
                evidence={capability?.layer1.process.evidence}
              />
            )}
          </div>
        ) : activeTab === 'lab' ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            {capability && ['done', 'in_progress'].includes(capability.layer2.calculation.status) ? (
              <div className="space-y-8">
            <AnalysisCard
              id="lab"
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
              onParamsUpdate={handleParamsUpdate}
              onToggle3P={handleToggle3P}
              onCalculate={handleCalculate}
              onMdmOffsetChange={handleMdmOffsetChange}
              onMethodClick={undefined}
              onDataClick={handleDataClick}
              hideCalculationProcessButton={true}
              isMdmOffsetUpdating={isCalculating && method.id.toLowerCase() === 'mdm'}
            />

            {!(dataSources?.length ? dataSources[activeSourceIndex]?.calculation : calculation) &&
              (dataSources?.length ? dataSources[activeSourceIndex]?.calculationError : calculationError) &&
              <p role="alert" className="rounded-xl bg-amber-50 px-4 py-3 text-base leading-relaxed text-amber-900">{dataSources?.length ? dataSources[activeSourceIndex]?.calculationError : calculationError}</p>}
            {(calculation || dataSources?.some(source => source.calculation)) && !isCalculating && (
              <CalculationProcessViewer
                calculation={dataSources?.length ? dataSources[activeSourceIndex]?.calculation : calculation}
                methodId={method.id}
              />
            )}

             {isCalculating && (
               <div className="bg-slate-50 rounded-3xl p-12 border border-slate-200 flex flex-col items-center justify-center">
                 <div className="animate-spin rounded-full h-12 w-12 border-4 border-indigo-200 border-t-indigo-600 mb-4"></div>
                 <p className="text-slate-600 font-bold">正在运行计算...</p>
               </div>
             )}
              </div>
            ) : (
              <MethodBuildStatus
                label="计算过程"
                status={capability?.layer2.calculation.status ?? 'todo'}
                reason={capability?.layer2.calculation.reason}
                evidence={capability?.layer2.calculation.evidence}
              />
            )}
          </div>
        ) : activeTab === 'analysis' ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            {capability && capability.layer2.analysis.status === 'done' ? (
              <div className="space-y-8">
            <AnalysisCard
              id="analysis"
              index={0}
              data={data}
              result={result}
              methodId={method.id}
              mdmOffset={mdmOffset}
              color="#10b981"
              fitMode={fitMode}
              is3P={is3P}
              dataSources={dataSources}
              availableLayers={[]}
              onAdd={() => {}}
              onDelete={() => {}}
              onDataChange={handleDataChange}
              onParamsUpdate={handleParamsUpdate}
              onToggle3P={handleToggle3P}
              onCalculate={handleCalculate}
              onMdmOffsetChange={handleMdmOffsetChange}
              onMethodClick={undefined}
              onDataClick={handleDataClick}
              hideCalculationProcessButton={true}
              isMdmOffsetUpdating={isCalculating && method.id.toLowerCase() === 'mdm'}
            />

            {result && result.beta !== null && result.eta !== null && (
              <div className="bg-slate-50 rounded-3xl p-8 max-[767px]:p-4 border border-slate-200">
                <ResultAnalysisLab
                  methodId={method.id}
                  trueBeta={result.beta}
                  trueEta={result.eta}
                  trueGamma={result.gamma}
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
