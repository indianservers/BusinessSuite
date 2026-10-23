import { api } from "@/services/api";

export type AiModule = "CRM" | "HRMS" | "PMS" | "CROSS";

export type AiAgent = {
  id: number;
  name: string;
  code: string;
  module: AiModule;
  description?: string | null;
  system_prompt?: string | null;
  model?: string | null;
  temperature?: number | null;
  is_active: boolean;
  requires_approval: boolean;
  created_at?: string;
  updated_at?: string;
};

export type AiConversation = {
  id: number;
  user_id: number;
  agent_id: number;
  module: AiModule;
  title?: string | null;
  related_entity_type?: string | null;
  related_entity_id?: string | null;
  status: string;
  created_at?: string;
  updated_at?: string;
};

export type AiMessage = {
  id: number;
  conversation_id: number;
  role: "user" | "assistant" | "system" | "tool";
  content?: string | null;
  tool_call_json?: Record<string, unknown> | null;
  tool_result_json?: Record<string, unknown> | null;
  created_at?: string;
};

export type AiApproval = {
  id: number;
  conversation_id?: number | null;
  agent_id?: number | null;
  user_id?: number | null;
  module: AiModule;
  action_type: string;
  related_entity_type?: string | null;
  related_entity_id?: string | null;
  proposed_action_json?: Record<string, unknown> | null;
  status: "pending" | "approved" | "rejected" | "expired" | "cancelled" | "failed";
  approved_by?: number | null;
  approved_at?: string | null;
  execution_status?: string | null;
  executed_at?: string | null;
  execution_result_json?: Record<string, unknown> | null;
  rejected_reason?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type AiAuditLog = {
  id: number;
  user_id?: number | null;
  agent_id?: number | null;
  module?: AiModule | string | null;
  action: string;
  status: string;
  related_entity_type?: string | null;
  related_entity_id?: string | null;
  input_json?: Record<string, unknown> | null;
  output_json?: Record<string, unknown> | null;
  created_at?: string;
};

export type AiAgentConfigRow = {
  agent: AiAgent;
  setting: {
    is_enabled: boolean;
    auto_action_enabled: boolean;
    approval_required: boolean;
    data_access_scope: "own_records" | "team" | "company" | string;
  };
};

export type AiChatResponse = {
  success: boolean;
  conversation_id: number;
  agent_id: number;
  message: string;
  tool_calls?: Array<Record<string, unknown>>;
  approvals?: Array<Record<string, unknown>>;
  suggested_actions?: Array<Record<string, unknown>>;
};

export type AiUsageLimit = {
  id?: number;
  user_id?: number | null;
  agent_id?: number | null;
  module?: AiModule | null;
  limit_type: "per_user" | "per_agent" | "per_company" | "per_module";
  max_requests: number;
  period: "hourly" | "daily" | "monthly";
  is_active: boolean;
};

export type AiPermissionRule = {
  id?: number;
  agent_id: number;
  role_id?: number | null;
  user_id?: number | null;
  can_use: boolean;
  can_configure: boolean;
  can_approve_actions: boolean;
  can_view_logs: boolean;
  can_export_conversations: boolean;
};

export type AiSecuritySettings = {
  ai_enabled: boolean;
  crm_ai_enabled: boolean;
  pms_ai_enabled: boolean;
  hrms_ai_enabled: boolean;
  cross_ai_enabled: boolean;
  emergency_message?: string | null;
};

export type AiHandoffNote = {
  id: number;
  conversation_id?: number | null;
  agent_id?: number | null;
  module: AiModule;
  related_entity_type?: string | null;
  related_entity_id?: string | null;
  assigned_to?: number | null;
  priority: "low" | "medium" | "high" | "urgent";
  summary: string;
  reason?: string | null;
  recommended_action?: string | null;
  status: "open" | "in_review" | "resolved" | "cancelled";
  created_by?: number | null;
  created_at?: string;
};

export const aiAgentsApi = {
  getAgents: (params?: { module?: AiModule | "ALL" }) =>
    api.get<AiAgent[]>("/ai-agents", {
      params: params?.module && params.module !== "ALL" ? { module: params.module } : undefined,
    }),
  getAgent: (agentId: number | string) => api.get<AiAgent>(`/ai-agents/${agentId}`),
  updateAgentStatus: (agentId: number | string, payload: { is_active: boolean }) =>
    api.patch<AiAgent>(`/ai-agents/${agentId}/status`, payload),
  getAgentConfig: () => api.get<AiAgentConfigRow[]>("/ai-agents/config"),
  updateAgentConfig: (agentId: number | string, payload: Record<string, unknown>) =>
    api.put(`/ai-agents/config/${agentId}`, payload),
  createConversation: (payload: Record<string, unknown>) =>
    api.post<AiConversation>("/ai-agents/conversations", payload),
  getConversations: (params?: Record<string, unknown>) =>
    api.get<AiConversation[]>("/ai-agents/conversations", { params }),
  getConversation: (conversationId: number | string) =>
    api.get<AiConversation>(`/ai-agents/conversations/${conversationId}`),
  getConversationMessages: (conversationId: number | string) =>
    api.get<AiMessage[]>(`/ai-agents/conversations/${conversationId}/messages`),
  sendMessage: (conversationId: number | string, payload: { content: string }) =>
    api.post(`/ai-agents/conversations/${conversationId}/messages`, payload),
  sendChatMessage: (agentId: number | string, payload: Record<string, unknown>) =>
    api.post<AiChatResponse>(`/ai-agents/${agentId}/chat`, payload),
  getPendingApprovals: (params?: Record<string, unknown>) =>
    api.get<AiApproval[]>("/ai-agents/approvals/pending", { params }),
  approveAiAction: (approvalId: number | string) =>
    api.post<AiApproval>(`/ai-agents/approvals/${approvalId}/approve`),
  rejectAiAction: (approvalId: number | string, payload: { rejected_reason: string }) =>
    api.post<AiApproval>(`/ai-agents/approvals/${approvalId}/reject`, payload),
  getAiLogs: (params?: Record<string, unknown>) => api.get<AiAuditLog[]>("/ai-agents/logs", { params }),
  getUsageSummary: () => api.get("/ai-agents/usage/summary"),
  getUsageLimits: () => api.get<AiUsageLimit[]>("/ai-agents/usage/limits"),
  updateUsageLimits: (payload: AiUsageLimit[]) => api.put("/ai-agents/usage/limits", payload),
  getSecuritySettings: () => api.get<AiSecuritySettings>("/ai-agents/security/settings"),
  updateSecuritySettings: (payload: AiSecuritySettings) => api.put("/ai-agents/security/settings", payload),
  getSecuritySummary: () => api.get("/ai-agents/security/summary"),
  getSecurityEvents: (params?: Record<string, unknown>) => api.get<AiAuditLog[]>("/ai-agents/security/events", { params }),
  getPermissions: () => api.get<AiPermissionRule[]>("/ai-agents/security/permissions"),
  updatePermissions: (payload: AiPermissionRule[]) => api.put("/ai-agents/security/permissions", payload),
  getAnalyticsSummary: () => api.get("/ai-agents/analytics/summary"),
  getAnalyticsByAgent: () => api.get("/ai-agents/analytics/by-agent"),
  getAnalyticsByModule: () => api.get("/ai-agents/analytics/by-module"),
  getAnalyticsByUser: () => api.get("/ai-agents/analytics/by-user"),
  getAnalyticsCost: () => api.get("/ai-agents/analytics/cost"),
  exportConversation: (conversationId: number | string, format: "pdf" | "csv" | "json") =>
    api.get(`/ai-agents/conversations/${conversationId}/export`, { params: { format }, responseType: "blob" }),
  submitFeedback: (messageId: number | string, payload: { rating: "thumbs_up" | "thumbs_down"; feedback_type?: string; feedback_text?: string }) =>
    api.post(`/ai-agents/messages/${messageId}/feedback`, payload),
  getFeedback: () => api.get("/ai-agents/feedback"),
  createHandoffNote: (payload: Record<string, unknown>) => api.post("/ai-agents/handoff-notes", payload),
  getHandoffNotes: (params?: Record<string, unknown>) => api.get<AiHandoffNote[]>("/ai-agents/handoff-notes", { params }),
  updateHandoffStatus: (noteId: number | string, payload: { status: AiHandoffNote["status"] }) =>
    api.patch(`/ai-agents/handoff-notes/${noteId}/status`, payload),
};
