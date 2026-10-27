import generatedData from '@/data/method-status.generated.json'

export type AtomicStatus = 'todo' | 'in_progress' | 'done' | 'blocked' | 'not_applicable'

export type MethodLevel =
  | 'not_started'
  | 'layer1_in_progress'
  | 'layer1_complete'
  | 'layer2_complete'
  | 'closed_loop'

interface GeneratedMethod {
  id: string
  name: string
  family: string
  shared_core: string | null
  classification_source: string
  level: MethodLevel
  calculatorEnabled: boolean
  missingLayer1: string[]
  paper: {
    status: AtomicStatus
    title?: string
    publication?: string
    year?: number
    stable_id?: string
    evidence: string[]
    reason?: string
    note?: string
  }
  layer1: {
    backend: StatusItem
    tests: StatusItem
    calculator: StatusItem
    theory: StatusItem
    process: StatusItem
  }
  layer2: {
    calculation: StatusItem
    analysis: StatusItem
  }
  layer3: {
    applicability: StatusItem
    verification: StatusItem
  }
}

interface StatusItem {
  status: AtomicStatus
  evidence: string[]
  reason?: string
  note?: string
  exception_approved?: boolean
}

export interface MethodCapability {
  id: string
  name: string
  family: string
  shared_core: string | null
  classification_source: string
  level: MethodLevel
  calculatorEnabled: boolean
  missingLayer1: string[]
  paper: GeneratedMethod['paper']
  layer1: GeneratedMethod['layer1']
  layer2: GeneratedMethod['layer2']
  layer3: GeneratedMethod['layer3']
}

function assertIsGeneratedData(data: unknown): asserts data is { methods: GeneratedMethod[] } {
  if (
    !data ||
    typeof data !== 'object' ||
    !('methods' in data) ||
    !Array.isArray((data as Record<string, unknown>).methods)
  ) {
    throw new Error('method-status: generated JSON has unexpected shape')
  }
}

const data: GeneratedMethod[] = (() => {
  assertIsGeneratedData(generatedData)
  return generatedData.methods
})()

const capabilities: MethodCapability[] = data

const byId = new Map<string, MethodCapability>(
  capabilities.map((cap) => [cap.id, cap]),
)

export function getMethodCapability(
  methodId: string | undefined,
): MethodCapability | undefined {
  if (!methodId) return undefined
  return byId.get(methodId)
}

export function isCalculatorEnabled(methodId: string | undefined): boolean {
  return getMethodCapability(methodId)?.calculatorEnabled ?? false
}

export function getEnabledMethodIds(): string[] {
  return capabilities.filter((c) => c.calculatorEnabled).map((c) => c.id)
}

export function getMethodCapabilities(): MethodCapability[] {
  return capabilities
}
