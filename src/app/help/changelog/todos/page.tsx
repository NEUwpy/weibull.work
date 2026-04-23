import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'

type ShortItem = {
  text: string
  status: 'focus' | 'next' | 'todo' | 'count'
  current?: number
  total?: number
}

type ShortTerm = {
  label: string
  items: ShortItem[]
}

type MidTerm = {
  label: string
  shorts: ShortTerm[]
}

type LongTerm = {
  label: string
  desc: string
  mids: MidTerm[]
}

/**
 * Parse 04-目标与待办.md into a three-level structure.
 * ## → long-term, ### → mid-term, #### → short-term group.
 * Item status: `- [>]` focus, `- [!]` next, `- [ ]` todo.
 */
function parseTodos(markdown: string): LongTerm[] {
  const { content } = matter(markdown)
  const lines = content.split('\n')
  const results: LongTerm[] = []
  let currentLong: LongTerm | null = null
  let currentMid: MidTerm | null = null
  let currentShort: ShortTerm | null = null

  for (const line of lines) {
    const h2 = line.match(/^## (.+)$/)
    if (h2) {
      const parts = h2[1].split('：', 2)
      currentLong = { label: parts[0].trim(), desc: parts[1]?.trim() || '', mids: [] }
      results.push(currentLong)
      currentMid = null
      currentShort = null
      continue
    }

    const h3 = line.match(/^### (.+)$/)
    if (h3) {
      if (!currentLong) continue
      currentMid = { label: h3[1].trim(), shorts: [] }
      currentLong.mids.push(currentMid)
      currentShort = null
      continue
    }

    const h4 = line.match(/^#### (.+)$/)
    if (h4) {
      if (!currentMid) continue
      currentShort = { label: h4[1].trim(), items: [] }
      currentMid.shorts.push(currentShort)
      continue
    }

    // - [>] focus, - [!] next, - [ ] todo, - [x/y] count
    const focusMatch = line.match(/^- \[>\] (.+)$/)
    if (focusMatch && currentShort) {
      currentShort.items.push({ text: focusMatch[1].trim(), status: 'focus' })
      continue
    }
    const nextMatch = line.match(/^- \[!\] (.+)$/)
    if (nextMatch && currentShort) {
      currentShort.items.push({ text: nextMatch[1].trim(), status: 'next' })
      continue
    }
    const todoMatch = line.match(/^- \[ \] (.+)$/)
    if (todoMatch && currentShort) {
      currentShort.items.push({ text: todoMatch[1].trim(), status: 'todo' })
      continue
    }
    const countMatch = line.match(/^- \[(\d+)\/(\d+)\] (.+)$/)
    if (countMatch && currentShort) {
      currentShort.items.push({
        text: countMatch[3].trim(),
        status: 'count',
        current: parseInt(countMatch[1], 10),
        total: parseInt(countMatch[2], 10),
      })
    }
  }
  return results
}

const LONG_STYLES: Record<string, { badge: string; dot: string; border: string }> = {
  '智能算法推荐': { badge: 'bg-blue-100 text-blue-700', dot: 'bg-blue-400', border: 'border-blue-100' },
  '人工智能方法优化': { badge: 'bg-violet-100 text-violet-700', dot: 'bg-violet-400', border: 'border-violet-100' },
  'RAG 智能问答': { badge: 'bg-emerald-100 text-emerald-700', dot: 'bg-emerald-400', border: 'border-emerald-100' },
  '完善方法系统': { badge: 'bg-amber-100 text-amber-700', dot: 'bg-amber-400', border: 'border-amber-100' },
  '完善文献库与案例库': { badge: 'bg-rose-100 text-rose-700', dot: 'bg-rose-400', border: 'border-rose-100' },
}
const DEFAULT_STYLE = { badge: 'bg-slate-100 text-slate-700', dot: 'bg-slate-400', border: 'border-slate-100' }

const ITEM_BORDER: Record<string, string> = {
  focus: 'border-2 border-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.4)]',
  next: 'border-2 border-amber-400',
  todo: 'border border-slate-200',
  count: 'border border-sky-200 bg-sky-50/30',
}

const ITEM_BADGE: Record<string, { text: string; cls: string }> = {
  focus: { text: '聚焦中', cls: 'bg-emerald-100 text-emerald-700' },
  next: { text: '下一个', cls: 'bg-amber-100 text-amber-700' },
  todo: { text: '待完成', cls: 'bg-slate-100 text-slate-400' },
  count: { text: '', cls: 'bg-sky-100 text-sky-700' },
}

export default function TodosPage() {
  const raw = fs.readFileSync(path.join(process.cwd(), '04-目标与待办.md'), 'utf-8')
  const PHASES = parseTodos(raw)

  return (
    <div className="bg-white p-10 rounded-3xl border border-slate-200 shadow-sm space-y-12">
      {/* 标题 */}
      <div>
        <h1 className="text-2xl font-black text-slate-900 mb-2">更新计划</h1>
        <p className="text-slate-500">后续开发方向与待办事项</p>
      </div>

      {/* 长期目标 */}
      <div className="space-y-10">
        {PHASES.map(phase => {
          const style = LONG_STYLES[phase.label] || DEFAULT_STYLE
          return (
            <section key={phase.label}>
              {/* 长期标题 */}
              <div className="flex items-center gap-3 mb-4">
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${style.badge}`}>
                  长期
                </span>
                <span className="text-base font-bold text-slate-900">{phase.label}</span>
                {phase.desc && (
                  <span className="text-xs text-slate-400">— {phase.desc}</span>
                )}
              </div>

              {/* 中期目标 */}
              <div className="space-y-6 ml-2">
                {phase.mids.map(mid => (
                  <div key={mid.label} className={`pl-4 border-l-2 ${style.border}`}>
                    <div className="flex items-center gap-2 mb-3">
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${style.badge}`}>
                        中期
                      </span>
                      <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
                      <span className="text-sm font-semibold text-slate-700">{mid.label}</span>
                    </div>

                    {/* 短期条目：卡片样式，按 #### 分组但不显示标题 */}
                    <div className="space-y-2 ml-3">
                      {mid.shorts.map(short => (
                        short.items.map(item => (
                          <div
                            key={item.text}
                            className={`flex items-center gap-3 py-2.5 px-4 rounded-xl bg-white ${ITEM_BORDER[item.status]}`}
                          >
                            <span className={`shrink-0 w-2 h-2 rounded-full ${
                              item.status === 'focus' ? 'bg-emerald-500' :
                              item.status === 'next' ? 'bg-amber-400' :
                              item.status === 'count' ? 'bg-sky-400' : style.dot
                            }`} />
                            <span className={`text-sm ${
                              item.status === 'focus' ? 'text-slate-800 font-medium' :
                              item.status === 'next' ? 'text-slate-600' :
                              item.status === 'count' ? 'text-slate-700' : 'text-slate-400'
                            }`}>
                              {item.text}
                            </span>
                            {short.label && item.status !== 'focus' && item.status !== 'next' && item.status !== 'count' && (
                              <span className="text-[10px] text-slate-300 bg-slate-50 px-1.5 py-0.5 rounded shrink-0">
                                {short.label}
                              </span>
                            )}
                            <span className={`ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0 ${ITEM_BADGE[item.status].cls}`}>
                              {item.status === 'count' && item.current !== undefined && item.total !== undefined ? `${item.current}/${item.total}` : ITEM_BADGE[item.status].text}
                            </span>
                          </div>
                        ))
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )
        })}
      </div>
    </div>
  )
}
