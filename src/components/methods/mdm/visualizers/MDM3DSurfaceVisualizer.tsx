"use client"

import Plot from 'react-plotly.js'

interface TraceData {
  sigma_beta_gamma?: { gamma: number; betas: number[]; sigmas: number[] }[]
  [key: string]: unknown
}

interface MDM3DSurfaceVisualizerProps {
  traceData: TraceData
  isLoading?: boolean
  loadingProgress?: number
  onLoadData?: () => void
  hasLoadedData?: boolean
}

/** Supplementary evaluated grid only. No surrogate heights or assumed optimum. */
export default function MDM3DSurfaceVisualizer({ traceData }: MDM3DSurfaceVisualizerProps) {
  const rows = traceData.sigma_beta_gamma
  const first = rows?.[0]
  const validGrid = first && first.betas.length > 1 && rows!.length > 1
    && rows!.every(row => Number.isFinite(row.gamma)
      && row.betas.length === first.betas.length && row.sigmas.length === first.betas.length
      && row.betas.every((beta, index) => Number.isFinite(beta) && beta === first.betas[index])
      && row.sigmas.every(Number.isFinite))

  if (!validGrid) {
    return <p role="status" className="rounded-xl bg-slate-100/70 px-4 py-4 text-base text-slate-600">这份记录没有完整的函数求值网格，暂不显示三维曲面。</p>
  }

  return <section className="min-w-0 rounded-2xl border border-slate-200/80 bg-white/70 p-4">
    <h3 className="text-lg font-semibold text-slate-800">离散度函数的补充采样</h3>
    <p className="mt-1 text-sm leading-relaxed text-slate-500">网格来自后端函数求值；曲面连接用于观察函数形态，不代表求解轨迹，最终选择见本次计算的判据图。</p>
    <Plot data={[{
      type: 'surface', x: first!.betas, y: rows!.map(row => row.gamma), z: rows!.map(row => row.sigmas),
      colorscale: 'Viridis', hovertemplate: 'β=%{x}<br>γ=%{y}<br>σ=%{z}<extra></extra>',
      colorbar: { title: { text: 'σ' }, tickfont: { size: 14 } },
    } as any]} layout={{
      autosize: true, height: 400, margin: { l: 0, r: 0, t: 10, b: 0 },
      scene: {
        xaxis: { title: { text: '形状参数 β' }, tickfont: { size: 14 } },
        yaxis: { title: { text: '位置参数 γ' }, tickfont: { size: 14 } },
        zaxis: { title: { text: '离散度 σ' }, tickfont: { size: 14 } },
      },
    }} config={{ responsive: true, displaylogo: false }} style={{ width: '100%', height: 400 }} useResizeHandler />
  </section>
}