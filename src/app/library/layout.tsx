import { LibraryDocumentProvider, LibraryFavoritesProvider } from '@/components/library'
import { listPapers } from '@/lib/server/literature'

export const dynamic = 'force-dynamic'

export default function LibraryLayout({ children }: { children: React.ReactNode }) {
  return <LibraryFavoritesProvider><LibraryDocumentProvider catalog={listPapers()}>{children}</LibraryDocumentProvider></LibraryFavoritesProvider>
}
