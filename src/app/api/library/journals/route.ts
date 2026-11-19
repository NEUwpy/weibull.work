import { NextResponse } from 'next/server'
import { createLibraryJournalProfiles } from '@/lib/library-directory-index'
import { validLibraryJournalFilter } from '@/lib/library-journals'
import { LibraryConfigurationError, listPapers } from '@/lib/server/literature'

export const dynamic = 'force-dynamic'

export async function GET(request: Request) {
  const key = new URL(request.url).searchParams.get('key')?.trim()
  if (!key || !validLibraryJournalFilter(key)) return NextResponse.json({ error: '请提供有效的期刊编号。' }, { status: 400 })

  try {
    const profile = createLibraryJournalProfiles(listPapers()).findJournal(key)
    if (!profile) return NextResponse.json({ error: '未找到该期刊的在库论文。' }, { status: 404 })
    return NextResponse.json(profile, { headers: { 'Cache-Control': 'no-store' } })
  } catch (error) {
    console.error('Library journal read failed:', error instanceof Error ? error.name : 'Unknown error')
    return NextResponse.json({ error: '期刊资料暂时不可用，请稍后重试。' }, { status: error instanceof LibraryConfigurationError ? 503 : 500 })
  }
}
