import React from 'react'
import Link from 'next/link'
import { INITIAL_METHOD_TREE } from '@/lib/methods'
import { ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

export default function MethodsPage() {
  return (
    <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12 space-y-4">
      {/* Method Categories - Horizontal Cards */}
      <div className="space-y-4">
        {INITIAL_METHOD_TREE.map((category, index) => (
          <div key={category.id} className="block group">
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 hover:shadow-md hover:border-amber-300 transition-all overflow-hidden">
              <div className="flex h-[140px]">
                {/* Left: Category Info (40%) - Clickable */}
                <Link
                  href={`/methods/${category.id}`}
                  className="w-[40%] min-w-[320px] flex bg-gradient-to-br from-amber-50 to-white border-r border-slate-100 hover:bg-amber-100/50 transition-colors"
                >
                  {/* Left Section: Icon + ShortName + Name (40%) */}
                  <div className="w-[40%] p-5 pr-4 pl-[60px] flex flex-col justify-center shrink-0">
                    <div className="flex items-center gap-2 mb-3">
                      {/* Number Icon */}
                      <div className="w-8 h-8 bg-amber-600 rounded-lg text-white shadow-sm shrink-0 flex items-center justify-center">
                        <span className="text-lg font-black leading-none" style={{ fontFamily: 'Georgia, serif' }}>
                          {index + 1}
                        </span>
                      </div>
                      <span className="text-[14px] font-mono font-bold text-amber-600 bg-amber-50 px-2 py-1 rounded border border-amber-100 leading-tight">
                        {category.shortName}
                      </span>
                    </div>
                    <div className="text-lg font-black text-slate-900 leading-tight">
                      {category.name}
                    </div>
                  </div>

                  {/* Vertical Divider */}
                  <div className="flex-none w-px bg-amber-200/50 my-5"></div>

                  {/* Right Section: Description (60%) */}
                  <div className="flex-1 p-5 pr-6 flex items-center">
                    <div className="text-sm text-slate-500 leading-relaxed">
                      {category.description}
                    </div>
                  </div>
                </Link>

                {/* Right: Methods List (60%) - Individual Links */}
                <div className="flex-1 p-6">
                  <div className="flex items-center gap-3 overflow-x-auto scrollbar-hide h-full">
                    {category.children && category.children.length > 0 ? (
                      category.children.map((method) => (
                        <Link
                          key={method.id}
                          href={`/methods/${method.id}`}
                          className="flex-none group/method"
                        >
                          <div className="px-7 py-4 bg-slate-50 hover:bg-amber-50 border border-slate-200 hover:border-amber-300 rounded-xl transition-all cursor-pointer">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-bold text-slate-700 group-hover/method:text-amber-700">
                                {method.shortName}
                              </span>
                            </div>
                            <div className="text-sm text-slate-400 font-mono">
                              {method.name}
                            </div>
                          </div>
                        </Link>
                      ))
                    ) : (
                      <div className="text-sm text-slate-400 italic">
                        暂无细分方法
                      </div>
                    )}
                    <div className="flex-none text-slate-300">
                      <ChevronRight size={20} />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
