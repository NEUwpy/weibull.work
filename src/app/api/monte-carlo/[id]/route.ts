import { NextResponse } from 'next/server'
import { registeredWorkbook, WorkbookIntegrityError } from '@/lib/server/monte-carlo'
import { DataConfigurationError } from '@/lib/server/data-root'
export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'
export async function GET(_request: Request, { params }: { params: { id: string } }) {
  try {
    const book = registeredWorkbook(params.id)
    return book ? NextResponse.json(book, { headers: { 'Cache-Control': 'no-store' } }) : NextResponse.json({ error: '数据批次未登记' }, { status: 404 })
  } catch (error) {
    const status = error instanceof WorkbookIntegrityError ? 409 : error instanceof DataConfigurationError ? 503 : 500
    return NextResponse.json({ error: status === 500 ? '工作簿读取失败' : (error as Error).message }, { status })
  }
}
