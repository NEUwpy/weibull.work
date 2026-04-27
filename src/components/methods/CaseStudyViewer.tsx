/**
 * 可信性验证渲染器
 *
 * 用于展示论文复现验证，支持：
 * - 下拉选择不同验证项
 * - 左右对比布局（论文原图 vs 系统复现）
 */
"use client"

import React, { useState, useEffect } from 'react'
import { BookOpen, ChevronDown, BarChart3 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { VerificationItem, type SampleInfo } from './shared/verification'
import { GradientGammaChart, type GradientCurveData } from './mdm/charts'
import type { VerificationConfig, SampleData, EstimateResult, SampleCurve } from './shared/verification/types'
import dynamic from 'next/dynamic'

const CurvePropertiesViewer = dynamic(() => import('./mdm/CurvePropertiesViewer'), {
  loading: () => <div className="p-8 text-center text-slate-400">加载中...</div>
})

interface CaseStudyViewerProps {
  methodId: string
}

// 曲线颜色
const CURVE_COLORS = [
  '#ef4444', '#10b981', '#3b82f6', '#f59e0b', '#8b5cf6',
  '#06b6d4', '#ec4899', '#84cc16', '#6366f1', '#14b8a6',
  '#f97316', '#065f46', '#2563eb', '#7c3aed', '#00b894',
  '#e63946', '#fb8500', '#4ea8de', '#6c5ce7', '#a29bfe',
  '#ff006e', '#008000', '#008080', '#800080', '#800000',
  '#808000', '#808000', '#ff8040', '#ff80ff', '#80ffff'
]

export default function CaseStudyViewer({ methodId }: CaseStudyViewerProps) {
  const [subTab, setSubTab] = useState<'paper' | 'curve'>('paper')
  const [verifications, setVerifications] = useState<VerificationConfig[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [loading, setLoading] = useState(true)

  // 数据状态
  const [curvesData, setCurvesData] = useState<SampleCurve[]>([])
  const [samples, setSamples] = useState<SampleData[]>([])
  const [results, setResults] = useState<EstimateResult[]>([])
  const [dataLoading, setDataLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 加载验证列表
  useEffect(() => {
    const loadVerifications = async () => {
      try {
        const res = await fetch(`/api/case-studies/${methodId.toLowerCase()}`)
        if (res.ok) {
          const data = await res.json()
          const cases = data.cases || []
          setVerifications(cases)
          if (cases.length > 0) {
            setSelectedId(cases[0].id)
          }
        }
      } catch (err) {
        console.error('Failed to load verifications:', err)
      } finally {
        setLoading(false)
      }
    }
    loadVerifications()
  }, [methodId])

  // 获取当前选中的验证配置
  const selectedVerification = verifications.find(v => v.id === selectedId)

  // 加载验证数据
  useEffect(() => {
    const verificationConfig = selectedVerification?.verification
    if (!verificationConfig) {
      return
    }

    const loadData = async () => {
      try {
        setDataLoading(true)
        setError(null)

        const v = verificationConfig
        const [curvesRes, samplesRes, resultsRes] = await Promise.all([
          fetch(v.curvesData),
          fetch(v.samplesData),
          fetch(v.resultsData)
        ])

        if (!curvesRes.ok) throw new Error('曲线数据加载失败')
        if (!samplesRes.ok) throw new Error('样本数据加载失败')
        if (!resultsRes.ok) throw new Error('估计结果加载失败')

        // 解析曲线数据
        const curvesJson = await curvesRes.json()
        const clippedSamples = curvesJson.samples.map((sample: SampleCurve) => ({
          ...sample,
          grad_gamma_curve: sample.grad_gamma_curve
            .map((p) => ({ ...p, gradient: Math.max(0, Math.min(0.6, p.gradient)) }))
            .filter((p) => p.gradient >= 0 && p.gradient <= 0.6)
        }))
        setCurvesData(clippedSamples)

        // 解析样本数据
        const samplesText = await samplesRes.text()
        setSamples(parseSamplesCSV(samplesText))

        // 解析估计结果
        const resultsText = await resultsRes.text()
        setResults(parseResultsCSV(resultsText))

      } catch (err) {
        setError(err instanceof Error ? err.message : '加载失败')
        console.error('Load error:', err)
      } finally {
        setDataLoading(false)
      }
    }

    loadData()
  }, [selectedVerification])

  const parseSamplesCSV = (csvText: string): SampleData[] => {
    const lines = csvText.trim().split('\n')
    return lines.slice(1).map(line => {
      const parts = line.split(',')
      return {
        id: parts[0],
        values: parts.slice(1).map(v => parseFloat(v))
      }
    })
  }

  const parseResultsCSV = (csvText: string): EstimateResult[] => {
    const lines = csvText.trim().split('\n')
    const headers = lines[0].split(',')
    return lines.slice(1).map(line => {
      const values = line.split(',')
      const obj: any = {}
      headers.forEach((header, idx) => {
        const val = values[idx]?.trim()
        obj[header] = header === 'sample_id' ? val : (val === '' ? null : Number(val))
      })
      return obj as EstimateResult
    })
  }

  // 加载中
  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-200 border-t-purple-600 mb-4"></div>
          <p className="text-slate-600 font-bold">加载验证列表中...</p>
        </div>
      </div>
    )
  }

  // 无验证项
  if (verifications.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center">
          <BookOpen className="text-slate-300 mb-4" size={48} />
          <h3 className="text-lg font-bold text-slate-600 mb-2">暂无验证项</h3>
          <p className="text-slate-400">该方法的可信性验证正在建设中...</p>
        </div>
      </div>
    )
  }

  // 数据加载错误
  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-2xl p-8">
        <p className="text-red-700 font-bold">加载失败: {error}</p>
      </div>
    )
  }

  const v = selectedVerification?.verification
  const paper = selectedVerification?.paper

  // 参数条件
  const params: SampleInfo[] = v ? [
    { label: '真实分布', value: `W(${v.trueParams.beta}, ${v.trueParams.eta}, ${v.trueParams.gamma})` },
    { label: '样本量', value: `n=${v.sampleSize}` },
    { label: '偏移量', value: `δ=${v.offset}` },
    { label: '样本数', value: `${v.nSamples}组` }
  ] : []

  // 样本数据表格
  const samplesTableData = v ? {
    headers: ['样本', 't₁', 't₂', 't₃', 't₄', 't₅', 't₆', 't₇'],
    rows: samples.map(s => [s.id, ...s.values])
  } : { headers: [], rows: [] }

  // 准备图表数据
  const chartCurves: GradientCurveData[] = curvesData.slice(0, 30).map((sample, idx) => ({
    id: sample.sample_id,
    data: sample.grad_gamma_curve,
    color: CURVE_COLORS[idx % CURVE_COLORS.length],
    strokeWidth: 1.5,
    name: sample.sample_id,
    opacity: 0.8
  }))

  // Sub-tab for MDM: curve properties research
  if (methodId.toLowerCase() === 'mdm') {
    return (
      <div className="space-y-6">
        {/* Sub-tab switcher */}
        <div className="bg-white p-3 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-2">
            <div className="bg-slate-100 p-1 rounded-xl flex gap-1 border border-slate-200">
              <button
                onClick={() => setSubTab('paper')}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all",
                  subTab === 'paper' ? "bg-white text-purple-600 shadow-sm" : "text-slate-500 hover:text-slate-700"
                )}
              >
                <BookOpen size={16} />
                论文复现
              </button>
              <button
                onClick={() => setSubTab('curve')}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all",
                  subTab === 'curve' ? "bg-white text-blue-600 shadow-sm" : "text-slate-500 hover:text-slate-700"
                )}
              >
                <BarChart3 size={16} />
                曲线性质
              </button>
            </div>
          </div>
        </div>

        {/* Content */}
        {subTab === 'paper' ? (
          <div className="space-y-6">
            {/* Loading state */}
            {loading && (
              <div className="bg-white rounded-2xl border border-slate-200 p-12">
                <div className="flex flex-col items-center justify-center">
                  <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-200 border-t-purple-600 mb-4" />
                  <p className="text-slate-600 font-bold">加载验证列表中...</p>
                </div>
              </div>
            )}

            {/* No verifications */}
            {!loading && verifications.length === 0 && (
              <div className="bg-white rounded-2xl border border-slate-200 p-12">
                <div className="flex flex-col items-center justify-center">
                  <BookOpen className="text-slate-300 mb-4" size={48} />
                  <h3 className="text-lg font-bold text-slate-600 mb-2">暂无验证项</h3>
                  <p className="text-slate-400">该方法的可信性验证正在建设中...</p>
                </div>
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-2xl p-8">
                <p className="text-red-700 font-bold">加载失败: {error}</p>
              </div>
            )}

            {/* Verification content */}
            {!loading && verifications.length > 0 && !error && (
              <>
                {/* Selector */}
                <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
                  <div className="flex items-center gap-4">
                    <BookOpen className="text-purple-600" size={20} />
                    <label className="text-sm font-bold text-slate-600 whitespace-nowrap">选择验证：</label>
                    <div className="relative flex-1 max-w-xl">
                      <select
                        value={selectedId}
                        onChange={(e) => setSelectedId(e.target.value)}
                        className="w-full appearance-none bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent cursor-pointer hover:bg-slate-100 transition-colors"
                      >
                        {verifications.map(v => (
                          <option key={v.id} value={v.id}>{v.name}</option>
                        ))}
                      </select>
                      <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={18} />
                    </div>
                    {selectedVerification?.paper?.id && (
                      <a
                        href={`/library/${selectedVerification.paper.id}-pdf原文`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1.5 px-3 py-2 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-lg transition-colors"
                        title="查看论文原文"
                      >
                        <BookOpen size={16} />
                        <span className="text-xs font-bold">论文</span>
                      </a>
                    )}
                  </div>
                </div>

                {/* Data loading */}
                {dataLoading && (
                  <div className="bg-white rounded-2xl border border-slate-200 p-12">
                    <div className="flex flex-col items-center justify-center">
                      <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-200 border-t-purple-600 mb-4" />
                      <p className="text-slate-600 font-bold">加载验证数据中...</p>
                    </div>
                  </div>
                )}

                {/* Verification item */}
                {!dataLoading && selectedVerification?.verification && (() => {
                  const v = selectedVerification.verification
                  const paper = selectedVerification.paper
                  const params: SampleInfo[] = [
                    { label: '真实分布', value: `W(${v.trueParams.beta}, ${v.trueParams.eta}, ${v.trueParams.gamma})` },
                    { label: '样本量', value: `n=${v.sampleSize}` },
                    { label: '偏移量', value: `δ=${v.offset}` },
                    { label: '样本数', value: `${v.nSamples}组` },
                  ]
                  const samplesTableData = {
                    headers: ['样本', 't₁', 't₂', 't₃', 't₄', 't₅', 't₆', 't₇'],
                    rows: samples.map(s => [s.id, ...s.values]),
                  }
                  const chartCurves: GradientCurveData[] = curvesData.slice(0, 30).map((sample, idx) => ({
                    id: sample.sample_id,
                    data: sample.grad_gamma_curve,
                    color: CURVE_COLORS[idx % CURVE_COLORS.length],
                    strokeWidth: 1.5,
                    name: sample.sample_id,
                    opacity: 0.8,
                  }))

                  return (
                    <VerificationItem
                      title={paper?.figure || '验证'}
                      params={params}
                      samplesData={samplesTableData}
                      samplesExpandable={true}
                      paperContent={{
                        type: 'image',
                        src: v.paperImage,
                        alt: paper?.figure || '论文图片',
                      }}
                      systemContent={
                        <GradientGammaChart
                          curves={chartCurves}
                          interactive={false}
                          overlayMode={true}
                          showTitle={false}
                          height={400}
                          offsetReference={v.offset}
                          domain={{ x: [200, 1800], y: [0, 0.6] }}
                        />
                      }
                      chartHeight={450}
                    />
                  )
                })()}
              </>
            )}
          </div>
        ) : (
          <CurvePropertiesViewer />
        )}
      </div>
    )
  }

  // Non-MDM methods: original layout
  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-200 border-t-purple-600 mb-4" />
          <p className="text-slate-600 font-bold">加载验证列表中...</p>
        </div>
      </div>
    )
  }

  if (verifications.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center">
          <BookOpen className="text-slate-300 mb-4" size={48} />
          <h3 className="text-lg font-bold text-slate-600 mb-2">暂无验证项</h3>
          <p className="text-slate-400">该方法的可信性验证正在建设中...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-2xl p-8">
        <p className="text-red-700 font-bold">加载失败: {error}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 验证选择下拉框 */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-4">
          <BookOpen className="text-purple-600" size={20} />
          <label className="text-sm font-bold text-slate-600 whitespace-nowrap">选择验证：</label>
          <div className="relative flex-1 max-w-xl">
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              className="w-full appearance-none bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent cursor-pointer hover:bg-slate-100 transition-colors"
            >
              {verifications.map(v => (
                <option key={v.id} value={v.id}>{v.name}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={18} />
          </div>
          {selectedVerification?.paper?.id && (
            <a
              href={`/library/${selectedVerification.paper.id}-pdf原文`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-2 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-lg transition-colors"
              title="查看论文原文"
            >
              <BookOpen size={16} />
              <span className="text-xs font-bold">论文</span>
            </a>
          )}
        </div>
      </div>

      {/* 数据加载中 */}
      {dataLoading && (
        <div className="bg-white rounded-2xl border border-slate-200 p-12">
          <div className="flex flex-col items-center justify-center">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-200 border-t-purple-600 mb-4" />
            <p className="text-slate-600 font-bold">加载验证数据中...</p>
          </div>
        </div>
      )}

      {/* 验证项 */}
      {!dataLoading && selectedVerification?.verification && (() => {
        const v = selectedVerification.verification
        const paper = selectedVerification.paper
        const params: SampleInfo[] = [
          { label: '真实分布', value: `W(${v.trueParams.beta}, ${v.trueParams.eta}, ${v.trueParams.gamma})` },
          { label: '样本量', value: `n=${v.sampleSize}` },
          { label: '偏移量', value: `δ=${v.offset}` },
          { label: '样本数', value: `${v.nSamples}组` },
        ]
        const samplesTableData = {
          headers: ['样本', 't₁', 't₂', 't₃', 't₄', 't₅', 't₆', 't₇'],
          rows: samples.map(s => [s.id, ...s.values]),
        }
        const chartCurves: GradientCurveData[] = curvesData.slice(0, 30).map((sample, idx) => ({
          id: sample.sample_id,
          data: sample.grad_gamma_curve,
          color: CURVE_COLORS[idx % CURVE_COLORS.length],
          strokeWidth: 1.5,
          name: sample.sample_id,
          opacity: 0.8,
        }))

        return (
          <VerificationItem
            title={paper?.figure || '验证'}
            params={params}
            samplesData={samplesTableData}
            samplesExpandable={true}
            paperContent={{
              type: 'image',
              src: v.paperImage,
              alt: paper?.figure || '论文图片',
            }}
            systemContent={
              <GradientGammaChart
                curves={chartCurves}
                interactive={false}
                overlayMode={true}
                showTitle={false}
                height={400}
                offsetReference={v.offset}
                domain={{ x: [200, 1800], y: [0, 0.6] }}
              />
            }
            chartHeight={450}
          />
        )
      })()}
    </div>
  )
}
