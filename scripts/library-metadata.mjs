import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import matter from 'gray-matter'
import { journalKey, journalName } from '../src/lib/library-journal-identity.mjs'

const website = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const dataRoot = process.env.WEIBULL_DATA_ROOT || path.resolve(website, '../weibull-data')
const registryPath = path.join(website, 'src/data/library-journals.json')
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''))
const normalize = value => String(value || '').normalize('NFKC').toLowerCase().replace(/<[^>]*>/g, '').replace(/[^\p{L}\p{N}]+/gu, '')
const doiValue = value => String(value || '').trim().replace(/^https?:\/\/(?:dx\.)?doi\.org\//i, '').replace(/[.,;]+$/, '')
const validDoi = value => /^10\.\d{4,9}\/\S+$/i.test(value) && !/xxx|placeholder|待填/i.test(value)

function sourceMetadata(directory, id) {
  const titles = [], dois = new Set(), arxiv = new Set()
  for (const suffix of ['pdf原文', 'pdf翻译', '笔记']) {
    const file = path.join(directory, `${id}-${suffix}.md`)
    if (!fs.existsSync(file)) continue
    // Only bibliographic frontmatter and the article opening participate.
    const descriptor = fs.openSync(file, 'r')
    const buffer = Buffer.alloc(16000)
    let raw
    try { raw = buffer.subarray(0, fs.readSync(descriptor, buffer, 0, buffer.length, 0)).toString('utf8') }
    finally { fs.closeSync(descriptor) }
    const { data, content } = matter(raw)
    for (const key of ['title', 'title_en', '英文标题', '中文标题']) if (typeof data[key] === 'string') titles.push(data[key])
    for (const key of ['doi', 'DOI']) if (validDoi(doiValue(data[key]))) dois.add(doiValue(data[key]))
    if (suffix === '笔记') continue
    const opening = content.split(/^#{1,6}\s*(?:References|参考文献)\s*$/im)[0].slice(0, 1800)
    for (const match of opening.matchAll(/(?:https?:\/\/(?:dx\.)?doi\.org\/|\bdoi\s*[:：]\s*)(10\.\d{4,9}\/[^\s<>"\]]+)/gi)) {
      const doi = doiValue(match[1])
      if (validDoi(doi)) dois.add(doi)
    }
    for (const match of opening.matchAll(/\barxiv\s*[:：]\s*(\d{4}\.\d{4,5})(?:v\d+)?/gi)) arxiv.add(match[1])
  }
  return { titles, dois: [...dois], arxiv: [...arxiv] }
}

function matchingWork(work, metadata, titles, source) {
  const candidates = (work.title || work.titles?.map(entry => entry.title) || []).map(normalize)
  if (!candidates.some(title => title.length > 12 && titles.includes(title))) return false
  const author = normalize(metadata.author)
  const authors = work.author || work.creators || []
  const authorMatch = authors.some(person => {
    const family = normalize(person.family || person.familyName || person.name)
    return family.length >= 2 && author.includes(family)
  })
  const years = ['published', 'issued', 'published-online', 'published-print']
    .flatMap(key => work[key]?.['date-parts']?.[0]?.[0] || [])
  if (work.publicationYear) years.push(work.publicationYear)
  const yearMatch = years.some(year => Math.abs(year - metadata.year) <= 1)
  const localDoi = source.dois.some(doi => doi.toLowerCase() === (work.DOI || work.doi || '').toLowerCase())
  const publication = journalKey(journalName(metadata.publication || ''))
  const publicationMatch = (work['container-title'] || []).some(name => journalKey(journalName(name)) === publication)
  if ((work.DOI || work.doi || '').toLowerCase().startsWith('10.48550/arxiv.')) {
    const number = (work.DOI || work.doi).split(/arxiv\./i)[1]
    return source.arxiv.includes(number) && authorMatch
  }
  if (metadata.type === '预印本') return false
  return authorMatch && yearMatch && (localDoi || publicationMatch || metadata.type !== '期刊')
}

export async function enrichLibraryMetadata(input, { registry = readJson(registryPath), index, fetchJson } = {}) {
  const metadata = { ...input.metadata }
  const warnings = [], evidence = []
  const source = input.source || sourceMetadata(input.directory, input.id)
  const titles = [metadata.title_en, metadata.title, ...source.titles].map(normalize).filter(Boolean)
  let matched
  const request = fetchJson || (async url => {
    const response = await fetch(url, { signal: AbortSignal.timeout(9000), headers: { 'User-Agent': 'WeibullLibrary/1.0 metadata maintenance', Accept: 'application/json' } })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    return response.json()
  })
  const lookup = async doi => {
    const arxiv = doi.toLowerCase().startsWith('10.48550/arxiv.')
    const url = arxiv ? `https://api.datacite.org/dois/${encodeURIComponent(doi)}` : `https://api.crossref.org/works/${encodeURIComponent(doi)}`
    let response
    try { response = await request(url) }
    catch (error) {
      if (/HTTP 404\b/.test(error.message)) return null
      throw error
    }
    const work = arxiv ? response.data?.attributes : response.message
    return work && matchingWork(work, metadata, titles, source) ? { work, url } : null
  }
  if (metadata.doi && !validDoi(doiValue(metadata.doi))) {
    warnings.push('原 DOI 格式无效或含占位内容，已继续补查。')
    delete metadata.doi
  }
  if (!metadata.doi) {
    const candidates = [...new Set([...source.arxiv.map(number => `10.48550/arXiv.${number}`), ...source.dois])].slice(0, 3)
    try {
      for (const doi of candidates) {
        const match = await lookup(doi)
        if (match) { matched = match; break }
      }
      if (!matched) {
        const params = new URLSearchParams({ 'query.bibliographic': metadata.title_en || metadata.title, rows: '5' })
        const url = `https://api.crossref.org/works?${params}`
        const response = await request(url)
        const works = (response.message?.items || []).filter(work => matchingWork(work, metadata, titles, source))
        const distinct = new Map(works.map(work => [work.DOI?.toLowerCase(), work]))
        if (distinct.size === 1) matched = { work: [...distinct.values()][0], url }
        if (distinct.size > 1) warnings.push('匹配到多个 DOI，需核对所藏版本。')
      }
      if (matched) {
        metadata.doi = matched.work.DOI || matched.work.doi
        evidence.push({ field: 'doi', value: metadata.doi, source: matched.url })
      }
    } catch (error) { warnings.push(`DOI 查询暂未完成（${error.message}），请重试补查。`) }
    if (!metadata.doi && !warnings.some(message => message.includes('DOI'))) warnings.push('未查得可确认的 DOI，请核对原刊或记录无 DOI 的依据。')
  }

  let journalUpdate
  if (metadata.type === '期刊') {
    const name = journalName(metadata.publication || metadata.short_publication || '')
    const key = journalKey(name)
    const existing = registry.journals.find(journal => [journal.name, ...journal.aliases || []].some(alias => journalKey(alias) === key))
    if (!existing?.metrics) {
      if (!index) {
        const file = path.join(dataRoot, 'literature-metadata', `jcr-${registry.year}.json`)
        if (fs.existsSync(file)) index = readJson(file)
      }
      const rows = index?.year === registry.year ? index.journals : []
      const titleFound = (rows || []).some(row => journalKey(row.name) === key)
      if (rows?.length && !titleFound && !matched && validDoi(doiValue(metadata.doi))) {
        try { matched = await lookup(doiValue(metadata.doi)) }
        catch (error) { warnings.push(`期刊 ISSN 查询暂未完成（${error.message}），请重试补查。`) }
      }
      const issns = matched?.work.ISSN || []
      const matches = (rows || []).filter(row => journalKey(row.name) === key || row.issns?.some(issn => issns.includes(issn)))
      const unique = new Map(matches.map(row => [JSON.stringify([row.issns, row.impactFactor, row.quartile]), row]))
      if (unique.size === 1) {
        const row = [...unique.values()][0]
        journalUpdate = { ...existing, name: existing?.name || name,
          metrics: { impactFactor: row.impactFactor, quartile: row.quartile, source: index.source } }
        evidence.push({ field: 'journal', value: name, source: index.source })
      } else warnings.push(`${name || '期刊名称缺失'}：未取得可确认的 ${registry.year} 年 JCR 指标，请核对 ISSN、刊名和当期收录情况。`)
    }
  }
  return { metadata, journalUpdate, year: registry.year, warnings, evidence }
}

export function applyJournalUpdate(report, file = registryPath) {
  if (!report.journalUpdate) return
  const lock = file + '.lock'
  let descriptor
  try {
    descriptor = fs.openSync(lock, 'wx')
    const registry = readJson(file)
    if (registry.year !== report.year) throw new Error('JCR 数据年已变化，请重新核对。')
    const key = journalKey(report.journalUpdate.name)
    const current = registry.journals.find(journal => journalKey(journal.name) === key)
    if (current?.metrics && JSON.stringify(current.metrics) !== JSON.stringify(report.journalUpdate.metrics)) throw new Error('同一期刊指标已被更新，请核对来源。')
    if (current?.metrics) return
    if (current) Object.assign(current, report.journalUpdate)
    else registry.journals.push(report.journalUpdate)
    registry.journals.sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
    const temporary = file + `.${process.pid}.tmp`
    try { fs.writeFileSync(temporary, JSON.stringify(registry, null, 2) + '\n'); fs.renameSync(temporary, file) }
    finally { if (fs.existsSync(temporary)) fs.unlinkSync(temporary) }
  } finally {
    if (descriptor !== undefined) { fs.closeSync(descriptor); fs.unlinkSync(lock) }
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const input = JSON.parse(fs.readFileSync(0, 'utf8').replace(/^\uFEFF/, ''))
    if (process.argv.includes('--apply-journal')) { applyJournalUpdate(input); process.stdout.write('{"ok":true}\n') }
    else process.stdout.write(JSON.stringify(await enrichLibraryMetadata(input)) + '\n')
  } catch (error) { process.stderr.write(error.message + '\n'); process.exitCode = 1 }
}
