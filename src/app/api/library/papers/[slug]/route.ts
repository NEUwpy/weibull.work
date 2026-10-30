import { NextResponse } from 'next/server'
import { isContentSlug } from '@/lib/server/content-files'
import { LibraryConfigurationError, getLibraryPaths, readLibraryDocuments } from '@/lib/server/literature'

export const dynamic = 'force-dynamic'

export async function GET(_request: Request, { params }: { params: { slug: string } }) {
  if (!isContentSlug(params.slug)) return NextResponse.json({ error: 'Invalid paper identifier' }, { status: 400 })
  try {
    const slug = params.slug === '144-003' && getLibraryPaths().mode === 'source' ? '171-003' : params.slug
    const documents = readLibraryDocuments().filter(document => document.paper.slug === slug)
    if (!documents.length) return NextResponse.json({ error: '文献未找到。' }, { status: 404 })
    const { title, title_en, author, doi, affiliation, publication, short_publication, type, year, tags, summary, related_method_id } = documents[0].paper
    return NextResponse.json({ paper: { slug, title, title_en, author, doi, affiliation, publication, short_publication, type, year, tags, summary, related_method_id },
      versions: documents.map(document => document.version) }, { headers: { 'Cache-Control': 'no-store' } })
  } catch (error) {
    console.error('Library metadata read failed:', error instanceof Error ? error.name : 'Unknown error')
    return NextResponse.json({ error: '文献信息暂时不可用，请稍后重试。' }, { status: error instanceof LibraryConfigurationError ? 503 : 500 })
  }
}
