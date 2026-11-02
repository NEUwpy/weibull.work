import { NextResponse } from 'next/server'
import { loadMethodFlow, MethodFlowError } from '@/lib/server/method-flow.mjs'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'
export async function GET(_request: Request, { params }: { params: { methodId: string } }) {
  try {
    const flow = loadMethodFlow(params.methodId)
    if (!flow) return NextResponse.json({ error: '该方法尚无程序流程配置' }, { status: 404 })
    return NextResponse.json(flow, { headers: { 'Cache-Control': 'no-store' } })
  } catch (error) {
    console.error('method-flow:', error instanceof Error ? error.message : error)
    return NextResponse.json({ error: error instanceof MethodFlowError ? error.message : '程序流程读取失败' }, { status: 500 })
  }
}
