"use client"

import { CalculationProcessViewer } from '@/components/shared/charts/CalculationProcessViewer'
import { embeddedCalculationTrace } from '@/lib/calculation-trace'

interface MDMIterationViewerProps {
  traceData: unknown
  calculation?: unknown
  isLoading?: boolean
  onLoadData: () => void
  hasData?: boolean
}

/** Compatibility entry: sampled function slices are never replayed as iterations. */
export default function MDMIterationViewer({ traceData, calculation }: MDMIterationViewerProps) {
  return <CalculationProcessViewer calculation={calculation ?? embeddedCalculationTrace(traceData)} methodId="mdm" />
}