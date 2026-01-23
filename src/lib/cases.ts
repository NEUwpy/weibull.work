import casesData from '@/data/cases.json'

export type CaseItem = {
  id: string
  name: string
  industry: string
  type: string
  size: string
  description?: string
  dataRaw: string
  related_paper_slug?: string
  tags: string[]
  created_at?: string
}

// Ensure type safety by casting the imported JSON
// In a real app, you might want to use Zod to validate the JSON structure at runtime.
export const CASE_LIBRARY: CaseItem[] = casesData as CaseItem[]