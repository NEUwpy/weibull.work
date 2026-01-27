import { NextRequest, NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const slug = searchParams.get('slug')

  if (!slug) {
    return NextResponse.json({ error: 'Missing slug parameter' }, { status: 400 })
  }

  try {
    const contentDir = path.join(process.cwd(), 'src/content/algorithms')
    const filePath = path.join(contentDir, `${slug}.md`)

    if (!fs.existsSync(filePath)) {
      return NextResponse.json({ error: 'Algorithm documentation not found' }, { status: 404 })
    }

    const content = fs.readFileSync(filePath, 'utf-8')
    return new NextResponse(content, {
      headers: {
        'Content-Type': 'text/markdown; charset=utf-8',
      },
    })
  } catch (error) {
    return NextResponse.json({ error: 'Failed to read file' }, { status: 500 })
  }
}
