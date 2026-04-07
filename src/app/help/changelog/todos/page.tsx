import WorkflowFlowchart, { FlowStep } from '@/components/help/WorkflowFlowchart'

const WORKFLOW_PLAN: FlowStep[] = [
  { label: '数据准备', status: 'done', desc: '手动输入 + 案例库调用' },
  { label: '方法选择', status: 'done', desc: '单方法 / 多方法对比' },
  { label: '参数估计', status: 'done', desc: '11 种算法实现' },
  { label: '结果分析', status: 'partial', desc: '部分方法已完成' },
  { label: '适用范围研究', status: 'partial', desc: 'MDM / MLE 已完成' },
  { label: '可信性验证', status: 'partial', desc: 'MDM 已完成' },
  { label: '方法横向对比', status: 'todo', desc: '统一评价体系' },
]

type PlanStatus = 'done' | 'todo'

interface PlanItem {
  text: string
  status: PlanStatus
}

const FEATURE_PLANS: { category: string; items: PlanItem[] }[] = [
  {
    category: '方法系统完善',
    items: [
      { text: '完成所有 25+ 算法的流程数据文件 (method_flows/*.json)', status: 'todo' },
      { text: '完成所有算法的 Markdown 原理文档', status: 'todo' },
      { text: '各方法的计算过程可视化', status: 'todo' },
      { text: '各方法的结果分析模块', status: 'todo' },
      { text: '各方法的适用范围蒙特卡洛分析', status: 'todo' },
      { text: '各方法的可信性验证（复现论文结果）', status: 'todo' },
    ],
  },
  {
    category: '横向比较与评价体系',
    items: [
      { text: '建立统一的参数估计结果评价标准', status: 'todo' },
      { text: '方法横向对比模块开发', status: 'todo' },
      { text: '根据样本特征智能推荐最佳方法', status: 'todo' },
    ],
  },
  {
    category: '数据与文献',
    items: [
      { text: '完善和校对案例数据库', status: 'todo' },
      { text: '完善和校对文献库', status: 'todo' },
      { text: '建立案例与文献的完整关联', status: 'todo' },
    ],
  },
  {
    category: '人工智能功能',
    items: [
      { text: '基于文献库的 RAG 智能问答', status: 'todo' },
      { text: '智能优化算法辅助参数估计', status: 'todo' },
      { text: '神经网络寻找最优过程量设置', status: 'todo' },
    ],
  },
]

export default function TodosPage() {
  return (
    <div className="bg-white p-10 rounded-3xl border border-slate-200 shadow-sm space-y-12">
      {/* 标题 */}
      <div>
        <h1 className="text-2xl font-black text-slate-900 mb-2">更新计划</h1>
        <p className="text-slate-500">后续开发方向与待办事项</p>
      </div>

      {/* 工作流完成状态 */}
      <section>
        <WorkflowFlowchart steps={WORKFLOW_PLAN} title="工作流开发进度" />
      </section>

      {/* 功能规划 */}
      <section>
        <h2 className="text-lg font-bold text-slate-900 mb-6">功能规划</h2>
        <div className="space-y-8">
          {FEATURE_PLANS.map(group => (
            <div key={group.category}>
              <h3 className="text-base font-bold text-slate-700 mb-3">{group.category}</h3>
              <div className="space-y-2">
                {group.items.map(item => (
                  <div
                    key={item.text}
                    className={`flex items-center gap-3 py-2.5 px-4 rounded-xl ${
                      item.status === 'todo' ? 'bg-slate-50' : 'bg-emerald-50/50'
                    }`}
                  >
                    <span
                      className={`shrink-0 w-2 h-2 rounded-full ${
                        item.status === 'done' ? 'bg-emerald-500' : 'bg-slate-300'
                      }`}
                    />
                    <span className={`text-sm ${item.status === 'todo' ? 'text-slate-400' : 'text-slate-700'}`}>
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
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
