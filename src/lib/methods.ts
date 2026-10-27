import methodsData from '@/data/methods.json'

export type MethodNode = {
  id: string
  name: string
  shortName: string
  description: string
  formula: string
  slug?: string
  hasDetail?: boolean
  children?: MethodNode[]
}

export const INITIAL_METHOD_TREE: MethodNode[] = methodsData as MethodNode[]

// Flatten method tree to create ID -> Method mapping
const methodMap: Record<string, { name: string, shortName: string }> = {}

function buildMethodMap(nodes: MethodNode[]) {
  nodes.forEach(node => {
    if (node.children && node.children.length > 0) {
      // This is a category, process its children
      node.children.forEach(child => {
        methodMap[child.id] = {
          name: child.name,
          shortName: child.shortName
        }
      })
    }
  })
}

buildMethodMap(INITIAL_METHOD_TREE)

// Get method info by ID
export function getMethodInfo(methodId: string | undefined): { name: string, short: string } {
  if (!methodId) {
    return { name: '未选择', short: 'N/A' }
  }
  const info = methodMap[methodId]
  if (info) {
    const result = { name: info.name, short: info.shortName }
    // Removed verbose logging to prevent blocking
    return result
  }
  // Fallback to showing ID
  console.warn('[getMethodInfo] methodId not found:', methodId)
  return { name: methodId.toUpperCase(), short: methodId.toUpperCase() }
}