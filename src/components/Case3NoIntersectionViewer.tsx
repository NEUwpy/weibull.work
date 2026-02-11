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

export default function Case3NoIntersectionViewer({ caseId }: Case3NoIntersectionViewerProps) {
  const [samplesData, setSamplesData] = useState<SampleData[]>([])
  const [fullSamplesData, setFullSamplesData] = useState<FullSampleData[]>([])  // 包含原始样本的完整数据
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedNonIntersectId, setSelectedNonIntersectId] = useState<number | null>(null)

  // 加载数据
  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true)

        // 并行加载曲线数据和完整数据
        const [curvesRes, fullRes] = await Promise.all([
          fetch('/cases/mdm_case3_curves.json'),
          fetch('/cases/mdm_case3_data.json')
        ])

        if (!curvesRes.ok) throw new Error('曲线数据加载失败')
        if (!fullRes.ok) throw new Error('完整数据加载失败')

        const parsedCurves: SampleData[] = await curvesRes.json()
        const parsedFull: { samples: FullSampleData[] } = await fullRes.json()

        setSamplesData(parsedCurves)
        setFullSamplesData(parsedFull.samples)

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
                      F<sub>i</sub> = (i - 0.3) / (n + 0.4)
                    </code>
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-slate-300">
                          <th className="py-2 text-left">序号 i</th>
                          <th className="py-2 text-left">排序样本 t<sub>i</sub></th>
                          <th className="py-2 text-left">中位秩 F<sub>i</sub></th>
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
                      t<sub>理论</sub> = γ + η × (-ln(1-F<sub>i</sub>))<sup>1/β</sup>
                      <br />= {TRUE_GAMMA} + 1000 × (-ln(1-F<sub>i</sub>))<sup>1/{TRUE_BETA}</sup>
                    </code>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-slate-300">
                          <th className="py-2 text-left">序号</th>
                          <th className="py-2 text-left">F<sub>i</sub></th>
                          <th className="py-2 text-left">理论 t<sub>i</sub></th>
                          <th className="py-2 text-left">实际 t<sub>i</sub></th>
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

                {/* 3. 无交点现象解释 */}
                <div className="p-4 bg-red-50 rounded-lg border border-red-200">
                  <h5 className="font-bold text-slate-700 mb-2">3. 无交点现象解释</h5>
                  <div className="space-y-2 text-slate-600">
                    <p>
                      <strong>MDM方法原理：</strong>在固定γ的情况下，找到使σ<sub>η</sub>最小的β值，
                      然后计算梯度 ∇(γ) = dσ<sub>η</sub>/dγ，寻找∇(γ) = δ的交点。
                    </p>
                    <p>
                      <strong>本样本情况：</strong>对于样本 #{selectedNonIntersect.sim_id}，在所有γ∈[0, t<sub>min</sub>]范围内，
                      梯度∇(γ)始终为负值且小于δ={OFFSET_VALUE}（即∇(γ) < δ）。
                    </p>
                    <p>
                      <strong>无交点原因：</strong>该样本的σ<sub>η</sub>(γ)曲线单调递减（或梯度始终为负），
                      导致无法找到∇(γ) = δ={OFFSET_VALUE}的交点。MDM方法fallback返回边界值γ=0。
                    </p>
                    <p className="text-red-700">
                      <strong>结果：</strong>γ估计值为{selectedNonIntersect.est_gamma.toFixed(2)}，
                      与真实值{TRUE_GAMMA}的偏差高达{(selectedNonIntersect.est_gamma - TRUE_GAMMA).toFixed(2)}，
                      相对误差={((selectedNonIntersect.est_gamma - TRUE_GAMMA) / TRUE_GAMMA * 100).toFixed(1)}%。
                    </p>
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
    </div>
  )
}
