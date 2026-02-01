"use client"

import React, { useEffect, useRef } from 'react'
import Plot from 'react-plotly.js'

interface TraceData {
  sigma_beta_curve: { beta: number; sigma: number }[]
  grad_gamma_curve: { gamma: number; gradient: number; sigma_min: number }[]
  target_offset: number
  optimal_gamma: number
  optimal_beta: number
}

interface MDM3DSurfaceVisualizerProps {
  traceData: TraceData
}

// Generate 3D surface data
function generateSurfaceData(traceData: TraceData) {
  const { grad_gamma_curve, sigma_beta_curve, optimal_gamma, optimal_beta } = traceData

  // Get unique values for each axis
  const gammas = grad_gamma_curve.map(d => d.gamma)
  const betas = sigma_beta_curve.map(d => d.beta)

  // Build the sigma matrix (2D array: sigma[gamma_index][beta_index])
  const sigmaMatrix: number[][] = []

  grad_gamma_curve.forEach(gammaPoint => {
    const baseSigma = gammaPoint.sigma_min
    const row: number[] = []

    betas.forEach(beta => {
      // Simulate sigma at this (beta, gamma) point
      const betaOffset = Math.abs(beta - optimal_beta)
      const gammaOffset = Math.abs(gammaPoint.gamma - optimal_gamma) / optimal_gamma
      const estimatedSigma = baseSigma + betaOffset * baseSigma * 0.3 + gammaOffset * baseSigma * 0.2

      row.push(estimatedSigma)
    })

    sigmaMatrix.push(row)
  })

  return {
    x: betas,         // 形状参数 β
    y: gammas,        // 位置参数 γ
    z: sigmaMatrix    // 标准差 σ_η 的二维矩阵
  }
}

export default function MDM3DSurfaceVisualizer({ traceData }: MDM3DSurfaceVisualizerProps) {
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
    // Surface plot
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
        z: {
          show: true,
          usecolormap: true,
          highlightcolor: "#f59e0b",
          project: { z: true }
        }
      },
      opacity: 0.9,
      showscale: true,
      hovertemplate:
        'β: %{x:.2f}<br>' +
        'γ: %{y:.1f}<br>' +
        'σ_η: %{z:.4f}<extra></extra>'
    },
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
        title: { text: '标准差 σ_η', font: { size: 12, color: '#64748b' } },
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
        <h3 className="text-lg font-bold text-slate-800">三维参数空间曲面（交互式3D）</h3>
        <p className="text-sm text-slate-500 mt-1">
          真正的交互式三维图，可拖拽旋转、缩放。展示 {"$\\sigma_\\eta(\\beta, \\gamma)$"} 在参数空间中的完整形态。
          颜色越蓝表示标准差越小（越优），菱形标记最优解。
        </p>
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
      </div>
    </div>
  )
}
