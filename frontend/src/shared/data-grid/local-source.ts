import type { GridColumn, GridDataSource, GridFilter, GridQuery, GridRule, GridValue } from "./types";

const text = (value: unknown) => value == null ? "" : String(value);
const compare = (a: unknown, b: unknown) => typeof a === "number" && typeof b === "number"
  ? a - b : text(a).localeCompare(text(b), undefined, { numeric: true, sensitivity: "base" });
const safe = (value: unknown) => {
  const s = text(value);
  return /^[\s]*[=+@-]/.test(s) ? `'${s}` : s;
};

/** Adapts only records already loaded by a page. It never claims server-wide scope. */
export function localGridSource<T>(key: string, rows: T[], columns: GridColumn<T>[], getId: (row: T) => string): GridDataSource<T> {
  const value = (row: T, id: string): unknown => {
    const column = columns.find(c => c.id === id);
    return column?.accessor ? column.accessor(row) : (row as Record<string, unknown>)[id];
  };
  const matchesRule = (row: T, rule: GridRule): boolean => {
    const actual = value(row, rule.field), expected = rule.value;
    const a = text(actual).toLocaleLowerCase(), b = text(expected).toLocaleLowerCase();
    switch (rule.operator) {
      case "empty": return actual == null || a === "";
      case "not_empty": return actual != null && a !== "";
      case "equals": return a === b;
      case "not_equals": return a !== b;
      case "contains": return a.includes(b);
      case "starts_with": return a.startsWith(b);
      case "ends_with": return a.endsWith(b);
      case "in": return Array.isArray(expected) && expected.some(v => text(v).toLocaleLowerCase() === a);
      case "gt": return compare(actual, expected) > 0;
      case "gte": return compare(actual, expected) >= 0;
      case "lt": return compare(actual, expected) < 0;
      case "lte": return compare(actual, expected) <= 0;
      case "between": return compare(actual, expected) >= 0 && compare(actual, rule.value2) <= 0;
    }
  };
  const matches = (row: T, filter: GridFilter): boolean => !filter.rules.length || (filter.logic === "or"
    ? filter.rules.some(r => "rules" in r ? matches(row, r) : matchesRule(row, r))
    : filter.rules.every(r => "rules" in r ? matches(row, r) : matchesRule(row, r)));
  const filtered = (query: GridQuery) => rows.filter(row => matches(row, query.filters) && (!query.search || columns.some(c => text(value(row, c.id)).toLocaleLowerCase().includes(query.search.toLocaleLowerCase()))));
  const sorted = (query: GridQuery) => [...filtered(query)].sort((a, b) => {
    for (const sort of query.sorting) { const result = compare(value(a, sort.id), value(b, sort.id)); if (result) return sort.desc ? -result : result; }
    return 0;
  });
  return {
    key,
    localRows: rows,
    load: async query => {
      const matching = sorted(query);
      const branch = matching.filter(row => query.path.every(part => text(value(row, part.field)) === text(part.value)));
      const field = query.grouping[query.path.length];
      const start = (query.page - 1) * query.pageSize;
      if (field) {
        const groups = new Map<string, { value: GridValue; count: number }>();
        for (const row of branch) {
          const raw = value(row, field), v = raw == null ? null : typeof raw === "number" || typeof raw === "boolean" ? raw : text(raw);
          const id = JSON.stringify(v), group = groups.get(id);
          if (group) group.count++; else groups.set(id, { value: v, count: 1 });
        }
        const entries = [...groups.values()];
        return { rows: [], groups: entries.slice(start, start + query.pageSize).map(g => ({ field, value: g.value, label: text(g.value) || "Not set", count: g.count, aggregates: [], path: [...query.path, { field, value: typeof g.value === "boolean" ? String(g.value) : g.value }] })), total: matching.length, pageTotal: entries.length, page: query.page, pageSize: query.pageSize, permissions: { export: true } };
      }
      return { rows: branch.slice(start, start + query.pageSize), total: matching.length, pageTotal: branch.length, page: query.page, pageSize: query.pageSize, permissions: { export: true } };
    },
    facets: async (field, search, query) => {
      const counts = new Map<string, number>();
      for (const row of filtered(query)) { const v = text(value(row, field)); if (v.toLocaleLowerCase().includes(search.toLocaleLowerCase())) counts.set(v, (counts.get(v) || 0) + 1); }
      return { values: [...counts].slice(0, 200).map(([v, count]) => ({ value: v, label: v || "Not set", count })), hasMore: counts.size > 200 };
    },
    export: async request => {
      const ids = new Set(request.ids);
      const records = sorted(request.query).filter(row => request.scope === "filtered" || ids.has(getId(row)));
      const selected = columns.filter(c => request.columns.includes(c.id));
      const separator = request.format === "clipboard" ? "\t" : ",";
      const escape = (v: unknown) => `"${safe(v).replace(/"/g, '""')}"`;
      const output = [selected.map(c => escape(c.title)).join(separator), ...records.map(row => selected.map(c => escape(c.exportValue?.(row) ?? value(row, c.id))).join(separator))].join("\r\n");
      return request.format === "clipboard" ? output : new Blob(["\ufeff", output], { type: "text/csv;charset=utf-8" });
    },
  };
}
