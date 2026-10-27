// This file now acts as a type definition and bridge for the new MD-based case system.
// Client components should fetch cases from /api/cases

export type CaseItem = {
  id: string
  title: string      // Previously 'name'
  name?: string       // For backward compatibility
  industry: string
  type: string
  size: string
  tags: string[]
  data_raw: string    // Previously 'dataRaw'
  dataRaw?: string    // For backward compatibility
  created_at: string
  description?: string // Map from content
  content?: string
  related_paper_slug?: string
  parameters?: {
    beta?: number
    eta?: number
    gamma?: number
  }
}

// Fallback empty array for synchronous imports
// In client components, use the API instead.
export const CASE_LIBRARY: CaseItem[] = []
