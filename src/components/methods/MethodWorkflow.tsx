"use client"

import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import { formatCalculationNumber as number } from '@/lib/calculation-trace'
import type { FlowDiagram, FlowDiagramItem, FlowStep } from '@/lib/method-flow'
import styles from './CalculationWorkspace.module.css'

type Wire = { d: string; dashed?: boolean; label?: { text: string; x: number; y: number } }

function ProgramBlock({ anchor, step, name, active, onClick, children }: {
  anchor: string; step: number; name: string; active?: boolean; onClick: () => void; children?: ReactNode
}) {
  return <button type="button" data-flow-anchor={anchor} data-mdm-anchor={anchor} data-flow-step={step} data-mdm-step={step} className={styles.block} onClick={onClick}
    aria-current={active ? 'step' : undefined}>
    <span className={styles.stepNumber}>{step}</span>
    <span className={styles.stepText}>
      <strong>{name}</strong>
      {children && <span className={styles.rule}>{children}</span>}
    </span>
  </button>
}

function Port({ id, direction, label, children, onClick }: {
  id: string; direction: 'input' | 'output'; label: string; children: ReactNode; onClick: () => void
}) {
  return <button type="button" data-flow-anchor={id} data-mdm-anchor={id} onClick={onClick} className={`${styles.port} ${styles[direction]}`}>
    <svg viewBox="0 0 120 60" preserveAspectRatio="none" aria-hidden="true">
      <path d={direction === 'input' ? 'M1 1H119V49L109 59H11L1 49Z' : 'M11 1H109L119 11V59H1V11Z'} vectorEffect="non-scaling-stroke" />
    </svg>
    <span className={styles.portKind}>{direction === 'input' ? '输入' : '输出'}</span>
    <span>{label}</span>
    {children && <span className={styles.value}>{children}</span>}
  </button>
}

export function MethodWorkflow({ methodId, diagram, steps, values = {}, ready, branch = 'ready', updating = false, activeProgramStep, onSelect }: {
  methodId: string; diagram: FlowDiagram; steps: FlowStep[]; values?: Record<string, number | undefined>
  ready: boolean; branch?: 'ready' | 'zero' | 'extrapolated' | 'failed'; updating?: boolean
  activeProgramStep?: number; onSelect: (step: number) => void
}) {
  const canvas = useRef<HTMLDivElement>(null)
  const navigation = useRef<HTMLElement>(null)
  const marker = `mdm-arrow-${useId().replace(/:/g, '')}`
  const [wires, setWires] = useState<{ width: number; height: number; paths: Wire[] }>({ width: 280, height: 700, paths: [] })
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    const pane = navigation.current
    const block = pane?.querySelector<HTMLElement>('[aria-current="step"]')
    if (!pane || !block || pane.scrollHeight <= pane.clientHeight) return
    const bounds = pane.getBoundingClientRect()
    const item = block.getBoundingClientRect()
    if (item.top < bounds.top + 64) pane.scrollTop += item.top - bounds.top - 64
    else if (item.bottom > bounds.bottom - 16) pane.scrollTop += item.bottom - bounds.bottom + 16
  }, [activeProgramStep])

  useLayoutEffect(() => {
    const element = canvas.current
    if (!element) return
    const measure = () => {
      if (!element.clientWidth) return
      const rect = element.getBoundingClientRect()
      const anchors = new Map(Array.from(element.querySelectorAll<HTMLElement>('[data-mdm-anchor]'))
        .map(item => [item.dataset.mdmAnchor, item.getBoundingClientRect()]))
      const paths = diagram.connections.flatMap<Wire>(connection => {
        const from = anchors.get(connection.from), to = anchors.get(connection.to)
        if (!from || !to) return []
        const x1 = (from.left + from.right) / 2 - rect.left, y1 = from.bottom - rect.top
        const x2 = (to.left + to.right) / 2 - rect.left, y2 = to.top - rect.top
        if (connection.route === 'loop') {
          return [{ d: `M${from.left - rect.left} ${(from.top + from.bottom) / 2 - rect.top} H21 V${(to.top + to.bottom) / 2 - rect.top} H${to.left - rect.left}`, dashed: connection.dashed }]
        }
        if (connection.route) {
          const lane = connection.route === 'left' ? 6 : rect.width - (connection.route === 'right-lower' ? 17 : 7)
          if (connection.route !== 'left') {
            const entry = to.top - rect.top + to.height * (connection.route === 'right-lower' ? 0.65 : 0.35)
            return [{ d: `M${x1} ${y1} V${y1 + 6} H${lane} V${entry} H${to.right - rect.left}`, dashed: connection.dashed }]
          }
          return [{ d: `M${x1} ${y1} V${y1 + 14} H${lane} V${y2 - 12} H${x2} V${y2}`, dashed: connection.dashed }]
        }
        const middle = (y1 + y2) / 2
        return [{
          d: `M${x1} ${y1} V${middle} H${x2} V${y2}`,
          dashed: connection.dashed,
          label: connection.label ? { text: connection.label, x: Math.max(x1, x2) + 8, y: middle } : undefined,
        }]
      })
      setWires({ width: rect.width, height: rect.height, paths })
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [diagram.connections, expanded])

  const names = new Map(steps.map(step => [step.id, step.name]))

  function renderItem(item: FlowDiagramItem, index: number): ReactNode {
    if (item.kind === 'group') return <div key={index} className={styles[item.layout]}>
      {item.title && <p className={styles.groupLabel}>{item.title}</p>}
      {item.sideLabel && <span className={styles.loopLabel}>{item.sideLabel}</span>}
      {item.children.map(renderItem)}
    </div>

    const variants = item.text
    const liveLines = ready && (variants?.[branch] ?? variants?.ready)
    const lines = liveLines && liveLines.every(line => Array.from(line.matchAll(/\{(\w+)\}/g)).every(([, key]) => values[key] !== undefined))
      ? liveLines : variants?.default
    const caption = lines?.map((line, i) => <span key={i}>{line.replace(/\{(\w+)\}/g, (_, key: string) => number(values[key]))}</span>)
    const step = item.kind === 'step' ? item.step : diagram.targets[item.target]
    const select = () => onSelect(step)
    if (item.kind === 'step') return <ProgramBlock key={item.anchor} anchor={item.anchor} step={step} name={names.get(step)!}
      active={activeProgramStep === step} onClick={select}>{caption}</ProgramBlock>
    return <Port key={item.anchor} id={item.anchor} direction={item.direction}
      label={updating ? item.updatingLabel ?? item.label : item.label} onClick={select}>{caption}</Port>
  }

  return <nav ref={navigation} className={styles.navigation} aria-label={diagram.title} data-method-workflow={methodId} data-mdm-workflow={methodId === 'mdm' ? true : undefined} data-ready={ready && !updating}>
    <div className={styles.heading}>
      <h3>{diagram.title}</h3>
      <button type="button" className={styles.toggle} aria-expanded={expanded} aria-label={(expanded ? '收起' : '展开') + diagram.title} onClick={() => setExpanded(value => !value)}>
        <ChevronDown size={18} style={{ transform: expanded ? 'rotate(180deg)' : undefined }} />
      </button>
      {updating && <span className={styles.updating}>重算中</span>}
    </div>
    <div className={`${styles.body} ${expanded ? styles.expanded : ''}`}>
      <div ref={canvas} className={styles.canvas}>
        <svg className={styles.wires} viewBox={`0 0 ${wires.width} ${wires.height}`} preserveAspectRatio="none" role="img" aria-label={diagram.description}>
          <defs><marker id={marker} markerWidth="6" markerHeight="6" refX="5.5" refY="3" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0L6 3L0 6Z" /></marker></defs>
          {wires.paths.map((wire, index) => <path key={index} d={wire.d} strokeDasharray={wire.dashed ? '4 3' : undefined} markerEnd={`url(#${marker})`} />)}
          {wires.paths.map(({ label }, index) => label && <text key={index} className={styles.wireLabel} x={label.x} y={label.y}
            dominantBaseline="central">{label.text}</text>)}
        </svg>
        {diagram.items.map(renderItem)}
      </div>
    </div>
  </nav>
}
