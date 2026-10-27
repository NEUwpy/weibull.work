import { LibraryPageClient } from '@/components/library'
import { listPapers } from '@/lib/server/literature'

// Read the selected library on each request, including papers added after build.
export const dynamic = 'force-dynamic'

export default function LibraryPage() {
  return <LibraryPageClient papers={listPapers()} />
}
