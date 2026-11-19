export function journalKey(name) {
  return name.normalize('NFKC').toLowerCase().replaceAll('&', ' and ')
    .replace(/[^\p{L}\p{M}\p{N}]+/gu, '-').replace(/^-|-$/g, '')
}

export function journalName(value) {
  return value.normalize('NFKC').trim()
    .replace(/,\s*(?:vol\.?|volume)\s*\d.*$|[,\s]+(?:[A-Z]-)?\d+(?:\s*\(\d+\))?\s*:\s*\d.*$/i, '').trim()
}
