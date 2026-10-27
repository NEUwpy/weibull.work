import { NextRequest, NextResponse } from 'next/server'

/** Keep existing /<paper>-图片/... URLs while selecting assets at runtime. */
export function middleware(request: NextRequest) {
  let segments: string[]
  try { segments = request.nextUrl.pathname.split('/').slice(1).map(decodeURIComponent) }
  catch { return NextResponse.next() }
  if (/^[A-Za-z0-9\u3400-\u9fff][A-Za-z0-9\u3400-\u9fff_-]*-图片$/.test(segments[0] || '') && segments.length > 1) {
    const target = request.nextUrl.clone()
    target.pathname = '/api/library/assets/' + segments.map(encodeURIComponent).join('/')
    return NextResponse.rewrite(target)
  }
  return NextResponse.next()
}

export const config = { matcher: ['/((?!api/|_next/|favicon.ico).*)'] }
