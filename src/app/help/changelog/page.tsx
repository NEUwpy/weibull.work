import { cn } from '@/lib/utils'

type Status = 'done' | 'partial' | 'todo'

interface MethodStatus {
  name: string
  tabs: {
    原理文档: Status
    程序流程: Status
    计算过程: Status
    结果分析: Status
    适用范围: Status
    可信性验证: Status
    方法对比: Status
  }
}

const TAB_NAMES = ['原理文档', '程序流程', '计算过程', '结果分析', '适用范围', '可信性验证', '方法对比'] as const

const METHOD_STATUS: MethodStatus[] = [
  { name: 'MDM',   tabs: { 原理文档: 'done', 程序流程: 'done', 计算过程: 'done', 结果分析: 'done', 适用范围: 'done', 可信性验证: 'partial', 方法对比: 'todo' } },
  { name: 'MLE',   tabs: { 原理文档: 'done', 程序流程: 'done', 计算过程: 'todo', 结果分析: 'todo', 适用范围: 'done', 可信性验证: 'todo', 方法对比: 'todo' } },
  { name: 'MMLE',  tabs: { 原理文档: 'done', 程序流程: 'done', 计算过程: 'todo', 结果分析: 'todo', 适用范围: 'todo', 可信性验证: 'todo', 方法对比: 'todo' } },
  { name: 'WMLE',  tabs: { 原理文档: 'done', 程序流程: 'done', 计算过程: 'done', 结果分析: 'todo', 适用范围: 'todo', 可信性验证: 'todo', 方法对比: 'todo' } },
  { name: 'LRE',   tabs: { 原理文档: 'todo', 程序流程: 'todo', 计算过程: 'todo', 结果分析: 'todo', 适用范围: 'todo', 可信性验证: 'todo', 方法对比: 'todo' } },
  { name: 'LSE',   tabs: { 原理文档: 'todo', 程序流程: 'todo', 计算过程: 'todo', 结果分析: 'todo', 适用范围: 'todo', 可信性验证: 'todo', 方法对比: 'todo' } },
  { name: 'MM',    tabs: { 原理文档: 'todo', 程序流程: 'todo', 计算过程: 'todo', 结果分析: 'todo', 适用范围: 'todo', 可信性验证: 'todo', 方法对比: 'todo' } },
  { name: 'MPS',   tabs: { 原理文档: 'todo', 程序流程: 'todo', 计算过程: 'todo', 结果分析: 'todo', 适用范围: 'todo', 可信性验证: 'todo', 方法对比: 'todo' } },
  { name: 'PWM',   tabs: { 原理文档: 'todo', 程序流程: 'todo', 计算过程: 'todo', 结果分析: 'todo', 适用范围: 'todo', 可信性验证: 'todo', 方法对比: 'todo' } },
  { name: 'Bayesian', tabs: { 原理文档: 'todo', 程序流程: 'todo', 计算过程: 'todo', 结果分析: 'todo', 适用范围: 'todo', 可信性验证: 'todo', 方法对比: 'todo' } },
  { name: 'Grey GM(1,1)', tabs: { 原理文档: 'todo', 程序流程: 'todo', 计算过程: 'todo', 结果分析: 'todo', 适用范围: 'todo', 可信性验证: 'todo', 方法对比: 'todo' } },
]

const STATUS_CELL: Record<Status, { label: string; cellClass: string }> = {
  done:    { label: '完成', cellClass: 'bg-emerald-50 text-emerald-700' },
  partial: { label: '进行中', cellClass: 'bg-amber-50 text-amber-700' },
  todo:    { label: '—', cellClass: 'bg-slate-50 text-slate-300' },
}

function countByStatus(methods: MethodStatus[]): { done: number; partial: number; total: number } {
  let done = 0, partial = 0, total = 0
  for (const m of methods) {
    for (const tab of TAB_NAMES) {
      total++
      if (m.tabs[tab] === 'done') done++
      else if (m.tabs[tab] === 'partial') partial++
    }
  }
  return { done, partial, total }
}

export default function StatusPage() {
  const { done, partial, total } = countByStatus(METHOD_STATUS)
  const pct = Math.round((done / total) * 100)

  return (
    <div className="bg-white p-10 rounded-3xl border border-slate-200 shadow-sm space-y-10">
      {/* 标题 */}
      <div>
        <h1 className="text-2xl font-black text-slate-900 mb-2">功能模块完成状态</h1>
        <p className="text-slate-500">各参数估计方法的开发进度总览</p>
      </div>

      {/* 汇总 */}
      <div className="flex items-center gap-6 p-5 rounded-2xl bg-slate-50 border border-slate-100">
        <div className="text-center">
          <div className="text-3xl font-black text-slate-900">{pct}%</div>
          <div className="text-xs text-slate-400 mt-1">总体完成率</div>
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
              <th className="text-left px-4 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-200 bg-slate-50/50 sticky left-0 z-10">
                方法
              </th>
              {TAB_NAMES.map(tab => (
                <th key={tab} className="px-3 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-200 bg-slate-50/50 text-center whitespace-nowrap">
                  {tab}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {METHOD_STATUS.map(method => (
              <tr key={method.name} className="hover:bg-slate-50/50">
                <td className="px-4 py-3 font-bold text-slate-900 border-b border-slate-100 sticky left-0 bg-white z-10 whitespace-nowrap">
                  {method.name}
                </td>
                {TAB_NAMES.map(tab => {
                  const s = method.tabs[tab]
                  const cfg = STATUS_CELL[s]
                  return (
                    <td key={tab} className="px-2 py-3 border-b border-slate-100 text-center">
                      <span className={cn('inline-block text-xs font-medium px-2 py-0.5 rounded-full', cfg.cellClass)}>
                        {cfg.label}
                      </span>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
