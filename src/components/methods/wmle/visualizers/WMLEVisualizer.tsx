"use client"

import { CalculationProcessViewer } from '@/components/shared/charts/CalculationProcessViewer'
import { embeddedCalculationTrace } from '@/lib/calculation-trace'
import type { DataSource } from '@/lib/weibull'

interface Props {
  traceData: unknown
  calculation?: unknown
  dataSources?: DataSource[]
  data?: number[]
  onSurfaceLoad?: (surfaceData: any) => void
}

export default function WMLEVisualizer({ traceData, calculation }: Props) {
  return <CalculationProcessViewer calculation={calculation ?? embeddedCalculationTrace(traceData)} methodId="wmle" />
}