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
  ComposedChart
} from 'recharts'
import { AlertTriangle, CheckCircle, ChevronDown, BookOpen } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useCaseList } from '@/hooks/useCaseList'

// 导入通用图表组件
import { SigmaBetaChart, GradientGammaChart } from '../../charts'

// 开关：使用新组件（true）或旧代码（false）
const USE_NEW_CHART_COMPONENTS = true

interface Case3NoIntersectionViewerProps {
  caseId: string
  onCaseChange?: (caseId: string) => void  // 案例切换回调
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

export default function Case3NoIntersectionViewer({ caseId, onCaseChange }: Case3NoIntersectionViewerProps) {
  const [samplesData, setSamplesData] = useState<SampleData[]>([])
  const [fullSamplesData, setFullSamplesData] = useState<FullSampleData[]>([])  // 包含原始样本的完整数据
  const [limitAnalysis, setLimitAnalysis] = useState<LimitAnalysisData | null>(null)
  const [activeLimitTab, setActiveLimitTab] = useState<'global' | 'micro'>('global')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedNonIntersectId, setSelectedNonIntersectId] = useState<number | null>(null)

  // 获取案例列表 - 必须在所有条件返回之前调用
  const { cases: caseList } = useCaseList()

  // 加载数据 - 使用新路径
  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true)

        // 并行加载曲线数据、完整数据和极限分析数据
        const [curvesRes, fullRes, limitRes] = await Promise.all([
          fetch('/case-studies/mdm/case3/curves.json'),
          fetch('/case-studies/mdm/case3/full_data.json'),
          fetch('/case-studies/mdm/case3/limit_analysis.json')
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
      {/* 案例选择下拉框 */}
      {onCaseChange && caseList.length > 0 && (
        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-4">
            <BookOpen className="text-purple-600" size={20} />
            <label className="text-sm font-bold text-slate-600 whitespace-nowrap">切换案例：</label>
            <div className="relative flex-1 max-w-md">
              <select
                value={caseId}
                onChange={(e) => onCaseChange(e.target.value)}
                className="w-full appearance-none bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent cursor-pointer hover:bg-slate-100 transition-colors"
              >
                {caseList.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={18} />
            </div>
          </div>
        </div>
      )}

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
          USE_NEW_CHART_COMPONENTS ? (
            <SigmaBetaChart
              curves={[{
                id: selectedNonIntersect.sim_id,
                data: selectedNonIntersect.sigma_beta_curve,
                color: '#ef4444',
                strokeWidth: 3,
                name: `样本 #${selectedNonIntersect.sim_id}`
              }]}
              interactive={false}
              overlayMode={false}
              height={300}
              domain={{ x: [0.5, 6], y: [0, 1400] }}
              referenceLines={[
                { value: TRUE_BETA, label: '真实β', color: '#94a3b8' },
                { value: selectedNonIntersect.est_beta, label: '估计β', color: '#ef4444' }
              ]}
              title="图1. 无交点样本 - 形状参数寻优"
              subtitle={`样本 #${selectedNonIntersect.sim_id} 的 σ_η 关于 β 变化`}
            />
          ) : (
            /* 旧代码模式（保留以便对比） */
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
          )
        )}

        {/* 图2: 单条无交点 - 梯度曲线 */}
        {selectedNonIntersect && (
          USE_NEW_CHART_COMPONENTS ? (
            <GradientGammaChart
              curves={[{
                id: selectedNonIntersect.sim_id,
                data: selectedNonIntersect.grad_gamma_curve,
                color: '#ef4444',
                strokeWidth: 2,
                name: `样本 #${selectedNonIntersect.sim_id}`
              }]}
              singleCurve={selectedNonIntersect.grad_gamma_curve}
              interactive={false}
              overlayMode={false}
              height={300}
              offsetReference={OFFSET_VALUE}
              gammaReferenceLines={[
                { gamma: selectedNonIntersect.est_gamma, label: '估计γ', color: '#ef4444' }
              ]}
              title="图2. 无交点样本 - 位置参数梯度判据"
              subtitle={`样本 #${selectedNonIntersect.sim_id} 的 ∇(γ) 与偏移值δ`}
            />
          ) : (
            /* 旧代码模式（保留以便对比） */
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
          )
        )}

        {/* 图3: 10条曲线簇 - σ(β)曲线 */}
        {USE_NEW_CHART_COMPONENTS ? (
          <SigmaBetaChart
            curves={allCurvesData.slice(0, 10).map((sample, idx) => ({
              id: sample.sim_id,
              data: sample.sigma_beta_curve,
              color: curveColors[idx % curveColors.length],
              strokeWidth: sample.has_intersection ? 1.5 : 3,
              name: `#${sample.sim_id}`,
              opacity: sample.has_intersection ? 0.7 : 1
            }))}
            interactive={false}
            overlayMode={true}
            height={300}
            yScale="log"
            domain={{ x: [0.5, 6], y: [1, 2000] }}
            referenceLines={[
              { value: TRUE_BETA, label: '真实β', color: '#94a3b8' }
            ]}
            title="图3. 曲线簇 - 形状参数寻优"
            subtitle="10条样本的 σ_η 关于 β 变化（对数坐标，红色为无交点）"
          />
        ) : (
          /* 旧代码模式（保留以便对比） */
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h4 className="text-base font-bold text-slate-800">图3. 曲线簇 - 形状参数寻优</h4>
                <p className="text-xs text-slate-500">10条样本的 σ_η 关于 β 变化（对数坐标，红色为无交点）</p>
              </div>
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
        )}

        {/* 图4: 10条曲线簇 - 梯度曲线 */}
        {USE_NEW_CHART_COMPONENTS ? (
          <GradientGammaChart
            curves={allCurvesData.slice(0, 10).map((sample, idx) => ({
              id: sample.sim_id,
              data: sample.grad_gamma_curve,
              color: curveColors[idx % curveColors.length],
              strokeWidth: sample.has_intersection ? 1.5 : 3,
              name: `#${sample.sim_id}`,
              opacity: sample.has_intersection ? 0.7 : 1
            }))}
            interactive={false}
            overlayMode={true}
            height={300}
            offsetReference={OFFSET_VALUE}
            title="图4. 曲线簇 - 位置参数梯度判据"
            subtitle="10条样本的 ∇(γ) 与偏移值δ（红色为无交点）"
          />
        ) : (
          /* 旧代码模式（保留以便对比） */
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h4 className="text-base font-bold text-slate-800">图4. 曲线簇 - 位置参数梯度判据</h4>
                <p className="text-xs text-slate-500">10条样本的 ∇(γ) 与偏移值δ（红色为无交点）</p>
              </div>
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
        )}

        {/* 图5: 扩展搜索范围 - 10条样本 σ(β)曲线簇 */}
        {limitAnalysis && (
          <div className="space-y-3">
            {USE_NEW_CHART_COMPONENTS ? (
              <SigmaBetaChart
                curves={allCurvesData.slice(0, 10).map((sample, idx) => {
                  if (!sample.has_intersection) {
                    const extData = limitAnalysis.data
                      .filter(d => d.sigma !== null)
                      .map(d => ({ beta: d.beta, sigma: d.sigma }))
                      .sort((a, b) => a.beta - b.beta)
                    return {
                      id: `ext-${sample.sim_id}`,
                      data: extData,
                      color: '#ef4444',
                      strokeWidth: 3,
                      name: `#${sample.sim_id} (新γ)`,
                      opacity: 1
                    }
                  }
                  return {
                    id: `ext-${sample.sim_id}`,
                    data: sample.sigma_beta_curve,
                    color: curveColors[idx % curveColors.length],
                    strokeWidth: 1.5,
                    name: `#${sample.sim_id}`,
                    opacity: 0.7
                  }
                })}
                interactive={false}
                overlayMode={true}
                height={300}
                yScale="log"
                domain={{ x: [0.5, 6], y: [1, 2000] }}
                referenceLines={[
                  { value: TRUE_BETA, label: '真实β', color: '#94a3b8' },
                  ...(limitAnalysis.data.find(d => d.gradient >= OFFSET_VALUE)
                    ? [{ value: limitAnalysis.data.find(d => d.gradient >= OFFSET_VALUE)!.beta, label: `β*=${limitAnalysis.data.find(d => d.gradient >= OFFSET_VALUE)!.beta.toFixed(1)}`, color: '#ef4444', strokeDasharray: '5 2' }]
                    : [])
                ]}
                title="图5. 扩展搜索范围 - 形状参数寻优"
                subtitle="10条样本的 σ_η 关于 β 变化（γ搜索范围扩展至 99.9999% t_min）"
              />
            ) : (
              /* 旧代码模式（保留以便对比） */
              <div className="bg-white rounded-2xl border border-slate-200 p-6">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h4 className="text-base font-bold text-slate-800">图5. 扩展搜索范围 - 形状参数寻优</h4>
                    <p className="text-xs text-slate-500">10条样本的 σ_η 关于 β 变化（γ搜索范围扩展至 99.9999% t_min）</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 bg-blue-500 rounded"></div>
                    <span className="text-xs text-blue-600 font-bold">扩展搜索</span>
                  </div>
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
                        tickFormatter={(v) => v.toFixed(3)}
                        tick={{ fontSize: 10 }}
                        tickLine={true}
                        stroke="#000"
                        strokeWidth={1}
                        label={{ value: '标准差 σ_η (对数)', angle: -90, position: 'insideLeft', fontSize: 12, fill: '#64748b' }}
                        axisLine={{ stroke: '#000', strokeWidth: 1 }}
                      />
                      <Tooltip
                        contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                        labelFormatter={(v) => `β: ${Number(v).toFixed(3)}`}
                        formatter={(v: number, name: string) => [v.toFixed(3), name]}
                      />
                      <ReferenceLine x={TRUE_BETA} stroke="#94a3b8" strokeDasharray="3 3" label={{ value: "真实β", fill: '#94a3b8', fontSize: 10 }} />
                      {/* 从图6交点找到的β*处画参考线 */}
                      {(() => {
                        const intersectionPoint = limitAnalysis.data.find(d => d.gradient >= OFFSET_VALUE)
                        if (!intersectionPoint) return null
                        return (
                          <ReferenceLine
                            x={intersectionPoint.beta}
                            stroke="#ef4444"
                            strokeDasharray="5 2"
                            label={{ value: `β*=${intersectionPoint.beta.toFixed(1)}`, fill: '#ef4444', fontSize: 10 }}
                          />
                        )
                      })()}
                      {allCurvesData.slice(0, 10).map((sample, idx) => {
                        // 原无交点样本：使用limitAnalysis.data绘制
                        if (!sample.has_intersection) {
                          const extData = limitAnalysis.data
                            .filter(d => d.sigma !== null)
                            .map(d => ({ beta: d.beta, sigma: d.sigma }))
                            .sort((a, b) => a.beta - b.beta)
                          return (
                            <Line
                              key={`ext-${sample.sim_id}`}
                              data={extData}
                              type="monotone"
                              dataKey="sigma"
                              stroke="#ef4444"
                              strokeWidth={3}
                              dot={false}
                              name={`#${sample.sim_id} (新γ)`}
                              opacity={1}
                            />
                          )
                        }
                        return (
                          <Line
                            key={`ext-${sample.sim_id}`}
                            data={sample.sigma_beta_curve}
                            type="monotone"
                            dataKey="sigma"
                            stroke={curveColors[idx % curveColors.length]}
                            strokeWidth={1.5}
                            dot={false}
                            name={`#${sample.sim_id}`}
                            opacity={0.7}
                          />
                        )
                      })}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
            {/* 分析说明（统一显示） */}
            <div className="text-xs text-blue-600 bg-blue-50 p-2 rounded border border-blue-200">
              <strong>重要发现：</strong>扩展搜索后，原"无交点"样本的σ_η(β)曲线同样存在最小值。这表明β<sup>*</sup>(γ)在扩展范围内始终存在，"无交点"问题只出现在γ层面的梯度判据上。
            </div>
          </div>
        )}

        {/* 图6: 扩展搜索范围 - 10条样本梯度曲线簇 */}
        {limitAnalysis && (
          <div className="space-y-3">
            {USE_NEW_CHART_COMPONENTS ? (
              <GradientGammaChart
                curves={allCurvesData.slice(0, 10).map((sample, idx) => ({
                  id: `ext-grad-${sample.sim_id}`,
                  data: sample.grad_gamma_curve,
                  color: curveColors[idx % curveColors.length],
                  strokeWidth: 2,
                  name: `#${sample.sim_id}`,
                  opacity: 0.8
                }))}
                interactive={false}
                overlayMode={true}
                height={300}
                offsetReference={OFFSET_VALUE}
                domain={{ x: [0, limitAnalysis.t_min * 1.0], y: [-0.5, 1] }}
                gammaReferenceLines={[
                  { gamma: limitAnalysis.t_min * 0.99, label: '原99%边界', color: '#f59e0b', position: 'top' as const },
                  { gamma: limitAnalysis.t_min, label: 't_min (极限)', color: '#ef4444', position: 'top' as const }
                ]}
                title="图6. 扩展搜索范围 - 位置参数梯度判据"
                subtitle="10条样本的 ∇(γ) 与 δ 比较（γ搜索范围扩展至 99.9999% t_min）"
              />
            ) : (
            /* 旧代码模式（保留以便对比） */
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h4 className="text-base font-bold text-slate-800">图6. 扩展搜索范围 - 位置参数梯度判据</h4>
                  <p className="text-xs text-slate-500">10条样本的 ∇(γ) 与 δ 比较（γ搜索范围扩展至 99.9999% t_min）</p>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-purple-500 rounded"></div>
                  <span className="text-xs text-purple-600 font-bold">找到交点!</span>
                </div>
              </div>
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart margin={{ top: 20, right: 25, bottom: 40, left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis
                      dataKey="gamma"
                      type="number"
                      domain={[0, limitAnalysis.t_min * 1.0]}
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
                      tickFormatter={(v) => v.toFixed(3)}
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
                    <ReferenceLine x={limitAnalysis.t_min * 0.99} stroke="#f59e0b" strokeDasharray="3 3" label={{ value: "原99%边界", position: 'top', fill: '#f59e0b', fontSize: 9 }} />
                    <ReferenceLine x={limitAnalysis.t_min} stroke="#ef4444" strokeWidth={2} label={{ value: 't_min (极限)', position: 'top', fill: '#ef4444', fontSize: 10 }} />
                    {allCurvesData.slice(0, 10).map((sample, idx) => (
                      <Line
                        key={`ext-grad-${sample.sim_id}`}
                        data={sample.grad_gamma_curve}
                        type="monotone"
                        dataKey="gradient"
                        stroke={curveColors[idx % curveColors.length]}
                        strokeWidth={2}
                        dot={false}
                        name={`#${sample.sim_id}`}
                        opacity={0.8}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-3 text-xs text-purple-600 bg-purple-50 p-2 rounded border border-purple-200">
                <strong>关键发现：</strong>扩展搜索后，红色无交点样本的梯度曲线在γ≈{limitAnalysis.data.find(d => d.gradient >= OFFSET_VALUE)?.gamma.toFixed(0)}处成功穿过δ={OFFSET_VALUE}线！这证明"无交点"是搜索范围不足(只到99% t_min)导致的伪象。
              </div>
            </div>
          )}
          </div>
        )}

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
