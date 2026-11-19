"use client"

import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { MathText } from '@/components/shared/MathText'
import type { FlowDiagram, FlowDiagramItem, FlowStep } from '@/lib/method-flow'
import { indexWorkflow, portSourceGroups, traceWorkflow, type PortSourceGroup, type WorkflowRelation, type WorkflowSelection } from '@/lib/workflow-relations'
import styles from './CalculationWorkspace.module.css'

type Wire = { from: string; to: string; d: string; label?: { text: string; x: number; y: number } }

function ProgramBlock({ anchor, step, name, fullName, active, related, onClick, children }: {
  anchor: string; step: number; name: string; fullName: string; active?: boolean; related?: boolean; onClick: () => void; children?: ReactNode
}) {
  return <button type="button" data-flow-anchor={anchor} data-flow-kind="process" data-flow-step={step} className={styles.block} onClick={onClick}
    aria-current={active ? 'step' : undefined} aria-label={step + ' ' + fullName} data-flow-related={related || undefined}>
    <span className={styles.stepText}>
      <span className={styles.stepTitle}><span className={styles.stepNumber}>{step}</span><strong>{name}</strong></span>
      {children && <span className={styles.rule}>{children}</span>}
    </span>
  </button>
}

function Port({ id, direction, name, label, refs, related, selected, groups, tracedRelations, stepNames, onReference, onClick }: {
  id: string; direction: 'input' | 'output'; name?: string; label: string; refs: string[]
  related: boolean; selected: boolean; groups: PortSourceGroup[]; tracedRelations: Set<string>; stepNames: Map<number, string>
  onReference: (relation: WorkflowRelation) => void; onClick: () => void
}) {
  return <div data-flow-anchor={id} data-flow-kind="data" data-flow-direction={direction} data-variable-refs={refs?.join(' ')}
      data-flow-related={related || undefined} data-flow-selected={selected || undefined} onClick={onClick} className={styles.port}
      role="group" aria-label={(direction === 'input' ? '输入' : '输出') + ' ' + (name ?? '')} tabIndex={-1}>
    <svg viewBox="0 0 120 60" preserveAspectRatio="none" aria-hidden="true">
      <path d={direction === 'input' ? 'M1 1H119V49L109 59H11L1 49Z' : 'M11 1H109L119 11V59H1V11Z'} vectorEffect="non-scaling-stroke" />
    </svg>
    <button type="button" className={styles.portSelect} aria-pressed={selected}>
      <span className={styles.portKind}>{direction === 'input' ? '输入' : '输出'}</span>
      {name && <span className={styles.portName}>{name}</span>}
    </button>
    <div className={styles.portValues}>
      {groups.map((group, index) => <div key={index} className={styles.portValueRow} data-source-variables={group.variables.map(variable => variable.id).join(' ')}>
        <span className={styles.portQuantity}>
        {group.references.map(reference => <span key={reference.key} className={styles.sourcePhrase}><button type="button" className={styles.sourceRef}
        data-flow-reference={reference.key} data-source-step={reference.sourceStep} data-target-step={reference.targetStep}
        aria-pressed={tracedRelations.has(reference.key)}
        data-call={reference.dashed || undefined} title={(reference.dashed ? '试算调用：' : '来自') + '第' + reference.sourceStep + '步 · ' + stepNames.get(reference.sourceStep)}
        aria-label={(name ?? '输入') + '，' + (reference.dashed ? '试算调用来自' : '来自') + '第' + reference.sourceStep + '步：' + stepNames.get(reference.sourceStep)}
        onClick={event => { event.stopPropagation(); onReference(reference) }}>{reference.sourceStep}</button><span>中的</span></span>)}
        <MathText math={groups.length === 1 ? label : group.variables.map(variable => variable.symbol).join(',')} />
        </span>
      </div>)}
    </div>
  </div>
}

export function MethodWorkflow({ methodId, diagram, steps, ready, branch = 'ready', updating = false, activeProgramStep, onSelect }: {
  methodId: string; diagram: FlowDiagram; steps: FlowStep[]
  ready: boolean; branch?: 'ready' | 'zero' | 'extrapolated' | 'failed'; updating?: boolean
  activeProgramStep?: number; onSelect: (step: number) => void
}) {
  const canvas = useRef<HTMLDivElement>(null)
  const navigation = useRef<HTMLElement>(null)
  const pendingFocus = useRef<string | null>(null)
  const marker = `flow-arrow-${useId().replace(/:/g, '')}`
  const [wires, setWires] = useState<{ width: number; height: number; paths: Wire[] }>({ width: 280, height: 700, paths: [] })
  const [selection, setSelection] = useState<WorkflowSelection>(null)
  const [locating, setLocating] = useState(0)
  const graph = useMemo(() => indexWorkflow(diagram), [diagram])
  const trace = traceWorkflow(graph.relations, selection)
  const tracedRelations = new Set(trace.map(relation => relation.key))
  const related = new Set(trace.flatMap(relation => [relation.from, relation.to]))
  const names = new Map(steps.map(step => [step.id, step.name]))

  useEffect(() => { setSelection(null) }, [diagram])

  useEffect(() => {
    const pane = navigation.current
    const selected = pane?.querySelector<HTMLElement>('[aria-current="step"]')
    const block = selected?.closest<HTMLElement>('[data-flow-module]') ?? selected
    if (!pane || !block) return
    if (pendingFocus.current) {
      pane.querySelectorAll<HTMLElement>('[data-flow-anchor]').forEach(node => {
        if (node.dataset.flowAnchor === pendingFocus.current) node.focus({ preventScroll: true })
      })
      pendingFocus.current = null
    }
    if (pane.scrollHeight <= pane.clientHeight) return
    const bounds = pane.getBoundingClientRect()
    const item = block.getBoundingClientRect()
    const heading = pane.querySelector<HTMLElement>('[data-flow-heading]')?.offsetHeight ?? 52
    if (item.top < bounds.top + heading + 12) pane.scrollTop += item.top - bounds.top - heading - 12
    else if (item.bottom > bounds.bottom - 16) pane.scrollTop += item.bottom - bounds.bottom + 16
  }, [activeProgramStep, selection, locating])

  useLayoutEffect(() => {
    const element = canvas.current
    if (!element) return
    let mounted = true
    const measure = () => {
      if (!mounted || !element.clientWidth) return
      const rect = element.getBoundingClientRect()
      const nodes = Array.from(element.querySelectorAll<HTMLElement>('[data-flow-anchor]'))
      const anchors = new Map(nodes.map(item => [item.dataset.flowAnchor, item.getBoundingClientRect()]))
      const paths = graph.relations.filter(relation => relation.presentation === 'line').flatMap<Wire>(connection => {
        const source = anchors.get(connection.from), target = anchors.get(connection.to)
        if (!source || !target) return []
        const from = source, to = target
        const endpoints = { from: connection.from, to: connection.to }
        const x1 = (from.left + from.right) / 2 - rect.left, y1 = from.bottom - rect.top
        const x2 = (to.left + to.right) / 2 - rect.left, y2 = to.top - rect.top
        const middle = (y1 + y2) / 2
        return [{
          ...endpoints,
          d: `M${x1} ${y1} V${middle} H${x2} V${y2}`,
          label: connection.label ? { text: connection.label, x: Math.max(x1, x2) + 8, y: middle } : undefined,
        }]
      })
      setWires({ width: rect.width, height: rect.height, paths })
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    element.querySelectorAll('[data-flow-anchor]').forEach(node => observer.observe(node))
    void document.fonts.ready.then(measure)
    return () => { mounted = false; observer.disconnect() }
  }, [graph, branch])

  function locate(step: number, anchor?: string) {
    pendingFocus.current = anchor ?? null
    setLocating(value => value + 1)
    onSelect(step)
  }

  function renderItem(item: FlowDiagramItem, index: number): ReactNode {
    if (item.kind === 'group') {
      if (item.layout === 'module') {
        const body = item.children.find(child => child.kind === 'step')
        const ports = item.children.filter(child => child.kind === 'port')
        return <section key={index} className={styles.module} data-flow-module={body?.kind === 'step' ? body.step : undefined}>
          <div className={styles.portRow}>{ports.filter(port => port.direction === 'input').map(renderItem)}</div>
          {body && renderItem(body, 0)}
          <div className={styles.portRow}>{ports.filter(port => port.direction === 'output').map(renderItem)}</div>
        </section>
      }
      return <div key={index} className={item.layout === 'search' ? styles.search : styles.sequence}>
        {item.title && <p className={styles.groupLabel}>{item.title}</p>}
        {item.children.map(renderItem)}
      </div>
    }

    const step = item.kind === 'step' ? item.step : diagram.targets[item.target]
    if (step === undefined) return null
    const select = () => {
      setSelection(item.kind === 'port' ? { port: item.anchor } : null)
      onSelect(step)
    }
    if (item.kind === 'step') {
      const symbol = typeof item.symbol === 'string' ? item.symbol : item.symbol?.[branch] ?? item.symbol?.default
      return <ProgramBlock key={item.anchor} anchor={item.anchor} step={step} name={item.label ?? names.get(step)!} fullName={names.get(step)!}
        active={activeProgramStep === step} related={related.has(item.anchor)} onClick={select}>{symbol && <MathText math={symbol} />}</ProgramBlock>
    }
    return <Port key={item.anchor} id={item.anchor} direction={item.direction}
      name={item.name} label={item.label} refs={item.refs} related={related.has(item.anchor)}
      selected={!!selection && 'port' in selection && selection.port === item.anchor}
      groups={portSourceGroups(item, graph.relations, steps)}
      tracedRelations={tracedRelations} stepNames={names} onReference={relation => {
        setSelection({ relation: relation.key })
        locate(relation.sourceStep, relation.from)
      }} onClick={select} />
  }

  return <nav ref={navigation} className={styles.navigation} aria-label={diagram.title} data-method-workflow={methodId} data-ready={ready && !updating} data-branch={branch}
    onKeyDown={event => { if (event.key === 'Escape') setSelection(null) }}>
    <div className={styles.heading} data-flow-heading>
      <h3>{diagram.title}</h3>
      {updating && <span className={styles.updating}>重算中</span>}
      {!!trace.length && <div className={styles.traceBar} role="group" aria-label="所选量的传递关系">
        {Array.from(new Set(trace.map(relation => relation.sourceStep))).map(step => <button key={'from-' + step} type="button"
          onClick={() => locate(step, trace.find(relation => relation.sourceStep === step)!.from)}
          aria-label={'跳到来源第' + step + '步：' + names.get(step)}>{step}</button>)}
        <span aria-hidden="true">→</span>
        {Array.from(new Set(trace.map(relation => relation.targetStep))).map(step => <button key={'to-' + step} type="button"
          onClick={() => locate(step, trace.find(relation => relation.targetStep === step)!.to)}
          aria-label={'跳到接收第' + step + '步：' + names.get(step)}>{step}</button>)}
        <button type="button" className={styles.clearTrace} aria-label="清除关系高亮" onClick={() => setSelection(null)}>×</button>
      </div>}
    </div>
    <div className={styles.body}>
      <div ref={canvas} className={styles.canvas}>
        <svg className={styles.wires} viewBox={`0 0 ${wires.width} ${wires.height}`} preserveAspectRatio="none" role="img" aria-label={diagram.description}>
          <defs><marker id={marker} markerWidth="6" markerHeight="6" refX="6" refY="3" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0L6 3L0 6Z" /></marker></defs>
          {wires.paths.map((wire, index) => <path key={index} d={wire.d} data-flow-from={wire.from} data-flow-to={wire.to}
            data-flow-related={tracedRelations.has(wire.from + '→' + wire.to) || undefined}
            markerEnd={`url(#${marker})`} />)}
          {wires.paths.map(({ label }, index) => label && <text key={index} className={styles.wireLabel} x={label.x} y={label.y}
            dominantBaseline="central">{label.text}</text>)}
        </svg>
        {diagram.items.map(renderItem)}
      </div>
    </div>
  </nav>
}
