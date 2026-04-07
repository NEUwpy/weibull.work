import Link from 'next/link'
import { BookOpen, FileText } from 'lucide-react'

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
          <p className="text-sm text-slate-500">软件介绍、模块概览、功能详解</p>
        </Link>
        <Link
          href="/help/changelog"
          className="group bg-white p-8 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md hover:border-amber-200 transition-all"
        >
          <div className="p-3 rounded-xl bg-amber-100 text-amber-600 w-fit mb-4 group-hover:bg-amber-600 group-hover:text-white transition-colors">
            <FileText size={24} />
          </div>
          <h2 className="text-lg font-bold text-slate-900 mb-2">更新日志</h2>
          <p className="text-sm text-slate-500">功能状态、版本记录、待办事项</p>
        </Link>
      </div>
    </div>
  )
}
