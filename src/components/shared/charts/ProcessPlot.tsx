import type { ReactNode } from 'react'
import type { LabelProps } from 'recharts'

export const processPlotFrame = 'aspect-[8/5] min-h-[240px] max-h-[360px] w-full min-w-0'
export const processPlotAxes = {
  margin: { top: 24, right: 24, bottom: 42, left: 8 },
  xAxisHeight: 30,
  yAxisWidth: 80,
}

export function ProcessPlotControls({ children }: { children: ReactNode }) {
  return <div className="flex min-h-[52px] min-w-0 flex-col gap-2">{children}</div>
}

export function ProcessYAxisLabel({ viewBox, value }: LabelProps) {
  if (!viewBox || !('height' in viewBox)) return null
  const x = (viewBox.x ?? 0) + 8
  const y = (viewBox.y ?? 0) + (viewBox.height ?? 0) / 2
  return <text className="recharts-label" data-process-y-label x={x} y={y}
    textAnchor="middle" dominantBaseline="central" transform={`rotate(-90, ${x}, ${y})`}
    fontSize={14} fill="#64748b">{value}</text>
}
