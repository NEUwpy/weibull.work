export async function register() {
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    const { warmLibrarySearch } = await import('./lib/server/library-search')
    try {
      warmLibrarySearch()
    } catch (error) {
      // A missing external library should leave the rest of the platform available.
      console.warn('Library search warm-up unavailable:', error instanceof Error ? error.name : 'Unknown error')
    }
  }
}
