import type { ReactNode } from 'react'

export const processPlotFrame = 'aspect-[8/5] min-h-[240px] max-h-[360px] w-full min-w-0'
export const processPlotAxes = {
  margin: { top: 24, right: 24, bottom: 42, left: 8 },
  xAxisHeight: 30,
  yAxisWidth: 80,
}

export function ProcessPlotControls({ children }: { children: ReactNode }) {
  return <div className="flex min-h-[52px] min-w-0 flex-col gap-2">{children}</div>
}
