import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSlug from 'rehype-slug'
import { extractFromHeading, stripBlockquotes } from '@/lib/markdown'

function readDoc(filename: string): string {
  return fs.readFileSync(path.join(process.cwd(), filename), 'utf-8')
}

export default function FeaturesPage() {
  const { content } = matter(readDoc('07-用户手册.md'))
  const body = stripBlockquotes(extractFromHeading(content, '功能详解'))

  return (
    <div className="bg-white p-10 rounded-3xl border border-slate-200 shadow-sm">
      <article className="prose prose-slate prose-base max-w-none prose-headings:scroll-mt-28 prose-headings:font-black prose-headings:tracking-tight prose-headings:text-slate-900 prose-h1:text-3xl prose-h2:text-2xl prose-h3:text-xl prose-h4:text-lg prose-p:text-slate-600 prose-p:leading-7 prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline prose-strong:text-slate-900 prose-strong:font-bold prose-table:text-sm">
        <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug]}>
          {body}
        </Markdown>
      </article>
    </div>
  )
}
