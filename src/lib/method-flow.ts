export interface FlowVariable { symbol: string; meaning: string; code: string }
export interface FlowSource { path: string; sha256: string; lines: string[] }
export interface FlowReference { file: string; symbol?: string; label: string; start: number; end: number }
export interface FlowStep {
  id: number; name: string; description: string; basis: string; notes: string
  formula: { expression: string; equations?: string[]; variants?: Record<string, string>; variantEquations?: Record<string, string[]>; symbols: { symbol: string; meaning: string }[]; explanation: string }
  inputs: FlowVariable[]; outputs: FlowVariable[]; sources: FlowReference[]
  primarySource?: number
  depth: number; number: string; context?: string; kind: 'step' | 'call' | 'loop' | 'condition' | 'return'
  isLoop?: boolean; loopCount?: string
}
export type FlowChartTarget = 'samples' | 'trial' | 'location' | 'shape' | 'scale' | 'result'
type FlowNodeText = Partial<Record<'default' | 'ready' | 'zero' | 'extrapolated' | 'failed', string[]>>
export type FlowDiagramItem =
  | { kind: 'group'; layout: string; title?: string; sideLabel?: string; children: FlowDiagramItem[] }
  | { kind: 'step'; anchor: string; step: number; target?: FlowChartTarget; text?: FlowNodeText }
  | { kind: 'port'; anchor: string; target: FlowChartTarget; direction: 'input' | 'output'; label: string; updatingLabel?: string; text?: FlowNodeText }
export interface FlowDiagramConnection {
  from: string; to: string; route?: 'loop' | 'left' | 'right-upper' | 'right-lower'; dashed?: boolean
  label?: string
}
export interface FlowDiagram {
  title: string; description: string
  targets: Record<FlowChartTarget, number>
  legacySourceSteps?: number[]
  items: FlowDiagramItem[]; connections: FlowDiagramConnection[]
}
export interface MethodFlow {
  schemaVersion: 2; methodId: string; methodName: string; description: string; implementation: string
  steps: FlowStep[]; sources: FlowSource[]
  artifacts: { path: string; sha256: string; bytes: number }[]
  workflow?: FlowDiagram
}
