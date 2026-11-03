import { NextRequest, NextResponse } from 'next/server'
import { LibraryConfigurationError } from '@/lib/server/literature'
import { searchLibrary, startLibrarySearchPrewarm, type LibrarySearchOptions } from '@/lib/server/library-search'
import { validLibraryCategoryFilter } from '@/lib/library-categories'
import { isLibrarySort } from '@/lib/library-sort'

export const dynamic = 'force-dynamic'

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams
  const query = params.get('q') ?? ''
  const type = params.get('type') ?? 'all'
  const scope = params.get('scope') ?? 'auto'
  const category = params.get('category') ?? 'all'
  const sort = params.get('sort') ?? 'relevance'
  const limit = params.has('limit') ? Number(params.get('limit')) : 10
  const offset = params.has('offset') ? Number(params.get('offset')) : 0
  if (query.length > 2000 || !isLibrarySort(sort) || !validLibraryCategoryFilter(category) || !['all', 'book', 'paper', 'journal', 'journal-conf'].includes(type) || !['auto', 'text'].includes(scope) || !Number.isInteger(limit) || limit < 1 || limit > 30 || !Number.isInteger(offset) || offset < 0) {
    return NextResponse.json({ error: '检索参数无效，请缩短检索内容或检查分页。' }, { status: 400 })
  }
  try {
    if (query.trim()) await startLibrarySearchPrewarm()
    const result = searchLibrary(query, { limit, offset, category, sort, type: type as LibrarySearchOptions['type'], scope: scope as LibrarySearchOptions['scope'] })
    return NextResponse.json({ ...result, results: result.results.map(({ text: _text, context: _context,
      contextStartLine: _start, contextEndLine: _end, ...hit }) => hit) }, { headers: { 'Cache-Control': 'no-store' } })
  } catch (error) {
    console.error('Library search failed:', error instanceof Error ? error.name : 'Unknown error')
    return NextResponse.json({ error: '文献检索暂时不可用，请稍后重试。' }, { status: error instanceof LibraryConfigurationError ? 503 : 500 })
  }
}
