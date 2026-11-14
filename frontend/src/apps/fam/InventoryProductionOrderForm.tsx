import { useEffect, useRef, useState } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { srmApi } from "@/apps/srm/api";
import { useAuthStore } from "@/store/authStore";
import { recordScope, useRecordScope } from "@/shared/records/Record360Workspace";
import { useDebounced } from "@/shared/master-data/CompanySelect";
import SmartRecordPicker from "@/shared/records/SmartRecordPicker";
import CompactForm from "@/components/forms/CompactForm";
import { NativeSelect } from "@/components/ui/native-select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { dealError } from "@/apps/crm/deals/deal-utils";
import { toast } from "@/hooks/use-toast";
import { useFinanceWrite } from "./useFinanceWrite";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import { defaultToday } from "@/lib/form-defaults";
import { RichTextField } from "@/components/rich-text/LazyRichText";
import type { FAMRecord } from "./types";

export default function InventoryProductionOrderForm() {
  const scope = useRecordScope();
  return <OrderForm key={scope} scope={scope} />;
}

function OrderForm({ scope }: { scope: string }) {
  const queryClient = useQueryClient();
  const canWrite = useFinanceWrite(["srm_manage", "srm_admin"], "create");
  const owner = useRef(recordScope(useAuthStore.getState().user));
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const owns = () => active.current && owner.current === recordScope(useAuthStore.getState().user);
  const [selected, setSelected] = useState<FAMRecord>();
  const [search, setSearch] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [date, setDate] = useState(() => defaultToday("srm"));
  const [notes, setNotes] = useState("");
  const [warehouse, setWarehouse] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const term = useDebounced(search);
  const orders = useInfiniteQuery({
    queryKey: ["srm", "production-bom-options", scope, term], initialPageParam: 1, retry: false,
    queryFn: ({ pageParam, signal }) => api.get<{ items: FAMRecord[]; has_more: boolean }>("/srm/inventory/manufacturing/bom", { signal, params: { page: pageParam, per_page: 30, search: term } }).then(r => r.data),
    getNextPageParam: (last, _pages, page) => last.has_more ? page + 1 : undefined,
  });
  const warehouses = useQuery({ queryKey: ["srm", "production-order-warehouses", scope], queryFn: srmApi.inventoryWarehouses, retry: false });
  const warehouseData = warehouses.data as { items?: FAMRecord[] } | FAMRecord[] | undefined;
  const warehouseRows = (Array.isArray(warehouseData) ? warehouseData : warehouseData?.items || []).filter(row => row.active !== false);
  const option = (row: FAMRecord) => ({
    id: String(row.id), label: String(row.bom_name), record: row,
    description: `${String(row.bom_number)} · ${String((row.finished_product as FAMRecord | undefined)?.item_name || "Product")} · Output ${String(row.output_quantity)}`,
  });
  const errors: Record<string, string> = {};
  if (!selected) errors.order = "Choose a BOM.";
  if (!/^(?:\d+\.?\d*|\.\d+)$/.test(quantity) || !Number.isFinite(Number(quantity)) || Number(quantity) <= 0) errors.quantity = "Enter a planned quantity greater than zero.";
  if (warehouse && !warehouseRows.some(row => String(row.id) === warehouse)) errors.warehouse = "Choose an available warehouse.";
  const post = useMutation({
    mutationFn: () => {
      if (!owns() || !selected) throw new Error("The inventory context changed. Reopen this form.");
      return srmApi.createProductionOrder({ bom_id: selected.id, planned_quantity: Number(quantity), warehouse_id: warehouse ? Number(warehouse) : undefined, order_date: date || undefined, notes: notes || undefined });
    },
    onSuccess: () => {
      if (!owns()) return;
      toast({ title: "Production order created" });
      setSelected(undefined); setQuantity("1"); setWarehouse(""); setSearch(""); setNotes(""); setSubmitted(false); setError("");
      void queryClient.invalidateQueries({ queryKey: ["srm"] });
    },
    onError: reason => { if (owns()) setError(dealError(reason)); },
  });
  return <SmartCreateSection title="Create production order" size="standard"><Card><CardHeader><CardTitle className="text-base">Create production order</CardTitle></CardHeader><CardContent>
    <CompactForm compactTabs={false} aria-label="Create production order" noValidate className="grid gap-3" onSubmit={event => {
      event.preventDefault(); setSubmitted(true); setError("");
      if (canWrite && !post.isPending && !warehouses.isError && !Object.keys(errors).length) post.mutate();
    }}>
      <fieldset className="grid gap-3" disabled={!canWrite || post.isPending}>
        <div className="grid gap-1 text-sm">BOM
          <SmartRecordPicker placeholder="Search BOM by name or number…" name="BOM" value={selected ? String(selected.id) : ""} selected={selected ? option(selected) : undefined} search={search} onSearch={setSearch} items={(orders.data?.pages.flatMap(page => page.items) || []).map(option)} onSelect={row => { setSelected(row); setError(""); }} onClear={() => setSelected(undefined)} loading={orders.isFetching} error={orders.isError ? "BOMs could not load." : undefined} retry={() => void orders.refetch()} hasMore={orders.hasNextPage} loadMore={() => void orders.fetchNextPage()} />
          {submitted && errors.order && <span role="alert" className="text-destructive">{errors.order}</span>}
        </div>
        <label className="grid gap-1 text-sm">Planned quantity<Input aria-label="Planned quantity" inputMode="decimal" value={quantity} aria-invalid={submitted && !!errors.quantity} onChange={event => setQuantity(event.target.value)} />{submitted && errors.quantity && <span role="alert" className="text-destructive">{errors.quantity}</span>}</label>
        <label className="grid gap-1 text-sm">Output warehouse (optional)<NativeSelect aria-label="Output warehouse" value={warehouse} onChange={event => setWarehouse(event.target.value)}><option value="">Use finished product default</option>{warehouseRows.map(row => <option key={String(row.id)} value={String(row.id)}>{String(row.warehouse_name)}</option>)}</NativeSelect>{submitted && errors.warehouse && <span role="alert">{errors.warehouse}</span>}</label>
        <label className="grid gap-1 text-sm">Order date<Input aria-label="Order date" type="date" value={date} onChange={event => setDate(event.target.value)} /></label>
        <label className="grid gap-1 text-sm">Notes<RichTextField value={notes} onChange={event => setNotes(event.target.value)} /></label>
      </fieldset>
      {warehouses.isError && <p role="alert">Warehouses could not load. <Button type="button" onClick={() => void warehouses.refetch()}>Retry warehouses</Button></p>}
      {error && <p role="alert" className="text-destructive">{error}</p>}
      <Button type="submit" disabled={!canWrite || post.isPending || warehouses.isPending || warehouses.isError}>{post.isPending ? "Creating…" : "Create order"}</Button>
    </CompactForm>
  </CardContent></Card></SmartCreateSection>;
}
