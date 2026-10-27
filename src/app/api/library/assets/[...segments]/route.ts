import { NextRequest, NextResponse } from 'next/server'
import fs from 'fs'
import { LibraryConfigurationError, resolveLibraryAsset } from '@/lib/server/literature'

export const dynamic = 'force-dynamic'

export async function GET(_request: NextRequest, { params }: { params: { segments: string[] } }) {
  try {
    const asset = resolveLibraryAsset(params.segments)
    if (!asset) return new NextResponse('File not found', { status: 404 })
    return new NextResponse(new Uint8Array(fs.readFileSync(asset.path)), {
      headers: { 'Content-Type': asset.contentType, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' },
    })
  } catch (error) {
    console.error('Literature asset read failed:', error)
    return new NextResponse('文献资源暂时不可用', { status: error instanceof LibraryConfigurationError ? 503 : 500 })
  }
}
