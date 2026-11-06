import definitions from "../../../backend/app/core/form_defaults.json";
import { useAuthStore } from "@/store/authStore";

export type DefaultValue = string | number | boolean | number[] | null;
export type DefaultValues = Record<string, DefaultValue>;
export type DefaultsPayload = { values: DefaultValues; modules: Record<string, DefaultValues>; companyId: number; branchId: number | null; leadSources?: string[] };
const builtIn = Object.fromEntries(definitions.map(field => [field.key, field.default])) as DefaultValues;
function storedContext(key: string): string | null { try { return sessionStorage.getItem(key); } catch { return null; } }
let snapshot: { scope: string; payload: DefaultsPayload } | undefined;
export function defaultsScope() {
  const user = useAuthStore.getState().user;
  return `${user?.id}:${storedContext("suite-organization") || user?.access?.companyId}:${storedContext("suite-branch") || ""}`;
}
export function installFormDefaults(payload: DefaultsPayload) {
  if (payload.branchId && !storedContext("suite-branch")) { try { sessionStorage.setItem("suite-branch", String(payload.branchId)); } catch { /* Preferences still work without browser storage. */ } }
  snapshot = { scope: defaultsScope(), payload };
}
export function currentModule(): string {
  const prefix = typeof location === "undefined" ? "" : location.pathname.split("/")[1];
  return prefix === "pms" ? "project_management" : ["crm", "srm", "fam", "hrms"].includes(prefix) ? prefix : "";
}
export function formDefaults(module = currentModule()): DefaultValues {
  if (snapshot?.scope !== defaultsScope()) return { ...builtIn };
  return { ...builtIn, ...snapshot.payload.values, ...(snapshot.payload.modules[module] || {}) };
}
export function defaultText(key: string, module?: string): string { return String(formDefaults(module)[key] ?? ""); }
export function leadSourceOptions(): string[] {
  const field = definitions.find(field => field.key === "lead_source");
  return snapshot?.scope === defaultsScope() && snapshot.payload.leadSources ? snapshot.payload.leadSources : (field?.options || []).map(option=>String(option.value));
}
export function defaultNumber(key: string, module?: string): number { return Number(formDefaults(module)[key] ?? 0); }
export function defaultId(key: string, module?: string): number | undefined { return defaultNumber(key, module) || undefined; }
export function defaultOwner(module?: string): number | undefined {
  const values = formDefaults(module);
  return values.owner_mode === "specific_user" ? Number(values.owner_id) || undefined : values.owner_mode === "current_user" ? useAuthStore.getState().user?.id : undefined;
}
export function defaultPaymentTerms(module?: string) { const days = defaultNumber("payment_terms_days", module); return days ? `Net ${days}` : "Due on receipt"; }
export function defaultDateAfter(key: string, module?: string, from = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: defaultText("timezone", module), year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(from);
  const part = (type: string) => Number(parts.find(item => item.type === type)?.value);
  const day = new Date(Date.UTC(part("year"), part("month") - 1, part("day")));
  day.setUTCDate(day.getUTCDate() + defaultNumber(key, module));
  return day.toISOString().slice(0, 10);
}
export function displayDate(value: string | Date, module?: string): string {
  const date = new Date(value); if (Number.isNaN(date.getTime())) return "";
  let year: string, month: string, day: string;
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) [year, month, day] = value.split("-");
  else {
    const parts = new Intl.DateTimeFormat("en-CA", { timeZone: defaultText("timezone", module), year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(date);
    const part = (type: string) => parts.find(item => item.type === type)?.value || "";
    year = part("year"); month = part("month"); day = part("day");
  }
  const format = defaultText("date_format", module);
  return format === "YYYY-MM-DD" ? `${year}-${month}-${day}` : format === "MM/DD/YYYY" ? `${month}/${day}/${year}` : `${day}/${month}/${year}`;
}
export function displayTime(value: string | Date, module?: string): string { return new Date(value).toLocaleTimeString(defaultText("number_format", module), { hour: "2-digit", minute: "2-digit", hour12: defaultText("time_format", module) === "12h", timeZone: defaultText("timezone", module) }); }
export function displayNumber(value: number, options?: Intl.NumberFormatOptions, module?: string): string { return value.toLocaleString(defaultText("number_format", module), options); }
export function defaultFiscalYear(module?: string) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: defaultText("timezone", module), year: "numeric", month: "numeric" }).formatToParts(new Date());
  const year = Number(parts.find(part => part.type === "year")?.value), month = Number(parts.find(part => part.type === "month")?.value);
  const startMonth = defaultNumber("fiscal_year_start_month", module);
  const startYear = month >= startMonth ? year : year - 1;
  return { name: `FY ${startYear}-${String(startYear + 1).slice(-2)}`, start_date: `${startYear}-${String(startMonth).padStart(2, "0")}-01`, end_date: new Date(Date.UTC(startYear + 1, startMonth - 1, 0)).toISOString().slice(0, 10) };
}
