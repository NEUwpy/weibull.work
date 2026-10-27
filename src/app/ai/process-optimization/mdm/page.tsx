"use client"

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import React, { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Gauge,
} from 'lucide-react'

import { AIChartLine } from '@/components/ai/charts/LineChart'
import AnalysisCard from '@/components/calculator/AnalysisCard'
import DataEditor from '@/components/calculator/DataEditor'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { calculateWeibull } from '@/hooks/useWeibullCalculation'
import { createManualParameterResult, MDM_DEFAULT_OFFSET } from '@/lib/calculator-state'
import {
  compareMdmOptimization,
  formatSigned,
  isMdmAiSampleSizeSupported,
  MdmOffsetMode,
  MdmProcessOptimizationResult,
  optimizeMdmOffset,
} from '@/lib/mdm-process-optimization'
import { calculateMedianRanks, DataPoint, WeibullResult } from '@/lib/weibull'

const DEFAULT_SAMPLE = [1314.68, 1509.32, 1672.86, 1832.55, 2005.13, 2215.02, 2536.73]


function parseSample(text: string): number[] {
  return text
    .split(/[\s,，;；]+/)
    .map(value => Number(value.trim()))
    .filter(Number.isFinite)
}

function toDataPoints(values: number[]): DataPoint[] {
  return values.map((value, id) => ({ id, value, status: 'F' }))
}

function MDMProcessOptimizationContent() {
  const searchParams = useSearchParams()
  const queryData = searchParams.get('data')
  const initialValues = useMemo(() => {
    const parsed = queryData ? parseSample(queryData) : []
    return parsed.length > 0 ? parsed : DEFAULT_SAMPLE
  }, [queryData])
  const [data, setData] = useState<DataPoint[]>(() => toDataPoints(initialValues))
  const [result, setResult] = useState<WeibullResult>(() => (
    createManualParameterResult(toDataPoints(initialValues), true, calculateMedianRanks)
  ))
  const [optimization, setOptimization] = useState<MdmProcessOptimizationResult | null>(null)
  const [aiEstimate, setAiEstimate] = useState<WeibullResult | null>(null)
  const [fixedEstimate, setFixedEstimate] = useState<WeibullResult | null>(null)
  const [mdmOffset, setMdmOffset] = useState(MDM_DEFAULT_OFFSET)
  const [mdmOffsetMode, setMdmOffsetMode] = useState<MdmOffsetMode>('ai')
  const [fitMode, setFitMode] = useState<'fit' | 'manual'>('manual')
  const [isDataEditorOpen, setIsDataEditorOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const handledQueryRef = useRef<string | null>(null)
  const calculationRequestRef = useRef(0)

  const clearOptimization = useCallback(() => {
    setOptimization(null)
    setAiEstimate(null)
    setFixedEstimate(null)
  }, [])

  const runOptimization = useCallback(async (points = data) => {
    const requestId = ++calculationRequestRef.current
    const values = points.filter(point => point.status === 'F').map(point => point.value)
    if (values.length !== points.length) {
      clearOptimization()
      setLoading(false)
      setError('AI 优化偏移量当前仅支持完整失效样本，不能包含悬停数据')
      return
    }
    if (!isMdmAiSampleSizeSupported(values.length)) {
      clearOptimization()
      setLoading(false)
      setError(`AI 优化偏移量当前支持 n=7、10、15、20；本次输入 n=${values.length}`)
      return
    }
    if (values.some(value => value <= 0)) {
      clearOptimization()
      setLoading(false)
      setError('失效时间必须全部大于 0')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const selected = await optimizeMdmOffset(values)
      const [calculation, fixedCalculation] = await Promise.all([
        calculateWeibull({
          methodId: 'mdm',
          data: points,
          offset: selected.selected_delta,
        }),
        calculateWeibull({
          methodId: 'mdm',
          data: points,
          offset: selected.default_delta,
        }),
      ])
      if (requestId !== calculationRequestRef.current) return
      setOptimization(selected)
      setAiEstimate(calculation.result)
      setFixedEstimate(fixedCalculation.result)
      setResult(calculation.result)
      setFitMode('fit')
    } catch (reason) {
      if (requestId !== calculationRequestRef.current) return
      clearOptimization()
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      if (requestId === calculationRequestRef.current) setLoading(false)
    }
  }, [clearOptimization, data])

  const runFixedCalculation = useCallback(async (offset: number, points = data) => {
    const requestId = ++calculationRequestRef.current
    if (points.length === 0) {
      setLoading(false)
      setError('请先输入失效样本')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const calculation = await calculateWeibull({ methodId: 'mdm', data: points, offset })
      if (requestId !== calculationRequestRef.current) return
      setResult(calculation.result)
      setFitMode('fit')
    } catch (reason) {
      if (requestId !== calculationRequestRef.current) return
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      if (requestId === calculationRequestRef.current) setLoading(false)
    }
  }, [data])

  useEffect(() => {
    if (!queryData || handledQueryRef.current === queryData) return
    handledQueryRef.current = queryData
    const points = toDataPoints(initialValues)
    setData(points)
    setResult(createManualParameterResult(points, true, calculateMedianRanks))
    setMdmOffsetMode('ai')
    void runOptimization(points)
  }, [initialValues, queryData, runOptimization])

  const values = data.filter(point => point.status === 'F').map(point => point.value)
  const curveData = optimization?.delta_grid.map((delta, index) => ({
    x: delta,
    y: optimization.predicted_loss_curve[index],
  })) || []
  const comparison = optimization ? compareMdmOptimization(optimization) : null
  const calculatorParams = optimization
    ? new URLSearchParams({
        method: 'mdm',
        data: values.join(','),
        mdmOffsetMode: 'ai',
      })
    : null
  const processParams = optimization
    ? new URLSearchParams({
        data: values.join(','),
        offset: optimization.selected_delta.toFixed(2),
      })
    : null

  const handleDataChange = useCallback((newData: DataPoint[]) => {
    calculationRequestRef.current += 1
    setData(newData)
    setResult(previous => {
      const gamma = previous?.gamma ?? 1000
      return {
        ...(previous ?? createManualParameterResult(newData, true, calculateMedianRanks)),
        points: calculateMedianRanks(newData, gamma),
        converged: true,
      }
    })
    clearOptimization()
    setFitMode('manual')
    setLoading(false)
    setError(null)
  }, [clearOptimization])

  const handleParamsUpdate = useCallback((updates: Partial<WeibullResult>, mode: 'fit' | 'manual' = 'manual') => {
    setResult(previous => {
      const base = previous ?? createManualParameterResult(data, true, calculateMedianRanks)
      const gamma = updates.gamma ?? base.gamma
      return {
        ...base,
        ...updates,
        points: updates.points ?? calculateMedianRanks(data, gamma),
      }
    })
    setFitMode(mode)
  }, [data])

  const handleMdmOffsetModeChange = useCallback(async (mode: MdmOffsetMode) => {
    setMdmOffsetMode(mode)
    if (mode === 'ai') {
      await runOptimization(data)
    } else {
      await runFixedCalculation(mdmOffset, data)
    }
  }, [data, mdmOffset, runFixedCalculation, runOptimization])

  const handleMdmOffsetChange = useCallback(async (offset: number) => {
    setMdmOffset(offset)
    setMdmOffsetMode('fixed')
    await runFixedCalculation(offset, data)
  }, [data, runFixedCalculation])

  const handleCalculate = useCallback(async () => {
    if (mdmOffsetMode === 'ai') {
      await runOptimization(data)
    } else {
      await runFixedCalculation(mdmOffset, data)
    }
  }, [data, mdmOffset, mdmOffsetMode, runFixedCalculation, runOptimization])

  return (
    <>
      <DataEditor
        isOpen={isDataEditorOpen}
        initialData={data}
        onClose={() => setIsDataEditorOpen(false)}
        onSave={newData => {
          handleDataChange(newData)
          setIsDataEditorOpen(false)
        }}
      />
      <section className="mx-auto w-full max-w-[1500px] space-y-6 px-8 py-9 pl-[4.5rem]">
      <header className="space-y-3">
        <Link href="/ai/process-optimization" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-600">
          <ArrowLeft size={14} /> 返回过程量优化
        </Link>
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-violet-600 p-2.5 text-white"><Gauge size={22} /></div>
          <div>
            <h1 className="text-xl font-black text-slate-900">MDM 偏移量优化</h1>
            <p className="text-sm text-slate-500">查看 AI 如何为当前样本选择过程量 δ</p>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-2 gap-2 rounded-xl border border-violet-100 bg-violet-50 p-3 text-center text-xs font-bold text-violet-700 md:grid-cols-5">
        <div>当前样本</div><div>排序与尺度处理</div><div>预测26点损失</div><div>选择最低点</div><div>执行MDM</div>
      </div>

      <div className="space-y-3">
        <div className="flex items-end justify-between">
          <div>
            <h2 className="font-black text-slate-800">当前计算卡片</h2>
            <p className="mt-1 text-xs text-slate-400">样本、参数和 AI 选择结果均以此卡片为准。</p>
          </div>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-500">n={values.length}</span>
        </div>
        <AnalysisCard
          id="ai-mdm-process-optimization"
          index={0}
          data={data}
          result={result}
          methodId="mdm"
          mdmOffset={mdmOffset}
          mdmOffsetMode={mdmOffsetMode}
          mdmOptimization={optimization ?? undefined}
          color="#7c3aed"
          fitMode={fitMode}
          is3P={true}
          availableLayers={[]}
          onAdd={() => {}}
          onMdmOffsetChange={handleMdmOffsetChange}
          onMdmOffsetModeChange={handleMdmOffsetModeChange}
          onDataClick={() => setIsDataEditorOpen(true)}
          onDataChange={handleDataChange}
          onParamsUpdate={handleParamsUpdate}
          onCalculate={handleCalculate}
          hideCalculationProcessButton={true}
          hideMdmOptimizationDetailsLink={true}
          lockParameterMode={true}
          isMdmOffsetUpdating={loading}
        />
        <p className="text-xs leading-relaxed text-slate-400">AI过程量优化当前支持 n=7、10、15、20 的三参数完整失效样本。</p>
      </div>

      <div className="space-y-4">
          {error && (
            <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <AlertCircle size={17} className="mt-0.5 shrink-0" /> {error}
            </div>
          )}

          {optimization ? (
            <>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-xl border border-violet-200 bg-violet-50 p-4">
                  <div className="text-xs font-bold text-violet-500">AI建议偏移量</div>
                  <div className="mt-1 font-mono text-3xl font-black text-violet-700">δ={optimization.selected_delta.toFixed(2)}</div>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-4">
                  <div className="text-xs font-bold text-slate-400">固定参照</div>
                  <div className="mt-1 font-mono text-2xl font-black text-slate-700">δ={optimization.default_delta.toFixed(2)}</div>
                </div>
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                  <div className="text-xs font-bold text-emerald-600">预测损失差异</div>
                  <div className="mt-1 font-mono text-2xl font-black text-emerald-700">
                    {comparison ? formatSigned(comparison.lossDifference, 4) : '—'}
                  </div>
                  <div className="text-xs text-emerald-600">AI损失 − 固定0.10损失</div>
                </div>
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                  <div className="text-xs font-bold text-emerald-600">预计估计准确度变化</div>
                  <div className="mt-1 font-mono text-2xl font-black text-emerald-700">
                    {comparison?.predictedAccuracyChangePercent == null
                      ? '—'
                      : formatSigned(comparison.predictedAccuracyChangePercent, 1, '%')}
                  </div>
                  <div className="text-xs text-emerald-600">正值表示预计改善</div>
                </div>
              </div>

              {aiEstimate && fixedEstimate && (
                <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                  <div className="border-b border-slate-100 px-5 py-4">
                    <h2 className="font-black text-slate-800">AI 与固定 δ=0.10 对比</h2>
                    <p className="mt-1 text-xs text-slate-400">差异列统一按 AI − 固定0.10 计算，并显式标注正负号。</p>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[620px] text-sm">
                      <thead className="bg-slate-50 text-xs font-bold text-slate-500">
                        <tr>
                          <th className="px-5 py-3 text-left">比较项</th>
                          <th className="px-5 py-3 text-right text-violet-700">AI选择</th>
                          <th className="px-5 py-3 text-right text-amber-700">固定0.10</th>
                          <th className="px-5 py-3 text-right">差异（AI − 固定）</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 font-mono">
                        {[
                          {
                            label: '偏移量 δ',
                            ai: optimization.selected_delta.toFixed(2),
                            fixed: optimization.default_delta.toFixed(2),
                            difference: formatSigned(optimization.selected_delta - optimization.default_delta, 2),
                          },
                          {
                            label: '预测损失',
                            ai: optimization.selected_predicted_loss.toFixed(4),
                            fixed: optimization.default_predicted_loss.toFixed(4),
                            difference: comparison ? formatSigned(comparison.lossDifference, 4) : '—',
                          },
                          {
                            label: '预计准确度变化',
                            ai: comparison?.predictedAccuracyChangePercent == null
                              ? '—'
                              : formatSigned(comparison.predictedAccuracyChangePercent, 1, '%'),
                            fixed: '+0.0%',
                            difference: comparison?.predictedAccuracyChangePercent == null
                              ? '—'
                              : formatSigned(comparison.predictedAccuracyChangePercent, 1, '%'),
                          },
                          {
                            label: 'β 估计值',
                            ai: aiEstimate.beta?.toFixed(4) ?? '—',
                            fixed: fixedEstimate.beta?.toFixed(4) ?? '—',
                            difference: aiEstimate.beta != null && fixedEstimate.beta != null
                              ? formatSigned(aiEstimate.beta - fixedEstimate.beta, 4)
                              : '—',
                          },
                          {
                            label: 'η 估计值',
                            ai: aiEstimate.eta?.toFixed(2) ?? '—',
                            fixed: fixedEstimate.eta?.toFixed(2) ?? '—',
                            difference: aiEstimate.eta != null && fixedEstimate.eta != null
                              ? formatSigned(aiEstimate.eta - fixedEstimate.eta, 2)
                              : '—',
                          },
                          {
                            label: 'γ 估计值',
                            ai: aiEstimate.gamma.toFixed(2),
                            fixed: fixedEstimate.gamma.toFixed(2),
                            difference: formatSigned(aiEstimate.gamma - fixedEstimate.gamma, 2),
                          },
                        ].map(row => (
                          <tr key={row.label}>
                            <td className="px-5 py-3 font-sans font-bold text-slate-600">{row.label}</td>
                            <td className="px-5 py-3 text-right font-bold text-violet-700">{row.ai}</td>
                            <td className="px-5 py-3 text-right text-slate-600">{row.fixed}</td>
                            <td className="px-5 py-3 text-right font-bold text-slate-700">{row.difference}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="border-t border-slate-100 bg-slate-50/70 px-5 py-3 text-xs leading-relaxed text-slate-500">
                    预计估计准确度变化由两者预测损失的相对差异换算；β、η、γ 的差异仅表示两套估计结果如何移动，
                    不表示当前未知真值下的实际参数误差。
                  </div>
                </div>
              )}

              <ChartCard title="当前样本的偏移量—预测损失曲线">
                <AIChartLine
                  data={curveData}
                  xLabel="偏移量 δ"
                  yLabel="预测损失"
                  color="#7c3aed"
                  xDomain={[0, 0.5]}
                  showDots
                  xTickFormatter={value => value.toFixed(2)}
                  yTickFormatter={value => value.toFixed(3)}
                  xReferences={[
                    { x: optimization.selected_delta, label: 'AI建议', color: '#7c3aed' },
                    { x: optimization.default_delta, label: '固定0.10', color: '#f59e0b' },
                  ]}
                />
              </ChartCard>

              {aiEstimate && (
                <div className={`flex flex-wrap items-center justify-between gap-3 rounded-2xl border p-4 shadow-sm ${
                  mdmOffsetMode === 'ai' && fitMode === 'fit'
                    ? 'border-emerald-200 bg-emerald-50/70'
                    : 'border-amber-200 bg-amber-50/70'
                }`}>
                  <div className={`flex items-center gap-2 text-sm font-black ${
                    mdmOffsetMode === 'ai' && fitMode === 'fit' ? 'text-emerald-800' : 'text-amber-800'
                  }`}>
                    <CheckCircle2 size={17} className={mdmOffsetMode === 'ai' && fitMode === 'fit' ? 'text-emerald-500' : 'text-amber-500'} />
                    {fitMode !== 'fit'
                      ? '上方参数已手动调整；下方保留最近一次 AI 对比'
                      : mdmOffsetMode === 'ai'
                        ? 'AI建议结果已同步到上方计算卡片'
                        : `上方计算卡片当前显示固定 δ=${mdmOffset.toFixed(2)} 的结果`}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Link
                      href={`/?${calculatorParams?.toString()}`}
                      className="inline-flex items-center gap-1 rounded-lg bg-violet-600 px-4 py-2 text-sm font-bold text-white hover:bg-violet-700"
                    >
                      应用到计算器 <ArrowRight size={14} />
                    </Link>
                    <Link
                      href={`/methods/mdm?${processParams?.toString()}`}
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-600 hover:bg-slate-50"
                    >
                      查看完整MDM计算过程 <ArrowRight size={14} />
                    </Link>
                  </div>
                </div>
              )}
            </>
          ) : !error && (
            <div className="flex min-h-[360px] items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white text-center text-sm text-slate-400">
              输入样本后查看26个候选偏移量的预测损失和AI建议。
            </div>
          )}
      </div>

      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-relaxed text-amber-800">
        <strong>适用边界：</strong> 当前仅支持三参数MDM、完整失效样本及 n=7、10、15、20；
        候选δ限定为0.00–0.50、步长0.02。曲线表示模型预测损失，用于本次候选值之间的比较，
        “预计估计准确度变化”由预测损失相对固定δ=0.10的变化换算，不是当前样本可直接观测的真实误差；
        当前样本没有参数真值时不能计算实测准确度，也不保证每个样本在真实误差上都优于固定δ=0.10。
      </div>
      </section>
    </>
  )
}

export default function MDMProcessOptimizationPage() {
  return (
    <Suspense fallback={<div className="p-16 text-center text-slate-400">加载过程量优化页面...</div>}>
      <MDMProcessOptimizationContent />
    </Suspense>
  )
}
