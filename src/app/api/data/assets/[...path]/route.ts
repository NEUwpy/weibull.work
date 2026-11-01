import { NextResponse } from 'next/server'
import fs from 'fs'
import { DataConfigurationError } from '@/lib/server/data-root'
import { isRuntimeDataPath, resolveRuntimeDataFile } from '@/lib/server/runtime-data'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function GET(_request: Request, { params }: { params: { path: string[] } }) {
  const segments = params.path
  if (!Array.isArray(segments) || !isRuntimeDataPath(segments)) {
    return NextResponse.json({ error: '数据路径无效' }, { status: 400 })
  }
  try {
    const file = resolveRuntimeDataFile(segments)
    if (!file) return NextResponse.json({ error: '外部数据文件不存在' }, { status: 404 })
    return new NextResponse(new Uint8Array(fs.readFileSync(file)), {
      headers: {
        'Content-Type': file.endsWith('.csv') ? 'text/csv; charset=utf-8' : 'application/json; charset=utf-8',
        'Cache-Control': 'no-cache',
        'X-Content-Type-Options': 'nosniff',
      },
    })
  } catch (error) {
    if (error instanceof DataConfigurationError) return NextResponse.json({ error: error.message }, { status: 503 })
    console.error('Error loading runtime data:', error)
    return NextResponse.json({ error: '外部数据读取失败' }, { status: 500 })
  }
}
