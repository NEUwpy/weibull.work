import { cn } from '@/lib/utils'
import { getMethodCapabilities, AtomicStatus, MethodLevel } from '@/lib/method-status'
import type { MethodCapability } from '@/lib/method-status'

const TAB_KEYS = ['theory', 'process', 'calculation', 'analysis', 'applicability', 'verification'] as const
const TAB_LABELS: Record<string, string> = {
  theory: '原理文档',
  process: '程序流程',
  calculation: '计算过程',
  analysis: '结果分析',
  applicability: '适用范围',
  verification: '可信性验证',
}
const COMPARE_LABEL = '方法对比'
const LAYER1_KEYS = ['paper', 'backend', 'tests', 'calculator', 'theory', 'process'] as const
const LAYER1_LABELS: Record<string, string> = {
  paper: '论文',
  backend: '后端',
  tests: '测试',
  calculator: '计算器',
  theory: '原理',
  process: '流程',
}

const STATUS_CELL: Record<AtomicStatus, { label: string; cellClass: string }> = {
  done: { label: '完成', cellClass: 'bg-emerald-50 text-emerald-700' },
  in_progress: { label: '进行中', cellClass: 'bg-amber-50 text-amber-700' },
  blocked: { label: '受阻', cellClass: 'bg-red-50 text-red-700' },
  todo: { label: '—', cellClass: 'bg-slate-50 text-slate-300' },
  not_applicable: { label: '不适用', cellClass: 'bg-blue-50 text-blue-600' },
}

const LEVEL_CELL: Record<MethodLevel, { label: string; cellClass: string }> = {
  closed_loop: { label: '完整闭环', cellClass: 'bg-emerald-100 text-emerald-800' },
  layer2_complete: { label: '第二层完成', cellClass: 'bg-teal-100 text-teal-800' },
  layer1_complete: { label: '第一层完成', cellClass: 'bg-blue-100 text-blue-800' },
  layer1_in_progress: { label: '第一层进行中', cellClass: 'bg-amber-100 text-amber-800' },
  not_started: { label: '未开始', cellClass: 'bg-slate-100 text-slate-500' },
}

function statusFromItem(item: { status: AtomicStatus }): AtomicStatus {
  return item.status
}

function getLayer1Readiness(cap: MethodCapability): { done: number; total: number } {
  let done = 0
  if (cap.paper.status === 'done') done++
  for (const key of ['backend', 'tests', 'calculator', 'theory', 'process'] as const) {
    if (cap.layer1[key].status === 'done') done++
  }
  return { done, total: 6 }
}

function getTabStatus(cap: MethodCapability, tabKey: string): AtomicStatus {
  if (tabKey === 'compare') return 'todo'
  const map: Record<string, keyof MethodCapability['layer1'] | keyof MethodCapability['layer2'] | keyof MethodCapability['layer3']> = {
    theory: 'theory',
    process: 'process',
    calculation: 'calculation',
    analysis: 'analysis',
    applicability: 'applicability',
    verification: 'verification',
  }
  const target = map[tabKey]
  if (!target) return 'todo'
  if (target === 'calculation' || target === 'analysis') {
    return cap.layer2[target].status
  }
  if (target === 'applicability' || target === 'verification') {
    return cap.layer3[target].status
  }
  return cap.layer1[target as keyof typeof cap.layer1].status
}

function countAllItems(methods: MethodCapability[]): { done: number; partial: number; total: number } {
  let done = 0
  let partial = 0
  let total = 0
  const itemKeys = [...TAB_KEYS]
  for (const cap of methods) {
    for (const key of itemKeys) {
      total++
      const s = getTabStatus(cap, key)
      if (s === 'done') done++
      else if (s === 'in_progress') partial++
    }
  }
  return { done, partial, total }
}

const ALL_TABS = [...TAB_KEYS, 'compare']

export default function StatusPage() {
  const methods = getMethodCapabilities()
  const { done, partial, total } = countAllItems(methods)
  const pct = total > 0 ? Math.round((done / total) * 100) : 0

  return (
    <div className="bg-white p-10 rounded-3xl border border-slate-200 shadow-sm space-y-10">
      <div>
        <h1 className="text-2xl font-black text-slate-900 mb-2">功能模块完成状态</h1>
        <p className="text-slate-500">各参数估计方法的开发进度总览（22 个叶子方法，状态源自 05-状态.md）</p>
      </div>

      {/* 汇总 */}
      <div className="flex items-center gap-6 p-5 rounded-2xl bg-slate-50 border border-slate-100">
        <div className="text-center">
          <div className="text-3xl font-black text-slate-900">{pct}%</div>
          <div className="text-xs text-slate-400 mt-1">Tab 完成率</div>
        </div>
        <div className="flex-1 h-3 bg-slate-200 rounded-full overflow-hidden">
          <div className="h-full bg-emerald-500 rounded-full transition-all" style={{ width: `${pct}%` }} />
        </div>
        <div className="flex gap-4 text-xs">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            完成 {done}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
            进行中 {partial}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-slate-300" />
            待开始 {total - done - partial}
          </span>
        </div>
      </div>

      {/* 状态表格 */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr>
              <th className="text-left px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-200 bg-slate-50/50 sticky left-0 z-10">
                方法
              </th>
              <th className="px-2 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-200 bg-slate-50/50 text-center whitespace-nowrap">
                层级
              </th>
              <th className="px-2 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-200 bg-slate-50/50 text-center whitespace-nowrap">
                第一层
              </th>
              {ALL_TABS.map((tab) => {
                const label = tab === 'compare' ? COMPARE_LABEL : TAB_LABELS[tab]
                return (
                  <th key={tab} className="px-2 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-200 bg-slate-50/50 text-center whitespace-nowrap">
                    {label}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {methods.map((cap) => {
              const levelCfg = LEVEL_CELL[cap.level]
              const l1r = getLayer1Readiness(cap)
              return (
                <tr key={cap.id} className="hover:bg-slate-50/50">
                  <td className="px-3 py-3 font-bold text-slate-900 border-b border-slate-100 sticky left-0 bg-white z-10 whitespace-nowrap">
                    {cap.name}
                  </td>
                  <td className="px-1 py-3 border-b border-slate-100 text-center">
                    <span className={cn('inline-block text-[10px] font-bold px-1.5 py-0.5 rounded-full', levelCfg.cellClass)}>
                      {levelCfg.label}
                    </span>
                  </td>
                  <td className="px-1 py-3 border-b border-slate-100 text-center">
                    <span className={cn(
                      'text-[10px] font-medium',
                      l1r.done === 6 ? 'text-emerald-600' : l1r.done > 0 ? 'text-amber-600' : 'text-slate-400'
                    )}>
                      {l1r.done}/{l1r.total}
                    </span>
                  </td>
                  {ALL_TABS.map((tab) => {
                    const s = getTabStatus(cap, tab)
                    const cfg = STATUS_CELL[s]
                    return (
                      <td key={tab} className="px-1 py-3 border-b border-slate-100 text-center">
                        <span className={cn('inline-block text-[10px] font-medium px-1.5 py-0.5 rounded-full', cfg.cellClass)}>
                          {cfg.label}
                        </span>
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
