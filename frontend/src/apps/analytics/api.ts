import { api } from "@/services/api";

export type AnalyticsRecord = Record<string, unknown> & { id?: number; name?: string; status?: string };
export type AnalyticsList = { items: AnalyticsRecord[]; total: number };
export type BusinessModuleKey = "crm" | "hrms" | "pms" | "sales" | "finance";
export type BusinessModule = { key: BusinessModuleKey; name: string; label: string; status: "available" | "restricted"; total: number | null; current: number | null; previous: number | null; path: string; details: Record<string, number> };
export type BusinessOverview = {
  context: { organization_id: number; timezone: string; as_of: string; branch_scope: "all" | "selected"; branch_count: number; branch_id: number | null };
  period: { days: number; start: string; end: string };
  modules: BusinessModule[];
  series: { date: string; previous_date: string; current: Partial<Record<BusinessModuleKey, number>>; previous: Partial<Record<BusinessModuleKey, number>> }[];
  branches: { id: number | null; name: string; active: boolean; counts: Partial<Record<BusinessModuleKey, number>> }[];
  money: Record<string, { currency: string; amount: string }[]>;
  definition: string;
};

const list = (path: string) => api.get<AnalyticsList>(path).then((res) => res.data);
const create = (path: string, data: unknown) => api.post(path, data).then((res) => res.data);

export const analyticsApi = {
  businessOverview: (days: number, allBranches: boolean) => api.get<BusinessOverview>("/analytics/overview", { params: { days }, headers: allBranches ? { "X-Suite-Branch": "all" } : undefined, progress: false }).then((res) => res.data),
  branchContext: () => api.get<{ all_branches: boolean; company_id: number; branches: { id: number; name: string }[] }>("/branches/context", { progress: false }).then((res) => res.data),
  reports: () => list("/analytics/reports"),
  createReport: (data: unknown) => create("/analytics/reports", data),
  runReport: (id: number, data?: unknown) => create(`/analytics/reports/${id}/run`, data || {}),
  exportReport: (id: number, data: unknown) => create(`/analytics/reports/${id}/export`, data),
  exports: (id: number) => api.get(`/analytics/exports/${id}`).then((res) => res.data),
  dashboards: () => list("/analytics/dashboards"),
  createDashboard: (data: unknown) => create("/analytics/dashboards", data),
  addWidget: (id: number, data: unknown) => create(`/analytics/dashboards/${id}/widgets`, data),
  schedules: () => list("/analytics/schedules"),
  createSchedule: (data: unknown) => create("/analytics/schedules", data),
  runSchedule: (id: number) => create(`/analytics/schedules/${id}/run-now`, {}),
  funnel: () => api.get("/analytics/funnel").then((res) => res.data),
  forecast: () => api.get("/analytics/forecast").then((res) => res.data),
  profitability: () => list("/analytics/profitability"),
  collections: () => list("/analytics/collections"),
  campaigns: () => list("/analytics/campaigns"),
  anomalies: () => api.get("/analytics/anomalies").then((res) => res.data),
  exportAudit: () => list("/analytics/export-audit"),
};

