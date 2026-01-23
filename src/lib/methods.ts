import methodsData from '@/data/methods.json'

export type MethodNode = {
  id: string
  name: string
  shortName: string
  description: string
  formula: string
  referenceSlug?: string
  children?: MethodNode[]
}

export const INITIAL_METHOD_TREE: MethodNode[] = methodsData as MethodNode[]