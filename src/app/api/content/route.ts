import { NextRequest, NextResponse } from 'next/server'
import { isContentSlug } from '@/lib/server/content-files'
import { LibraryConfigurationError, readPaper } from '@/lib/server/literature'

export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const slug = searchParams.get('slug')
  const type = searchParams.get('type')
  if (!slug || !type) return new NextResponse('Missing parameters', { status: 400 })
  if (!isContentSlug(slug) || !['翻译', '原文'].includes(type)) {
    return new NextResponse('Invalid content identifier', { status: 400 })
  }
  try {
    const content = readPaper(slug, type as '翻译' | '原文')
    if (content === null) return new NextResponse('File not found', { status: 404 })
    return new NextResponse(content, { headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' } })
  } catch (error) {
    console.error('Literature content read failed:', error)
    return new NextResponse('文献库暂时不可用', { status: error instanceof LibraryConfigurationError ? 503 : 500 })
  }
}
