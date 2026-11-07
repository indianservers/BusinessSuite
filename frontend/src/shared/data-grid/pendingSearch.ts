/** Compose non-search controls with input that has not reached the debounce yet. */
export function mergePendingGridSearch<T extends { search: string; page: number }>(current: T, next: T, pendingSearch: string, replaceSearch = false): T {
  if (replaceSearch) return next;
  return { ...next, search: pendingSearch, page: pendingSearch !== current.search ? 1 : next.page };
}
