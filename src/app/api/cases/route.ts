import { NextResponse } from 'next/server'
import { getAllCases } from '@/lib/cases_md'

export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    const cases = getAllCases().filter(item => item.can_calculate !== false)
    return NextResponse.json(cases)
  } catch (error) {
    console.error('Failed to fetch cases:', error)
    return NextResponse.json({ error: 'Failed to fetch cases' }, { status: 500 })
  }
}
