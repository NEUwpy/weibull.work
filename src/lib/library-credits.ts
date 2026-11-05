export interface LibraryCreditName {
  name: string
  name_en?: string
  aliases?: string[]
}

export interface LibraryCredits {
  authors: (LibraryCreditName & { units?: string[] })[]
  institutions?: (LibraryCreditName & { id: string })[]
}

export interface LibraryCreditPaper {
  slug: string
  author: string
  affiliation?: string
  year?: number
  credits?: LibraryCredits
}

export function libraryCreditDiagnostics(metadata: { credits?: LibraryCredits }) {
  if (!metadata.credits) return [{ code: 'META_CREDITS_MISSING', severity: 'warning', message: '缺少结构化署名 credits；既有文献兼容读取，新上架须补齐作者及其署名单位。' }]
  const credits = validateLibraryCredits(metadata.credits)
  const diagnostics = []
  if (!credits.institutions?.length || credits.authors.some(author => !author.units?.length)) {
    diagnostics.push({ code: 'META_CREDITS_UNITS_MISSING', severity: 'warning', message: '部分作者缺少署名单位，请对照原文补录；来源未载明时保留缺失。' })
  }
  if ([...credits.authors, ...(credits.institutions || [])].some(row => !row.name_en && /[\u3400-\u9fff]/.test(row.name))) {
    diagnostics.push({ code: 'META_CREDITS_EN_MISSING', severity: 'warning', message: '部分中文署名缺少有据可查的英文名；不自动拼音归并或翻译单位名称。' })
  }
  return diagnostics
}

const object = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === 'object' && !Array.isArray(value)
const label = (value: unknown): value is string => typeof value === 'string' && Boolean(value.trim()) && !/[\r\n]/.test(value) && !/^(?:unknown|未登记|待核实|未知|n\/?a|[-—]+)$/i.test(value.trim())
const only = (value: Record<string, unknown>, keys: string[]) => Object.keys(value).every(key => keys.includes(key))
const labels = (value: unknown): value is string[] => Array.isArray(value) && value.every(label)

export function libraryCreditNames(credit: LibraryCreditName): string[] {
  return [credit.name, ...(credit.name_en ? [credit.name_en] : []), ...(credit.aliases || [])]
}

export function libraryCreditNameKey(name: string): string {
  return name.normalize('NFKC').toLowerCase().replace(/&/g, ' and ').replace(/[.,，'’\-‐‑]/g, '').replace(/\s+/g, ' ').trim()
}

/** The site and the compiler bridge both validate this public subset of the source front matter. */
export function validateLibraryCredits(value: unknown): LibraryCredits {
  const fail = (field: string, reason: string): never => { throw new Error(`credits.${field} ${reason}`) }
  const nameFields = ['name', 'name_en', 'aliases']
  function checkName(row: Record<string, unknown>, field: string) {
    if (!label(row.name)) fail(`${field}.name`, '须为有依据的单行名称')
    if (row.name_en !== undefined && !label(row.name_en)) fail(`${field}.name_en`, '须为有依据的单行名称，缺失时省略')
    if (row.aliases !== undefined && !labels(row.aliases)) fail(`${field}.aliases`, '须为单行名称数组')
  }
  if (!object(value) || !only(value, ['authors', 'institutions'])) throw new Error('credits 须为仅含 authors 和可选 institutions 的对象')
  const institutions = value.institutions ?? []
  if (!Array.isArray(institutions) || value.institutions === null) return fail('institutions', '须为数组')
  const ids = new Set<string>()
  for (const [index, unit] of Array.from(institutions.entries())) {
    const field = `institutions[${index}]`
    if (!object(unit) || !only(unit, [...nameFields, 'id'])) return fail(field, '只接受 id、name、name_en、aliases')
    checkName(unit, field)
    const id = unit.id
    if (typeof id !== 'string' || !/^[a-zA-Z0-9_-]+$/.test(id)) return fail(`${field}.id`, '须为文献内的单位编号')
    if (ids.has(id)) return fail(`${field}.id`, `重复单位编号 ${id}`)
    ids.add(id)
  }
  const authors = value.authors
  if (!Array.isArray(authors) || !authors.length) return fail('authors', '须为非空作者数组')
  for (const [index, author] of Array.from(authors.entries())) {
    const field = `authors[${index}]`
    if (!object(author) || !only(author, [...nameFields, 'units'])) return fail(field, '只接受 name、name_en、aliases、units')
    checkName(author, field)
    if (author.units !== undefined) {
      if (!labels(author.units)) return fail(`${field}.units`, '须为单位编号数组')
      for (const id of author.units) if (!ids.has(id)) return fail(`${field}.units`, `未登记单位编号 ${id}`)
    }
  }
  return value as unknown as LibraryCredits
}

/** Merge spelling evidence anchored to the same primary name. Ambiguous aliases keep their original identity. */
export function findLibraryCredit<T extends LibraryCreditName>(credits: T[], name: string): T | undefined {
  const key = libraryCreditNameKey(name)
  const matches = credits.filter(credit => libraryCreditNames(credit).some(alias => libraryCreditNameKey(alias) === key))
  const first = matches.find(credit => libraryCreditNameKey(credit.name) === key) || matches[0]
  if (!first || matches.some(credit => libraryCreditNameKey(credit.name) !== libraryCreditNameKey(first.name))) return undefined
  const primary = libraryCreditNameKey(first.name)
  const aliases = Array.from(new Set(credits.filter(credit => libraryCreditNameKey(credit.name) === primary).flatMap(libraryCreditNames)))
  const english = matches.find(credit => credit.name_en)?.name_en
  return { ...first, ...(english ? { name_en: english } : {}), aliases }
}
