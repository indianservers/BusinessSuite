import type { BranchAvailabilityValue } from "@/shared/BranchAvailability";
import type { Schedule } from "@/shared/follow-ups/ScheduleFields";
import { useEffect, useState } from "react";
import { api } from "@/services/api";

export type CatalogSource = "pms" | "crm" | "srm";
export type CatalogKind = "product" | "service";
export type CatalogPrice = { id: string; name: string; amount: number; currency: string; interval: "once" | "day" | "week" | "month" | "year" };
export type CatalogItem = {
  branch_availability?: BranchAvailabilityValue | null; follow_up?: Schedule; id: number; kind: CatalogKind; name: string; code: string; description: string; category: string; price: number; currency: string; tax: number; unit: string; barcode?: string; hsn_code?: string; cost?: number; mrp?: number; reorder_level?: number; track_inventory?: boolean; status: "Active" | "Archived"; workspace_id: number | null; images: string[]; custom_fields: Record<string, string | number | boolean | null>; pricing_options: CatalogPrice[]; version: number };
export type CatalogLine = { kind: CatalogKind; item_id: number; name?: string; pricing_id?: string | null; quantity: number; unit_price: number; discount: number; currency?: string; tax_rate?: number; total_amount?: number; item?: CatalogItem };
export const linePayload = (line: CatalogLine) => ({ kind: line.kind, item_id: line.item_id, pricing_id: line.pricing_id || null, quantity: line.quantity, unit_price: line.unit_price, discount: line.discount });
const channel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("suite-shared-catalog") : null;
export function catalogChanged() { window.dispatchEvent(new Event("suite:catalog-changed")); channel?.postMessage("changed"); }
channel?.addEventListener("message", () => window.dispatchEvent(new Event("suite:catalog-changed")));
export function useCatalogRefresh(refresh: () => void) {
  useEffect(() => {
    const update = () => { if (document.visibilityState !== "hidden") refresh(); };
    const interval = window.setInterval(update, 45000);
    const synchronized = (event: Event) => { if ((event as CustomEvent<{entity: string}>).detail?.entity === "catalog") update(); };
    window.addEventListener("suite:records-updated", synchronized);
    window.addEventListener("suite:catalog-changed", update); window.addEventListener("focus", update);
    return () => { window.removeEventListener("suite:records-updated", synchronized); clearInterval(interval); window.removeEventListener("suite:catalog-changed", update); window.removeEventListener("focus", update); };
  }, [refresh]);
}
export function useDebounced(value: string) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => { const timer = setTimeout(() => setDebounced(value), 250); return () => clearTimeout(timer); }, [value]);
  return debounced;
}
export const catalogApi = {
  list: (source: CatalogSource, params: Record<string, string | number | undefined> = {}) => api.get<{ items: CatalogItem[]; total: number; pages: number; permissions: Partial<Record<CatalogKind, boolean>> }>("/catalog/items", { params: { source, ...params }, progress: false }),
  get: (source: CatalogSource, kind: CatalogKind, id: number) => api.get<CatalogItem>(`/catalog/items/${kind}/${id}`, { params: { source } }),
  save: (source: CatalogSource, item: Omit<CatalogItem, "id"> & { id?: number }, branchId?: number) => { const { id, ...data } = item; return id ? api.put<CatalogItem>(`/catalog/items/${item.kind}/${id}`, data, { params: { source } }) : api.post<CatalogItem>("/catalog/items", data, { params: { source }, ...(branchId ? { headers: { "X-Suite-Branch": String(branchId) } } : {}) }); },
};
export function catalogError(error: unknown): string { const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail; return typeof detail === "string" ? detail : "Unable to save or load the catalog. Check the fields and your access, then try again."; }
export const money = (value: number, currency: string) => { try { return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(value); } catch { return `${currency} ${value.toFixed(2)}`; } };
