interface PlanItem {
  text: string
  status: 'done' | 'todo'
}

type Phase = {
  label: string
  desc: string
  items: PlanItem[]
}

const PHASES: Phase[] = [
  {
    label: '短期',
    desc: '',
    items: [
      { text: '完成所有 25+ 算法的流程数据文件 (method_flows/*.json)', status: 'todo' },
      { text: '完成所有算法的 Markdown 原理文档', status: 'todo' },
      { text: '各方法的计算过程可视化', status: 'todo' },
      { text: '各方法的结果分析模块', status: 'todo' },
      { text: '各方法的适用范围蒙特卡洛分析', status: 'todo' },
      { text: '各方法的可信性验证（复现论文结果）', status: 'todo' },
      { text: '完善和校对案例数据库', status: 'todo' },
      { text: '完善和校对文献库', status: 'todo' },
      { text: '建立案例与文献的完整关联', status: 'todo' },
    ],
  },
  {
    label: '中期',
    desc: '',
    items: [
      { text: '建立统一的参数估计结果评价标准', status: 'todo' },
      { text: '方法横向对比模块开发', status: 'todo' },
      { text: '根据样本特征智能推荐最佳方法', status: 'todo' },
    ],
  },
  {
    label: '长期',
    desc: '',
    items: [
      { text: '基于文献库的 RAG 智能问答', status: 'todo' },
      { text: '智能优化算法辅助参数估计', status: 'todo' },
      { text: '神经网络寻找最优过程量设置', status: 'todo' },
    ],
  },
]

const PHASE_STYLES: Record<string, { badge: string; dot: string }> = {
  '短期': { badge: 'bg-blue-100 text-blue-700', dot: 'bg-blue-400' },
  '中期': { badge: 'bg-amber-100 text-amber-700', dot: 'bg-amber-400' },
  '长期': { badge: 'bg-violet-100 text-violet-700', dot: 'bg-violet-400' },
}

export default function TodosPage() {
  return (
    <div className="bg-white p-10 rounded-3xl border border-slate-200 shadow-sm space-y-12">
      {/* 标题 */}
      <div>
        <h1 className="text-2xl font-black text-slate-900 mb-2">更新计划</h1>
        <p className="text-slate-500">后续开发方向与待办事项</p>
      </div>

      {/* 阶段规划 */}
      <div className="space-y-10">
        {PHASES.map(phase => {
          const style = PHASE_STYLES[phase.label]
          const doneCount = phase.items.filter(i => i.status === 'done').length
          const totalCount = phase.items.length
          return (
            <section key={phase.label}>
              {/* 阶段标题 */}
              <div className="flex items-center gap-3 mb-2">
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${style.badge}`}>
                  {phase.label}
                </span>
                <span className="ml-auto text-xs text-slate-400">{doneCount}/{totalCount}</span>
              </div>

              {/* 任务列表 */}
              <div className="space-y-2 mt-3">
                {phase.items.map(item => (
                  <div
                    key={item.text}
                    className={`flex items-center gap-3 py-2.5 px-4 rounded-xl ${
                      item.status === 'todo' ? 'bg-slate-50' : 'bg-emerald-50/50'
                    }`}
                  >
                    <span
                      className={`shrink-0 w-2 h-2 rounded-full ${
                        item.status === 'done' ? 'bg-emerald-500' : style.dot
                      }`}
                    />
                    <span className={`text-sm ${item.status === 'todo' ? 'text-slate-500' : 'text-slate-700'}`}>
                      {item.text}
                    </span>
                    {item.status === 'todo' && (
                      <span className="ml-auto text-[10px] font-bold text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded shrink-0">
                        待完成
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )
        })}
      </div>
    </div>
  )
}
