const PREVIEW_KEY = '__weibullLibraryPreview'

/** One temporary history entry per preview; document/tab changes replace that entry. */
export function createLibraryPreviewHistory(target: Pick<Window, 'history' | 'location' | 'addEventListener' | 'removeEventListener'>, onChange: (href: string | null) => void) {
  let closing = false
  const currentHref = () => {
    const href = target.history.state?.[PREVIEW_KEY]
    return typeof href === 'string' && /^\/library\/[^/?#]+(?:[?#]|$)/.test(href) ? href : null
  }
  const stateWith = (href: string | null) => {
    const state = { ...target.history.state }
    if (href) state[PREVIEW_KEY] = href
    else delete state[PREVIEW_KEY]
    return state
  }
  const pop = () => { closing = false; onChange(currentHref()) }
  target.addEventListener('popstate', pop)
  onChange(currentHref())

  return {
    open(href: string) {
      if (closing) return
      if (currentHref()) target.history.replaceState(stateWith(href), '', target.location.href)
      else target.history.pushState(stateWith(href), '', target.location.href)
      onChange(href)
    },
    close() {
      if (closing) return
      if (currentHref()) { closing = true; target.history.back() }
      else onChange(null)
    },
    // Full-page reading replaces the temporary entry; Logo also discards its preview state.
    leave() {
      if (currentHref()) target.history.replaceState(stateWith(null), '', target.location.href)
      closing = false
      onChange(null)
    },
    dispose() { target.removeEventListener('popstate', pop) },
  }
}
