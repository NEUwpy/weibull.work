import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'
import HelpContent from './HelpContent'
import { stripBlockquotes, extractFirstSection } from '@/lib/markdown'

function readDoc(filename: string): string {
  return fs.readFileSync(path.join(process.cwd(), filename), 'utf-8')
}

export default function HelpPage() {
  // 读取多个文档源
  const { content: features } = matter(readDoc('07-功能.md'))
  const { content: modules } = matter(readDoc('06-模块.md'))
  const structureRaw = readDoc('01-结构.md')

  // 过滤：引用为开发者内部注释，不呈现给用户
  // 01-结构.md 只取第 1 节（系统架构概览），其余为内部架构细节
  const helpBody = stripBlockquotes(features)
  const modulesBody = stripBlockquotes(modules)
  const structureBody = stripBlockquotes(extractFirstSection(structureRaw))

  return (
    <HelpContent
      helpBody={helpBody}
      modulesBody={modulesBody}
      structureBody={structureBody}
    />
  )
}
