import {crmApi, type CRMApiRecord} from "../api";
import {defaultText} from "@/lib/form-defaults";

export function dealError(error: unknown): string {
  const value = error as {response?: {data?: {detail?: unknown}}; message?: string};
  const detail = value?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map(item => {
    const field = String(item.loc?.slice(-1)[0] || "Field").replace(/_/g, " ");
    return `${field}: ${String(item.msg || "Check this value")}`;
  }).join(". ");
  if (detail && typeof detail === "object" && "message" in detail) return String(detail.message);
  return "Unable to complete this request. Your draft is retained; try again.";
}

export async function dealOptions(resource: string, params: Record<string, string | number> = {}, signal?: AbortSignal) {
  const items: CRMApiRecord[] = [];
  let page = 1, pages = 1;
  do {
    // The API maximum is 100. Never bypass it with an unlimited page request.
    const response = await crmApi.list(resource, {...params, page, per_page: 100}, signal ? {signal, progress:false, recordCache:false} : undefined);
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
    items.push(...response.data.items);
    pages = response.data.pages || Math.ceil((response.data.total || 0) / 100) || 1;
    page++;
  } while (page <= pages);
  return items;
}

export function dealMoney(amount: unknown, currency: unknown = "INR") {
  const code = String(currency || "INR");
  try {return new Intl.NumberFormat(defaultText("number_format"), {style: "currency", currency: code, maximumFractionDigits: 2}).format(Number(amount || 0));}
  catch {return `${code} ${Number(amount || 0).toLocaleString(defaultText("number_format"))}`;}
}

export const dealTabs = ["Deal Overview", "Financial Information", "People and Ownership", "Timeline", "Qualification", "Notes & Attachments"];
export const qualificationFields = ["budget_range", "decision_authority", "business_need", "purchase_timeline", "pain_points", "proposed_solution", "competitor", "decision_criteria", "decision_process", "champion", "economic_buyer", "risks", "win_strategy"];
export const label = (value: string) => value.replace(/_/g, " ").replace(/\b\w/g, letter => letter.toUpperCase());
