import registry from '../data/library-journals.json'
import { compareLibraryOrder, type LibrarySort } from './library-sort'
import { journalKey, journalName } from './library-journal-identity.mjs'

type PaperPublication = { type?: string; publication?: string; short_publication?: string }

interface JournalMetrics {
  impactFactor: number
  quartile?: string
  category?: string
  source?: string
}

interface JournalRecord {
  name: string
  abbreviation?: string
  abbreviationSource?: string
  aliases?: string[]
  metrics?: JournalMetrics
}

export interface LibraryJournal {
  key: string
  name: string
  shortName?: string
  metrics?: JournalMetrics
}

export const libraryJournalMetricsYear = registry.year
export const libraryJournalMetricsSource = registry.source

const journalFilterPattern = new RegExp('^[\\p{L}\\p{M}\\p{N}][\\p{L}\\p{M}\\p{N}-]{0,239}$', 'u')

const journalAliases = new Map<string, LibraryJournal>()
for (const { name, abbreviation, aliases, metrics } of registry.journals as JournalRecord[]) {
  const shortName = abbreviation || aliases?.find(alias => /^[A-Z][A-Z .-]{1,19}$/.test(alias))
  const journal = { key: journalKey(name), name, shortName, metrics }
  for (const alias of [name, ...(aliases || [])]) journalAliases.set(journalKey(alias), journal)
}

const unspecified = new Set(['期刊', '待核实', 'elsevier', 'elsevier-b-v'])

function publicationShortName(value: string | undefined, name: string) {
  const short = value?.trim().replace(/\s+(?:19|20)\d{2}$/, '')
  if (!short || short.length > 42 || /\d/.test(short) || journalKey(short) === journalKey(name)) return
  // Older tickets sometimes contain a clipped title, rather than a short journal name.
  if (journalKey(name).startsWith(journalKey(short)) && /[a-z]/.test(short)) return
  return short
}

export function libraryJournalInitials(name: string): string {
  if (/[^\x00-\x7F]/.test(name) && /[\u3400-\u9fff\u0600-\u06ff]/.test(name)) return name
  const words = name.replace(/\([^)]*\)/g, '').split(/[\s,:.&-]+/).filter(word => word && !/^(?:a|an|the|and|of|in|on|for|et|de)$/i.test(word))
  if (words.length < 2) return name
  return words.map(word => /^[A-Z]{2,}$/.test(word) ? word : word[0].toUpperCase()).join('') || name
}

export function libraryJournalForPaper({ type, publication, short_publication }: PaperPublication): LibraryJournal | undefined {
  if (type !== '期刊') return
  for (const rawName of [publication, short_publication]) {
    if (!rawName) continue
    const name = journalName(rawName)
    const key = journalKey(name)
    if (key && !unspecified.has(key)) {
      const journal: LibraryJournal = journalAliases.get(key) || { key, name }
      return { ...journal, shortName: publicationShortName(short_publication, journal.name) || journal.shortName }
    }
  }
}

export function groupLibraryJournalPapers<T extends PaperPublication>(papers: T[]) {
  const groups = new Map<string, { journal: LibraryJournal & { count: number }; papers: T[] }>()
  for (const paper of papers) {
    const journal = libraryJournalForPaper(paper)
    if (!journal) continue
    const group = groups.get(journal.key)
    if (group) {
      group.papers.push(paper)
      group.journal.count++
      if (!group.journal.shortName && journal.shortName) group.journal.shortName = journal.shortName
    }
    else groups.set(journal.key, { journal: { ...journal, count: 1 }, papers: [paper] })
  }
  return groups
}

export function libraryJournalGroups(papers: PaperPublication[]) {
  return Array.from(groupLibraryJournalPapers(papers).values(), group => group.journal)
    .sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
}

export function validLibraryJournalFilter(value: string): boolean {
  return journalFilterPattern.test(value)
}

export function libraryJournalPreviewHref(key: string): string {
  return `/library?${new URLSearchParams({ view: 'journals', journal: key })}`
}

export function libraryJournalMetricsLabel(metrics?: JournalMetrics): string {
  if (!metrics) return `暂无 ${libraryJournalMetricsYear} 年 JCR 指标`
  return `${libraryJournalMetricsYear} 年影响因子 ${metrics.impactFactor.toFixed(1)} · ${metrics.quartile ? `JCR ${metrics.quartile}${metrics.category ? `（${metrics.category}）` : ''}` : 'JCR 分区待核实'}`
}

export function libraryPaperOrder<T extends PaperPublication & { slug: string; year?: number }>(papers: T[], sort: LibrarySort) {
  return papers.map(paper => ({ paper, slug: paper.slug, year: paper.year,
    impactFactor: sort === 'impact-desc' ? libraryJournalForPaper(paper)?.metrics?.impactFactor : undefined,
  })).sort((left, right) => compareLibraryOrder(left, right, sort)).map(({ paper }) => paper)
}
