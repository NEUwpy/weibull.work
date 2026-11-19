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
      '在样本栏输入失效时间，或从案例库导入样本',
      '点击「方法」按钮，选择估计方法（如 MLE、MDM）',
      '选择三参数模型（3P）',
      '点击「参数估计」，查看 β、η、γ 估计值和概率分布图',
    ],
    entry: '前往计算器',
    entryHref: '/',
  },
  {
    goal: '对比多种方法的估计结果',
    steps: [
      '在计算器中完成一次计算后',
      '点击「＋ → 继承样本」创建一张使用同组数据的分析卡片',
      '选择其他估计方法，再点击「参数估计」',
      '在图表的「叠加图层」中选择要对照的结果',
    ],
    entry: '前往计算器',
    entryHref: '/',
  },
  {
    goal: '根据指定参数生成抽样数据',
    steps: [
      '点击样本栏与参数栏之间的互换按钮，切换到参数输入',
      '选择 2P 或 3P，输入分布参数与样本量',
      '点击「生成样本」，在样本栏查看结果',
    ],
    entry: '前往计算器',
    entryHref: '/',
  },
  {
    goal: '进行不同参数的分布图对比',
    steps: [
      '在计算器中添加分析卡片，在各卡片切换到参数输入',
      '为各卡片设置不同的参数组合（如不同 β 值）并生成样本',
      '多条分布曲线叠加显示',
      '直观对比参数变化对分布形态的影响',
    ],
    entry: '前往计算器',
    entryHref: '/',
  },
  {
    goal: '引用案例数据进行参数估计',
    steps: [
      '打开案例数据库，浏览或搜索失效样本',
      '选择一个案例，查看数据详情和来源文献',
      '点案例详情中的复制图标，再将数值样本粘贴到计算器的样本栏',
      '选择估计方法，执行计算',
    ],
    entry: '前往案例库',
    entryHref: '/cases',
  },
  {
    goal: '深入了解某方法的原理与计算过程',
    steps: [
      '打开方法系统，选择一个方法（如 MDM）',
      '在「方法原理」查看公式和适用条件',
      '在「计算过程」准备样本，点击「计算并展示过程」',
      '依次查看实际试算、采用的判据与估计结果，切换到「代码」可核对源码',
    ],
    entry: '前往方法系统',
    entryHref: '/methods',
  },
  {
    goal: '评估方法在不同条件下的适用性',
    steps: [
      '进入方法页的「结果分析」，在「预计算结果」选择参数与样本量',
      '切换样本数据与估计结果，在表下查看统计和差值分布',
      '切换到「现场计算」，在计算器卡片上生成多组样本并做参数估计',
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
    <div className="bg-white p-10 max-[767px]:p-5 rounded-3xl border border-slate-200 shadow-sm space-y-10">
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
