"use client"

import React, { useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ComposedChart, Area
} from 'recharts'
import { DataSource, MULTI_CURVE_COLORS } from '@/lib/weibull'

interface TraceItem {
  phase: string // 'init', 'iter', 'final'
  step?: number
  gamma?: number
  alpha?: number
  beta?: number // In final step
  eta?: number // In final step
  w1?: number
  w2?: number
  w3?: number
  obj_val?: number
}

interface Props {
  traceData: TraceItem[]
  dataSources?: DataSource[]  // 多选数据源
}

export default function WMLEVisualizer({ traceData, dataSources }: Props) {
  if (!traceData || traceData.length === 0) return null

  // 是否有多个数据源
  const hasMultipleSources = dataSources && dataSources.length > 0

  // Filter only iteration steps for charts
  const iterData = traceData
    .filter(d => d.phase === 'iter')
    .map((d, i) => ({
      ...d,
      step: i + 1,
      obj_val: typeof d.obj_val === 'number' ? parseFloat(d.obj_val.toFixed(6)) : null,
      gamma: typeof d.gamma === 'number' ? parseFloat(d.gamma.toFixed(4)) : null,
      w3: typeof d.w3 === 'number' ? parseFloat(d.w3.toFixed(4)) : null
    }))

  // Get static weights from init step
  const initData = traceData.find(d => d.phase === 'init')
  const w1 = initData?.w1?.toFixed(4) || 'N/A'
  const w2 = initData?.w2?.toFixed(4) || 'N/A'

  // 准备多曲线数据（用于叠加显示多组样本的寻优过程）
  const allObjectiveCurves = useMemo(() => {
    const curves: { id: string; data: any[]; color: string }[] = [
      { id: 'current', data: iterData, color: hasMultipleSources ? MULTI_CURVE_COLORS[0] : '#ef4444' }
    ]

    // 如果有 dataSources，添加每组的目标函数曲线
    if (hasMultipleSources) {
      dataSources.forEach((ds, index) => {
        if (ds.traceData && Array.isArray(ds.traceData)) {
          const processedData = ds.traceData
            .filter((d: TraceItem) => d.phase === 'iter')
            .map((d: TraceItem, i: number) => ({
              ...d,
              step: i + 1,
              obj_val: typeof d.obj_val === 'number' ? parseFloat(d.obj_val.toFixed(6)) : null
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
  }, [iterData, dataSources, hasMultipleSources])

  // 准备多曲线动态权重数据
  const allDynamicWeightCurves = useMemo(() => {
    const curves: { id: string; data: any[]; color: string }[] = [
      { id: 'current', data: iterData, color: hasMultipleSources ? MULTI_CURVE_COLORS[0] : '#10b981' }
    ]

    if (hasMultipleSources) {
      dataSources.forEach((ds, index) => {
        if (ds.traceData && Array.isArray(ds.traceData)) {
          const processedData = ds.traceData
            .filter((d: TraceItem) => d.phase === 'iter')
            .map((d: TraceItem, i: number) => ({
              ...d,
              step: i + 1,
              gamma: typeof d.gamma === 'number' ? parseFloat(d.gamma.toFixed(4)) : null,
              w3: typeof d.w3 === 'number' ? parseFloat(d.w3.toFixed(4)) : null
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
  }, [iterData, dataSources, hasMultipleSources])

  return (
    <div className="space-y-8">

      {/* Info Cards - 仅显示当前样本 */}
      <div className="grid grid-cols-2 gap-4">
         <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
            <span className="text-[10px] uppercase font-bold text-slate-400">静态权重 W1</span>
            <div className="text-2xl font-black text-slate-700">{w1}</div>
         </div>
         <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
            <span className="text-[10px] uppercase font-bold text-slate-400">静态权重 W2</span>
            <div className="text-2xl font-black text-slate-700">{w2}</div>
         </div>
      </div>

      {/* Chart 1: Objective Minimization */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <h3 className="text-sm font-black text-slate-700 uppercase mb-1">加权目标函数优化 (Objective Minimization)</h3>
        <p className="text-xs text-slate-500 mb-4">
          横轴：迭代次数 | 纵轴：残差平方和 (Objective Value)
          <br/>
          解释：WMLE 寻找加权方程组的根，即使得残差平方和趋近于 0。
        </p>
        <div className="h-[250px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="step" type="number" domain={['auto', 'auto']} tick={{fontSize: 10}} tickLine={false} />
              <YAxis domain={[0, 'auto']} tick={{fontSize: 10}} axisLine={false} width={40} />
              <Tooltip
                contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}}
                itemStyle={{fontSize: '12px'}}
              />
              <Legend wrapperStyle={{fontSize: '12px'}} />
              {allObjectiveCurves.map((curve) => (
                <Line
                  key={curve.id}
                  data={curve.data}
                  type="monotone"
                  dataKey="obj_val"
                  stroke={curve.color}
                  strokeWidth={2}
                  dot={false}
                  name={curve.id === 'current' ? '当前' : curve.id}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
        {/* 多曲线图例 */}
        {hasMultipleSources && (
          <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-slate-100">
            {allObjectiveCurves.map((curve) => (
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

      {/* Chart 2: Dynamic Weight W3 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <h3 className="text-sm font-black text-slate-700 uppercase mb-1">动态权重 W3 监测 (Dynamic Weight)</h3>
        <p className="text-xs text-slate-500 mb-4">
          横轴：迭代次数 | 左轴：形状参数 (Gamma/Beta) | 右轴：权重 W3
          <br/>
          解释：W3 不是常数，它随当前估计的形状参数动态调整，这是 WMLE 修正偏差的核心机制。
        </p>
        <div className="h-[250px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="step" type="number" domain={['auto', 'auto']} tick={{fontSize: 10}} tickLine={false} />
              <YAxis yAxisId="left" domain={['auto', 'auto']} tick={{fontSize: 10}} axisLine={false} label={{ value: 'Gamma', angle: -90, position: 'insideLeft', fontSize: 10 }} />
              <YAxis yAxisId="right" orientation="right" domain={['auto', 'auto']} tick={{fontSize: 10}} axisLine={false} label={{ value: 'W3', angle: 90, position: 'insideRight', fontSize: 10 }} />
              <Tooltip
                contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}}
                itemStyle={{fontSize: '12px'}}
              />
              <Legend wrapperStyle={{fontSize: '12px'}} />
              {allDynamicWeightCurves.map((curve) => (
                <React.Fragment key={curve.id}>
                  <Area
                    yAxisId="right"
                    data={curve.data}
                    type="monotone"
                    dataKey="w3"
                    fill={curve.color + '33'}
                    stroke={curve.color}
                    name={`${curve.id === 'current' ? '当前' : curve.id} W3`}
                  />
                  <Line
                    yAxisId="left"
                    data={curve.data}
                    type="monotone"
                    dataKey="gamma"
                    stroke={curve.color}
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    dot={false}
                    name={`${curve.id === 'current' ? '当前' : curve.id} γ`}
                  />
                </React.Fragment>
              ))}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        {/* 多曲线图例 */}
        {hasMultipleSources && (
          <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-slate-100">
            {allDynamicWeightCurves.map((curve) => (
              <div key={curve.id} className="flex items-center gap-1.5 text-xs">
                <div
                  className="w-3 h-0.5 rounded"
                  style={{ backgroundColor: curve.color }}
                />
                <span className="text-slate-600">{curve.id === 'current' ? '当前' : curve.id}</span>
                <span className="text-slate-400">(γ 虚线)</span>
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  )
}
