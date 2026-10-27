/** A per-view request ticket. Input changes invalidate pending completions. */
export function createLatestRequestTracker() {
  const tickets = new Map<string, number>()
  let nextTicket = 0
  return {
    begin(key: string): number {
      const ticket = ++nextTicket
      tickets.set(key, ticket)
      return ticket
    },
    invalidate(key: string) {
      tickets.delete(key)
    },
    clear() {
      tickets.clear()
    },
    isCurrent(key: string, ticket: number): boolean {
      return tickets.get(key) === ticket
    },
  }
}
