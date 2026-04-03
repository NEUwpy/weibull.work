"use client"

import React from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSlug from 'rehype-slug'
import Link from 'next/link'
import { FileText, Activity, ArrowLeft } from 'lucide-react'
import { APP_VERSION } from '@/lib/config'

export default function ChangelogContent({ changelogBody, statusBody }: { changelogBody: string; statusBody: string }) {
  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      {/* Header */}
      <div className="mb-10">
        <div className="flex items-center gap-3 mb-2">
          <FileText size={28} className="text-blue-600" />
          <h1 className="text-2xl font-bold text-slate-900">更新日志</h1>
          <span className="text-sm text-slate-400 font-mono bg-slate-100 px-2 py-0.5 rounded">{APP_VERSION}</span>
        </div>
        <p className="text-slate-500">版本更新记录与功能建设状态</p>
      </div>

      {/* Version Changelog */}
      <section className="mb-12">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 rounded-lg text-white shadow-sm bg-blue-600 shadow-blue-200">
            <FileText size={18} />
          </div>
          <h2 className="text-lg font-bold text-slate-900">版本记录</h2>
        </div>
        <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-sm">
          <article className="prose prose-slate prose-base max-w-none prose-headings:scroll-mt-28 prose-headings:font-black prose-headings:text-slate-900 prose-h2:text-xl prose-p:text-slate-600 prose-p:leading-7 prose-strong:text-slate-900 prose-strong:font-bold">
            <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug]}>
              {changelogBody}
            </Markdown>
          </article>
        </div>
      </section>

      {/* Method Status */}
      <section className="mb-12">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 rounded-lg text-white shadow-sm bg-amber-600 shadow-amber-200">
            <Activity size={18} />
          </div>
          <h2 className="text-lg font-bold text-slate-900">功能状态</h2>
          <span className="text-xs text-slate-400">各方法各功能完成情况</span>
        </div>
        <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-sm">
          <article className="prose prose-slate prose-base max-w-none prose-headings:scroll-mt-28 prose-headings:font-black prose-headings:text-slate-900 prose-h2:text-xl prose-p:text-slate-600 prose-p:leading-7 prose-strong:text-slate-900 prose-strong:font-bold prose-table:text-sm prose-th:bg-slate-50 prose-th:px-3 prose-th:py-2 prose-td:px-3 prose-td:py-2 prose-th:border-b prose-td:border-b prose-td:border-slate-100">
            <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug]}>
              {statusBody}
            </Markdown>
          </article>
        </div>
      </section>

      {/* Navigation */}
      <div className="flex justify-between items-center py-4 border-t border-slate-200">
        <Link href="/help" className="text-sm text-blue-600 hover:text-blue-800 hover:underline flex items-center gap-1">
          <ArrowLeft size={14} />
          用户手册
        </Link>
        <Link href="/" className="text-sm text-blue-600 hover:text-blue-800 hover:underline">
          返回首页
        </Link>
      </div>
    </div>
  )
}
