import type {
  GridColumn,
  GridFilter,
  GridLayout,
  GridQuery,
  GridRule,
} from "./types";
import { emptyQuery } from "./types";
export function defaultLayout<T>(columns: GridColumn<T>[]): GridLayout {
  return {
    order: columns.map((c) => c.id),
    visibility: {},
    pinning: { left: [columns[0]?.id].filter(Boolean), right: [] },
    sizes: {},
    density: "compact",
    rowHeight: 42,
    view: "grid",
    summary: "sum",
  };
}
export function sanitizeLayout<T>(
  value: Partial<GridLayout> | undefined,
  columns: GridColumn<T>[],
): GridLayout {
  const defaults = defaultLayout(columns),
    valid = new Set(defaults.order);
  if (!value || typeof value !== "object") return defaults;
  const order = Array.isArray(value.order)
    ? [...new Set(value.order)].filter((c) => valid.has(c))
    : [];
  const pin = (side: "left" | "right") =>
    (Array.isArray(value.pinning?.[side]) ? value.pinning[side] : []).filter(
      (c) => valid.has(c),
    );
  const left = pin("left"),
    right = pin("right").filter((c) => !left.includes(c));
  return {
    ...defaults,
    ...value,
    order: [...order, ...defaults.order.filter((c) => !order.includes(c))],
    visibility: Object.fromEntries(
      Object.entries(value.visibility || {}).filter(
        ([key, v]) => valid.has(key) && typeof v === "boolean",
      ),
    ),
    sizes: Object.fromEntries(
      Object.entries(value.sizes || {})
        .filter(
          ([key, v]) =>
            valid.has(key) && typeof v === "number" && Number.isFinite(v),
        )
        .map(([key, v]) => [key, Math.max(60, Math.min(800, v))]),
    ),
    pinning: { left, right },
    rowHeight: Math.max(32, Math.min(88, Number(value.rowHeight) || 42)),
    density: value.density === "comfortable" ? "comfortable" : "compact",
    view: ["grid", "cards", "list", "kanban"].includes(String(value.view))
      ? value.view!
      : "grid",
    summary: ["sum", "avg", "min", "max", "count"].includes(
      String(value.summary),
    )
      ? value.summary!
      : "sum",
  };
}
export function isGroup(rule: GridRule | GridFilter): rule is GridFilter {
  return "rules" in rule;
}
export function filterRules(filter: GridFilter): GridRule[] {
  return filter.rules.flatMap((rule) =>
    isGroup(rule) ? filterRules(rule) : [rule],
  );
}
export function removeField(filter: GridFilter, field: string): GridFilter {
  return {
    ...filter,
    rules: filter.rules
      .filter((rule) => isGroup(rule) || rule.field !== field)
      .map((rule) => (isGroup(rule) ? removeField(rule, field) : rule))
      .filter((rule) => !isGroup(rule) || rule.rules.length),
  };
}
export function setFieldFilter(filter: GridFilter, rule: GridRule): GridFilter {
  const clean = removeField(filter, rule.field);
  return {
    logic: "and",
    rules: [
      ...(clean.logic === "and"
        ? clean.rules
        : clean.rules.length
          ? [clean]
          : []),
      rule,
    ],
  };
}
export function removeRule(filter: GridFilter, target: GridRule): GridFilter {
  return {
    ...filter,
    rules: filter.rules
      .filter((rule) => rule !== target)
      .map((rule) => (isGroup(rule) ? removeRule(rule, target) : rule))
      .filter((rule) => !isGroup(rule) || rule.rules.length),
  };
}
export function querySignature(query: GridQuery) {
  return JSON.stringify({ ...query, page: 1, path: [] });
}
export function sanitizeQuery<T>(
  value: Partial<GridQuery> | undefined,
  columns: GridColumn<T>[],
): GridQuery {
  const defaults = emptyQuery(),
    valid = new Set(columns.map((c) => c.id));
  if (!value || typeof value !== "object") return defaults;
  let count = 0;
  const walk = (filter: GridFilter | undefined, depth = 0): GridFilter => ({
    logic: filter?.logic === "or" ? "or" : "and",
    rules:
      depth > 4 || !Array.isArray(filter?.rules)
        ? []
        : filter.rules.slice(0, 50).flatMap<GridRule | GridFilter>((rule) => {
            if (!rule || typeof rule !== "object" || count >= 50) return [];
            if (isGroup(rule)) return [walk(rule, depth + 1)];
            if (
              !valid.has(rule.field) ||
              ![
                "equals",
                "not_equals",
                "contains",
                "starts_with",
                "ends_with",
                "between",
                "gt",
                "gte",
                "lt",
                "lte",
                "empty",
                "not_empty",
                "in",
              ].includes(rule.operator)
            )
              return [];
            count++;
            return [rule];
          }),
  });
  return {
    ...defaults,
    search: typeof value.search === "string" ? value.search.slice(0, 180) : "",
    filters: walk(value.filters),
    sorting: Array.isArray(value.sorting)
      ? value.sorting
          .filter((s) => s && valid.has(s.id))
          .slice(0, 6)
          .map((s) => ({ id: s.id, desc: !!s.desc }))
      : [],
    grouping: Array.isArray(value.grouping)
      ? [...new Set(value.grouping)]
          .filter(
            (id) =>
              valid.has(id) &&
              columns.find((c) => c.id === id)?.groupable !== false,
          )
          .slice(0, 4)
      : [],
    pageSize: [25, 50, 100, 200].includes(Number(value.pageSize))
      ? Number(value.pageSize)
      : 50,
    page: Math.max(1, Number(value.page) || 1),
    path: [],
  };
}
