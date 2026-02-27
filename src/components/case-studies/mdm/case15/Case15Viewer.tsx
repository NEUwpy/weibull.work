"use client"

import React, { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Legend
} from 'recharts'
import { BookOpen, ChevronDown, Table2, Info, LineChart as LineChartIcon, CheckCircle, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Case15ViewerProps {
  caseId: string
  onCaseChange?: (caseId: string) => void
}

// 权重结果接口
interface WeightResult {
  n: number
  monte_carlo: {
    E1: number
    E2: number
    E3: number
    G1: number
    G2: number
    G3: number
    J1: number
    J2: number
    J3: number
  }
  code: {
    J1: number
    J2: number
    J3: number
  }
  paper: {
    J1: number | null
    J2: number | null
    J3: number | null
    G1?: number | null
    G2?: number | null
    G3?: number | null
    E1?: number | null
    E2?: number | null
  }
  errors: {
    J1_mc_vs_paper: number | null
    J2_mc_vs_paper: number | null
    J3_mc_vs_paper: number | null
    J1_code_vs_paper: number | null
    J2_code_vs_paper: number | null
    J3_code_vs_paper: number | null
    J3_code_vs_mc: number | null
  }
}

interface SimulationParams {
  n_simulations: number
  sample_sizes: number[]
  gamma_values: number[]
  seed: number
}

interface CaseData {
  simulation_params: SimulationParams
  paper_values: Record<string, Record<number, number>>
  results: Array<{
    gamma: number
    n_simulations: number
    weights: WeightResult[]
  }>
}

// 格式化数字
const fmt = (v: number | null | undefined, decimals: number = 4): string => {
  if (v === null || v === undefined) return '-'
  return v.toFixed(decimals)
}

// 格式化误差百分比
const fmtErr = (v: number | null | undefined): string => {
  if (v === null || v === undefined) return '-'
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`
}

// 获取误差颜色类名
const getErrorColorClass = (v: number | null | undefined): string => {
  if (v === null || v === undefined) return ''
  const absV = Math.abs(v)
  if (absV < 0.5) return 'text-green-600 bg-green-50'
  if (absV < 2) return 'text-yellow-600 bg-yellow-50'
  return 'text-red-600 bg-red-50'
}

// 获取误差图标
const getErrorIcon = (v: number | null | undefined) => {
  if (v === null || v === undefined) return null
  const absV = Math.abs(v)
  if (absV < 0.5) return <CheckCircle size={14} className="text-green-500" />
  if (absV < 2) return <AlertCircle size={14} className="text-yellow-500" />
  return <AlertCircle size={14} className="text-red-500" />
}

export default function Case15Viewer({ caseId, onCaseChange }: Case15ViewerProps) {
  const [data, setData] = useState<CaseData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'J1' | 'J2' | 'J3'>('J3')
  const [showAllN, setShowAllN] = useState(false)

  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true)
        const res = await fetch('/case-studies/mdm/case15/data.json')
        if (!res.ok) throw new Error('数据加载失败')
        const json = await res.json()
        setData(json)
      } catch (err: any) {
        setError(err.message)
      } finally {
        setIsLoading(false)
      }
    }
    loadData()
  }, [])

  // 获取当前 gamma 的数据
  const currentData = useMemo(() => {
    if (!data || !data.results || data.results.length === 0) return null
    return data.results[0] // gamma = 2.0
  }, [data])

  // 准备图表数据
  const chartData = useMemo(() => {
    if (!currentData) return []

    return currentData.weights.map(w => ({
      n: w.n,
      mc: w.monte_carlo[activeTab],
      code: w.code[activeTab],
      paper: w.paper[activeTab],
    }))
  }, [currentData, activeTab])

  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-4 border-teal-200 border-t-teal-600 mb-4"></div>
          <p className="text-slate-600 font-bold">加载案例15数据中...</p>
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700">
        数据加载失败: {error}
      </div>
    )
  }

  const params = data.simulation_params

  return (
    <div className="space-y-6">
      {/* 案例选择下拉框 */}
      {onCaseChange && (
        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-4">
            <BookOpen className="text-purple-600" size={20} />
            <label className="text-sm font-bold text-slate-600 whitespace-nowrap">切换案例：</label>
            <div className="relative flex-1 max-w-md">
              <select
                value={caseId}
                onChange={(e) => onCaseChange(e.target.value)}
                className="w-full appearance-none bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-purple-500 cursor-pointer hover:bg-slate-100 transition-colors"
              >
                <option value="case-1">案例1: 多维度参数影响研究</option>
                <option value="case-2">案例2: 样本量与偏移量影响</option>
                <option value="case-3">案例3: 无交点梯度曲线研究 ★</option>
                <option value="case-4">案例4: 大样本性能验证</option>
                <option value="case-5">案例5: 30组实际样本分析 ★</option>
                <option value="case-6">案例6: 搜索步长对结果的影响 (c2数据)</option>
                <option value="case-7">案例7: 搜索步长对结果的影响 (实际样本) ★</option>
                <option value="case-8">案例8: β搜索方式对比 (β步长0.05) ★</option>
                <option value="case-9">案例9: β步长对估计结果的影响 ★</option>
                <option value="case-10">案例10: 中位秩方法对比研究 ★</option>
                <option value="case-11">案例11: 中位秩方法对比 (多样本量) ★</option>
                <option value="case-12">案例12: MDM vs WMLE 方法对比 ★</option>
                <option value="case-13">案例13: 中位秩方法对比 (多尺度参数) ★</option>
                <option value="case-14">案例14: MDM vs WMLE 方法对比 (多尺度参数) ★</option>
                <option value="case-15">案例15: WMLE 权重 Monte Carlo 验证 ★</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={18} />
            </div>
          </div>
        </div>
      )}

      {/* 标题 */}
      <div className="bg-gradient-to-r from-violet-50 to-purple-50 rounded-2xl p-6 border border-violet-200">
        <h2 className="text-xl font-bold text-slate-800 mb-2">案例15: WMLE 权重 Monte Carlo 验证</h2>
        <p className="text-sm text-slate-600 mb-2">
          Monte Carlo 模拟: {params.n_simulations.toLocaleString()} 次/n | 样本量: n = 1-{params.sample_sizes[params.sample_sizes.length-1]} | 形状参数: γ = {params.gamma_values.join(', ')}
        </p>
        <div className="flex items-center gap-2 text-xs text-violet-600 bg-violet-100 px-3 py-1.5 rounded-lg w-fit">
          <Info size={14} />
          <span>复现 Cousineau (2009) 论文的权重计算方法 | 验证代码实现的准确性</span>
        </div>
      </div>

      {/* 权重说明 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <h3 className="text-lg font-bold text-slate-800 mb-4">权重说明</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-blue-50 p-4 rounded-xl border border-blue-100">
            <h4 className="font-bold text-blue-700 mb-2">J₁ (W1 的中位数)</h4>
            <p className="text-sm text-slate-600">修正尺度参数 η 的估计偏差。仅依赖样本量 n。</p>
            <p className="text-xs text-slate-500 mt-2">公式: E[gamma分布&#123;n, 1/n&#125;] 的中位数</p>
          </div>
          <div className="bg-green-50 p-4 rounded-xl border border-green-100">
            <h4 className="font-bold text-green-700 mb-2">J₂ (W2 的中位数)</h4>
            <p className="text-sm text-slate-600">修正形状参数 β 的估计偏差。仅依赖样本量 n。</p>
            <p className="text-xs text-slate-500 mt-2">论文通过 Monte Carlo 模拟得到</p>
          </div>
          <div className="bg-amber-50 p-4 rounded-xl border border-amber-100">
            <h4 className="font-bold text-amber-700 mb-2">J₃ (W3 的中位数)</h4>
            <p className="text-sm text-slate-600">修正位置参数 γ 的估计偏差。依赖样本量 n 和形状参数 β。</p>
            <p className="text-xs text-slate-500 mt-2">论文通过 Monte Carlo 模拟得到</p>
          </div>
        </div>
      </div>

      {/* 主对比表格 */}
      {currentData && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Table2 className="text-violet-600" size={20} />
              <h3 className="text-lg font-bold text-slate-800">权重值对比表 (γ=2.0)</h3>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowAllN(!showAllN)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                  showAllN ? "bg-violet-100 text-violet-700" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                )}
              >
                {showAllN ? '显示 n≤16' : '显示全部 n'}
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full border-collapse" style={{ fontSize: '13px' }}>
              <thead>
                <tr className="border-b-2 border-slate-300">
                  <th className="py-2 px-2 text-left font-bold text-slate-700" rowSpan={2}>n</th>
                  <th className="py-1 px-1 text-center font-bold text-slate-700 border-l border-slate-300" colSpan={3}>J₁</th>
                  <th className="py-1 px-1 text-center font-bold text-slate-700 border-l border-slate-300" colSpan={3}>J₂</th>
                  <th className="py-1 px-1 text-center font-bold text-slate-700 border-l border-slate-300" colSpan={4}>J₃</th>
                </tr>
                <tr className="border-b border-slate-200 text-xs text-slate-500">
                  <th className="py-1 px-1 text-right border-l border-slate-300">论文</th>
                  <th className="py-1 px-1 text-right">MC模拟</th>
                  <th className="py-1 px-1 text-right">误差%</th>
                  <th className="py-1 px-1 text-right border-l border-slate-300">论文</th>
                  <th className="py-1 px-1 text-right">MC模拟</th>
                  <th className="py-1 px-1 text-right">误差%</th>
                  <th className="py-1 px-1 text-right border-l border-slate-300">论文</th>
                  <th className="py-1 px-1 text-right">MC模拟</th>
                  <th className="py-1 px-1 text-right">代码</th>
                  <th className="py-1 px-1 text-right">误差%</th>
                </tr>
              </thead>
              <tbody>
                {currentData.weights
                  .filter(w => showAllN || w.n <= 16)
                  .map((w) => (
                  <tr key={w.n} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="py-1.5 px-2 font-bold text-slate-700">{w.n}</td>
                    {/* J1 */}
                    <td className="py-1.5 px-1 text-right font-mono border-l border-slate-300">{fmt(w.paper.J1, 3)}</td>
                    <td className="py-1.5 px-1 text-right font-mono">{fmt(w.monte_carlo.J1, 3)}</td>
                    <td className={cn("py-1.5 px-1 text-right font-mono", getErrorColorClass(w.errors.J1_mc_vs_paper))}>
                      {fmtErr(w.errors.J1_mc_vs_paper)}
                    </td>
                    {/* J2 */}
                    <td className="py-1.5 px-1 text-right font-mono border-l border-slate-300">{fmt(w.paper.J2, 3)}</td>
                    <td className="py-1.5 px-1 text-right font-mono">{fmt(w.monte_carlo.J2, 3)}</td>
                    <td className={cn("py-1.5 px-1 text-right font-mono", getErrorColorClass(w.errors.J2_mc_vs_paper))}>
                      {fmtErr(w.errors.J2_mc_vs_paper)}
                    </td>
                    {/* J3 */}
                    <td className="py-1.5 px-1 text-right font-mono border-l border-slate-300">{fmt(w.paper.J3, 3)}</td>
                    <td className="py-1.5 px-1 text-right font-mono">{fmt(w.monte_carlo.J3, 4)}</td>
                    <td className="py-1.5 px-1 text-right font-mono text-blue-600">{fmt(w.code.J3, 4)}</td>
                    <td className={cn("py-1.5 px-1 text-right font-mono", getErrorColorClass(w.errors.J3_mc_vs_paper))}>
                      {fmtErr(w.errors.J3_mc_vs_paper)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-3 flex items-center gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded bg-green-100 border border-green-200"></span>
              误差 &lt; 0.5%
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded bg-yellow-100 border border-yellow-200"></span>
              误差 0.5% ~ 2%
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded bg-red-100 border border-red-200"></span>
              误差 &gt; 2%
            </span>
          </div>
        </div>
      )}

      {/* J3 代码公式 vs Monte Carlo 对比 */}
      {currentData && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <Table2 className="text-blue-600" size={20} />
            <h3 className="text-lg font-bold text-slate-800">J₃ 代码公式 vs Monte Carlo 详细对比</h3>
          </div>
          <p className="text-xs text-slate-500 mb-3">
            当前代码使用近似公式计算 J₃，此处对比公式结果与 Monte Carlo 模拟真值
          </p>

          <div className="overflow-x-auto">
            <table className="w-full border-collapse" style={{ fontSize: '13px' }}>
              <thead>
                <tr className="border-b-2 border-slate-300">
                  <th className="py-2 px-2 text-left font-bold text-slate-700">n</th>
                  <th className="py-2 px-2 text-right font-bold text-slate-700">MC模拟</th>
                  <th className="py-2 px-2 text-right font-bold text-slate-700">代码公式</th>
                  <th className="py-2 px-2 text-right font-bold text-slate-700">代码 vs MC</th>
                  <th className="py-2 px-2 text-right font-bold text-slate-700">论文值</th>
                  <th className="py-2 px-2 text-right font-bold text-slate-700">MC vs 论文</th>
                  <th className="py-2 px-2 text-center font-bold text-slate-700">精度评估</th>
                </tr>
              </thead>
              <tbody>
                {currentData.weights
                  .filter(w => w.n <= 20)
                  .map((w) => {
                    const codeVsMcErr = w.errors.J3_code_vs_mc
                    const mcVsPaperErr = w.errors.J3_mc_vs_paper
                    return (
                      <tr key={w.n} className="border-b border-slate-100 hover:bg-slate-50">
                        <td className="py-1.5 px-2 font-bold text-slate-700">{w.n}</td>
                        <td className="py-1.5 px-1 text-right font-mono">{fmt(w.monte_carlo.J3, 4)}</td>
                        <td className="py-1.5 px-1 text-right font-mono text-blue-600">{fmt(w.code.J3, 4)}</td>
                        <td className={cn("py-1.5 px-1 text-right font-mono", getErrorColorClass(codeVsMcErr))}>
                          {fmtErr(codeVsMcErr)}
                        </td>
                        <td className="py-1.5 px-1 text-right font-mono">{fmt(w.paper.J3, 3)}</td>
                        <td className={cn("py-1.5 px-1 text-right font-mono", getErrorColorClass(mcVsPaperErr))}>
                          {fmtErr(mcVsPaperErr)}
                        </td>
                        <td className="py-1.5 px-1 text-center">
                          <div className="flex items-center justify-center gap-1">
                            {getErrorIcon(codeVsMcErr)}
                            {codeVsMcErr !== null && Math.abs(codeVsMcErr) < 1 ? (
                              <span className="text-green-600 text-xs">公式准确</span>
                            ) : codeVsMcErr !== null && Math.abs(codeVsMcErr) < 3 ? (
                              <span className="text-yellow-600 text-xs">可接受</span>
                            ) : (
                              <span className="text-red-600 text-xs">需优化</span>
                            )}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 权重曲线图 */}
      {currentData && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <LineChartIcon className="text-violet-600" size={20} />
              <h3 className="text-lg font-bold text-slate-800">权重随样本量变化曲线</h3>
            </div>
            {/* Tab 切换 */}
            <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
              {[
                { id: 'J1' as const, label: 'J₁', color: '#3b82f6' },
                { id: 'J2' as const, label: 'J₂', color: '#22c55e' },
                { id: 'J3' as const, label: 'J₃', color: '#f59e0b' },
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "px-4 py-1.5 rounded-md text-sm font-bold transition-all",
                    activeTab === tab.id
                      ? "bg-white shadow-sm"
                      : "text-slate-500 hover:text-slate-700"
                  )}
                  style={activeTab === tab.id ? { color: tab.color } : {}}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* 图例说明 */}
          <div className="flex flex-wrap gap-4 mb-4 text-xs">
            <span className="flex items-center gap-1">
              <span className="w-4 h-0.5 inline-block bg-violet-500"></span>
              <span className="text-slate-600">Monte Carlo 模拟</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-4 h-0.5 inline-block bg-blue-500"></span>
              <span className="text-slate-600">代码公式</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-full bg-slate-400 inline-block"></span>
              <span className="text-slate-600">论文值 (n≤16)</span>
            </span>
          </div>

          <div className="h-[400px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 30, bottom: 30, left: 50 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="n"
                  tick={{ fontSize: 11 }}
                  type="number"
                  domain={[1, 30]}
                  label={{ value: '样本量 n', position: 'bottom', offset: 10, fontSize: 12 }}
                />
                <YAxis
                  tick={{ fontSize: 11 }}
                  label={{ value: activeTab, angle: -90, position: 'insideLeft', fontSize: 12 }}
                />
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '12px' }}
                  formatter={(v: number, name: string) => {
                    const labels: Record<string, string> = { mc: 'Monte Carlo', code: '代码公式', paper: '论文值' }
                    return [v.toFixed(4), labels[name] || name]
                  }}
                  labelFormatter={(l) => `n = ${l}`}
                />
                <Legend />
                {/* Monte Carlo 曲线 */}
                <Line
                  type="monotone"
                  dataKey="mc"
                  stroke="#8b5cf6"
                  strokeWidth={2}
                  dot={false}
                  name="Monte Carlo"
                />
                {/* 代码公式曲线 */}
                <Line
                  type="monotone"
                  dataKey="code"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  strokeDasharray="5 3"
                  dot={false}
                  name="代码公式"
                />
                {/* 论文值散点 */}
                <Line
                  type="monotone"
                  dataKey="paper"
                  stroke="none"
                  fill="#64748b"
                  dot={{ r: 4, fill: '#64748b' }}
                  name="论文值"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <p className="text-center text-xs text-slate-500 mt-3">
            {activeTab === 'J3'
              ? 'J₃ 的代码公式与 Monte Carlo 模拟在小样本时可能存在差异，大样本时趋于一致'
              : `${activeTab} 的代码查表值与 Monte Carlo 模拟高度一致`
            }
          </p>
        </div>
      )}

      {/* 结论 */}
      <div className="bg-slate-50 p-6 rounded-2xl border border-slate-200">
        <h3 className="text-lg font-bold text-slate-800 mb-3">验证结论</h3>
        <div className="space-y-2 text-sm text-slate-600">
          <p>
            <strong>1. J₁ 验证:</strong> Monte Carlo 模拟结果与论文值在小数点后 2-3 位一致，验证了 W1 的采样分布为 Gamma(n, 1/n) 的理论推导。
          </p>
          <p>
            <strong>2. J₂ 验证:</strong> Monte Carlo 模拟结果与论文表格值高度一致，验证了论文的 Monte Carlo 模拟方法可复现。
          </p>
          <p>
            <strong>3. J₃ 验证:</strong> 当前代码使用的近似公式在 n≥7 时误差小于 2%，但对于 n&lt;7 的小样本情况，建议使用 Monte Carlo 模拟的查表值。
          </p>
          <p className="text-xs text-slate-500 mt-3">
            注: 本验证使用 {params.n_simulations.toLocaleString()} 次 Monte Carlo 模拟，与论文设置一致。理论上误差应小于 0.1%。
          </p>
        </div>
      </div>
    </div>
  )
}
