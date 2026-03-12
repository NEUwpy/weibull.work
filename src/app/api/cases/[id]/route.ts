import { NextResponse } from 'next/server'
import { getCaseById } from '@/lib/cases_md'

export async function GET(
  request: Request,
  props: { params: Promise<{ id: string }> }
) {
  try {
    const params = await props.params
    const caseItem = getCaseById(params.id)

    if (!caseItem) {
      return NextResponse.json({ error: 'Case not found' }, { status: 404 })
    }

    return NextResponse.json(caseItem)
  } catch (error) {
    console.error('Failed to fetch case:', error)
    return NextResponse.json({ error: 'Failed to fetch case' }, { status: 500 })
  }
}
