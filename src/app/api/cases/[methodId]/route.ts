import { NextRequest, NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'

export async function GET(
  request: NextRequest,
  { params }: { params: { methodId: string } }
) {
  const { methodId } = params

  try {
    // 构建MD案例目录
    const casesDir = path.join(process.cwd(), 'public', 'cases')
    const cases: any[] = []

    // 尝试读取多个案例文件 (case1, case2, ...)
    const caseNumbers = [1, 2, 3, 4, 5]  // 支持最多5个案例

    for (const caseNum of caseNumbers) {
      const mdPath = path.join(casesDir, `${methodId}_case${caseNum}.md`)

      // 检查文件是否存在
      if (!fs.existsSync(mdPath)) {
        continue  // 跳过不存在的案例文件
      }

      // 读取并解析MD文件
      const mdContent = fs.readFileSync(mdPath, 'utf-8')
      const { data } = matter(mdContent)

      // 确保params存在
      if (!data.params || !Array.isArray(data.params)) {
        console.warn(`No valid params found in case ${caseNum}`)
        continue
      }

      cases.push(data)
    }

    if (cases.length === 0) {
      console.log(`No case files found for method: ${methodId}`)
      return NextResponse.json({ cases: [] }, { status: 200 })
    }

    return NextResponse.json({ cases })
  } catch (error) {
    console.error('Error loading case config:', error)
    return NextResponse.json(
      { error: 'Failed to load case configuration' },
      { status: 500 }
    )
  }
}
