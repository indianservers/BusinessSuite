import { standardRecordGroups } from "@/shared/data-grid/record-group-fields";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

export type PaymentSource = "crm_deal" | "crm_quotation" | "srm_order" | "srm_invoice";
type Props = { source: PaymentSource; sourceId: number };
type Request = { id: number; request_id: string; reference: string; amount: string; currency: string; instructions: string; status: string; payment_url?: string; amount_paid: string; receipt_id?:number };
type Context = { reference: string; currency: string; available_amount: string; payable: boolean; guidance: string; can_match_receipt: boolean; gateway: { connected: boolean; provider?: string; test_mode: boolean; planned_provider: string } };
const errorText = (error: unknown) => {
  const detail = (error as {response?:{data?:{detail?:unknown}}})?.response?.data?.detail;
  return typeof detail === "string" ? detail : "Payment request could not be updated. Your draft is retained; refresh requests before retrying.";
};
const statusLabel = (status: string) => ({ awaiting_gateway: "Saved · awaiting gateway", creating_link: "Link creation in progress", reconciliation_required: "Provider outcome needs reconciliation", link_ready: "Payment link ready", gateway_paid: "Gateway reports paid · reconcile receipt", partially_paid: "Gateway reports partial payment · reconcile receipt", receipt_recorded:"Matched to recorded receipt", cancelled: "Cancelled", expired: "Expired" }[status] || status);
export const requestMessage = (row: Request) => `Please arrange payment of ${row.currency} ${row.amount} for ${row.reference}.\nPayment request reference: ${row.request_id}${row.payment_url ? `\nPay securely: ${row.payment_url}` : ""}${row.instructions ? `\n${row.instructions}` : ""}${!row.payment_url && !row.instructions ? "\nPlease contact us for payment details." : ""}`;

export function PaymentRequestButton(props: Props) {
  const [open, setOpen] = useState(false);
  return <><Button type="button" variant="outline" onClick={() => setOpen(true)}>Request payment</Button>{open && <Dialog open onOpenChange={setOpen}><DialogContent className="max-w-3xl max-h-[90dvh] overflow-y-auto"><DialogTitle>Request payment</DialogTitle><PaymentRequests {...props}/></DialogContent></Dialog>}</>;
}

export default function PaymentRequests(props: Props) {
  const user = useAuthStore(state => state.user);
  const scope = `${user?.id}:${user?.access?.companyId}:${sessionStorage.getItem("suite-branch") || "all"}`;
  return <Workspace key={`${scope}:${props.source}:${props.sourceId}`} {...props} scope={scope}/>;
}

function Workspace({ source, sourceId, scope }: Props & {scope: string}) {
  const cache = useQueryClient(), navigate = useNavigate();
  const user = useAuthStore(state => state.user);
  const canUseWhatsApp = canAccessRoute("/crm/whatsapp", user?.role, user?.is_superuser);
  const [amount, setAmount] = useState(""), [instructions, setInstructions] = useState("");
  const [requestId, setRequestId] = useState(() => crypto.randomUUID()), [notice, setNotice] = useState("");
  const key = ["payment-requests", scope, source, sourceId];
  const params = {source_type: source, source_id: sourceId};
  const context = useQuery({queryKey: [...key, "context"], queryFn: async () => (await api.get<Context>("/payment-requests/context", {params})).data});
  const requests = useQuery({queryKey: [...key, "items"], queryFn: async () => (await api.get<{items: Request[]}>("/payment-requests", {params})).data});
  const save = useMutation({mutationFn: async () => (await api.post<Request>("/payment-requests", {...params, request_id: requestId, amount, instructions})).data,
    onSuccess: async () => {setRequestId(crypto.randomUUID());setAmount("");setInstructions("");setNotice("Payment request saved. No payment has been recorded.");await cache.invalidateQueries({queryKey:key});}});
  const action = useMutation({mutationFn: async ({id, operation}:{id:number;operation:"link"|"refresh"|"cancel"|"reconcile-receipt"}) => (await api.post<Request>(`/payment-requests/${id}/${operation}`)).data,
    onSuccess: () => {setNotice("Payment request updated. Receipts and accounting remain separate.");},
    onSettled: () => cache.invalidateQueries({queryKey:key})});
  const ctx = context.data, working = save.isPending || action.isPending;
  if (context.isPending) return <p role="status">Loading payment source…</p>;
  if (context.isError || !ctx) return <p role="alert">{errorText(context.error)} <Button variant="outline" onClick={() => void context.refetch()}>Retry</Button></p>;
  const valid = /^\d+(\.\d{1,2})?$/.test(amount) && Number(amount) > 0 && Number(amount) <= Number(ctx.available_amount);
  return <section className="space-y-4">
    <p><strong>{ctx.reference}</strong> · Available to request: {ctx.currency} {ctx.available_amount}</p>
    <p className="rounded-lg border p-3 text-sm" role="status">{ctx.gateway.connected ? ctx.gateway.test_mode ? "Razorpay test credentials configured. Test links do not collect real money." : "Razorpay credentials configured. Generate a hosted link after saving the request." : "No online payment gateway connected. Save a request and share your payment instructions now. Connect Razorpay later to generate online payment links."}</p>
    <p className="text-sm text-muted-foreground">Saving, sharing or opening a payment request does not mark a sale or invoice paid. Reconcile confirmed receipts in Collections.</p>
    {ctx.payable && Number(ctx.available_amount) > 0 ? <form className="space-y-3" onSubmit={event => {event.preventDefault();setNotice("");save.mutate();}}>
      <label className="block text-sm">Amount to request ({ctx.currency})<Input aria-label="Amount to request" type="number" inputMode="decimal" min="0.01" step="0.01" max={ctx.available_amount} value={amount} disabled={working} onChange={e => setAmount(e.target.value)} required/></label>
      <label className="block text-sm">Payment instructions (optional)<textarea aria-label="Payment instructions" className="block w-full rounded-md border bg-background p-3" rows={3} maxLength={2000} value={instructions} disabled={working} onChange={e => setInstructions(e.target.value)} placeholder="How the customer should pay, or an agreed payment reference"/></label>
      <Button type="submit" disabled={working || !valid}>{save.isPending ? "Saving…" : "Save payment request"}</Button>
    </form> : <p>{ctx.guidance} No additional amount is currently available to request.</p>}
    {(save.isError || action.isError) && <p role="alert" className="text-destructive">{errorText(save.error || action.error)}</p>}
    {notice && <p role="status">{notice}</p>}
    {requests.isPending && <p role="status">Loading saved requests…</p>}
    {requests.isError && <p role="alert">{errorText(requests.error)} <button onClick={() => void requests.refetch()}>Retry</button></p>}
    {<GroupedRecords scope="shared/payments/PaymentRequests:records-1" items={(requests.data?.items) || []} fields={standardRecordGroups((requests.data?.items) || [])} gridClassName="space-y-3" renderItem={row => <article key={row.id} className="space-y-2 rounded-lg border p-4">
      <div className="flex flex-wrap justify-between gap-2"><strong>{row.currency} {row.amount}</strong><span>{statusLabel(row.status)}</span></div>
      <p className="break-all text-xs text-muted-foreground">Reference: {row.request_id}</p>
      {row.instructions && <p className="whitespace-pre-wrap text-sm">{row.instructions}</p>}
      {row.payment_url && <a className="break-all underline text-primary" href={row.payment_url} target="_blank" rel="noopener noreferrer">Open hosted payment link</a>}
      <div className="flex flex-wrap gap-2">
        {!["cancelled", "expired", "gateway_paid", "receipt_recorded"].includes(row.status) && <>
          {!row.payment_url && <Button variant="outline" disabled={working || !ctx.gateway.connected} title={ctx.gateway.connected ? "Create or reconcile the original provider request" : "Connect Razorpay to generate a link"} onClick={() => action.mutate({id:row.id,operation:"link"})}>{row.status === "reconciliation_required" || row.status === "creating_link" ? "Reconcile original link" : "Generate payment link"}</Button>}
          <Button variant="outline" disabled={working} onClick={() => void navigator.clipboard.writeText(requestMessage(row)).then(() => setNotice("Payment request text copied.")).catch(() => setNotice("Could not copy. Select and copy the request reference manually."))}>Copy request text</Button>
          <Button variant="outline" disabled={working || !canUseWhatsApp} title={canUseWhatsApp ? "Review recipient and message in Communication" : "WhatsApp access is required; you can copy the request text instead"} onClick={() => navigate("/crm/whatsapp", {state:{whatsappDraft:{key:`payment-request:${row.id}`,to:"",body:requestMessage(row)}}})}>Prepare WhatsApp request</Button>
          <Button variant="ghost" disabled={working} onClick={() => action.mutate({id:row.id,operation:"cancel"})}>Cancel request</Button>
        </>}
        {row.payment_url && ctx.gateway.connected && !row.receipt_id && <Button variant="outline" disabled={working} onClick={() => action.mutate({id:row.id,operation:"refresh"})}>Check provider status</Button>}
        {!row.receipt_id && ctx.can_match_receipt && <Button variant="outline" disabled={working} title="Match a receipt already recorded in Collections using this request reference" onClick={() => action.mutate({id:row.id,operation:"reconcile-receipt"})}>Match recorded receipt</Button>}
        {source === "srm_invoice" && Number(row.amount_paid) > 0 && <Link className="underline" to={`/srm/invoices/${sourceId}`}>Open invoice to reconcile receipt</Link>}
      </div>
    </article>}/>}
    {requests.data && !requests.data.items.length && <p className="text-sm text-muted-foreground">No payment requests for this record yet.</p>}
  </section>;
}
