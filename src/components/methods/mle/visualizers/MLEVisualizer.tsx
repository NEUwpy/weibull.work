"use client"

import React, { useMemo, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ComposedChart, Area, BarChart, Bar
} from 'recharts'
import { cn } from '@/lib/utils'
import { DataSource, MULTI_CURVE_COLORS } from '@/lib/weibull'

interface TraceItem {
  step: number
  beta: number
  eta: number
  gamma: number
  log_likelihood: number | null
  hessian_eigenvalues?: number[]
  hessian_negative_definite?: boolean
  converged?: boolean
}

interface Props {
  traceData: TraceItem[]
  dataSources?: DataSource[]  // 多选数据源
}

export default function MLEVisualizer({ traceData, dataSources }: Props) {
  const [activeTab, setActiveTab] = useState<'convergence' | 'params' | 'table'>('convergence')

  if (!traceData || traceData.length === 0) return null

  // 是否有多个数据源需要叠加显示
  const hasMultipleSources = dataSources && dataSources.length > 0

  // Process data for display (e.g. filter out nulls if needed)
  const data = useMemo(() => traceData
    .filter(d => typeof d.beta === 'number' && typeof d.eta === 'number') // Only keep valid steps
    .map(d => ({
      ...d,
      log_likelihood: d.log_likelihood ? parseFloat(d.log_likelihood.toFixed(4)) : null,
      beta: parseFloat(d.beta.toFixed(4)),
      eta: parseFloat(d.eta.toFixed(2))
    })), [traceData])

  // 准备多曲线数据（用于叠加显示多组样本的寻优过程）
  const allLikelihoodCurves = useMemo(() => {
    const curves: { id: string; data: any[]; color: string }[] = [
      { id: 'current', data, color: hasMultipleSources ? MULTI_CURVE_COLORS[0] : '#3b82f6' }
    ]

    // 如果有 dataSources，添加每组的 log_likelihood 曲线
    if (hasMultipleSources) {
      dataSources.forEach((ds, index) => {
        if (ds.traceData && Array.isArray(ds.traceData)) {
          const processedData = ds.traceData
            .filter((d: TraceItem) => typeof d.beta === 'number' && typeof d.eta === 'number')
            .map((d: TraceItem) => ({
              ...d,
              log_likelihood: d.log_likelihood ? parseFloat(d.log_likelihood.toFixed(4)) : null,
              beta: parseFloat(d.beta.toFixed(4)),
              eta: parseFloat(d.eta.toFixed(2))
            }))
          curves.push({
            id: ds.name || `样本${index + 1}`,
            data: processedData,
            color: MULTI_CURVE_COLORS[(index + 1) % MULTI_CURVE_COLORS.length]
          })
        }
      })
    }

    return curves
  }, [data, dataSources, hasMultipleSources])

  // 准备多曲线参数收敛数据
  const allParameterCurves = useMemo(() => {
    const curves: { id: string; data: any[]; color: string }[] = [
      { id: 'current', data, color: hasMultipleSources ? MULTI_CURVE_COLORS[0] : '#3b82f6' }
    ]

    if (hasMultipleSources) {
      dataSources.forEach((ds, index) => {
        if (ds.traceData && Array.isArray(ds.traceData)) {
          const processedData = ds.traceData
            .filter((d: TraceItem) => typeof d.beta === 'number' && typeof d.eta === 'number')
            .map((d: TraceItem) => ({
              ...d,
              beta: parseFloat(d.beta.toFixed(4)),
              eta: parseFloat(d.eta.toFixed(2))
            }))
          curves.push({
            id: ds.name || `样本${index + 1}`,
            data: processedData,
            color: MULTI_CURVE_COLORS[(index + 1) % MULTI_CURVE_COLORS.length]
          })
        }
      })
    }

    return curves
  }, [data, dataSources, hasMultipleSources])

  return (
    <div className="space-y-6">
      {/* Tab Selector */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-3">
          <span className="text-sm font-bold text-slate-700">迭代过程可视化：</span>
          <div className="flex bg-slate-100 p-1 rounded-lg border border-slate-200">
            <button
              onClick={() => setActiveTab('convergence')}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-bold transition-all",
                activeTab === 'convergence'
                  ? "bg-white text-emerald-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              收敛曲线
            </button>
            <button
              onClick={() => setActiveTab('params')}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-bold transition-all",
                activeTab === 'params'
                  ? "bg-white text-blue-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              参数变化
            </button>
            <button
              onClick={() => setActiveTab('table')}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-bold transition-all",
                activeTab === 'table'
                  ? "bg-white text-purple-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              迭代表格
            </button>
          </div>
        </div>
      </div>

      {/* 收敛曲线 Tab */}
      {activeTab === 'convergence' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <h3 className="text-sm font-black text-slate-700 uppercase mb-1">似然函数优化轨迹 (Likelihood Maximization)</h3>
          <p className="text-xs text-slate-500 mb-4">
            横轴：迭代次数 (Step) | 纵轴：对数似然值 (Log-Likelihood)
            <br/>
            解释：曲线应呈现上升趋势并逐渐平缓。上升越快，说明收敛越快；震荡则意味着不稳。
          </p>
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="step" type="number" domain={['auto', 'auto']} tick={{fontSize: 10}} tickLine={false} axisLine={{stroke: '#e2e8f0'}} />
                <YAxis domain={['auto', 'auto']} tick={{fontSize: 10}} tickLine={false} axisLine={false} width={40} />
                <Tooltip
                  contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}}
                  itemStyle={{fontSize: '12px'}}
                />
                <Legend wrapperStyle={{fontSize: '12px'}} />
                {allLikelihoodCurves.map((curve) => (
                  <Line
                    key={curve.id}
                    data={curve.data}
                    type="monotone"
                    dataKey="log_likelihood"
                    stroke={curve.color}
                    strokeWidth={2}
                    dot={curve.id === 'current' ? {r: 2, fill: curve.color} : false}
                    activeDot={{r: 6}}
                    name={curve.id === 'current' ? '当前' : curve.id}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          {/* 多曲线图例 */}
          {hasMultipleSources && (
            <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-slate-100">
              {allLikelihoodCurves.map((curve) => (
                <div key={curve.id} className="flex items-center gap-1.5 text-xs">
                  <div
                    className="w-3 h-0.5 rounded"
                    style={{ backgroundColor: curve.color }}
                  />
                  <span className="text-slate-600">{curve.id === 'current' ? '当前' : curve.id}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 参数变化 Tab */}
      {activeTab === 'params' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <h3 className="text-sm font-black text-slate-700 uppercase mb-1">参数收敛过程 (Parameter Convergence)</h3>
          <p className="text-xs text-slate-500 mb-4">
            横轴：迭代次数 | 左轴：形状参数 (Beta) | 右轴：尺度参数 (Eta)
            <br/>
            解释：观察算法如何在多维空间中搜索。Beta 和 Eta 通常是耦合的，一个变动会影响另一个。
          </p>
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="step" type="number" domain={['auto', 'auto']} tick={{fontSize: 10}} tickLine={false} />
                <YAxis yAxisId="left" domain={['auto', 'auto']} tick={{fontSize: 10}} axisLine={false} label={{ value: 'Beta', angle: -90, position: 'insideLeft', fontSize: 10 }} />
                <YAxis yAxisId="right" orientation="right" domain={['auto', 'auto']} tick={{fontSize: 10}} axisLine={false} label={{ value: 'Eta', angle: 90, position: 'insideRight', fontSize: 10 }} />
                <Tooltip
                  contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}}
                  itemStyle={{fontSize: '12px'}}
                />
                <Legend wrapperStyle={{fontSize: '12px'}} />
                {allParameterCurves.map((curve) => (
                  <React.Fragment key={curve.id}>
                    <Line
                      yAxisId="left"
                      data={curve.data}
                      type="monotone"
                      dataKey="beta"
                      stroke={curve.color}
                      strokeWidth={2}
                      dot={false}
                      name={`${curve.id === 'current' ? '当前' : curve.id} β`}
                    />
                    <Line
                      yAxisId="right"
                      data={curve.data}
                      type="monotone"
                      dataKey="eta"
                      stroke={curve.color}
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      dot={false}
                      name={`${curve.id === 'current' ? '当前' : curve.id} η`}
                    />
                  </React.Fragment>
                ))}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          {/* 多曲线图例 */}
          {hasMultipleSources && (
            <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-slate-100">
              {allParameterCurves.map((curve) => (
                <div key={curve.id} className="flex items-center gap-1.5 text-xs">
                  <div
                    className="w-3 h-0.5 rounded"
                    style={{ backgroundColor: curve.color }}
                  />
                  <span className="text-slate-600">{curve.id === 'current' ? '当前' : curve.id}</span>
                  <span className="text-slate-400">(β 实线, η 虚线)</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 迭代表格 Tab */}
      {activeTab === 'table' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-slate-100">
            <h3 className="text-lg font-bold text-slate-800">迭代详情</h3>
            <p className="text-sm text-slate-500">
              每次迭代的参数值和对数似然值
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-4 py-3 text-left font-bold">迭代</th>
                  <th className="px-4 py-3 text-right font-bold">β</th>
                  <th className="px-4 py-3 text-right font-bold">η</th>
                  <th className="px-4 py-3 text-right font-bold">γ</th>
                  <th className="px-4 py-3 text-right font-bold">ln L</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.map((item, index) => {
                  const isLast = index === data.length - 1
                  return (
                    <tr
                      key={index}
                      className={cn(
                        "hover:bg-slate-50 transition-colors",
                        isLast && "bg-emerald-50/50"
                      )}
                    >
                      <td className="px-4 py-2.5 font-medium">
                        {item.step}
                        {isLast && (
                          <span className="ml-2 text-xs text-emerald-600 font-bold">
                            最终
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-blue-600">
                        {item.beta?.toFixed(4) ?? '-'}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-amber-600">
                        {item.eta?.toFixed(2) ?? '-'}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-emerald-600">
                        {item.gamma?.toFixed(4) ?? '-'}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-slate-700">
                        {item.log_likelihood?.toFixed(4) ?? '-'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Hessian Eigenvalues - 仅显示当前样本，放在所有 Tab 之后 */}
      {data.some(d => d.hessian_eigenvalues) && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <h3 className="text-sm font-black text-slate-700 uppercase mb-1">Hessian 矩阵特征值 (Hessian Eigenvalues)</h3>
          <p className="text-xs text-slate-500 mb-4">
            <strong>收敛判断标准：</strong>所有特征值 &lt; 0 → 负定矩阵 → 确认是局部最大值 ✓
            <br/>
            <strong>不收敛情况：</strong>有特征值 ≥ 0 → 可能是鞍点或局部最小值 → 未找到真正的最大值
            <br/>
            <strong>特征值含义：</strong>λ₁(β方向)、λ₂(η方向)、λ₃(γ方向) — 负值越大，该方向上越"陡峭"（更确定）
          </p>
          <div className="h-[250px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={
                data
                  .filter(d => d.hessian_eigenvalues)
                  .flatMap((d, i) =>
                    d.hessian_eigenvalues!.map((eig, j) => ({
                      step: d.step,
                      eigenvalue: eig,
                      index: j,
                      name: ['λ₁ (β方向)', 'λ₂ (η方向)', 'λ₃ (γ方向)'][j]
                    }))
                  )
              }>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="step" tick={{fontSize: 10}} tickLine={false} label={{ value: '迭代次数', position: 'insideBottom', fontSize: 10 }} />
                <YAxis domain={['auto', 'auto']} tick={{fontSize: 10}} tickLine={false} label={{ value: '特征值', angle: -90, position: 'insideLeft', fontSize: 10 }} />
                <Tooltip
                  contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}}
                  itemStyle={{fontSize: '12px'}}
                  formatter={(value, name) => typeof value === 'number' ? value.toFixed(4) : value}
                />
                <Legend wrapperStyle={{fontSize: '12px'}} />
                <Line
                  type="monotone"
                  dataKey="eigenvalue"
                  stroke="#8b5cf6"
                  strokeWidth={2}
                  dot={false}
                  name="特征值"
                />
                {/* Zero line */}
                <Line
                  type="monotone"
                  data={[{ step: 0, eigenvalue: 0 }, { step: (data[data.length - 1]?.step || 0) + 10, eigenvalue: 0 }]}
                  stroke="#ef4444"
                  strokeWidth={2}
                  strokeDasharray="3 3"
                  dot={false}
                  name="零线 (λ=0)"
                  legendType="none"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          {/* Convergence Status */}
          {data.length > 0 && data[data.length - 1].hessian_negative_definite !== undefined && (
            <div className="mt-4 p-3 rounded-lg border">
              {data[data.length - 1].hessian_negative_definite ? (
                <div className="flex items-center gap-2 text-emerald-700 bg-emerald-50 border border-emerald-200">
                  <span className="text-sm font-bold">✓ Hessian 负定</span>
                  <span className="text-xs">确认是局部最大值，收敛成功</span>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-red-700 bg-red-50 border border-red-200">
                  <span className="text-sm font-bold">✗ Hessian 非负定</span>
                  <span className="text-xs">可能不是最大值（鞍点或局部最小值），不收敛</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

    </div>
  )
}
