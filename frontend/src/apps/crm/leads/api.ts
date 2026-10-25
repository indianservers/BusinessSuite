import { api } from "@/services/api";
import { getApiBaseUrl } from "@/config/runtime";

export type Stage = { name: string; required: string[]; allowedNext: string[] };
export type AssignmentRule = { field: string; equals: string; ownerId: number };
export type Sequence = {
  name: string;
  steps: { day: number; type: string; title: string }[];
};
export type Workflow = {
  name: string;
  enabled: boolean;
  trigger: string;
  stage: string;
  action: string;
  title: string;
  delayHours: number;
  ownerId?: number | null;
};
export type Settings = {
  stages: Stage[];
  slaHours: number;
  staleDays: number;
  preventDuplicates: boolean;
  assignment: { mode: string; ownerIds: number[]; rules: AssignmentRule[] };
  sequences: Sequence[];
  workflows: Workflow[];
};
export type LeadDetails = {
  qualification?: {
    need: string;
    budget: string;
    decisionMaker: string;
    timeline: string;
  };
  interests?: { name: string; value: number | string; requirements: string }[];
  lossReason?: string;
  competitor?: string;
  scoreOverrideReason?: string;
  archived?: boolean;
  archiveReason?: string;
  reviewAt?: string | null;
  stageEnteredAt?: string;
  sequence?: { name: string; active: boolean; stopReason?: string };
};
export type Lead = {
  id: number;
  full_name: string;
  email?: string;
  phone?: string;
  phone_country_code?: string;
  company_name?: string;
  job_title?: string;
  source?: string;
  status: string;
  owner_user_id?: number;
  estimated_value?: number;
  lead_score?: number;
  lead_score_mode?: string;
  next_follow_up_at?: string;
  last_contacted_at?: string;
  created_at?: string;
  notes?: string;
  is_converted?: boolean;
  converted_contact_id?: number;
  converted_company_id?: number;
  converted_deal_id?: number;
  details: LeadDetails;
  version: number;
  signals: {
    overdue: boolean;
    slaBreached: boolean;
    stale: boolean;
    active: boolean;
    slaDeadline: string;
    ageDays: number;
    nextAction: string;
    priority: number;
    followUpLabel: string;
  };
  timeline?: {
    id: number;
    title: string;
    description?: string;
    event_type: string;
    actor_user_id?: number;
    occurred_at: string;
    metadata_json?: { durationHours?: number };
  }[];
  activities?: {
    id: number;
    subject: string;
    status: string;
    due_date?: string;
    activity_type: string;
  }[];
  scoreReasons?: { name: string; matched: boolean; points: number }[];
};
export type LeadPatch = {
  values?: Record<string, unknown>;
  details?: Partial<LeadDetails>;
  version?: number;
};
export type ListResult = {
  items: Lead[];
  total: number;
  page: number;
  perPage: number;
  truncated: boolean;
  limit: number;
  summary: Record<string, number>;
  byStage: Record<string, number>;
  bySource: Record<string, number>;
  convertedBySource: Record<string, number>;
  lostReasons: Record<string, number>;
};
export type Bootstrap = {
  settings: Settings;
  owners: {
    id: number;
    name: string;
    email?: string;
    employeeId?: number | null;
    employeeCode?: string | null;
    kind?: "employee" | "crm_user";
  }[];
  unavailableEmployees?: {
    employeeId: number;
    employeeCode: string;
    name: string;
    reason: string;
  }[];
  canManage: boolean;
  canAdmin: boolean;
  userId: number;
};
export type ImportPreview = {
  rows: Record<string, unknown>[];
  validRows: { row: number; values: Record<string, unknown> }[];
  errors: { row: number; error: unknown }[];
  skipped: { row: number; reason: string }[];
  ready: number;
  total: number;
};
export type ConversionPreview = {
  ready: boolean;
  alreadyConverted: boolean;
  matches: {
    contacts: { id: number; name: string }[];
    companies: { id: number; name: string }[];
  };
};
export type AnalyticsGroup = {
  key: string;
  leads: number;
  converted: number;
  qualified: number;
  averageFirstResponseMinutes: number | null;
  responseSampleSize: number;
  conversionRate: number;
};
export type LeadAnalytics = {
  scope: string;
  truncated: boolean;
  leadCount: number;
  measurementNote: string;
  bySource: AnalyticsGroup[];
  byOwner: AnalyticsGroup[];
  stageHistory: {
    stage: string;
    leadsEverInStage: number;
    averageHoursBeforeExit: number | null;
    timedExits: number;
  }[];
};
const root = "/crm/lead-management";
export const leadsApi = {
  analytics: () => api.get<LeadAnalytics>(`${root}/analytics`),
  bootstrap: () => api.get<Bootstrap>(`${root}/settings`),
  settings: (settings: Settings) => api.put(`${root}/settings`, settings),
  list: (params: Record<string, string | number>, signal?: AbortSignal) =>
    api.get<ListResult>(`${root}/leads`, { params, signal }),
  detail: (id: number, signal?: AbortSignal) =>
    api.get<Lead>(`${root}/leads/${id}`, { signal }),
  create: (patch: LeadPatch) => api.post<Lead>(`${root}/leads`, patch),
  update: (id: number, patch: LeadPatch) =>
    api.patch<Lead>(`${root}/leads/${id}`, patch),
  activity: (id: number, data: Record<string, unknown>) =>
    api.post(`${root}/leads/${id}/activity`, data),
  completeTask: (id: number, activityId: number) =>
    api.post(`${root}/leads/${id}/activities/${activityId}/complete`, {}),
  sequence: (id: number, name: string, stop = false) =>
    api.post(`${root}/leads/${id}/sequence`, { name, stop }),
  previewConversion: (id: number) =>
    api.get<ConversionPreview>(`${root}/leads/${id}/conversion-preview`),
  convert: (id: number, data: Record<string, unknown>) =>
    api.post<{
      lead: Lead;
      contact?: { id: number };
      company?: { id: number };
      deal?: { id: number };
    }>(`${root}/leads/${id}/convert`, data),
  bulkPreview: (ids: number[], patch: LeadPatch) =>
    api.post<{
      count: number;
      items: { id: number; name: string; stage: string }[];
    }>(`${root}/bulk/preview`, { ids, patch }),
  bulkApply: (ids: number[], patch: LeadPatch) =>
    api.post<{ updated: number }>(`${root}/bulk/apply`, { ids, patch }),
  alerts: () =>
    api.post<{ notificationsCreated: number }>(`${root}/alerts/evaluate`, {}),
  captureSettings: () =>
    api.get<{ enabled: boolean; path?: string; ownerId?: number }>(
      `${root}/capture-settings`,
    ),
  enableCapture: (enabled: boolean, ownerId: number) =>
    api.put<{ enabled: boolean; path?: string; ownerId?: number }>(
      `${root}/capture-settings`,
      { enabled, ownerId },
    ),
  bookingLink: (id: number) =>
    api.post<{ path: string; expires: string }>(
      `${root}/leads/${id}/booking-link`,
      {},
    ),
  previewImport: (file: File) => {
    const data = new FormData();
    data.append("file", file);
    return api.post<ImportPreview>(`${root}/excel/preview`, data);
  },
  import: (rows: Record<string, unknown>[]) =>
    api.post<{ created: number; skipped: unknown[] }>(`${root}/excel/import`, {
      rows,
      skipDuplicates: true,
    }),
  export: (params: Record<string, string | number>) =>
    api.get<Blob>(`${root}/excel/export`, { params, responseType: "blob" }),
  template: () =>
    api.get<Blob>(`${root}/excel/template`, { responseType: "blob" }),
};

export function publicUrl(path: string) {
  const base = new URL(getApiBaseUrl(), window.location.origin);
  return new URL(
    path.replace(/^\/api\/v1/, base.pathname.replace(/\/$/, "")),
    base.origin,
  ).href;
}

export function captureEmbed(path: string) {
  return `<form action="${publicUrl(path)}" method="post">
  <label>Name <input name="full_name" maxlength="220" required></label>
  <label>Email <input name="email" type="email" maxlength="150" required></label>
  <label>Company <input name="company_name" maxlength="180"></label>
  <label>How can we help? <textarea name="message" maxlength="4000" required></textarea></label>
  <input name="website" type="hidden" value="">
  <label><input name="consent" type="checkbox" value="yes" required> I agree to be contacted about this enquiry.</label>
  <button type="submit">Submit enquiry</button>
</form>`;
}

export function errorMessage(error: unknown): string {
  const value = error as {
    response?: { data?: { detail?: unknown } };
    message?: string;
  };
  const detail = value?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    const info = detail as { message: string; missingFields?: string[] };
    return (
      info.message +
      (info.missingFields?.length ? ": " + info.missingFields.join(", ") : "")
    );
  }
  return detail
    ? JSON.stringify(detail)
    : value?.message || "The request failed. Try again.";
}

export function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
