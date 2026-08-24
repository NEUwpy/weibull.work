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
  Loader2,
  Sparkles,
} from 'lucide-react'

import { AIChartLine } from '@/components/ai/charts/LineChart'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { calculateWeibull } from '@/hooks/useWeibullCalculation'
import {
  isMdmAiSampleSizeSupported,
  MdmProcessOptimizationResult,
  optimizeMdmOffset,
} from '@/lib/mdm-process-optimization'
import { DataPoint, WeibullResult } from '@/lib/weibull'

const DEFAULT_SAMPLE = [1314.68, 1509.32, 1672.86, 1832.55, 2005.13, 2215.02, 2536.73]


function parseSample(text: string): number[] {
  return text
    .split(/[\s,，;；]+/)
    .map(value => Number(value.trim()))
    .filter(Number.isFinite)
}

function formatSample(values: number[]): string {
  return values.map(value => String(value)).join('\n')
}

function MDMProcessOptimizationContent() {
  const searchParams = useSearchParams()
  const queryData = searchParams.get('data')
  const initialValues = useMemo(() => {
    const parsed = queryData ? parseSample(queryData) : []
    return parsed.length > 0 ? parsed : DEFAULT_SAMPLE
  }, [queryData])
  const [sampleInput, setSampleInput] = useState(() => formatSample(initialValues))
  const [optimization, setOptimization] = useState<MdmProcessOptimizationResult | null>(null)
  const [estimate, setEstimate] = useState<WeibullResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const autoRunRef = useRef(false)

  const runOptimization = useCallback(async (text = sampleInput) => {
    const values = parseSample(text)
    if (!isMdmAiSampleSizeSupported(values.length)) {
      setOptimization(null)
      setEstimate(null)
      setError(`AI 优化偏移量当前支持 n=7、10、15、20；本次输入 n=${values.length}`)
      return
    }
    if (values.some(value => value <= 0)) {
      setOptimization(null)
      setEstimate(null)
      setError('失效时间必须全部大于 0')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const selected = await optimizeMdmOffset(values)
      const data: DataPoint[] = values.map((value, id) => ({ id, value, status: 'F' }))
      const calculation = await calculateWeibull({
        methodId: 'mdm',
        data,
        offset: selected.selected_delta,
      })
      setOptimization(selected)
      setEstimate(calculation.result)
    } catch (reason) {
      setOptimization(null)
      setEstimate(null)
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setLoading(false)
    }
  }, [sampleInput])

  useEffect(() => {
    if (!queryData || autoRunRef.current) return
    autoRunRef.current = true
    void runOptimization(formatSample(initialValues))
  }, [initialValues, queryData, runOptimization])

  const values = parseSample(sampleInput)
  const curveData = optimization?.delta_grid.map((delta, index) => ({
    x: delta,
    y: optimization.predicted_loss_curve[index],
  })) || []
  const predictedReduction = optimization && optimization.default_predicted_loss > 0
    ? (optimization.default_predicted_loss - optimization.selected_predicted_loss)
      / optimization.default_predicted_loss * 100
    : null
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

  return (
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

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[360px_1fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="font-black text-slate-800">当前失效样本</h2>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-bold text-slate-500">n={values.length}</span>
          </div>
          <textarea
            value={sampleInput}
            onChange={event => {
              setSampleInput(event.target.value)
              setOptimization(null)
              setEstimate(null)
              setError(null)
            }}
            className="mt-3 h-56 w-full resize-none rounded-xl border border-slate-200 p-3 font-mono text-sm outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-100"
            aria-label="MDM AI 偏移量优化样本"
          />
          <button
            type="button"
            onClick={() => void runOptimization()}
            disabled={loading}
            className="mt-3 flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-violet-600 text-sm font-black text-white transition-colors hover:bg-violet-700 disabled:opacity-50"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            {loading ? '正在选择并估计' : 'AI选择偏移量'}
          </button>
          <p className="mt-2 text-xs leading-relaxed text-slate-400">支持 n=7、10、15、20 的完整失效样本。</p>
        </div>

        <div className="space-y-4">
          {error && (
            <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <AlertCircle size={17} className="mt-0.5 shrink-0" /> {error}
            </div>
          )}

          {optimization ? (
            <>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                <div className="rounded-xl border border-violet-200 bg-violet-50 p-4">
                  <div className="text-xs font-bold text-violet-500">AI建议偏移量</div>
                  <div className="mt-1 font-mono text-3xl font-black text-violet-700">δ={optimization.selected_delta.toFixed(2)}</div>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-4">
                  <div className="text-xs font-bold text-slate-400">固定参照</div>
                  <div className="mt-1 font-mono text-2xl font-black text-slate-700">δ={optimization.default_delta.toFixed(2)}</div>
                </div>
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                  <div className="text-xs font-bold text-emerald-600">本次预测损失差异</div>
                  <div className="mt-1 text-2xl font-black text-emerald-700">
                    {predictedReduction === null ? '—' : `${predictedReduction.toFixed(1)}%`}
                  </div>
                  <div className="text-xs text-emerald-600">相对固定 δ=0.10</div>
                </div>
              </div>

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

              {estimate && (
                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex items-center gap-2 text-sm font-black text-slate-800">
                    <CheckCircle2 size={17} className="text-emerald-500" /> 使用建议δ后的MDM结果
                  </div>
                  <div className="mt-4 grid grid-cols-3 gap-3 text-center">
                    {[
                      ['β', estimate.beta],
                      ['η', estimate.eta],
                      ['γ', estimate.gamma],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-lg bg-slate-50 p-3">
                        <div className="text-xs font-bold text-slate-400">{label}</div>
                        <div className="mt-1 font-mono text-lg font-black text-slate-700">
                          {typeof value === 'number' ? value.toFixed(label === 'β' ? 4 : 2) : '—'}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
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
      </div>

      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-relaxed text-amber-800">
        <strong>适用边界：</strong> 当前仅支持三参数MDM、完整失效样本及 n=7、10、15、20；
        候选δ限定为0.00–0.50、步长0.02。曲线表示模型预测损失，用于本次候选值之间的比较，
        不是当前样本可直接观测的真实误差，也不保证每个样本都优于固定δ=0.10。
      </div>
    </section>
  )
}

export default function MDMProcessOptimizationPage() {
  return (
    <Suspense fallback={<div className="p-16 text-center text-slate-400">加载过程量优化页面...</div>}>
      <MDMProcessOptimizationContent />
    </Suspense>
  )
}
