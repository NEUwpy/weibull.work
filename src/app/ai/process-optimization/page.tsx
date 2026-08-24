import Link from 'next/link'
import { ArrowLeft, ArrowRight, Gauge, SlidersHorizontal } from 'lucide-react'

export default function ProcessOptimizationPage() {
  return (
    <section className="mx-auto w-full max-w-[1500px] space-y-7 px-8 py-10 pl-[4.5rem]">
      <header className="space-y-3">
        <Link href="/ai" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-600">
          <ArrowLeft size={14} /> 返回人工智能方法
        </Link>
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-violet-600 p-2.5 text-white"><Gauge size={22} /></div>
          <div>
            <h1 className="text-xl font-black text-slate-900">过程量优化</h1>
            <p className="text-sm text-slate-500">AI 为已选参数估计方法配置内部过程量</p>
          </div>
        </div>
      </header>

      <Link href="/ai/process-optimization/mdm" className="group block max-w-3xl">
        <article className="rounded-2xl border border-violet-200 bg-white p-6 shadow-sm transition-all hover:border-violet-400 hover:shadow-md">
          <div className="flex items-start justify-between gap-5">
            <div className="flex gap-4">
              <div className="rounded-xl bg-violet-50 p-3 text-violet-600"><SlidersHorizontal size={22} /></div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-black text-slate-900">最小差异法（MDM）</h2>
                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-bold text-emerald-700">可用</span>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-slate-500">
                  根据当前失效样本预测不同偏移量 δ 的损失，选择预测损失最低的候选值，再执行标准 MDM 参数估计。
                </p>
              </div>
            </div>
            <ArrowRight className="mt-2 shrink-0 text-slate-300 transition-colors group-hover:text-violet-600" size={20} />
          </div>
        </article>
      </Link>
    </section>
  )
}
