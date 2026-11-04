import { NextResponse } from 'next/server'
import { isContentSlug } from '@/lib/server/content-files'
import { LibraryConfigurationError, readPaperMetadata } from '@/lib/server/literature'

export const dynamic = 'force-dynamic'

export async function GET(_request: Request, { params }: { params: { slug: string } }) {
  if (!isContentSlug(params.slug)) return NextResponse.json({ error: 'Invalid paper identifier' }, { status: 400 })
  try {
    const paper = readPaperMetadata(params.slug)
    if (!paper) return NextResponse.json({ error: '文献未找到。' }, { status: 404 })
    const { slug, title, title_en, display_title, original_title, original_language, author, doi, affiliation, publication, short_publication, type, year, tags, summary, related_method_id, category } = paper
    return NextResponse.json({ paper: { slug, title, title_en, display_title, original_title, original_language, author, doi, affiliation, publication, short_publication, type, year, tags, summary, related_method_id, category },
      versions: paper.availableVersions }, { headers: { 'Cache-Control': 'no-store' } })
  } catch (error) {
    console.error('Library metadata read failed:', error instanceof Error ? error.name : 'Unknown error')
    return NextResponse.json({ error: '文献信息暂时不可用，请稍后重试。' }, { status: error instanceof LibraryConfigurationError ? 503 : 500 })
  }
}
