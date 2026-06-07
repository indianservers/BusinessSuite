import { api } from "@/services/api";

export type SaaSRecord = Record<string, any>;
type ListResponse = { items: SaaSRecord[]; total: number };

const portalHeaders = () => {
  const token = window.localStorage.getItem("portalSessionToken");
  return token ? { "X-Portal-Session": token } : {};
};

export const saasApi = {
  portalUsers: () => api.get<ListResponse>("/portals/users").then((response) => response.data),
  invitePortalUser: (data: SaaSRecord) => api.post<SaaSRecord>("/portals/invite", data).then((response) => response.data),
  customerMe: () => api.get<SaaSRecord>("/customer-portal/me", { headers: portalHeaders() }).then((response) => response.data),
  customerQuotes: () => api.get<ListResponse>("/customer-portal/quotes", { headers: portalHeaders() }).then((response) => response.data),
  customerInvoices: () => api.get<ListResponse>("/customer-portal/invoices", { headers: portalHeaders() }).then((response) => response.data),
  customerProjects: () => api.get<ListResponse>("/customer-portal/projects", { headers: portalHeaders() }).then((response) => response.data),
  acceptQuote: (id: number) => api.post<SaaSRecord>(`/customer-portal/quotes/${id}/accept`, {}, { headers: portalHeaders() }).then((response) => response.data),
  partnerLeads: () => api.get<ListResponse>("/partner-portal/leads", { headers: portalHeaders() }).then((response) => response.data),
  submitPartnerLead: (data: SaaSRecord) => api.post<SaaSRecord>("/partner-portal/leads", data, { headers: portalHeaders() }).then((response) => response.data),
  partnerDashboard: () => api.get<SaaSRecord>("/partner-portal/dashboard", { headers: portalHeaders() }).then((response) => response.data),
  checkIns: () => api.get<ListResponse>("/mobile/check-in").then((response) => response.data),
  createCheckIn: (data: SaaSRecord) => api.post<SaaSRecord>("/mobile/check-in", data).then((response) => response.data),
  apiKeys: () => api.get<ListResponse>("/developer/api-keys").then((response) => response.data),
  createApiKey: (data: SaaSRecord) => api.post<SaaSRecord>("/developer/api-keys", data).then((response) => response.data),
  revokeApiKey: (id: number) => api.delete(`/developer/api-keys/${id}`),
  webhooks: () => api.get<ListResponse>("/developer/webhooks").then((response) => response.data),
  createWebhook: (data: SaaSRecord) => api.post<SaaSRecord>("/developer/webhooks", data).then((response) => response.data),
  testWebhook: (id: number) => api.post<SaaSRecord>(`/developer/webhooks/${id}/test`, {}).then((response) => response.data),
  replayWebhook: (id: number) => api.post<SaaSRecord>(`/developer/webhooks/${id}/replay`, {}).then((response) => response.data),
  apiLogs: () => api.get<ListResponse>("/developer/api-logs").then((response) => response.data),
  developerDocs: () => api.get<SaaSRecord>("/developer/docs").then((response) => response.data),
  marketplaceApps: () => api.get<ListResponse>("/marketplace/apps").then((response) => response.data),
  createMarketplaceApp: (data: SaaSRecord) => api.post<SaaSRecord>("/marketplace/apps", data).then((response) => response.data),
  installMarketplaceApp: (id: number) => api.post<SaaSRecord>(`/marketplace/apps/${id}/install`, {}).then((response) => response.data),
  installedMarketplaceApps: () => api.get<ListResponse>("/marketplace/installed").then((response) => response.data),
  sandboxes: () => api.get<ListResponse>("/admin/sandbox").then((response) => response.data),
  createSandbox: (data: SaaSRecord) => api.post<SaaSRecord>("/admin/sandbox/create", data).then((response) => response.data),
  refreshSandbox: (id: number) => api.post<SaaSRecord>(`/admin/sandbox/${id}/refresh`, {}).then((response) => response.data),
  companySettings: () => api.get<SaaSRecord>("/admin/company-settings").then((response) => response.data),
  updateCompanySettings: (data: SaaSRecord) => api.put<SaaSRecord>("/admin/company-settings", data).then((response) => response.data),
  featureFlags: () => api.get<ListResponse>("/admin/feature-flags").then((response) => response.data),
  upsertFeatureFlag: (data: SaaSRecord) => api.put<SaaSRecord>("/admin/feature-flags", data).then((response) => response.data),
  subscriptionPlans: () => api.get<ListResponse>("/admin/subscription-plans").then((response) => response.data),
  subscription: () => api.get<SaaSRecord>("/admin/subscription").then((response) => response.data),
  updateSubscription: (data: SaaSRecord) => api.put<SaaSRecord>("/admin/subscription", data).then((response) => response.data),
  usage: () => api.get<ListResponse>("/admin/usage").then((response) => response.data),
};
