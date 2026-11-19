export interface FlowVariable { id: string; name: string; symbol: string; meaning: string; code: string; axisLabel?: string }
export interface FlowSource { path: string; sha256: string; lines: string[] }
export interface FlowReference { file: string; symbol?: string; label: string; start: number; end: number }
export interface FlowStep {
  id: number; name: string; description: string; basis: string; notes: string
  formula: { equations: string[]; variantEquations?: Record<string, string[]>; symbols: { symbol: string; meaning: string }[]; explanation: string }
  inputs: FlowVariable[]; outputs: FlowVariable[]; sources: FlowReference[]
  extraInputs?: FlowVariable[]; extraOutputs?: FlowVariable[]
  primarySource?: number
}
export type FlowChartTarget = 'samples' | 'trial' | 'location' | 'shape' | 'scale' | 'result'
  | 'transformation' | 'regression' | 'moments' | 'estimate' | 'adjustment' | 'comparison'
type FlowNodeSymbol = string | Partial<Record<'default' | 'ready' | 'zero' | 'extrapolated' | 'failed', string>>
export type FlowDiagramItem =
  | { kind: 'group'; layout: string; title?: string; children: FlowDiagramItem[] }
  | { kind: 'step'; anchor: string; step: number; target?: FlowChartTarget; label?: string; symbol?: FlowNodeSymbol }
  | { kind: 'port'; anchor: string; target: FlowChartTarget; direction: 'input' | 'output'; name?: string; label: string; external?: boolean; group: string; refs: string[] }
export interface FlowDiagramConnection {
  from: string; to: string; dashed?: boolean
  label?: string
}
export interface FlowDiagram {
  title: string; description: string
  targets: Partial<Record<FlowChartTarget, number>>
  items: FlowDiagramItem[]; connections: FlowDiagramConnection[]
}
export interface MethodFlow {
  schemaVersion: 2; methodId: string; methodName: string; description: string; implementation: string
  steps: FlowStep[]; sources: FlowSource[]
  artifacts: { path: string; sha256: string; bytes: number }[]
  workflow: FlowDiagram
  variables: Record<string, FlowVariable>
  chartBindings: Record<string, { x: string; y: string }>
}
