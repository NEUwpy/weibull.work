"use client"

import React, { useEffect, useRef, useState } from 'react'
import Plot from 'react-plotly.js'
import { Play, Loader2, Box } from 'lucide-react'

interface TraceData {
  sigma_beta_curve: { beta: number; sigma: number }[]
  grad_gamma_curve: { gamma: number; gradient: number; sigma_min: number }[]
  sigma_beta_gamma?: { gamma: number; betas: number[]; sigmas: number[] }[]  // New: full 2D surface data
  target_offset: number
  optimal_gamma: number
  optimal_beta: number
}

interface MDM3DSurfaceVisualizerProps {
  traceData: TraceData
  isLoading?: boolean
  loadingProgress?: number
  onLoadData?: () => void
  hasLoadedData?: boolean
}

// Interpolate between two arrays
function lerpArray(arr1: number[], arr2: number[], t: number): number[] {
  return arr1.map((v1, i) => v1 + t * (arr2[i] - v1))
}

// Generate 3D surface data using real calculated data with interpolation
function generateSurfaceData(traceData: TraceData) {
  const { grad_gamma_curve, sigma_beta_gamma, optimal_gamma, optimal_beta } = traceData

  // If we have the new sigma_beta_gamma data, use it
  if (sigma_beta_gamma && sigma_beta_gamma.length > 0) {
    // Sort by gamma
    const sortedData = [...sigma_beta_gamma].sort((a, b) => a.gamma - b.gamma)

    // Get all gammas from grad_gamma_curve for the full surface
    const allGammas = grad_gamma_curve.map(d => d.gamma)
    const betas = sortedData[0].betas  // All curves share the same beta values

    // Build the sigma matrix with interpolation
    const sigmaMatrix: number[][] = []

    for (const targetGamma of allGammas) {
      // Find the two surrounding calculated gamma values
      let lowerIdx = -1, upperIdx = -1

      for (let i = 0; i < sortedData.length - 1; i++) {
        if (targetGamma >= sortedData[i].gamma && targetGamma <= sortedData[i + 1].gamma) {
          lowerIdx = i
          upperIdx = i + 1
          break
        }
      }

      // Handle edge cases
      if (lowerIdx === -1) {
        if (targetGamma <= sortedData[0].gamma) {
          // Before first point - use first curve
          sigmaMatrix.push(sortedData[0].sigmas)
          continue
        } else {
          // After last point - use last curve
          sigmaMatrix.push(sortedData[sortedData.length - 1].sigmas)
          continue
        }
      }

      // Linear interpolation between the two curves
      const lower = sortedData[lowerIdx]
      const upper = sortedData[upperIdx]
      const t = (targetGamma - lower.gamma) / (upper.gamma - lower.gamma)

      const interpolatedSigmas = lerpArray(lower.sigmas, upper.sigmas, t)
      sigmaMatrix.push(interpolatedSigmas)
    }

    return {
      x: betas,
      y: allGammas,
      z: sigmaMatrix
    }
  }

  // Fallback to old method if sigma_beta_gamma is not available
  const { sigma_beta_curve } = traceData
  const gammas = grad_gamma_curve.map(d => d.gamma)
  const betas = sigma_beta_curve.map(d => d.beta)

  const sigmaMatrix: number[][] = []
  const sigmaBetaMap = new Map<number, number>()
  sigma_beta_curve.forEach(point => {
    sigmaBetaMap.set(point.beta, point.sigma)
  })

  grad_gamma_curve.forEach(gammaPoint => {
    const row: number[] = []
    const currentGamma = gammaPoint.gamma
    const isOptimalGamma = Math.abs(currentGamma - optimal_gamma) < 0.01

    betas.forEach(beta => {
      if (isOptimalGamma) {
        const sigma = sigmaBetaMap.get(beta) ?? 0
        row.push(sigma)
      } else {
        const baseSigma = gammaPoint.sigma_min
        const optimalSigmaAtBeta = sigmaBetaMap.get(beta) ?? baseSigma
        const sigmaRatio = optimalSigmaAtBeta / sigmaBetaMap.get(optimal_beta)!
        const gammaOffset = Math.abs(currentGamma - optimal_gamma) / optimal_gamma
        const estimatedSigma = baseSigma * sigmaRatio * (1 + gammaOffset * 0.5)
        row.push(estimatedSigma)
      }
    })

    sigmaMatrix.push(row)
  })

  return {
    x: betas,
    y: gammas,
    z: sigmaMatrix
  }
}

export default function MDM3DSurfaceVisualizer({
  traceData,
  isLoading = false,
  loadingProgress = 0,
  onLoadData,
  hasLoadedData = false
}: MDM3DSurfaceVisualizerProps) {
  // Toggle states
  const [showContours, setShowContours] = useState(false)
  const [showSigmaBetaCurve, setShowSigmaBetaCurve] = useState(false)

  // Show loading button if data hasn't been loaded yet
  if (!hasLoadedData && !isLoading) {
    return (
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="mb-4">
          <h3 className="text-lg font-bold text-slate-800">三维参数空间曲面（交互式3D）</h3>
          <p className="text-sm text-slate-500 mt-1">
            需要为多个γ值计算真实的 σ(β) 曲线以生成三维曲面。点击下方按钮开始计算。
          </p>
        </div>

        <div className="flex flex-col items-center justify-center py-16">
          <div className="mb-6">
            <Box size={64} className="text-purple-300" />
          </div>
          <p className="text-slate-600 font-bold mb-2">三维曲面数据未加载</p>
          <p className="text-sm text-slate-500 mb-8 text-center max-w-md">
            将为20个γ值计算完整的 σ(β) 曲线，其余值通过插值平滑补齐。
            <br />预计计算时间：5-15秒
          </p>
          <button
            onClick={onLoadData}
            className="flex items-center gap-2 px-8 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-bold transition-all shadow-lg shadow-purple-200"
          >
            <Play size={20} />
            加载三维曲面数据
          </button>
        </div>
      </div>
    )
  }

  // Show loading progress
  if (isLoading) {
    return (
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="mb-4">
          <h3 className="text-lg font-bold text-slate-800">三维参数空间曲面（交互式3D）</h3>
          <p className="text-sm text-slate-500 mt-1">
            正在计算 σ(β, γ) 二维曲面数据...
          </p>
        </div>

        <div className="flex flex-col items-center justify-center py-16">
          <Loader2 size={48} className="text-purple-600 animate-spin mb-6" />
          <p className="text-slate-600 font-bold mb-4">正在计算三维曲面数据</p>

          {/* Progress Bar */}
          <div className="w-full max-w-md">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-slate-500">计算进度</span>
              <span className="text-xs font-bold text-purple-600">{Math.round(loadingProgress)}%</span>
            </div>
            <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-purple-500 to-purple-600 transition-all duration-300 ease-out"
                style={{ width: `${loadingProgress}%` }}
              />
            </div>
            <p className="text-xs text-slate-400 mt-2 text-center">
              正在为 γ 值计算 σ(β) 曲线...
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (!traceData) return null

  const surfaceData = generateSurfaceData(traceData)
  const { optimal_beta, optimal_gamma } = traceData

  // Calculate min sigma for the optimal point marker
  const allSigmaValues = surfaceData.z.flat()
  const minSigma = Math.min(...allSigmaValues)

  // Find the indices of optimal point
  const optimalBetaIndex = surfaceData.x.findIndex(b => Math.abs(b - optimal_beta) < 0.1)
  const optimalGammaIndex = surfaceData.y.findIndex(g => Math.abs(g - optimal_gamma) < 1)

  const plotData = [
    // Surface plot - 完全关闭等高线
    {
      type: 'surface' as const,
      x: surfaceData.x,
      y: surfaceData.y,
      z: surfaceData.z,
      colorscale: [
        [0, '#3b82f6'],    // blue - 低 σ (优)
        [0.25, '#10b981'],  // emerald
        [0.5, '#22c55e'],   // green
        [0.75, '#f59e0b'],  // amber
        [1, '#ef4444']      // red - 高 σ (差)
      ],
      colorbar: {
        title: { text: 'σ_η', side: 'right', font: { size: 12, color: '#64748b' } },
        tickfont: { size: 10, color: '#64748b' },
        thickness: 15,
        len: 0.8
      },
      contours: {
        x: { show: false },
        y: { show: false },
        z: { show: false }  // 完全关闭曲面上所有等高线
      },
      showscale: true,
      hovertemplate:
        'β: %{x:.2f}<br>' +
        'γ: %{y:.1f}<br>' +
        'σ_η: %{z:.4f}<extra></extra>'
    },
    // Contours projection - 只投影到底部（z方向）
    ...(showContours ? [{
      type: 'surface' as const,
      x: surfaceData.x,
      y: surfaceData.y,
      z: surfaceData.z,
      showscale: false,
      showlegend: false,
      hoverinfo: 'skip',
      surfacecolor: surfaceData.z,
      colorscale: [
        [0, '#3b82f6'],
        [0.25, '#10b981'],
        [0.5, '#22c55e'],
        [0.75, '#f59e0b'],
        [1, '#ef4444']
      ],
      contours: {
        x: { show: false, project: { x: false } },
        y: { show: false, project: { y: false } },
        z: {
          show: true,
          usecolormap: true,
          highlightcolor: '#ffffff',
          project: { z: true },  // 只投影到z=0平面（底部）
          width: 1.5,
          start: null,
          end: null,
          size: null
        }
      }
    }] : []),
    // Gamma curve slices - 显示每个γ值对应的 σ-β 曲线切片
    ...(showSigmaBetaCurve && traceData.sigma_beta_gamma ? traceData.sigma_beta_gamma.map((curve, idx) => {
      const isOptimalGamma = Math.abs(curve.gamma - optimal_gamma) < 5
      return {
        type: 'scatter3d' as const,
        mode: 'lines' as const,
        x: curve.betas,
        y: Array(curve.betas.length).fill(curve.gamma),
        z: curve.sigmas,
        line: {
          width: isOptimalGamma ? 4 : 2,
          color: isOptimalGamma ? '#f59e0b' : `hsl(${(idx / traceData.sigma_beta_gamma!.length) * 240}, 70%, 50%)`
        },
        name: `γ=${curve.gamma.toFixed(0)}`,
        hovertemplate:
          `γ: ${curve.gamma.toFixed(0)}<br>` +
          'β: %{x:.2f}<br>' +
          'σ_η: %{z:.4f}<extra></extra>'
      }
    }) : []),
    // Optimal point marker
    {
      type: 'scatter3d' as const,
      mode: 'markers' as const,
      x: [optimal_beta],
      y: [optimal_gamma],
      z: [minSigma],
      marker: {
        size: 12,
        color: '#f59e0b',
        symbol: 'diamond',
        line: {
          color: '#ffffff',
          width: 2
        }
      },
      name: '最优解 (β*, γ*)',
      hovertemplate:
        '<b>最优解</b><br>' +
        'β*: %{x:.2f}<br>' +
        'γ*: %{y:.1f}<br>' +
        '最小 σ: %{z:.4f}<extra></extra>'
    }
  ]

  const layout = {
    title: {
      text: 'σ_η(β, γ) 三维参数空间曲面',
      font: { size: 16, color: '#1e293b' },
      x: 0.05,
      y: 0.95
    },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    margin: { l: 0, r: 0, t: 40, b: 0, pad: 0 },
    scene: {
      xaxis: {
        title: { text: '形状参数 β', font: { size: 12, color: '#64748b' } },
        range: [0, 5],  // 固定范围 0-5
        gridcolor: '#e2e8f0',
        showgrid: true,
        tickfont: { size: 10, color: '#64748b' },
        backgroundcolor: 'rgba(248, 250, 252, 0.5)'
      },
      yaxis: {
        title: { text: '位置参数 γ', font: { size: 12, color: '#64748b' } },
        gridcolor: '#e2e8f0',
        showgrid: true,
        tickfont: { size: 10, color: '#64748b' },
        backgroundcolor: 'rgba(248, 250, 252, 0.5)'
      },
      zaxis: {
        title: { text: '标准差 σ_η (对数)', font: { size: 12, color: '#64748b' } },
        type: 'log',  // 使用对数坐标
        gridcolor: '#e2e8f0',
        showgrid: true,
        tickfont: { size: 10, color: '#64748b' },
        backgroundcolor: 'rgba(248, 250, 252, 0.5)'
      },
      camera: {
        eye: { x: 1.5, y: 1.5, z: 1.3 }  // 初始视角
      },
      aspectmode: 'manual',
      aspectratio: { x: 1, y: 1.5, z: 0.8 }
    },
    showlegend: true,
    legend: {
      x: 0.02,
      y: 0.98,
      bgcolor: 'rgba(255,255,255,0.8)',
      bordercolor: '#e2e8f0',
      borderwidth: 1,
      font: { size: 11 }
    },
    annotations: [
      {
        x: 0.02,
        y: 0.02,
        xref: 'paper',
        yref: 'paper',
        text: `★ 最优解: β*=${optimal_beta.toFixed(2)}, γ*=${optimal_gamma.toFixed(1)}, σ_min=${minSigma.toFixed(4)}`,
        showarrow: false,
        font: { size: 12, color: '#f59e0b' },
        bgcolor: 'rgba(255,255,255,0.9)',
        bordercolor: '#f59e0b',
        borderwidth: 1,
        borderpad: 6,
        xanchor: 'left',
        yanchor: 'bottom'
      }
    ]
  }

  const config = {
    responsive: true,
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['lasso2d', 'select2d'],
    toImageButtonOptions: {
      format: 'png',
      filename: 'MDM_3D_Surface',
      height: 500,
      width: 700,
      scale: 1
    }
  }

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-bold text-slate-800">三维参数空间曲面（交互式3D）</h3>
        </div>
        <p className="text-sm text-slate-500">
          真正的交互式三维图，可拖拽旋转、缩放。展示 {"$\\sigma_\\eta(\\beta, \\gamma)$"} 在参数空间中的完整形态。
          颜色越蓝表示标准差越小（越优），菱形标记最优解。
        </p>
      </div>

      {/* Toggle Controls */}
      <div className="flex items-center gap-6 mb-4 flex-wrap">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={showContours}
            onChange={(e) => setShowContours(e.target.checked)}
            className="w-4 h-4 rounded border-slate-300 text-purple-600 focus:ring-purple-500"
          />
          <span className="text-sm text-slate-700">显示等高线投影</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={showSigmaBetaCurve}
            onChange={(e) => setShowSigmaBetaCurve(e.target.checked)}
            className="w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
          />
          <span className="text-sm text-slate-700">显示γ值曲线切片（20条）</span>
        </label>
      </div>

      <div className="h-[450px] w-full">
        <Plot
          data={plotData as any}
          layout={layout as any}
          config={config as any}
          style={{ width: '100%', height: '100%' }}
          useResizeHandler={true}
        />
      </div>

      {/* Instructions */}
      <div className="mt-4 flex items-center gap-4 text-xs text-slate-500 bg-slate-50 rounded-lg p-3 border border-slate-200">
        <div className="flex items-center gap-1.5">
          <span className="w-5 h-5 rounded bg-slate-200 flex items-center justify-center">🖱️</span>
          <span>拖拽旋转</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-5 h-5 rounded bg-slate-200 flex items-center justify-center">🔍</span>
          <span>滚轮缩放</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-5 h-5 rounded bg-slate-200 flex items-center justify-center">◆</span>
          <span>菱形 = 最优解</span>
        </div>
        {showSigmaBetaCurve && (
          <div className="flex items-center gap-1.5">
            <span className="w-5 h-5 rounded bg-orange-200 flex items-center justify-center">📈</span>
            <span>曲线 = γ值切片（橙色为最优γ）</span>
          </div>
        )}
      </div>
    </div>
  )
}
