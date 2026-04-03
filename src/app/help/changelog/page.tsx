import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'
import ChangelogContent from './ChangelogContent'
import { stripBlockquotes } from '@/lib/markdown'

function readDoc(filename: string): string {
  return fs.readFileSync(path.join(process.cwd(), filename), 'utf-8')
}

export default function ChangelogPage() {
  const { content: changelog } = matter(readDoc('07-A-更新日志.md'))
  const statusRaw = readDoc('05-状态.md')

  return <ChangelogContent changelogBody={changelog} statusBody={stripBlockquotes(statusRaw)} />
}
