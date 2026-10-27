import { NextRequest, NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'

// 获取单个案例配置
export async function GET(
  request: NextRequest,
  { params }: { params: { caseId: string } }
) {
  const { caseId } = params

  try {
    const configPath = path.join(process.cwd(), 'public', 'case-studies', 'mdm', caseId, 'config.md')

    if (!fs.existsSync(configPath)) {
      return NextResponse.json({ error: '案例不存在' }, { status: 404 })
    }

    const mdContent = fs.readFileSync(configPath, 'utf-8')
    const { data, content } = matter(mdContent)

    // 更新 csvFile 路径指向新位置
    const config = {
      ...data,
      content: data.architecture === 'markdown' ? content : undefined,
      csvFile: `/case-studies/mdm/${caseId}/data.csv`
    }

    return NextResponse.json({ config })
  } catch (error) {
    console.error('Error loading case config:', error)
    return NextResponse.json({ error: '配置加载失败' }, { status: 500 })
  }
}
