import { NextResponse } from 'next/server'
import { getAllCasesAndGroups } from '@/lib/cases_md'

// 获取所有案例和案例组（用于列表页）
export async function GET() {
  try {
    const items = getAllCasesAndGroups()
    return NextResponse.json(items)
  } catch (error) {
    console.error('Failed to fetch cases and groups:', error)
    return NextResponse.json({ error: 'Failed to fetch data' }, { status: 500 })
  }
}
