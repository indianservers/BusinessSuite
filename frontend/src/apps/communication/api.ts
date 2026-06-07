import { api } from "@/services/api";

export type CommunicationRecord = Record<string, unknown> & { id?: number; name?: string; subject?: string; status?: string };
export type CommunicationList = { items: CommunicationRecord[]; total: number };

const list = (path: string) => api.get<CommunicationList>(path).then((res) => res.data);
const create = (path: string, data: unknown) => api.post(path, data).then((res) => res.data);

export const communicationApi = {
  moduleInfo: () => api.get("/communication/module-info").then((res) => res.data),
  templates: () => list("/communication/email-templates"),
  createTemplate: (data: unknown) => create("/communication/email-templates", data),
  draftEmail: (data: unknown) => create("/communication/emails/draft", data),
  sendEmail: (data: unknown) => create("/communication/emails/send", data),
  timeline: (recordType = "lead", recordId = 1) => list(`/communication/timeline/${recordType}/${recordId}`),
  webforms: () => list("/communication/webforms"),
  createWebform: (data: unknown) => create("/communication/webforms", data),
  publicWebform: (slug: string) => api.get(`/public/webforms/${slug}`).then((res) => res.data),
  submitWebform: (slug: string, data: unknown) => create(`/public/webforms/${slug}/submit`, data),
  autoResponseRules: () => list("/communication/auto-response-rules"),
  createAutoResponseRule: (data: unknown) => create("/communication/auto-response-rules", data),
  campaigns: () => list("/communication/campaigns"),
  createCampaign: (data: unknown) => create("/communication/campaigns", data),
  previewCampaign: (id: number) => create(`/communication/campaigns/${id}/preview`, {}),
  sendCampaign: (id: number) => create(`/communication/campaigns/${id}/send`, {}),
  scheduleCampaign: (id: number, data: unknown) => create(`/communication/campaigns/${id}/schedule`, data),
  cancelCampaign: (id: number) => create(`/communication/campaigns/${id}/cancel`, {}),
  consents: () => list("/communication/consents"),
  createConsent: (data: unknown) => create("/communication/consents", data),
  optOut: (data: unknown) => create("/communication/opt-out", data),
  whatsappTemplates: () => list("/communication/whatsapp-templates"),
  createWhatsAppTemplate: (data: unknown) => create("/communication/whatsapp-templates", data),
  deliveryLogs: () => list("/communication/delivery-logs"),
};

