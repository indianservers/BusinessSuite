import { api } from "@/services/api";

export type OperatorProviderName = "openai" | "gemini" | "claude";
export type OperatorProvider = { provider: OperatorProviderName; model: string; enabled: boolean; data_sharing_allowed: boolean; has_key: boolean; max_tokens: number; input_price: number | null; output_price: number | null; allow_workspace_inheritance?: boolean; inherited?: boolean; configuration_scope?: string };
export type OperatorStep = { tool: string; task_id: number; changes?: Record<string, unknown> | null; title?: string | null; sprint_id?: number | null; start_date?: string; due_date?: string; source_task_id?: number; dependency_id?: number; item_id?: number; is_completed?: boolean; body?: string; depends_on?: number[] };
export type OperatorRun = { id: number; project_id: number; command: string; input_mode: string; provider: string; status: string; selection: number[]; plan_hash: string | null; plan: { summary: string; clarification: string | null; steps: OperatorStep[] } | null; error_code: string | null; background?: boolean; execution_mode?: "atomic" | "checkpointed"; parent_run_id?: number | null; revision?: number; timezone?: string; result: { success: boolean; partial?: boolean; receipts?: { step: number; tool: string; task_id: number; record_id: number }[]; message?: string } | null };
export type OperatorEvent = { id: number; type: string; payload: { status: string; step?: number; error_code?: string }; created_at: string };
export type ApiLog = { id: number; provider: string; model: string; purpose: string; status: string; error_code: string | null; input_tokens: number | null; output_tokens: number | null; duration_ms: number; estimated_cost: number | null; run_id: number | null; user_id: number; created_at: string };
export type OperatorAnalytics = { local_plans?: number; groups: { provider: string; model: string; status: string; requests: number; input_tokens: number | null; output_tokens: number | null; estimated_cost: number | null; priced_requests: number; average_latency_ms: number }[]; logs: ApiLog[]; cost_note: string };
const scope = (workspace?: number) => workspace ? { workspace_id: workspace } : {};
export const operatorApi = {
  providers: (workspace?: number) => api.get<{ items: OperatorProvider[] }>("/ai-operator/providers", { params: scope(workspace) }),
  saveProvider: (provider: OperatorProviderName, data: Omit<OperatorProvider, "provider" | "has_key"> & { api_key?: string }, workspace?: number) => api.put(`/ai-operator/providers/${provider}`, data, { params: scope(workspace) }),
  testProvider: (provider: OperatorProviderName, workspace?: number) => api.post(`/ai-operator/providers/${provider}/test`, {}, { params: scope(workspace), timeout: 60000 }),
  analytics: (workspace?: number) => api.get<OperatorAnalytics>("/ai-operator/analytics", { params: scope(workspace) }),
  command: (data: { project_id: number; task_ids: number[]; command: string; provider: OperatorProviderName; request_key: string; input_mode: "text" | "voice"; background?: boolean; execution_mode?: "atomic" | "checkpointed"; timezone?: string; parent_run_id?: number; parent_plan_hash?: string | null; local_plan?: { summary: string; clarification: null; steps: OperatorStep[] } }) => api.post<OperatorRun>("/ai-operator/commands", data, { timeout: 65000 }),
  events: (id: number, after: number) => api.get<{ items: OperatorEvent[]; next_cursor: number; has_more: boolean; run: OperatorRun }>(`/ai-operator/runs/${id}/events`, { params: { after_id: after } }),
  revise: (run: OperatorRun, command: string, key: string, mode: "text" | "voice") => api.post<OperatorRun>(`/ai-operator/runs/${run.id}/revise`, { command, request_key: key, plan_hash: run.plan_hash, input_mode: mode }),
  resume: (run: OperatorRun) => api.post<OperatorRun>(`/ai-operator/runs/${run.id}/resume`, { plan_hash: run.plan_hash }),
  runs: (project: number) => api.get<{ items: OperatorRun[] }>("/ai-operator/runs", { params: { project_id: project } }),
  run: (id: number) => api.get<OperatorRun>(`/ai-operator/runs/${id}`),
  approve: (run: OperatorRun) => api.post<OperatorRun>(`/ai-operator/runs/${run.id}/approve`, { plan_hash: run.plan_hash }, { timeout: 65000 }),
  cancel: (id: number) => api.post<OperatorRun>(`/ai-operator/runs/${id}/cancel`),
};
