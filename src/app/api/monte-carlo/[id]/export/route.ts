import { NextResponse } from 'next/server'
import { registeredWorkbookFile, WorkbookIntegrityError } from '@/lib/server/monte-carlo'
import { DataConfigurationError } from '@/lib/server/data-root'
export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'
export async function GET(request: Request, { params }: { params: { id: string } }) {
  try {
    const codePath = new URL(request.url).searchParams.get('code') || undefined
    const result = registeredWorkbookFile(params.id, codePath)
    if (!result) return NextResponse.json({ error: '文件未登记' }, { status: 404 })
    return new NextResponse(new Uint8Array(result.bytes), { headers: {
      'Content-Type': codePath ? 'application/octet-stream' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(result.filename)}`,
      'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
    } })
  } catch (error) {
    const status = error instanceof WorkbookIntegrityError ? 409 : error instanceof DataConfigurationError ? 503 : 500
    return NextResponse.json({ error: status === 500 ? '导出失败' : (error as Error).message }, { status })
  }
}
