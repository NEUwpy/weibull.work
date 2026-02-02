"use client"

import React, { useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Label,
  Legend,
  Brush
} from 'recharts'
import Plot from 'react-plotly.js'
import MDM3DSurfaceVisualizer from './MDM3DSurfaceVisualizer'
import MDMOffsetAnalyzer from './MDMOffsetAnalyzer'
import { cn } from '@/lib/utils'

interface TraceData {
  sigma_beta_curve: { beta: number; sigma: number }[]
  grad_gamma_curve: { gamma: number; gradient: number; sigma_min: number }[]
  sigma_beta_gamma?: { gamma: number; betas: number[]; sigmas: number[] }[]
  target_offset: number
  optimal_gamma: number
  optimal_beta: number
  data?: number[]  // Original data for 3D surface calculation
}

interface MDMVisualizerProps {
  traceData: TraceData
  methodId?: string  // For API calls
}

export default function MDMVisualizer({ traceData, methodId = 'mdm' }: MDMVisualizerProps) {
  const [activeScheme, setActiveScheme] = useState<'original' | '3d' | 'offset'>('original')
  const [surfaceData, setSurfaceData] = useState<TraceData | null>(null)
  const [isLoadingSurface, setIsLoadingSurface] = useState(false)
  const [loadingProgress, setLoadingProgress] = useState(0)

  // Gamma slider state for original view (shape parameter optimization)
  const [gammaIndex, setGammaIndex] = useState(() => {
    // Prefer sigma_beta_gamma (20 points) if available, otherwise use grad_gamma_curve (60 points)
    if (traceData.sigma_beta_gamma && traceData.sigma_beta_gamma.length > 0) {
      const optimalIdx = traceData.sigma_beta_gamma.findIndex(
        d => Math.abs(d.gamma - traceData.optimal_gamma) < 5
      )
      return optimalIdx >= 0 ? optimalIdx : Math.floor(traceData.sigma_beta_gamma.length / 2)
    } else {
      const optimalIdx = traceData.grad_gamma_curve.findIndex(
        d => Math.abs(d.gamma - traceData.optimal_gamma) < 1
      )
      return optimalIdx >= 0 ? optimalIdx : Math.floor(traceData.grad_gamma_curve.length / 2)
    }
  })

  if (!traceData) return null

  // Determine which data source to use for the slider
  const useSigmaBetaGamma = traceData.sigma_beta_gamma && traceData.sigma_beta_gamma.length > 0
  const gammaDataCount = useSigmaBetaGamma ? traceData.sigma_beta_gamma!.length : traceData.grad_gamma_curve.length

  // Get the currently selected gamma data
  const selectedGammaData = useSigmaBetaGamma
    ? traceData.sigma_beta_gamma![gammaIndex]
    : traceData.grad_gamma_curve[gammaIndex]
  const selectedGamma = selectedGammaData?.gamma ?? traceData.optimal_gamma

  // Generate sigma(beta) curve for the selected gamma
  const currentSigmaBetaCurve = useSigmaBetaGamma && selectedGammaData && 'betas' in selectedGammaData
    ? selectedGammaData.betas.map((beta: number, i: number) => ({
        beta,
        sigma: selectedGammaData.sigmas[i]
      }))
    : traceData.sigma_beta_curve // Fallback to optimal gamma curve if sigma_beta_gamma not available

  // Handle loading 3D surface data
  const handleLoad3DSurface = async () => {
    setIsLoadingSurface(true)
    setLoadingProgress(0)

    // Simulate progress while loading
    const progressInterval = setInterval(() => {
      setLoadingProgress(prev => {
        if (prev >= 90) {
          clearInterval(progressInterval)
          return 90
        }
        return prev + Math.random() * 15
      })
    }, 200)

    try {
      // Call backend to calculate sigma_beta_gamma
      const response = await fetch('http://localhost:8001/calculate_3d_surface', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          method: methodId,
          data: traceData.data || [],
          trace_data: traceData
        })
      })

      if (!response.ok) {
        throw new Error('Failed to load 3D surface data')
      }

      const result = await response.json()

      clearInterval(progressInterval)
      setLoadingProgress(100)

      // Update trace data with sigma_beta_gamma from backend result
      const newTraceData = result.trace_data || result
      setSurfaceData({
        ...traceData,
        sigma_beta_gamma: newTraceData.sigma_beta_gamma || traceData.sigma_beta_gamma
      })

      setTimeout(() => {
        setIsLoadingSurface(false)
        setLoadingProgress(0)
      }, 300)
    } catch (error) {
      clearInterval(progressInterval)
      console.error('Failed to load 3D surface:', error)
      setIsLoadingSurface(false)
      setLoadingProgress(0)
      alert('加载三维曲面数据失败，请确保后端服务已启动。')
    }
  }

  // Reset 3D data when switching away from 3D view
  const handleSchemeChange = (scheme: 'original' | '3d' | 'offset') => {
    setActiveScheme(scheme)
    if (scheme !== '3d') {
      setSurfaceData(null)
    }
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Scheme Selector */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-sm font-bold text-slate-700">寻优过程可视化：</span>
          <div className="flex bg-slate-100 p-1 rounded-lg border border-slate-200">
            <button
              onClick={() => handleSchemeChange('original')}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-bold transition-all",
                activeScheme === 'original'
                  ? "bg-white text-blue-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              原始视图
            </button>
            <button
              onClick={() => handleSchemeChange('offset')}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-bold transition-all",
                activeScheme === 'offset'
                  ? "bg-white text-emerald-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              偏移量分析
            </button>
            <button
              onClick={() => handleSchemeChange('3d')}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-bold transition-all",
                activeScheme === '3d'
                  ? "bg-white text-purple-600 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              三维曲面
            </button>
          </div>
          <span className="text-xs text-slate-400 ml-auto">点击切换不同可视化方案</span>
        </div>
      </div>

      {/* Original View */}
      {activeScheme === 'original' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

        {/* Chart 1: Sigma vs Beta (with Gamma Slider) */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-bold text-slate-800">形状参数寻优</h3>
              <span className="text-sm font-bold text-blue-600">γ = {selectedGamma.toFixed(2)}</span>
            </div>
            <p className="text-sm text-slate-500">
              展示在选定的位置参数下，尺度参数标准差 {"$\\sigma_{\\eta}$"} 随形状参数 {"$\\beta$"} 的变化。
            </p>
          </div>

          {/* Gamma Slider */}
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-slate-500">位置参数 γ</span>
              <span className="text-xs text-slate-400">
                {gammaIndex + 1} / {gammaDataCount}
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={gammaDataCount - 1}
              step={1}
              value={gammaIndex}
              onChange={(e) => setGammaIndex(parseInt(e.target.value))}
              className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
              style={{
                background: `linear-gradient(to right, #93c5fd 0%, #93c5fd ${(gammaIndex / (gammaDataCount - 1)) * 100}%, #e2e8f0 ${(gammaIndex / (gammaDataCount - 1)) * 100}%, #e2e8f0 100%)`
              }}
            />
            <div className="flex justify-between text-xs text-slate-400 mt-1">
              <span>{useSigmaBetaGamma
                ? traceData.sigma_beta_gamma![0].gamma.toFixed(1)
                : traceData.grad_gamma_curve[0].gamma.toFixed(1)}
              </span>
              <span>{useSigmaBetaGamma
                ? traceData.sigma_beta_gamma![traceData.sigma_beta_gamma!.length - 1].gamma.toFixed(1)
                : traceData.grad_gamma_curve[traceData.grad_gamma_curve.length - 1].gamma.toFixed(1)}
              </span>
            </div>
          </div>

          <div className="h-[280px] w-full">
            <Plot
              data={[
                {
                  x: currentSigmaBetaCurve.map(d => d.beta),
                  y: currentSigmaBetaCurve.map(d => d.sigma),
                  type: 'scatter',
                  mode: 'lines',
                  line: { color: '#3b82f6', width: 3 },
                  name: 'σ_η'
                },
                ...(Math.abs(selectedGamma - traceData.optimal_gamma) < 5 ? [{
                  x: [traceData.optimal_beta, traceData.optimal_beta],
                  y: [0.1, Math.max(...currentSigmaBetaCurve.map(d => d.sigma))],
                  type: 'scatter',
                  mode: 'lines',
                  line: { color: '#f59e0b', width: 2, dash: 'dashdot' },
                  name: '最优 β',
                  hovertemplate: 'β: %{x:.2f}<extra></extra>'
                }] : [])
              ] as any}
              layout={{
                margin: { t: 20, r: 20, b: 40, l: 40 },
                xaxis: {
                  title: '形状参数 β',
                  range: [0, 5],
                  tickfont: { size: 10, color: '#64748b' },
                  gridcolor: '#f1f5f9',
                  showgrid: true
                },
                yaxis: {
                  title: { text: '标准差 σ_η (对数)', font: { size: 11, color: '#64748b' } },
                  type: 'log',
                  tickfont: { size: 10, color: '#64748b' },
                  gridcolor: '#f1f5f9',
                  showgrid: true
                },
                hovermode: 'x unified',
                showlegend: false,
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)'
              } as any}
              config={{
                responsive: true,
                displayModeBar: false,
                displaylogo: false
              }}
              style={{ width: '100%', height: '100%' }}
              useResizeHandler={true}
            />
          </div>
        </div>

        {/* Chart 2: Gradient vs Gamma */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="mb-4">
            <h3 className="text-lg font-bold text-slate-800">位置参数梯度判据</h3>
            <p className="text-sm text-slate-500">
              {"$\\nabla(\\gamma)$"} 曲线与补偿阈值 {"$\\delta$"}={traceData.target_offset} 的交点即为最佳位置参数。
              <span className="text-blue-600 font-medium">蓝色竖线</span>标示当前选择的 γ 值。
            </p>
          </div>
          <div className="h-[280px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={traceData.grad_gamma_curve} margin={{ top: 5, right: 20, bottom: 20, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="gamma"
                  type="number"
                  domain={['auto', 'auto']}
                  tickFormatter={(v) => v.toFixed(0)}
                  tick={{ fontSize: 10 }}
                >
                  <Label value="位置参数 γ" position="bottom" offset={0} style={{ fontSize: 10, fill: '#94a3b8' }} />
                </XAxis>
                <YAxis
                  width={40}
                  tick={{ fontSize: 10 }}
                />
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                  labelFormatter={(v) => `γ: ${Number(v).toFixed(1)}`}
                  formatter={(v: number) => [v.toFixed(4), '∇(γ)']}
                />
                <ReferenceLine y={traceData.target_offset} stroke="#10b981" strokeDasharray="3 3" label={{ position: 'right', value: `δ=${traceData.target_offset}`, fill: '#10b981', fontSize: 10 }} />
                <ReferenceLine y={0} stroke="#cbd5e1" />
                <Line
                  type="monotone"
                  dataKey="gradient"
                  stroke="#ef4444"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 6 }}
                />
                {/* Current selected gamma marker */}
                <ReferenceLine x={selectedGamma} stroke="#3b82f6" strokeDasharray="2 2" strokeWidth={2}>
                  <Label value="当前" position="top" fill="#3b82f6" fontSize={9} />
                </ReferenceLine>
                {/* Optimal gamma marker */}
                {Math.abs(selectedGamma - traceData.optimal_gamma) > 1 && (
                  <ReferenceLine x={traceData.optimal_gamma} stroke="#f59e0b" strokeDasharray="3 3">
                    <Label value="最优" position="bottom" fill="#f59e0b" fontSize={9} />
                  </ReferenceLine>
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>
      )}

      {/* Offset Analysis */}
      {activeScheme === 'offset' && (
        <MDMOffsetAnalyzer traceData={traceData} />
      )}

      {/* 3D Surface Plot */}
      {activeScheme === '3d' && (
        <MDM3DSurfaceVisualizer
          traceData={surfaceData || traceData}
          isLoading={isLoadingSurface}
          loadingProgress={loadingProgress}
          onLoadData={handleLoad3DSurface}
          hasLoadedData={surfaceData !== null}
        />
      )}
    </div>
  )
}
