import { NextResponse } from 'next/server'
import { registeredWorkbookProcess, registeredWorkbookTrialShapes, WorkbookIntegrityError } from '@/lib/server/monte-carlo'
import { DataConfigurationError } from '@/lib/server/data-root'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function GET(request: Request, { params }: { params: { id: string } }) {
  const query = new URL(request.url).searchParams
  try {
    const n = Number(query.get('n')), delta = Number(query.get('delta'))
    const process = query.has('trialRun')
      ? registeredWorkbookTrialShapes(params.id, n, delta, Number(query.get('trialRun')))
      : registeredWorkbookProcess(params.id, n, delta)
    return process ? NextResponse.json(process, { headers: { 'Cache-Control': 'no-store' } })
      : NextResponse.json({ error: '该组合尚未登记整组计算过程' }, { status: 404 })
  } catch (error) {
    const status = error instanceof WorkbookIntegrityError ? 409 : error instanceof DataConfigurationError ? 503 : 500
    return NextResponse.json({ error: status === 500 ? '归档计算过程读取失败' : (error as Error).message }, { status })
  }
}
