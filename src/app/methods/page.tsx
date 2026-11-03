import MethodTree from '@/components/shared/MethodTree'

export default function MethodsPage() {
  return <section className="page-shell w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12 space-y-4">
    <MethodTree showCategoryDescription />
  </section>
}
