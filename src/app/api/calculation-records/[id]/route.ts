import { NextResponse } from 'next/server'
import { readCalculationRecordSet, mdmRecordSetProcess, CalculationRecordIntegrityError } from '@/lib/server/calculation-records'
import { DataConfigurationError } from '@/lib/server/data-root'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function GET(request: Request, { params }: { params: { id: string } }) {
  try {
    const set = readCalculationRecordSet(params.id)
    if (!set) return NextResponse.json({ error: '计算记录编号无效' }, { status: 404 })
    const query = new URL(request.url).searchParams
    const process = query.has('trialRun') || query.get('view') === 'process'
      ? mdmRecordSetProcess(params.id, set, query.has('trialRun')) : null
    const value = query.has('trialRun')
      ? process?.runs.find(run => run.id === Number(query.get('trialRun')))?.trace.trialShapes : process ?? set
    return value ? NextResponse.json(value, { headers: { 'Cache-Control': 'no-store' } })
      : NextResponse.json({ error: '该次计算不存在' }, { status: 404 })
  } catch (error) {
    const status = error instanceof CalculationRecordIntegrityError ? 409 : error instanceof DataConfigurationError ? 503 : 500
    return NextResponse.json({ error: status === 500 ? '计算记录读取失败' : (error as Error).message }, { status })
  }
}
