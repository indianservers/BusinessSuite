import InventorySalesProductMapping from "./InventorySalesProductMapping";
import { useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRecordScope } from "@/shared/records/Record360Workspace";
import CompactForm from "@/components/forms/CompactForm";
import { NativeSelect } from "@/components/ui/native-select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/hooks/use-toast";
import { dealError } from "@/apps/crm/deals/deal-utils";
import { srmApi } from "@/apps/srm/api";
import { famApi } from "./api";
import { useFinanceWrite } from "./useFinanceWrite";
import type { FAMRecord } from "./types";

const items = (data: unknown): FAMRecord[] => Array.isArray(data) ? data : (data as { items?: FAMRecord[] })?.items || [];
const ledgerFields = [["inventory_ledger_id", "Inventory ledger"], ["purchase_ledger_id", "Purchase ledger"], ["sales_ledger_id", "Sales ledger"], ["cogs_ledger_id", "Cost of goods sold ledger"], ["adjustment_gain_ledger_id", "Adjustment gain ledger"], ["adjustment_loss_ledger_id", "Adjustment loss ledger"], ["grni_ledger_id", "Goods received not invoiced ledger"]];
const validId = (value?: string) => !!value && /^\d+$/.test(value) && Number.isSafeInteger(Number(value)) && Number(value) > 0;
export default function InventoryLedgerMappingPage() {
  const { id } = useParams(), scope = useRecordScope(), location = useLocation();
  if (!validId(id)) return <p role="alert">Choose a stock item before editing its ledger mapping.</p>;
  return location.pathname.startsWith("/srm/") ? <SalesFinanceSelection key={`${scope}:${id}`} id={id!} scope={scope}/> : <MappingEditor key={`${scope}:${id}`} id={id!} scope={scope}/>;
}
function SalesFinanceSelection({ id, scope }: { id: string; scope: string }) {
  const [selected, setSelected] = useState("");
  const product = useQuery({ queryKey: ["srm", "mapping-source-product", scope, id], queryFn: () => srmApi.inventoryItem(id), retry: false });
  const financeItems = useQuery({ queryKey: ["fam", "mapping-item-options", scope], queryFn: () => famApi.inventoryItems(), enabled: product.isSuccess, retry: false });
  if (product.isPending) return <p role="status">Loading Sales product…</p>;
  if (product.isError) return <div role="alert">{dealError(product.error)} <Button onClick={() => void product.refetch()}>Retry Sales product</Button></div>;
  return <div className="space-y-4"><Card><CardHeader><CardTitle>Finance mapping for {String(product.data?.item_name || "Sales product")}</CardTitle></CardHeader><CardContent className="space-y-3"><p>Choose the Finance stock item whose accounts you want to edit. This does not change the Sales product.</p><label className="grid gap-1 text-sm">Finance stock item<NativeSelect searchable aria-label="Finance stock item" value={selected} onChange={event => setSelected(event.target.value)}><option value="">Choose Finance stock item</option>{(financeItems.isError ? [] : items(financeItems.data)).filter(row => row.active !== false).map(row => <option key={String(row.id)} value={String(row.id)}>{String(row.item_name)} · {String(row.sku)}</option>)}</NativeSelect></label>{financeItems.isError && <p role="alert">Finance items could not load. Check Finance access or retry. <Button onClick={() => void financeItems.refetch()}>Retry Finance items</Button></p>}</CardContent></Card>{selected && <MappingEditor key={`${scope}:${selected}`} id={selected} scope={scope}/>}</div>;
}
function MappingEditor({ id, scope }: { id: string; scope: string }) {
  const qc = useQueryClient(), canEdit = useFinanceWrite(["fam_admin", "fam_inventory_accounting_manage", "fam_inventory_post_accounting", "fam_inventory_manage"], "edit");
  const [draft, setDraft] = useState<FAMRecord>({}), [error, setError] = useState("");
  const mapping = useQuery({ queryKey: ["fam", "inventoryLedgerMapping", scope, id], queryFn: () => famApi.inventoryLedgerMapping(id), retry: false });
  const ledgers = useQuery({ queryKey: ["fam", "mapping-ledgers", scope], queryFn: famApi.ledgers, enabled: mapping.isSuccess, retry: false, staleTime: 30000 });
  const tax = useQuery({ queryKey: ["fam", "mapping-tax", scope], queryFn: famApi.gstRates, enabled: mapping.isSuccess, retry: false, staleTime: 30000 });
  const costs = useQuery({ queryKey: ["fam", "mapping-costs", scope], queryFn: famApi.costCenters, enabled: mapping.isSuccess, retry: false, staleTime: 30000 });
  const branches = useQuery({ queryKey: ["fam", "mapping-branches", scope], queryFn: famApi.branches, enabled: mapping.isSuccess, retry: false, staleTime: 30000 });
  const warehouses = useQuery({ queryKey: ["fam", "mapping-warehouses", scope], queryFn: famApi.inventoryWarehouses, enabled: mapping.isSuccess, retry: false, staleTime: 30000 });
  const data: FAMRecord = { ...mapping.data, ...draft };
  const references = [...ledgerFields.map(([key, label]) => ({ key, label, query: ledgers, name: "ledger_name", code: "ledger_code" })), { key: "gst_rate_id", label: "GST rate", query: tax, name: "rate_name", code: "tax_type" }, { key: "cost_center_id", label: "Cost center", query: costs, name: "name", code: "code" }, { key: "default_warehouse_id", label: "Default warehouse", query: warehouses, name: "warehouse_name", code: "warehouse_code" }];
  const mutation = useMutation({ mutationFn: (payload: FAMRecord) => famApi.updateInventoryLedgerMapping(id, payload), onSuccess: response => { toast({ title: "Inventory ledger mapping saved" }); setDraft({}); qc.setQueryData(["fam", "inventoryLedgerMapping", scope, id], response); void qc.invalidateQueries({ queryKey: ["fam"] }); }, onError: failure => setError(dealError(failure)) });
  if (mapping.isPending) return <p role="status">Loading ledger mapping…</p>;
  if (mapping.isError) return <div role="alert">{dealError(mapping.error)} <Button onClick={() => void mapping.refetch()}>Retry mapping</Button></div>;
  const unresolved = references.some(ref => data[ref.key] != null && (ref.query.isPending || ref.query.isError || !items(ref.query.data).some(row => row.active !== false && String(row.id) === String(data[ref.key]))));
  return <><Card><CardHeader><CardTitle className="text-base">{String(data.item_name || data.sku || "Stock item")} ledger mapping</CardTitle></CardHeader><CardContent><CompactForm compactTabs={false} className="grid gap-3 md:grid-cols-3" onSubmit={event => {
    event.preventDefault(); setError(""); if (!canEdit || mutation.isPending) return;
    if (unresolved) { setError("Choose available references or clear unavailable selections before saving."); return; }
    if (data.valuation_method !== "weighted_average") { setError("Choose weighted average valuation, the supported inventory valuation method."); return; }
    const payload: FAMRecord = { hsn_code: String(data.hsn_code || "").trim() || null, valuation_method: "weighted_average" };
    references.forEach(ref => { payload[ref.key] = data[ref.key] == null || data[ref.key] === "" ? null : Number(data[ref.key]); });
    mutation.mutate(payload);
  }}><fieldset className="contents" disabled={!canEdit || mutation.isPending}>
    {references.map(ref => { const options = (ref.query.isError ? [] : items(ref.query.data)).filter(row => row.active !== false); const value = String(data[ref.key] ?? ""); return <div key={ref.key}><label className="grid gap-1 text-sm">{ref.label}<NativeSelect searchable aria-label={ref.label} value={value} onChange={event => setDraft(current => ({ ...current, [ref.key]: event.target.value ? Number(event.target.value) : null }))}><option value="">Not assigned</option>{options.map(row => <option key={String(row.id)} value={String(row.id)}>{String(row[ref.name])}{row[ref.code] ? ` · ${row[ref.code]}` : ""}</option>)}{value && !options.some(row => String(row.id) === value) && <option value={value}>Unavailable selection</option>}</NativeSelect></label>{ref.query.isError && <p role="alert">{ref.label} choices could not load. <Button type="button" onClick={() => void ref.query.refetch()}>Retry {ref.label.toLowerCase()}</Button></p>}</div>; })}
    <label className="grid gap-1 text-sm">HSN code<Input maxLength={30} value={String(data.hsn_code || "")} onChange={event => setDraft(current => ({ ...current, hsn_code: event.target.value }))}/></label>
    <label className="grid gap-1 text-sm">Valuation method<NativeSelect required aria-label="Valuation method" value={String(data.valuation_method || "")} onChange={event => setDraft(current => ({ ...current, valuation_method: event.target.value }))}><option value="weighted_average">Weighted average</option>{data.valuation_method !== "weighted_average" && <option value={String(data.valuation_method || "")}>Unsupported saved method — choose weighted average</option>}</NativeSelect></label>
  </fieldset><p className="text-sm md:col-span-3">Branch: {data.branch_id == null ? "Not assigned" : String(items(branches.data).find(row => String(row.id) === String(data.branch_id))?.branch_name || "Unavailable branch")}. Use branch transfer to change item ownership.</p>{branches.isError && <Button type="button" onClick={() => void branches.refetch()}>Retry branch name</Button>}{error && <p role="alert" className="md:col-span-3">{error}</p>}<Button type="submit" disabled={!canEdit || mutation.isPending || unresolved}>Save mapping</Button></CompactForm></CardContent></Card><InventorySalesProductMapping itemId={id}/></>;
}
