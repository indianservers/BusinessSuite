import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { srmApi } from "@/apps/srm/api";
import { useAuthStore } from "@/store/authStore";
import { recordScope, useRecordScope } from "@/shared/records/Record360Workspace";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import CompactForm from "@/components/forms/CompactForm";
import { NativeSelect } from "@/components/ui/native-select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RichTextField } from "@/components/rich-text/LazyRichText";
import { dealError } from "@/apps/crm/deals/deal-utils";
import { toast } from "@/hooks/use-toast";
import { useFinanceWrite } from "./useFinanceWrite";
import type { FAMRecord } from "./types";

const rows = (data: unknown): FAMRecord[] => Array.isArray(data) ? data : (data as { items?: FAMRecord[] })?.items || [];
const amount = (value: string) => /^(?:\d+\.?\d*|\.\d+)$/.test(value) && Number.isFinite(Number(value));
export default function InventoryBomForm() {
  const scope = useRecordScope();
  return <BomForm key={scope} scope={scope} />;
}
function BomForm({ scope }: { scope: string }) {
  const queryClient = useQueryClient();
  const canWrite = useFinanceWrite(["srm_manage", "srm_admin"], "create");
  const owner = useRef(recordScope(useAuthStore.getState().user)), active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const owns = () => active.current && owner.current === recordScope(useAuthStore.getState().user);
  const [draft, setDraft] = useState({ code: "", name: "", finished: "", output: "1", component: "", warehouse: "", quantity: "1", cost: "0", notes: "" });
  const [submitted, setSubmitted] = useState(false), [error, setError] = useState("");
  const products = useQuery({ queryKey: ["srm", "bom-products", scope], queryFn: () => srmApi.inventoryItems(), retry: false });
  const warehouses = useQuery({ queryKey: ["srm", "bom-warehouses", scope], queryFn: srmApi.inventoryWarehouses, retry: false });
  const productRows = rows(products.data).filter(row => row.active !== false), warehouseRows = rows(warehouses.data).filter(row => row.active !== false);
  const errors: Record<string, string> = {};
  if (!draft.name.trim()) errors.name = "Enter a BOM name.";
  for (const field of ["finished", "component"] as const) if (!productRows.some(row => String(row.id) === draft[field])) errors[field] = "Choose an available product.";
  if (draft.finished && draft.finished === draft.component) errors.component = "Finished product cannot also be a component.";
  if (draft.warehouse && !warehouseRows.some(row => String(row.id) === draft.warehouse)) errors.warehouse = "Choose an available warehouse.";
  for (const field of ["output", "quantity"] as const) if (!amount(draft[field]) || Number(draft[field]) <= 0) errors[field] = "Enter a quantity greater than zero.";
  if (!amount(draft.cost)) errors.cost = "Enter a nonnegative unit cost.";
  const save = useMutation({
    mutationFn: () => {
      if (!owns()) throw new Error("The inventory context changed. Reopen this form.");
      return srmApi.createBom({ bom_number: draft.code.trim() || undefined, bom_name: draft.name.trim(), finished_product_id: Number(draft.finished), output_quantity: Number(draft.output), status: "active", notes: draft.notes || undefined, components: [{ component_product_id: Number(draft.component), warehouse_id: draft.warehouse ? Number(draft.warehouse) : undefined, quantity: Number(draft.quantity), unit_cost: Number(draft.cost) }] });
    },
    onSuccess: () => { if (owns()) { toast({ title: "BOM saved" }); void queryClient.invalidateQueries({ queryKey: ["srm"] }); } },
    onError: reason => { if (owns()) setError(dealError(reason)); },
  });
  const change = (key: keyof typeof draft, value: string) => setDraft(current => ({ ...current, [key]: value }));
  const message = (key: string) => submitted && errors[key] && <span role="alert" className="text-destructive">{errors[key]}</span>;
  const field = (key: "code" | "name" | "output" | "quantity" | "cost", label: string) => <label className="grid gap-1 text-sm">{label}<Input aria-label={label} aria-invalid={submitted && !!errors[key]} maxLength={key === "code" ? 80 : key === "name" ? 180 : undefined} inputMode={["output", "quantity", "cost"].includes(key) ? "decimal" : undefined} value={draft[key]} onChange={event => change(key, event.target.value)} />{message(key)}</label>;
  const product = (key: "finished" | "component", label: string) => <label className="grid gap-1 text-sm">{label}<NativeSelect aria-label={label} aria-invalid={submitted && !!errors[key]} value={draft[key]} onChange={event => change(key, event.target.value)}><option value="">Choose product</option>{productRows.map(row => <option key={String(row.id)} value={String(row.id)}>{String(row.item_name)}{row.sku ? ` · ${row.sku}` : ""}</option>)}</NativeSelect>{message(key)}</label>;
  return <SmartCreateSection title="Create BOM" size="standard"><Card><CardHeader><CardTitle className="text-base">Create BOM</CardTitle></CardHeader><CardContent>
    <CompactForm compactTabs={false} aria-label="Create BOM" noValidate className="grid gap-3" onSubmit={event => { event.preventDefault(); setSubmitted(true); setError(""); if (canWrite && !save.isPending && !products.isError && !warehouses.isError && !Object.keys(errors).length) save.mutate(); }}>
      <fieldset className="grid gap-3" disabled={!canWrite || save.isPending}>
        {field("code", "BOM number (optional)")}{field("name", "BOM name")}{product("finished", "Finished product")}{field("output", "Output quantity")}{product("component", "Component product")}
        <label className="grid gap-1 text-sm">Component warehouse (optional)<NativeSelect aria-label="Component warehouse" value={draft.warehouse} onChange={event => change("warehouse", event.target.value)}><option value="">Use component product default</option>{warehouseRows.map(row => <option key={String(row.id)} value={String(row.id)}>{String(row.warehouse_name)}</option>)}</NativeSelect>{message("warehouse")}</label>
        {field("quantity", "Component quantity")}{field("cost", "Component unit cost")}
        <p className="text-sm text-muted-foreground">Zero unit cost uses the component product’s current cost.</p>
        <label className="grid gap-1 text-sm">Notes<RichTextField value={draft.notes} onChange={event => change("notes", event.target.value)} /></label>
      </fieldset>
      {products.isError && <p role="alert">Products could not load. <Button type="button" onClick={() => void products.refetch()}>Retry products</Button></p>}
      {warehouses.isError && <p role="alert">Warehouses could not load. <Button type="button" onClick={() => void warehouses.refetch()}>Retry warehouses</Button></p>}
      {error && <p role="alert" className="text-destructive">{error}</p>}
      <Button data-save-action type="submit" disabled={!canWrite || save.isPending || products.isPending || warehouses.isPending || products.isError || warehouses.isError}>Save BOM</Button>
    </CompactForm>
  </CardContent></Card></SmartCreateSection>;
}
