import { notFound } from 'next/navigation'
import { METHOD_SECTIONS } from '@/lib/method-navigation'
import { INITIAL_METHOD_TREE } from '@/lib/methods'
export default function MethodSection({ params }: { params: { methodId: string; section: string } }) {
  if (!(params.section in METHOD_SECTIONS) || !INITIAL_METHOD_TREE.some(category => category.children?.some(m => m.id === params.methodId))) notFound()
  return null
}
