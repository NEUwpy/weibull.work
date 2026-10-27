/**
 * 通用等高线图组件 - 用于展示目标函数的等高线 + 优化路径
 *
 * 功能：
 * - 等高线图（2D contour）
 * - 优化路径（迭代点连线）
 * - 最优点标记
 *
 * 用途：WMLE、MLE 等基于优化的参数估计方法
 */
"use client"

import React from 'react'
import Plot from 'react-plotly.js'

// 等高线网格数据
export interface ContourGridData {
  x: number[]           // x 轴值数组
  y: number[]           // y 轴值数组
  z: (number | null)[][]  // 目标函数值矩阵 [y_idx][x_idx]
}

// 优化路径点
export interface OptimizationPoint {
  x: number             // x 坐标
  y: number             // y 坐标
  value?: number        // 目标函数值
  iteration?: number    // 迭代次数
}

interface ContourChartProps {
  // 等高线数据
  contourData: ContourGridData

  // 优化路径（可选）
  optimizationPath?: OptimizationPoint[]

  // 最优点（可选）
  optimalPoint?: { x: number; y: number; label?: string }

  // 轴标签
  xLabel?: string
  yLabel?: string
  title?: string

  // 颜色配置
  colorscale?: Array<[number, string]>

  // 尺寸
  height?: number

  // 显示配置
  showColorbar?: boolean
  showPathLabels?: boolean  // 是否在路径点上显示迭代编号
}

// 默认颜色方案：蓝(优) -> 红(差)
const DEFAULT_COLORSCALE: Array<[number, string]> = [
  [0, '#3b82f6'],      // blue - 低值 (优)
  [0.25, '#10b981'],   // emerald
  [0.5, '#fbbf24'],    // amber
  [0.75, '#f97316'],   // orange
  [1, '#ef4444']       // red - 高值 (差)
]

export function ContourChart({
  contourData,
  optimizationPath,
  optimalPoint,
  xLabel = 'x',
  yLabel = 'y',
  title,
  colorscale = DEFAULT_COLORSCALE,
  height = 400,
  showColorbar = true,
  showPathLabels = false
}: ContourChartProps) {
  // 构建 Plotly traces
  const traces: any[] = []

  // 1. 等高线图
  traces.push({
    type: 'contour',
    x: contourData.x,
    y: contourData.y,
    z: contourData.z,
    colorscale: colorscale,
    showscale: showColorbar,
    colorbar: {
      title: { text: '目标函数', side: 'right', font: { size: 11, color: '#64748b' } },
      tickfont: { size: 10, color: '#64748b' },
      thickness: 15,
      len: 0.85
    },
    contours: {
      coloring: 'heatmap',
      showlabels: true,
      labelfont: { size: 9, color: '#374151' }
    },
    hovertemplate: `${xLabel}: %{x:.2f}<br>${yLabel}: %{y:.2f}<br>值: %{z:.4f}<extra></extra>`
  })

  // 2. 优化路径
  if (optimizationPath && optimizationPath.length > 0) {
    // 路径线
    traces.push({
      type: 'scatter',
      mode: 'lines+markers',
      x: optimizationPath.map(p => p.x),
      y: optimizationPath.map(p => p.y),
      line: { color: '#f59e0b', width: 2, dash: 'dash' },
      marker: {
        size: 6,
        color: optimizationPath.map((_, i) => i),
        colorscale: [[0, '#fcd34d'], [1, '#f59e0b']],
        showscale: false
      },
      name: '优化路径',
      hovertemplate: `迭代: %{text}<br>${xLabel}: %{x:.2f}<br>${yLabel}: %{y:.2f}<extra></extra>`,
      text: optimizationPath.map((p, i) => p.iteration ?? i)
    })

    // 路径点标签（可选）
    if (showPathLabels && optimizationPath.length > 1) {
      traces.push({
        type: 'scatter',
        mode: 'text',
        x: optimizationPath.map(p => p.x),
        y: optimizationPath.map(p => p.y),
        text: optimizationPath.map((p, i) => (p.iteration ?? i).toString()),
        textposition: 'top right',
        textfont: { size: 8, color: '#92400e' },
        showlegend: false,
        hoverinfo: 'skip'
      })
    }
  }

  // 3. 最优点标记
  if (optimalPoint) {
    traces.push({
      type: 'scatter',
      mode: 'markers',
      x: [optimalPoint.x],
      y: [optimalPoint.y],
      marker: {
        size: 14,
        color: '#10b981',
        symbol: 'star',
        line: { color: '#ffffff', width: 2 }
      },
      name: optimalPoint.label || '最优解',
      hovertemplate: `<b>${optimalPoint.label || '最优解'}</b><br>${xLabel}: %{x:.3f}<br>${yLabel}: %{y:.3f}<extra></extra>`
    })
  }

  const layout: any = {
    title: title ? {
      text: title,
      font: { size: 14, color: '#1e293b' },
      x: 0.05
    } : undefined,
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(248,250,252,0.5)',
    margin: { l: 60, r: 60, t: title ? 40 : 20, b: 50 },
    xaxis: {
      title: { text: xLabel, font: { size: 12, color: '#64748b' } },
      gridcolor: '#e2e8f0',
      tickfont: { size: 10, color: '#64748b' }
    },
    yaxis: {
      title: { text: yLabel, font: { size: 12, color: '#64748b' } },
      gridcolor: '#e2e8f0',
      tickfont: { size: 10, color: '#64748b' }
    },
    showlegend: !!(optimizationPath || optimalPoint),
    legend: {
      x: 0.02,
      y: 0.98,
      bgcolor: 'rgba(255,255,255,0.8)',
      bordercolor: '#e2e8f0',
      borderwidth: 1,
      font: { size: 10 }
    }
  }

  const config = {
    responsive: true,
    displayModeBar: true,
    displaylogo: false,
    toImageButtonOptions: {
      format: 'png' as const,
      filename: 'contour_chart',
      height: height,
      width: 600,
      scale: 1
    }
  }

  return (
    <div style={{ height, width: '100%' }}>
      <Plot
        data={traces}
        layout={layout}
        config={config}
        style={{ width: '100%', height: '100%' }}
        useResizeHandler={true}
      />
    </div>
  )
}

export default ContourChart
