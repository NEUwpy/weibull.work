import { LibraryDocumentProvider } from '@/components/library/LibraryDocumentDialog'

export default function CasesLayout({ children }: { children: React.ReactNode }) {
  return <LibraryDocumentProvider returnLabel="返回案例">{children}</LibraryDocumentProvider>
}
