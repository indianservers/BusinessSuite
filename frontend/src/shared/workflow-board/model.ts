export type WorkflowModule = "crm" | "hrms" | "pms" | "srm" | "fam" | "power_apps";
export type WorkflowFacet = { id: string; label: string };
export type WorkflowStage = { id: string; name: string };
export type WorkflowRecord = {
  id: string;
  stageId: string;
  title: string;
  subtitle?: string;
  href: string;
  owners: WorkflowFacet[];
  teams: WorkflowFacet[];
  date?: string;
  due?: string;
  closed?: boolean;
  blocked?: boolean;
  awaitingApproval?: boolean;
  priority?: string;
  amount?: number;
  currency?: string;
  effort?: number;
  canChangeStage?: boolean;
  jobId?: number;
};
export type WorkflowData = {
  title: string;
  stages: WorkflowStage[];
  records: WorkflowRecord[];
  dateLabel: string;
  totalLabel: string;
  workspaceHref: string;
  note: string;
  truncated?: boolean;
};
export type WorkflowFilters = { team: string; owner: string; from: string; to: string };
export const emptyWorkflowFilters: WorkflowFilters = { team: "", owner: "", from: "", to: "" };

// Date-only deadlines remain due throughout their local calendar day.
export function localDay(date = new Date()): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
export function workflowDeadline(value: string): number {
  const time = Date.parse(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T23:59:59.999` : value);
  return Number.isFinite(time) ? time : Infinity;
}
export function isOverdue(record: WorkflowRecord, now = new Date()): boolean {
  if (record.closed || !record.due) return false;
  return /^\d{4}-\d{2}-\d{2}$/.test(record.due)
    ? record.due < localDay(now)
    : Number.isFinite(Date.parse(record.due)) && Date.parse(record.due) < now.getTime();
}
export function workflowBadges(record: WorkflowRecord, now = new Date()): string[] {
  return [isOverdue(record, now) && "Overdue", record.blocked && "Blocked", record.awaitingApproval && "Awaiting approval"].filter((v): v is string => !!v);
}
function facetMatches(facets: WorkflowFacet[], selected: string) {
  return !selected || (selected === "__unassigned" ? !facets.length : facets.some(f => f.id === selected));
}
export function filterWorkflowRecords(records: WorkflowRecord[], filters: WorkflowFilters): WorkflowRecord[] {
  if (filters.from && filters.to && filters.from > filters.to) return [];
  return records.filter(r => {
    const date = r.date && (/^\d{4}-\d{2}-\d{2}$/.test(r.date) ? r.date : Number.isFinite(Date.parse(r.date)) ? localDay(new Date(r.date)) : undefined);
    return facetMatches(r.teams, filters.team) && facetMatches(r.owners, filters.owner)
      && (!filters.from || !!date && date >= filters.from) && (!filters.to || !!date && date <= filters.to);
  });
}
export function sortWorkflowRecords(records: WorkflowRecord[], now = new Date()): WorkflowRecord[] {
  const rank = (r: WorkflowRecord) => r.closed ? 0 : isOverdue(r, now) ? 4 : r.blocked ? 3 : r.awaitingApproval ? 2 : 1;
  const priority = (r: WorkflowRecord) => ({ critical: 4, urgent: 4, high: 3, medium: 2, normal: 2, low: 1 }[r.priority?.toLowerCase() || ""] || 0);
  const due = (r: WorkflowRecord) => r.due ? workflowDeadline(r.due) : Infinity;
  return [...records].sort((a, b) => rank(b) - rank(a) || priority(b) - priority(a) || due(a) - due(b) || a.title.localeCompare(b.title) || a.id.localeCompare(b.id));
}
export function workflowFacets(records: WorkflowRecord[], field: "owners" | "teams"): WorkflowFacet[] {
  return [...new Map(records.flatMap(r => r[field]).map(f => [f.id, f])).values()].sort((a, b) => a.label.localeCompare(b.label));
}
export function formatWorkflowMoney(value: number, currency?: string): string {
  if (!currency) return `${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })} (currency unavailable)`;
  try { return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 2 }).format(value); }
  catch { return `${currency} ${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`; }
}
export function workflowTotal(records: WorkflowRecord[], kind: string): string {
  if (kind === "Effort") {
    const known = records.filter(r => r.effort != null);
    return `${known.reduce((n, r) => n + (r.effort || 0), 0).toLocaleString()} h estimated${known.length < records.length ? ` · ${records.length - known.length} unestimated` : ""}`;
  }
  if (kind === "Value" || kind === "Outstanding") {
    const totals = new Map<string, number>();
    for (const r of records) if (r.amount != null) totals.set(r.currency || "", (totals.get(r.currency || "") || 0) + r.amount);
    return totals.size ? [...totals].map(([c, v]) => formatWorkflowMoney(v, c)).join(" / ") : "No recorded value";
  }
  return `${records.filter(r => !r.closed).length} active${records.some(r => r.closed) ? ` · ${records.filter(r => r.closed).length} closed` : ""}`;
}
export function ageingStage(due: string | undefined, now = new Date()): string {
  if (!due || !/^\d{4}-\d{2}-\d{2}/.test(due) || !Number.isFinite(Date.parse(due))) return "undated";
  const day = due.slice(0, 10), today = localDay(now);
  if (day > today) return "upcoming";
  if (day === today) return "today";
  const days = Math.round((Date.parse(today) - Date.parse(day)) / 86400000);
  return days <= 30 ? "1-30" : days <= 60 ? "31-60" : "60+";
}
