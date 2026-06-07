import { api } from "@/services/api";

export type AnalyticsRecord = Record<string, unknown> & { id?: number; name?: string; status?: string };
export type AnalyticsList = { items: AnalyticsRecord[]; total: number };

const list = (path: string) => api.get<AnalyticsList>(path).then((res) => res.data);
const create = (path: string, data: unknown) => api.post(path, data).then((res) => res.data);

export const analyticsApi = {
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

