import { api } from "@/services/api";

export type AutomationRecord = Record<string, unknown> & { id?: number; name?: string; status?: string };

export const automationApi = {
  moduleInfo: () => api.get("/automation/module-info").then((res) => res.data),
  workflows: () => api.get<{ items: AutomationRecord[]; total: number }>("/automation/workflows").then((res) => res.data),
  createWorkflow: (data: unknown) => api.post("/automation/workflows", data).then((res) => res.data),
  activateWorkflow: (id: number) => api.post(`/automation/workflows/${id}/activate`).then((res) => res.data),
  deactivateWorkflow: (id: number) => api.post(`/automation/workflows/${id}/deactivate`).then((res) => res.data),
  testWorkflow: (id: number, data: unknown) => api.post(`/automation/workflows/${id}/test`, data).then((res) => res.data),
  blueprints: () => api.get<{ items: AutomationRecord[]; total: number }>("/automation/blueprints").then((res) => res.data),
  createBlueprint: (data: unknown) => api.post("/automation/blueprints", data).then((res) => res.data),
  validateTransition: (id: number, data: unknown) => api.post(`/automation/blueprints/${id}/validate-transition`, data).then((res) => res.data),
  approvals: () => api.get<{ items: AutomationRecord[]; total: number }>("/automation/approvals").then((res) => res.data),
  createApprovalRule: (data: unknown) => api.post("/automation/approvals/rules", data).then((res) => res.data),
  createApproval: (data: unknown) => api.post("/automation/approvals", data).then((res) => res.data),
  submitApproval: (id: number) => api.post(`/automation/approvals/${id}/submit`).then((res) => res.data),
  approveApproval: (id: number, comment = "Approved from Automation Studio") => api.post(`/automation/approvals/${id}/approve`, { comment }).then((res) => res.data),
  rejectApproval: (id: number, comment = "Rejected from Automation Studio") => api.post(`/automation/approvals/${id}/reject`, { comment }).then((res) => res.data),
  assignmentRules: () => api.get<{ items: AutomationRecord[]; total: number }>("/automation/assignment-rules").then((res) => res.data),
  createAssignmentRule: (data: unknown) => api.post("/automation/assignment-rules", data).then((res) => res.data),
  testAssignmentRule: (id: number, data: unknown) => api.post(`/automation/assignment-rules/${id}/test`, data).then((res) => res.data),
  cadences: () => api.get<{ items: AutomationRecord[]; total: number }>("/automation/cadences").then((res) => res.data),
  createCadence: (data: unknown) => api.post("/automation/cadences", data).then((res) => res.data),
  enrollCadence: (id: number, data: unknown) => api.post(`/automation/cadences/${id}/enroll`, data).then((res) => res.data),
  pauseCadence: (id: number) => api.post(`/automation/cadences/${id}/pause`).then((res) => res.data),
  resumeCadence: (id: number) => api.post(`/automation/cadences/${id}/resume`).then((res) => res.data),
  webhooks: () => api.get<{ items: AutomationRecord[]; total: number }>("/automation/webhooks").then((res) => res.data),
  createWebhook: (data: unknown) => api.post("/automation/webhooks", data).then((res) => res.data),
  testWebhook: (id: number, data: unknown) => api.post(`/automation/webhooks/${id}/test`, data).then((res) => res.data),
  logs: () => api.get<{ items: AutomationRecord[]; total: number }>("/automation/logs").then((res) => res.data),
  retryLog: (id: number) => api.post(`/automation/logs/${id}/retry`).then((res) => res.data),
};

