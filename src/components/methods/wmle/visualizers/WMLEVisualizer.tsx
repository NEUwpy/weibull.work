"use client"

import React, { useMemo, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ComposedChart, Area
} from 'recharts'
import { DataSource, MULTI_CURVE_COLORS } from '@/lib/weibull'
import { ObjectiveSurface3D } from '@/components/shared/charts'
import type { SurfaceGridData, OptimizationStep } from '@/components/shared/charts'
import { cn } from '@/lib/utils'
import { Box, Loader2, Play } from 'lucide-react'
import { getApiBaseUrl } from '@/lib/config'

interface TraceItem {
  phase: string // 'init', 'iter', 'final', 'surface'
  step?: number
  beta?: number   // 系统符号：形状参数
  gamma?: number  // 系统符号：位置参数
  eta?: number    // 系统符号：尺度参数
  w1?: number
  w2?: number
  w3?: number
  obj_val?: number
  // surface data
  betas?: number[]
  gammas?: number[]
  values?: (number | null)[][]
  optimal_beta?: number
  optimal_gamma?: number
}

interface Props {
  traceData: TraceItem[]
  dataSources?: DataSource[]  // 多选数据源
  data?: number[]             // 原始数据（用于加载 3D 曲面）
  onSurfaceLoad?: (surfaceData: TraceItem) => void  // 曲面数据加载完成回调
}

export default function WMLEVisualizer({ traceData, dataSources, data, onSurfaceLoad }: Props) {
  if (!traceData || traceData.length === 0) return null

  // 视图模式：'surface' (3D曲面) 或 'iter' (迭代过程)
  const [viewMode, setViewMode] = useState<'surface' | 'iter'>('surface')

  // 加载状态
  const [isLoadingSurface, setIsLoadingSurface] = useState(false)
  const [loadProgress, setLoadProgress] = useState(0)
  const [hasLoadedSurface, setHasLoadedSurface] = useState(false)

  // 是否有多个数据源
  const hasMultipleSources = dataSources && dataSources.length > 0

  // Filter only iteration steps for charts
  const iterData = traceData
    .filter(d => d.phase === 'iter')
    .map((d, i) => ({
      ...d,
      step: i + 1,
      obj_val: typeof d.obj_val === 'number' ? parseFloat(d.obj_val.toFixed(6)) : null,
      beta: typeof d.beta === 'number' ? parseFloat(d.beta.toFixed(4)) : null,
      w3: typeof d.w3 === 'number' ? parseFloat(d.w3.toFixed(4)) : null
    }))

  // Get static weights from init step
  const initData = traceData.find(d => d.phase === 'init')
  const w1 = initData?.w1?.toFixed(4) || 'N/A'
  const w2 = initData?.w2?.toFixed(4) || 'N/A'

  // 获取 3D 曲面数据
  const surfaceItem = traceData.find(d => d.phase === 'surface')
  const hasSurfaceData = surfaceItem && surfaceItem.betas && surfaceItem.gammas && surfaceItem.values

  // 构建 3D 曲面数据
  const surfaceGridData: SurfaceGridData | null = hasSurfaceData ? {
    betas: surfaceItem!.betas!,
    gammas: surfaceItem!.gammas!,
    values: surfaceItem!.values!
  } : null

  // 构建优化路径数据（用于 3D 曲面上的轨迹）
  const optimizationPath: OptimizationStep[] = useMemo(() => {
    return iterData.map((d, i) => ({
      beta: d.beta ?? 0,
      gamma: d.gamma ?? 0,
      objValue: d.obj_val ?? 0,
      iteration: i + 1
    }))
  }, [iterData])

  // 最优点
  const finalData = traceData.find(d => d.phase === 'final')
  const optimalPoint = surfaceItem ? {
    beta: surfaceItem.optimal_beta ?? finalData?.beta ?? 0,
    gamma: surfaceItem.optimal_gamma ?? finalData?.gamma ?? 0,
    objValue: optimizationPath.length > 0 ? optimizationPath[optimizationPath.length - 1].objValue : undefined
  } : finalData ? {
    beta: finalData.beta ?? 0,
    gamma: finalData.gamma ?? 0,
    objValue: optimizationPath.length > 0 ? optimizationPath[optimizationPath.length - 1].objValue : undefined
  } : null

  // 加载 3D 曲面数据
  const handleLoadSurface = async () => {
    if (!data || data.length === 0) return

    setIsLoadingSurface(true)
    setLoadProgress(0)

    // 模拟进度
    const progressInterval = setInterval(() => {
      setLoadProgress(prev => {
        if (prev >= 90) {
          clearInterval(progressInterval)
          return 90
        }
        return prev + Math.random() * 15
      })
    }, 200)

    try {
      const response = await fetch(`${getApiBaseUrl()}/calculate_3d_surface`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          method: 'wmle',
          data: data
        })
      })

      if (!response.ok) {
        throw new Error('Failed to load 3D surface data')
      }

      const result = await response.json()

      clearInterval(progressInterval)
      setLoadProgress(100)

      // 提取曲面数据
      if (result.trace_data) {
        const surfaceData = result.trace_data.find((d: TraceItem) => d.phase === 'surface')
        if (surfaceData && onSurfaceLoad) {
          onSurfaceLoad(surfaceData)
        }
      }

      setHasLoadedSurface(true)

      setTimeout(() => {
        setIsLoadingSurface(false)
        setLoadProgress(0)
      }, 300)
    } catch (error) {
      clearInterval(progressInterval)
      console.error('Failed to load 3D surface:', error)
      setIsLoadingSurface(false)
      setLoadProgress(0)
      alert('加载三维曲面数据失败，请确保后端服务已启动。')
    }
  }

  // 准备多曲线数据（用于迭代过程视图）
  const allObjectiveCurves = useMemo(() => {
    const curves: { id: string; data: any[]; color: string }[] = [
      { id: 'current', data: iterData, color: hasMultipleSources ? MULTI_CURVE_COLORS[0] : '#ef4444' }
    ]

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
              beta: typeof d.beta === 'number' ? parseFloat(d.beta.toFixed(4)) : null,
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
    <div className="space-y-8 animate-in fade-in duration-500">

      {/* 视图切换 */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-sm font-bold text-slate-700">寻优过程可视化：</span>
          <div className="flex bg-slate-100 p-1 rounded-lg border border-slate-200">
            <button
              onClick={() => setViewMode('surface')}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-bold transition-all",
                viewMode === 'surface'
                  ? "bg-white text-purple-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              3D 曲面
            </button>
            <button
              onClick={() => setViewMode('iter')}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-bold transition-all",
                viewMode === 'iter'
                  ? "bg-white text-blue-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              迭代过程
            </button>
          </div>
          <span className="text-xs text-slate-400 ml-auto">点击切换不同可视化方案</span>
        </div>
      </div>

      {/* 3D 曲面视图 */}
      {viewMode === 'surface' && (
        <>
          {/* 未加载曲面数据时显示加载按钮 */}
          {!hasSurfaceData && !isLoadingSurface && (
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
              <div className="mb-4">
                <h3 className="text-lg font-bold text-slate-800">目标函数三维曲面</h3>
                <p className="text-sm text-slate-500 mt-1">
                  展示 WMLE 目标函数 <span className="font-mono bg-slate-100 px-1 rounded">O(β, γ) = T₁² + T₂²</span> 在参数空间中的形态。
                  点击下方按钮加载三维曲面数据。
                </p>
              </div>

              <div className="flex flex-col items-center justify-center py-12">
                <div className="mb-6">
                  <Box size={64} className="text-purple-300" />
                </div>
                <p className="text-slate-600 font-bold mb-2">三维曲面数据未加载</p>
                <p className="text-sm text-slate-500 mb-8 text-center max-w-md">
                  将计算 50×50=2500 个网格点的目标函数值。
                  <br />预计计算时间：3-10秒
                </p>
                <button
                  onClick={handleLoadSurface}
                  disabled={!data || data.length === 0}
                  className={cn(
                    "flex items-center gap-2 px-8 py-3 rounded-xl font-bold transition-all shadow-lg",
                    data && data.length > 0
                      ? "bg-purple-600 hover:bg-purple-700 text-white shadow-purple-200"
                      : "bg-slate-200 text-slate-400 cursor-not-allowed shadow-none"
                  )}
                >
                  <Play size={20} />
                  加载三维曲面数据
                </button>
                {(!data || data.length === 0) && (
                  <p className="text-xs text-slate-400 mt-3">需要先输入数据才能加载曲面</p>
                )}
              </div>
            </div>
          )}

          {/* 加载中状态 */}
          {isLoadingSurface && (
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
              <div className="mb-4">
                <h3 className="text-lg font-bold text-slate-800">目标函数三维曲面</h3>
                <p className="text-sm text-slate-500 mt-1">
                  正在计算 50×50 网格点的目标函数值...
                </p>
              </div>

              <div className="flex flex-col items-center justify-center py-12">
                <Loader2 size={48} className="text-purple-600 animate-spin mb-6" />
                <p className="text-slate-600 font-bold mb-4">正在计算三维曲面数据</p>

                {/* Progress Bar */}
                <div className="w-full max-w-md">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-slate-500">计算进度</span>
                    <span className="text-xs font-bold text-purple-600">{Math.round(loadProgress)}%</span>
                  </div>
                  <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-purple-500 to-purple-600 transition-all duration-300 ease-out"
                      style={{ width: `${loadProgress}%` }}
                    />
                  </div>
                  <p className="text-xs text-slate-400 mt-2 text-center">
                    正在计算 O(β, γ) 在 2500 个网格点的值...
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* 曲面数据已加载 */}
          {hasSurfaceData && surfaceGridData && (
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
              <div className="mb-4">
                <h3 className="text-lg font-bold text-slate-800">目标函数三维曲面</h3>
                <p className="text-sm text-slate-500 mt-1">
                  展示 WMLE 目标函数 <span className="font-mono bg-slate-100 px-1 rounded">O(β, γ) = T₁² + T₂²</span> 在参数空间中的形态。
                  <span className="text-amber-600 font-medium"> 虚线</span>为 Nelder-Mead 优化路径，
                  <span className="text-emerald-600 font-medium"> 菱形</span>为最优解（谷底）。
                </p>
              </div>

              <ObjectiveSurface3D
                surfaceData={surfaceGridData}
                optimizationPath={optimizationPath}
                optimalPoint={optimalPoint ?? undefined}
                showOptimalMarker={true}
                height={450}
                logScale={true}
              />

              {/* 图例说明 */}
              <div className="mt-4 flex items-center gap-4 text-xs text-slate-500 bg-slate-50 rounded-lg p-3 border border-slate-200 flex-wrap">
                <div className="flex items-center gap-1.5">
                  <div className="w-4 h-0.5 bg-gradient-to-r from-blue-500 via-green-400 to-red-500 rounded"></div>
                  <span>曲面：目标函数 O（蓝=谷底/优，红=峰值/差）</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-4 h-0.5 bg-amber-500 rounded" style={{ borderStyle: 'dashed' }}></div>
                  <span>优化路径</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-emerald-500 text-base">◆</span>
                  <span>最优解</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-slate-400">🖱️</span>
                  <span>拖拽旋转 | 滚轮缩放</span>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* 迭代过程视图 */}
      {viewMode === 'iter' && (
        <>
          {/* Info Cards - 仅显示当前样本 */}
          <div className="grid grid-cols-2 gap-4">
             <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                <span className="text-[10px] uppercase font-bold text-slate-400">静态权重 J₁</span>
                <div className="text-2xl font-black text-slate-700">{w1}</div>
             </div>
             <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                <span className="text-[10px] uppercase font-bold text-slate-400">静态权重 J₂</span>
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
            <h3 className="text-sm font-black text-slate-700 uppercase mb-1">动态权重 J₃ 监测 (Dynamic Weight)</h3>
            <p className="text-xs text-slate-500 mb-4">
              横轴：迭代次数 | 左轴：形状参数 (β) | 右轴：权重 J₃
              <br/>
              解释：J₃ 不是常数，它随当前估计的形状参数动态调整，这是 WMLE 修正偏差的核心机制。
            </p>
            <div className="h-[250px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="step" type="number" domain={['auto', 'auto']} tick={{fontSize: 10}} tickLine={false} />
                  <YAxis yAxisId="left" domain={['auto', 'auto']} tick={{fontSize: 10}} axisLine={false} label={{ value: 'β', angle: -90, position: 'insideLeft', fontSize: 10 }} />
                  <YAxis yAxisId="right" orientation="right" domain={['auto', 'auto']} tick={{fontSize: 10}} axisLine={false} label={{ value: 'J₃', angle: 90, position: 'insideRight', fontSize: 10 }} />
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
                        name={`${curve.id === 'current' ? '当前' : curve.id} J₃`}
                      />
                      <Line
                        yAxisId="left"
                        data={curve.data}
                        type="monotone"
                        dataKey="beta"
                        stroke={curve.color}
                        strokeWidth={2}
                        strokeDasharray="5 5"
                        dot={false}
                        name={`${curve.id === 'current' ? '当前' : curve.id} β`}
                      />
                    </React.Fragment>
                  ))}
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            {hasMultipleSources && (
              <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-slate-100">
                {allDynamicWeightCurves.map((curve) => (
                  <div key={curve.id} className="flex items-center gap-1.5 text-xs">
                    <div
                      className="w-3 h-0.5 rounded"
                      style={{ backgroundColor: curve.color }}
                    />
                    <span className="text-slate-600">{curve.id === 'current' ? '当前' : curve.id}</span>
                    <span className="text-slate-400">(β 虚线)</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

    </div>
  )
}
