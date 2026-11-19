import { NextResponse } from 'next/server'
import { createLibraryAuthorProfiles } from '@/lib/library-author-profiles'
import { LibraryConfigurationError, listPapers } from '@/lib/server/literature'

export const dynamic = 'force-dynamic'

export async function GET(request: Request) {
  const name = new URL(request.url).searchParams.get('name')?.trim()
  if (!name || name.length > 200) return NextResponse.json({ error: '请提供有效的作者姓名。' }, { status: 400 })
  try {
    const profile = createLibraryAuthorProfiles(listPapers())(name)
    if (!profile) return NextResponse.json({ error: '未找到该作者的在库文献。' }, { status: 404 })
    return NextResponse.json(profile, { headers: { 'Cache-Control': 'no-store' } })
  } catch (error) {
    console.error('Library author read failed:', error instanceof Error ? error.name : 'Unknown error')
    return NextResponse.json({ error: '作者资料暂时不可用，请稍后重试。' }, { status: error instanceof LibraryConfigurationError ? 503 : 500 })
  }
}
