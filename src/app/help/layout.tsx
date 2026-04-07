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
    <div className="max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-12 flex gap-12 items-start">
      <HelpSidebar />
      <div className="flex-1 min-w-0">
        {children}
      </div>
    </div>
  )
}
