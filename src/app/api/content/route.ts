import { NextRequest, NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

function readTextFile(filePath: string): string {
  const buffer = fs.readFileSync(filePath)
  try {
    const decoder = new TextDecoder('utf-8', { fatal: true })
    return decoder.decode(buffer)
  } catch (e) {
    try {
      const decoder = new TextDecoder('gbk')
      return decoder.decode(buffer)
    } catch (e2) {
      return buffer.toString('binary')
    }
  }
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const slug = searchParams.get('slug')
  const type = searchParams.get('type') // '翻译' or '原文'

  if (!slug || !type) {
    return new NextResponse('Missing parameters', { status: 400 })
  }

  const contentDir = path.join(process.cwd(), 'src/content')
  const fileName = `${slug}-pdf${type}.md`
  const filePath = path.join(contentDir, fileName)

  if (!fs.existsSync(filePath)) {
    return new NextResponse('File not found', { status: 404 })
  }

  const content = readTextFile(filePath)
  return new NextResponse(content)
}
