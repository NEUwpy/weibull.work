import { notFound, redirect } from 'next/navigation'
import { legacyProcessHref, methodHref, METHOD_SECTIONS } from '@/lib/method-navigation'
import { INITIAL_METHOD_TREE } from '@/lib/methods'
export default function MethodSection({ params, searchParams }: {
  params: { methodId: string; section: string }
  searchParams: Record<string, string | string[] | undefined>
}) {
  if (!INITIAL_METHOD_TREE.some(category => category.children?.some(m => m.id === params.methodId))) notFound()
  if (params.section === 'process' || params.section === 'applicability') {
    const query = new URLSearchParams()
    for (const [name, value] of Object.entries(searchParams)) {
      for (const item of Array.isArray(value) ? value : [value]) {
        if (item !== undefined) query.append(name, item)
      }
    }
    if (params.section === 'process') redirect(legacyProcessHref(params.methodId, query))
    query.set('source', 'basic')
    redirect(methodHref(params.methodId, 'analysis', query))
  }
  if (!Object.hasOwn(METHOD_SECTIONS, params.section)) notFound()
  return null
}
