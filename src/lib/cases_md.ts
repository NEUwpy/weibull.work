import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'

const CASES_DIR = path.join(process.cwd(), 'src/content/cases')
const GROUPS_DIR = path.join(CASES_DIR, 'groups')

// 单案例类型
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
  // 标识为单案例
  isGroup?: false
}

// 子案例类型（案例组内）
export type SubCaseItem = CaseItem & {
  groupId: string
}

// 案例组类型
export type CaseGroup = {
  id: string
  title: string
  industry: string
  type: 'group'
  description: string
  related_paper?: string
  sample_count: number
  true_params?: {
    beta?: number
    eta?: number
    gamma?: number
  }
  created_at: string
  tags: string[]
  // 标识为案例组
  isGroup: true
  // 子案例列表（可选，用于详情页）
  subCases?: SubCaseItem[]
}

// 统一类型（列表页使用）
export type CaseOrGroup = CaseItem | CaseGroup

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

// ============ 案例组相关函数 ============

// 获取所有案例组（不含子案例）
export function getAllGroups(): CaseGroup[] {
  if (!fs.existsSync(GROUPS_DIR)) {
    return []
  }

  const groupDirs = fs.readdirSync(GROUPS_DIR, { withFileTypes: true })
    .filter(dirent => dirent.isDirectory())
    .map(dirent => dirent.name)

  const groups = groupDirs.map(groupDir => {
    const configPath = path.join(GROUPS_DIR, groupDir, '_config.md')

    // 如果没有配置文件，尝试从目录名推断
    if (!fs.existsSync(configPath)) {
      return {
        id: groupDir,
        title: groupDir,
        industry: 'Unknown',
        type: 'group' as const,
        description: '',
        sample_count: 0,
        created_at: new Date().toISOString(),
        tags: [],
        isGroup: true as const
      }
    }

    const fileContent = fs.readFileSync(configPath, 'utf-8')
    const { data, content } = matter(fileContent)

    // 统计子案例数量
    const subCaseCount = countSubCases(groupDir)

    return {
      id: data.id || groupDir,
      title: data.title || groupDir,
      industry: data.industry || 'Unknown',
      type: 'group' as const,
      description: data.description || content.slice(0, 200),
      related_paper: data.related_paper,
      sample_count: data.sample_count || subCaseCount,
      true_params: data.true_params,
      created_at: data.created_at || new Date().toISOString(),
      tags: data.tags || [],
      isGroup: true as const
    }
  })

  return groups.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
}

// 统计案例组内的子案例数量
function countSubCases(groupId: string): number {
  const groupPath = path.join(GROUPS_DIR, groupId)
  if (!fs.existsSync(groupPath)) return 0

  return fs.readdirSync(groupPath)
    .filter(file => file.endsWith('.md') && !file.startsWith('_'))
    .length
}

// 获取案例组详情（含子案例列表）
export function getGroupById(groupId: string): CaseGroup | null {
  const configPath = path.join(GROUPS_DIR, groupId, '_config.md')

  if (!fs.existsSync(configPath)) {
    return null
  }

  const fileContent = fs.readFileSync(configPath, 'utf-8')
  const { data, content } = matter(fileContent)

  // 读取所有子案例
  const subCases = getSubCases(groupId)

  return {
    id: data.id || groupId,
    title: data.title || groupId,
    industry: data.industry || 'Unknown',
    type: 'group' as const,
    description: data.description || '',
    related_paper: data.related_paper,
    sample_count: data.sample_count || subCases.length,
    true_params: data.true_params,
    created_at: data.created_at || new Date().toISOString(),
    tags: data.tags || [],
    isGroup: true as const,
    subCases
  }
}

// 获取案例组内的所有子案例
export function getSubCases(groupId: string): SubCaseItem[] {
  const groupPath = path.join(GROUPS_DIR, groupId)

  if (!fs.existsSync(groupPath)) {
    return []
  }

  const files = fs.readdirSync(groupPath)
    .filter(file => file.endsWith('.md') && !file.startsWith('_'))

  const subCases = files.map(file => {
    const filePath = path.join(groupPath, file)
    const fileContent = fs.readFileSync(filePath, 'utf-8')
    const { data, content } = matter(fileContent)

    return {
      id: data.id || file.replace(/\.md$/, ''),
      title: data.title || file.replace(/\.md$/, ''),
      industry: data.industry || 'Unknown',
      type: data.type || 'Unknown',
      size: data.size || 'Unknown',
      tags: data.tags || [],
      data_raw: data.data_raw || '',
      created_at: data.created_at || new Date().toISOString(),
      related_paper_slug: data.related_paper_slug,
      parameters: data.parameters,
      content,
      groupId
    }
  })

  return subCases.sort((a, b) => {
    const numA = parseInt(a.id.replace(/\D/g, '')) || 0
    const numB = parseInt(b.id.replace(/\D/g, '')) || 0
    return numA - numB
  })
}

// 获取单个子案例
export function getSubCaseById(groupId: string, caseId: string): SubCaseItem | null {
  const groupPath = path.join(GROUPS_DIR, groupId)
  const filePath = path.join(groupPath, `${caseId}.md`)

  if (!fs.existsSync(filePath)) {
    // 尝试其他命名方式
    const files = fs.readdirSync(groupPath)
      .filter(file => file.endsWith('.md') && !file.startsWith('_'))

    for (const file of files) {
      const fullPath = path.join(groupPath, file)
      const fileContent = fs.readFileSync(fullPath, 'utf-8')
      const { data } = matter(fileContent)

      if (data.id === caseId) {
        const { data: d, content } = matter(fileContent)
        return {
          id: d.id || file.replace(/\.md$/, ''),
          title: d.title || file.replace(/\.md$/, ''),
          industry: d.industry || 'Unknown',
          type: d.type || 'Unknown',
          size: d.size || 'Unknown',
          tags: d.tags || [],
          data_raw: d.data_raw || '',
          created_at: d.created_at || new Date().toISOString(),
          related_paper_slug: d.related_paper_slug,
          parameters: d.parameters,
          content,
          groupId
        }
      }
    }
    return null
  }

  const fileContent = fs.readFileSync(filePath, 'utf-8')
  const { data, content } = matter(fileContent)

  return {
    id: data.id || caseId,
    title: data.title || caseId,
    industry: data.industry || 'Unknown',
    type: data.type || 'Unknown',
    size: data.size || 'Unknown',
    tags: data.tags || [],
    data_raw: data.data_raw || '',
    created_at: data.created_at || new Date().toISOString(),
    related_paper_slug: data.related_paper_slug,
    parameters: data.parameters,
    content,
    groupId
  }
}

// 获取所有案例和案例组（用于列表页）
export function getAllCasesAndGroups(): CaseOrGroup[] {
  const cases = getAllCases().map(c => ({ ...c, isGroup: false as const }))
  const groups = getAllGroups()

  // 合并并按日期排序
  return [...cases, ...groups].sort((a, b) =>
    new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )
}
