import { api } from "@/services/api";
export type DashboardFilters = {
  project_ids: number[];
  statuses: string[];
  priorities: string[];
  assignee_ids: number[];
  sprint_ids: number[];
  tag_ids: number[];
  team_ids: number[];
  project_statuses: string[];
  date_from: string | null;
  date_to: string | null;
  date_field: "created_at" | "due_date" | "completed_at" | "start_date";
  timezone: string;
  custom_field_id: number | null;
  custom_field_value: string;
};
export type Widget = {
  icon?: string;
  drilldown?: boolean;
  id: string;
  type: string;
  title: string;
  description: string;
  x: number;
  y: number;
  w: number;
  h: number;
  hidden: boolean;
  locked: boolean;
  source: string;
  metric: string;
  aggregation: string;
  group_by: string;
  filters: DashboardFilters | null;
  color: string;
  legend: boolean;
  gridlines: boolean;
  labels: boolean;
  tooltips: boolean;
  comparison: boolean;
  decimals: number;
  number_format: string;
  sort: string;
  limit: number;
  notes: string;
  url: string;
  formula: string;
};
export type Configuration = {
  version: 2;
  widgets: Widget[];
  filters: DashboardFilters;
  template: string;
  refresh_seconds: number;
  density: "comfortable" | "compact";
  filter_presets: Record<string, DashboardFilters>;
};
export type Dashboard = {
  id: number;
  workspace_id: number;
  owner_id: number;
  name: string;
  description: string;
  visibility: "private" | "selected" | "workspace" | "organization";
  revision: number;
  deleted_at: string | null;
  updated_at: string;
  created_at: string;
  archived: boolean;
  icon: string;
  accent: string;
  category: string;
  shared_users: { user_id: number; role: "viewer" | "editor" }[];
  configuration: Configuration;
  can_edit: boolean;
  can_manage: boolean;
  favorite?: boolean;
  last_viewed_at?: string;
};
export type Spec = {
  id: string;
  title: string;
  category: string;
  view: string;
  source: string;
  requirement: string;
};
export type Catalog = {
  widgets: Spec[];
  templates: { id: string; name: string; configuration: Configuration }[];
  sources: Record<string, string[]>;
  limits: { widgets: number; source_records: number };
};
export type Row = Record<string, any>;
export type WidgetData = {
  state: "ready" | "error" | "unavailable";
  value?: number | null;
  previous?: number | null;
  change?: number | null;
  rows?: Row[];
  series?: Row[];
  message: string;
  total?: number;
};
export type Batch = {
  widgets: Record<string, WidgetData>;
  generated_at: string;
  scope: { visible_projects: number; time_scope: string };
};
export type Scope = {
  projects: { id: number; name: string; status: string }[];
  people: { id: number; name: string }[];
  sprints: { id: number; name: string }[];
  teams: { id: number; name: string }[];
  tags: { id: number; name: string }[];
  custom_fields: { id: number; name: string }[];
};
export const base = "/project-management/dashboards";
export const emptyFilters = (): DashboardFilters => ({
  project_ids: [],
  statuses: [],
  priorities: [],
  assignee_ids: [],
  sprint_ids: [],
  tag_ids: [],
  team_ids: [],
  project_statuses: [],
  date_from: null,
  date_to: null,
  date_field: "created_at",
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  custom_field_id: null,
  custom_field_value: "",
});
export const emptyConfig = (): Configuration => ({
  version: 2,
  widgets: [],
  filters: emptyFilters(),
  template: "blank",
  refresh_seconds: 120,
  density: "comfortable",
  filter_presets: {},
});
export const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value));
export function makeWidget(spec: Spec, existing: Widget[]): Widget {
  return {
    id: "w_" + crypto.randomUUID().replace(/-/g, ""),
    type: spec.id,
    title: spec.title,
    description: "",
    source: spec.source,
    x: 0,
    y: Math.max(0, ...existing.map((w) => w.y + w.h)),
    w: spec.view === "metric" ? 2 : 4,
    h: spec.view === "metric" ? 4 : 8,
    hidden: false,
    locked: false,
    metric:
      spec.id === "project_budget"
        ? "budget_amount"
        : spec.id === "histogram"
          ? "estimated_hours"
          : "count",
    aggregation: spec.id === "project_budget" ? "sum" : "count",
    group_by: spec.id.includes("priority")
      ? "priority"
      : spec.id.includes("workload") || spec.id === "hours_by_employee"
        ? "assignee"
        : "status",
    filters: null,
    color: "#6d3df5",
    legend: true,
    gridlines: true,
    labels: false,
    tooltips: true,
    comparison: false,
    decimals: 0,
    number_format: "number",
    sort: "value_desc",
    limit: 10,
    notes: "",
    url: "",
    formula: "completion_rate",
  };
}
export function pack(widgets: Widget[]): Widget[] {
  let x = 0,
    y = 0,
    row = 0;
  return widgets.map((widget) => {
    if (widget.hidden) return widget;
    if (x + widget.w > 12) {
      x = 0;
      y += row;
      row = 0;
    }
    const next = { ...widget, x, y };
    x += widget.w;
    row = Math.max(row, widget.h);
    return next;
  });
}
export async function queryDashboard(
  id: number,
  config: Configuration,
): Promise<Batch> {
  return (await api.post(`${base}/${id}/query`, config)).data;
}
export function download(content: Blob, filename: string) {
  const url = URL.createObjectURL(content);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename.replace(/[<>:"/\\|?*]/g, "-");
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function exportCSV(name: string, rows: Row[]) {
  const keys = [...new Set(rows.flatMap((row) => Object.keys(row)))];
  const cell = (v: unknown) => {
    let text = Array.isArray(v)
      ? v.join("; ")
      : typeof v === "object"
        ? JSON.stringify(v)
        : String(v ?? "");
    if (typeof v === "string" && /^[=+@\-\t\r]/.test(text)) text = "'" + text;
    return '"' + text.split('"').join('""') + '"';
  };
  download(
    new Blob(
      [
        "\ufeff" +
          [
            keys.map(cell).join(","),
            ...rows.map((r) => keys.map((k) => cell(r[k])).join(",")),
          ].join("\r\n"),
      ],
      { type: "text/csv;charset=utf-8" },
    ),
    name + ".csv",
  );
}
export function widgetRows(data: WidgetData): Row[] {
  return (
    data.rows ||
    data.series || [
      {
        value: data.value ?? null,
        previous: data.previous ?? null,
        change: data.change ?? null,
        note: data.message,
      },
    ]
  );
}
export function formatMetric(value: number | null | undefined, widget: Widget) {
  if (value == null) return "—";
  return (
    new Intl.NumberFormat(undefined, {
      maximumFractionDigits: widget.decimals ?? 0,
    }).format(value) +
    (widget.number_format === "percent" ||
    ["completion_rate", "on_time_rate", "budget_utilization"].includes(
      widget.type,
    )
      ? "%"
      : widget.number_format === "hours" || widget.type.endsWith("hours")
        ? "h"
        : widget.type === "average_completion"
          ? " days"
          : "")
  );
}
