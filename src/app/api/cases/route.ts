import { NextResponse } from 'next/server'
import { getAllCases } from '@/lib/cases_md'

export async function GET() {
  try {
    const cases = getAllCases()
    return NextResponse.json(cases)
  } catch (error) {
    console.error('Failed to fetch cases:', error)
    return NextResponse.json({ error: 'Failed to fetch cases' }, { status: 500 })
  }
}
