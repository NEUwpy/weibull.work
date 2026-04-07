import fs from 'fs'
import path from 'path'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSlug from 'rehype-slug'
import { stripBlockquotes } from '@/lib/markdown'

function readDoc(filename: string): string {
  return fs.readFileSync(path.join(process.cwd(), filename), 'utf-8')
}

export default function TodosPage() {
  const body = stripBlockquotes(readDoc('04-目标与待办.md'))

  return (
    <div className="bg-white p-10 rounded-3xl border border-slate-200 shadow-sm">
      <article className="prose prose-slate prose-base max-w-none prose-headings:scroll-mt-28 prose-headings:font-black prose-headings:text-slate-900 prose-h2:text-2xl prose-h3:text-xl prose-p:text-slate-600 prose-p:leading-7 prose-strong:text-slate-900 prose-strong:font-bold prose-table:text-sm">
        <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug]}>
          {body}
        </Markdown>
      </article>
    </div>
  )
}
