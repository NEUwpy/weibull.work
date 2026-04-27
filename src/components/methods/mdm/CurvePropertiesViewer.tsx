/**
 * MSE-δ 曲线性质研究展示组件
 *
 * 展示 MDM 方法中 MSE(δ) 曲线的数学性质研究结果：
 * 1. 曲线概览 — 选择案例查看 MSE(δ) 曲线 + 分量
 * 2. 跨案例汇总 — 所有案例的关键指标表
 * 3. MDM 失败条件 — max(∇σ) 与 β 的关系
 * 4. 搜索策略对比 — 效率 vs 精度
 * 5. 结论与建议
 */
"use client"

import React, { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, ScatterChart, Scatter,
  Legend, Cell,
} from 'recharts'
import { ChevronDown, BarChart3, Search, AlertTriangle, CheckCircle, Lightbulb } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ChartCard } from '@/components/shared/charts'

// === Types ===

interface CurvePoint {
  delta: number
  mse: number | null
  mse_beta: number | null
  mse_eta: number | null
  mse_gamma: number | null
  est_beta: number | null
  est_eta: number | null
  est_gamma: number | null
}

interface CurveSample {
  label: string
  desc: string
  beta: number
  eta: number
  gamma: number
  n: number
  seed: number
  sample: number[]
  curve: CurvePoint[]
  best_delta: number | null
  best_mse: number | null
  failure_delta: number | null
  shape: string
  at_left_boundary: boolean
  at_right_boundary: boolean
  valid_count: number
  total_count: number
  max_gradient: number
}

interface StrategyResult {
  label: string
  full_scan: { delta: number; mse: number; calls: number }
  three_phase: { delta: number; mse: number; calls: number; err_pct: number }
}

interface BetaSensitivity {
  beta: number
  max_gradient: number
  delta_limit: number
}

interface CurveStudyData {
  meta: any
  curve_samples: CurveSample[]
  search_strategy: StrategyResult[]
  beta_sensitivity: BetaSensitivity[]
  conclusions: any
}

// === Constants ===

const COLORS = {
  primary: '#3b82f6',
  mse: '#ef4444',
  mse_beta: '#f59e0b',
  mse_eta: '#10b981',
  mse_gamma: '#8b5cf6',
  best: '#22c55e',
  failure: '#ef4444',
  grid: '#e2e8f0',
}

const SHAPE_LABELS: Record<string, string> = {
  unimodal: '单峰（内部极值）',
  monotone_increasing: '单调递增（左边界最优）',
  monotone_decreasing: '单调递减（右边界最优）',
  non_unimodal: '非单峰（窄谷）',
  all_failed: '全部失败',
}

// === Main Component ===

export default function CurvePropertiesViewer() {
  const [data, setData] = useState<CurveStudyData | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedCase, setSelectedCase] = useState<string>('b2_n7')
  const [showComponents, setShowComponents] = useState(false)

  useEffect(() => {
    fetch('/case-studies/mdm/curve-study/data.json')
      .then(res => res.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(err => { console.error('Failed to load curve study data:', err); setLoading(false) })
  }, [])

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-200 border-t-purple-600 mb-4" />
          <p className="text-slate-600 font-bold">加载曲线性质数据中...</p>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-2xl p-8">
        <p className="text-red-700 font-bold">数据加载失败</p>
      </div>
    )
  }

  const selectedSample = data.curve_samples.find(c => c.label === selectedCase) || data.curve_samples[0]

  return (
    <div className="space-y-6">
      {/* Section 1: Curve Overview */}
      <CurveOverview
        samples={data.curve_samples}
        selected={selectedSample}
        onSelect={setSelectedCase}
        showComponents={showComponents}
        onToggleComponents={() => setShowComponents(!showComponents)}
      />

      {/* Section 2: Cross-case Summary */}
      <CrossCaseSummary samples={data.curve_samples} />

      {/* Section 3: Failure Analysis */}
      <FailureAnalysis
        betaSensitivity={data.beta_sensitivity}
        samples={data.curve_samples}
      />

      {/* Section 4: Search Strategy */}
      <SearchStrategyComparison strategies={data.search_strategy} />

      {/* Section 5: Conclusions */}
      <Conclusions conclusions={data.conclusions} />
    </div>
  )
}

// === Section 1: Curve Overview ===

function CurveOverview({
  samples, selected, onSelect, showComponents, onToggleComponents,
}: {
  samples: CurveSample[]
  selected: CurveSample
  onSelect: (label: string) => void
  showComponents: boolean
  onToggleComponents: () => void
}) {
  const chartData = useMemo(() => {
    return selected.curve
      .filter(p => p.mse !== null)
      .map(p => ({
        delta: p.delta,
        MSE: p.mse,
        'MSE(β)': p.mse_beta,
        'MSE(η)': p.mse_eta,
        'MSE(γ)': p.mse_gamma,
      }))
  }, [selected])

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6">
      <div className="flex items-center gap-2 mb-4">
        <BarChart3 className="text-blue-500" size={20} />
        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
          MSE(δ) 曲线概览
        </h3>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-4 mb-4 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-sm font-bold text-slate-600">案例:</label>
          <div className="relative">
            <select
              value={selected.label}
              onChange={e => onSelect(e.target.value)}
              className="appearance-none bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 pr-8 text-sm font-bold text-slate-700 cursor-pointer hover:bg-slate-100"
            >
              {samples.map(s => (
                <option key={s.label} value={s.label}>{s.desc}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={14} />
          </div>
        </div>

        <button
          onClick={onToggleComponents}
          className={cn(
            "px-3 py-1.5 rounded-lg text-xs font-bold transition-all border",
            showComponents
              ? "bg-blue-50 border-blue-300 text-blue-700"
              : "bg-slate-50 border-slate-200 text-slate-500 hover:bg-slate-100"
          )}
        >
          {showComponents ? '隐藏分量' : '显示分量 (β/η/γ)'}
        </button>
      </div>

      {/* Chart */}
      <ChartCard title={`图 1: ${selected.desc} — MSE(δ) 曲线`}>
        <ResponsiveContainer width="100%" height={380}>
          <LineChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
            <XAxis
              dataKey="delta"
              label={{ value: 'δ (偏移量)', position: 'insideBottom', offset: -5, style: { fontWeight: 'bold', fontSize: 12 } }}
              tick={{ fontSize: 11 }}
            />
            <YAxis
              label={{ value: 'MSE', angle: -90, position: 'insideLeft', style: { fontWeight: 'bold', fontSize: 12 } }}
              tick={{ fontSize: 11 }}
            />
            <Tooltip
              formatter={(value: number, name: string) => [value?.toFixed(4), name]}
              labelFormatter={(v: number) => `δ = ${v}`}
            />
            <Legend verticalAlign="top" height={30} />

            <Line
              type="monotone"
              dataKey="MSE"
              stroke={COLORS.mse}
              strokeWidth={2.5}
              dot={false}
              name="总 MSE"
            />

            {showComponents && (
              <>
                <Line type="monotone" dataKey="MSE(β)" stroke={COLORS.mse_beta} strokeWidth={1.5} dot={false} strokeDasharray="5 3" name="MSE(β)" />
                <Line type="monotone" dataKey="MSE(η)" stroke={COLORS.mse_eta} strokeWidth={1.5} dot={false} strokeDasharray="5 3" name="MSE(η)" />
                <Line type="monotone" dataKey="MSE(γ)" stroke={COLORS.mse_gamma} strokeWidth={1.5} dot={false} strokeDasharray="5 3" name="MSE(γ)" />
              </>
            )}

            {/* Best delta marker */}
            {selected.best_delta && (
              <ReferenceLine
                x={selected.best_delta}
                stroke={COLORS.best}
                strokeWidth={2}
                strokeDasharray="6 3"
                label={{ value: `最优 δ=${selected.best_delta}`, position: 'top', style: { fontSize: 11, fontWeight: 'bold', fill: COLORS.best } }}
              />
            )}

            {/* Failure boundary */}
            {selected.failure_delta && (
              <ReferenceLine
                x={selected.failure_delta}
                stroke={COLORS.failure}
                strokeWidth={2}
                strokeDasharray="4 4"
                label={{ value: `MDM 失败`, position: 'top', style: { fontSize: 11, fontWeight: 'bold', fill: COLORS.failure } }}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* Info cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
        <InfoCard label="最优 δ" value={selected.best_delta?.toFixed(4) ?? 'N/A'} color="text-green-600" />
        <InfoCard label="最小 MSE" value={selected.best_mse?.toFixed(6) ?? 'N/A'} color="text-green-600" />
        <InfoCard label="曲线形状" value={SHAPE_LABELS[selected.shape] || selected.shape} color="text-blue-600" />
        <InfoCard
          label="MDM 失败 δ"
          value={selected.failure_delta?.toFixed(3) ?? '无失败'}
          color={selected.failure_delta ? 'text-red-600' : 'text-slate-500'}
        />
      </div>
    </div>
  )
}

// === Section 2: Cross-case Summary ===

function CrossCaseSummary({ samples }: { samples: CurveSample[] }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6">
      <div className="flex items-center gap-2 mb-4">
        <BarChart3 className="text-emerald-500" size={20} />
        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
          跨案例汇总
        </h3>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-slate-50">
              <th className="px-3 py-2.5 text-center font-bold text-slate-700 border border-slate-200">案例</th>
              <th className="px-3 py-2.5 text-center font-bold text-slate-700 border border-slate-200">β</th>
              <th className="px-3 py-2.5 text-center font-bold text-slate-700 border border-slate-200">n</th>
              <th className="px-3 py-2.5 text-center font-bold text-slate-700 border border-slate-200">最优 δ</th>
              <th className="px-3 py-2.5 text-center font-bold text-slate-700 border border-slate-200">最小 MSE</th>
              <th className="px-3 py-2.5 text-center font-bold text-slate-700 border border-slate-200">曲线形状</th>
              <th className="px-3 py-2.5 text-center font-bold text-slate-700 border border-slate-200">失败 δ</th>
              <th className="px-3 py-2.5 text-center font-bold text-slate-700 border border-slate-200">有效率</th>
              <th className="px-3 py-2.5 text-center font-bold text-slate-700 border border-slate-200">max(∇σ)</th>
            </tr>
          </thead>
          <tbody>
            {samples.map((s, i) => (
              <tr key={s.label} className={i % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                <td className="px-3 py-2 text-center font-mono text-slate-700 border border-slate-200 font-bold">{s.desc}</td>
                <td className="px-3 py-2 text-center font-mono border border-slate-200">{s.beta}</td>
                <td className="px-3 py-2 text-center font-mono border border-slate-200">{s.n}</td>
                <td className="px-3 py-2 text-center font-mono border border-slate-200 text-green-700 font-bold">{s.best_delta?.toFixed(4)}</td>
                <td className="px-3 py-2 text-center font-mono border border-slate-200">{s.best_mse?.toFixed(4)}</td>
                <td className="px-3 py-2 text-center border border-slate-200">
                  <ShapeBadge shape={s.shape} />
                </td>
                <td className={cn("px-3 py-2 text-center font-mono border border-slate-200",
                  s.failure_delta ? 'text-red-600 font-bold' : 'text-slate-400')}>
                  {s.failure_delta?.toFixed(3) ?? '—'}
                </td>
                <td className="px-3 py-2 text-center font-mono border border-slate-200">{s.valid_count}/{s.total_count}</td>
                <td className="px-3 py-2 text-center font-mono border border-slate-200">{s.max_gradient.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// === Section 3: Failure Analysis ===

function FailureAnalysis({
  betaSensitivity, samples,
}: {
  betaSensitivity: BetaSensitivity[]
  samples: CurveSample[]
}) {
  const scatterData = betaSensitivity.map(b => ({
    beta: b.beta,
    max_gradient: b.max_gradient,
  }))

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6">
      <div className="flex items-center gap-2 mb-4">
        <AlertTriangle className="text-amber-500" size={20} />
        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
          MDM 失败条件分析
        </h3>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chart */}
        <ChartCard title="图 2: max(∇σ_min) 与 β 的关系">
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
              <XAxis
                dataKey="beta"
                name="β"
                label={{ value: 'β (形状参数)', position: 'insideBottom', offset: -5, style: { fontWeight: 'bold', fontSize: 12 } }}
                tick={{ fontSize: 11 }}
              />
              <YAxis
                dataKey="max_gradient"
                name="max(∇σ)"
                label={{ value: 'max(∇σ_min)', angle: -90, position: 'insideLeft', style: { fontWeight: 'bold', fontSize: 12 } }}
                tick={{ fontSize: 11 }}
              />
              <Tooltip
                formatter={(value: number, name: string) => [value.toFixed(4), name]}
                labelFormatter={(v: number) => `β = ${v}`}
              />
              <Scatter data={scatterData} fill={COLORS.primary}>
                {scatterData.map((_, i) => (
                  <Cell key={i} fill={COLORS.primary} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Explanation */}
        <div className="space-y-4">
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
            <h4 className="text-sm font-bold text-amber-800 mb-2">失败条件</h4>
            <p className="text-sm text-amber-700 leading-relaxed">
              MDM 在 <strong>δ &gt; max(∇σ_min)</strong> 时必然失败。梯度曲线的最大值是数据的固有属性，
              增大 <code className="bg-amber-100 px-1 rounded">gamma_steps</code> 无法改变这一上限。
            </p>
          </div>

          <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
            <h4 className="text-sm font-bold text-slate-800 mb-2">关键发现</h4>
            <ul className="text-sm text-slate-600 space-y-1.5">
              <li>• max(∇σ) 随 β 非单调变化</li>
              <li>• β=3.0 时 max(∇σ) 最低（~0.32），δ 搜索范围最窄</li>
              <li>• β=0.5 时 max(∇σ) 极高（~27.6），几乎不受限</li>
              <li>• 不同随机种子的 max(∇σ) 不同（样本依赖）</li>
            </ul>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
            <h4 className="text-sm font-bold text-blue-800 mb-2">b2_n20 实例</h4>
            <p className="text-sm text-blue-700">
              max(∇σ) = 0.5153。当 δ=0.52 时梯度曲线永远达不到该值，
              找不到交点，MDM 返回 <code className="bg-blue-100 px-1 rounded">no_intersection</code>。
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// === Section 4: Search Strategy ===

function SearchStrategyComparison({ strategies }: { strategies: StrategyResult[] }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6">
      <div className="flex items-center gap-2 mb-4">
        <Search className="text-indigo-500" size={20} />
        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
          搜索策略对比
        </h3>
      </div>

      <div className="overflow-x-auto mb-4">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-slate-50">
              <th className="px-3 py-2.5 text-center font-bold text-slate-700 border border-slate-200">案例</th>
              <th className="px-3 py-2.5 text-center font-bold text-slate-700 border border-slate-200" colSpan={3}>全量细扫 (step=0.001)</th>
              <th className="px-3 py-2.5 text-center font-bold text-slate-700 border border-slate-200" colSpan={4}>三阶段搜索</th>
            </tr>
            <tr className="bg-slate-100">
              <th className="px-3 py-2 text-center font-bold text-slate-600 border border-slate-200"></th>
              <th className="px-3 py-2 text-center font-bold text-slate-600 border border-slate-200">最优 δ</th>
              <th className="px-3 py-2 text-center font-bold text-slate-600 border border-slate-200">MSE</th>
              <th className="px-3 py-2 text-center font-bold text-slate-600 border border-slate-200">调用次数</th>
              <th className="px-3 py-2 text-center font-bold text-slate-600 border border-slate-200">最优 δ</th>
              <th className="px-3 py-2 text-center font-bold text-slate-600 border border-slate-200">MSE</th>
              <th className="px-3 py-2 text-center font-bold text-slate-600 border border-slate-200">调用次数</th>
              <th className="px-3 py-2 text-center font-bold text-slate-600 border border-slate-200">误差</th>
            </tr>
          </thead>
          <tbody>
            {strategies.map((s, i) => (
              <tr key={s.label} className={i % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                <td className="px-3 py-2 text-center font-mono font-bold text-slate-700 border border-slate-200">{s.label}</td>
                <td className="px-3 py-2 text-center font-mono border border-slate-200">{s.full_scan.delta.toFixed(4)}</td>
                <td className="px-3 py-2 text-center font-mono border border-slate-200">{s.full_scan.mse.toFixed(4)}</td>
                <td className="px-3 py-2 text-center font-mono border border-slate-200 text-slate-400">{s.full_scan.calls}</td>
                <td className="px-3 py-2 text-center font-mono border border-slate-200 text-green-700 font-bold">{s.three_phase.delta.toFixed(4)}</td>
                <td className="px-3 py-2 text-center font-mono border border-slate-200">{s.three_phase.mse.toFixed(4)}</td>
                <td className="px-3 py-2 text-center font-mono border border-slate-200 text-green-700 font-bold">{s.three_phase.calls}</td>
                <td className="px-3 py-2 text-center font-mono border border-slate-200">
                  <span className={s.three_phase.err_pct === 0 ? 'text-green-600 font-bold' : 'text-amber-600'}>
                    {s.three_phase.err_pct.toFixed(1)}%
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-green-50 border border-green-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="text-green-600" size={16} />
            <h4 className="text-sm font-bold text-green-800">三阶段搜索</h4>
          </div>
          <p className="text-xs text-green-700">72 次调用，0% 误差，28x 加速</p>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="text-red-600" size={16} />
            <h4 className="text-sm font-bold text-red-800">Scipy Brent</h4>
          </div>
          <p className="text-xs text-red-700">b2_n20 完全失败（被 MDM 失败的 penalty 误导）</p>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Lightbulb className="text-blue-600" size={16} />
            <h4 className="text-sm font-bold text-blue-800">策略参数</h4>
          </div>
          <p className="text-xs text-blue-700">粗 0.05 → 中 0.01 → 细 0.001，范围 [0.001, 2.0]</p>
        </div>
      </div>
    </div>
  )
}

// === Section 5: Conclusions ===

function Conclusions({ conclusions }: { conclusions: any }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6">
      <div className="flex items-center gap-2 mb-4">
        <Lightbulb className="text-yellow-500" size={20} />
        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
          结论与建议
        </h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
            <h4 className="text-sm font-bold text-slate-800 mb-3">曲线形状分类</h4>
            <div className="space-y-2">
              {conclusions.curve_shapes.map((cs: any) => (
                <div key={cs.shape} className="flex items-start gap-2">
                  <ShapeBadge shape={cs.shape} />
                  <p className="text-xs text-slate-600 leading-relaxed">{cs.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-green-50 rounded-xl p-4 border border-green-200">
            <h4 className="text-sm font-bold text-green-800 mb-2">推荐搜索策略</h4>
            <div className="text-xs text-green-700 space-y-1">
              <p><strong>策略：</strong>三阶段搜索</p>
              <p><strong>范围：</strong>[0.001, 2.0]</p>
              <p><strong>步骤：</strong>粗(0.05) → 中(0.01) → 细(0.001)</p>
              <p><strong>效率：</strong>~72 次 MDM 调用/样本</p>
              <p><strong>精度：</strong>0% 误差（vs 全量扫描）</p>
            </div>
          </div>

          <div className="bg-amber-50 rounded-xl p-4 border border-amber-200">
            <h4 className="text-sm font-bold text-amber-800 mb-2">边界样本处理</h4>
            <p className="text-xs text-amber-700 leading-relaxed">
              {conclusions.boundary_samples}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// === Helpers ===

function InfoCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
      <div className="text-xs font-bold text-slate-400 mb-1">{label}</div>
      <div className={cn("text-sm font-black", color)}>{value}</div>
    </div>
  )
}

function ShapeBadge({ shape }: { shape: string }) {
  const colorMap: Record<string, string> = {
    unimodal: 'bg-blue-100 text-blue-700 border-blue-200',
    monotone_increasing: 'bg-amber-100 text-amber-700 border-amber-200',
    monotone_decreasing: 'bg-purple-100 text-purple-700 border-purple-200',
    non_unimodal: 'bg-red-100 text-red-700 border-red-200',
    all_failed: 'bg-slate-100 text-slate-500 border-slate-200',
  }
  const cls = colorMap[shape] || colorMap.all_failed
  return (
    <span className={cn("inline-block px-2 py-0.5 rounded text-xs font-bold border whitespace-nowrap", cls)}>
      {SHAPE_LABELS[shape] || shape}
    </span>
  )
}
