"use client"

import React, { useState, useEffect, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, ReferenceLine, Cell
} from 'recharts'
import { AlertTriangle, Info, BarChart2, LineChart as LineChartIcon, BookOpen, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useCaseList } from '@/hooks/useCaseList'

interface Case16ViewerProps {
  caseId: string
  onCaseChange?: (caseId: string) => void
}

interface SampleResult {
  n: number
  n_valid: number
  w1: number
  w2: number
  beta: {
    mean: number
    std: number
    min: number
    max: number
    median: number
    estimates: number[]
  }
  gamma: {
    mean: number
    std: number
    estimates: number[]
  }
  eta: {
    mean: number
    std: number
    estimates: number[]
  }
  distribution: {
    bins: number[]
    counts: number[]
  }
}

interface ContourData {
  n: number
  sample_data: number[]
  beta_range: number[]
  gamma_range: number[]
  Z_log: number[][]
}

interface J3CurveData {
  n: number
  beta_values: number[]
  j3_values: number[]
  mle_values: number[]
}

interface CaseData {
  simulation_params: {
    n_simulations: number
    true_beta: number
    true_eta: number
    true_gamma: number
    seed: number
  }
  sample_results: SampleResult[]
  contour_data: ContourData[]
  j3_curve_data: J3CurveData[]
}

export default function Case16Viewer({ caseId, onCaseChange }: Case16ViewerProps) {
  const [data, setData] = useState<CaseData | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedN, setSelectedN] = useState<number>(3)
  const [activeTab, setActiveTab] = useState<'distribution' | 'contour' | 'j3curve'>('distribution')

  // 获取案例列表
  const { cases: caseList } = useCaseList()

  useEffect(() => {
    fetch('/case-studies/mdm/case16/data.json')
      .then(res => res.json())
      .then(jsonData => {
        setData(jsonData)
        setLoading(false)
      })
      .catch(err => {
        console.error('Failed to load case16 data:', err)
        setLoading(false)
      })
  }, [])

  const sampleSizes = useMemo(() => {
    if (!data) return []
    return data.sample_results.map(r => r.n)
  }, [data])

  const currentSample = useMemo(() => {
    if (!data) return null
    return data.sample_results.find(r => r.n === selectedN)
  }, [data, selectedN])

  // 准备直方图数据
  const histogramData = useMemo(() => {
    if (!currentSample) return []
    const { bins, counts } = currentSample.distribution
    const labels = ['<0.9', '0.9-1.1', '1.1-1.4', '1.4-1.6', '1.6-1.9', '1.9-2.1', '2.1-2.4', '2.4-2.6', '>2.6']
    return bins.slice(0, -1).map((bin, i) => ({
      range: labels[i] || `${bin.toFixed(1)}-${bins[i+1].toFixed(1)}`,
      count: counts[i],
      isTarget: bin >= 1.9 && bin < 2.1, // 真值附近的区间
      isAnomaly: bin >= 2.4 && bin < 2.6 // 异常收敛区间
    }))
  }, [currentSample])

  // 准备 J3 曲线数据
  const j3CurveData = useMemo(() => {
    if (!data) return []
    const j3Data = data.j3_curve_data.find(d => d.n === selectedN)
    if (!j3Data) return []
    return j3Data.beta_values.map((beta, i) => ({
      beta,
      j3: j3Data.j3_values[i],
      mle: j3Data.mle_values[i]
    }))
  }, [data, selectedN])

  // 不同样本量的 beta 分布对比
  const distributionComparison = useMemo(() => {
    if (!data) return []
    return data.sample_results.map(sample => {
      const anomalyRate = sample.distribution.counts[7] / sample.n_valid * 100 // 2.4-2.6 区间
      const normalRate = sample.distribution.counts[5] / sample.n_valid * 100 // 1.9-2.1 区间
      return {
        n: sample.n,
        mean: sample.beta.mean,
        std: sample.beta.std,
        anomalyRate,
        normalRate
      }
    })
  }, [data])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">加载中...</div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-500">数据加载失败</div>
      </div>
    )
  }

  const trueBeta = data.simulation_params.true_beta

  return (
    <div className="space-y-6">
      {/* 案例选择下拉框 */}
      {onCaseChange && caseList.length > 0 && (
        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-4">
            <BookOpen className="text-orange-600" size={20} />
            <label className="text-sm font-bold text-slate-600 whitespace-nowrap">切换案例：</label>
            <div className="relative flex-1 max-w-md">
              <select
                value={caseId}
                onChange={(e) => onCaseChange(e.target.value)}
                className="w-full appearance-none bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-orange-500 cursor-pointer hover:bg-slate-100 transition-colors"
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

      {/* 警告信息 */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
          <div>
            <h4 className="font-medium text-amber-800">WMLE 极小样本失效警告</h4>
            <p className="text-sm text-amber-700 mt-1">
              当样本量 n &lt; 5 或 n &lt; 7 时，WMLE 的 β 估计值可能出现异常收敛现象。
              估计值倾向于收敛到 J3 权重表的边界值 (β=2.5)，而非真实的 β 值。
            </p>
          </div>
        </div>
      </div>

      {/* 参数选择 */}
      <div className="bg-white rounded-lg border p-4">
        <div className="flex items-center gap-4">
          <span className="text-sm font-medium text-gray-700">选择样本量 n:</span>
          <div className="flex gap-2">
            {sampleSizes.map(n => (
              <button
                key={n}
                onClick={() => setSelectedN(n)}
                className={cn(
                  "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                  selectedN === n
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                )}
              >
                n = {n}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tab 切换 */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-4">
          {[
            { id: 'distribution', label: 'β 估计分布', icon: BarChart2 },
            { id: 'j3curve', label: 'J3 权重曲线', icon: LineChartIcon },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={cn(
                "flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors",
                activeTab === tab.id
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              )}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* β 估计分布 Tab */}
      {activeTab === 'distribution' && currentSample && (
        <div className="space-y-6">
          {/* 统计摘要 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-lg border p-4">
              <div className="text-xs text-gray-500 uppercase">真值 β</div>
              <div className="text-2xl font-bold text-gray-900">{trueBeta}</div>
            </div>
            <div className="bg-white rounded-lg border p-4">
              <div className="text-xs text-gray-500 uppercase">估计均值</div>
              <div className={cn(
                "text-2xl font-bold",
                Math.abs(currentSample.beta.mean - trueBeta) < 0.1 ? "text-green-600" : "text-red-600"
              )}>
                {currentSample.beta.mean.toFixed(3)}
              </div>
            </div>
            <div className="bg-white rounded-lg border p-4">
              <div className="text-xs text-gray-500 uppercase">标准差</div>
              <div className="text-2xl font-bold text-gray-900">{currentSample.beta.std.toFixed(3)}</div>
            </div>
            <div className="bg-white rounded-lg border p-4">
              <div className="text-xs text-gray-500 uppercase">正常收敛率</div>
              <div className={cn(
                "text-2xl font-bold",
                currentSample.distribution.counts[5] / currentSample.n_valid > 0.7 ? "text-green-600" : "text-red-600"
              )}>
                {(currentSample.distribution.counts[5] / currentSample.n_valid * 100).toFixed(1)}%
              </div>
            </div>
          </div>

          {/* 直方图 */}
          <div className="bg-white rounded-lg border p-4">
            <h3 className="text-sm font-medium text-gray-700 mb-4">
              β 估计值分布 (n={selectedN}, {currentSample.n_valid} 次模拟)
            </h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={histogramData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="range" />
                  <YAxis label={{ value: '频次', angle: -90, position: 'insideLeft' }} />
                  <Tooltip />
                  <Bar dataKey="count" name="频次">
                    {histogramData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={entry.isTarget ? '#22c55e' : entry.isAnomaly ? '#ef4444' : '#3b82f6'}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-center gap-6 mt-4 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-green-500 rounded" />
                <span>真值附近 (1.9-2.1)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-red-500 rounded" />
                <span>异常收敛 (2.4-2.6)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-blue-500 rounded" />
                <span>其他区间</span>
              </div>
            </div>
          </div>

          {/* 不同样本量对比 */}
          <div className="bg-white rounded-lg border p-4">
            <h3 className="text-sm font-medium text-gray-700 mb-4">不同样本量的异常收敛率对比</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={distributionComparison} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="n" label={{ value: '样本量 n', position: 'bottom' }} />
                  <YAxis label={{ value: '百分比 (%)', angle: -90, position: 'insideLeft' }} />
                  <Tooltip />
                  <Bar dataKey="normalRate" name="正常收敛率 (%)" fill="#22c55e" />
                  <Bar dataKey="anomalyRate" name="异常收敛率 (%)" fill="#ef4444" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* J3 权重曲线 Tab */}
      {activeTab === 'j3curve' && (
        <div className="space-y-6">
          <div className="bg-white rounded-lg border p-4">
            <h3 className="text-sm font-medium text-gray-700 mb-4">
              J3 权重随 β 变化的曲线 (n={selectedN})
            </h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={j3CurveData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="beta" label={{ value: 'β (形状参数)', position: 'bottom' }} />
                  <YAxis label={{ value: 'J3 权重', angle: -90, position: 'insideLeft' }} />
                  <Tooltip />
                  <ReferenceLine x={2.0} stroke="#22c55e" strokeDasharray="5 5" label={{ value: '真值 β=2.0', position: 'top' }} />
                  <ReferenceLine x={2.5} stroke="#ef4444" strokeDasharray="5 5" label={{ value: '异常收敛点 β=2.5', position: 'top' }} />
                  <Line type="monotone" dataKey="j3" name="J3 (中位数权重)" stroke="#3b82f6" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="mle" name="MLE 渐近权重" stroke="#9ca3af" strokeWidth={1} strokeDasharray="5 5" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-4 text-sm text-gray-600">
              <p>
                <strong>说明：</strong>J3 权重表只提供了 5 个离散 β 值 (0.5, 1.0, 1.5, 2.0, 2.5)，
                中间值通过线性插值获得。当 β 接近 2.5 时，J3 的变化率可能导致优化器被"吸"向这个边界值。
              </p>
            </div>
          </div>

          {/* J3 表格 */}
          <div className="bg-white rounded-lg border p-4">
            <h3 className="text-sm font-medium text-gray-700 mb-4">
              J3 权重表 (论文 Table 4, n={selectedN})
            </h3>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="px-4 py-2 text-left font-medium">β</th>
                    <th className="px-4 py-2 text-left font-medium">0.5</th>
                    <th className="px-4 py-2 text-left font-medium">1.0</th>
                    <th className="px-4 py-2 text-left font-medium">1.5</th>
                    <th className="px-4 py-2 text-left font-medium">2.0</th>
                    <th className="px-4 py-2 text-left font-medium">2.5</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="px-4 py-2 font-medium">J3</td>
                    <td className="px-4 py-2 text-blue-600">-</td>
                    <td className="px-4 py-2 text-blue-600">-</td>
                    <td className="px-4 py-2 text-blue-600">-</td>
                    <td className="px-4 py-2 text-green-600 font-bold">查表值</td>
                    <td className="px-4 py-2 text-red-600 font-bold">查表值</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="mt-4 text-sm text-gray-600">
              J3 权重在 β=2.0 和 β=2.5 之间线性插值。当优化器在 β=2.0 附近搜索时，
              可能会因为目标函数的形状而被"吸引"到 β=2.5 附近的局部最小值。
            </p>
          </div>
        </div>
      )}

      {/* 结论 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
          <div>
            <h4 className="font-medium text-blue-800">结论</h4>
            <ul className="text-sm text-blue-700 mt-2 space-y-1 list-disc list-inside">
              <li>n=3 时，β 估计值呈现明显的双峰分布（约 44% 在真值附近，55% 收敛到 2.5）</li>
              <li>随着 n 增大，正常收敛率提高：n=5 (51%), n=7 (51%), n=10 (59%)</li>
              <li><strong>WMLE 不适用于 n &lt; 5 或 n &lt; 7 的极小样本</strong></li>
              <li>论文的验证也是从 n=8 开始的，可能作者也意识到了这个问题</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
