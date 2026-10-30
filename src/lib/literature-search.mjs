/** One dependency-free engine for citation identity and interactive catalog search. */
export const LITERATURE_SEARCH_VERSION = '1.0.0'

export function fold(value) {
  return String(value ?? '').normalize('NFKC').toLowerCase().replaceAll('ß', 'ss').replaceAll('ς', 'σ')
}

export function titleKey(value) {
  return [...fold(value)].filter(c => /[\p{L}\p{N}]/u.test(c) || '<>=+±×÷/∓∝∞'.includes(c)).join('')
}

export function extractDois(value) {
  let text = fold(value).replaceAll('\\_', '_')
  try { text = decodeURIComponent(text) } catch { /* Keep an already readable DOI. */ }
  return [...new Set((text.match(/10\.\d{4,9}\/[^\s<>"\]。]+/g) ?? []).map(value => {
    value = value.replace(/[.,;:*`]+$/, '')
    while (value.endsWith(')') && (value.match(/\)/g)?.length ?? 0) > (value.match(/\(/g)?.length ?? 0)) value = value.slice(0, -1)
    return value
  }))]
}

function nameTokens(value) {
  return fold(value).normalize('NFKD').replace(/\p{M}/gu, '').match(/\p{L}+/gu) ?? []
}

// Matching-block similarity, shared by strict author corroboration and search.
function nameSimilarity(left, right) {
  if (left === right) return 1
  if (!left || !right) return 0
  const count = (a0, a1, b0, b1) => {
    let best = 0, ai = a0, bi = b0, previous = new Map()
    for (let a = a0; a < a1; a++) {
      const current = new Map()
      for (let b = b0; b < b1; b++) {
        if (left[a] !== right[b]) continue
        const size = (previous.get(b - 1) ?? 0) + 1
        current.set(b, size)
        if (size > best) { best = size; ai = a - size + 1; bi = b - size + 1 }
      }
      previous = current
    }
    return best ? best + count(a0, ai, b0, bi) + count(ai + best, a1, bi + best, b1) : 0
  }
  return 2 * count(0, left.length, 0, right.length) / (left.length + right.length)
}

export function authorMatches(author, reference) {
  const clean = String(author ?? '').replace(/（[^）]*）|\([^)]*\)/g, '')
  const first = clean.split(/\s+(?:and|et al)\.?\s*|[;&、]/i)[0].split(',')[0]
  const tokens = nameTokens(first).filter(t => t.length > 1)
  if (!tokens.length || tokens.some(t => ['unknown', '未知'].includes(t))) return false
  const surname = tokens.at(-1)
  return nameTokens(reference).some(t => t === surname || (surname.length >= 5 && t.length >= 5 &&
    surname[0] === t[0] && nameSimilarity(surname, t) >= .88))
}

function* titleCandidates(reference) {
  const text = String(reference).replaceAll('\\_', '_')
  const quoted = [...text.matchAll(/["“]([^"”]+)["”]/g)]
  if (quoted.length) { for (const match of quoted) yield titleKey(match[1]); return }
  const separators = [...text.matchAll(/[.,;:!?‘’()\[\]，；：。\n]+/g)].map(m => m[0])
  const chunks = text.split(/[.,;:!?‘’()\[\]，；：。\n]+/)
  for (let start = 0; start < chunks.length; start++) {
    for (let end = start + 1; end <= Math.min(chunks.length, start + 10); end++) {
      const boundary = (separators[start - 1] ?? '') + (separators[end - 1] ?? '')
      if (/[:：]/.test(boundary)) continue
      const key = titleKey(chunks.slice(start, end).join(' '))
      if (key) yield key
    }
  }
}

function intersect(left, right) { return left.some(key => right.includes(key)) }
function add(index, key, value) {
  if (!index.has(key)) index.set(key, new Set())
  index.get(key).add(value)
}

export function createLiteratureIndex(records) {
  const rows = records.map(record => ({ key: String(record.key ?? record.slug ?? record.id), record,
    titles: [record.title, record.title_en].filter(Boolean).map(titleKey),
    dois: extractDois(record.doi), author: nameTokens(record.author),
    text: fold([record.id, record.slug, record.title, record.title_en, record.author, record.year,
      record.publication, record.tags, record.directory, record.reason, record.summary].filter(Boolean).join(' ')),
  }))
  const byKey = new Map(rows.map(row => [row.key, row]))
  if (byKey.size !== rows.length) throw new Error('文献检索身份重复，须按具体目录和UID区分')
  const byDoi = new Map(), byTitle = new Map()
  for (const row of rows) {
    for (const doi of row.dois) add(byDoi, doi, row.key)
    if (!row.record.title_source) for (const title of row.titles) if (title.length >= 8) add(byTitle, title, row.key)
  }
  function matchReference(reference) {
    const identifiers = extractDois(reference)
    const doiHits = new Set(identifiers.flatMap(doi => [...(byDoi.get(doi) ?? [])]))
    const titleHits = new Set([...titleCandidates(reference)].flatMap(title => [...(byTitle.get(title) ?? [])]))
    if (doiHits.size) {
      if (doiHits.size !== 1 || (titleHits.size && (titleHits.size !== 1 || !doiHits.has([...titleHits][0])))) return { key: null, method: 'conflict' }
      const key = [...doiHits][0]
      if (identifiers.some(doi => !byKey.get(key).dois.includes(doi))) return { key: null, method: 'conflict' }
      return { key, method: 'doi' }
    }
    if (titleHits.size !== 1) return { key: null, method: titleHits.size ? 'ambiguous' : 'unmatched' }
    const key = [...titleHits][0], row = byKey.get(key), meta = row.record
    if (identifiers.length && row.dois.length && !intersect(identifiers, row.dois)) return { key: null, method: 'conflict' }
    const years = String(reference).match(/\b(?:18|19|20)\d{2}\b/g) ?? []
    if (meta.year && years.length && !years.includes(String(meta.year))) return { key: null, method: 'conflict' }
    if (authorMatches(meta.author, reference)) return { key, method: 'title+author' }
    if (meta.year && years.includes(String(meta.year)) && titleKey(meta.title_en || meta.title).length >= 24) return { key, method: 'title+year' }
    return { key: null, method: 'insufficient' }
  }
  function search(query) {
    const raw = fold(query).trim()
    if (!raw) return rows.map(row => ({ key: row.key, record: row.record, score: 0, fields: [] }))
    const identifiers = extractDois(raw), compact = titleKey(raw)
    const terms = nameTokens(raw)
    const candidates = new Set(titleCandidates(raw))
    const results = []
    for (const row of rows) {
      let score = 0
      const fields = []
      const hit = (field, value) => { fields.push(field); score = Math.max(score, value) }
      if (intersect(identifiers, row.dois)) hit('doi', 1000)
      if (identifiers.length) {
        if (identifiers.some(doi => row.dois.some(value => value.startsWith(doi)))) hit('doi', 850)
        // A DOI is an identifier; never approximate it using author/title similarity.
        if (!score) continue
      } else {
        const id = titleKey(row.record.id || row.record.slug)
        if (compact && id === compact) hit('id', 950)
        else if (compact && id.startsWith(compact)) hit('id', 700)
        if (row.titles.includes(compact)) hit('title', 900)
        else if (row.titles.some(title => candidates.has(title))) hit('title', 800)
        else if (compact && row.titles.some(title => title.includes(compact))) hit('title', 700)
        const authorKey = nameTokens(raw).join('')
        if (authorKey && row.author.join('').includes(authorKey)) hit('author', 720)
        const normalizedText = nameTokens(row.text).join(' ')
        const authorAnchor = terms.some(term => term.length >= 3 && row.author.includes(term))
        const authorTerm = term => row.author.some(token => token === term || token.startsWith(term) ||
          (authorAnchor && token.length === 1 && token === term[0]) ||
          (term.length >= 4 && token.length >= 4 && nameSimilarity(term, token) >= .78))
        if (terms.length && terms.every(term => authorTerm(term))) hit('author', 600)
        // Mixed title/author/year terms may occur in any order. Title typos do not
        // become exact citation identities; fuzzy matching is limited to names.
        const mixed = raw.split(/\s+/).filter(Boolean).every(term => {
          const key = titleKey(term), token = nameTokens(term)
          return (key && titleKey(row.text).includes(key)) || (token.length && token.every(authorTerm)) || normalizedText.includes(term)
        })
        if (mixed) hit('metadata', 400)
      }
      if (score) results.push({ key: row.key, record: row.record, score, fields })
    }
    return results.sort((a, b) => b.score - a.score || a.key.localeCompare(b.key))
  }
  return { search, matchReference }
}

export const LiteratureSearch = { version: LITERATURE_SEARCH_VERSION, createIndex: createLiteratureIndex,
  titleKey, extractDois, authorMatches }
