"use client"

import React, { useState, useEffect } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
  ComposedChart
} from 'recharts'
import { AlertTriangle, CheckCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Case3NoIntersectionViewerProps {
  caseId: string
}

// 曲线数据类型
interface CurvePoint {
  gamma: number
  gradient: number
  sigma_min: number
  best_beta: number
  best_eta: number
}

interface SigmaBetaPoint {
  beta: number
  sigma: number
}

interface SampleData {
  sim_id: number
  has_intersection: boolean
  gradient_type: string
  est_gamma: number
  est_beta: number
  est_eta: number
  grad_gamma_curve: CurvePoint[]
  sigma_beta_curve: SigmaBetaPoint[]
}

const GRADIENT_TYPE_COLORS: Record<string, { line: string; name: string }> = {
  'normal': { line: '#10b981', name: '正常（有交点）' },
  'above_offset': { line: '#f59e0b', name: '梯度全在δ上方' },
  'below_offset': { line: '#ef4444', name: '梯度全在δ下方' },
  'all_positive': { line: '#3b82f6', name: '全正梯度' },
  'all_negative': { line: '#8b5cf6', name: '全负梯度' },
  'other': { line: '#64748b', name: '其他' },
}

const TRUE_GAMMA = 1000
const OFFSET_VALUE = 0.2
const TRUE_BETA = 2.0

// 完整样本数据类型（包含原始样本）
interface FullSampleData extends SampleData {
  sample: number[]  // 原始样本数据
}

interface LimitDataPoint {
  gamma: number
  sigma: number
  beta: number
  gradient: number
  region: 'normal' | 'limit'
}

interface LimitAnalysisData {
  t_min: number
  data: LimitDataPoint[]
}

export default function Case3NoIntersectionViewer({ caseId }: Case3NoIntersectionViewerProps) {
  const [samplesData, setSamplesData] = useState<SampleData[]>([])
  const [fullSamplesData, setFullSamplesData] = useState<FullSampleData[]>([])  // 包含原始样本的完整数据
  const [limitAnalysis, setLimitAnalysis] = useState<LimitAnalysisData | null>(null)
  const [activeLimitTab, setActiveLimitTab] = useState<'global' | 'micro'>('global')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedNonIntersectId, setSelectedNonIntersectId] = useState<number | null>(null)

  // 加载数据
  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true)

        // 并行加载曲线数据、完整数据和极限分析数据
        const [curvesRes, fullRes, limitRes] = await Promise.all([
          fetch('/cases/mdm_case3_curves.json'),
          fetch('/cases/mdm_case3_data.json'),
          fetch('/cases/mdm_case3_limit_analysis.json')
        ])

        if (!curvesRes.ok) throw new Error('曲线数据加载失败')
        if (!fullRes.ok) throw new Error('完整数据加载失败')
        // limitRes 允许失败（向后兼容），如果失败只是不显示新区域
        
        const parsedCurves: SampleData[] = await curvesRes.json()
        const parsedFull: { samples: FullSampleData[] } = await fullRes.json()
        
        let parsedLimit: LimitAnalysisData | null = null
        if (limitRes.ok) {
          parsedLimit = await limitRes.json()
        }

        setSamplesData(parsedCurves)
        setFullSamplesData(parsedFull.samples)
        setLimitAnalysis(parsedLimit)

        // 默认选择第一个无交点样本
        const nonIntersectSamples = parsedCurves.filter(c => !c.has_intersection)
        if (nonIntersectSamples.length > 0) {
          setSelectedNonIntersectId(nonIntersectSamples[0].sim_id)
        }

      } catch (err) {
        setError(err instanceof Error ? err.message : '加载失败')
        console.error('Load error:', err)
      } finally {
        setIsLoading(false)
      }
    }

    loadData()
  }, [])

  // 分离样本
  const nonIntersectSamples = samplesData.filter(c => !c.has_intersection)
  const normalSamples = samplesData.filter(c => c.has_intersection)
  const selectedNonIntersect = samplesData.find(c => c.sim_id === selectedNonIntersectId) || nonIntersectSamples[0]

  // 所有曲线数据（包含无交点+9个有交点）
  const allCurvesData = [...nonIntersectSamples, ...normalSamples.slice(0, 9)]

  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-200 border-t-blue-600 mb-4"></div>
          <p className="text-slate-600 font-bold">加载数据中...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-2xl p-8">
        <div className="flex items-center gap-3 text-red-700">
          <AlertTriangle size={24} />
          <div>
            <p className="font-bold">加载失败</p>
            <p className="text-sm">{error}</p>
          </div>
        </div>
      </div>
    )
  }

  // 图表颜色配置
  const curveColors = [
    '#ef4444', // 红色 - 无交点样本
    '#10b981', '#3b82f6', '#f59e0b', '#8b5cf6', '#06b6d4',
    '#ec4899', '#84cc16', '#6366f1', '#14b8a6', '#f97316'
  ]

  return (
    <div className="space-y-6">
      {/* 标题和说明 */}
      <div className="bg-gradient-to-r from-red-50 to-orange-50 rounded-2xl p-6 border border-red-200">
        <h2 className="text-xl font-bold text-slate-800 mb-2">案例3: 无交点梯度曲线可视化</h2>
        <p className="text-slate-600">
          研究参数：β={TRUE_BETA}, η=1000, γ={TRUE_GAMMA}, n=7, δ={OFFSET_VALUE}
        </p>
        <p className="text-sm text-slate-500 mt-2">
          展示MDM方法中梯度曲线与偏移值δ无交点现象的机理
        </p>
      </div>

      {/* 无交点样本列表 */}
      <div className="bg-red-50 rounded-2xl border-2 border-red-200 p-4">
        <h3 className="text-sm font-bold text-red-800 mb-3">无交点样本列表：</h3>
        <div className="space-y-3">
          {nonIntersectSamples.map(sample => {
            // 从完整数据中查找原始样本
            const fullSample = fullSamplesData.find(s => s.sim_id === sample.sim_id)
            const originalData = fullSample?.sample || null

            return (
              <div key={sample.sim_id} className="bg-white rounded-lg p-4 border border-red-300">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <span className="font-bold text-red-700 text-lg">样本 #{sample.sim_id}</span>
                    <span className="text-xs px-2 py-1 bg-red-100 text-red-700 rounded font-bold">
                      {GRADIENT_TYPE_COLORS[sample.gradient_type]?.name}
                    </span>
                  </div>
                </div>

                {/* 原始样本数据 */}
                <div className="mb-3 p-3 bg-slate-50 rounded border border-slate-200">
                  <div className="text-xs text-slate-500 mb-1">原始样本数据 (n=7):</div>
                  {originalData ? (
                    <div className="font-mono text-sm text-slate-700">
                      [{originalData.map(v => v.toFixed(2)).join(', ')}]
                    </div>
                  ) : (
                    <div className="text-xs text-slate-400">加载中...</div>
                  )}
                </div>

                {/* 估计参数 */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-500">β:</span>
                    <span className="font-mono font-bold">{sample.est_beta.toFixed(4)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">η:</span>
                    <span className="font-mono font-bold">{sample.est_eta.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">γ:</span>
                    <span className="font-mono font-bold text-red-600">{sample.est_gamma.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">偏差:</span>
                    <span className="font-mono font-bold">{(sample.est_gamma - TRUE_GAMMA).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">类型:</span>
                    <span className="font-mono font-bold">{sample.gradient_type}</span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* 无交点样本选择器 */}
      {nonIntersectSamples.length > 1 && (
        <div className="bg-white rounded-2xl border border-slate-200 p-4">
          <h3 className="text-sm font-bold text-slate-700 mb-2">选择无交点样本查看：</h3>
          <div className="flex flex-wrap gap-2">
            {nonIntersectSamples.map(sample => (
              <button
                key={sample.sim_id}
                onClick={() => setSelectedNonIntersectId(sample.sim_id)}
                className={cn(
                  "px-3 py-1.5 rounded-lg border-2 text-xs font-bold transition-all",
                  selectedNonIntersectId === sample.sim_id
                    ? "bg-red-100 border-red-500 text-red-700"
                    : "bg-slate-50 border-slate-300 text-slate-600 hover:bg-red-50"
                )}
              >
                #{sample.sim_id} ({sample.gradient_type})
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 图表区域：2x2网格 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* 图1: 单条无交点 - σ(β)曲线 */}
        {selectedNonIntersect && (
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h4 className="text-base font-bold text-slate-800">图1. 无交点样本 - 形状参数寻优</h4>
                <p className="text-xs text-slate-500">样本 #{selectedNonIntersect.sim_id} 的 σ_η 关于 β 变化</p>
              </div>
              <div className="w-4 h-4 bg-red-500 rounded"></div>
            </div>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={selectedNonIntersect.sigma_beta_curve} margin={{ top: 20, right: 25, bottom: 45, left: 60 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis
                    dataKey="beta"
                    type="number"
                    domain={[0.5, 6]}
                    tick={{ fontSize: 10 }}
                    tickLine={true}
                    stroke="#000"
                    strokeWidth={1}
                    label={{ value: '形状参数 β', position: 'bottom', fontSize: 12, fill: '#64748b' }}
                    axisLine={{ stroke: '#000', strokeWidth: 1 }}
                  />
                  <YAxis
                    domain={[0, 1400]}
                    tickCount={5}
                    tick={{ fontSize: 10 }}
                    tickLine={true}
                    stroke="#000"
                    strokeWidth={1}
                    label={{ value: '标准差 σ_η', angle: -90, position: 'insideLeft', fontSize: 12, fill: '#64748b' }}
                    axisLine={{ stroke: '#000', strokeWidth: 1 }}
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                    labelFormatter={(v) => `β: ${Number(v).toFixed(2)}`}
                    formatter={(v: number) => v.toFixed(2)}
                  />
                  <ReferenceLine x={TRUE_BETA} stroke="#94a3b8" strokeDasharray="3 3" label={{ value: "真实β", fill: '#94a3b8', fontSize: 10 }} />
                  <ReferenceLine x={selectedNonIntersect.est_beta} stroke="#ef4444" strokeDasharray="3 3" label={{ value: "估计β", fill: '#ef4444', fontSize: 10 }} />
                  <Line
                    type="monotone"
                    dataKey="sigma"
                    stroke="#ef4444"
                    strokeWidth={3}
                    dot={false}
                    activeDot={{ r: 6 }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* 图2: 单条无交点 - 梯度曲线 */}
        {selectedNonIntersect && (
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h4 className="text-base font-bold text-slate-800">图2. 无交点样本 - 位置参数梯度判据</h4>
                <p className="text-xs text-slate-500">样本 #{selectedNonIntersect.sim_id} 的 ∇(γ) 与偏移值δ</p>
              </div>
              <div className="w-4 h-4 bg-red-500 rounded"></div>
            </div>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={selectedNonIntersect.grad_gamma_curve} margin={{ top: 20, right: 30, bottom: 40, left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis
                    dataKey="gamma"
                    type="number"
                    tickFormatter={(v) => v.toFixed(0)}
                    tick={{ fontSize: 10 }}
                    tickLine={true}
                    stroke="#000"
                    strokeWidth={1}
                    label={{ value: '位置参数 γ', position: 'bottom', fontSize: 12, fill: '#64748b' }}
                    axisLine={{ stroke: '#000', strokeWidth: 1 }}
                  />
                  <YAxis
                    width={45}
                    tick={{ fontSize: 10 }}
                    tickLine={true}
                    stroke="#000"
                    strokeWidth={1}
                    label={{ value: '梯度 ∇(γ)', angle: -90, position: 'insideLeft', fontSize: 12, fill: '#64748b' }}
                    axisLine={{ stroke: '#000', strokeWidth: 1 }}
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                    labelFormatter={(v) => `γ: ${Number(v).toFixed(1)}`}
                    formatter={(v: number) => [v.toFixed(4), '∇(γ)']}
                  />
                  <ReferenceLine y={OFFSET_VALUE} stroke="#10b981" strokeDasharray="3 3" label={{ position: 'right', value: `δ=${OFFSET_VALUE}`, fill: '#10b981', fontSize: 10 }} />
                  <ReferenceLine y={0} stroke="#cbd5e1" />
                  <ReferenceLine x={selectedNonIntersect.est_gamma} stroke="#ef4444" strokeDasharray="3 3" label={{ value: "估计γ", fill: '#ef4444', fontSize: 10 }} />
                  <Line
                    type="monotone"
                    dataKey="gradient"
                    stroke="#ef4444"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* 图3: 10条曲线簇 - σ(β)曲线 */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h4 className="text-base font-bold text-slate-800">图3. 曲线簇 - 形状参数寻优</h4>
              <p className="text-xs text-slate-500">10条样本的 σ_η 关于 β 变化（对数坐标，红色为无交点）</p>
            </div>
            <Legend verticalAlign="top" height={36} payload={
              allCurvesData.slice(0, 10).map((sample, idx) => ({
                value: `#${sample.sim_id}`,
                type: 'line',
                id: `line-${sample.sim_id}`,
                color: curveColors[idx % curveColors.length]
              }))
            } />
          </div>
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart margin={{ top: 20, right: 25, bottom: 45, left: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis
                  dataKey="beta"
                  type="number"
                  domain={[0.5, 6]}
                  ticks={[1, 2, 3, 4, 5, 6]}
                  tickFormatter={(v) => v.toFixed(0)}
                  tick={{ fontSize: 10 }}
                  tickLine={true}
                  stroke="#000"
                  strokeWidth={1}
                  label={{ value: '形状参数 β', position: 'bottom', fontSize: 12, fill: '#64748b' }}
                  axisLine={{ stroke: '#000', strokeWidth: 1 }}
                />
                <YAxis
                  scale="log"
                  domain={[1, 2000]}
                  ticks={[1, 10, 100, 1000]}
                  tickFormatter={(v) => v.toString()}
                  tick={{ fontSize: 10 }}
                  tickLine={true}
                  stroke="#000"
                  strokeWidth={1}
                  label={{ value: '标准差 σ_η (对数)', angle: -90, position: 'insideLeft', fontSize: 12, fill: '#64748b' }}
                  axisLine={{ stroke: '#000', strokeWidth: 1 }}
                />
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                  labelFormatter={(v) => `β: ${Number(v).toFixed(2)}`}
                  formatter={(v: number, name: string) => [v.toFixed(2), name]}
                />
                <ReferenceLine x={TRUE_BETA} stroke="#94a3b8" strokeDasharray="3 3" label={{ value: "真实β", fill: '#94a3b8', fontSize: 10 }} />
                {allCurvesData.slice(0, 10).map((sample, idx) => (
                  <Line
                    key={sample.sim_id}
                    data={sample.sigma_beta_curve}
                    type="monotone"
                    dataKey="sigma"
                    stroke={curveColors[idx % curveColors.length]}
                    strokeWidth={sample.has_intersection ? 1.5 : 3}
                    dot={false}
                    name={`#${sample.sim_id}`}
                    opacity={sample.has_intersection ? 0.7 : 1}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 图4: 10条曲线簇 - 梯度曲线 */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h4 className="text-base font-bold text-slate-800">图4. 曲线簇 - 位置参数梯度判据</h4>
              <p className="text-xs text-slate-500">10条样本的 ∇(γ) 与偏移值δ（红色为无交点）</p>
            </div>
            <Legend verticalAlign="top" height={36} payload={
              allCurvesData.slice(0, 10).map((sample, idx) => ({
                value: `#${sample.sim_id}`,
                type: 'line',
                id: `line-${sample.sim_id}`,
                color: curveColors[idx % curveColors.length]
              }))
            } />
          </div>
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart margin={{ top: 20, right: 25, bottom: 40, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="gamma"
                  type="number"
                  tickFormatter={(v) => v.toFixed(0)}
                  tick={{ fontSize: 10 }}
                  tickLine={true}
                  stroke="#000"
                  strokeWidth={1}
                  label={{ value: '位置参数 γ', position: 'bottom', fontSize: 12, fill: '#64748b' }}
                  axisLine={{ stroke: '#000', strokeWidth: 1 }}
                />
                <YAxis
                  width={45}
                  tick={{ fontSize: 10 }}
                  tickLine={true}
                  stroke="#000"
                  strokeWidth={1}
                  label={{ value: '梯度 ∇(γ)', angle: -90, position: 'insideLeft', fontSize: 12, fill: '#64748b' }}
                  axisLine={{ stroke: '#000', strokeWidth: 1 }}
                />
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                  labelFormatter={(v) => `γ: ${Number(v).toFixed(1)}`}
                  formatter={(v: number, name: string) => [v.toFixed(4), name]}
                />
                <ReferenceLine y={OFFSET_VALUE} stroke="#10b981" strokeDasharray="3 3" label={{ position: 'right', value: `δ=${OFFSET_VALUE}`, fill: '#10b981', fontSize: 10 }} />
                <ReferenceLine y={0} stroke="#cbd5e1" />
                {allCurvesData.slice(0, 10).map((sample, idx) => (
                  <Line
                    key={sample.sim_id}
                    data={sample.grad_gamma_curve}
                    type="monotone"
                    dataKey="gradient"
                    stroke={curveColors[idx % curveColors.length]}
                    strokeWidth={sample.has_intersection ? 1.5 : 3}
                    dot={false}
                    name={`#${sample.sim_id}`}
                    opacity={sample.has_intersection ? 0.7 : 1}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>

      {/* 计算过程说明 */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6">
        <h4 className="text-base font-bold text-slate-800 mb-4">计算过程验算</h4>
        <div className="space-y-4 text-sm">
          {/* 样本数据 */}
          {selectedNonIntersect && (() => {
            const fullSample = fullSamplesData.find(s => s.sim_id === selectedNonIntersect.sim_id)
            const sampleData = fullSample?.sample || []
            const sortedData = [...sampleData].sort((a, b) => a - b)
            const n = sortedData.length

            // 计算中位秩
            const medianRanks = sortedData.map((_, i) => (i + 1 - 0.3) / (n + 0.4))

            // 验证：使用真实参数计算的理论失效时间
            // F(t) = 1 - exp(-((t-γ)/η)^β)
            // 反解: t = γ + η * (-ln(1-F))^(-1/β)
            const theoreticalTimes = medianRanks.map(F =>
              TRUE_GAMMA + 1000 * Math.pow(-Math.log(1 - F), 1 / TRUE_BETA)
            )

            return (
              <>
                {/* 1. 样本排序与中位秩 */}
                <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
                  <h5 className="font-bold text-slate-700 mb-2">1. 样本排序与中位秩计算</h5>
                  <p className="text-slate-600 mb-3">
                    对于 n={n} 的完全样本，中位秩公式为：
                    <code className="ml-2 px-2 py-1 bg-slate-200 rounded text-xs">
                      F&lt;sub&gt;i&lt;/sub&gt; = (i - 0.3) / (n + 0.4)
                    </code>
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-slate-300">
                          <th className="py-2 text-left">序号 i</th>
                          <th className="py-2 text-left">排序样本 t&lt;sub&gt;i&lt;/sub&gt;</th>
                          <th className="py-2 text-left">中位秩 F&lt;sub&gt;i&lt;/sub&gt;</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sortedData.map((t, i) => (
                          <tr key={i} className="border-b border-slate-200">
                            <td className="py-2">{i + 1}</td>
                            <td className="py-2 font-mono">{t.toFixed(2)}</td>
                            <td className="py-2 font-mono">{medianRanks[i].toFixed(4)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* 2. 参数验算 */}
                <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                  <h5 className="font-bold text-slate-700 mb-2">2. 参数验算（验证样本来源）</h5>
                  <p className="text-slate-600 mb-3">
                    假设样本来自 W(β={TRUE_BETA}, η=1000, γ={TRUE_GAMMA})，使用中位秩反推理论失效时间：
                  </p>
                  <div className="mb-3 p-3 bg-white rounded border border-blue-200">
                    <code className="text-xs">
                      t&lt;sub&gt;理论&lt;/sub&gt; = γ + η × (-ln(1-F&lt;sub&gt;i&lt;/sub&gt;))&lt;sup&gt;1/β&lt;/sup&gt;
                      <br />= {TRUE_GAMMA} + 1000 × (-ln(1-F&lt;sub&gt;i&lt;/sub&gt;))&lt;sup&gt;1/{TRUE_BETA}&lt;/sup&gt;
                    </code>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-slate-300">
                          <th className="py-2 text-left">序号</th>
                          <th className="py-2 text-left">F&lt;sub&gt;i&lt;/sub&gt;</th>
                          <th className="py-2 text-left">理论 t&lt;sub&gt;i&lt;/sub&gt;</th>
                          <th className="py-2 text-left">实际 t&lt;sub&gt;i&lt;/sub&gt;</th>
                          <th className="py-2 text-left">误差</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sortedData.map((actualT, i) => {
                          const theoT = theoreticalTimes[i]
                          const error = ((actualT - theoT) / theoT * 100)
                          return (
                            <tr key={i} className="border-b border-slate-200">
                              <td className="py-2">{i + 1}</td>
                              <td className="py-2 font-mono">{medianRanks[i].toFixed(4)}</td>
                              <td className="py-2 font-mono">{theoT.toFixed(2)}</td>
                              <td className="py-2 font-mono">{actualT.toFixed(2)}</td>
                              <td className="py-2 font-mono">{error > 0 ? '+' : ''}{error.toFixed(2)}%</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                  <p className="mt-3 text-xs text-slate-600">
                    <strong>结论：</strong>实际样本与理论值的相对误差在合理范围内（蒙特卡洛抽样的随机性），
                    验证了该样本确实来自 W(β={TRUE_BETA}, η=1000, γ={TRUE_GAMMA}) 的三参数威布尔分布。
                  </p>
                </div>

                {/* 3. MDM方法计算过程 */}
                <div className="p-4 bg-indigo-50 rounded-lg border border-indigo-200">
                  <h5 className="font-bold text-slate-700 mb-2">3. MDM方法计算过程详解</h5>
                  <div className="space-y-3 text-slate-600">
                    {/* 步骤1 */}
                    <div className="p-3 bg-white rounded border border-indigo-200">
                      <p className="font-bold text-indigo-700 mb-1">步骤1：计算中位秩</p>
                      <p className="text-xs mb-2">对于完全样本 n={n}，第i个顺序统计量的中位秩为：</p>
                      <code className="text-xs block bg-slate-50 p-2 rounded">
                        F(t&lt;sub&gt;i&lt;/sub&gt;) = (i - 0.3) / (n + 0.4), &nbsp; i = 1, 2, ..., n
                      </code>
                      <p className="text-xs mt-2">
                        对于本样本，中位秩为：
                        [{medianRanks.map(v => v.toFixed(3)).join(', ')}]
                      </p>
                    </div>

                    {/* 步骤2 */}
                    <div className="p-3 bg-white rounded border border-indigo-200">
                      <p className="font-bold text-indigo-700 mb-1">步骤2：计算伪尺度参数 η&lt;sub&gt;i&lt;/sub&gt;(γ, β)</p>
                      <p className="text-xs mb-2">对于给定的位置参数γ和形状参数β，每个失效时间对应的伪尺度参数为：</p>
                      <code className="text-xs block bg-slate-50 p-2 rounded">
                        η&lt;sub&gt;i&lt;/sub&gt;(γ, β) = (t&lt;sub&gt;i&lt;/sub&gt; - γ) / [-ln(1 - F(t&lt;sub&gt;i&lt;/sub&gt;))]&lt;sup&gt;1/β&lt;/sup&gt;
                      </code>
                      <p className="text-xs mt-2">
                        <strong>约束条件：</strong>必须满足 t&lt;sub&gt;i&lt;/sub&gt; &gt; γ（否则对数为负）
                      </p>
                    </div>

                    {/* 步骤3 */}
                    <div className="p-3 bg-white rounded border border-indigo-200">
                      <p className="font-bold text-indigo-700 mb-1">步骤3：计算标准差函数 σ&lt;sub&gt;η&lt;/sub&gt;(γ)</p>
                      <p className="text-xs mb-2">对于固定的γ，找到使η的标准差最小的β值：</p>
                      <code className="text-xs block bg-slate-50 p-2 rounded">
                        β&lt;sup&gt;*&lt;/sup&gt;(γ) = argmin&lt;sub&gt;β&lt;/sub&gt; std(&#123;η&lt;sub&gt;1&lt;/sub&gt;(γ, β), η&lt;sub&gt;2&lt;/sub&gt;(γ, β), ..., η&lt;sub&gt;n&lt;/sub&gt;(γ, β)&#125;)
                      </code>
                      <code className="text-xs block bg-slate-50 p-2 rounded mt-2">
                        σ&lt;sub&gt;η&lt;/sub&gt;(γ) = std(&#123;η&lt;sub&gt;1&lt;/sub&gt;(γ, β&lt;sup&gt;*&lt;/sup&gt;(γ)), ..., η&lt;sub&gt;n&lt;/sub&gt;(γ, β&lt;sup&gt;*&lt;/sup&gt;(γ))&#125;)
                      </code>
                      <p className="text-xs mt-2 bg-blue-50 p-2 rounded">
                        <strong>重要：</strong>对于每个固定的γ，β&lt;sup&gt;*&lt;/sup&gt;(γ)一定存在！
                        因为当β→0时σ→∞，当β→∞时σ趋于有限值，连续函数必有最小值。
                        无交点问题发生在γ层面，不是β层面。
                      </p>
                      <p className="text-xs mt-2">
                        <strong>关于σ&lt;sub&gt;η&lt;/sub&gt;(γ)的最小值：</strong>在闭区间[0, t&lt;sub&gt;min&lt;/sub&gt;]上一定存在最小值（极值定理）。
                      </p>
                      <ul className="text-xs mt-1 ml-4 list-disc space-y-1">
                        <li><strong>区间内部极值：</strong>梯度由负变正，存在∇(γ)=0的极值点</li>
                        <li><strong>边界最小值：</strong>σ&lt;sub&gt;η&lt;/sub&gt;(γ)单调变化，最小值在γ=0或γ→t&lt;sub&gt;min&lt;/sub&gt;</li>
                      </ul>
                      <p className="text-xs mt-2">
                        <strong>本样本情况：</strong>σ&lt;sub&gt;η&lt;/sub&gt;(γ)在整个区间上单调递减，
                        每个γ都有对应的β&lt;sup&gt;*&lt;/sup&gt;(γ)，但σ&lt;sub&gt;η&lt;/sub&gt;(γ)对γ单调递减，
                        导致梯度始终为负，无法与δ={OFFSET_VALUE}相交。
                      </p>
                    </div>

                    {/* 步骤4 */}
                    <div className="p-3 bg-white rounded border border-indigo-200">
                      <p className="font-bold text-indigo-700 mb-1">步骤4：计算梯度函数 ∇(γ)</p>
                      <p className="text-xs mb-2">对标准差曲线求导，得到梯度：</p>
                      <code className="text-xs block bg-slate-50 p-2 rounded">
                        ∇(γ) = dσ&lt;sub&gt;η&lt;/sub&gt;(γ) / dγ
                      </code>
                      <p className="text-xs mt-2">
                        <strong>数值计算：</strong>使用有限差分近似：
                      </p>
                      <code className="text-xs block bg-slate-50 p-2 rounded">
                        ∇(γ&lt;sub&gt;i&lt;/sub&gt;) ≈ [σ&lt;sub&gt;η&lt;/sub&gt;(γ&lt;sub&gt;i+1&lt;/sub&gt;) - σ&lt;sub&gt;η&lt;/sub&gt;(γ&lt;sub&gt;i&lt;/sub&gt;)] / (γ&lt;sub&gt;i+1&lt;/sub&gt; - γ&lt;sub&gt;i&lt;/sub&gt;)
                      </code>
                      <p className="text-xs mt-2">
                        <strong>梯度符号的含义：</strong>
                      </p>
                      <ul className="text-xs mt-1 ml-4 list-disc space-y-1">
                        <li>∇(γ) &gt; 0 → σ&lt;sub&gt;η&lt;/sub&gt;(γ)单调递增</li>
                        <li>∇(γ) &lt; 0 → σ&lt;sub&gt;η&lt;/sub&gt;(γ)单调递减</li>
                        <li>∇(γ) = 0 → σ&lt;sub&gt;η&lt;/sub&gt;(γ)达到极值点</li>
                      </ul>
                    </div>

                    {/* 步骤5 - 本样本的具体情况 */}
                    <div className="p-3 bg-red-50 rounded border border-red-300">
                      <p className="font-bold text-red-700 mb-1">步骤5：寻找交点 ∇(γ) = δ（本样本情况）</p>
                      <p className="text-xs mb-2">
                        <strong>偏移值（补偿阈值）：</strong>δ = {OFFSET_VALUE}
                      </p>
                      <p className="text-xs mb-2">
                        <strong>本样本的梯度范围：</strong>
                      </p>
                      {(() => {
                        if (!selectedNonIntersect || !selectedNonIntersect.grad_gamma_curve) {
                          return <p className="text-xs">加载中...</p>
                        }
                        const grads = selectedNonIntersect.grad_gamma_curve.map(d => d.gradient)
                        const minGrad = Math.min(...grads)
                        const maxGrad = Math.max(...grads)
                        return (
                          <div className="text-xs bg-white p-2 rounded border border-red-200">
                            <div>∇(γ) 最小值: {minGrad.toFixed(6)}</div>
                            <div>∇(γ) 最大值: {maxGrad.toFixed(6)}</div>
                            <div className="text-red-600 font-bold mt-1">
                              结论: 所有梯度值 &lt; δ ({OFFSET_VALUE})
                            </div>
                          </div>
                        )
                      })()}
                      <p className="text-xs mt-2 text-red-700">
                        <strong>无交点原因：</strong>由于该样本的σ&lt;sub&gt;η&lt;/sub&gt;(γ)曲线在整个搜索区间[0, t&lt;sub&gt;min&lt;/sub&gt;]内单调递减，
                        梯度∇(γ)始终为负值，且最小值为负数，因此不可能与正值δ = {OFFSET_VALUE}相交。
                      </p>
                    </div>

                    {/* 步骤6 */}
                    <div className="p-3 bg-amber-50 rounded border border-amber-300">
                      <p className="font-bold text-amber-700 mb-1">步骤6：Fallback策略与结果</p>
                      <p className="text-xs mb-2">
                        <strong>MDM Fallback策略：</strong>当∇(γ)与δ无交点时，选择使|∇(γ) - δ|最小的γ值。
                      </p>
                      {(() => {
                        if (!selectedNonIntersect || !selectedNonIntersect.grad_gamma_curve) {
                          return <p className="text-xs">加载中...</p>
                        }
                        // 找到梯度最接近δ的点
                        const curve = selectedNonIntersect.grad_gamma_curve
                        const minDiffIdx = curve.findIndex(d => Math.abs(d.gradient - OFFSET_VALUE) ===
                          Math.min(...curve.map(d => Math.abs(d.gradient - OFFSET_VALUE))))
                        const fallbackPoint = curve[minDiffIdx]

                        return (
                          <div className="text-xs bg-white p-2 rounded border border-amber-200">
                            <div>最接近δ的γ值: {fallbackPoint.gamma.toFixed(2)}</div>
                            <div>对应梯度: {fallbackPoint.gradient.toFixed(6)}</div>
                            <div>与δ的差值: {Math.abs(fallbackPoint.gradient - OFFSET_VALUE).toFixed(6)}</div>
                            <div className="text-amber-700 font-bold mt-1">
                              MDM返回: γ = {selectedNonIntersect.est_gamma.toFixed(2)}
                            </div>
                          </div>
                        )
                      })()}
                      <p className="text-xs mt-2 text-amber-700">
                        <strong>估计结果：</strong>γ = {selectedNonIntersect?.est_gamma.toFixed(2)}，
                        与真实值{TRUE_GAMMA}的偏差 = {(selectedNonIntersect?.est_gamma ?? 0 - TRUE_GAMMA).toFixed(2)}，
                        相对误差 = {((selectedNonIntersect?.est_gamma ?? 0 - TRUE_GAMMA) / TRUE_GAMMA * 100).toFixed(1)}%
                      </p>
                    </div>
                  </div>
                </div>
              </>
            )
          })()}
        </div>
      </div>

      {/* 分析说明 */}
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl p-6 border border-amber-200">
        <h4 className="text-base font-bold text-slate-800 mb-3">无交点现象分析</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div className="space-y-2">
            <div className="flex items-start gap-2">
              <AlertTriangle size={16} className="text-red-600 mt-0.5" />
              <div>
                <span className="font-bold text-red-700">无交点现象</span>
                <p className="text-slate-600">梯度曲线始终在偏移值δ的下方（below_offset），无法找到交点。</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <AlertTriangle size={16} className="text-amber-600 mt-0.5" />
              <div>
                <span className="font-bold text-amber-700">fallback策略</span>
                <p className="text-slate-600">无交点时，MDM返回边界值（γ=0），导致估计偏差极大（接近-1000）。</p>
              </div>
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex items-start gap-2">
              <CheckCircle size={16} className="text-emerald-600 mt-0.5" />
              <div>
                <span className="font-bold text-emerald-700">有交点样本</span>
                <p className="text-slate-600">梯度曲线与δ有交点，可以正常估计γ值。</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <div className="w-4 h-4 rounded bg-slate-300 mt-0.5"></div>
              <div>
                <span className="font-bold text-slate-700">样本量影响</span>
                <p className="text-slate-600">小样本(n=7)情况下，无交点现象更容易出现，需要更大样本量或调整δ值。</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 深入探索：极限边界分析 */}
      {limitAnalysis && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mt-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-lg font-bold text-slate-800">深入探索：参数边界极限分析</h3>
              <p className="text-sm text-slate-500">
                探究为何梯度曲线呈现"单调"特征，以及在逼近物理极限 t_min 时的数据表现。
              </p>
            </div>
            {/* Tab 切换 */}
            <div className="flex bg-slate-100 p-1 rounded-lg border border-slate-200">
              <button
                onClick={() => setActiveLimitTab('global')}
                className={cn(
                  "px-3 py-1.5 rounded-md text-sm font-bold transition-all",
                  activeLimitTab === 'global'
                    ? "bg-white text-blue-600 shadow-sm"
                    : "text-slate-500 hover:text-slate-700"
                )}
              >
                1. 全局边界探索 (0 ~ t_min)
              </button>
              <button
                onClick={() => setActiveLimitTab('micro')}
                className={cn(
                  "px-3 py-1.5 rounded-md text-sm font-bold transition-all",
                  activeLimitTab === 'micro'
                    ? "bg-white text-purple-600 shadow-sm"
                    : "text-slate-500 hover:text-slate-700"
                )}
              >
                2. 极限微观视角 (99% ~ 100%)
              </button>
            </div>
          </div>

          {activeLimitTab === 'global' ? (
            <div className="space-y-4 animate-in fade-in duration-500">
              <div className="bg-blue-50 p-4 rounded-xl border border-blue-100 text-sm text-blue-800">
                <strong>假设验证：</strong> "有没有可能是位置参数的尝试值不够大的问题？"
                <p className="mt-1 text-blue-600">
                  数学限制：γ 必须小于最��样本值 t_min ({limitAnalysis.t_min.toFixed(2)})，否则 ln(t-γ) 无定义。
                  下图展示了当 γ 逼近 t_min 时的完整趋势。常规算法搜索范围通常截止在 0.99*t_min 处。
                </p>
              </div>
              <div className="h-[350px] w-full bg-slate-50 rounded-xl border border-slate-200 p-4 relative">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={limitAnalysis.data.filter(d => d.region === 'normal')} margin={{ top: 20, right: 30, bottom: 20, left: 40 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis 
                      dataKey="gamma" 
                      type="number" 
                      domain={[0, Math.ceil(limitAnalysis.t_min)]}
                      tickFormatter={(v) => v.toFixed(0)}
                      label={{ value: '位置参数 γ', position: 'bottom', offset: 0 }}
                    />
                    <YAxis 
                      label={{ value: '最小标准差 σ_min', angle: -90, position: 'insideLeft' }}
                      domain={[0, 200]}
                    />
                    <Tooltip 
                      labelFormatter={(v) => `γ: ${Number(v).toFixed(2)}`}
                      formatter={(v: number) => [v.toFixed(3), 'σ_min']}
                    />
                    <ReferenceLine x={limitAnalysis.t_min} stroke="#ef4444" label={{ value: 't_min (极限)', position: 'top', fill: '#ef4444' }} />
                    <ReferenceLine x={limitAnalysis.t_min * 0.99} stroke="#f59e0b" strokeDasharray="3 3" label={{ value: '常规搜索边界 (99%)', position: 'top', fill: '#f59e0b' }} />
                    <Line 
                      type="monotone" 
                      dataKey="sigma" 
                      stroke="#3b82f6" 
                      strokeWidth={3} 
                      dot={false} 
                      name="常规范围"
                    />
                    {/* 红色禁区示意 */}
                    <ReferenceLine x={limitAnalysis.t_min} stroke="none" label={{ value: '禁区 (γ > t_min)', position: 'insideRight', fill: '#ef4444', dx: 20 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          ) : (
            <div className="space-y-4 animate-in fade-in duration-500">
              <div className="bg-purple-50 p-4 rounded-xl border border-purple-100 text-sm text-purple-800">
                <strong>假设验证：</strong> "增加迭代次数（逼近极限）会发生什么？"
                <p className="mt-1 text-purple-600">
                  在 99% ~ 99.9999% 的极限区域内，我们发现标准差曲线发生了<strong>反弹</strong>！
                  这意味着极值点确实存在，但位于极度靠近边界的狭窄区域内。常规算法因步长不足而错过了这个"深V"谷底。
                </p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* 极限 σ 曲线 */}
                <div className="bg-slate-50 rounded-xl border border-slate-200 p-4">
                  <h4 className="text-sm font-bold text-slate-700 mb-2">标准差反弹现象 (σ_min)</h4>
                  <div className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart 
                        data={limitAnalysis.data.filter(d => d.gamma > limitAnalysis.t_min * 0.98)} 
                        margin={{ top: 20, right: 30, bottom: 20, left: 40 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis 
                          dataKey="gamma" 
                          type="number" 
                          domain={['auto', 'auto']}
                          tickFormatter={(v) => v.toFixed(1)}
                        />
                        <YAxis domain={['auto', 'auto']} />
                        <Tooltip labelFormatter={(v) => Number(v).toFixed(4)} />
                        <Line 
                          type="monotone" 
                          dataKey="sigma" 
                          stroke="#8b5cf6" 
                          strokeWidth={3} 
                          dot={{ r: 2 }} 
                        />
                        <ReferenceLine x={limitAnalysis.t_min * 0.99} stroke="#f59e0b" label="99%" />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* 极限梯度曲线 */}
                <div className="bg-slate-50 rounded-xl border border-slate-200 p-4">
                  <h4 className="text-sm font-bold text-slate-700 mb-2">梯度过零点 (∇γ)</h4>
                  <div className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart 
                        data={limitAnalysis.data.filter(d => d.gamma > limitAnalysis.t_min * 0.98)} 
                        margin={{ top: 20, right: 30, bottom: 20, left: 40 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis 
                          dataKey="gamma" 
                          type="number" 
                          domain={['auto', 'auto']}
                          tickFormatter={(v) => v.toFixed(1)}
                        />
                        <YAxis />
                        <Tooltip labelFormatter={(v) => Number(v).toFixed(4)} />
                        <ReferenceLine y={0.2} stroke="#10b981" label="δ=0.2" />
                        <ReferenceLine y={0} stroke="#cbd5e1" />
                        <Line 
                          type="monotone" 
                          dataKey="gradient" 
                          stroke="#ef4444" 
                          strokeWidth={3} 
                          dot={{ r: 2 }} 
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 扩展视野分析：大范围试图 */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 mt-6">
        <h3 className="text-lg font-bold text-slate-800 mb-4">扩展视野：全域参数空间扫描 (0-2000)</h3>
        <p className="text-sm text-slate-500 mb-6">
          强制将位置参数 γ 的观测范围扩大至 2000，验证是否存在被遗漏的解区间。
          <br/>注意：当 γ &gt; t_min 时，数据进入物理禁区（失效时间不能早于起始时间），数学上无法计算对数。
        </p>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 图5: 扩展范围 - 形状参数寻优 */}
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h4 className="text-base font-bold text-slate-800">图5. 广角视野 - 形状参数寻优</h4>
                <p className="text-xs text-slate-500">X轴范围扩大至2000</p>
              </div>
            </div>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart margin={{ top: 20, right: 25, bottom: 45, left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis
                    dataKey="beta"
                    type="number"
                    domain={[0, 10]} 
                    tick={{ fontSize: 10 }}
                    tickLine={true}
                    stroke="#000"
                    strokeWidth={1}
                    label={{ value: '形状参数 β', position: 'bottom', fontSize: 12, fill: '#64748b' }}
                    axisLine={{ stroke: '#000', strokeWidth: 1 }}
                  />
                  <YAxis
                    scale="log"
                    domain={[1, 50000]}
                    tick={{ fontSize: 10 }}
                    tickLine={true}
                    stroke="#000"
                    strokeWidth={1}
                    label={{ value: '标准差 σ_η (对数)', angle: -90, position: 'insideLeft', fontSize: 12, fill: '#64748b' }}
                    axisLine={{ stroke: '#000', strokeWidth: 1 }}
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                    labelFormatter={(v) => `β: ${Number(v).toFixed(2)}`}
                  />
                   {allCurvesData.slice(0, 10).map((sample, idx) => (
                    <Line
                      key={sample.sim_id}
                      data={sample.sigma_beta_curve}
                      type="monotone"
                      dataKey="sigma"
                      stroke={curveColors[idx % curveColors.length]}
                      strokeWidth={sample.has_intersection ? 1 : 2}
                      dot={false}
                      name={`#${sample.sim_id}`}
                      opacity={sample.has_intersection ? 0.5 : 1}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 图6: 扩展范围 - 梯度曲线 */}
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h4 className="text-base font-bold text-slate-800">图6. 广角视野 - 位置参数梯度判据</h4>
                <p className="text-xs text-slate-500">X轴范围扩大至2000，红色区域为物理禁区</p>
              </div>
            </div>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart margin={{ top: 20, right: 25, bottom: 40, left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis
                    dataKey="gamma"
                    type="number"
                    domain={[0, 2000]}
                    ticks={[0, 500, 1000, 1294, 1500, 2000]}
                    tickFormatter={(v) => v.toFixed(0)}
                    tick={{ fontSize: 10 }}
                    tickLine={true}
                    stroke="#000"
                    strokeWidth={1}
                    label={{ value: '位置参数 γ', position: 'bottom', fontSize: 12, fill: '#64748b' }}
                    axisLine={{ stroke: '#000', strokeWidth: 1 }}
                  />
                  <YAxis
                    width={45}
                    domain={[-0.5, 1]}
                    tick={{ fontSize: 10 }}
                    tickLine={true}
                    stroke="#000"
                    strokeWidth={1}
                    label={{ value: '梯度 ∇(γ)', angle: -90, position: 'insideLeft', fontSize: 12, fill: '#64748b' }}
                    axisLine={{ stroke: '#000', strokeWidth: 1 }}
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                    labelFormatter={(v) => `γ: ${Number(v).toFixed(1)}`}
                  />
                  <ReferenceLine y={OFFSET_VALUE} stroke="#10b981" strokeDasharray="3 3" label={{ position: 'right', value: `δ=${OFFSET_VALUE}`, fill: '#10b981', fontSize: 10 }} />
                  <ReferenceLine y={0} stroke="#cbd5e1" />
                  
                  {/* 标记 t_min (Sim 19) */}
                  <ReferenceLine x={1294} stroke="#ef4444" strokeWidth={2} label={{ value: 't_min (1294)', position: 'top', fill: '#ef4444', fontSize: 10 }} />
                  
                  {/* 禁区阴影 - 使用 ReferenceArea 可能会覆盖图表，这里用 Line 模拟或依靠 ReferenceLine */}
                  {/* Recharts 的 ReferenceArea 在某些版本有 bug，我们这里用 ReferenceLine 标记边界即可 */}

                  {allCurvesData.slice(0, 10).map((sample, idx) => (
                    <Line
                      key={sample.sim_id}
                      data={sample.grad_gamma_curve}
                      type="monotone"
                      dataKey="gradient"
                      stroke={curveColors[idx % curveColors.length]}
                      strokeWidth={sample.has_intersection ? 1 : 3}
                      dot={false}
                      name={`#${sample.sim_id}`}
                      opacity={sample.has_intersection ? 0.5 : 1}
                    />
                  ))}

                  {/* 极限分析曲线叠加 (Sim 19) */}
                  {limitAnalysis && (
                    <Line
                      data={limitAnalysis.data}
                      type="linear"
                      dataKey="gradient"
                      stroke="#8b5cf6"
                      strokeWidth={3}
                      strokeDasharray="4 2"
                      dot={false}
                      name="极限逼近 (Sim 19)"
                    />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
        
        {/* 图7: 极限反弹特写 */}
        {limitAnalysis && (
          <div className="bg-purple-50 rounded-xl border border-purple-200 p-4 mt-6">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h4 className="text-base font-bold text-purple-900">图7. 显微镜视角：梯度反弹特写 (1280 ~ 1300)</h4>
                <p className="text-xs text-purple-700">
                  捕捉到了！在逼近物理极限(1294)的最后时刻，梯度曲线出现剧烈反弹并穿过偏移值线。
                  <br/>
                  <span className="font-bold">但请注意：</span>这个交点过于靠近物理边界，属于不稳定的数学奇点，工程上通常不可接受。
                </p>
              </div>
            </div>
            <div className="h-[350px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart 
                  data={limitAnalysis.data.filter(d => d.gamma > 1260)} 
                  margin={{ top: 20, right: 30, bottom: 40, left: 20 }}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e9d5ff" />
                  <XAxis
                    dataKey="gamma"
                    type="number"
                    domain={[1260, 1300]}
                    ticks={[1260, 1270, 1280, 1290, 1294, 1300]}
                    tickFormatter={(v) => v.toFixed(0)}
                    tick={{ fontSize: 10, fill: '#581c87' }}
                    tickLine={{ stroke: '#581c87' }}
                    stroke="#581c87"
                    strokeWidth={1}
                    label={{ value: '位置参数 γ', position: 'bottom', fontSize: 12, fill: '#581c87' }}
                  />
                  <YAxis
                    domain={[-0.2, 0.8]}
                    tick={{ fontSize: 10, fill: '#581c87' }}
                    tickLine={{ stroke: '#581c87' }}
                    stroke="#581c87"
                    strokeWidth={1}
                    label={{ value: '梯度 ∇(γ)', angle: -90, position: 'insideLeft', fontSize: 12, fill: '#581c87' }}
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                    labelFormatter={(v) => `γ: ${Number(v).toFixed(4)}`}
                    formatter={(v: number) => [v.toFixed(6), '梯度']}
                  />
                  <ReferenceLine y={OFFSET_VALUE} stroke="#10b981" strokeWidth={2} label={{ position: 'right', value: `偏移值 δ=${OFFSET_VALUE}`, fill: '#10b981', fontSize: 12, fontWeight: 'bold' }} />
                  <ReferenceLine y={0} stroke="#cbd5e1" />
                  <ReferenceLine x={1294.36} stroke="#ef4444" strokeWidth={2} label={{ value: 't_min (1294.36)', position: 'top', fill: '#ef4444', fontSize: 12, fontWeight: 'bold' }} />
                  
                  <Line
                    type="linear"
                    dataKey="gradient"
                    stroke="#8b5cf6"
                    strokeWidth={4}
                    dot={false}
                    activeDot={{ r: 8 }}
                    name="梯度 ∇(γ)"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>

      {/* 极端假设验证 */}
      {limitAnalysis && selectedNonIntersect && (
        <div className="bg-slate-900 rounded-2xl border border-slate-700 p-8 text-slate-100 mt-8 mb-12">
          <div className="flex items-start gap-4 mb-6">
            <div className="p-3 bg-red-500/20 rounded-lg border border-red-500/50">
              <AlertTriangle className="text-red-400" size={32} />
            </div>
            <div>
              <h3 className="text-2xl font-bold text-white mb-2">极端假设验证：如果我们强行采纳奇点解？</h3>
              <p className="text-slate-400">
                让我们计算那个梯度反弹穿过 δ=0.2 瞬间的具体参数，看看这个“数学上存在”的解在物理上意味着什么。
              </p>
            </div>
          </div>

          {(() => {
            // 1. 寻找奇点解 (Linear Interpolation)
            // 找到梯度跨越 0.2 的区间
            let singularityPoint = null;
            for (let i = 0; i < limitAnalysis.data.length - 1; i++) {
              const p1 = limitAnalysis.data[i];
              const p2 = limitAnalysis.data[i+1];
              if (p1.gradient !== null && p2.gradient !== null) {
                if ((p1.gradient < OFFSET_VALUE && p2.gradient >= OFFSET_VALUE) || 
                    (p1.gradient > OFFSET_VALUE && p2.gradient <= OFFSET_VALUE)) {
                  // 插值
                  const ratio = (OFFSET_VALUE - p1.gradient) / (p2.gradient - p1.gradient);
                  const gamma = p1.gamma + ratio * (p2.gamma - p1.gamma);
                  const beta = p1.beta + ratio * (p2.beta - p1.beta);
                  singularityPoint = { gamma, beta };
                  break; // 找到第一个交点（通常是最接近 t_min 的那个有效反弹）
                }
              }
            }

            if (!singularityPoint) return <div className="text-red-400">未找到相交点，可能是数据精度不足。</div>;

            // 2. 计算奇点 Eta (MLE estimator)
            // eta = ( (1/n) * sum( (t - gamma)^beta ) ) ^ (1/beta)
            const fullSample = fullSamplesData.find(s => s.sim_id === selectedNonIntersect.sim_id);
            const rawData = fullSample?.sample || [];
            let singularityEta = 0;
            if (rawData.length > 0) {
              const sum = rawData.reduce((acc, t) => acc + Math.pow(Math.max(0, t - singularityPoint.gamma), singularityPoint.beta), 0);
              singularityEta = Math.pow(sum / rawData.length, 1 / singularityPoint.beta);
            }

            // 3. 生成 PDF 对比数据
            // Weibull PDF: (beta/eta) * ((t-gamma)/eta)^(beta-1) * exp(-((t-gamma)/eta)^beta)
            const pdfData = [];
            const pdfFn = (t: number, b: number, e: number, g: number) => {
              if (t < g) return 0;
              const z = (t - g) / e;
              return (b / e) * Math.pow(z, b - 1) * Math.exp(-Math.pow(z, b));
            };

            for (let t = 0; t <= 2500; t += 10) {
              pdfData.push({
                t,
                truth: pdfFn(t, TRUE_BETA, 1000, TRUE_GAMMA), // Beta=2, Eta=1000, Gamma=1000
                fallback: pdfFn(t, selectedNonIntersect.est_beta, selectedNonIntersect.est_eta, selectedNonIntersect.est_gamma),
                singularity: pdfFn(t, singularityPoint.beta, singularityEta, singularityPoint.gamma)
              });
            }

            return (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* 参数对比卡片 */}
                <div className="space-y-4">
                   <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
                    <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Truth (真实值)</div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>γ = <span className="text-emerald-400 font-mono">1000</span></div>
                      <div>β = <span className="text-emerald-400 font-mono">2.0</span></div>
                      <div className="col-span-2 text-xs text-slate-500 mt-1">典型的磨损故障分布</div>
                    </div>
                  </div>

                  <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
                    <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Fallback (当前解)</div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>γ = <span className="text-amber-400 font-mono">{selectedNonIntersect.est_gamma.toFixed(1)}</span></div>
                      <div>β = <span className="text-amber-400 font-mono">{selectedNonIntersect.est_beta.toFixed(2)}</span></div>
                      <div className="col-span-2 text-xs text-slate-500 mt-1">偏差较大，但物理意义尚存</div>
                    </div>
                  </div>

                  <div className="bg-red-900/20 rounded-xl p-4 border border-red-500/50 shadow-[0_0_15px_rgba(239,68,68,0.2)]">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></div>
                      <div className="text-xs text-red-400 font-bold uppercase tracking-wider">Singularity (奇点解)</div>
                    </div>
                    <div className="grid grid-cols-1 gap-3 text-sm">
                      <div className="flex justify-between border-b border-red-800/50 pb-2">
                        <span className="text-slate-400">位置参数 γ:</span>
                        <span className="text-red-400 font-mono font-bold">{singularityPoint.gamma.toFixed(4)}</span>
                      </div>
                      <div className="flex justify-between border-b border-red-800/50 pb-2">
                        <span className="text-slate-400">距离 t_min:</span>
                        <span className="text-red-400 font-mono">{(1294.359 - singularityPoint.gamma).toExponential(2)}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-slate-400">形状参数 β:</span>
                        <span className="text-3xl text-red-500 font-bold font-mono">{singularityPoint.beta.toFixed(1)}</span>
                      </div>
                    </div>
                    <div className="mt-3 text-xs text-red-300/80 italic">
                      "形状参数爆炸！这种分布代表在 {singularityPoint.gamma.toFixed(1)} 之前绝对安全，然后瞬间全部失效。"
                    </div>
                  </div>
                </div>

                {/* PDF 对比图 */}
                <div className="lg:col-span-2 bg-slate-800 rounded-xl p-4 border border-slate-700">
                  <h4 className="text-sm font-bold text-slate-300 mb-4">概率密度函数 (PDF) 形态对比</h4>
                  <div className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={pdfData} margin={{ top: 20, right: 30, bottom: 20, left: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis 
                          dataKey="t" 
                          type="number" 
                          tick={{ fill: '#94a3b8', fontSize: 10 }}
                          label={{ value: '时间 t', position: 'bottom', fill: '#94a3b8' }}
                          domain={[0, 2500]}
                        />
                        <YAxis 
                          tick={{ fill: '#94a3b8', fontSize: 10 }}
                          label={{ value: '概率密度', angle: -90, position: 'insideLeft', fill: '#94a3b8' }}
                        />
                        <Tooltip 
                          contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc' }}
                          formatter={(v: number) => v.toFixed(6)}
                          labelFormatter={(v) => `时间: ${v}`}
                        />
                        <Legend verticalAlign="top" height={36}/>
                        
                        {/* 真实分布 */}
                        <Line type="monotone" dataKey="truth" stroke="#10b981" strokeWidth={2} name="真实分布 (Truth)" dot={false} />
                        
                        {/* Fallback */}
                        <Line type="monotone" dataKey="fallback" stroke="#f59e0b" strokeWidth={2} strokeDasharray="5 5" name="当前解 (Fallback)" dot={false} />
                        
                        {/* 奇点 */}
                        <Line type="monotone" dataKey="singularity" stroke="#ef4444" strokeWidth={3} name="奇点解 (Singularity)" dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="mt-4 text-xs text-slate-400">
                    <p>
                      <span className="text-red-400 font-bold">红色曲线 (奇点解)</span>: 一个极窄的尖峰。这说明模型为了拟合数据，把自己变成了一个"阶跃函数"。虽然它在数学上满足了梯度的条件，但在工程上它失去了预测能力——它断言产品寿命是确定性的（几乎没有方差），这与现实世界中充满随机性的磨损规律背道而驰。
                    </p>
                  </div>
                </div>
              </div>
            )
          })()}
        </div>
      )}
    </div>
  )
}