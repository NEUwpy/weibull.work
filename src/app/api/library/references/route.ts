import { NextRequest, NextResponse } from 'next/server'
import { isContentSlug } from '@/lib/server/content-files'
import { LibraryConfigurationError, readReferences } from '@/lib/server/literature'

export const dynamic = 'force-dynamic'

export async function GET(request: NextRequest) {
  const slug = request.nextUrl.searchParams.get('slug')
  if (!slug || !isContentSlug(slug)) return NextResponse.json({ error: 'Invalid paper identifier' }, { status: 400 })
  try {
    return NextResponse.json(readReferences(slug), { headers: { 'Cache-Control': 'no-store' } })
  } catch (error) {
    console.error('Literature reference read failed:', error)
    return NextResponse.json({ error: '文献引用暂时不可用' }, { status: error instanceof LibraryConfigurationError ? 503 : 500 })
  }
}
