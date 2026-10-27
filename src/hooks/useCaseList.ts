/**
 * 获取 MDM 案例列表的共享 hook
 *
 * 使用方式：
 * const { cases, loading } = useCaseList()
 */

import { useState, useEffect } from 'react'

interface CaseInfo {
  id: string
  name: string
  architecture?: string
}

export function useCaseList() {
  const [cases, setCases] = useState<CaseInfo[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchCases = async () => {
      try {
        const res = await fetch('/api/case-studies/mdm')
        if (res.ok) {
          const data = await res.json()
          setCases(data.cases || [])
        }
      } catch (err) {
        console.error('Failed to load case list:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchCases()
  }, [])

  return { cases, loading }
}
