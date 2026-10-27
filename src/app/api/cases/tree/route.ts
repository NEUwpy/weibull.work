import { NextResponse } from 'next/server'
import { getCasesTree } from '@/lib/cases_md'

// 获取案例树形结构（用于多选选择器）
// 返回: CaseTreeNode[] - 组+子案例，独立案例
export async function GET() {
  try {
    const tree = getCasesTree()
    return NextResponse.json(tree)
  } catch (error) {
    console.error('Failed to fetch cases tree:', error)
    return NextResponse.json({ error: 'Failed to fetch cases tree' }, { status: 500 })
  }
}
