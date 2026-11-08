/** UI metadata only: bounded in-memory views, never records, drafts, tokens, or API responses. */
export type NavigationView = {
  search: string;
  scrollTop: number;
  scrollLeft: number;
  values?: Record<string, unknown>;
};
const entries = new Map<string, NavigationView>();
let identity = "";
const LIMIT = 40;
const presentationKeys =
  /^(?:q|search|view|layout|sort|sort_by|sort_order|sortBy|sortOrder|page|per_page|pageSize|page_size|filter|filters|status|priority|owner|assignee|project|projectId|workspace|group|groupBy|tab|period|date_from|date_to)$/;
export const presentationSearch = (search: string) => {
  const params = new URLSearchParams();
  new URLSearchParams(search).forEach((value, key) => {
    if (presentationKeys.test(key)) params.append(key, value);
  });
  return params.size ? `?${params}` : "";
};
export const navigationViews = {
  scope(scope: string) {
    if (scope !== identity) {
      identity = scope;
      entries.clear();
    }
  },
  get(path: string) {
    const entry = entries.get(path);
    if (entry) {
      entries.delete(path);
      entries.set(path, entry);
    }
    return entry;
  },
  save(path: string, view: NavigationView) {
    const previous = entries.get(path);
    entries.delete(path);
    entries.set(path, {
      ...previous,
      ...view,
      search: presentationSearch(view.search),
    });
    while (entries.size > LIMIT) entries.delete(entries.keys().next().value!);
  },
  setValue(scope: string, path: string, name: string, value: unknown) {
    if (scope !== identity) return;
    try {
      if (JSON.stringify(value).length > 50000) return;
    } catch {
      return;
    }
    const previous = entries.get(path) || {
      search: "",
      scrollTop: 0,
      scrollLeft: 0,
    };
    this.save(path, {
      ...previous,
      values: { ...previous.values, [name]: value },
    });
  },
  isScope(scope: string) {
    return scope === identity;
  },
  clear() {
    entries.clear();
    identity = "";
  },
  size: () => entries.size,
};
