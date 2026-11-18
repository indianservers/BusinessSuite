import SmartRecordPicker from "@/shared/records/SmartRecordPicker";
import { useState } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import CompanySelect, { useDebounced, type Company } from "@/shared/master-data/CompanySelect";
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
import { useFinanceWrite } from "./useFinanceWrite";
import type { FAMRecord } from "./types";

const items = (data: unknown): FAMRecord[] => Array.isArray(data) ? data : (data as { items?: FAMRecord[] })?.items || [];
const amountValid = (value: string) => /^(?:\d+\.?\d*|\.\d+)$/.test(value) && Number.isFinite(Number(value));
const emptyPo = { product: "", warehouse: "", quantity: "1", price: "0", tax: "0" };
const emptyGrn = { order: "", line: "", quantity: "1", accepted: "1", rejected: "0", price: "0", tax: "0", reference: "" };

export default function InventoryProcurementForms() {
  const scope = useRecordScope();
  return <ProcurementForms key={scope} scope={scope} />;
}

function ProcurementForms({ scope }: { scope: string }) {
  const qc = useQueryClient(), canWrite = useFinanceWrite(["srm_manage", "srm_admin"], "create");
  const [vendor, setVendor] = useState<Company>(), [vendorId, setVendorId] = useState("");
  const [po, setPo] = useState(emptyPo), [grn, setGrn] = useState(emptyGrn);
  const [poError, setPoError] = useState(""), [grnError, setGrnError] = useState("");
  const products = useQuery({ queryKey: ["srm", "procurement-products", scope], queryFn: () => srmApi.inventoryItems(), staleTime: 30000, retry: false });
  const warehouses = useQuery({ queryKey: ["srm", "procurement-warehouses", scope], queryFn: srmApi.inventoryWarehouses, staleTime: 30000, retry: false });
  const [orderSearch, setOrderSearch] = useState("");
  const orderTerm = useDebounced(orderSearch);
  const orders = useInfiniteQuery({ queryKey: ["srm", "receipt-order-options", scope, orderTerm], initialPageParam: 1, queryFn: ({ pageParam, signal }) => srmApi.purchaseOrderOptions(orderTerm, pageParam, signal), getNextPageParam: page => page.has_more ? page.page + 1 : undefined, staleTime: 30000, retry: false });
  // Authoritative details stay separate from paginated search results.
  const selectedOrder = useQuery({ queryKey: ["srm", "procurement-order", scope, grn.order], queryFn: () => srmApi.purchaseOrder(grn.order), enabled: !!grn.order, retry: false });
  const productRows = products.isError ? [] : items(products.data).filter(row => row.active !== false && row.status !== "Inactive");
  const warehouseRows = warehouses.isError ? [] : items(warehouses.data).filter(row => row.active !== false);
  const orderRows = orders.isError ? [] : [...new Map((orders.data?.pages.flatMap(page => page.items) || []).map(row => [String(row.id), row])).values()].filter(row => !["received", "cancelled", "closed"].includes(String(row.status)));
  const order = selectedOrder.isError ? undefined : selectedOrder.data as FAMRecord | undefined;
  const lines = ((order?.lines || []) as FAMRecord[]).filter(line => Number(line.quantity) > Number(line.received_quantity || 0));
  const orderSuggestion = (row: FAMRecord) => ({ id: String(row.id), label: String(row.po_number), description: String(row.vendor_name || "Supplier"), record: row });
  const pickerOrder = order || orderRows.find(row => String(row.id) === grn.order);
  const selectedLine = lines.find(line => String(line.id) === grn.line);
  const createPo = useMutation({ mutationFn: () => srmApi.createPurchaseOrder({ vendor_id: Number(vendorId), vendor_name: vendor!.name, lines: [{ product_id: Number(po.product), warehouse_id: Number(po.warehouse), quantity: Number(po.quantity), unit_price: Number(po.price), tax_amount: Number(po.tax) }] }), onSuccess: () => { toast({ title: "Purchase order created" }); setPo(emptyPo); setVendor(undefined); setVendorId(""); void qc.invalidateQueries({ queryKey: ["srm"] }); }, onError: error => setPoError(dealError(error)) });
  const createGrn = useMutation({ mutationFn: () => srmApi.createGoodsReceipt({ purchase_order_id: Number(grn.order), reference_number: grn.reference, lines: [{ purchase_order_line_id: Number(grn.line), quantity: Number(grn.quantity), accepted_quantity: Number(grn.accepted), rejected_quantity: Number(grn.rejected), unit_price: Number(grn.price), tax_amount: Number(grn.tax) }] }), onSuccess: () => { toast({ title: "GRN posted and stock updated" }); setGrn(emptyGrn); void qc.invalidateQueries({ queryKey: ["srm"] }); }, onError: error => setGrnError(dealError(error)) });
  const numberField = (label: string, value: string, change: (value: string) => void) => <label className="grid gap-1 text-sm">{label}<Input required inputMode="decimal" aria-label={label} value={value} onChange={event => change(event.target.value)} /></label>;
  return <div className="grid gap-4 lg:grid-cols-2">
    <SmartCreateSection title="Create purchase order" size="compact"><Card><CardHeader><CardTitle className="text-base">Create purchase order</CardTitle></CardHeader><CardContent>
      <CompactForm className="grid gap-3 md:grid-cols-2" onSubmit={event => {
        event.preventDefault(); setPoError(""); if (!canWrite || createPo.isPending) return;
        if (!vendor || String(vendor.id) !== vendorId || !productRows.some(row => String(row.id) === po.product) || !warehouseRows.some(row => String(row.id) === po.warehouse)) { setPoError("Choose an available vendor, product and warehouse."); return; }
        if (![po.quantity, po.price, po.tax].every(amountValid) || Number(po.quantity) <= 0) { setPoError("Enter a quantity greater than zero and nonnegative price and tax."); return; }
        createPo.mutate();
      }}><fieldset disabled={!canWrite || createPo.isPending} className="contents">
        <div className="md:col-span-2"><CompanySelect source="srm" entityKind="all" label="Vendor" value={vendorId} onChange={value => { setVendorId(value); if (!value) setVendor(undefined); }} onSelected={setVendor} createRoles={["Vendor"]} createRecordLabel="vendor" /></div>
        <label className="grid gap-1 text-sm">Product<NativeSelect required searchable aria-label="Purchase product" value={po.product} onChange={event => setPo(current => ({ ...current, product: event.target.value }))}><option value="">Choose product</option>{productRows.map(row => <option key={String(row.id)} value={String(row.id)}>{String(row.item_name || row.name)}{row.sku ? ` · ${row.sku}` : ""}</option>)}</NativeSelect></label>
        <label className="grid gap-1 text-sm">Warehouse<NativeSelect required searchable aria-label="Purchase warehouse" value={po.warehouse} onChange={event => setPo(current => ({ ...current, warehouse: event.target.value }))}><option value="">Choose warehouse</option>{warehouseRows.map(row => <option key={String(row.id)} value={String(row.id)}>{String(row.warehouse_name)}</option>)}</NativeSelect></label>
        {numberField("Order quantity", po.quantity, quantity => setPo(current => ({ ...current, quantity })))}{numberField("Order unit price", po.price, price => setPo(current => ({ ...current, price })))}{numberField("Order tax amount", po.tax, tax => setPo(current => ({ ...current, tax })))}
        {products.isError && <p role="alert">Products could not load. <Button type="button" onClick={() => void products.refetch()}>Retry products</Button></p>}{warehouses.isError && <p role="alert">Warehouses could not load. <Button type="button" onClick={() => void warehouses.refetch()}>Retry warehouses</Button></p>}
        {poError && <p role="alert" className="md:col-span-2">{poError}</p>}<Button type="submit" disabled={products.isPending || products.isError || warehouses.isPending || warehouses.isError}>Create PO</Button>
      </fieldset></CompactForm>
    </CardContent></Card></SmartCreateSection>
    <Card><CardHeader><CardTitle className="text-base">Post GRN</CardTitle></CardHeader><CardContent><CompactForm className="grid gap-3 md:grid-cols-2" onSubmit={event => {
      event.preventDefault(); setGrnError(""); if (!canWrite || createGrn.isPending) return;
      if (!order || !selectedLine || selectedOrder.isFetching) { setGrnError("Choose an available purchase order and order line."); return; }
      if (![grn.quantity, grn.accepted, grn.rejected, grn.price, grn.tax].every(amountValid) || Number(grn.quantity) <= 0 || Math.abs(Number(grn.accepted) + Number(grn.rejected) - Number(grn.quantity)) > 0.000001) { setGrnError("Enter nonnegative amounts. Accepted and rejected quantities must add up to the received quantity."); return; }
      if (Number(grn.accepted) > Number(selectedLine.quantity) - Number(selectedLine.received_quantity || 0)) { setGrnError("Accepted quantity exceeds the remaining ordered quantity."); return; }
      createGrn.mutate();
    }}><fieldset disabled={!canWrite || createGrn.isPending} className="contents">
      <div><span className="text-sm">Purchase order</span><SmartRecordPicker name="Purchase order" value={grn.order} search={orderSearch} onSearch={setOrderSearch} items={orderRows.map(orderSuggestion)} selected={pickerOrder ? orderSuggestion(pickerOrder) : undefined} onSelect={row => { setGrn({ ...emptyGrn, order: String(row.id) }); setOrderSearch(""); }} onClear={() => { setGrn(emptyGrn); setOrderSearch(""); }} loading={orders.isFetching} error={orders.isError ? "Purchase orders could not load." : undefined} retry={() => void orders.refetch()} hasMore={orders.hasNextPage} loadMore={() => void orders.fetchNextPage()}/></div>
      <label className="grid gap-1 text-sm">Order line<NativeSelect required searchable aria-label="Receipt order line" disabled={!order || selectedOrder.isFetching} value={grn.line} onChange={event => { const line = lines.find(row => String(row.id) === event.target.value); setGrn(current => ({ ...current, line: event.target.value, price: String(line?.unit_price || 0) })); }}><option value="">Choose order line</option>{lines.map(line => <option key={String(line.id)} value={String(line.id)}>{String(line.description || line.item_code || "Order item")} · {Number(line.quantity) - Number(line.received_quantity || 0)} remaining</option>)}</NativeSelect></label>
      {numberField("Received quantity", grn.quantity, quantity => setGrn(current => ({ ...current, quantity })))}{numberField("Accepted quantity", grn.accepted, accepted => setGrn(current => ({ ...current, accepted })))}{numberField("Rejected quantity", grn.rejected, rejected => setGrn(current => ({ ...current, rejected })))}{numberField("Receipt unit price", grn.price, price => setGrn(current => ({ ...current, price })))}{numberField("Receipt tax amount", grn.tax, tax => setGrn(current => ({ ...current, tax })))}
      <label className="grid gap-1 text-sm">Reference number<Input value={grn.reference} onChange={event => setGrn(current => ({ ...current, reference: event.target.value }))} /></label>
      {orders.isError && <p role="alert">Purchase orders could not load. <Button type="button" onClick={() => void orders.refetch()}>Retry purchase orders</Button></p>}{selectedOrder.isError && <p role="alert">Order lines could not load. <Button type="button" onClick={() => void selectedOrder.refetch()}>Retry order lines</Button></p>}
      {grnError && <p role="alert" className="md:col-span-2">{grnError}</p>}<Button type="submit" disabled={!grn.order || selectedOrder.isPending || selectedOrder.isFetching || selectedOrder.isError}>Post GRN</Button>
    </fieldset></CompactForm></CardContent></Card>
  </div>;
}
