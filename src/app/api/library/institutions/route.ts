import { NextResponse } from 'next/server'
import { libraryInstitutionIdentity, libraryPapersByInstitution } from '@/lib/library-institutions'
import { compareLibraryOrder } from '@/lib/library-sort'
import { LibraryConfigurationError, listPapers } from '@/lib/server/literature'

export const dynamic = 'force-dynamic'

export async function GET(request: Request) {
  const name = new URL(request.url).searchParams.get('name')?.trim()
  if (!name || name.length > 1000) return NextResponse.json({ error: '请提供有效的单位名称。' }, { status: 400 })
  try {
    const catalog = listPapers()
    const papers = libraryPapersByInstitution(catalog, name).sort((a, b) => compareLibraryOrder(a, b, 'year-desc'))
    if (!papers.length) return NextResponse.json({ error: '未找到该单位的在库文献。' }, { status: 404 })
    return NextResponse.json({ institution: libraryInstitutionIdentity(name, catalog), papers }, { headers: { 'Cache-Control': 'no-store' } })
  } catch (error) {
    console.error('Library institution read failed:', error instanceof Error ? error.name : 'Unknown error')
    return NextResponse.json({ error: '单位资料暂时不可用，请稍后重试。' }, { status: error instanceof LibraryConfigurationError ? 503 : 500 })
  }
}
