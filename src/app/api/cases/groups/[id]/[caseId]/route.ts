import { NextResponse } from 'next/server'
import { getSubCaseById } from '@/lib/cases_md'

// 获取单个子案例详情
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string; caseId: string }> }
) {
  try {
    const { id, caseId } = await params
    const subCase = getSubCaseById(id, caseId)

    if (!subCase) {
      return NextResponse.json({ error: 'Sub-case not found' }, { status: 404 })
    }

    return NextResponse.json(subCase)
  } catch (error) {
    console.error('Failed to fetch sub-case:', error)
    return NextResponse.json({ error: 'Failed to fetch sub-case' }, { status: 500 })
  }
}
