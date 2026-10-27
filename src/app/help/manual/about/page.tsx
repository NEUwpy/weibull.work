import {
  Calculator,
  Settings2,
  Brain,
  Database,
  Library,
  Zap,
  Search,
  BookOpen,
  FolderOpen,
  Link2,
} from 'lucide-react'

const CORE_FEATURES = [
  {
    icon: Zap,
    title: '直接计算',
    desc: '输入失效数据，即可获得威布尔参数估计值和概率分布图',
    color: 'bg-blue-100 text-blue-600',
  },
  {
    icon: Search,
    title: '深入研究参数估计方法',
    desc: '原理文档、程序流程、计算过程、结果分析、适用范围、可信性验证',
    color: 'bg-amber-100 text-amber-600',
  },
  {
    icon: Brain,
    title: '结合人工智能方法辅助',
    desc: 'RAG 智能问答、智能优化算法辅助参数估计',
    color: 'bg-violet-100 text-violet-600',
    badge: '规划中',
  },
  {
    icon: FolderOpen,
    title: '方便存储调用的寿命数据库',
    desc: '标准失效数据集，支持按行业、样本量检索，一键调用到计算器',
    color: 'bg-indigo-100 text-indigo-600',
  },
  {
    icon: Link2,
    title: '方法和数据的文献支撑',
    desc: '学术文献管理与阅读，支持双语切换，为方法和案例提供理论依据',
    color: 'bg-emerald-100 text-emerald-600',
  },
]

const MODULES = [
  {
    icon: Calculator,
    name: '威布尔计算器',
    desc: '交互式参数估计，支持多方法对比，一键出图',
    color: 'border-blue-200 bg-blue-50/50',
  },
  {
    icon: Settings2,
    name: '参数估计方法',
    desc: '25+ 种估计方法的全方位分析：原理、流程、过程、分析、适用范围、验证',
    color: 'border-amber-200 bg-amber-50/50',
  },
  {
    icon: Brain,
    name: '人工智能方法',
    desc: 'RAG 智能问答、智能优化算法辅助、神经网络增强',
    color: 'border-violet-200 bg-violet-50/50',
    badge: '规划中',
  },
  {
    icon: Database,
    name: '案例数据库',
    desc: '科研文献中的标准失效数据集，多维检索，一键调用',
    color: 'border-indigo-200 bg-indigo-50/50',
  },
  {
    icon: Library,
    name: '可靠性图书馆',
    desc: 'Markdown 文献阅读，双语切换，参考文献跳转',
    color: 'border-emerald-200 bg-emerald-50/50',
  },
]

export default function AboutPage() {
  return (
    <div className="bg-white p-10 rounded-3xl border border-slate-200 shadow-sm space-y-16">
      {/* 一句话定义 */}
      <section className="text-center py-8">
        <h1 className="text-3xl font-black text-slate-900 leading-snug">
          集计算、方法研究、人工智能方法辅助、案例数据库及文献支撑于一体的
          <br />
          <span className="text-blue-600">威布尔参数估计研究平台</span>
        </h1>
        <p className="mt-4 text-slate-500 text-lg">
          为可靠性工程师和研究者提供从方法选型到结果验证的完整工作流
        </p>
      </section>

      {/* 五大核心功能 */}
      <section>
        <h2 className="text-2xl font-black text-slate-900 mb-8 text-center">核心功能</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {CORE_FEATURES.map(feat => (
            <div
              key={feat.title}
              className="relative p-6 rounded-2xl border border-slate-200 hover:border-slate-300 hover:shadow-sm transition-all"
            >
              {feat.badge && (
                <span className="absolute top-4 right-4 text-[10px] font-bold text-violet-600 bg-violet-100 px-2 py-0.5 rounded-full">
                  {feat.badge}
                </span>
              )}
              <div className={`p-2.5 rounded-xl w-fit mb-4 ${feat.color}`}>
                <feat.icon size={20} />
              </div>
              <h3 className="text-base font-bold text-slate-900 mb-1.5">{feat.title}</h3>
              <p className="text-sm text-slate-500 leading-relaxed">{feat.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 五大模块结构 */}
      <section>
        <h2 className="text-2xl font-black text-slate-900 mb-8 text-center">模块结构</h2>
        <div className="space-y-4">
          {MODULES.map(mod => (
            <div
              key={mod.name}
              className={`relative flex items-center gap-5 p-5 rounded-2xl border ${mod.color} transition-all`}
            >
              {mod.badge && (
                <span className="absolute top-3 right-4 text-[10px] font-bold text-violet-600 bg-violet-100 px-2 py-0.5 rounded-full">
                  {mod.badge}
                </span>
              )}
              <div className="shrink-0 p-2.5 rounded-xl bg-white shadow-sm border border-slate-200/50">
                <mod.icon size={20} className="text-slate-700" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">{mod.name}</h3>
                <p className="text-sm text-slate-500 leading-relaxed">{mod.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 在线访问 */}
      <section className="text-center pt-4 border-t border-slate-100">
        <p className="text-sm text-slate-400">
          在线访问：<a href="https://weibull.work" className="text-blue-600 hover:underline font-medium">weibull.work</a>
        </p>
      </section>
    </div>
  )
}
