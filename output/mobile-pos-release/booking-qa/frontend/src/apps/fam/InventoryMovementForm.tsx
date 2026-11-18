import { useAuthStore } from "@/store/authStore";
import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { recordScope, useRecordScope } from "@/shared/records/Record360Workspace";
import CompactForm from "@/components/forms/CompactForm";
import { NativeSelect } from "@/components/ui/native-select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { defaultToday } from "@/lib/form-defaults";
import { dealError } from "@/apps/crm/deals/deal-utils";
import { srmApi } from "@/apps/srm/api";
import { syncSrmNow } from "@/apps/srm/realtime";
import { toast } from "@/hooks/use-toast";
import { famApi } from "./api";
import { useFinanceWrite } from "./useFinanceWrite";
import type { FAMRecord } from "./types";

type MovementKind = "transfer" | "adjustment" | "in" | "out" | "purchase" | "delivery" | "opening";
const rows = (data: unknown): FAMRecord[] => Array.isArray(data) ? data : (data as { items?: FAMRecord[] })?.items || [];
const decimal = (value: string) => /^(?:\d+\.?\d*|\.\d+)$/.test(value) && Number.isFinite(Number(value));
export default function InventoryMovementForm({ kind }: { kind: MovementKind }) {
  const scope = useRecordScope(), location = useLocation();
  const source = location.pathname.startsWith("/srm/inventory") ? "srm" : "fam";
  return <MovementForm key={`${scope}:${source}:${kind}`} source={source} kind={kind} scope={scope} />;
}
function MovementForm({ source, kind, scope }: { source: "srm" | "fam"; kind: MovementKind; scope: string }) {
  const qc = useQueryClient(), transfer = kind === "transfer", adjustment = kind === "adjustment", stockDocument = !["transfer", "adjustment", "opening"].includes(kind);
  const movementType = kind === "in" ? "stock_in" : kind === "out" ? "stock_out" : kind === "purchase" ? "purchase_receipt" : "delivery_note";
  const title = ({transfer:"Stock transfer",adjustment:"Stock adjustment",in:"Stock in",out:"Stock out",purchase:"Purchase receipt",delivery:"Delivery note",opening:"Opening stock"})[kind];
  const buttonLabel = kind === "opening" ? "Save opening stock" : stockDocument ? "Post movement" : `Post ${kind}`;
  const owner = useRef(recordScope(useAuthStore.getState().user)), active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const owns = () => active.current && owner.current === recordScope(useAuthStore.getState().user);
  const canWrite = useFinanceWrite(source === "srm" ? ["srm_admin", "srm_manage"] : ["fam_admin", transfer ? "fam_stock_transfer" : adjustment ? "fam_stock_adjust" : "fam_stock_post", "fam_inventory_manage"], "create");
  const initial = () => ({ date: defaultToday(source), product: "", warehouse: "", destination: "", quantity: "1", quantityIn: "0", quantityOut: "0", rate: "0", reason: "", reference: "", notes: "" });
  const [draft, setDraft] = useState(initial), [error, setError] = useState("");
  // Finance creates a draft before posting. Retrying a failed post must reuse it.
  const pending = useRef<{ id: string; payload: FAMRecord }>();
  const [savedDraft, setSavedDraft] = useState(false);
  const products = useQuery({ queryKey: [source, "movement-products", scope], queryFn: () => source === "srm" ? srmApi.inventoryItems() : famApi.inventoryItems(), staleTime: 30000, retry: false });
  const warehouses = useQuery({ queryKey: [source, "movement-warehouses", scope], queryFn: () => source === "srm" ? srmApi.inventoryWarehouses() : famApi.inventoryWarehouses(), staleTime: 30000, retry: false });
  const productRows = products.isError ? [] : rows(products.data).filter(row => row.active !== false && !["inactive", "archived"].includes(String(row.status).toLowerCase()));
  const warehouseRows = warehouses.isError ? [] : rows(warehouses.data).filter(row => row.active !== false);
  const mutation = useMutation({ mutationFn: async () => {
    if (!owns()) throw new Error("The inventory context changed. Reopen the form to continue.");
    const common = { rate: Number(draft.rate), notes: draft.notes || undefined };
    if (source === "srm") {
      const payload = { ...common, product_id: Number(draft.product), movement_date: draft.date, reference_number: draft.reference || undefined };
      if (stockDocument) return srmApi.createInventoryStockMovement({ ...payload, warehouse_id: Number(draft.warehouse), movement_type: movementType, quantity: Number(draft.quantity) });
      if (kind === "opening") return srmApi.createInventoryOpeningStock({ ...payload, warehouse_id: Number(draft.warehouse), quantity: Number(draft.quantity) });
      return transfer ? srmApi.createInventoryStockTransfer({ ...payload, from_warehouse_id: Number(draft.warehouse), to_warehouse_id: Number(draft.destination), quantity: Number(draft.quantity) }) : srmApi.createInventoryStockAdjustment({ ...payload, warehouse_id: Number(draft.warehouse), reason: draft.reason, quantity_in: Number(draft.quantityIn), quantity_out: Number(draft.quantityOut) });
    }
    if (stockDocument) return famApi.postInventoryDocument(({in:"stock-in",out:"stock-out",purchase:"purchase-receipts",delivery:"delivery-notes"} as const)[kind as "in"|"out"|"purchase"|"delivery"], { movement_date: draft.date, movement_type: movementType, reference_number: draft.reference || undefined, narration: draft.notes || undefined, lines: [{ stock_item_id: Number(draft.product), warehouse_id: Number(draft.warehouse), [kind === "out" || kind === "delivery" ? "quantity_out" : "quantity_in"]: Number(draft.quantity), rate: Number(draft.rate), notes: draft.notes || undefined }] });
    if (kind === "opening") return famApi.createInventoryOpeningStock({ stock_item_id: Number(draft.product), warehouse_id: Number(draft.warehouse), opening_date: draft.date, quantity: Number(draft.quantity), rate: Number(draft.rate), notes: draft.notes || undefined });
    if (!pending.current) {
      const line = { ...common, stock_item_id: Number(draft.product) };
      const payload = transfer ? { transfer_date: draft.date, from_warehouse_id: Number(draft.warehouse), to_warehouse_id: Number(draft.destination), notes: draft.notes || undefined, lines: [{ ...line, quantity: Number(draft.quantity) }] } : { adjustment_date: draft.date, warehouse_id: Number(draft.warehouse), reason: draft.reason, notes: draft.notes || undefined, lines: [{ ...line, quantity_in: Number(draft.quantityIn), quantity_out: Number(draft.quantityOut) }] };
      const created = transfer ? await famApi.createInventoryTransfer(payload) : await famApi.createInventoryAdjustment(payload);
      if (!owns()) throw new Error("The draft was saved in the previous context. Reopen it there to continue posting.");
      if (!created.id) throw new Error("The draft response did not identify the saved record.");
      pending.current = { id: String(created.id), payload }; setSavedDraft(true);
    }
    return transfer ? famApi.postInventoryTransfer(pending.current.id) : famApi.postInventoryAdjustment(pending.current.id, pending.current.payload);
  }, onSuccess: () => {
    if (!owns()) return;
    pending.current = undefined; setSavedDraft(false); setDraft(initial()); setError(""); toast({ title: kind === "opening" ? "Opening stock saved" : stockDocument ? "Stock movement posted" : transfer ? "Transfer posted" : "Adjustment posted" });
    if (source === "srm") void syncSrmNow(qc, { type: "inventory_changed", source: `srm-stock-${kind}` });
    else void qc.invalidateQueries({ queryKey: ["fam"] });
  }, onError: failure => { if (owns()) setError(dealError(failure)); } });
  const select = (label: string, key: "product" | "warehouse" | "destination", choices: FAMRecord[], placeholder: string) => <label className="grid gap-1 text-sm">{label}<NativeSelect required searchable aria-label={label} value={draft[key]} onChange={event => setDraft(current => ({ ...current, [key]: event.target.value }))}><option value="">{placeholder}</option>{choices.map(row => <option key={String(row.id)} value={String(row.id)}>{String(key === "product" ? row.item_name || row.name : row.warehouse_name)}{key === "product" && row.sku ? ` · ${row.sku}` : ""}</option>)}</NativeSelect></label>;
  const number = (label: string, key: "quantity" | "quantityIn" | "quantityOut" | "rate") => <label className="grid gap-1 text-sm">{label}<Input required aria-label={label} inputMode="decimal" value={draft[key]} onChange={event => setDraft(current => ({ ...current, [key]: event.target.value }))} /></label>;
  return <Card><CardHeader><CardTitle className="text-base">{title}</CardTitle></CardHeader><CardContent><CompactForm compactTabs={false} className="grid gap-3 md:grid-cols-3" onSubmit={event => {
    event.preventDefault(); setError(""); if (!canWrite || mutation.isPending) return;
    if (pending.current) { mutation.mutate(); return; }
    if (!productRows.some(row => String(row.id) === draft.product) || !warehouseRows.some(row => String(row.id) === draft.warehouse) || transfer && !warehouseRows.some(row => String(row.id) === draft.destination)) { setError("Choose an available item and warehouse."); return; }
    if (transfer && draft.warehouse === draft.destination) { setError("Choose different source and destination warehouses."); return; }
    const amounts = !adjustment ? [draft.quantity, draft.rate] : [draft.quantityIn, draft.quantityOut, draft.rate];
    if (!amounts.every(decimal) || !adjustment && Number(draft.quantity) <= 0 || adjustment && (Number(draft.quantityIn) > 0) === (Number(draft.quantityOut) > 0)) { setError(!adjustment ? "Enter a quantity greater than zero and a nonnegative rate." : "Enter a positive quantity in either stock in or stock out, with a nonnegative rate."); return; }
    mutation.mutate();
  }}><fieldset className="contents" disabled={!canWrite || mutation.isPending || savedDraft}>
    <label className="grid gap-1 text-sm">Movement date<Input required type="date" aria-label="Movement date" value={draft.date} onChange={event => setDraft(current => ({ ...current, date: event.target.value }))} /></label>
    {select("Stock item", "product", productRows, "Choose stock item")}{select(transfer ? "Source warehouse" : "Warehouse", "warehouse", warehouseRows, "Choose warehouse")}{transfer && select("Destination warehouse", "destination", warehouseRows, "Choose destination")}
    {!adjustment ? number("Quantity", "quantity") : <>{number("Stock in", "quantityIn")}{number("Stock out", "quantityOut")}</>}{number("Rate", "rate")}
    {adjustment && <label className="grid gap-1 text-sm">Reason<Input required value={draft.reason} onChange={event => setDraft(current => ({ ...current, reason: event.target.value }))} /></label>}
    {(source === "srm" || stockDocument) && <label className="grid gap-1 text-sm">Reference number<Input value={draft.reference} onChange={event => setDraft(current => ({ ...current, reference: event.target.value }))} /></label>}
    <label className="grid gap-1 text-sm md:col-span-3">Notes<Input value={draft.notes} onChange={event => setDraft(current => ({ ...current, notes: event.target.value }))} /></label>
  </fieldset>
    {products.isError && <p role="alert">Items could not load. <Button type="button" onClick={() => void products.refetch()}>Retry items</Button></p>}{warehouses.isError && <p role="alert">Warehouses could not load. <Button type="button" onClick={() => void warehouses.refetch()}>Retry warehouses</Button></p>}
    {savedDraft && <p role="status" className="md:col-span-3">The draft is saved. Retry posting to finish this same record.</p>}{error && <p role="alert" className="md:col-span-3">{error}</p>}
    <Button data-save-action className="inventory-movement-submit" type="submit" disabled={!canWrite || mutation.isPending || !savedDraft && (products.isPending || products.isError || warehouses.isPending || warehouses.isError)}>{savedDraft ? "Retry posting" : buttonLabel}</Button>
  </CompactForm></CardContent></Card>;
}
