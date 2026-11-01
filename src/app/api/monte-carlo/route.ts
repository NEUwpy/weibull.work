import { NextResponse } from 'next/server'
import { workbookCatalog } from '@/lib/server/monte-carlo'
export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'
export async function GET() { return NextResponse.json({ entries: workbookCatalog() }) }
