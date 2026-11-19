import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSlug from 'rehype-slug'
import { APP_VERSION } from '@/lib/config'

const recentVersionLimit = 10
const articleClass = 'prose prose-slate prose-base max-w-none prose-headings:scroll-mt-28 prose-headings:font-black prose-headings:text-slate-900 prose-h2:text-xl prose-p:text-slate-600 prose-p:leading-7 prose-strong:text-slate-900 prose-strong:font-bold'

function readDoc(filename: string): string {
  return fs.readFileSync(path.join(process.cwd(), filename), 'utf-8')
}

export default function VersionsPage() {
  const { content } = matter(readDoc('08-更新日志.md'))
  const versions = Array.from(content.matchAll(/^## v\d[^\r\n]*/gm))
  const historyStart = versions[recentVersionLimit]?.index ?? content.length
  const recent = content.slice(0, historyStart)
  const history = content.slice(historyStart)

  return (
    <div className="bg-white p-10 max-[767px]:p-5 rounded-3xl border border-slate-200 shadow-sm">
      <div className="flex items-center gap-3 mb-6">
        <span className="text-sm text-slate-400 font-mono bg-slate-100 px-2 py-0.5 rounded">{APP_VERSION}</span>
        <span className="text-xs text-slate-400">当前版本</span>
      </div>
      <article className={articleClass}>
        <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug]}>
          {recent}
        </Markdown>
      </article>
      {history && (
        <details className="mt-8 rounded-xl border border-slate-200 bg-slate-50/50">
          <summary className="cursor-pointer px-4 py-3 font-medium text-slate-700">
            较早版本（{versions.length - recentVersionLimit}）
          </summary>
          <article className={`${articleClass} px-4 pb-4`}>
            <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug]}>
              {history}
            </Markdown>
          </article>
        </details>
      )}
    </div>
  )
}
