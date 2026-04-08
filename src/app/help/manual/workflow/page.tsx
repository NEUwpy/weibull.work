import Link from 'next/link'

interface Workflow {
  goal: string
  steps: string[]
  entry: string
  entryHref: string
}

const WORKFLOWS: Workflow[] = [
  {
    goal: '获得一组样本的参数估计结果',
    steps: [
      '打开计算器',
      '点击「数据」按钮，输入失效时间数据',
      '点击「方法」按钮，选择估计方法（如 MLE、MDM）',
      '选择 2 参数或 3 参数模型',
      '点击「计算」，获得 β、η、γ 估计值和概率分布图',
    ],
    entry: '前往计算器',
    entryHref: '/',
  },
  {
    goal: '对比多种方法的估计结果',
    steps: [
      '在计算器中完成一次计算后',
      '点击「+」添加新的方法卡片',
      '选择不同的估计方法（可叠加多个）',
      '各方法的分布曲线叠加在同一图上，直观对比差异',
    ],
    entry: '前往计算器',
    entryHref: '/',
  },
  {
    goal: '根据指定参数生成抽样数据',
    steps: [
      '在计算器中点击「+」添加卡片，选择「参数」模式',
      '输入 β、η、γ 参数值',
      '系统根据参数生成对应的概率分布曲线',
      '可用于教学演示或理论对照',
    ],
    entry: '前往计算器',
    entryHref: '/',
  },
  {
    goal: '进行不同参数的分布图对比',
    steps: [
      '在计算器中添加多个「参数」卡片',
      '为每张卡片设置不同的参数组合（如不同 β 值）',
      '多条分布曲线叠加显示',
      '直观对比参数变化对分布形态的影响',
    ],
    entry: '前往计算器',
    entryHref: '/',
  },
  {
    goal: '引用案例数据进行参数估计',
    steps: [
      '打开案例数据库，浏览或搜索标准失效数据集',
      '选择一个案例，查看数据详情和来源文献',
      '点击「在计算器中使用」，数据自动加载到计算器',
      '选择估计方法，执行计算',
    ],
    entry: '前往案例库',
    entryHref: '/cases',
  },
  {
    goal: '深入了解某方法的原理与计算过程',
    steps: [
      '打开方法系统，选择一个方法（如 MDM）',
      '默认页面显示原理文档：公式推导、适用条件',
      '切换到「程序流程」标签，看公式与代码的对应关系',
      '切换到「计算过程」标签，观察参数的迭代收敛过程',
    ],
    entry: '前往方法系统',
    entryHref: '/methods',
  },
  {
    goal: '评估方法在不同条件下的适用性',
    steps: [
      '在方法页面切换到「适用范围」标签',
      '选择不同的参数组合（β、η、γ、样本量）',
      '查看基于蒙特卡洛模拟的统计结果（偏差、方差、收敛率）',
      '通过箱型图、热力图了解方法的表现规律',
    ],
    entry: '前往方法系统',
    entryHref: '/methods',
  },
  {
    goal: '查看方法的过程量设置对估计结果的影响',
    steps: [
      '在方法页面切换到「计算过程」标签',
      '调整过程量参数（如 MDM 的偏移量 δ）',
      '观察过程量变化如何影响参数的搜索路径和最终结果',
      '理解"结果是怎么一步步算出来的"',
    ],
    entry: '前往方法系统',
    entryHref: '/methods',
  },
  {
    goal: '验证方法实现的正确性',
    steps: [
      '在方法页面切换到「可信性验证」标签',
      '选择一个验证项（复现某篇论文的计算设置）',
      '左侧展示论文原图，右侧展示系统复现结果',
      '对比确认方法实现的正确性',
    ],
    entry: '前往方法系统',
    entryHref: '/methods',
  },
  {
    goal: '查阅方法或案例的原始文献',
    steps: [
      '打开可靠性图书馆',
      '浏览文献列表，或从方法/案例页面跳转到关联文献',
      '支持中英双语切换阅读',
      '参考文献之间可互相跳转',
    ],
    entry: '前往图书馆',
    entryHref: '/library',
  },
]

export default function WorkflowPage() {
  return (
    <div className="bg-white p-10 rounded-3xl border border-slate-200 shadow-sm space-y-10">
      {/* 标题 */}
      <div>
        <h1 className="text-2xl font-black text-slate-900 mb-2">工作流介绍</h1>
        <p className="text-slate-500">想做什么 → 怎么操作</p>
      </div>

      {/* 工作流列表 */}
      <div className="space-y-6">
        {WORKFLOWS.map((wf, i) => (
          <div
            key={i}
            className="p-6 rounded-2xl border border-slate-200 hover:border-slate-300 transition-colors"
          >
            {/* 目标 */}
            <div className="flex items-start gap-3 mb-4">
              <span className="shrink-0 mt-0.5 w-7 h-7 rounded-lg bg-blue-600 text-white flex items-center justify-center text-xs font-bold">
                {i + 1}
              </span>
              <h3 className="text-base font-bold text-slate-900 leading-relaxed">
                {wf.goal}
              </h3>
            </div>

            {/* 步骤 */}
            <div className="ml-10 space-y-2">
              {wf.steps.map((step, j) => (
                <div key={j} className="flex items-start gap-3">
                  <span className="shrink-0 mt-1 w-1.5 h-1.5 rounded-full bg-slate-300" />
                  <span className="text-sm text-slate-600 leading-relaxed">{step}</span>
                </div>
              ))}
            </div>

            {/* 入口链接 */}
            <div className="ml-10 mt-4">
              <Link
                href={wf.entryHref}
                className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline font-medium"
              >
                {wf.entry} →
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
