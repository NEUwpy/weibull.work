import Link from 'next/link'
import { BookOpen, FileText, BarChart3, GitBranch } from 'lucide-react'

export default function HelpPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-20">
      <div className="text-center mb-12">
        <h1 className="text-3xl font-black text-slate-900 mb-3">帮助中心</h1>
        <p className="text-slate-500">了解平台功能、查阅更新记录</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        <Link
          href="/help/manual/about"
          className="group bg-white p-8 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md hover:border-blue-200 transition-all"
        >
          <div className="p-3 rounded-xl bg-blue-100 text-blue-600 w-fit mb-4 group-hover:bg-blue-600 group-hover:text-white transition-colors">
            <BookOpen size={24} />
          </div>
          <h2 className="text-lg font-bold text-slate-900 mb-2">用户手册</h2>
          <p className="text-sm text-slate-500">软件结构、功能详情、工作流介绍</p>
        </Link>
        <Link
          href="/help/changelog"
          className="group bg-white p-8 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md hover:border-amber-200 transition-all"
        >
          <div className="p-3 rounded-xl bg-amber-100 text-amber-600 w-fit mb-4 group-hover:bg-amber-600 group-hover:text-white transition-colors">
            <FileText size={24} />
          </div>
          <h2 className="text-lg font-bold text-slate-900 mb-2">更新日志</h2>
          <p className="text-sm text-slate-500">功能状态、版本记录、更新计划</p>
        </Link>
        <Link
          href="/help/metrics"
          className="group bg-white p-8 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md hover:border-emerald-200 transition-all"
        >
          <div className="p-3 rounded-xl bg-emerald-100 text-emerald-600 w-fit mb-4 group-hover:bg-emerald-600 group-hover:text-white transition-colors">
            <BarChart3 size={24} />
          </div>
          <h2 className="text-lg font-bold text-slate-900 mb-2">指标规范</h2>
          <p className="text-sm text-slate-500">评价指标定义、公式、模块使用图谱</p>
        </Link>
        <Link
          href="/help/charts"
          className="group bg-white p-8 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md hover:border-violet-200 transition-all"
        >
          <div className="p-3 rounded-xl bg-violet-100 text-violet-600 w-fit mb-4 group-hover:bg-violet-600 group-hover:text-white transition-colors">
            <GitBranch size={24} />
          </div>
          <h2 className="text-lg font-bold text-slate-900 mb-2">图表规范</h2>
          <p className="text-sm text-slate-500">图表组件清单、使用图谱、配色规范</p>
        </Link>
      </div>
    </div>
  )
}
