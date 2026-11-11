"use client"

import { useEffect, useId, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { LineChart, Code2, PanelLeft, PanelRight } from 'lucide-react'
import type { FlowChartTarget, FlowStep } from '@/lib/method-flow'
import { useCalculationStage } from './CalculationSource'
import { useMethodFlow } from './useMethodFlow'
import { FlowStepCode, FlowStepDetails } from './VariableFlowViewer'
import { MethodWorkflow } from './MethodWorkflow'
import styles from './CalculationWorkspace.module.css'

const views = [{ id: 'charts', label: '图像', icon: LineChart }, { id: 'program', label: '代码', icon: Code2 }] as const
type View = (typeof views)[number]['id']
type Side = 'left' | 'right'
const DEFAULT_SIDEBAR_WIDTH = 300
const MIN_SIDEBAR_WIDTH = 248
const MAX_SIDEBAR_WIDTH = 520
const MIN_READER_WIDTH = 440
const PANE_GAP = 24
const COLLAPSED_SIDEBAR_WIDTH = 32

function SidebarDivider({ side, controls, width, maxWidth, onResize }: {
  side: Side; controls: string; width: number; maxWidth: number; onResize: (width: number) => void
}) {
  const drag = useRef<{ x: number; width: number } | null>(null)
  const direction = side === 'left' ? 1 : -1
  const label = side === 'left' ? '调整左侧栏宽度' : '调整右侧栏宽度'
  const resize = (next: number) => onResize(Math.max(MIN_SIDEBAR_WIDTH, Math.min(maxWidth, Math.round(next))))

  return <div className={styles.sidebarDivider} data-side={side} role="separator" tabIndex={0}
    title={label} aria-label={label} aria-controls={controls} aria-orientation="vertical"
    aria-valuemin={MIN_SIDEBAR_WIDTH} aria-valuemax={maxWidth} aria-valuenow={width}
    onPointerDown={event => {
      if (!event.isPrimary || event.button !== 0) return
      event.preventDefault()
      event.currentTarget.focus({ preventScroll: true })
      event.currentTarget.setPointerCapture(event.pointerId)
      drag.current = { x: event.clientX, width }
    }}
    onPointerMove={event => {
      if (!drag.current || !event.currentTarget.hasPointerCapture(event.pointerId)) return
      resize(drag.current.width + direction * (event.clientX - drag.current.x))
    }}
    onLostPointerCapture={() => { drag.current = null }}
    onKeyDown={event => {
      switch (event.key) {
        case 'ArrowLeft': resize(width - direction * 16); break
        case 'ArrowRight': resize(width + direction * 16); break
        case 'Home': resize(MIN_SIDEBAR_WIDTH); break
        case 'End': resize(maxWidth); break
        default: return
      }
      event.preventDefault()
    }} />
}

interface WorkspaceProps {
  methodId: string
  ready: boolean
  updating?: boolean
  revision?: unknown
  values?: Record<string, string>
  workflowValues?: Record<string, number | undefined>
  workflowBranch?: 'ready' | 'zero' | 'extrapolated' | 'failed'
  formulaVariant?: (step: FlowStep, target?: FlowChartTarget) => string | undefined
  renderFigure: (step: FlowStep, target?: FlowChartTarget) => ReactNode
  renderDetails?: (step: FlowStep, target?: FlowChartTarget) => ReactNode
  notice?: ReactNode
  emptyContent?: ReactNode
}

export function CalculationWorkspace({ methodId, ready, updating = false, revision, values, workflowValues,
  workflowBranch = 'ready', formulaVariant, renderFigure, renderDetails, notice, emptyContent }: WorkspaceProps) {
  const { flow, loading, error, retry } = useMethodFlow(methodId)
  const [view, setView] = useState<View>('charts')
  const [activeId, setActiveId] = useState<number>()
  const [leftOpenOverride, setLeftOpenOverride] = useState<boolean>()
  const [rightOpen, setRightOpen] = useState(true)
  const [leftWidth, setLeftWidth] = useState(DEFAULT_SIDEBAR_WIDTH)
  const [rightWidth, setRightWidth] = useState(DEFAULT_SIDEBAR_WIDTH)
  const [layoutWidth, setLayoutWidth] = useState(0)
  const layout = useRef<HTMLDivElement>(null)
  const leftPane = useRef<HTMLDivElement>(null)
  const reader = useRef<HTMLDivElement>(null)
  const pendingScroll = useRef<number | 'flow' | null>(null)
  const id = useId()
  const sourceRequest = useCalculationStage()?.sourceRequest
  const diagram = flow?.workflow
  const activeStep = flow?.steps.find(step => step.id === activeId) ?? flow?.steps[0]
  const targetFor = (step: number) => Object.entries(diagram?.targets ?? {}).find(([, value]) => value === step)?.[0] as FlowChartTarget | undefined
  const sidebarSlots = Math.min(2, Math.max(0, Math.floor((layoutWidth - MIN_READER_WIDTH) / (MIN_SIDEBAR_WIDTH + PANE_GAP))))
  const columns = sidebarSlots + 1
  const leftOpen = leftOpenOverride ?? (columns === 3)
  const openSidebars = Number(columns === 3 && leftOpen) + Number(columns >= 2 && rightOpen)
  const sidebarSpace = layoutWidth - MIN_READER_WIDTH - sidebarSlots * PANE_GAP
    - (sidebarSlots - openSidebars) * COLLAPSED_SIDEBAR_WIDTH
  const maxSidebarWidth = openSidebars
    ? Math.min(MAX_SIDEBAR_WIDTH, Math.floor(sidebarSpace / openSidebars))
    : MAX_SIDEBAR_WIDTH

  useLayoutEffect(() => {
    const element = layout.current
    if (!element) return
    const measure = () => setLayoutWidth(element.clientWidth)
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [diagram])

  function scrollToStep(step: number) {
    setActiveId(step)
    reader.current?.querySelector<HTMLElement>(`[data-reader-step="${step}"]`)?.scrollIntoView({ behavior: 'instant', block: 'start' })
  }

  function chooseView(next: View) {
    if (next === view) return
    pendingScroll.current = activeStep?.id ?? null
    setView(next)
  }

  function togglePanel(side: Side) {
    pendingScroll.current = side === 'left' && !leftOpen && columns < 3 ? 'flow' : activeStep?.id ?? null
    if (side === 'left') setLeftOpenOverride(!leftOpen)
    else setRightOpen(value => !value)
  }

  useLayoutEffect(() => {
    const step = pendingScroll.current
    pendingScroll.current = null
    if (step === null) return
    if (step === 'flow') {
      leftPane.current?.scrollIntoView({ behavior: 'instant', block: 'start' })
      return
    }
    scrollToStep(step)
    // Row splitting settles after the available width changes.
    let secondFrame = 0
    const firstFrame = requestAnimationFrame(() => {
      secondFrame = requestAnimationFrame(() => scrollToStep(step))
    })
    return () => { cancelAnimationFrame(firstFrame); cancelAnimationFrame(secondFrame) }
  }, [view, flow, leftOpen, rightOpen])

  useEffect(() => {
    if (!sourceRequest || !flow) return
    const requested = sourceRequest.fromUrl && sourceRequest.step
      ? diagram?.legacySourceSteps?.[sourceRequest.step - 1] ?? sourceRequest.step : sourceRequest.step
    const step = flow.steps.find(item => item.id === requested) ?? flow.steps[0]
    if (view === 'program') scrollToStep(step.id)
    else {
      pendingScroll.current = step.id
      setActiveId(step.id)
      setView('program')
    }
  }, [sourceRequest, flow, diagram])

  useEffect(() => {
    const container = reader.current
    if (!container) return
    let frame = 0
    function measure() {
      frame = 0
      const sections = Array.from(container!.querySelectorAll<HTMLElement>('[data-reader-step]'))
      const line = Math.min(300, Math.max(180, window.innerHeight * .3))
      if (container!.getBoundingClientRect().top > line) return
      let row: HTMLElement[] = []
      let rowTop = -Infinity
      const atEnd = container!.getBoundingClientRect().bottom <= window.innerHeight
      const nearestTop = sections.map(section => section.getBoundingClientRect().top)
        .sort((left, right) => Math.abs(left - line) - Math.abs(right - line))[0] ?? line
      const readingLine = atEnd ? nearestTop + 2 : line
      for (const section of sections) {
        const top = section.getBoundingClientRect().top
        if (top > readingLine) continue
        if (top > rowTop + 2) { row = [section]; rowTop = top }
        else if (Math.abs(top - rowTop) <= 2) row.push(section)
      }
      if (!row.length && sections[0]) row = [sections[0]]
      setActiveId(previous => {
        const selected = sections.find(section => Number(section.dataset.readerStep) === previous)
        const top = selected?.getBoundingClientRect().top
        if (atEnd && top !== undefined && top >= 128 && top < window.innerHeight - 80) return previous
        return row.some(section => Number(section.dataset.readerStep) === previous)
          ? previous : Number(row[0]?.dataset.readerStep) || undefined
      })
    }
    const schedule = () => { if (!frame) frame = requestAnimationFrame(measure) }
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)
    const observer = new ResizeObserver(schedule)
    observer.observe(container)
    schedule()
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
    }
  }, [flow, view, revision])

  if (!flow || !diagram || !activeStep) return <div className="px-4 py-6 text-slate-600" role={error ? 'alert' : 'status'}>
    <p>{loading ? '加载计算过程…' : error || '计算过程暂不可用。'}</p>
    {!loading && <button type="button" className="mt-2 text-blue-700" onClick={retry}>重新加载</button>}
  </div>

  function explanation(step: FlowStep) {
    const target = targetFor(step.id)
    const equationStart = flow!.steps.filter(item => item.id < step.id)
      .reduce((total, item) => total + (item.formula.equations?.length ?? 1), 1)
    return <FlowStepDetails step={step} values={values} formulaVariant={formulaVariant?.(step, target)} equationStart={equationStart} compact>
      {renderDetails?.(step, target)}
    </FlowStepDetails>
  }

  const visibleLeftWidth = Math.min(leftWidth, maxSidebarWidth)
  const visibleRightWidth = Math.min(rightWidth, maxSidebarWidth)
  const sidebarWidths = {
    '--left-sidebar-width': `${visibleLeftWidth}px`,
    '--right-sidebar-width': `${visibleRightWidth}px`,
    '--collapsed-sidebar-width': `${COLLAPSED_SIDEBAR_WIDTH}px`,
    '--pane-gap': `${PANE_GAP}px`,
  } as CSSProperties

  return <div className={styles.workspace} data-calculation-method={methodId} data-columns={columns} data-left-open={leftOpen}
    data-right-open={rightOpen} style={sidebarWidths} aria-busy={updating}>
    <div className={styles.readerToolbar}>
      <div>
        <button type="button" className={styles.panelToggle} title="显示或隐藏流程图" aria-label="显示或隐藏流程图"
          aria-expanded={leftOpen} aria-controls={`${id}-flow`} onClick={() => togglePanel('left')}>
          <PanelLeft size={19} />
        </button>
      </div>
      <div className={styles.modeButtons} role="tablist" aria-label="计算过程视角">
        {views.map(({ id: tab, label, icon: Icon }, index) => <button key={tab} type="button" role="tab" id={`${id}-${tab}-tab`}
          data-calculation-view={tab} data-mdm-view={methodId === 'mdm' ? tab : undefined} aria-controls={`${id}-reader`} aria-selected={view === tab} tabIndex={view === tab ? 0 : -1}
          onClick={() => chooseView(tab)} onKeyDown={event => {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
            event.preventDefault()
            const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? views.length - 1 : (index + 1) % views.length
            chooseView(views[nextIndex].id)
            event.currentTarget.parentElement?.querySelector<HTMLButtonElement>(`[data-calculation-view="${views[nextIndex].id}"]`)?.focus()
          }}><Icon size={16} aria-hidden="true" />{label}</button>)}
      </div>
      <div className={styles.rightToggle}>
        <button type="button" className={styles.panelToggle} title="显示或隐藏公式与输入输出" aria-label="显示或隐藏公式与输入输出"
          aria-expanded={rightOpen} aria-controls={`${id}-details`} onClick={() => togglePanel('right')}>
          <PanelRight size={19} />
        </button>
      </div>
    </div>
    {notice}
    <div ref={layout} className={styles.layout}>
      <div ref={leftPane} className={styles.leftPane} id={`${id}-flow`} hidden={!leftOpen}>
        <MethodWorkflow methodId={methodId} diagram={diagram} steps={flow.steps} values={workflowValues}
          ready={ready} updating={updating} branch={workflowBranch} activeProgramStep={activeStep.id} onSelect={scrollToStep} />
      </div>
      {columns === 3 && leftOpen && <SidebarDivider side="left" controls={`${id}-flow`} width={visibleLeftWidth}
        maxWidth={maxSidebarWidth} onResize={setLeftWidth} />}
      <div ref={reader} className={styles.readerMain} id={`${id}-reader`} role="tabpanel"
        aria-labelledby={`${id}-${view}-tab`} data-reader-view={view}>
        <div className={styles.readerGrid}>{flow.steps.map(step => {
          const target = targetFor(step.id)
          return <section key={step.id} className={styles.readerStep} data-reader-step={step.id} data-flow-target={target}
            data-flow-active={step.id === activeStep.id} tabIndex={-1} aria-label={step.name}
            onPointerEnter={() => setActiveId(step.id)} onFocusCapture={() => setActiveId(step.id)}>
            <h3 className={styles.stepHeading}><span>{step.id}</span>{step.name}</h3>
            {view === 'program' ? <FlowStepCode flow={flow} step={step} continuous />
              : !ready && step.id === flow.steps[0].id && emptyContent ? emptyContent
              : renderFigure(step, target) ?? <p className="text-sm text-slate-500">计算后显示本步数据。</p>}
            {rightOpen && <div className={styles.mobileExplanation}>{explanation(step)}</div>}
          </section>
        })}</div>
      </div>
      {columns >= 2 && rightOpen && <SidebarDivider side="right" controls={`${id}-details`} width={visibleRightWidth}
        maxWidth={maxSidebarWidth} onResize={setRightWidth} />}
      <aside id={`${id}-details`} className={styles.explanation} hidden={!rightOpen}
        aria-label="当前步骤的公式与输入输出" data-explanation-step={activeStep.id}>
        <h3 className={styles.explanationHeading}><span>{activeStep.id}</span>{activeStep.name}</h3>
        {explanation(activeStep)}
      </aside>
    </div>
  </div>
}
