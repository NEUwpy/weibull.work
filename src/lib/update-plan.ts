export type PlanStatus = '待开始' | '进行中' | '已完成' | '已取消'

export interface PlanTask {
  title: string
  status: PlanStatus
  focus: boolean
  problem: string
  acceptance: string
  dependency: string
}

export interface PlanDateGroup {
  date: string
  tasks: PlanTask[]
}

const STATUSES: PlanStatus[] = ['待开始', '进行中', '已完成', '已取消']

function isDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const date = new Date(`${value}T00:00:00Z`)
  return Number.isFinite(date.getTime()) && date.toISOString().startsWith(value)
}

/** Read the dated task records in 04-目标与待办.md without exposing internal notes. */
export function parseUpdatePlan(markdown: string) {
  const content = markdown.replace(/<!--[\s\S]*?-->/g, '')
  const updatedAt = content.match(/^>\s*\*\*更新时间\*\*[:：]\s*(\d{4}-\d{2}-\d{2})\s*$/m)?.[1]
  const groups = new Map<string, PlanDateGroup>()
  const backlog: string[] = []
  let currentGroup: PlanDateGroup | undefined
  let currentTask: PlanTask | undefined
  let inBacklog = false
  let inCode = false

  for (const line of content.split(/\r?\n/)) {
    if (/^\s*```/.test(line)) {
      inCode = !inCode
      continue
    }
    if (inCode || /^\s*>/.test(line)) continue

    const section = line.match(/^## (.+?)\s*$/)
    if (section) {
      currentGroup = undefined
      currentTask = undefined
      inBacklog = section[1] === '历史待梳理'
      if (isDate(section[1])) {
        if (!groups.has(section[1])) groups.set(section[1], { date: section[1], tasks: [] })
        currentGroup = groups.get(section[1])
      }
      continue
    }

    const heading = line.match(/^### (.+?)\s*$/)
    if (heading && currentGroup) {
      currentTask = { title: heading[1], status: '待开始', focus: false, problem: '', acceptance: '', dependency: '' }
      currentGroup.tasks.push(currentTask)
      continue
    }

    if (inBacklog) {
      const item = line.match(/^- (.+)$/)
      if (item) backlog.push(item[1].trim())
      continue
    }

    if (!currentTask) continue
    const field = line.match(/^- (状态|重点|问题|完成条件|依赖)[:：]\s*(.+?)\s*$/)
    if (!field) continue
    const [, name, value] = field
    if (name === '状态' && STATUSES.includes(value as PlanStatus)) currentTask.status = value as PlanStatus
    if (name === '重点') currentTask.focus = value === '是'
    if (name === '问题') currentTask.problem = value
    if (name === '完成条件') currentTask.acceptance = value
    if (name === '依赖') currentTask.dependency = value
  }

  return {
    updatedAt: updatedAt && isDate(updatedAt) ? updatedAt : undefined,
    groups: Array.from(groups.values()).filter(group => group.tasks.length > 0).sort((a, b) => b.date.localeCompare(a.date)),
    backlog,
  }
}
