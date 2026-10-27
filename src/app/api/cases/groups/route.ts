import { NextResponse } from 'next/server'
import { getAllGroups } from '@/lib/cases_md'

// 获取所有案例组列表
export async function GET() {
  try {
    const groups = getAllGroups()
    return NextResponse.json(groups)
  } catch (error) {
    console.error('Failed to fetch groups:', error)
    return NextResponse.json({ error: 'Failed to fetch groups' }, { status: 500 })
  }
}
