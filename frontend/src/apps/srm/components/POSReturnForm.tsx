import { useEffect, useRef, useState } from "react";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { recordScope, useRecordScope } from "@/shared/records/Record360Workspace";
import { useDebounced } from "@/shared/master-data/CompanySelect";
import SmartRecordPicker from "@/shared/records/SmartRecordPicker";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import CompactForm from "@/components/forms/CompactForm";
import { NativeSelect } from "@/components/ui/native-select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/hooks/use-toast";
import { dealError } from "@/apps/crm/deals/deal-utils";
import { useFinanceWrite } from "@/apps/fam/useFinanceWrite";
import { srmApi } from "../api";
import { syncSrmNow } from "../realtime";
import type { SRMRecord } from "../types";

export default function POSReturnForm() {
  const scope = useRecordScope();
  return <ReturnForm key={scope} scope={scope} />;
}
function ReturnForm({ scope }: { scope: string }) {
  const queryClient = useQueryClient(), canWrite = useFinanceWrite(["srm_manage", "srm_admin"], "create");
  const owner = useRef(recordScope(useAuthStore.getState().user)), active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const owns = () => active.current && owner.current === recordScope(useAuthStore.getState().user);
  const [sale, setSale] = useState<SRMRecord>();
  const [lineId, setLineId] = useState("");
  const [search, setSearch] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [method, setMethod] = useState("cash"), [reason, setReason] = useState("");
  const [submitted, setSubmitted] = useState(false), [error, setError] = useState("");
  const term = useDebounced(search);
  const sales = useInfiniteQuery({ queryKey: ["srm", "return-sale-options", scope, term], initialPageParam: 1, retry: false,
    queryFn: ({ pageParam, signal }) => api.get<{ items: SRMRecord[]; has_more: boolean }>("/srm/pos/return-sales", { signal, params: { page: pageParam, per_page: 30, search: term } }).then(r => r.data),
    getNextPageParam: (last, _pages, page) => last.has_more ? page + 1 : undefined });
  const lines = ((sale?.lines || []) as SRMRecord[]).filter(line => Number(line.returnable_quantity) > 0);
  const selectedLine = lines.find(line => String(line.id) === lineId);
  const option = (row: SRMRecord) => ({ id: String(row.id), label: String(row.order_number), description: String(row.title || ""), record: row });
  const errors: Record<string, string> = {};
  if (!sale) errors.sale = "Choose the original POS sale.";
  if (!selectedLine) errors.line = "Choose a returnable sale line.";
  if (!/^(?:\d+\.?\d*|\.\d+)$/.test(quantity) || !Number.isFinite(Number(quantity)) || Number(quantity) <= 0) errors.quantity = "Enter a return quantity greater than zero.";
  else if (selectedLine && Number(quantity) > Number(selectedLine.returnable_quantity)) errors.quantity = "Quantity exceeds the remaining returnable quantity.";
  if (!method.trim()) errors.method = "Enter a refund method.";
  const resetLine = () => { setLineId(""); setQuantity("1"); setError(""); };
  const create = useMutation({ mutationFn: () => {
    if (!owns() || !sale || !selectedLine) throw new Error("The sales context changed. Reopen this form.");
    return srmApi.createPosReturn({ sales_order_id: sale.id, refund_method: method.trim(), reason: reason.trim() || undefined, lines: [{ sales_order_line_id: selectedLine.id, product_id: selectedLine.product_id || undefined, quantity: Number(quantity), restock: true, condition: "sellable" }] });
  }, onSuccess: result => {
    if (!owns()) return;
    toast({ title: "POS return created" }); setSale(undefined); resetLine(); setSearch(""); setReason(""); setSubmitted(false);
    void syncSrmNow(queryClient, { type: "pos_return_completed", source: "srm-pos-returns", ids: { return_id: Number((result as SRMRecord | undefined)?.id || 0) || undefined } }).catch(() => undefined);
  }, onError: value => { if (owns()) setError(dealError(value)); } });
  return <SmartCreateSection title="Create return" size="standard"><Card><CardHeader><CardTitle className="text-base">Create return</CardTitle></CardHeader><CardContent>
    <CompactForm compactTabs={false} aria-label="Create POS return" noValidate className="grid gap-3" onSubmit={event => { event.preventDefault(); setSubmitted(true); setError(""); if (canWrite && !create.isPending && !Object.keys(errors).length) create.mutate(); }}>
      <fieldset className="grid gap-3" disabled={!canWrite || create.isPending}>
        <div className="grid gap-1 text-sm">Original POS sale<SmartRecordPicker name="POS sale" placeholder="Search sale by number or title…" value={sale ? String(sale.id) : ""} selected={sale ? option(sale) : undefined} search={search} onSearch={setSearch} items={(sales.data?.pages.flatMap(page => page.items) || []).map(option)} onSelect={row => { setSale(row); resetLine(); }} onClear={() => { setSale(undefined); resetLine(); }} loading={sales.isFetching} error={sales.isError ? "POS sales could not load." : undefined} retry={() => void sales.refetch()} hasMore={sales.hasNextPage} loadMore={() => void sales.fetchNextPage()} />{submitted && errors.sale && <span role="alert" className="text-destructive">{errors.sale}</span>}</div>
        <label className="grid gap-1 text-sm">Sale line<NativeSelect aria-label="Sale line" aria-invalid={submitted && !!errors.line} value={lineId} onChange={event => { setLineId(event.target.value); setQuantity("1"); setError(""); }}><option value="">Choose sale line</option>{lines.map((line, index) => <option key={String(line.id)} value={String(line.id)}>{index + 1}. {String(line.description || line.item_code || "Sale item")} · {String(line.returnable_quantity)} returnable · {String(line.unit_price)} {String(sale?.currency || "")}</option>)}</NativeSelect>{submitted && errors.line && <span role="alert" className="text-destructive">{errors.line}</span>}</label>
        {sale && !lines.length && <p role="status">This sale has no remaining returnable lines.</p>}
        <label className="grid gap-1 text-sm">Return quantity<Input aria-label="Return quantity" inputMode="decimal" aria-invalid={submitted && !!errors.quantity} value={quantity} onChange={event => setQuantity(event.target.value)} />{submitted && errors.quantity && <span role="alert" className="text-destructive">{errors.quantity}</span>}</label>
        <label className="grid gap-1 text-sm">Refund method<Input aria-label="Refund method" value={method} onChange={event => setMethod(event.target.value)} />{submitted && errors.method && <span role="alert" className="text-destructive">{errors.method}</span>}</label>
        <label className="grid gap-1 text-sm">Reason (optional)<Input aria-label="Reason" value={reason} onChange={event => setReason(event.target.value)} /></label>
        <p className="text-sm text-muted-foreground">Refund value and tax come from the original sale. Returned products are restocked as sellable.</p>
      </fieldset>
      {error && <p role="alert" className="text-destructive">{error}</p>}
      <Button data-save-action type="submit" disabled={!canWrite || create.isPending}>{create.isPending ? "Creating…" : "Create return"}</Button>
    </CompactForm>
  </CardContent></Card></SmartCreateSection>;
}
