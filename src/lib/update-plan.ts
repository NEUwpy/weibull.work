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
  const content = markdown.replace(/<!--[\s\S]*?-->/g, comment => comment.replace(/[^\r\n]/g, ''))
  const diagnostics: { line: number; message: string }[] = []
  const groups = new Map<string, PlanDateGroup>()
  const backlog: string[] = []
  let updatedAt: string | undefined
  let currentGroup: PlanDateGroup | undefined
  let currentTask: PlanTask | undefined
  let currentTaskLine = 0
  const currentFields = new Set<string>()
  let inBacklog = false
  let fence: string | undefined

  function finishTask() {
    if (!currentTask) return
    for (const field of ['状态', '问题', '完成条件']) {
      if (!currentFields.has(field)) {
        diagnostics.push({ line: currentTaskLine, message: `任务「${currentTask.title}」缺少「${field}」。` })
      }
    }
    currentTask = undefined
    currentFields.clear()
  }

  const lines = content.split(/\r?\n/)
  for (let index = 0; index < lines.length; index++) {
    const line = lines[index]
    const lineNumber = index + 1
    const marker = line.match(/^ {0,3}(`{3,}|~{3,})(.*)$/)
    if (marker) {
      if (!fence) fence = marker[1]
      else if (marker[1].startsWith(fence) && !marker[2].trim()) fence = undefined
      continue
    }
    if (fence) continue

    const update = line.match(/^>\s*\*\*更新时间\*\*[:：]\s*(.*?)\s*$/)
    if (update) {
      if (isDate(update[1])) updatedAt = update[1]
      else diagnostics.push({ line: lineNumber, message: '更新时间应为有效的 YYYY-MM-DD 日期。' })
    }
    if (/^\s*>/.test(line)) continue

    const section = line.match(/^## (.+?)\s*$/)
    if (section) {
      finishTask()
      currentGroup = undefined
      inBacklog = section[1] === '历史待梳理'
      if (isDate(section[1])) {
        if (!groups.has(section[1])) groups.set(section[1], { date: section[1], tasks: [] })
        currentGroup = groups.get(section[1])
      } else if (/^\d{4}-/.test(section[1])) {
        diagnostics.push({ line: lineNumber, message: '任务分组标题应为有效的 YYYY-MM-DD 日期。' })
      }
      continue
    }

    const heading = line.match(/^### (.+?)\s*$/)
    if (heading && currentGroup) {
      finishTask()
      currentTask = { title: heading[1], status: '待开始', focus: false, problem: '', acceptance: '', dependency: '' }
      currentTaskLine = lineNumber
      currentGroup.tasks.push(currentTask)
      continue
    }

    if (inBacklog) {
      const item = line.match(/^- (.+)$/)
      if (item) backlog.push(item[1].trim())
      continue
    }

    if (!currentTask) continue
    const field = line.match(/^- (状态|重点|问题|完成条件|依赖)[:：]\s*(.*?)\s*$/)
    if (!field) continue
    const [, name, value] = field
    if (currentFields.has(name)) diagnostics.push({ line: lineNumber, message: `任务「${currentTask.title}」重复填写「${name}」。` })
    if (!value) continue
    currentFields.add(name)
    if (name === '状态') {
      if (STATUSES.includes(value as PlanStatus)) currentTask.status = value as PlanStatus
      else diagnostics.push({ line: lineNumber, message: `任务「${currentTask.title}」的状态应为${STATUSES.join('、')}之一。` })
    }
    if (name === '重点') currentTask.focus = value === '是'
    if (name === '问题') currentTask.problem = value
    if (name === '完成条件') currentTask.acceptance = value
    if (name === '依赖') currentTask.dependency = value
  }
  finishTask()

  return {
    updatedAt,
    groups: Array.from(groups.values()).filter(group => group.tasks.length > 0).sort((a, b) => b.date.localeCompare(a.date)),
    backlog,
    diagnostics,
  }
}
