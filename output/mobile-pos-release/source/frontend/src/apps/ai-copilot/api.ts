import { api } from "@/services/api";

export type AICopilotRecord = Record<string, any>;

export const aiCopilotApi = {
  providerSettings: () => api.get<{ items: AICopilotRecord[] }>("/ai/provider-settings").then((response) => response.data),
  createProviderSetting: (data: AICopilotRecord) => api.post<AICopilotRecord>("/ai/provider-settings", data).then((response) => response.data),
  updateProviderSetting: (id: number, data: AICopilotRecord) => api.put<AICopilotRecord>(`/ai/provider-settings/${id}`, data).then((response) => response.data),
  testProviderSetting: (id: number) => api.post<AICopilotRecord>(`/ai/provider-settings/${id}/test`, {}).then((response) => response.data),
  promptTemplates: () => api.get<{ items: AICopilotRecord[] }>("/ai/prompt-templates").then((response) => response.data),
  createPromptTemplate: (data: AICopilotRecord) => api.post<AICopilotRecord>("/ai/prompt-templates", data).then((response) => response.data),
  run: (path: string, data: AICopilotRecord) => api.post<AICopilotRecord>(`/ai/${path}`, data).then((response) => response.data),
  previewAction: (data: AICopilotRecord) => api.post<AICopilotRecord>("/ai/agent-action/preview", data).then((response) => response.data),
  confirmAction: (data: AICopilotRecord) => api.post<AICopilotRecord>("/ai/agent-action/confirm", data).then((response) => response.data),
  actionLog: () => api.get<{ items: AICopilotRecord[]; total: number }>("/ai/action-log").then((response) => response.data),
  feedback: (data: AICopilotRecord) => api.post<AICopilotRecord>("/ai/feedback", data).then((response) => response.data),
};

