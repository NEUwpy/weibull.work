import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'

const CASES_DIR = path.join(process.cwd(), 'src/content/cases')

export type CaseItem = {
  id: string
  title: string
  industry: string
  type: string
  size: string
  tags: string[]
  data_raw: string
  created_at: string
  // Optional metadata
  related_paper_slug?: string
  parameters?: {
    beta?: number
    eta?: number
    gamma?: number
  }
  // Content body
  content: string
}

export function getAllCases(): CaseItem[] {
  if (!fs.existsSync(CASES_DIR)) {
    return []
  }

  const files = fs.readdirSync(CASES_DIR)
  
  const cases = files
    .filter(file => file.endsWith('.md') && !file.startsWith('_')) // Ignore _template.md
    .map(file => {
      const filePath = path.join(CASES_DIR, file)
      const fileContent = fs.readFileSync(filePath, 'utf-8')
      const { data, content } = matter(fileContent)
      
      // Map frontmatter to CaseItem
      return {
        id: data.id || file.replace(/\.md$/, ''),
        title: data.title || 'Untitled Case',
        industry: data.industry || 'Unknown',
        type: data.type || 'Unknown',
        size: data.size || 'Unknown',
        tags: data.tags || [],
        data_raw: data.data_raw || '',
        created_at: data.created_at || new Date().toISOString(),
        related_paper_slug: data.related_paper_slug,
        parameters: data.parameters,
        content: content
      }
    })
    // Sort by date desc
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  return cases
}

export function getCaseById(id: string): CaseItem | null {
  // Try to find file by ID (assuming filename matches ID for simplicity, or search content)
  // For performance, direct filename match is preferred. 
  // We'll search both: filename == id.md OR frontmatter.id == id
  
  const allCases = getAllCases()
  return allCases.find(c => c.id === id) || null
}
