import type { GridDataSource, GridQuery } from "./types";

/** Zero means All in personal grid state; APIs continue receiving bounded pages. */
export function withAllRows<T>(source: GridDataSource<T>): GridDataSource<T> {
  const bounded = (query: GridQuery) => query.pageSize === 0 ? { ...query, page: 1, pageSize: 200 } : query;
  return {
    ...source,
    load: async (query, signal) => {
      if (query.pageSize !== 0) return source.load(query, signal);
      const first = await source.load(bounded(query), signal);
      const rows = [...first.rows], groups = [...(first.groups || [])];
      let loaded = rows.length + groups.length;
      const total = first.pageTotal ?? first.total;
      for (let page = 2; loaded < total; page++) {
        signal?.throwIfAborted();
        const next = await source.load({ ...query, page, pageSize: 200 }, signal);
        const count = next.rows.length + (next.groups?.length || 0);
        if (!count) throw new Error("Could not load all records. Refresh to try again.");
        rows.push(...next.rows); groups.push(...(next.groups || [])); loaded += count;
      }
      return { ...first, rows, groups, page: 1, pageSize: 0 };
    },
    facets: source.facets ? (field, search, query, signal) => source.facets!(field, search, bounded(query), signal) : undefined,
    export: source.export ? request => source.export!({ ...request, query: bounded(request.query) }) : undefined,
  };
}
