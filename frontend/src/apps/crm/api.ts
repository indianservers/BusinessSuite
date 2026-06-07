import { api } from "@/services/api";

export interface CRMApiRecord {
  [key: string]: CRMApiValue;
}

export type CRMApiValue = string | number | boolean | null | undefined | CRMApiRecord | CRMApiRecord[] | string[] | number[] | boolean[];

export type CRMListParams = {
  page?: number;
  per_page?: number;
  search?: string;
  sort_by?: string;
  sort_order?: "asc" | "desc";
  owner_id?: number;
  [key: string]: string | number | boolean | undefined;
};

export type CRMPaginatedResponse<T = CRMApiRecord> = {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
};

export type CRMCalendarEvent = {
  id: string;
  recordId: number;
  source: string;
  title: string;
  start: string;
  end: string;
  type: string;
  entityType?: string | null;
  entityId?: number | null;
  ownerId?: number | null;
  status?: string | null;
  color?: string;
  category?: string;
  syncStatus?: string | null;
  externalProvider?: string | null;
  externalEventId?: string | null;
};

export type CRMCalendarResponse = {
  items: CRMCalendarEvent[];
  startDate: string;
  endDate: string;
  total: number;
};

export type CRMApprovalStep = CRMApiRecord & {
  id?: number;
  stepOrder?: number;
  approverType?: "user" | "role" | "manager";
  approverId?: number | null;
  actionOnReject?: "stop" | "send_back";
};

export type CRMApprovalWorkflow = CRMApiRecord & {
  id: number;
  name: string;
  entityType: string;
  triggerType: string;
  conditions?: CRMApiRecord;
  isActive?: boolean;
  steps?: CRMApprovalStep[];
};

export type CRMApprovalRequest = CRMApiRecord & {
  id: number;
  workflowId?: number | null;
  entityType: string;
  entityId: number;
  status: "pending" | "approved" | "rejected" | "cancelled";
  submittedBy?: number | null;
  submittedAt?: string | null;
  completedAt?: string | null;
  workflow?: CRMApprovalWorkflow | null;
  steps?: CRMApiRecord[];
};

export type CRMDuplicateGroup = CRMApiRecord & {
  id: string;
  entityType: "lead" | "contact" | "account";
  score: number;
  reasons: string[];
  matchingFields: string[];
  recordIds: number[];
  records: CRMApiRecord[];
  pairs?: CRMApiRecord[];
};

export type CRMWinLossReport = {
  summary: {
    totalDeals: number;
    closedDeals: number;
    wonDeals: number;
    lostDeals: number;
    winRate: number;
    wonRevenue: number;
    lostAmount: number;
    averageWonDealSize: number;
    averageLostDealSize: number;
    averageSalesCycleDays: number;
  };
  winRateByMonth: CRMApiRecord[];
  winRateByOwner: CRMApiRecord[];
  winRateByPipeline: CRMApiRecord[];
  winLossBySource: CRMApiRecord[];
  averageDealSize: { won: number; lost: number };
  lostReasonBreakdown: CRMApiRecord[];
  topCompetitors: CRMApiRecord[];
  revenueWonTrend: CRMApiRecord[];
  deals: CRMApiRecord[];
  filters?: CRMApiRecord;
};

export type CRMEnrichmentField = {
  key: string;
  label: string;
  targetField?: string | null;
  supported: boolean;
  oldValue?: CRMApiValue;
  newValue?: CRMApiValue;
  changed: boolean;
};

export type CRMEnrichmentPreview = {
  logId?: number;
  entityType: string;
  entityId: number;
  provider: string;
  fields: CRMEnrichmentField[];
  values: CRMApiRecord;
  supportedFields: string[];
};

export const crmApi = {
  moduleInfo: () => api.get("/crm/module-info"),
  calendar: (params?: Record<string, unknown>) => api.get<CRMCalendarResponse>("/crm/calendar", { params }),
  calendarIntegrations: () => api.get<{ items: CRMApiRecord[]; total: number }>("/crm/calendar-integrations"),
  connectCalendarIntegration: (data: CRMApiRecord) => api.post<CRMApiRecord>("/crm/calendar-integrations/connect", data),
  disconnectCalendarIntegration: (id: number) => api.delete(`/crm/calendar-integrations/${id}`),
  syncMeeting: (id: number, data?: CRMApiRecord) => api.post<CRMApiRecord>(`/crm/meetings/${id}/sync`, data || {}),
  emailTemplates: (params?: Record<string, unknown>) => api.get("/crm/email-templates", { params }),
  approvalWorkflows: () => api.get<{ items: CRMApprovalWorkflow[]; total: number }>("/crm/approval-workflows"),
  createApprovalWorkflow: (data: CRMApiRecord) => api.post<CRMApprovalWorkflow>("/crm/approval-workflows", data),
  updateApprovalWorkflow: (id: number, data: CRMApiRecord) => api.patch<CRMApprovalWorkflow>(`/crm/approval-workflows/${id}`, data),
  submitApproval: (data: CRMApiRecord) => api.post<CRMApprovalRequest>("/crm/approvals/submit", data),
  approve: (id: number, data?: CRMApiRecord) => api.post<CRMApprovalRequest>(`/crm/approvals/${id}/approve`, data || {}),
  reject: (id: number, data?: CRMApiRecord) => api.post<CRMApprovalRequest>(`/crm/approvals/${id}/reject`, data || {}),
  myPendingApprovals: () => api.get<{ items: CRMApprovalRequest[]; total: number }>("/crm/approvals/my-pending"),
  approvals: (params?: Record<string, unknown>) => api.get<{ items: CRMApprovalRequest[]; total: number }>("/crm/approvals", { params }),
  duplicates: (params: { entityType: string }) => api.get<{ items: CRMDuplicateGroup[]; total: number; entityType: string }>("/crm/duplicates", { params }),
  scanDuplicates: (data?: CRMApiRecord) => api.post<{ items: CRMDuplicateGroup[]; total: number }>("/crm/duplicates/scan", data || {}),
  mergeDuplicates: (data: CRMApiRecord) => api.post<{ winner: CRMApiRecord; mergedIds: number[]; relatedCounts: CRMApiRecord }>("/crm/duplicates/merge", data),
  quotationPdf: (id: number, download = false) => api.get<Blob>(`/crm/quotations/${id}/pdf`, { params: { download }, responseType: "blob" }),
  quotePdf: (id: number, download = false) => api.get<Blob>(`/crm/quotes/${id}/pdf`, { params: { download }, responseType: "blob" }),
  addQuoteLine: (id: number, data: CRMApiRecord) => api.post<CRMApiRecord>(`/crm/quotes/${id}/lines`, data),
  updateQuoteLine: (id: number, data: CRMApiRecord) => api.patch<CRMApiRecord>(`/crm/quote-lines/${id}`, data),
  deleteQuoteLine: (id: number) => api.delete(`/crm/quote-lines/${id}`),
  calculateQuote: (id: number) => api.post<CRMApiRecord>(`/crm/quotes/${id}/calculate`, {}),
  submitQuote: (id: number, data?: CRMApiRecord) => api.post<CRMApiRecord>(`/crm/quotes/${id}/submit`, data || {}),
  approveQuote: (id: number, data?: CRMApiRecord) => api.post<CRMApiRecord>(`/crm/quotes/${id}/approve`, data || {}),
  rejectQuote: (id: number, data?: CRMApiRecord) => api.post<CRMApiRecord>(`/crm/quotes/${id}/reject`, data || {}),
  sendQuote: (id: number) => api.post<CRMApiRecord>(`/crm/quotes/${id}/send`, {}),
  acceptQuote: (id: number) => api.post<CRMApiRecord>(`/crm/quotes/${id}/accept`, {}),
  declineQuote: (id: number) => api.post<CRMApiRecord>(`/crm/quotes/${id}/decline`, {}),
  newQuoteVersion: (id: number) => api.post<CRMApiRecord>(`/crm/quotes/${id}/new-version`, {}),
  convertQuoteToSrm: (id: number) => api.post<CRMApiRecord>(`/crm/quotes/${id}/convert-to-srm`, {}),
  evaluateCpq: (data: CRMApiRecord) => api.post<CRMApiRecord>("/crm/cpq/evaluate", data),
  sendQuotationPdfEmail: (id: number, data: CRMApiRecord) => api.post<CRMApiRecord>(`/crm/quotations/${id}/send-pdf-email`, data),
  searchUsers: (params: { q: string; limit?: number }) => api.get<{ items: CRMApiRecord[]; total: number }>("/users/search", { params }),
  winLossReport: (params?: Record<string, unknown>) => api.get<CRMWinLossReport>("/crm/reports/win-loss", { params }),
  salesFunnelReport: (params?: Record<string, unknown>) => api.get<{ items: CRMApiRecord[]; total: number }>("/crm/reports/sales-funnel", { params }),
  forecast: (params?: Record<string, unknown>) => api.get<{ summary: CRMApiRecord; items: CRMApiRecord[]; total: number }>("/crm/forecast", { params }),
  forecastByOwner: (params?: Record<string, unknown>) => api.get<{ summary: CRMApiRecord; items: CRMApiRecord[]; total: number }>("/crm/forecast/by-owner", { params }),
  forecastByTeam: (params?: Record<string, unknown>) => api.get<{ summary: CRMApiRecord; items: CRMApiRecord[]; total: number }>("/crm/forecast/by-team", { params }),
  forecastByTerritory: (params?: Record<string, unknown>) => api.get<{ summary: CRMApiRecord; items: CRMApiRecord[]; total: number }>("/crm/forecast/by-territory", { params }),
  createForecastSnapshot: (data: CRMApiRecord) => api.post<CRMApiRecord>("/crm/forecast/snapshot", data),
  targets: (params?: Record<string, unknown>) => api.get<{ items: CRMApiRecord[]; total: number }>("/crm/targets", { params }),
  createTarget: (data: CRMApiRecord) => api.post<CRMApiRecord>("/crm/targets", data),
  updateTarget: (id: number, data: CRMApiRecord) => api.put<CRMApiRecord>(`/crm/targets/${id}`, data),
  targetPerformance: (params?: Record<string, unknown>) => api.get<{ items: CRMApiRecord[]; total: number }>("/crm/targets/performance", { params }),
  funnel: (params?: Record<string, unknown>) => api.get<{ items: CRMApiRecord[]; total: number }>("/crm/funnel", { params }),
  lostAnalysis: (params?: Record<string, unknown>) => api.get<CRMApiRecord>("/crm/lost-analysis", { params }),
  salesPerformance: (params?: Record<string, unknown>) => api.get<{ summary: CRMApiRecord; items: CRMApiRecord[]; total: number }>("/crm/sales-performance", { params }),
  revenueTrendReport: (params?: Record<string, unknown>) => api.get<{ items: CRMApiRecord[]; total: number }>("/crm/reports/revenue-trend", { params }),
  territoryReport: () => api.get<{ items: CRMApiRecord[]; total: number }>("/crm/reports/territories"),
  territories: () => api.get<{ items: CRMApiRecord[]; total: number }>("/crm/territories"),
  createTerritory: (data: CRMApiRecord) => api.post<CRMApiRecord>("/crm/territories", data),
  updateTerritory: (id: number, data: CRMApiRecord) => api.patch<CRMApiRecord>(`/crm/territories/${id}`, data),
  deleteTerritory: (id: number) => api.delete(`/crm/territories/${id}`),
  addTerritoryUser: (id: number, data: CRMApiRecord) => api.post<CRMApiRecord>(`/crm/territories/${id}/users`, data),
  assignTerritory: (id: number, data: CRMApiRecord) => api.post<CRMApiRecord>(`/crm/territories/${id}/assign`, data),
  autoAssignTerritories: (data?: CRMApiRecord) => api.post<{ updated: number; items: CRMApiRecord[] }>("/crm/territories/auto-assign", data || {}),
  enrichmentPreview: (data: CRMApiRecord) => api.post<CRMEnrichmentPreview>("/crm/enrichment/preview", data),
  enrichmentApply: (data: CRMApiRecord) => api.post<{ record: CRMApiRecord; log: CRMApiRecord; appliedFields: string[] }>("/crm/enrichment/apply", data),
  enrichmentHistory: (params: { entityType: string; entityId: number }) => api.get<{ items: CRMApiRecord[]; total: number }>("/crm/enrichment/history", { params }),
  messages: (params: { entityType: string; entityId: number }) => api.get<{ items: CRMApiRecord[]; total: number }>("/crm/messages", { params }),
  messageTemplates: (params?: Record<string, unknown>) => api.get<{ items: CRMApiRecord[] }>("/crm/message-templates", { params }),
  createMessageTemplate: (data: CRMApiRecord) => api.post<CRMApiRecord>("/crm/message-templates", data),
  sendMessage: (data: CRMApiRecord) => api.post<CRMApiRecord>("/crm/messages/send", data),
  webhooks: () => api.get<{ items: CRMApiRecord[]; total: number; events: string[] }>("/crm/webhooks"),
  createWebhook: (data: CRMApiRecord) => api.post<CRMApiRecord>("/crm/webhooks", data),
  updateWebhook: (id: number, data: CRMApiRecord) => api.patch<CRMApiRecord>(`/crm/webhooks/${id}`, data),
  deleteWebhook: (id: number) => api.delete(`/crm/webhooks/${id}`),
  testWebhook: (id: number) => api.post<CRMApiRecord>(`/crm/webhooks/${id}/test`, {}),
  webhookDeliveries: (id: number) => api.get<{ items: CRMApiRecord[]; total: number }>(`/crm/webhooks/${id}/deliveries`),
  createEmailTemplate: (data: CRMApiRecord) => api.post("/crm/email-templates", data),
  sendEmail: <T = CRMApiRecord>(data: CRMApiRecord) => api.post<T>("/crm/emails/send", data),
  upsertCustomFieldValue: <T = CRMApiRecord>(data: CRMApiRecord) => api.post<T>("/crm/custom-field-values/upsert", data),
  list: <T = CRMApiRecord>(entity: string, params?: CRMListParams) =>
    api.get<CRMPaginatedResponse<T>>(`/crm/${entity}`, { params }),
  get: <T = CRMApiRecord>(entity: string, id: number) => api.get<T>(`/crm/${entity}/${id}`),
  related: <T = CRMApiRecord>(entity: string, id: number) => api.get<T>(`/crm/${entity}/${id}/related`),
  create: <T = CRMApiRecord>(entity: string, data: CRMApiRecord) => api.post<T>(`/crm/${entity}`, data),
  createPipelineStage: <T = CRMApiRecord>(pipelineId: number, data: CRMApiRecord) => api.post<T>(`/crm/pipelines/${pipelineId}/stages`, data),
  convertLead: <T = CRMApiRecord>(leadId: number, data: CRMApiRecord) => api.post<T>(`/crm/leads/${leadId}/convert`, data),
  importRows: <T = CRMApiRecord>(entity: string, rows: CRMApiRecord[]) => api.post<T>(`/crm/${entity}/import`, { rows }),
  exportEntity: (entity: string) => api.get<Blob>(`/crm/${entity}/export`, { responseType: "blob" }),
  recalculateLeadScore: <T = CRMApiRecord>(leadId: number) => api.post<T>(`/crm/leads/${leadId}/recalculate-score`),
  recalculateLeadScores: () => api.post<{ updated: number; total: number }>("/crm/leads/recalculate-scores"),
  update: <T = CRMApiRecord>(entity: string, id: number, data: CRMApiRecord) =>
    api.patch<T>(`/crm/${entity}/${id}`, data),
  delete: (entity: string, id: number, params?: Record<string, unknown>) => api.delete(`/crm/${entity}/${id}`, { params }),
};
