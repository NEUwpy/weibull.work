import React from 'react'
import Link from 'next/link'
import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'
import { BookOpen, FileText, Calendar, Tag, User, Filter } from 'lucide-react'
import { LibraryPageClient } from '@/components/library'


// Library Page (Server Component)

interface PaperMetadata {
  slug: string
  title: string
  title_en?: string
  author: string
  affiliation?: string
  publication?: string
  short_publication?: string
  type?: string
  year: number
  tags: string[]
  summary: string
  related_method_id?: string
}

// Helper to safely read text with encoding detection
function readTextFile(filePath: string): string {
  const buffer = fs.readFileSync(filePath)
  try {
    const decoder = new TextDecoder('utf-8', { fatal: true })
    return decoder.decode(buffer)
  } catch (e) {
    try {
      const decoder = new TextDecoder('gbk')
      return decoder.decode(buffer)
    } catch (e2) {
      return buffer.toString('binary')
    }
  }
}

async function getPapers(): Promise<PaperMetadata[]> {
  const contentDir = path.join(process.cwd(), 'src/content')
  // Ensure dir exists
  if (!fs.existsSync(contentDir)) return []

  const files = fs.readdirSync(contentDir)
  
  // We want to group by ID (slug). 
  // Map ID -> preferred file path.
  const paperMap = new Map<string, string>()

  files.forEach(file => {
    // Check if file matches our pattern: ID-pdf翻译.md or ID-pdf原文.md
    // We assume ID is the part before the suffix.
    let slug = ''
    let isTranslation = false

    if (file.endsWith('-pdf翻译.md')) {
      slug = file.replace('-pdf翻译.md', '')
      isTranslation = true
    } else if (file.endsWith('-pdf原文.md')) {
      slug = file.replace('-pdf原文.md', '')
      isTranslation = false
    } else {
      return // Skip non-matching files
    }

    // Logic: If slug already exists, overwrite ONLY if current file is translation (preference).
    // If not exists, set it.
    if (!paperMap.has(slug)) {
      paperMap.set(slug, file)
    } else {
      if (isTranslation) {
        paperMap.set(slug, file)
      }
    }
  })
  
  const papers = Array.from(paperMap.entries()).map(([slug, file]) => {
      const filePath = path.join(contentDir, file)
      const fileContent = readTextFile(filePath)
      const { data } = matter(fileContent)
      
      // If no frontmatter, skip or provide defaults? 
      // User said "only show if yaml header exists", so we check data.title
      if (!data.title) return null

      return {
        slug: slug,
        title: data.title,
        title_en: data.title_en,
        author: data.author || 'Unknown',
        affiliation: data.affiliation,
        publication: data.publication,
        short_publication: data.short_publication,
        type: data.type || '文献',
        year: data.year || new Date().getFullYear(),
        tags: data.tags || [],
        summary: data.summary || '',
        related_method_id: data.related_method_id
      } as PaperMetadata
    })
    .filter((paper): paper is PaperMetadata => paper !== null)

  return papers
}

export default async function LibraryPage() {
  const papers = await getPapers()

  return <LibraryPageClient papers={papers} />
}
