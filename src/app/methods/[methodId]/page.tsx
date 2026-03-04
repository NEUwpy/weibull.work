"use client"

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { notFound } from 'next/navigation'
import { INITIAL_METHOD_TREE, MethodNode } from '@/lib/methods'
import { ArrowLeft, ExternalLink, Info, Sigma, BookOpen, Microscope, FileText, BarChart3, GitBranch, FlaskConical } from 'lucide-react'
import { cn } from '@/lib/utils'
import { AlgorithmDetail } from '@/components/AlgorithmDetail'
import AnalysisCard from '@/components/AnalysisCard'
import ResultAnalysisLab from '@/components/ResultAnalysisLab'
import DataEditor from '@/components/DataEditor'
import dynamic from 'next/dynamic'
import { DataPoint, WeibullResult, calculateMedianRanks, calculateWeibullParameters } from '@/lib/weibull'

// Dynamic imports for heavy visualizers
const VariableFlowViewer = dynamic(() => import('@/components/VariableFlowViewer'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
const MLEVisualizer = dynamic(() => import('@/components/visualizers/MLEVisualizer'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
const WMLEVisualizer = dynamic(() => import('@/components/visualizers/WMLEVisualizer'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
const MDMVisualizer = dynamic(() => import('@/components/visualizers/MDMVisualizer'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
const CaseStudyViewer = dynamic(() => import('@/components/CaseStudyViewer'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
const WMLEExample = dynamic(() => import('@/components/WMLEExample'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
const MDMStudyViewer = dynamic(() => import('@/components/studies/mdm/MDMStudyViewer'), { loading: () => <div className="p-8 text-center text-slate-400">加载中...</div> })
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
  // ... (Keep existing implementation for category overview)
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
  const [activeTab, setActiveTab] = useState<'doc' | 'flow' | 'lab' | 'analysis' | 'examples' | 'cases'>('doc')

  // Result Analysis Card State (similar to Lab)
  const [analysisData, setAnalysisData] = useState<DataPoint[]>([])
  const [analysisResult, setAnalysisResult] = useState<WeibullResult | undefined>(undefined)
  const [analysisFitMode, setAnalysisFitMode] = useState<'fit' | 'manual'>('manual')
  const [analysisIs3P, setAnalysisIs3P] = useState(false)
  const [isAnalysisDataEditorOpen, setIsAnalysisDataEditorOpen] = useState(false)

  // Calculator Lab State
  const [labData, setLabData] = useState<DataPoint[]>([])
  const [labResult, setLabResult] = useState<WeibullResult | undefined>(undefined)
  const [labFitMode, setLabFitMode] = useState<'fit' | 'manual'>('fit')
  const [labIs3P, setLabIs3P] = useState(false)
  const [traceData, setTraceData] = useState<any>(null)
  const [isCalculating, setIsCalculating] = useState(false)
  const [isDataEditorOpen, setIsDataEditorOpen] = useState(false)

  // Read trueBeta, trueEta, trueGamma from URL params and initialize analysis card
  useEffect(() => {
    const betaParam = searchParams.get('trueBeta')
    const etaParam = searchParams.get('trueEta')
    const gammaParam = searchParams.get('trueGamma')

    if (betaParam && etaParam && gammaParam) {
      const beta = parseFloat(betaParam)
      const eta = parseFloat(etaParam)
      const gamma = parseFloat(gammaParam)

      // Initialize analysis result with parameters from URL
      setAnalysisResult({
        beta,
        eta,
        gamma,
        rSquared: null,
        points: [],
        converged: true
      })
      setAnalysisFitMode('manual')
      setAnalysisIs3P(gamma !== 0)
      setActiveTab('analysis') // Auto-switch to analysis tab
    }
  }, [searchParams])

  // Initialize default parameters when switching to analysis tab
  useEffect(() => {
    if (activeTab === 'analysis' && !analysisResult) {
      // Set default parameters: β=2, η=1000, γ=1000
      setAnalysisResult({
        beta: 2,
        eta: 1000,
        gamma: 1000,
        rSquared: null,
        points: [],
        converged: true
      })
      setAnalysisFitMode('manual')
      setAnalysisIs3P(true)
    }
  }, [activeTab, analysisResult])

  // Auto-switch to lab if data is present and parse data
  useEffect(() => {
    const dataParam = searchParams.get('data')
    if (dataParam) {
      setActiveTab('lab')
      try {
        const parsed = dataParam.split(',').map(Number).filter(n => !isNaN(n))
        const points: DataPoint[] = parsed.map((v, i) => ({ id: i, value: v, status: 'F' }))
        setLabData(points)
        // Auto-calculate with initial data
        const calculatedPoints = calculateMedianRanks(points, 0)
        const result = calculateWeibullParameters(calculatedPoints, 0)
        setLabResult(result)
      } catch(e) {
        console.error("Failed to parse data", e)
      }
    }
  }, [searchParams])

  // Calculator Lab Handlers
  const handleLabDataClick = () => {
    setIsDataEditorOpen(true)
  }

  const handleLabDataSave = (newData: DataPoint[]) => {
    const currentGamma = labResult?.gamma || 0
    const points = calculateMedianRanks(newData, currentGamma)
    const result = calculateWeibullParameters(points, currentGamma)
    setLabData(newData)
    setLabResult(result)
    setLabFitMode('fit')
    setIsDataEditorOpen(false)
  }

  const handleLabDataChange = (newData: DataPoint[]) => {
    const currentGamma = labResult?.gamma || 0
    const points = calculateMedianRanks(newData, currentGamma)
    setLabData(newData)
    setLabResult(prev => prev ? { ...prev, points } : undefined)
    setLabFitMode('fit')
  }

  const handleLabParamsUpdate = (updates: Partial<WeibullResult>, mode?: 'fit' | 'manual') => {
    const baseResult = labResult || { beta: 1, eta: 100, gamma: 0, rSquared: 0, points: [] }
    const newResult = { ...baseResult, ...updates }
    let newPoints = labResult?.points || []
    // Only recalculate points if gamma changed AND points not already provided in updates
    if (updates.gamma !== undefined && !updates.points && labData) {
      newPoints = calculateMedianRanks(labData, updates.gamma)
    } else if (updates.points !== undefined) {
      newPoints = updates.points
    }
    setLabResult({ ...newResult, points: newPoints })
    if (mode) setLabFitMode(mode)
  }

  const handleLabCalculate = async () => {
    if (!labData || labData.length === 0) return

    setIsCalculating(true)
    try {
      // Build request body - MDM method requires offset parameter
      const requestBody: any = {
        method: method.id,
        data: labData.filter(d => d.status === 'F').map(d => d.value),
        trace: true // Request process trace
      }

      // Add offset for MDM method
      if (method.id.toLowerCase() === 'mdm') {
        requestBody.offset = 0.1 // Default offset value
      }

      const response = await fetch('http://localhost:8001/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      })

      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || '计算失败')
      }

      const res = await response.json()

      // Check convergence
      if (res.converged === false) {
        // Return result with actual values (0) but marked as not converged
        const newPoints = calculateMedianRanks(labData, res.gamma || 0)
        const newResult: WeibullResult = {
          beta: res.beta,
          eta: res.eta,
          gamma: res.gamma || 0,
          rSquared: res.rSquared,
          points: newPoints,
          converged: false
        }
        setLabResult(newResult)
        setLabFitMode('fit')

        // Store trace data for visualization even when not converged
        if (res.trace_data) {
          setTraceData(res.trace_data)
        }

        setIsCalculating(false)
        return
      }

      const newPoints = calculateMedianRanks(labData, res.gamma || 0)
      const newResult: WeibullResult = {
        beta: res.beta,
        eta: res.eta,
        gamma: res.gamma || 0,
        rSquared: res.rSquared,
        points: newPoints,
        converged: true
      }
      setLabResult(newResult)
      setLabFitMode('fit')

      // Store trace data for visualization
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

  const handleLabToggle3P = () => {
    const nextIs3P = !labIs3P
    let updates: Partial<WeibullResult> = {}
    let newPoints = labResult?.points || []

    if (!nextIs3P) {
      updates = { gamma: 0 }
      if (labData) {
        newPoints = calculateMedianRanks(labData, 0)
      }
    }
    setLabResult(prev => prev ? { ...prev, ...updates, points: newPoints } : undefined)
    setLabIs3P(nextIs3P)
  }

  // Result Analysis Card Handlers
  const handleAnalysisDataClick = () => {
    setIsAnalysisDataEditorOpen(true)
  }

  const handleAnalysisDataSave = (newData: DataPoint[]) => {
    const currentGamma = analysisResult?.gamma || 0
    const points = calculateMedianRanks(newData, currentGamma)
    const result = calculateWeibullParameters(points, currentGamma)
    setAnalysisData(newData)
    setAnalysisResult(result)
    setAnalysisFitMode('fit')
    setIsAnalysisDataEditorOpen(false)
  }

  const handleAnalysisDataChange = (newData: DataPoint[]) => {
    const currentGamma = analysisResult?.gamma || 0
    const points = calculateMedianRanks(newData, currentGamma)
    setAnalysisData(newData)
    setAnalysisResult(prev => prev ? { ...prev, points } : undefined)
    setAnalysisFitMode('fit')
  }

  const handleAnalysisParamsUpdate = (updates: Partial<WeibullResult>, mode?: 'fit' | 'manual') => {
    const baseResult = analysisResult || { beta: 1, eta: 100, gamma: 0, rSquared: 0, points: [] }
    const newResult = { ...baseResult, ...updates }
    let newPoints = analysisResult?.points || []
    if (updates.gamma !== undefined && !updates.points && analysisData) {
      newPoints = calculateMedianRanks(analysisData, updates.gamma)
    } else if (updates.points !== undefined) {
      newPoints = updates.points
    }
    setAnalysisResult({ ...newResult, points: newPoints })
    if (mode) setAnalysisFitMode(mode)
  }

  const handleAnalysisCalculate = async () => {
    if (!analysisData || analysisData.length === 0) return

    setIsCalculating(true)
    try {
      const response = await fetch('http://localhost:8001/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          method: method.id,
          data: analysisData.filter(d => d.status === 'F').map(d => d.value),
          trace: false
        })
      })

      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || '计算失败')
      }

      const res = await response.json()
      const newPoints = calculateMedianRanks(analysisData, res.gamma || 0)
      const newResult: WeibullResult = {
        beta: res.beta,
        eta: res.eta,
        gamma: res.gamma || 0,
        rSquared: res.rSquared,
        points: newPoints,
        converged: res.converged
      }
      setAnalysisResult(newResult)
      setAnalysisFitMode('fit')
    } catch (err: any) {
      console.error(err)
      alert(`后端计算错误: ${err.message}\n请确保 Python main.py 已在 8001 端口运行。`)
    } finally {
      setIsCalculating(false)
    }
  }

  const handleAnalysisToggle3P = () => {
    const nextIs3P = !analysisIs3P
    let updates: Partial<WeibullResult> = {}
    let newPoints = analysisResult?.points || []

    if (!nextIs3P) {
      updates = { gamma: 0 }
      if (analysisData) {
        newPoints = calculateMedianRanks(analysisData, 0)
      }
    }
    setAnalysisResult(prev => prev ? { ...prev, ...updates, points: newPoints } : undefined)
    setAnalysisIs3P(nextIs3P)
  }

  // Auto-run calculation when data is present from URL
  useEffect(() => {
    const dataParam = searchParams.get('data')
    if (dataParam && labData.length > 0 && !traceData) {
      handleLabCalculate()
    }
    // Only run once when data is first loaded
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <>
      <DataEditor
        isOpen={isDataEditorOpen}
        initialData={labData}
        onClose={() => setIsDataEditorOpen(false)}
        onSave={handleLabDataSave}
      />
      <DataEditor
        isOpen={isAnalysisDataEditorOpen}
        initialData={analysisData}
        onClose={() => setIsAnalysisDataEditorOpen(false)}
        onSave={handleAnalysisDataSave}
      />

      <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12">
        {/* Header */}
        <div className="mb-8">
          <Link href="/methods" className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-800 transition-colors font-bold mb-6">
            <ArrowLeft size={18} /> 返回方法总览
          </Link>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-black text-slate-900">{method.name}</h1>
              <span className="text-lg font-mono text-slate-400">{method.shortName.toUpperCase()}</span>
            </div>

            <div className="flex items-center gap-4">
               {/* Mode Toggle */}
               <div className="bg-slate-100 p-1 rounded-xl flex gap-1 border border-slate-200">
                <button
                  onClick={() => setActiveTab('doc')}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all",
                    activeTab === 'doc' ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700"
                  )}
                >
                  <FileText size={16} />
                  原理文档
                </button>
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
                  <FlaskConical size={16} />
                  方法示例
                </button>
                <button
                  onClick={() => setActiveTab('cases')}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all",
                    activeTab === 'cases' ? "bg-white text-purple-600 shadow-sm" : "text-slate-500 hover:text-slate-700"
                  )}
                >
                  <FlaskConical size={16} />
                  案例展示
                </button>
             </div>

             {/* Apply Link */}
             <Link
               href={`/?method=${method.id}`}
               className="inline-flex items-center gap-2 px-5 py-3 bg-blue-600 text-white hover:bg-blue-700 font-bold rounded-xl transition-all shadow-sm shadow-blue-200"
             >
               <Sigma size={18} />
               在计算器中应用
               <ExternalLink size={14} />
             </Link>
          </div>
        </div>
      </div>

      {/* Content Area */}
      <div className="min-h-[500px]">
        {activeTab === 'doc' ? (
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
             {/* Calculator Lab - Full Featured Analysis Card */}
             <AnalysisCard
               id="lab"
               index={0}
               data={labData}
               result={labResult}
               methodId={method.id}
               color="#4f46e5" // Indigo-600
               fitMode={labFitMode}
               is3P={labIs3P}
               availableLayers={[]}
               onAdd={() => {}}
               onDelete={() => {}}
               onDataChange={handleLabDataChange}
               onParamsUpdate={handleLabParamsUpdate}
               onToggle3P={handleLabToggle3P}
               onCalculate={handleLabCalculate}
               onMethodClick={undefined}
               onDataClick={handleLabDataClick}
               hideCalculationProcessButton={true}
             />

             {/* Calculation Process Visualization */}
             {traceData && (
                <div className="bg-slate-50 rounded-3xl p-8 border border-slate-200">
                  <div className="flex items-center gap-2 mb-6">
                    <Microscope className="text-indigo-500" size={20} />
                    <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">计算过程</h3>
                  </div>

                  {/* Stats Bar */}
                  {labResult && labResult.converged !== false && (
                    <div className="grid grid-cols-4 gap-4 mb-8">
                       <StatBox label="估计 β" value={labResult.beta !== null ? labResult.beta.toFixed(4) : '--'} />
                       <StatBox label="估计 η" value={labResult.eta !== null ? labResult.eta.toFixed(2) : '--'} />
                       <StatBox label="估计 γ" value={labResult.gamma.toFixed(2)} />
                       <StatBox label="R²" value={labResult.rSquared !== null ? labResult.rSquared.toFixed(4) : '--'} />
                    </div>
                  )}

                  {/* Visualizers */}
                  {method.id.toLowerCase() === 'mle' && (
                    <MLEVisualizer traceData={traceData} />
                  )}
                  {method.id.toLowerCase() === 'wmle' && (
                    <WMLEVisualizer traceData={traceData} />
                  )}
                  {method.id.toLowerCase() === 'mdm' && (
                    <MDMVisualizer
                      traceData={{...traceData, data: labData.filter(d => d.status === 'F').map(d => d.value)}}
                      methodId={method.id}
                    />
                  )}

                  {/* Fallback for others */}
                  {!['mle', 'wmle', 'mdm'].includes(method.id.toLowerCase()) && (
                    <div className="text-center py-12 text-slate-400">
                      此算法暂未适配可视化组件。
                    </div>
                  )}
                </div>
             )}

             {/* Loading State */}
             {isCalculating && (
                <div className="bg-slate-50 rounded-3xl p-12 border border-slate-200 flex flex-col items-center justify-center">
                  <div className="animate-spin rounded-full h-12 w-12 border-4 border-indigo-200 border-t-indigo-600 mb-4"></div>
                  <p className="text-slate-600 font-bold">正在运行计算...</p>
                </div>
             )}
          </div>
        ) : activeTab === 'analysis' ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8">
             {/* Result Analysis Tab - Analysis Card */}
             <AnalysisCard
               id="analysis"
               index={0}
               data={analysisData}
               result={analysisResult}
               methodId={method.id}
               color="#10b981" // Emerald-500
               fitMode={analysisFitMode}
               is3P={analysisIs3P}
               availableLayers={[]}
               onAdd={() => {}}
               onDelete={() => {}}
               onDataChange={handleAnalysisDataChange}
               onParamsUpdate={handleAnalysisParamsUpdate}
               onToggle3P={handleAnalysisToggle3P}
               onCalculate={handleAnalysisCalculate}
               onMethodClick={undefined}
               onDataClick={handleAnalysisDataClick}
               hideCalculationProcessButton={true}
             />

             {/* Monte Carlo Simulation */}
             {analysisResult && analysisResult.beta !== null && analysisResult.eta !== null && (
               <div className="bg-slate-50 rounded-3xl p-8 border border-slate-200">
                 <ResultAnalysisLab
                   methodId={method.id}
                   trueBeta={analysisResult.beta}
                   trueEta={analysisResult.eta}
                   trueGamma={analysisResult.gamma}
                 />
               </div>
             )}
          </div>
        ) : activeTab === 'examples' ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            <MDMStudyViewer methodId={method.id} />
          </div>
        ) : activeTab === 'cases' ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            <CaseStudyViewer methodId={method.id} />
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