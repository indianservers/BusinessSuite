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
import type { FAMRecord } from "./types";

export default function InventoryProductionPostingForm() {
  const scope = useRecordScope();
  return <PostingForm key={scope} scope={scope} />;
}

function PostingForm({ scope }: { scope: string }) {
  const queryClient = useQueryClient();
  const canWrite = useFinanceWrite(["srm_manage", "srm_admin"], "create");
  const owner = useRef(recordScope(useAuthStore.getState().user));
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const owns = () => active.current && owner.current === recordScope(useAuthStore.getState().user);
  const [selected, setSelected] = useState<FAMRecord>();
  const [search, setSearch] = useState("");
  const [quantity, setQuantity] = useState("");
  const [warehouse, setWarehouse] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const term = useDebounced(search);
  const orders = useInfiniteQuery({
    queryKey: ["srm", "production-posting-options", scope, term], initialPageParam: 1, retry: false,
    queryFn: ({ pageParam, signal }) => api.get<{ items: FAMRecord[]; has_more: boolean }>("/srm/inventory/manufacturing/orders", { signal, params: { page: pageParam, per_page: 30, search: term, open_only: true } }).then(r => r.data),
    getNextPageParam: (last, _pages, page) => last.has_more ? page + 1 : undefined,
  });
  const warehouses = useQuery({ queryKey: ["srm", "production-posting-warehouses", scope], queryFn: srmApi.inventoryWarehouses, retry: false });
  const warehouseData = warehouses.data as { items?: FAMRecord[] } | FAMRecord[] | undefined;
  const warehouseRows = (Array.isArray(warehouseData) ? warehouseData : warehouseData?.items || []).filter(row => row.active !== false);
  const option = (row: FAMRecord) => ({
    id: String(row.id), label: String(row.production_number), record: row,
    description: `${String((row.finished_product as FAMRecord | undefined)?.item_name || "Product")} · Remaining ${Number(row.planned_quantity) - Number(row.completed_quantity)} · ${String(row.status).replace(/_/g, " ")}`,
  });
  const errors: Record<string, string> = {};
  if (!selected) errors.order = "Choose an open production order.";
  if (!/^(?:\d+\.?\d*|\.\d+)$/.test(quantity) || !Number.isFinite(Number(quantity)) || Number(quantity) <= 0) errors.quantity = "Enter a completed quantity greater than zero.";
  if (warehouse && !warehouseRows.some(row => String(row.id) === warehouse)) errors.warehouse = "Choose an available warehouse.";
  const post = useMutation({
    mutationFn: () => {
      if (!owns() || !selected) throw new Error("The inventory context changed. Reopen this form.");
      return srmApi.postProductionOrder(String(selected.id), { completed_quantity: Number(quantity), warehouse_id: warehouse ? Number(warehouse) : undefined });
    },
    onSuccess: () => {
      if (!owns()) return;
      toast({ title: "Production posted and stock updated" });
      setSelected(undefined); setQuantity(""); setWarehouse(""); setSearch(""); setSubmitted(false); setError("");
      void queryClient.invalidateQueries({ queryKey: ["srm"] });
    },
    onError: reason => { if (owns()) setError(dealError(reason)); },
  });
  return <Card><CardHeader><CardTitle className="text-base">Post production</CardTitle></CardHeader><CardContent>
    <CompactForm compactTabs={false} aria-label="Post production" noValidate className="grid gap-3" onSubmit={event => {
      event.preventDefault(); setSubmitted(true); setError("");
      if (canWrite && !post.isPending && !warehouses.isError && !Object.keys(errors).length) post.mutate();
    }}>
      <fieldset className="grid gap-3" disabled={!canWrite || post.isPending}>
        <div className="grid gap-1 text-sm">Production order
          <SmartRecordPicker placeholder="Search production order by number…" name="production order" value={selected ? String(selected.id) : ""} selected={selected ? option(selected) : undefined} search={search} onSearch={setSearch} items={(orders.data?.pages.flatMap(page => page.items) || []).map(option)} onSelect={row => { setSelected(row); setError(""); }} onClear={() => setSelected(undefined)} loading={orders.isFetching} error={orders.isError ? "Production orders could not load." : undefined} retry={() => void orders.refetch()} hasMore={orders.hasNextPage} loadMore={() => void orders.fetchNextPage()} />
          {submitted && errors.order && <span role="alert" className="text-destructive">{errors.order}</span>}
        </div>
        <label className="grid gap-1 text-sm">Completed quantity<Input aria-label="Completed quantity" inputMode="decimal" value={quantity} aria-invalid={submitted && !!errors.quantity} onChange={event => setQuantity(event.target.value)} />{submitted && errors.quantity && <span role="alert" className="text-destructive">{errors.quantity}</span>}</label>
        <label className="grid gap-1 text-sm">Output warehouse (optional)<NativeSelect aria-label="Output warehouse" value={warehouse} onChange={event => setWarehouse(event.target.value)}><option value="">Use order or product default</option>{warehouseRows.map(row => <option key={String(row.id)} value={String(row.id)}>{String(row.warehouse_name)}</option>)}</NativeSelect>{submitted && errors.warehouse && <span role="alert">{errors.warehouse}</span>}</label>
        <p className="text-sm text-muted-foreground">Posting consumes component stock and adds the completed product quantity.</p>
      </fieldset>
      {warehouses.isError && <p role="alert">Warehouses could not load. <Button type="button" onClick={() => void warehouses.refetch()}>Retry warehouses</Button></p>}
      {error && <p role="alert" className="text-destructive">{error}</p>}
      <Button type="submit" disabled={!canWrite || post.isPending || warehouses.isPending || warehouses.isError}>{post.isPending ? "Posting…" : "Post stock"}</Button>
    </CompactForm>
  </CardContent></Card>;
}
