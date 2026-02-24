"use client"

import React, { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine
} from 'recharts'
import { BookOpen, ChevronDown, Table2, Info, LineChart as LineChartIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

// 参数 Tab 类型
type ParamTab = 'beta' | 'eta' | 'gamma'

interface Case14ViewerProps {
  caseId: string
  onCaseChange?: (caseId: string) => void
}

// 参数统计结构
interface ParamStats {
  mean: number
  median: number
  std: number
  min: number
  max: number
  p005: number  // 0.5%
  p995: number  // 99.5%
  p025: number  // 2.5%
  p975: number  // 97.5%
  q1: number
  q3: number
  bias: number
  mse: number
}

interface MethodStats {
  count: number
  valid_count: number
  solution_rate: number
  beta?: ParamStats
  eta?: ParamStats
  gamma?: ParamStats
}

interface SimulationResult {
  sim_id: number
  method: string
  beta: number | null
  eta: number | null
  gamma: number | null
  status: string
}

interface SampleResult {
  n: number
  mdm_stats: MethodStats
  wmle_stats: MethodStats
  mdm_results: SimulationResult[]
  wmle_results: SimulationResult[]
}

interface EtaResult {
  eta: number
  sample_results: SampleResult[]
}

interface SimulationParams {
  sample_sizes: number[]
  eta_values: number[]
  n_simulations: number
  true_beta: number
  true_gamma: number
  offset: number
  seed: number
}

interface CaseData {
  simulation_params: SimulationParams
  eta_results: EtaResult[]
}

// 核密度估计 (KDE)
function computeKDE(values: number[], bandwidth?: number) {
  const n = values.length
  if (n === 0) return { points: [], bandwidth: 0 }

  const mean = values.reduce((a, b) => a + b, 0) / n
  const std = Math.sqrt(values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / n)
  const iqr = (() => {
    const sorted = [...values].sort((a, b) => a - b)
    const q1 = sorted[Math.floor(n * 0.25)]
    const q3 = sorted[Math.floor(n * 0.75)]
    return q3 - q1
  })()
  const defaultBandwidth = 0.9 * Math.min(std, iqr / 1.34) / Math.pow(n, 0.2)
  const h = bandwidth ?? defaultBandwidth

  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min
  const numPoints = 200

  const points = Array.from({ length: numPoints }, (_, i) => {
    const x = min - range * 0.1 + (i / (numPoints - 1)) * range * 1.2
    let density = 0
    for (const v of values) {
      const u = (x - v) / h
      density += Math.exp(-0.5 * u * u)
    }
    density /= (n * h * Math.sqrt(2 * Math.PI))
    return { x, y: density }
  })

  return { points, bandwidth: h }
}

const colors = {
  beta: '#1e40af',
  eta: '#047857',
  gamma: '#b45309'
}

// 样本量颜色：MDM 蓝色系(随n增大变深)，WMLE 红色系(随n增大变深)
const sampleColors: Record<number, { mdm: string; wmle: string }> = {
  7: { mdm: '#93c5fd', wmle: '#fca5a5' },    // 浅蓝 / 浅红
  9: { mdm: '#60a5fa', wmle: '#f87171' },    // 蓝 / 红
  10: { mdm: '#3b82f6', wmle: '#ef4444' },   // 亮蓝 / 亮红
  12: { mdm: '#2563eb', wmle: '#dc2626' },   // 深蓝 / 深红
  15: { mdm: '#1d4ed8', wmle: '#b91c1c' },   // 更深蓝 / 更深红
  20: { mdm: '#1e40af', wmle: '#991b1b' },   // 最深蓝 / 最深红
}

export default function Case14Viewer({ caseId, onCaseChange }: Case14ViewerProps) {
  const [data, setData] = useState<CaseData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedEta, setSelectedEta] = useState<number>(1000)
  const [activeTab, setActiveTab] = useState<ParamTab>('beta')

  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true)
        const res = await fetch('/case-studies/mdm/case14/data.json')
        if (!res.ok) throw new Error('数据加载失败')
        const json = await res.json()
        setData(json)
        if (json.eta_results?.length > 0) {
          setSelectedEta(json.eta_results[0].eta)
        }
      } catch (err: any) {
        setError(err.message)
      } finally {
        setIsLoading(false)
      }
    }
    loadData()
  }, [])

  // 获取当前选中 η 的数据
  const currentEtaData = useMemo(() => {
    if (!data) return null
    return data.eta_results.find(er => er.eta === selectedEta)
  }, [data, selectedEta])

  // 计算所有样本量的 KDE 数据
  const allKDEData = useMemo(() => {
    if (!currentEtaData) return null

    const result: Record<number, { beta: { mdm: any[]; wmle: any[] }; eta: { mdm: any[]; wmle: any[] }; gamma: { mdm: any[]; wmle: any[] } }> = {}

    for (const sr of currentEtaData.sample_results) {
      const validMDM = sr.mdm_results.filter(r => r.beta !== null && r.status === 'success')
      const validWMLE = sr.wmle_results.filter(r => r.beta !== null && r.status === 'success')

      result[sr.n] = {
        beta: {
          mdm: computeKDE(validMDM.map(r => r.beta!)).points,
          wmle: computeKDE(validWMLE.map(r => r.beta!)).points,
        },
        eta: {
          mdm: computeKDE(validMDM.map(r => r.eta!)).points,
          wmle: computeKDE(validWMLE.map(r => r.eta!)).points,
        },
        gamma: {
          mdm: computeKDE(validMDM.map(r => r.gamma!)).points,
          wmle: computeKDE(validWMLE.map(r => r.gamma!)).points,
        }
      }
    }

    return result
  }, [currentEtaData])

  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-4 border-teal-200 border-t-teal-600 mb-4"></div>
          <p className="text-slate-600 font-bold">加载案例14数据中...</p>
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
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={18} />
            </div>
          </div>
        </div>
      )}

      {/* 标题 */}
      <div className="bg-gradient-to-r from-teal-50 to-cyan-50 rounded-2xl p-6 border border-teal-200">
        <h2 className="text-xl font-bold text-slate-800 mb-2">案例14: MDM vs WMLE 方法对比 (多尺度参数)</h2>
        <p className="text-sm text-slate-600 mb-2">
          蒙特卡洛模拟: η ∈ {'{' + params.eta_values.join(', ') + '}'}, n ∈ {'{' + params.sample_sizes.join(', ') + '}'}, 各{params.n_simulations}次 | 真实参数: β={params.true_beta}, γ={params.true_gamma}
        </p>
        <div className="flex items-center gap-2 text-xs text-teal-600 bg-teal-100 px-3 py-1.5 rounded-lg w-fit">
          <Info size={14} />
          <span>研究尺度参数（分散性）对 MDM vs WMLE 的影响 | MDM偏移量 δ={params.offset}</span>
        </div>
      </div>

      {/* 尺度参数选择器 */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-4">
          <label className="text-sm font-bold text-slate-600 whitespace-nowrap">选择尺度参数：</label>
          <div className="flex gap-2">
            {params.eta_values.map(eta => (
              <button
                key={eta}
                onClick={() => setSelectedEta(eta)}
                className={cn(
                  "px-4 py-2 rounded-xl text-sm font-bold transition-all",
                  selectedEta === eta
                    ? "bg-teal-600 text-white shadow-md"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                )}
              >
                η = {eta}
              </button>
            ))}
          </div>
          <span className="text-xs text-slate-500 ml-4">
            {selectedEta === 200 ? '(分散性小)' : selectedEta === 1000 ? '(基准)' : '(分散性大)'}
          </span>
        </div>
      </div>

      {/* 参数统计汇总表 (Tab 切换) */}
      {currentEtaData && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Table2 className="text-teal-600" size={20} />
              <h3 className="text-lg font-bold text-slate-800">参数估计统计汇总 (η={selectedEta})</h3>
            </div>
            {/* Tab 切换按钮 */}
            <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
              {[
                { id: 'beta' as const, label: 'β', color: colors.beta },
                { id: 'eta' as const, label: 'η', color: colors.eta },
                { id: 'gamma' as const, label: 'γ', color: colors.gamma },
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
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b-2 border-slate-300">
                  <th className="py-2 px-2 text-left font-bold text-slate-700">n</th>
                  <th className="py-2 px-2 text-left font-bold text-slate-700">方法</th>
                  <th className="py-2 px-2 text-right font-bold text-slate-700">有解率</th>
                  <th className="py-2 px-2 text-right font-bold text-slate-700">均值</th>
                  <th className="py-2 px-2 text-right font-bold text-slate-700">中位数</th>
                  <th className="py-2 px-2 text-right font-bold text-slate-700">标准差</th>
                  <th className="py-2 px-2 text-right font-bold text-slate-700">偏差</th>
                  <th className="py-2 px-2 text-right font-bold text-slate-700">MSE</th>
                  <th className="py-2 px-2 text-right font-bold text-slate-700">95% CI</th>
                  <th className="py-2 px-2 text-right font-bold text-slate-700">全范围</th>
                </tr>
              </thead>
              <tbody>
                {currentEtaData.sample_results.map((sr) => (
                  <React.Fragment key={sr.n}>
                    {[
                      { name: 'MDM', stats: sr.mdm_stats, color: 'blue' },
                      { name: 'WMLE', stats: sr.wmle_stats, color: 'red' }
                    ].map(({ name, stats, color }) => {
                      const paramStats = activeTab === 'beta' ? stats.beta :
                                         activeTab === 'eta' ? stats.eta :
                                         stats.gamma
                      const trueValue = activeTab === 'beta' ? params.true_beta :
                                        activeTab === 'eta' ? selectedEta :
                                        params.true_gamma
                      const decimals = activeTab === 'beta' ? 4 : activeTab === 'eta' ? 2 : 2
                      const ciDecimals = activeTab === 'beta' ? 4 : 0

                      return (
                        <tr key={name} className={cn("border-b border-slate-200", color === 'blue' ? 'bg-blue-50' : 'bg-red-50')}>
                          {name === 'MDM' && (
                            <td rowSpan={2} className="py-2 px-2 font-bold text-slate-700 text-center align-middle border-r border-slate-200">
                              {sr.n}
                            </td>
                          )}
                          <td className={cn("py-2 px-2 font-bold", color === 'blue' ? 'text-blue-700' : 'text-red-700')}>{name}</td>
                          <td className="py-2 px-2 text-right font-mono">{(stats.solution_rate * 100).toFixed(1)}%</td>
                          <td className="py-2 px-2 text-right font-mono">{paramStats?.mean.toFixed(decimals)}</td>
                          <td className="py-2 px-2 text-right font-mono">{paramStats?.median.toFixed(decimals)}</td>
                          <td className="py-2 px-2 text-right font-mono">{paramStats?.std.toFixed(decimals)}</td>
                          <td className="py-2 px-2 text-right font-mono text-red-600">{paramStats?.bias.toFixed(decimals)}</td>
                          <td className="py-2 px-2 text-right font-mono">{paramStats?.mse.toFixed(decimals)}</td>
                          <td className="py-2 px-2 text-right font-mono text-xs">
                            [{paramStats?.p025.toFixed(ciDecimals)}, {paramStats?.p975.toFixed(ciDecimals)}]
                          </td>
                          <td className="py-2 px-2 text-right font-mono text-xs">
                            [{paramStats?.min.toFixed(ciDecimals)}, {paramStats?.max.toFixed(ciDecimals)}]
                          </td>
                        </tr>
                      )
                    })}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            真实值 {activeTab === 'beta' ? 'β' : activeTab === 'eta' ? 'η' : 'γ'} = {
              activeTab === 'beta' ? params.true_beta :
              activeTab === 'eta' ? selectedEta :
              params.true_gamma
            } | 偏差 = 估计均值 - 真实值 | 95% CI = [P2.5, P97.5]
          </p>
        </div>
      )}

      {/* 概率密度分布对比 (所有样本量) */}
      {allKDEData && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <LineChartIcon className="text-teal-600" size={20} />
            <h3 className="text-lg font-bold text-slate-800">参数估计值概率密度分布 (η={selectedEta})</h3>
          </div>

          {/* 图例说明 */}
          <div className="flex flex-wrap gap-4 mb-4 text-xs">
            {params.sample_sizes.map(n => (
              <React.Fragment key={n}>
                <span className="flex items-center gap-1">
                  <span className="w-4 h-0.5 inline-block" style={{ backgroundColor: sampleColors[n].mdm }}></span>
                  <span className="text-slate-600">n={n} MDM</span>
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-4 h-0.5 inline-block" style={{ backgroundColor: sampleColors[n].wmle }}></span>
                  <span className="text-slate-600">n={n} WMLE</span>
                </span>
              </React.Fragment>
            ))}
            <span className="flex items-center gap-1 ml-4">
              <span className="w-4 h-0.5 bg-red-500 inline-block" style={{ borderStyle: 'dashed' }}></span>
              <span className="text-slate-600">真实值</span>
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* β 分布曲线 */}
            <div>
              <p className="text-center text-sm font-semibold mb-2" style={{ color: colors.beta }}>β 参数估计分布</p>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart margin={{ top: 10, right: 15, bottom: 30, left: 45 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis dataKey="x" tick={{ fontSize: 10 }} type="number" domain={['auto', 'auto']} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ borderRadius: '4px', border: '1px solid #e5e7eb', fontSize: '11px' }}
                      formatter={(v: number) => v.toFixed(4)}
                      labelFormatter={(l) => `β: ${Number(l).toFixed(3)}`}
                    />
                    <ReferenceLine x={params.true_beta} stroke="#ef4444" strokeDasharray="5 5" strokeWidth={2} />
                    {params.sample_sizes.map(n => (
                      <React.Fragment key={n}>
                        <Line type="monotone" dataKey="y" data={allKDEData[n].beta.mdm} stroke={sampleColors[n].mdm} strokeWidth={2} dot={false} />
                        <Line type="monotone" dataKey="y" data={allKDEData[n].beta.wmle} stroke={sampleColors[n].wmle} strokeWidth={2} dot={false} />
                      </React.Fragment>
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            {/* η 分布曲线 */}
            <div>
              <p className="text-center text-sm font-semibold mb-2" style={{ color: colors.eta }}>η 参数估计分布</p>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart margin={{ top: 10, right: 15, bottom: 30, left: 45 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis dataKey="x" tick={{ fontSize: 10 }} type="number" domain={['auto', 'auto']} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ borderRadius: '4px', border: '1px solid #e5e7eb', fontSize: '11px' }}
                      formatter={(v: number) => v.toFixed(5)}
                      labelFormatter={(l) => `η: ${Number(l).toFixed(1)}`}
                    />
                    <ReferenceLine x={selectedEta} stroke="#ef4444" strokeDasharray="5 5" strokeWidth={2} />
                    {params.sample_sizes.map(n => (
                      <React.Fragment key={n}>
                        <Line type="monotone" dataKey="y" data={allKDEData[n].eta.mdm} stroke={sampleColors[n].mdm} strokeWidth={2} dot={false} />
                        <Line type="monotone" dataKey="y" data={allKDEData[n].eta.wmle} stroke={sampleColors[n].wmle} strokeWidth={2} dot={false} />
                      </React.Fragment>
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            {/* γ 分布曲线 */}
            <div>
              <p className="text-center text-sm font-semibold mb-2" style={{ color: colors.gamma }}>γ 参数估计分布</p>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart margin={{ top: 10, right: 15, bottom: 30, left: 45 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis dataKey="x" tick={{ fontSize: 10 }} type="number" domain={['auto', 'auto']} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ borderRadius: '4px', border: '1px solid #e5e7eb', fontSize: '11px' }}
                      formatter={(v: number) => v.toFixed(5)}
                      labelFormatter={(l) => `γ: ${Number(l).toFixed(1)}`}
                    />
                    <ReferenceLine x={params.true_gamma} stroke="#ef4444" strokeDasharray="5 5" strokeWidth={2} />
                    {params.sample_sizes.map(n => (
                      <React.Fragment key={n}>
                        <Line type="monotone" dataKey="y" data={allKDEData[n].gamma.mdm} stroke={sampleColors[n].mdm} strokeWidth={2} dot={false} />
                        <Line type="monotone" dataKey="y" data={allKDEData[n].gamma.wmle} stroke={sampleColors[n].wmle} strokeWidth={2} dot={false} />
                      </React.Fragment>
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
          <p className="text-center text-xs text-slate-500 mt-3">
            使用高斯核密度估计 (KDE)。蓝色系 = MDM，红色系 = WMLE。
            <span className="text-red-500 font-medium ml-2">红色虚线</span>为真实参数值。
          </p>
        </div>
      )}
    </div>
  )
}
