"use client"

import { CalculationProcessViewer } from '@/components/shared/charts/CalculationProcessViewer'
import { embeddedCalculationTrace } from '@/lib/calculation-trace'
import type { DataSource } from '@/lib/weibull'

interface MDMVisualizerProps {
  traceData: unknown
  calculation?: unknown
  methodId?: string
  dataSources?: DataSource[]
  mdmOffset: number
  onMdmOffsetChange: (offset: number) => void
  offsetStale?: boolean
  isOffsetUpdating?: boolean
}

export default function MDMVisualizer({ traceData, calculation, offsetStale, isOffsetUpdating }: MDMVisualizerProps) {
  return <CalculationProcessViewer calculation={calculation ?? embeddedCalculationTrace(traceData)}
    methodId="mdm" stale={offsetStale} isUpdating={isOffsetUpdating} />
}