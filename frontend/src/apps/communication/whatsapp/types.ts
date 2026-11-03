export const whatsappBase = "/integrations/whatsapp";
export type Connection = { id: number; wabaId: string; phoneNumberId: string; displayNumber?: string; businessName?: string; status: string; source: string; subscribed: boolean };
export type Status = { configured: boolean; connection: Connection | null; canAdmin: boolean; onboardingConfigured: boolean; webhookConfigured: boolean; webhookPath: string };
export type Contact = { id: number; recipient: string; name?: string; entityType?: string; entityId?: number; consent: string; consentSource?: string; serviceWindowOpen: boolean; serviceWindowEndsAt?: string };
export type Message = { id: number; direction: string; body: string; status: string; kind: string; createdAt: string; errorCode?: string };
export type Template = { id: string; name: string; language: string; status: string; category: string; components?: { type: string; text?: string; format?: string; buttons?: { url?: string }[] }[] };
export type RecordLink = { entityType: string; entityId: string };
export function whatsappError(error: unknown) {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === "string" ? detail : error instanceof Error && !('response' in error) ? error.message : "The request failed. Review the entered fields and try again.";
}
export function templateParameters(template?: Template) {
  return [...new Set((template?.components?.find(c => c.type === "BODY")?.text || "").match(/\{\{\d+\}\}/g) || [])]
    .sort((a, b) => Number(a.replace(/\D/g, "")) - Number(b.replace(/\D/g, "")));
}
export function templateSupported(template: Template) {
  return !(template.components || []).some(c => (c.type === "HEADER" && (c.format !== "TEXT" || /\{\{/.test(c.text || ""))) ||
    (c.type === "BUTTONS" && c.buttons?.some(b => /\{\{/.test(b.url || "")))) &&
    !/\{\{[^0-9]/.test(template.components?.find(c => c.type === "BODY")?.text || "");
}
