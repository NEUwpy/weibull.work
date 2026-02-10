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
    // 构建MD文件路径
    const casesDir = path.join(process.cwd(), 'public', 'cases')
    const mdPath = path.join(casesDir, `${methodId}_case1.md`)

    // 检查文件是否存在
    if (!fs.existsSync(mdPath)) {
      console.log(`Case file not found: ${mdPath}`)
      return NextResponse.json({ cases: [] }, { status: 200 })
    }

    // 读取并解析MD文件
    const mdContent = fs.readFileSync(mdPath, 'utf-8')
    const { data } = matter(mdContent)

    // 确保params存在
    if (!data.params || !Array.isArray(data.params)) {
      console.error('No valid params found in case config')
      return NextResponse.json({ cases: [] }, { status: 200 })
    }

    return NextResponse.json({
      cases: [data]
    })
  } catch (error) {
    console.error('Error loading case config:', error)
    return NextResponse.json(
      { error: 'Failed to load case configuration' },
      { status: 500 }
    )
  }
}
