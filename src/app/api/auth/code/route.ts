import { sendLibraryLoginCode } from '@/lib/server/library-auth'

export const dynamic = 'force-dynamic'

export async function POST(request: Request) {
  return sendLibraryLoginCode(request)
}
