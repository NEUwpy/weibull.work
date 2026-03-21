"use client"

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
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
import { getApiBaseUrl } from '@/lib/config'

// Dynamic imports for heavy visualizers
const VariableFlowViewer = dynamic(() => import('@/components/methods/VariableFlowViewer'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
const MLEVisualizer = dynamic(() => import('@/components/methods/mle/visualizers/MLEVisualizer'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
const WMLEVisualizer = dynamic(() => import('@/components/methods/wmle/visualizers/WMLEVisualizer'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
const MDMVisualizer = dynamic(() => import('@/components/methods/mdm/visualizers/MDMVisualizer'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
const CaseStudyViewer = dynamic(() => import('@/components/methods/CaseStudyViewer'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
const GenericStudyViewer = dynamic(() => import('@/components/methods/shared/studies/GenericStudyViewer'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
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

  return <MethodDetail category={category} method={method} />
}

function CategoryOverview({ category }: { category: MethodNode }) {
  return (
    <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12">
      <div className="mb-8">
        <Link href="/methods" className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-800 transition-colors font-bold mb-4">
          <ArrowLeft size={18} /> 返回方法总览
        </Link>
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
  const [activeTab, setActiveTab] = useState<null | 'flow' | 'lab' | 'analysis' | 'examples' | 'cases' | 'compare'>(null)

  const [data, setData] = useState<DataPoint[]>([])
  const [result, setResult] = useState<WeibullResult | undefined>(undefined)
  const [fitMode, setFitMode] = useState<'fit' | 'manual'>('fit')
  const [is3P, setIs3P] = useState(false)
  const [dataSources, setDataSources] = useState<DataSource[] | undefined>(undefined)
  const [traceData, setTraceData] = useState<any>(null)
  const [isCalculating, setIsCalculating] = useState(false)
  const [isDataEditorOpen, setIsDataEditorOpen] = useState(false)
  const [activeSourceIndex, setActiveSourceIndex] = useState(0)

  useEffect(() => {
    const betaParam = searchParams.get('trueBeta')
    const etaParam = searchParams.get('trueEta')
    const gammaParam = searchParams.get('trueGamma')

    if (betaParam && etaParam && gammaParam) {
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
    if (dataParam) {
      setActiveTab('lab')
      try {
        const parsed = dataParam.split(',').map(Number).filter(n => !isNaN(n))
        const points: DataPoint[] = parsed.map((v, i) => ({ id: i, value: v, status: 'F' }))
        setData(points)
        const calculatedPoints = calculateMedianRanks(points, 0)
        const res = calculateWeibullParameters(calculatedPoints, 0)
        setResult(res)
      } catch(e) {
        console.error("Failed to parse data", e)
      }
    }
  }, [searchParams])

  const handleDataClick = () => {
    setIsDataEditorOpen(true)
  }

  const handleDataSave = (newData: DataPoint[]) => {
    const currentGamma = result?.gamma || 0
    const points = calculateMedianRanks(newData, currentGamma)
    const res = calculateWeibullParameters(points, currentGamma)
    setData(newData)
    setResult(res)
    setFitMode('fit')
    setDataSources(undefined)
    setIsDataEditorOpen(false)
  }

  const handleDataSaveMulti = (sources: DataSource[]) => {
    if (sources.length === 0) return

    const firstSource = sources[0]
    const firstGamma = 0
    const points = calculateMedianRanks(firstSource.data, firstGamma)
    const res = calculateWeibullParameters(points, firstGamma)

    const dataSourcesWithResults: DataSource[] = sources.map((source, index) => ({
      ...source,
      color: MULTI_CURVE_COLORS[index % MULTI_CURVE_COLORS.length],
      result: undefined as WeibullResult | undefined
    }))

    setData(firstSource.data)
    setResult(res)
    setFitMode('fit')
    setDataSources(dataSourcesWithResults)
    setActiveSourceIndex(0)
    setIsDataEditorOpen(false)
  }

  const handleBatchCalculate = async (dataSourcesParam?: DataSource[]) => {
    const sourcesToCalculate = dataSourcesParam || dataSources
    if (!sourcesToCalculate || sourcesToCalculate.length === 0) return

    setIsCalculating(true)
    let updatedSources = [...sourcesToCalculate]

    try {
      for (let i = 0; i < updatedSources.length; i++) {
        const source = updatedSources[i]

        const requestBody: any = {
          method: method.id,
          data: source.data.filter(d => d.status === 'F').map(d => d.value),
          trace: true
        }

        if (method.id.toLowerCase() === 'mdm') {
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

          updatedSources[i] = {
            ...updatedSources[i],
            result: {
              beta: res.beta,
              eta: res.eta,
              gamma,
              rSquared: res.rSquared,
              points,
              converged: res.converged
            },
            traceData: res.trace_data
          }
        }
      }

      setDataSources(updatedSources)

      if (updatedSources.length > 0 && updatedSources[0].traceData) {
        setTraceData(updatedSources[0].traceData)
      }

      if (updatedSources.length > 0 && updatedSources[0].result) {
        setResult(updatedSources[0].result)
      }

    } catch (err: any) {
      console.error(err)
      alert(`后端计算错误: ${err.message}`)
    } finally {
      setIsCalculating(false)
    }
  }

  const handleDataChange = (newData: DataPoint[]) => {
    const currentGamma = result?.gamma || 0
    const points = calculateMedianRanks(newData, currentGamma)
    setData(newData)
    setResult(prev => prev ? { ...prev, points } : undefined)
    setFitMode('fit')
  }

  const handleParamsUpdate = (updates: Partial<WeibullResult>, mode?: 'fit' | 'manual') => {
    const baseResult = result || { beta: 1, eta: 100, gamma: 0, rSquared: 0, points: [] }
    const newResult = { ...baseResult, ...updates }
    let newPoints = result?.points || []
    if (updates.gamma !== undefined && !updates.points && data) {
      newPoints = calculateMedianRanks(data, updates.gamma)
    } else if (updates.points !== undefined) {
      newPoints = updates.points
    }
    setResult({ ...newResult, points: newPoints })
    if (mode) setFitMode(mode)
  }

  const handleCalculate = async () => {
    if (dataSources && dataSources.length > 0) {
      await handleBatchCalculate(dataSources)
      return
    }

    if (!data || data.length === 0) return

    setIsCalculating(true)
    try {
      const requestBody: any = {
        method: method.id,
        data: data.filter(d => d.status === 'F').map(d => d.value),
        trace: true
      }

      if (method.id.toLowerCase() === 'mdm') {
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

      if (res.converged === false) {
        const newPoints = calculateMedianRanks(data, res.gamma || 0)
        const newResult: WeibullResult = {
          beta: res.beta,
          eta: res.eta,
          gamma: res.gamma || 0,
          rSquared: res.rSquared,
          points: newPoints,
          converged: false
        }
        setResult(newResult)
        setFitMode('fit')

        if (res.trace_data) {
          setTraceData(res.trace_data)
        }

        setIsCalculating(false)
        return
      }

      const newPoints = calculateMedianRanks(data, res.gamma || 0)
      const newResult: WeibullResult = {
        beta: res.beta,
        eta: res.eta,
        gamma: res.gamma || 0,
        rSquared: res.rSquared,
        points: newPoints,
        converged: true
      }
      setResult(newResult)
      setFitMode('fit')

      if (res.trace_data) {
        setTraceData(res.trace_data)
      }
    } catch (err: any) {
      console.error(err)
      alert(`后端计算错误: ${err.message}\n请确保 Python main.py 已在 8001 端口运行。`)
    } finally {
      setIsCalculating(false)
    }
  }

  const handleToggle3P = () => {
    const nextIs3P = !is3P
    let updates: Partial<WeibullResult> = {}
    let newPoints = result?.points || []

    if (!nextIs3P) {
      updates = { gamma: 0 }
      if (data) {
        newPoints = calculateMedianRanks(data, 0)
      }
    }
    setResult(prev => prev ? { ...prev, ...updates, points: newPoints } : undefined)
    setIs3P(nextIs3P)
  }

  useEffect(() => {
    const dataParam = searchParams.get('data')
    if (dataParam && data.length > 0 && !traceData) {
      handleCalculate()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <>
      <DataEditor
        isOpen={isDataEditorOpen}
        initialData={data}
        onClose={() => setIsDataEditorOpen(false)}
        onSave={handleDataSave}
        onSaveMulti={handleDataSaveMulti}
      />

      <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12">
        {/* Header */}
        <div className="mb-8">
          <Link href="/methods" className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-800 transition-colors font-bold mb-6">
            <ArrowLeft size={18} /> 返回方法总览
          </Link>
          <div className="flex items-center justify-between">
            {/* 方法名 - 点击返回原理文档 */}
            <button
              onClick={() => setActiveTab(null)}
              className="flex items-center gap-3 hover:opacity-80 transition-opacity"
            >
              <h1 className={cn(
                "text-3xl font-black text-left",
                activeTab === null ? "text-slate-900" : "text-slate-500 hover:text-slate-800"
              )}>
                {method.name}
              </h1>
              <span className="text-lg font-mono text-slate-400">{method.shortName.toUpperCase()}</span>
            </button>

            <div className="flex items-center gap-4">
               {/* Tab Toggle */}
               <div className="bg-slate-100 p-1 rounded-xl flex gap-1 border border-slate-200">
                <button
                  onClick={() => setActiveTab('flow')}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all",
                    activeTab === 'flow' ? "bg-white text-purple-600 shadow-sm" : "text-slate-500 hover:text-slate-700"
                  )}
                >
                  <GitBranch size={16} />
                  程序流程
                </button>
                <button
                  onClick={() => setActiveTab('lab')}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all",
                    activeTab === 'lab' ? "bg-white text-indigo-600 shadow-sm" : "text-slate-500 hover:text-slate-700"
                  )}
                >
                  <Microscope size={16} />
                  计算过程
                </button>
                <button
                  onClick={() => setActiveTab('analysis')}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all",
                    activeTab === 'analysis' ? "bg-white text-emerald-600 shadow-sm" : "text-slate-500 hover:text-slate-700"
                  )}
                >
                  <BarChart3 size={16} />
                  结果分析
                </button>
                <button
                  onClick={() => setActiveTab('examples')}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all",
                    activeTab === 'examples' ? "bg-white text-orange-600 shadow-sm" : "text-slate-500 hover:text-slate-700"
                  )}
                >
                  <Gauge size={16} />
                  适用范围
                </button>
                <button
                  onClick={() => setActiveTab('cases')}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all",
                    activeTab === 'cases' ? "bg-white text-purple-600 shadow-sm" : "text-slate-500 hover:text-slate-700"
                  )}
                >
                  <FileCheck size={16} />
                  可信性验证
                </button>
                <button
                  onClick={() => setActiveTab('compare')}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all",
                    activeTab === 'compare' ? "bg-white text-cyan-600 shadow-sm" : "text-slate-500 hover:text-slate-700"
                  )}
                >
                  <Scale size={16} />
                  方法对比
                </button>
             </div>

             {/* Apply Link */}
             <Link
               href={`/?method=${method.id}`}
               className="inline-flex items-center gap-2 px-5 py-3 bg-blue-600 text-white hover:bg-blue-700 font-bold rounded-xl transition-all shadow-sm shadow-blue-200"
             >
               <Play size={18} />
               在计算器中应用
               <ExternalLink size={14} />
             </Link>
          </div>
        </div>
      </div>

      {/* Content Area */}
      <div className="min-h-[500px]">
        {activeTab === null ? (
          // 默认显示原理文档
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
             {'slug' in method && method.hasDetail && method.slug ? (
               <AlgorithmDetail slug={method.slug} />
             ) : (
               <div className="p-12 text-center text-slate-400 bg-white rounded-3xl border border-slate-200">
                 暂无详细文档
               </div>
             )}
          </div>
        ) : activeTab === 'flow' ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            <VariableFlowViewer methodId={method.id} />
          </div>
        ) : activeTab === 'lab' ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8">
            <AnalysisCard
              id="lab"
              index={0}
              data={data}
              result={result}
              methodId={method.id}
              color="#4f46e5"
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
              onMethodClick={undefined}
              onDataClick={handleDataClick}
              hideCalculationProcessButton={true}
            />

            {traceData && (
              <div className="bg-slate-50 rounded-3xl p-8 border border-slate-200">
                <div className="flex items-center gap-2 mb-6">
                  <Microscope className="text-indigo-500" size={20} />
                  <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">计算过程</h3>
                </div>

                {(() => {
                  const displayResult = (dataSources && dataSources.length > 0 && dataSources[activeSourceIndex]?.result)
                    ? dataSources[activeSourceIndex].result
                    : result

                  return displayResult && displayResult.converged !== false && (
                    <div className="mb-8">
                      <div className="grid grid-cols-4 gap-4 mb-3">
                        <StatBox label="估计 β" value={displayResult.beta !== null ? displayResult.beta.toFixed(4) : '--'} />
                        <StatBox label="估计 η" value={displayResult.eta !== null ? displayResult.eta.toFixed(2) : '--'} />
                        <StatBox label="估计 γ" value={displayResult.gamma.toFixed(2)} />
                        <StatBox label="R²" value={displayResult.rSquared !== null ? displayResult.rSquared.toFixed(4) : '--'} />
                      </div>
                    </div>
                  )
                })()}

                {method.id.toLowerCase() === 'mle' && (
                  <MLEVisualizer traceData={traceData} dataSources={dataSources} />
                )}
                {method.id.toLowerCase() === 'wmle' && (
                  <WMLEVisualizer
                    traceData={traceData}
                    dataSources={dataSources}
                    data={data.filter(d => d.status === 'F').map(d => d.value)}
                    onSurfaceLoad={(surfaceData) => {
                      setTraceData((prev: any) => {
                        if (!prev) return [surfaceData]
                        const filtered = prev.filter((d: any) => d.phase !== 'surface')
                        return [...filtered, surfaceData]
                      })
                    }}
                  />
                )}
                {method.id.toLowerCase() === 'mdm' && (
                  <MDMVisualizer
                    traceData={{...traceData, data: data.filter(d => d.status === 'F').map(d => d.value)}}
                    methodId={method.id}
                    dataSources={dataSources}
                  />
                )}

                {!['mle', 'wmle', 'mdm'].includes(method.id.toLowerCase()) && (
                  <div className="text-center py-12 text-slate-400">
                    此算法暂未适配可视化组件。
                  </div>
                )}
              </div>
            )}

            {isCalculating && (
              <div className="bg-slate-50 rounded-3xl p-12 border border-slate-200 flex flex-col items-center justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-indigo-200 border-t-indigo-600 mb-4"></div>
                <p className="text-slate-600 font-bold">正在运行计算...</p>
              </div>
            )}
          </div>
        ) : activeTab === 'analysis' ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8">
            <AnalysisCard
              id="analysis"
              index={0}
              data={data}
              result={result}
              methodId={method.id}
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
              onMethodClick={undefined}
              onDataClick={handleDataClick}
              hideCalculationProcessButton={true}
            />

            {result && result.beta !== null && result.eta !== null && (
              <div className="bg-slate-50 rounded-3xl p-8 border border-slate-200">
                <ResultAnalysisLab
                  methodId={method.id}
                  trueBeta={result.beta}
                  trueEta={result.eta}
                  trueGamma={result.gamma}
                />
              </div>
            )}
          </div>
        ) : activeTab === 'examples' ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            {method.id.toLowerCase() === 'mdm' ? (
              <GenericStudyViewer
                methodId={method.id}
                extraParamDefs={[
                  { id: 'offset', name: '偏移量', symbol: 'δ', chunkKey: 'd', isVariable: true }
                ]}
                extraChunkKeys={['d']}
              />
            ) : (
              <GenericStudyViewer methodId={method.id} />
            )}
          </div>
        ) : activeTab === 'cases' ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            <CaseStudyViewer methodId={method.id} />
          </div>
        ) : activeTab === 'compare' ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="p-12 text-center text-slate-400 bg-white rounded-3xl border border-slate-200">
              方法对比功能开发中...
            </div>
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
