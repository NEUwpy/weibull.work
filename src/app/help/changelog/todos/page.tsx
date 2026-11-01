import fs from 'fs'
import path from 'path'
import Link from 'next/link'
import { parseUpdatePlan, type PlanStatus } from '@/lib/update-plan'

const STATUS_STYLE: Record<PlanStatus, string> = {
  待开始: 'bg-slate-100 text-slate-600',
  进行中: 'bg-blue-50 text-blue-700',
  已完成: 'bg-emerald-50 text-emerald-700',
  已取消: 'bg-slate-100 text-slate-500',
}

export default function TodosPage() {
  const raw = fs.readFileSync(path.join(process.cwd(), '04-目标与待办.md'), 'utf-8')
  const plan = parseUpdatePlan(raw)

  return (
    <div className="min-w-0 rounded-3xl border border-slate-200 bg-white p-10 max-[767px]:p-5">
      <header className="mb-9 border-b border-slate-100 pb-6">
        <div className="flex flex-wrap items-baseline justify-between gap-x-5 gap-y-2">
          <h1 className="text-2xl font-black text-slate-900">更新计划</h1>
          {plan.updatedAt && (
            <p className="text-xs text-slate-500">最近整理 <time dateTime={plan.updatedAt}>{plan.updatedAt}</time></p>
          )}
        </div>
        <p className="mt-3 text-sm leading-6 text-slate-600">按事项确认日期倒序排列，列出具体问题与完成条件。</p>
      </header>

      <div className="space-y-10">
        {plan.groups.map(group => (
          <section key={group.date} aria-label={`${group.date} 确认的事项`} className="grid min-w-0 grid-cols-[7rem_minmax(0,1fr)] gap-6 max-[767px]:grid-cols-1 max-[767px]:gap-4">
            <h2 className="pt-1 text-sm font-bold tabular-nums text-slate-700">
              <time dateTime={group.date}>{group.date}</time>
            </h2>
            <div className="min-w-0 space-y-5 border-l border-slate-200 pl-6 max-[767px]:pl-4">
              {group.tasks.map((task, index) => (
                <article key={`${task.title}-${index}`} className={`relative min-w-0 rounded-xl border p-5 max-[767px]:p-4 ${task.focus ? 'border-amber-200 bg-amber-50/50' : 'border-slate-200 bg-white'}`}>
                  <span aria-hidden="true" className={`absolute -left-[29px] top-6 h-2 w-2 rounded-full ring-4 ring-white max-[767px]:-left-[21px] ${task.focus ? 'bg-amber-500' : 'bg-slate-300'}`} />
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <h3 className="min-w-0 flex-1 break-words text-base font-bold leading-6 text-slate-900">{task.title}</h3>
                    <div className="flex shrink-0 flex-wrap gap-2">
                      {task.focus && <span className="rounded-md bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-800">当前重点</span>}
                      <span className={`rounded-md px-2 py-1 text-xs font-medium ${STATUS_STYLE[task.status]}`}>{task.status}</span>
                    </div>
                  </div>
                  <dl className="mt-4 space-y-3 text-sm leading-6">
                    {task.problem && (
                      <div>
                        <dt className="text-xs font-medium text-slate-500">问题</dt>
                        <dd className="mt-1 break-words text-slate-700">{task.problem}</dd>
                      </div>
                    )}
                    {task.acceptance && (
                      <div>
                        <dt className="text-xs font-medium text-slate-500">完成条件</dt>
                        <dd className="mt-1 break-words text-slate-700">{task.acceptance}</dd>
                      </div>
                    )}
                    {task.dependency && (
                      <div>
                        <dt className="text-xs font-medium text-slate-500">依赖</dt>
                        <dd className="mt-1 break-words text-slate-600">{task.dependency}</dd>
                      </div>
                    )}
                  </dl>
                </article>
              ))}
            </div>
          </section>
        ))}
        {plan.groups.length === 0 && <p className="text-sm text-slate-500">暂无已确认日期的更新事项。</p>}
      </div>

      {plan.backlog.length > 0 && (
        <details className="mt-10 rounded-xl border border-slate-200 bg-slate-50/50 p-5 max-[767px]:p-4">
          <summary className="cursor-pointer text-sm font-bold text-slate-700">历史待梳理 <span className="ml-2 font-normal text-slate-500">{plan.backlog.length} 项</span></summary>
          <p className="mt-3 text-xs leading-5 text-slate-500">这些旧条目缺少确认日期或具体范围，明确后再加入日期清单。</p>
          <ul className="mt-4 space-y-3 pl-5 text-sm leading-6 text-slate-600 marker:text-slate-400 list-disc">
            {plan.backlog.map((item, index) => <li key={index} className="break-words">{item}</li>)}
          </ul>
        </details>
      )}

      <footer className="mt-8 flex flex-wrap gap-x-5 gap-y-2 border-t border-slate-100 pt-5 text-sm">
        <Link href="/help/changelog" className="text-slate-500 hover:text-blue-600">查看功能状态</Link>
        <Link href="/help/changelog/versions" className="text-slate-500 hover:text-blue-600">查看版本记录</Link>
      </footer>
    </div>
  )
}
