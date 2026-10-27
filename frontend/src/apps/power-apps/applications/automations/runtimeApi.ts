import { api } from "@/services/api";
import type { WorkflowGraph } from "./builder/types";
export type RunStatus =
  | "queued"
  | "running"
  | "waiting"
  | "retry_scheduled"
  | "completed"
  | "failed"
  | "cancelled";
export type RunSummary = {
  environment: string;
  id: number;
  resource_id: number;
  status: RunStatus;
  workflow_version: number;
  actor_user_id: number;
  effective_user_id: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_type: string | null;
  correlation_id: string;
};
export type RuntimeStep = {
  id: number;
  node_id: string;
  original_node_id: string;
  status: string;
  attempt: number;
  input_payload: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  active_ports: string[];
  error: string | null;
  error_type: string | null;
  started_at: string | null;
  finished_at: string | null;
};
export type RuntimeHistory = {
  can_export: boolean;
  execution: RunSummary;
  run: {
    correlation_id: string;
    effective_user_id: number;
    input_payload: Record<string, unknown>;
    variables: Record<string, unknown>;
    error: string | null;
    deadline: string;
  };
  definition: WorkflowGraph;
  steps: RuntimeStep[];
  events: {
    id: number;
    kind: string;
    created_at: string;
    details: Record<string, unknown>;
  }[];
  jobs: {
    id: number;
    status: string;
    claims: number;
    available_at: string;
    heartbeat_at: string | null;
  }[];
};
export type RuntimePolicy = {
  concurrency: number;
  overflow: "queue" | "reject" | "ignore";
  max_queued: number;
  max_duration_seconds: number;
  identity: "initiator" | "owner" | "service";
  delegated_owner: boolean;
  service_user_id?: number | null;
  input_schema?: Record<string, unknown> | null;
};
export type Deployment = {
  status: string;
  validated_version: number | null;
  version_id: number | null;
  revision: number;
  policy: Partial<RuntimePolicy>;
};
export type ExecutionList = {
  items: RunSummary[];
  total: number;
  offset: number;
  limit: number;
  metrics: Record<string, number | null>;
};
export type RuntimeTrigger = {
  id: number;
  kind: string;
  enabled: boolean;
  endpoint: string;
  config: Record<string, unknown>;
  next_at: string | null;
  secret_version: number;
};
export type Health = {
  workers_alive: number;
  scheduler_last_at: string | null;
  queue_depth: number;
  leased: number;
  oldest_due_seconds: number;
  dead_letters: {
    id: number;
    run_id: number;
    reason: string;
    created_at: string;
  }[];
};
export const runtimeApi = (environment: string) => {
  const options = { params: { environment } };
  return {
    list: (filters: Record<string, string | number>) =>
      api
        .get<ExecutionList>("/power-apps/executions", {
          params: { environment, ...filters },
        })
        .then((r) => r.data),
    history: (id: number) =>
      api
        .get<RuntimeHistory>(`/power-apps/executions/${id}`, options)
        .then((r) => r.data),
    report: (id: number) =>
      api
        .get<RuntimeHistory>(`/power-apps/executions/${id}/export`, options)
        .then((r) => r.data),
    deployment: (id: number) =>
      api
        .get<Deployment>(`/power-apps/automations/${id}/runtime`, options)
        .then((r) => r.data),
    transition: (
      id: number,
      action: string,
      version: number,
      policy: RuntimePolicy,
    ) =>
      api
        .post<Deployment>(
          `/power-apps/automations/${id}/runtime/${action}`,
          { expected_version: version, policy },
          options,
        )
        .then((r) => r.data),
    execute: (id: number, input: Record<string, unknown>, key: string) =>
      api
        .post<{ id: number }>(
          `/power-apps/automations/${id}/execute`,
          { input, idempotency_key: key },
          options,
        )
        .then((r) => r.data),
    action: (id: number, action: "cancel" | "retry") =>
      api.post(`/power-apps/executions/${id}/${action}`, {}, options),
    rerun: (id: number, input: Record<string, unknown>, key: string) =>
      api
        .post<{ id: number }>(
          `/power-apps/executions/${id}/rerun`,
          { input, idempotency_key: key, confirm: true },
          options,
        )
        .then((r) => r.data),
    triggers: (id: number) =>
      api
        .get<{ items: RuntimeTrigger[] }>(
          `/power-apps/automations/${id}/triggers`,
          options,
        )
        .then((r) => r.data.items),
    configure: (
      id: number,
      kind: string,
      enabled: boolean,
      config: Record<string, unknown>,
    ) =>
      api
        .put<{
          endpoint: string | null;
          secret: string | null;
          next_at: string | null;
        }>(
          `/power-apps/automations/${id}/triggers/${kind}`,
          { enabled, config },
          options,
        )
        .then((r) => r.data),
    rotate: (id: number) =>
      api
        .post<{ secret: string }>(
          `/power-apps/automations/${id}/triggers/webhook/rotate`,
          {},
          options,
        )
        .then((r) => r.data),
    limits: (id: number, version: number, policy: RuntimePolicy) =>
      api
        .put<Deployment>(
          `/power-apps/automations/${id}/runtime-limits`,
          { expected_version: version, policy },
          options,
        )
        .then((r) => r.data),
    resume: (id: number, event_key: string) =>
      api.post(`/power-apps/executions/${id}/resume`, { event_key }, options),
    health: () =>
      api
        .get<Health>("/power-apps/runtime/health", options)
        .then((r) => r.data),
  };
};
export function runtimeError(error: unknown): string {
  if (error instanceof SyntaxError)
    return "Enter valid JSON before continuing.";
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "issues" in detail)
    return (detail as { issues: { message: string }[] }).issues
      .map((i) => i.message)
      .join(" · ");
  return "The request could not be completed. Check the configuration and your current access.";
}
