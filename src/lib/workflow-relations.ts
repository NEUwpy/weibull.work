import type { FlowDiagram, FlowDiagramConnection, FlowDiagramItem, FlowStep, FlowVariable } from './method-flow'

type FlowNode = Exclude<FlowDiagramItem, { kind: 'group' }>
export interface WorkflowRelation extends FlowDiagramConnection {
  key: string
  sourceStep: number
  targetStep: number
  presentation: 'line' | 'reference'
}
export type WorkflowSelection = { port: string } | { relation: string } | null

/** Project the existing dependency graph; references never create a second graph. */
export function indexWorkflow(diagram: FlowDiagram) {
  const nodes = new Map<string, FlowNode>()
  function visit(items: FlowDiagramItem[]) {
    for (const item of items) {
      if (item.kind === 'group') visit(item.children)
      else nodes.set(item.anchor, item)
    }
  }
  visit(diagram.items)
  const owner = (node: FlowNode) => node.kind === 'step' ? node.step : diagram.targets[node.target]!
  const relations: WorkflowRelation[] = diagram.connections.map(connection => {
    const sourceStep = owner(nodes.get(connection.from)!)
    const targetStep = owner(nodes.get(connection.to)!)
    return { ...connection, key: connection.from + '→' + connection.to, sourceStep, targetStep,
      presentation: targetStep === sourceStep + 1 && !connection.dashed ? 'line' : 'reference' }
  })
  return { nodes, relations }
}

export function traceWorkflow(relations: WorkflowRelation[], selection: WorkflowSelection) {
  if (!selection) return []
  return relations.filter(relation => 'port' in selection
    ? relation.from === selection.port || relation.to === selection.port
    : relation.key === selection.relation)
}

export interface PortSourceGroup { variables: FlowVariable[]; references: WorkflowRelation[] }

/** Associate each displayed quantity with its existing incoming dependency. */
export function portSourceGroups(port: Extract<FlowNode, { kind: 'port' }>, relations: WorkflowRelation[], steps: FlowStep[]) {
  const incoming = relations.filter(relation => relation.to === port.anchor)
  const variables = new Map(steps.flatMap(step => [...step.inputs, ...step.outputs, ...(step.extraInputs ?? []), ...(step.extraOutputs ?? [])])
    .map(variable => [variable.id, variable]))
  const groups: PortSourceGroup[] = []
  for (const id of port.refs ?? []) {
    const variable = variables.get(id)
    if (!variable) continue
    const source = incoming.find(relation => {
      const step = steps.find(step => step.id === relation.sourceStep)!
      return [...step.outputs, ...(step.extraOutputs ?? [])].some(output => output.id === id)
    }) ?? (incoming.length === 1 ? incoming[0] : undefined)
    const reference = source?.presentation === 'reference' ? source : undefined
    let group = groups.find(group => group.references[0]?.key === reference?.key)
    if (!group) { group = { variables: [], references: reference ? [reference] : [] }; groups.push(group) }
    group.variables.push(variable)
  }
  return groups.length ? groups : [{ variables: [], references: incoming.filter(relation => relation.presentation === 'reference') }]
}
