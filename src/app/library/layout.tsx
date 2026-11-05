import { LibraryDocumentProvider } from '@/components/library/LibraryDocumentDialog'

export default function LibraryLayout({ children }: { children: React.ReactNode }) {
  return <LibraryDocumentProvider>{children}</LibraryDocumentProvider>
}
