import WorkflowFlowchart from '@/components/help/WorkflowFlowchart'
import Link from 'next/link'

const WORKFLOW_STEPS = [
  { label: '数据准备', desc: '手动输入或从案例库选择失效数据' },
  { label: '方法选择', desc: '选择参数估计方法和模型类型' },
  { label: '参数估计', desc: '执行计算，获得 β, η, γ 估计值' },
  { label: '结果分析', desc: '拟合优度评估与置信区间' },
  { label: '方法研究', desc: '适用范围分析与可信性验证' },
]

const DATA_FLOW = [
  {
    from: '案例数据库',
    to: '计算器',
    data: '失效数据集 (CSV)',
  },
  {
    from: '计算器',
    to: '参数估计方法',
    data: '估计结果 (β, η, γ, R²)',
  },
  {
    from: '参数估计方法',
    to: '结果分析',
    data: '拟合优度、残差、置信区间',
  },
  {
    from: '可靠性图书馆',
    to: '参数估计方法',
    data: '理论依据与参考文献',
  },
]

export default function WorkflowPage() {
  return (
    <div className="bg-white p-10 rounded-3xl border border-slate-200 shadow-sm space-y-12">
      {/* 标题 */}
      <div>
        <h1 className="text-2xl font-black text-slate-900 mb-2">工作流介绍</h1>
        <p className="text-slate-500">通过平台功能模块的操作步骤与参数传递逻辑，呈现完整工作流程</p>
      </div>

      {/* 核心工作流 */}
      <section>
        <h2 className="text-lg font-bold text-slate-900 mb-6">核心工作流</h2>
        <WorkflowFlowchart steps={WORKFLOW_STEPS} />
      </section>

      {/* 各步骤说明 */}
      <section>
        <h2 className="text-lg font-bold text-slate-900 mb-6">步骤详解</h2>
        <div className="space-y-5">
          {WORKFLOW_STEPS.map((step, i) => (
            <div key={step.label} className="flex gap-4 items-start">
              <div className="shrink-0 w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-sm font-bold">
                {i + 1}
              </div>
              <div>
                <h3 className="font-bold text-slate-900">{step.label}</h3>
                <p className="text-sm text-slate-500 mt-0.5">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 数据流向 */}
      <section>
        <h2 className="text-lg font-bold text-slate-900 mb-6">模块间数据流向</h2>
        <div className="space-y-3">
          {DATA_FLOW.map((flow, i) => (
            <div
              key={i}
              className="flex items-center gap-3 p-4 rounded-xl bg-slate-50 border border-slate-100"
            >
              <span className="text-sm font-bold text-slate-700 shrink-0">{flow.from}</span>
              <div className="flex items-center gap-1 shrink-0">
                <div className="w-4 h-0.5 bg-slate-300" />
                <div className="w-0 h-0 border-t-[4px] border-t-transparent border-b-[4px] border-b-transparent border-l-[5px] border-l-slate-300" />
              </div>
              <span className="text-sm font-bold text-slate-700 shrink-0">{flow.to}</span>
              <span className="text-xs text-slate-400 ml-auto">{flow.data}</span>
            </div>
          ))}
        </div>
      </section>

      {/* 快速入口 */}
      <section className="flex gap-4 pt-4 border-t border-slate-100">
        <Link
          href="/"
          className="text-sm text-blue-600 hover:underline font-medium"
        >
          前往计算器 →
        </Link>
        <Link
          href="/methods"
          className="text-sm text-blue-600 hover:underline font-medium"
        >
          浏览方法系统 →
        </Link>
        <Link
          href="/cases"
          className="text-sm text-blue-600 hover:underline font-medium"
        >
          查看案例库 →
        </Link>
      </section>
    </div>
  )
}
