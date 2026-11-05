type PreviewWindow = Pick<Window, 'history' | 'location' | 'addEventListener' | 'removeEventListener'>

/** One temporary history entry per preview. Switching its contents replaces the entry. */
export function createPreviewHistory(target: PreviewWindow, onChange: (value: string | null, trail: string[]) => void,
  key: string, isValid: (value: string) => boolean) {
  let closing = false
  const currentHref = () => {
    const href = target.history.state?.[key]
    return typeof href === 'string' && isValid(href) ? href : null
  }
  const currentTrail = (): string[] => {
    const href = currentHref()
    if (!href) return []
    const trail = target.history.state?.[`${key}Trail`]
    return Array.isArray(trail) && trail.length && trail.every(value => typeof value === 'string' && isValid(value)) && trail.at(-1) === href ? [...trail] : [href]
  }
  const stateWith = (trail: string[]) => {
    const state = { ...target.history.state }
    const href = trail.at(-1)
    if (href) state[key] = href
    else delete state[key]
    if (trail.length > 1) state[`${key}Trail`] = trail
    else delete state[`${key}Trail`]
    return state
  }
  const pop = () => { closing = false; onChange(currentHref(), currentTrail()) }
  target.addEventListener('popstate', pop)
  onChange(currentHref(), currentTrail())

  return {
    open(href: string) {
      if (closing || !isValid(href)) return
      const trail = currentTrail()
      if (trail.length) {
        trail[trail.length - 1] = href
        target.history.replaceState(stateWith(trail), '', target.location.href)
      } else {
        trail.push(href)
        target.history.pushState(stateWith(trail), '', target.location.href)
      }
      onChange(href, trail)
    },
    push(href: string) {
      if (closing || !isValid(href)) return
      const trail = [...currentTrail(), href]
      target.history.pushState(stateWith(trail), '', target.location.href)
      onChange(href, trail)
    },
    close() {
      if (closing) return
      if (currentHref()) { closing = true; target.history.back() }
      else onChange(null, [])
    },
    // Full-page reading replaces the temporary entry; Logo also discards its preview state.
    leave() {
      if (currentHref()) target.history.replaceState(stateWith([]), '', target.location.href)
      closing = false
      onChange(null, [])
    },
    restore() { pop() },
    dispose() { target.removeEventListener('popstate', pop) },
  }
}

export function createLibraryPreviewHistory(target: PreviewWindow, onChange: (href: string | null, trail: string[]) => void) {
  return createPreviewHistory(target, onChange, '__weibullLibraryPreview', href => /^\/library\/[^/?#]+(?:[?#]|$)/.test(href) ||
    (href.startsWith('/library?') && ['author', 'institution'].some(key => Boolean(new URL(href, 'http://library.local').searchParams.get(key)))))
}
