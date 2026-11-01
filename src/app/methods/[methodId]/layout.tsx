import MethodPage from '@/components/methods/MethodPage'
export default function MethodLayout({ params, children }: { params: { methodId: string }; children: React.ReactNode }) {
  return <><MethodPage params={params} />{children}</>
}
