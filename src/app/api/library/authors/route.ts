import { NextResponse } from 'next/server'
import { libraryAuthorIdentity, libraryAuthorNames, libraryPapersByAuthor } from '@/lib/library-authors'
import { compareLibraryOrder } from '@/lib/library-sort'
import { LibraryConfigurationError, listPapers } from '@/lib/server/literature'

export const dynamic = 'force-dynamic'

export async function GET(request: Request) {
  const name = new URL(request.url).searchParams.get('name')?.trim()
  if (!name || name.length > 200) return NextResponse.json({ error: '请提供有效的作者姓名。' }, { status: 400 })
  try {
    const catalog = listPapers()
    const papers = libraryPapersByAuthor(catalog, name).sort((a, b) => compareLibraryOrder(a, b, 'year-desc'))
    if (!papers.length) return NextResponse.json({ error: '未找到该作者的在库文献。' }, { status: 404 })
    const author = libraryAuthorIdentity(name, catalog)
    if (!author.affiliations.length) {
      for (const paper of papers) {
        if (paper.credits) continue // Structured unit assignments must be explicit.
        const names = libraryAuthorNames(paper.author)
        const signature = names.find(value => libraryAuthorIdentity(value).key === author.key) || ''
        const annotation = /[（(]([^）)]+)[）)]/.exec(signature)?.[1]
        const unit = annotation && /大学|学院|公司|实验室|研究|university|univ\.|institute|college|department|cent(?:er|re)|laboratory|school|IBM|USGS/i.test(annotation)
          ? annotation.replace(/^[\u3400-\u9fff]{2,5}[，,]\s*/, '')
          : names.length === 1 && !/(?:et\s+al|等)/i.test(paper.author) ? paper.affiliation : undefined
        if (unit && !author.affiliations.some(item => item.name === unit)) author.affiliations.push({ name: unit, slug: paper.slug, year: paper.year })
      }
    }
    return NextResponse.json({ author, papers }, { headers: { 'Cache-Control': 'no-store' } })
  } catch (error) {
    console.error('Library author read failed:', error instanceof Error ? error.name : 'Unknown error')
    return NextResponse.json({ error: '作者资料暂时不可用，请稍后重试。' }, { status: error instanceof LibraryConfigurationError ? 503 : 500 })
  }
}
