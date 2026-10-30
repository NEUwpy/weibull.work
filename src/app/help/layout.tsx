"use client"

import { usePathname } from 'next/navigation'
import HelpSidebar from '@/components/help/HelpSidebar'

export default function HelpLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isRoot = pathname === '/help'

  if (isRoot) {
    return <>{children}</>
  }

  return (
    <div className="page-shell max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12 flex gap-12 items-start max-[1279px]:flex-col max-[1279px]:gap-5">
      <HelpSidebar />
      <div className="flex-1 min-w-0 max-[1279px]:w-full max-[1279px]:[&_table]:block max-[1279px]:[&_table]:max-w-full max-[1279px]:[&_table]:overflow-x-auto max-[1279px]:[&_pre]:max-w-full max-[1279px]:[&_pre]:overflow-x-auto">
        {children}
      </div>
    </div>
  )
}
