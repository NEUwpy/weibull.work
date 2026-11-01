import { NextRequest, NextResponse } from 'next/server'

/** Preserve public image and result URLs while selecting external assets at runtime. */
export function middleware(request: NextRequest) {
  let segments: string[]
  try { segments = request.nextUrl.pathname.split('/').slice(1).map(decodeURIComponent) }
  catch { return NextResponse.next() }
  if (/^[A-Za-z0-9\u3400-\u9fff][A-Za-z0-9\u3400-\u9fff_-]*-图片$/.test(segments[0] || '') && segments.length > 1) {
    const target = request.nextUrl.clone()
    target.pathname = '/api/library/assets/' + segments.map(encodeURIComponent).join('/')
    return NextResponse.rewrite(target)
  }
  const resultNamespace = segments[0] === 'studies' || segments[0] === 'case-studies'
    || (segments[0] === 'ai' && segments[1] === 'data')
  if (resultNamespace && /\.(csv|json)$/.test(segments[segments.length - 1] || '')) {
    const target = request.nextUrl.clone()
    target.pathname = '/api/data/assets/' + segments.map(encodeURIComponent).join('/')
    return NextResponse.rewrite(target)
  }
  return NextResponse.next()
}

export const config = { matcher: ['/((?!api/|_next/|favicon.ico).*)'] }
