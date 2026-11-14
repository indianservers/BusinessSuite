import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRecordScope } from "@/shared/records/Record360Workspace";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import CompactForm from "@/components/forms/CompactForm";
import { NativeSelect } from "@/components/ui/native-select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/hooks/use-toast";
import { dealError } from "@/apps/crm/deals/deal-utils";
import { srmApi } from "@/apps/srm/api";
import { famApi } from "./api";
import { useFinanceWrite } from "./useFinanceWrite";
import type { FAMRecord } from "./types";

const empty = { sku: "", item_name: "", hsn_code: "", stock_group_id: "", unit_id: "", default_warehouse_id: "", barcode: "", category_name: "", unit_code: "PCS", gst_rate: "0", purchase_rate: "0", sales_rate: "0", mrp: "0", reorder_level: "0", min_stock: "0" };
const numeric = ["purchase_rate", "sales_rate", "reorder_level", "min_stock", "gst_rate", "mrp"] as const;
const items = (data: unknown): FAMRecord[] => Array.isArray(data) ? data : (data as { items?: FAMRecord[] })?.items || [];
export default function InventoryItemCreateForm({ source }: { source: "fam" | "srm" }) {
  const scope = useRecordScope();
  return <ItemForm key={`${scope}:${source}`} source={source} scope={scope} />;
}
function ItemForm({ source, scope }: { source: "fam" | "srm"; scope: string }) {
  const qc = useQueryClient(), finance = source === "fam";
  const canWrite = useFinanceWrite(finance ? ["fam_admin", "fam_inventory_manage"] : ["srm_admin", "srm_manage"], "create");
  const [draft, setDraft] = useState(empty), [error, setError] = useState("");
  const groups = useQuery({ queryKey: ["fam", "item-create-groups", scope], queryFn: famApi.inventoryStockGroups, enabled: finance, staleTime: 30000, retry: false });
  const units = useQuery({ queryKey: ["fam", "item-create-units", scope], queryFn: famApi.inventoryUnits, enabled: finance, staleTime: 30000, retry: false });
  const warehouses = useQuery({ queryKey: ["fam", "item-create-warehouses", scope], queryFn: famApi.inventoryWarehouses, enabled: finance, staleTime: 30000, retry: false });
  const references = [
    { key: "stock_group_id", label: "Stock group", query: groups, name: "group_name" },
    { key: "unit_id", label: "Unit", query: units, name: "unit_name" },
    { key: "default_warehouse_id", label: "Default warehouse", query: warehouses, name: "warehouse_name" },
  ] as const;
  const mutation = useMutation({ mutationFn: (payload: FAMRecord) => finance ? famApi.createInventoryItem(payload) : srmApi.createInventoryItem(payload), onSuccess: () => { toast({ title: finance ? "Stock item created" : "Product created" }); setDraft(empty); void qc.invalidateQueries({ queryKey: [source] }); }, onError: failure => setError(dealError(failure)) });
  const text = (label: string, key: keyof typeof draft, required = false, maxLength = 180) => <label className="grid gap-1 text-sm">{label}<Input required={required} maxLength={maxLength} aria-label={label} value={draft[key]} onChange={event => setDraft(current => ({ ...current, [key]: event.target.value }))} /></label>;
  const numberFields = finance ? numeric.filter(key => !["gst_rate", "mrp"].includes(key)) : numeric;
  return <SmartCreateSection title={finance ? "Create item" : "Create SRM product"}><Card><CardHeader><CardTitle className="text-base">{finance ? "Create item" : "Create SRM product"}</CardTitle></CardHeader><CardContent><CompactForm compactTabs={false} className="grid gap-3" onSubmit={event => {
    event.preventDefault(); setError(""); if (!canWrite || mutation.isPending) return;
    if (!draft.sku.trim() || !draft.item_name.trim()) { setError("SKU and item name are required."); return; }
    if (numberFields.some(key => !/^(?:\d+\.?\d*|\.\d+)$/.test(draft[key]) || !Number.isFinite(Number(draft[key]))) || !finance && Number(draft.gst_rate) > 100) { setError(finance ? "Enter nonnegative prices and stock levels." : "Enter nonnegative prices and stock levels, and a GST rate from 0 to 100."); return; }
    if (finance && references.some(ref => draft[ref.key] && (ref.query.isError || !items(ref.query.data).some(row => row.active !== false && String(row.id) === draft[ref.key])))) { setError("Choose available stock group, unit and warehouse references, or leave them unassigned."); return; }
    const payload: FAMRecord = { sku: draft.sku.trim(), item_name: draft.item_name.trim(), hsn_code: draft.hsn_code.trim() || undefined, track_inventory: true, ...Object.fromEntries(numberFields.map(key => [key, Number(draft[key])])) };
    if (finance) references.forEach(ref => { if (draft[ref.key]) payload[ref.key] = Number(draft[ref.key]); });
    else Object.assign(payload, { barcode: draft.barcode.trim() || undefined, category_name: draft.category_name.trim() || undefined, unit_code: draft.unit_code.trim() || "PCS" });
    mutation.mutate(payload);
  }}><fieldset className="grid gap-3" disabled={!canWrite || mutation.isPending}>
    {text("SKU", "sku", true, 80)}{text("Item name", "item_name", true, 220)}{text("HSN code", "hsn_code")}
    {finance ? references.map(ref => <div key={ref.key}><label className="grid gap-1 text-sm">{ref.label}<NativeSelect searchable aria-label={ref.label} value={draft[ref.key]} onChange={event => setDraft(current => ({ ...current, [ref.key]: event.target.value }))}><option value="">Not assigned</option>{(ref.query.isError ? [] : items(ref.query.data)).filter(row => row.active !== false).map(row => <option key={String(row.id)} value={String(row.id)}>{String(row[ref.name])}</option>)}</NativeSelect></label>{ref.query.isError && <p role="alert">{ref.label} choices could not load. <Button type="button" onClick={() => void ref.query.refetch()}>Retry {ref.label.toLowerCase()}</Button></p>}</div>) : <>{text("Barcode", "barcode")}{text("Category", "category_name")}{text("Unit code", "unit_code")}</>}
    {numberFields.map(key => { const label = ({ purchase_rate: "Purchase rate", sales_rate: "Sales rate", reorder_level: "Reorder level", min_stock: "Minimum stock", gst_rate: "GST rate", mrp: "MRP" })[key]; return <label key={key} className="grid gap-1 text-sm">{label}<Input required inputMode="decimal" aria-label={label} value={draft[key]} onChange={event => setDraft(current => ({ ...current, [key]: event.target.value }))} /></label>; })}
    {error && <p role="alert">{error}</p>}<Button type="submit">{finance ? "Save item" : "Save product"}</Button>
  </fieldset></CompactForm></CardContent></Card></SmartCreateSection>;
}
