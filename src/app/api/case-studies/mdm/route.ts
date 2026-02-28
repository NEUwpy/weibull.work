import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'

// 获取所有MDM案例配置 - 自动扫描目录
export async function GET() {
  try {
    const casesDir = path.join(process.cwd(), 'public', 'case-studies', 'mdm')
    const cases: any[] = []

    // 自动扫描目录
    if (fs.existsSync(casesDir)) {
      const entries = fs.readdirSync(casesDir, { withFileTypes: true })

      // 过滤出以 case 开头的目录
      const caseDirs = entries
        .filter(entry => entry.isDirectory() && entry.name.startsWith('case'))
        .map(entry => entry.name)
        .sort((a, b) => {
          // 按数字排序：case3, case4, ..., case10, ..., case16
          const numA = parseInt(a.replace('case', ''), 10)
          const numB = parseInt(b.replace('case', ''), 10)
          return numA - numB
        })

      // 读取每个案例的配置
      for (const caseDir of caseDirs) {
        const configPath = path.join(casesDir, caseDir, 'config.md')

        // 检查 config.md 是否存在
        if (!fs.existsSync(configPath)) {
          console.warn(`[MDM Cases] 跳过 ${caseDir}: 缺少 config.md`)
          continue
        }

        try {
          const mdContent = fs.readFileSync(configPath, 'utf-8')
          const { data, content } = matter(mdContent)

          // 验证必要的字段
          if (!data.id || !data.name) {
            console.warn(`[MDM Cases] 跳过 ${caseDir}: config.md 缺少 id 或 name 字段`)
            continue
          }

          // 添加案例
          cases.push({
            ...data,
            dirName: caseDir,  // 保存目录名
            content: data.architecture === 'markdown' ? content : undefined,
            csvFile: `/case-studies/mdm/${caseDir}/data.json`
          })

          console.log(`[MDM Cases] 加载案例: ${data.name} (${caseDir})`)
        } catch (parseError) {
          console.error(`[MDM Cases] 解析 ${caseDir}/config.md 失败:`, parseError)
        }
      }
    }

    console.log(`[MDM Cases] 共加载 ${cases.length} 个案例`)

    return NextResponse.json({ cases })
  } catch (error) {
    console.error('Error loading case configs:', error)
    return NextResponse.json({ error: 'Failed to load case configurations' }, { status: 500 })
  }
}
