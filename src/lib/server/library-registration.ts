function parseTimestamp(value: string | undefined) {
  if (!value || !/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$/.test(value)) return NaN
  const date = value.slice(0, 10)
  const timestamp = Date.parse(value)
  return Number.isFinite(timestamp) && new Date(`${date}T00:00:00Z`).toISOString().slice(0, 10) === date ? timestamp : NaN
}

export function libraryRegistrationWindow() {
  const opensAt = parseTimestamp(process.env.WEIBULL_LIBRARY_REGISTRATION_OPENS_AT)
  const closesAt = parseTimestamp(process.env.WEIBULL_LIBRARY_REGISTRATION_CLOSES_AT)
  return opensAt < closesAt ? { opensAt, closesAt } : null
}

export function isLibraryRegistrationOpen(now = Date.now()) {
  const window = libraryRegistrationWindow()
  return window !== null && window.opensAt <= now && now < window.closesAt
}
