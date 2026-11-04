/** Compatibility reader for existing Markdown samples and external case datasets. */

import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'
import { readCaseDatasetById, readCalculableCaseDatasets, datasetCaseItem, readCaseCatalogLayout } from './server/case-datasets'
import type { CaseDataset } from './case-datasets'

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
  can_calculate?: boolean
  dataset?: CaseDataset
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

export function getMarkdownCases(): CaseItem[] {
  const files = fs.existsSync(CASES_DIR) ? fs.readdirSync(CASES_DIR) : []

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

export function getAllCases(): CaseItem[] {
  const cases = getMarkdownCases()
  const ids = new Set(cases.map(item => item.id))
  return [...cases, ...readCalculableCaseDatasets().filter(record => !ids.has(record.id)).map(datasetCaseItem)]
}

export function getCaseById(id: string): CaseItem | null {
  const legacy = getMarkdownCases().find(item => item.id === id)
  if (legacy) return legacy
  const dataset = readCaseDatasetById(id)
  return dataset ? datasetCaseItem(dataset) : null
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
  const group = getAllGroups().find(group => group.id === groupId)

  const subCases = files.map(file => {
    const filePath = path.join(groupPath, file)
    const fileContent = fs.readFileSync(filePath, 'utf-8')
    const { data, content } = matter(fileContent)

    return {
      id: data.id || file.replace(/\.md$/, ''),
      title: /^样本\d+-\d+$/.test(data.title || '') ? `第${Number((data.id || file).match(/-(\d+)/)?.[1])}次抽样` : data.title || file.replace(/\.md$/, ''),
      type: group?.type || data.type || '真实样本',
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
  if (!getAllGroups().some(group => group.id === groupId)) return null
  return getSubCases(groupId).find(item => item.id === caseId) || null
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
  const byId = new Map(allCases.map(item => [item.id, item]))
  const grouped = new Set<string>()
  for (const group of readCaseCatalogLayout().groups) {
    const children = group.members.flatMap(member => {
      grouped.add(member.id)
      const item = byId.get(member.id)
      if (!item || item.can_calculate === false || member.role === 'derived') return []
      return [{ id: item.id, title: member.name, data_raw: item.data_raw,
        dataPoints: item.data_raw.split('\n').filter(line => line.trim()).length, groupId: group.id }]
    })
    if (children.length) nodes.push({ type: 'group', id: group.id, title: group.name,
      sample_count: children.length, children })
  }
  for (const c of allCases) {
    if (grouped.has(c.id)) continue
    if (c.can_calculate === false) continue
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
