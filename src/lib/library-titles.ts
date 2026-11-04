export interface LibraryTitlePresentation {
  display_title?: string
  original_title?: string
  original_language?: 'zh' | 'en' | 'other'
}

const chinese = (value: unknown): value is string => typeof value === 'string' && /[\u3400-\u9fff]/.test(value)
const english = (value: unknown): value is string => typeof value === 'string' && !chinese(value) && /[a-z]/i.test(value)
export function libraryOriginalLanguage(value?: string): LibraryTitlePresentation['original_language'] {
  if (!value) return undefined
  if (/[\u3040-\u30ff\u0600-\u06ff\u0400-\u04ff]/.test(value)) return 'other'
  return chinese(value) ? 'zh' : english(value) ? 'en' : undefined
}
const useful = (value: unknown): value is string => typeof value === 'string' && Boolean(value.trim()) &&
  !/^(?:abstract|review|preface|contents|introduction|博士学位论文|硕士(?:专业)?学位论文|.*网络首发论文|青洛师苑大学)$/i.test(value.trim())

// Only titles without an existing Chinese source need a website translation.
const missingTranslations: Record<string, string> = {
  'Bias and Standard Deviation due to Weibull Parameter Estimation for Small Data Sets': '小数据集威布尔参数估计的偏差与标准差',
}

/** Reuse an existing formula when its plain spelling also occurs in the translated title. */
function preserveTitleMath(title: string, candidates: (string | undefined)[]): string {
  if (title.includes('$')) return title
  for (const candidate of candidates) for (const match of Array.from(candidate?.matchAll(/\$([^$\n]+)\$/g) || [])) {
    const compact = match[1].replace(/\s/g, '')
    if (!compact) continue
    const pattern = compact.split('').map(char => char.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('\\s*')
    title = title.split(/(\$[^$\n]+\$)/g).map(part => part.startsWith('$') ? part : part.replace(new RegExp(pattern), () => match[0])).join('')
  }
  return title
}

export function libraryTitlePresentation(input: {
  title: string; title_en?: string; noteZh?: string; noteEn?: string; noteTitle?: string
  sourceTitle?: string; sourceHeading?: string; sourceLanguage?: LibraryTitlePresentation['original_language']
}): LibraryTitlePresentation {
  const { title, title_en, noteZh, noteEn, noteTitle, sourceTitle, sourceHeading } = input
  const evidence = sourceHeading || sourceTitle
  const original_language = input.sourceLanguage || libraryOriginalLanguage(evidence)
  const original = [title_en, noteEn, title, sourceHeading, sourceTitle].find(value => english(value) && useful(value))
  // Explicit Chinese catalog titles remain authoritative, except imported cover headings or fused bilingual OCR titles.
  const candidates = [title, noteZh, noteTitle]
  const fused = (value: string) => /(?:[A-Z]{3,}[ -]*){4,}/.test(value)
  const translated = candidates.find(value => chinese(value) && useful(value) && !fused(value)) || missingTranslations[original || title] || missingTranslations[title]
  return {
    display_title: preserveTitleMath(translated || title, [title, sourceHeading, title_en]),
    ...(original ? { original_title: preserveTitleMath(original, [title, sourceHeading]) } : {}),
    ...(original_language ? { original_language } : {}),
  }
}

export function libraryPresentedTitle(paper: { title: string; title_en?: string } & LibraryTitlePresentation, expanded = false): string {
  return expanded && paper.original_language === 'en' && paper.original_title
    ? paper.original_title : paper.display_title || paper.title
}
