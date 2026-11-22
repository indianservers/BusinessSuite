import { selectedBranch } from "@/lib/branch-context";
import { syncScope } from "@/shared/record-sync/store";
import { offlineChangeEvent, offlineChanges, offlineRead, saveOffline } from "@/lib/offline-work";
import { defaultText } from "@/lib/form-defaults";
import type { BranchAvailabilityValue } from "@/shared/BranchAvailability";
import type { Schedule } from "@/shared/follow-ups/ScheduleFields";
import { useEffect, useState } from "react";
import { api } from "@/services/api";

export type CatalogSource = "pms" | "crm" | "srm";
export type CatalogKind = "product" | "service" | "membership" | "subscription" | "bundle";
export const offeringKinds: CatalogKind[] = ["product", "service", "membership", "subscription", "bundle"];
export const offeringLabel = (kind: CatalogKind) => ({product:"Products",service:"Services",membership:"Memberships",subscription:"Subscriptions",bundle:"Bundles"})[kind];
export type PlanConfiguration = {duration:{unit:"day"|"week"|"month"|"year"|"custom"|"lifetime";count:number;start?:string|null;end?:string|null}; activation:"purchase"|"first_use"|"selected_date"|"approval"; tier?:string; beneficiary_type?:"person"|"organization"|"family"|"group";beneficiary_limit?:number; benefits:BenefitDefinition[]; eligibility?:EligibilityConfiguration; renewal?:{mode:"manual"|"automatic";reminder_days:number[]};billing?:{mode:"prepaid"|"postpaid";recurring:boolean;automation:boolean;interval_unit:"day"|"week"|"month"|"year";interval_count:number;timezone:string};allow_pause?:boolean;allow_transfer?:boolean};
export type EligibilityConfiguration = {offering_ids?:number[];locations?:string[];customer_groups?:string[];weekdays?:number[];blackout_dates?:string[]};
export type BenefitDefinition = {key:string;type:"access"|"discount_percent"|"discount_fixed"|"special_price"|"credits"|"sessions"|"seats"|"priority_booking"|"included_service"|"custom";label:string;allowance:number|null;value:number;eligibility?:EligibilityConfiguration;stacking?:"exclusive"|"best"|"stack";consumption_event?:"booking"|"check_in"|"attendance"|"completion"|"purchase"};
export type BundleConfiguration = {type:"fixed"|"configurable"|"quantity"|"prepaid"|"mix_and_match";pricing:"package"|"components";components:{offering_id:number;quantity:number;optional:boolean;allocated_price?:number|null;fulfillment?:"purchase"|"delivery"|"completion"}[]};
export type CatalogPrice = { id: string; name: string; amount: number; currency: string; interval: "once" | "day" | "week" | "month" | "year" };
export type CatalogStaffChange = { provider_resource_id: number; employee_id: number; active: boolean; expected_revision?: number };
export type CatalogFeatures = { selected_context: boolean; workspaces: boolean; follow_ups: boolean; image_upload: boolean; imports: boolean; exports: boolean; branch_reuse: boolean; archive: boolean; duplicate: boolean; scheduling_configure: boolean; pharma_lot_tracking?: boolean };
export type CatalogItem = {
  plan?:PlanConfiguration;bundle?:BundleConfiguration;
  features?: CatalogFeatures; can_edit?: boolean; service_scheduling?: {mode:"none"|"optional"|"required";duration:number;employee_categories:string[];expected_revision?:number;staff_changes?:CatalogStaffChange[]};
  branch_availability?: BranchAvailabilityValue | null; follow_up?: Schedule; id: number; kind: CatalogKind; name: string; code: string; description: string; category: string; category_ids?: string[] | null; categories?: string[]; tags?: string[]; price: number; currency: string; tax: number; unit: string; barcode?: string; hsn_code?: string; cost?: number; mrp?: number; reorder_level?: number; track_inventory?: boolean; pharma_lot_tracking?: boolean; pharma_warehouse_id?: number | null; status: "Active" | "Archived"; workspace_id: number | null; images: string[]; custom_fields: Record<string, string | number | boolean | null>; pricing_options: CatalogPrice[]; version: number; offline_pending?: boolean };
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
    const local = (event: Event) => { if (String((event as CustomEvent).detail).startsWith("catalog:")) update(); };
    window.addEventListener(offlineChangeEvent, local);
    window.addEventListener("suite:records-updated", synchronized);
    window.addEventListener("suite:catalog-changed", update); window.addEventListener("focus", update); window.addEventListener("online", update);
    return () => { window.removeEventListener(offlineChangeEvent, local); window.removeEventListener("suite:records-updated", synchronized); clearInterval(interval); window.removeEventListener("suite:catalog-changed", update); window.removeEventListener("focus", update); window.removeEventListener("online", update); };
  }, [refresh]);
}
export function useDebounced(value: string) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => { const timer = setTimeout(() => setDebounced(value), 250); return () => clearTimeout(timer); }, [value]);
  return debounced;
}
type CatalogQuery = Record<string, string | number | boolean | undefined>;
type CatalogList = {items: CatalogItem[]; total: number; pages: number; permissions: Partial<Record<CatalogKind, boolean>>; features?: CatalogFeatures; facets?: {categories:string[];tags:string[]} };
const family = (source: CatalogSource) => "catalog:" + source;
const requestList = (source: CatalogSource, params: CatalogQuery) =>
  api.get<CatalogList>("/catalog/items", {params: {source, ...params}, timeout: 4000, progress: false, recordCache: false}).then(response => response.data);

const warming = new Map<string, number>();
async function warmCatalog(source: CatalogSource) {
  // Cache a complete small catalog for search and filters the user has not visited yet.
  const key = family(source) + ":index";
  const identity = syncScope() + key;
  if (Date.now() - (warming.get(identity) || 0) < 60000 || !navigator.onLine) return;
  warming.set(identity, Date.now());
  void offlineRead("catalog-branch-options", () => api.get("/branches/context", {progress: false, recordCache: false, timeout: 4000}).then(response => response.data)).catch(() => undefined);
  try {
    await offlineRead(key, async () => {
      const first = await requestList(source, {status: "all", per_page: 100, include_facets: true});
      if (first.pages > 20) throw new Error("Catalog exceeds offline search capacity.");
      const items = [...first.items];
      for (let page = 2; page <= first.pages; page++) {
        const next = await requestList(source, {status: "all", per_page: 100, page});
        items.push(...next.items);
      }
      return {...first, items};
    });
  } catch { /* Exact visited pages remain available. */ }

}

function matches(item: CatalogItem, params: CatalogQuery) {
  return (!params.kind || item.kind === params.kind) &&
    (params.status === "all" || item.status === (params.status || "Active")) &&
    (!params.category || item.category === params.category || item.categories?.includes(String(params.category))) &&
    (!params.tag || item.tags?.includes(String(params.tag))) &&
    (!params.workspace_id || item.workspace_id === Number(params.workspace_id)) &&
    (!params.item_keys || String(params.item_keys).split(",").includes(item.kind + ":" + item.id)) &&
    (!params.search || [item.name, item.code, item.barcode, item.description].join(" ").toLowerCase().includes(String(params.search).trim().toLowerCase()));
}

export const catalogApi = {
  list: async (source: CatalogSource, params: CatalogQuery = {}) => {
    const key = family(source) + JSON.stringify(Object.entries(params).filter(([,value]) => value !== undefined).sort());
    const indexed = !navigator.onLine && !params.price_book_id && !params.key_order;
    let data: CatalogList;
    let localIndex = false;
    if (indexed) {
      try {
        data = await offlineRead<CatalogList>(family(source) + ":index", () => requestList(source, params));
        localIndex = true;
      } catch { data = await offlineRead(key, () => requestList(source, params), family(source)); }
    } else {
      data = await offlineRead(key, () => requestList(source, params), family(source));
      if (params.include_facets && navigator.onLine) void warmCatalog(source);
    }
    const entries = (await offlineChanges(family(source)).catch(() => [])).filter(entry => !entry.confirmed || Date.now() - entry.created < 300000);
    const byId = new Map(entries.map(entry => [String(entry.row.kind) + ":" + String(entry.row.id), entry.row as unknown as CatalogItem]));
    let items = data.items.map(item => {
      const saved = byId.get(item.kind + ":" + item.id);
      return saved && (saved.offline_pending || saved.version > item.version) ? saved : item;
    });
    const additions = (localIndex || Number(params.page || 1) === 1) && !params.price_book_id
      ? entries.filter(entry => entry.method === "post").map(entry => entry.row as unknown as CatalogItem)
        .filter(item => matches(item, params) && !items.some(row => row.code === item.code && row.kind === item.kind))
      : [];
    if (localIndex) {
      items = [...additions, ...items].filter(item => matches(item, params));
      const sort = params.sort === "price" ? "price" : params.sort === "category" ? "category" : params.sort === "code" ? "code" : "name";
      items.sort((a,b) => (params.direction === "desc" ? -1 : 1) *
        (sort === "price" ? a.price - b.price : String(a[sort]).localeCompare(String(b[sort]))));
      const limit = Number(params.per_page || 24);
      const offset = (Number(params.page || 1) - 1) * limit;
      return {data: {...data, items: items.slice(offset, offset + limit), total: items.length, pages: Math.max(1, Math.ceil(items.length / limit))}};
    }
    return {data: {...data, items: [...additions, ...items], total: data.total + additions.length}};
  },
  get: async (source: CatalogSource, kind: CatalogKind, id: number) => {
    const entries = await offlineChanges(family(source)).catch(() => []);
    const pending = [...entries].reverse().find(entry => !entry.confirmed && entry.row.kind === kind && entry.row.id === id);
    if (pending) return {data: pending.row as unknown as CatalogItem};
    const url = `/catalog/items/${kind}/${id}`;
    const fetchItem = () => api.get<CatalogItem>(url, {params: {source}, timeout: 4000, recordCache: false}).then(response => response.data);
    try { return {data: await offlineRead(family(source) + url, fetchItem)}; }
    catch (error) {
      if (navigator.onLine) throw error;
      const index = await offlineRead<CatalogList>(family(source) + ":index", () => requestList(source, {status: "all"}));
      const item = index.items.find(item => item.kind === kind && item.id === id);
      if (!item) throw error;
      return {data: item};
    }
  },
  save: async (source: CatalogSource, item: Omit<CatalogItem, "id"> & {id?: number}, branchId?: number, direct = false) => {
    const {id, features, can_edit, ...body} = item;
    delete (body as Record<string, unknown>).offline_pending;
    const url = id ? `/catalog/items/${item.kind}/${id}` : "/catalog/items";
    if (direct || (branchId && String(branchId) !== selectedBranch()) || item.service_scheduling?.staff_changes?.length || !["product", "service", "membership"].includes(item.kind)) {
      return id ? api.put<CatalogItem>(url, body, {params: {source}}) : api.post<CatalogItem>(url, body, {params: {source}, ...(branchId ? {headers: {"X-Suite-Branch": String(branchId)}} : {})});
    }
    if (id && !Number.isSafeInteger(item.version)) throw new Error("Reload this item before saving changes.");
    if (id && id < 0) throw new Error("Wait for this item to sync before editing it.");
    const data = await saveOffline<CatalogItem>({family: family(source), target: item.kind + ":" + (id || item.code.trim().toLowerCase()),
      url, method: id ? "put" : "post", body, params: {source}, row: id ? {...body, id, features, can_edit} : {...body, features, can_edit}});
    return {data};
  },
};
export function catalogError(error: unknown): string { const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail; return typeof detail === "string" ? detail : error instanceof Error ? error.message : "Unable to save or load the catalog. Check the fields and your access, then try again."; }
export const money = (value: number, currency: string) => { try { return new Intl.NumberFormat(defaultText("number_format"), { style: "currency", currency }).format(value); } catch { return `${currency} ${value.toFixed(2)}`; } };
