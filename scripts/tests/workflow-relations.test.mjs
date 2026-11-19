import test from 'node:test'
import assert from 'node:assert/strict'
import { loadMethodFlow } from '../../src/lib/server/method-flow.mjs'
import { loadServerModule } from './helpers/load-server-module.mjs'

const { indexWorkflow, portSourceGroups, traceWorkflow } = loadServerModule('src/lib/workflow-relations.ts')

test('every existing dependency has exactly one short line or source reference', () => {
  let lines = 0, references = 0
  for (const id of ['mdm', 'mle', 'wmle', 'lse', 'lre', 'mm', 'mmle']) {
    const diagram = loadMethodFlow(id).workflow
    const graph = indexWorkflow(diagram)
    assert.equal(graph.relations.length, diagram.connections.length)
    for (const relation of graph.relations) {
      assert.ok(graph.nodes.has(relation.from) && graph.nodes.has(relation.to))
      if (relation.presentation === 'line') {
        assert.equal(relation.targetStep, relation.sourceStep + 1)
        assert.ok(!relation.dashed)
        lines++
      } else references++
    }
  }
  assert.equal(lines, 30)
  assert.equal(references, 28)
})

test('MMLE reused samples retain their exact source and recipients without cross-stage wires', () => {
  const graph = indexWorkflow(loadMethodFlow('mmle').workflow)
  const reuse = graph.relations.find(relation => relation.sourceStep === 2 && relation.targetStep === 4)
  assert.equal(reuse.presentation, 'reference')
  assert.equal(traceWorkflow(graph.relations, { relation: reuse.key })[0], reuse)
  const recipients = traceWorkflow(graph.relations, { port: reuse.from }).map(relation => relation.targetStep)
  assert.equal(Array.from(recipients).join(','), '3,4,5')
  assert.equal(traceWorkflow(graph.relations, null).length, 0)
})

test('independent MM comparison and MDM trial calls keep their real relationships', () => {
  const mm = indexWorkflow(loadMethodFlow('mm').workflow)
  assert.ok(!mm.relations.some(relation => relation.sourceStep === 5 && relation.targetStep === 6))
  assert.equal(mm.relations.find(relation => relation.sourceStep === 4 && relation.targetStep === 6).presentation, 'reference')
  const mdm = indexWorkflow(loadMethodFlow('mdm').workflow)
  const call = mdm.relations.find(relation => relation.sourceStep === 3 && relation.targetStep === 2)
  assert.equal(call.presentation, 'reference')
  assert.ok(call.dashed)
  assert.equal(mdm.nodes.get(call.from).kind, 'step')
  assert.equal(mdm.relations.find(relation => relation.sourceStep === 4 && relation.targetStep === 5).presentation, 'line')
})

test('merged input quantities retain their own sources, including quantities omitted from the flow summary', () => {
  function groups(id, target, refs) {
    const flow = loadMethodFlow(id), graph = indexWorkflow(flow.workflow)
    const port = Array.from(graph.nodes.values()).find(node => node.kind === 'port' && node.direction === 'input'
      && flow.workflow.targets[node.target] === target && node.refs.join(',') === refs)
    return Array.from(portSourceGroups(port, graph.relations, flow.steps), group => ({
      ids: Array.from(group.variables, variable => variable.id).join(','),
      source: group.references[0]?.sourceStep,
    }))
  }
  assert.deepEqual(groups('mmle', 5, 'gamma_hat,beta_hat'), [{ ids: 'gamma_hat', source: 2 }, { ids: 'beta_hat', source: 3 }])
  assert.deepEqual(groups('mdm', 5, 'gamma_hat,beta_hat'), [{ ids: 'gamma_hat', source: 3 }, { ids: 'beta_hat', source: undefined }])
  assert.deepEqual(groups('lre', 4, 'ordered,scores'), [{ ids: 'ordered', source: 1 }, { ids: 'scores', source: 2 }])
  assert.deepEqual(groups('mle', 5, 'ordered,n'), [{ ids: 'ordered,n', source: 1 }])
  assert.deepEqual(groups('mm', 4, 'minimum'), [{ ids: 'minimum', source: 1 }])
})
