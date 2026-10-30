import { librarySessionResponse } from '@/lib/server/library-auth'

export const dynamic = 'force-dynamic'

export async function GET(request: Request) {
  return librarySessionResponse(request)
}
