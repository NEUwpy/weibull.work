"use client"

import { createContext, useContext } from 'react'
import type { MethodFlow } from '@/lib/method-flow'
import type { CalculationChart } from '@/lib/calculation-trace'

export const ProcessDefinitionContext = createContext<MethodFlow | null>(null)

export function useProcessAxisLabel(chartId: string, axis: 'x' | 'y', fallback: string) {
  const definition = useContext(ProcessDefinitionContext)
  const id = definition?.chartBindings?.[chartId]?.[axis]
  return id ? definition?.variables?.[id]?.axisLabel ?? fallback : fallback
}

export function bindProcessChart(chart: CalculationChart, definition: MethodFlow | null) {
  const binding = definition?.chartBindings?.[chart.id]
  if (!binding) return chart
  return { ...chart,
    x: { ...chart.x, label: definition!.variables[binding.x]?.axisLabel ?? chart.x.label },
    y: { ...chart.y, label: definition!.variables[binding.y]?.axisLabel ?? chart.y.label },
  }
}

export function useProcessChart(chart: CalculationChart) {
  const definition = useContext(ProcessDefinitionContext)
  return { chart: bindProcessChart(chart, definition), binding: definition?.chartBindings?.[chart.id] }
}
