import { api } from "@/services/api";
export type Stage = {
  escalation?: { kind: string; ids: number[] } | null;
  escalation_action?: "notify" | "reassign";
  id: string;
  name: string;
  mode: "all" | "any" | "majority" | "quorum";
  selectors: { kind: string; ids: number[]; field?: string }[];
  quorum?: number;
  sla_seconds?: number;
  remind_after_seconds?: number;
  expire_after_seconds?: number;
  allow_delegation?: boolean;
  require_reason?: boolean;
  when?: Record<string, unknown> | null;
};
export type Process = {
  business_calendar?: {
    timezone: string;
    weekdays: number[];
    opens_at: number;
    closes_at: number;
    holidays: string[];
  } | null;
  layout?: Record<string, { x: number; y: number }>;
  stages: Stage[];
  fields: {
    key: string;
    label: string;
    kind: string;
    required?: boolean;
    options?: string[];
  }[];
  prohibit_self_approval: boolean;
  documents_required: boolean;
};
export type Policy = {
  id: number;
  name: string;
  version: number;
  enabled: boolean;
  definition: Process;
  published_definition?: Process | null;
};
export type RequestRow = {
  requester_name?: string;
  request_type?: string;
  current_stage?: string | null;
  assigned_user_ids?: number[];
  id: number;
  title: string;
  description: string;
  status: string;
  priority: string;
  requester_user_id: number;
  created_at: string;
  sla_due_at: string | null;
};
export type Assignment = {
  id: number;
  stage_name: string;
  user_id: number;
  original_user_id: number;
  status: string;
  can_decide: boolean;
  cycle: number;
};
export type History = {
  id: number;
  event_type: string;
  actor_user_id: number | null;
  created_at: string;
  reason: string | null;
};
export type Detail = RequestRow & {
  state: {
    revision: number;
    run_id: number;
    version_id: number;
    fields: Record<string, unknown>;
  };
  assignments: Assignment[];
  history: History[];
  comments: { id: number; comment: string; author_user_id: number }[];
  attachments: { id: number; name: string }[];
  can_cancel: boolean;
  can_upload: boolean;
  can_resubmit: boolean;
  can_reassign: boolean;
  evidence_valid: boolean;
};
export type Analytics = {
  stage_times: { stage: string; average_seconds: number; decisions: number }[];
  bottlenecks: { stage: string; pending: number; overdue: number }[];
  by_department: { department: string; count: number }[];
  volume_trend: { date: string; count: number }[];
  sla_compliance: number | null;
  counts: Record<string, number | null>;
  by_status: Record<string, number>;
  total: number;
  rejection_rate: number | null;
  workload: { user_id: number; pending: number }[];
  recent: History[];
};
export type Person = { id: number; label: string };
export const root = "/power-apps/approvals";
export const approvalApi = {
  get: async <T>(p: string, e: string, params: Record<string, unknown> = {}) =>
    (await api.get<T>(root + p, { params: { environment: e, ...params } }))
      .data,
  post: async <T>(
    p: string,
    e: string,
    data: unknown = {},
    params: Record<string, unknown> = {},
  ) =>
    (
      await api.post<T>(root + p, data, {
        params: { environment: e, ...params },
      })
    ).data,
  put: async <T>(p: string, e: string, data: unknown) =>
    (await api.put<T>(root + p, data, { params: { environment: e } })).data,
};
export function errorMessage(error: unknown) {
  const e = error as { response?: { data?: { detail?: unknown } } };
  return typeof e.response?.data?.detail === "string"
    ? e.response.data.detail
    : "Could not complete the request. Reload and try again.";
}
export const formatDate = (s: string | null) =>
  s ? new Date(s).toLocaleString() : "—";
export const duration = (n: number | null | undefined) =>
  n == null ? "—" : `${(n / 3600).toFixed(1)} hr`;
export async function upload(id: number, e: string, file: File) {
  const data = new FormData();
  data.append("file", file);
  await api.post(`${root}/requests/${id}/attachments`, data, {
    params: { environment: e },
  });
}
export async function download(
  id: number,
  e: string,
  file: { id: number; name: string },
) {
  const response = await api.get(
    `${root}/requests/${id}/attachments/${file.id}`,
    { params: { environment: e }, responseType: "blob" },
  );
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = file.name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
