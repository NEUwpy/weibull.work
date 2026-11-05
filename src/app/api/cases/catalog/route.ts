import { NextResponse } from 'next/server'
import { readCaseCatalog } from '@/lib/server/case-catalog'

export const dynamic = 'force-dynamic'

export async function GET(request: Request) {
  try {
    const result = readCaseCatalog(new URL(request.url).searchParams)
    return result ? NextResponse.json(result, { headers: { 'Cache-Control': 'no-store' } })
      : NextResponse.json({ error: '案例不存在或尚未整理入目录。' }, { status: 404 })
  } catch (error) {
    console.error('Failed to read case catalog:', error)
    return NextResponse.json({ error: '案例数据暂时无法读取。' }, { status: 500 })
  }
}
