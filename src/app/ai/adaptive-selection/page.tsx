import Link from 'next/link'
import { ArrowLeft, Network } from 'lucide-react'

export default function AdaptiveSelectionPage() {
  return (
    <section className="mx-auto w-full max-w-[1200px] space-y-7 px-8 py-10 pl-[4.5rem]">
      <Link href="/ai" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-600">
        <ArrowLeft size={14} /> 返回人工智能方法
      </Link>
      <div className="rounded-2xl border border-amber-200 bg-white p-8 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-amber-50 p-3 text-amber-600"><Network size={23} /></div>
          <div>
            <h1 className="text-xl font-black text-slate-900">自适应选择</h1>
            <p className="text-sm text-slate-500">在候选估计方法或策略之间进行样本自适应选择</p>
          </div>
        </div>
        <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-5 text-sm leading-relaxed text-slate-600">
          当前仍在建立可部署的选择和回退规则。现有证据尚不足以向用户自动推荐“最佳估计方法”，
          因此本页面暂不提供在线决策功能。
        </div>
      </div>
    </section>
  )
}
