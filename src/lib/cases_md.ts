/**
 * 案例数据读取模块
 *
 * ============================================================================
 * 案例数据统一格式规范
 * ============================================================================
 *
 * 【名称】格式：[id] 标题 [文献ID]
 *   - 示例：[c1] MDM方法验证样本 [182-030]
 *   - 文献ID通过 related_paper_slug 指定，自动显示
 *
 * 【类型】只有两种：
 *   - 抽样样本：Monte Carlo 等模拟生成的数据，有已知真实参数
 *   - 真实样本：实际工程/实验中的失效数据，无已知参数
 *
 * 【数据规模】自动计算：X点×Y组
 *   - 单案例：根据 data_raw 行数自动计算
 *   - 案例组：根据 sample_count 字段
 *
 * 【描述】统一模板（content 正文部分）：
 *   - 抽样样本：来源：文献ID/描述，β=x，η=x，γ=x，用于XX验证
 *   - 真实样本：来源：XX设备/XX实验，描述
 *
 * 【Tags】必选标签（3-4个）：
 *   - 方法：MDM / MLE / WMLE / 通用
 *   - 参数类型：三参数Weibull / 两参数Weibull
 *   - 样本量：大样本 / 小样本
 *   - 数据完整度（真实样本必选）：完全样本 / 截断样本
 *
 * ============================================================================
 */

import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'

const CASES_DIR = path.join(process.cwd(), 'src/content/cases')
const GROUPS_DIR = path.join(CASES_DIR, 'groups')

// 单案例类型
export type CaseItem = {
  id: string
  title: string
  type: string  // 抽样样本 | 真实样本
  tags: string[]
  data_raw: string
  created_at: string
  description: string  // 从 content 提取的简短描述
  // Optional metadata
  related_paper_slug?: string
  parameters?: {
    beta?: number
    eta?: number
    gamma?: number
  }
  true_params?: {
    beta?: number
    eta?: number
    gamma?: number
  }
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
  type: string  // 抽样样本 | 真实样本
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

// 从 content 中提取描述（第一段非空文本）
function extractDescription(content: string): string {
  const lines = content.split('\n')
  const descLines: string[] = []

  for (const line of lines) {
    const trimmed = line.trim()
    // 跳过空行和标题
    if (!trimmed || trimmed.startsWith('#')) continue
    descLines.push(trimmed)
    // 只取第一段
    if (descLines.length === 1) break
  }

  return descLines.join(' ').trim()
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
        type: data.type || '真实样本',  // 默认为真实样本
        tags: data.tags || [],
        data_raw: data.data_raw || '',
        description: extractDescription(content),
        created_at: data.created_at || new Date().toISOString(),
        related_paper_slug: data.related_paper_slug,
        parameters: data.parameters,
        true_params: data.true_params,
        isGroup: false as const
      }
    })
    // Sort by date desc
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  return cases
}

export function getCaseById(id: string): CaseItem | null {
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
        type: '真实样本',
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
      type: data.type || '真实样本',
      description: data.description || extractDescription(content),
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
    type: data.type || '真实样本',
    description: data.description || extractDescription(content),
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
      type: data.type || '真实样本',
      tags: data.tags || [],
      data_raw: data.data_raw || '',
      description: extractDescription(content),
      created_at: data.created_at || new Date().toISOString(),
      related_paper_slug: data.related_paper_slug,
      parameters: data.parameters,
      true_params: data.true_params,
      groupId,
      isGroup: false as const
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
          type: d.type || '真实样本',
          tags: d.tags || [],
          data_raw: d.data_raw || '',
          description: extractDescription(content),
          created_at: d.created_at || new Date().toISOString(),
          related_paper_slug: d.related_paper_slug,
          parameters: d.parameters,
          true_params: d.true_params,
          groupId,
          isGroup: false as const
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
    type: data.type || '真实样本',
    tags: data.tags || [],
    data_raw: data.data_raw || '',
    description: extractDescription(content),
    created_at: data.created_at || new Date().toISOString(),
    related_paper_slug: data.related_paper_slug,
    parameters: data.parameters,
    true_params: data.true_params,
    groupId,
    isGroup: false as const
  }
}

// 获取所有案例和案例组（用于列表页）
export function getAllCasesAndGroups(): CaseOrGroup[] {
  const cases = getAllCases()
  const groups = getAllGroups()

  // 合并并按日期排序
  return [...cases, ...groups].sort((a, b) =>
    new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )
}

// ============ 树形结构（用于多选选择器） ============

// DataEditor 期望的扁平化树形结构
export type CaseTreeNode =
  | { type: 'group'; id: string; title: string; sample_count: number; children: CaseItemNode[] }
  | { type: 'case'; id: string; title: string; data_raw: string; dataPoints: number }

// 子案例节点（扁平化）
export type CaseItemNode = {
  id: string
  title: string
  data_raw: string
  dataPoints: number
  groupId: string
}

// 获取案例树形结构（组+子案例，独立案例）
export function getCasesTree(): CaseTreeNode[] {
  const nodes: CaseTreeNode[] = []

  // 1. 获取所有案例组（含子案例）
  const groups = getAllGroups()
  for (const group of groups) {
    const subCases = getSubCases(group.id)
    // 转换为 DataEditor 期望的扁平结构
    const children: CaseItemNode[] = subCases.map(sc => ({
      id: sc.id,
      title: sc.title,
      data_raw: sc.data_raw,
      dataPoints: sc.data_raw.split('\n').filter(l => l.trim()).length,
      groupId: group.id
    }))
    nodes.push({
      type: 'group',
      id: group.id,
      title: group.title,
      sample_count: group.sample_count,
      children
    })
  }

  // 2. 获取所有独立案例（不在组内的）
  const allCases = getAllCases()
  for (const c of allCases) {
    nodes.push({
      type: 'case',
      id: c.id,
      title: c.title,
      data_raw: c.data_raw,
      dataPoints: c.data_raw.split('\n').filter(l => l.trim()).length
    })
  }

  return nodes
}
