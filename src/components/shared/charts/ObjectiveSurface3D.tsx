/**
 * 3D 目标函数曲面组件 - 用于展示参数优化过程
 *
 * 功能：
 * - 3D 曲面图（目标函数在参数空间的形态）
 * - 网格格点（计算的真实点）
 * - 优化路径（迭代点在曲面上的轨迹）
 * - 最优点标记（谷底位置）
 *
 * 用途：WMLE、MLE 等基于优化的参数估计方法
 */
"use client"

import React, { useMemo, useState } from 'react'
import Plot from 'react-plotly.js'

// 曲面网格数据
export interface SurfaceGridData {
  betas: number[]           // x 轴：形状参数 β
  gammas: number[]          // y 轴：位置参数 γ
  values: (number | null)[][]  // z 轴：目标函数值矩阵 [gamma_idx][beta_idx]
}

// 优化路径点
export interface OptimizationStep {
  beta: number              // 形状参数 β
  gamma: number             // 位置参数 γ
  objValue: number          // 目标函数值
  iteration: number         // 迭代次数
}

interface ObjectiveSurface3DProps {
  // 曲面数据
  surfaceData: SurfaceGridData

  // 优化路径（可选）
  optimizationPath?: OptimizationStep[]

  // 最优点（可选）
  optimalPoint?: { beta: number; gamma: number; objValue?: number }

  // 显示配置
  showOptimalMarker?: boolean // 是否显示最优点标记
  height?: number

  // 对数尺度（目标函数值可能跨越多个数量级）
  logScale?: boolean
}

// 默认颜色方案：蓝(优/谷底) -> 红(差/峰值)
const SURFACE_COLORSCALE: Array<[number, string]> = [
  [0, '#3b82f6'],      // blue - 低值 (优/谷底)
  [0.2, '#10b981'],    // emerald
  [0.4, '#22c55e'],    // green
  [0.6, '#fbbf24'],    // amber
  [0.8, '#f97316'],    // orange
  [1, '#ef4444']       // red - 高值 (差/峰值)
]

export function ObjectiveSurface3D({
  surfaceData,
  optimizationPath,
  optimalPoint,
  showOptimalMarker = true,
  height = 450,
  logScale = true
}: ObjectiveSurface3DProps) {

  // 显示开关状态
  const [showGridPoints, setShowGridPoints] = useState(false)
  const [showContours, setShowContours] = useState(true)
  const [showPath, setShowPath] = useState(true)

  // 过滤有效值，计算统计信息
  const stats = useMemo(() => {
    const validValues = surfaceData.values.flat().filter((v): v is number => v !== null && v > 0)
    if (validValues.length === 0) return { min: 0.001, max: 1 }
    return {
      min: Math.min(...validValues),
      max: Math.max(...validValues)
    }
  }, [surfaceData.values])

  // 构建 Plotly traces
  const traces: any[] = useMemo(() => {
    const result: any[] = []

    // 1. 3D 曲面
    result.push({
      type: 'surface',
      x: surfaceData.betas,
      y: surfaceData.gammas,
      z: surfaceData.values,
      colorscale: SURFACE_COLORSCALE,
      colorbar: {
        title: { text: logScale ? 'log(O)' : 'O(β,γ)', side: 'right', font: { size: 11, color: '#64748b' } },
        tickfont: { size: 10, color: '#64748b' },
        thickness: 15,
        len: 0.85
      },
      contours: {
        x: { show: false },
        y: { show: false },
        z: {
          show: showContours,
          usecolormap: true,
          highlightcolor: '#ffffff',
          project: { z: showContours },
          width: 2
        }
      },
      showscale: true,
      hovertemplate:
        'β: %{x:.2f}<br>' +
        'γ: %{y:.1f}<br>' +
        'O: %{z:.4f}<extra></extra>',
      opacity: 0.9
    })

    // 2. 网格格点（计算的真实点）
    if (showGridPoints) {
      const gridBetas: number[] = []
      const gridGammas: number[] = []
      const gridValues: number[] = []

      surfaceData.gammas.forEach((gamma, gi) => {
        surfaceData.betas.forEach((beta, bi) => {
          const val = surfaceData.values[gi]?.[bi]
          if (val !== null && val !== undefined) {
            gridBetas.push(beta)
            gridGammas.push(gamma)
            gridValues.push(val > 0 ? val : stats.min)
          }
        })
      })

      result.push({
        type: 'scatter3d',
        mode: 'markers',
        x: gridBetas,
        y: gridGammas,
        z: gridValues,
        marker: {
          size: 3,
          color: '#6366f1',
          opacity: 0.6
        },
        name: '网格点',
        hovertemplate: 'β: %{x:.2f}<br>γ: %{y:.1f}<br>O: %{z:.4f}<extra></extra>',
        showlegend: true
      })
    }

    // 3. 优化路径（3D 散点 + 连线）
    if (showPath && optimizationPath && optimizationPath.length > 0) {
      const pathBeta = optimizationPath.map(p => p.beta)
      const pathGamma = optimizationPath.map(p => p.gamma)
      const pathObj = optimizationPath.map(p => p.objValue > 0 ? p.objValue : stats.min)

      // 路径线
      result.push({
        type: 'scatter3d',
        mode: 'lines',
        x: pathBeta,
        y: pathGamma,
        z: pathObj,
        line: { color: '#f59e0b', width: 4, dash: 'dash' },
        name: '优化路径',
        hovertemplate: '迭代: %{text}<br>β: %{x:.2f}<br>γ: %{y:.1f}<extra></extra>',
        text: optimizationPath.map(p => p.iteration),
        showlegend: true
      })

      // 路径点
      result.push({
        type: 'scatter3d',
        mode: 'markers',
        x: pathBeta,
        y: pathGamma,
        z: pathObj,
        marker: {
          size: 5,
          color: optimizationPath.map((_, i) => i),
          colorscale: [[0, '#fcd34d'], [1, '#f59e0b']],
          showscale: false
        },
        name: '迭代点',
        hovertemplate: '迭代 %{text}<br>β: %{x:.2f}<br>γ: %{y:.1f}<br>O: %{z:.4f}<extra></extra>',
        text: optimizationPath.map(p => p.iteration),
        showlegend: false
      })
    }

    // 4. 最优点标记
    if (showOptimalMarker && optimalPoint) {
      const optObj = optimalPoint.objValue ?? stats.min
      result.push({
        type: 'scatter3d',
        mode: 'markers',
        x: [optimalPoint.beta],
        y: [optimalPoint.gamma],
        z: [optObj > 0 ? optObj : stats.min],
        marker: {
          size: 12,
          color: '#10b981',
          symbol: 'diamond',
          line: { color: '#ffffff', width: 2 }
        },
        name: '最优解',
        hovertemplate:
          '<b>最优解</b><br>' +
          'β*: %{x:.3f}<br>' +
          'γ*: %{y:.2f}<br>' +
          'O*: %{z:.6f}<extra></extra>'
      })
    }

    return result
  }, [surfaceData, optimizationPath, optimalPoint, showPath, showOptimalMarker, showContours, showGridPoints, stats, logScale])

  const layout: any = {
    title: {
      text: '目标函数 O(β, γ) 三维曲面',
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
        title: { text: logScale ? 'log(O)' : '目标函数 O', font: { size: 12, color: '#64748b' } },
        type: logScale ? 'log' : 'linear',
        gridcolor: '#e2e8f0',
        showgrid: true,
        tickfont: { size: 10, color: '#64748b' },
        backgroundcolor: 'rgba(248, 250, 252, 0.5)'
      },
      camera: {
        eye: { x: 1.5, y: 1.5, z: 1.2 }
      },
      aspectmode: 'manual',
      aspectratio: { x: 1, y: 1.2, z: 0.8 }
    },
    showlegend: true,
    legend: {
      x: 0.02,
      y: 0.98,
      bgcolor: 'rgba(255,255,255,0.8)',
      bordercolor: '#e2e8f0',
      borderwidth: 1,
      font: { size: 11 }
    }
  }

  const config = {
    responsive: true,
    displayModeBar: true,
    displaylogo: false,
    toImageButtonOptions: {
      format: 'png' as const,
      filename: 'objective_surface_3d',
      height: height,
      width: 700,
      scale: 1
    }
  }

  return (
    <div>
      {/* 开关控件 */}
      <div className="flex items-center gap-6 mb-4 flex-wrap">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={showContours}
            onChange={(e) => setShowContours(e.target.checked)}
            className="w-4 h-4 rounded border-slate-300 text-purple-600 focus:ring-purple-500"
          />
          <span className="text-sm text-slate-700">显示等高线</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={showGridPoints}
            onChange={(e) => setShowGridPoints(e.target.checked)}
            className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
          />
          <span className="text-sm text-slate-700">显示网格点 ({surfaceData.betas.length * surfaceData.gammas.length} 个)</span>
        </label>
        {optimizationPath && optimizationPath.length > 0 && (
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={showPath}
              onChange={(e) => setShowPath(e.target.checked)}
              className="w-4 h-4 rounded border-slate-300 text-amber-600 focus:ring-amber-500"
            />
            <span className="text-sm text-slate-700">显示优化路径 ({optimizationPath.length} 步)</span>
          </label>
        )}
      </div>

      {/* 3D 图表 */}
      <div style={{ height, width: '100%' }}>
        <Plot
          data={traces}
          layout={layout}
          config={config}
          style={{ width: '100%', height: '100%' }}
          useResizeHandler={true}
        />
      </div>

      {/* 操作提示 */}
      <div className="mt-4 flex items-center gap-4 text-xs text-slate-500 bg-slate-50 rounded-lg p-3 border border-slate-200 flex-wrap">
        <div className="flex items-center gap-1.5">
          <span className="w-5 h-5 rounded bg-slate-200 flex items-center justify-center">🖱️</span>
          <span>拖拽旋转</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-5 h-5 rounded bg-slate-200 flex items-center justify-center">🔍</span>
          <span>滚轮缩放</span>
        </div>
        {showGridPoints && (
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-indigo-500"></span>
            <span>紫色点 = 计算的网格点</span>
          </div>
        )}
        {showPath && optimizationPath && optimizationPath.length > 0 && (
          <div className="flex items-center gap-1.5">
            <div className="w-4 h-0.5 bg-amber-500 rounded" style={{ borderStyle: 'dashed' }}></div>
            <span>橙色线 = 优化路径</span>
          </div>
        )}
        {showOptimalMarker && optimalPoint && (
          <div className="flex items-center gap-1.5">
            <span className="text-emerald-500 text-base">◆</span>
            <span>绿色菱形 = 最优解</span>
          </div>
        )}
      </div>
    </div>
  )
}

export default ObjectiveSurface3D
