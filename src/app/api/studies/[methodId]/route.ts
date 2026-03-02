import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'

// 获取指定方法的示例列表 - 自动扫描目录
export async function GET(
  request: Request,
  { params }: { params: { methodId: string } }
) {
  const methodId = params.methodId.toLowerCase()

  try {
    const studiesDir = path.join(process.cwd(), 'public', 'studies', methodId)
    const studies: any[] = []

    // 自动扫描目录
    if (fs.existsSync(studiesDir)) {
      const entries = fs.readdirSync(studiesDir, { withFileTypes: true })

      // 过滤出以 demo 开头的目录
      const studyDirs = entries
        .filter(entry => entry.isDirectory() && entry.name.startsWith('demo'))
        .map(entry => entry.name)
        .sort((a, b) => {
          // 按数字排序：demo1, demo2, ...
          const numA = parseInt(a.replace('demo', ''), 10)
          const numB = parseInt(b.replace('demo', ''), 10)
          return numA - numB
        })

      // 读取每个示例的配置
      for (const studyDir of studyDirs) {
        const configPath = path.join(studiesDir, studyDir, 'config.md')

        // 检查 config.md 是否存在
        if (!fs.existsSync(configPath)) {
          console.warn(`[Studies] 跳过 ${studyDir}: 缺少 config.md`)
          continue
        }

        try {
          const mdContent = fs.readFileSync(configPath, 'utf-8')
          const { data, content } = matter(mdContent)

          // 验证必要的字段
          if (!data.id || !data.name) {
            console.warn(`[Studies] 跳过 ${studyDir}: config.md 缺少 id 或 name 字段`)
            continue
          }

          // 添加示例
          studies.push({
            ...data,
            dirName: studyDir,
            method: methodId
          })

          console.log(`[Studies] 加载示例: ${data.name} (${studyDir})`)
        } catch (parseError) {
          console.error(`[Studies] 解析 ${studyDir}/config.md 失败:`, parseError)
        }
      }
    }

    console.log(`[Studies] ${methodId} 共加载 ${studies.length} 个示例`)

    return NextResponse.json({ studies })
  } catch (error) {
    console.error('Error loading study configs:', error)
    return NextResponse.json({ error: 'Failed to load study configurations' }, { status: 500 })
  }
}
