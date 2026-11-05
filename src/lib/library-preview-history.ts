type PreviewWindow = Pick<Window, 'history' | 'location' | 'addEventListener' | 'removeEventListener'>

/** One temporary history entry per preview. Switching its contents replaces the entry. */
export function createPreviewHistory(target: PreviewWindow, onChange: (value: string | null) => void,
  key: string, isValid: (value: string) => boolean) {
  let closing = false
  const currentHref = () => {
    const href = target.history.state?.[key]
    return typeof href === 'string' && isValid(href) ? href : null
  }
  const stateWith = (href: string | null) => {
    const state = { ...target.history.state }
    if (href) state[key] = href
    else delete state[key]
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

export function createLibraryPreviewHistory(target: PreviewWindow, onChange: (href: string | null) => void) {
  return createPreviewHistory(target, onChange, '__weibullLibraryPreview', href => /^\/library\/[^/?#]+(?:[?#]|$)/.test(href))
}
