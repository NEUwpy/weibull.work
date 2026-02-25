import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'

// 获取所有MDM案例配置
export async function GET() {
  try {
    const casesDir = path.join(process.cwd(), 'public', 'case-studies', 'mdm')
    const cases: any[] = []

    // 遍历 case1-case14 目录
    const caseDirs = ['case1', 'case2', 'case3', 'case4', 'case5', 'case6', 'case7', 'case8', 'case9', 'case10', 'case11', 'case12', 'case13', 'case14']

    for (const caseDir of caseDirs) {
      const configPath = path.join(casesDir, caseDir, 'config.md')

      if (!fs.existsSync(configPath)) {
        continue
      }

      const mdContent = fs.readFileSync(configPath, 'utf-8')
      const { data, content } = matter(mdContent)

      // 更新 csvFile 路径指向新位置
      cases.push({
        ...data,
        content: data.architecture === 'markdown' ? content : undefined,
        csvFile: `/case-studies/mdm/${caseDir}/data.json`
      })
    }

    return NextResponse.json({ cases })
  } catch (error) {
    console.error('Error loading case configs:', error)
    return NextResponse.json({ error: 'Failed to load case configurations' }, { status: 500 })
  }
}
