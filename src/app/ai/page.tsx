import Link from 'next/link'
import { ArrowRight, Brain, Gauge, Network, Target } from 'lucide-react'


const modules = [
  {
    href: '/ai/process-optimization',
    title: '过程量优化',
    description: '方法保持不变，由 AI 为当前样本选择方法内部的过程量。当前已接入 MDM 偏移量优化。',
    status: '可用',
    icon: Gauge,
    color: 'violet',
  },
  {
    href: '/ai/direct-estimation',
    title: '直接估计',
    description: '从样本直接输出 Weibull 参数估计，用于探索端到端估计路线。',
    status: '原型',
    icon: Target,
    color: 'cyan',
  },
  {
    href: '/ai/adaptive-selection',
    title: '自适应选择',
    description: '根据当前样本与工程任务，在候选估计方法或策略之间作有边界的选择。',
    status: '建设中',
    icon: Network,
    color: 'amber',
  },
] as const


const colorClasses = {
  violet: 'border-violet-200 bg-violet-50 text-violet-700',
  cyan: 'border-cyan-200 bg-cyan-50 text-cyan-700',
  amber: 'border-amber-200 bg-amber-50 text-amber-700',
}

export default function AIPage() {
  return (
    <section className="mx-auto w-full max-w-[1500px] space-y-8 px-8 py-12 pl-[4.5rem]">
      <header className="space-y-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-violet-600 p-2.5 text-white shadow-sm">
            <Brain size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-black text-slate-900">人工智能方法</h1>
            <p className="text-sm font-medium text-slate-500">AI-assisted Weibull estimation</p>
          </div>
        </div>
        <p className="max-w-3xl text-sm leading-relaxed text-slate-600">
          AI 可以优化传统方法内部的过程量、直接估计参数，或在多个候选策略之间进行自适应选择。
          每项能力都单独说明输入、选择过程和适用边界。
        </p>
      </header>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {modules.map(module => {
          const Icon = module.icon
          return (
            <Link key={module.href} href={module.href} className="group">
              <article className="flex h-full flex-col rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition-all hover:-translate-y-0.5 hover:border-violet-300 hover:shadow-md">
                <div className="mb-5 flex items-center justify-between">
                  <div className={`rounded-xl border p-2.5 ${colorClasses[module.color]}`}>
                    <Icon size={21} />
                  </div>
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-500">
                    {module.status}
                  </span>
                </div>
                <h2 className="text-lg font-black text-slate-900">{module.title}</h2>
                <p className="mt-2 flex-1 text-sm leading-relaxed text-slate-500">{module.description}</p>
                <div className="mt-5 flex items-center justify-end gap-1 text-sm font-bold text-violet-600">
                  进入 <ArrowRight size={15} />
                </div>
              </article>
            </Link>
          )
        })}
      </div>
    </section>
  )
}
