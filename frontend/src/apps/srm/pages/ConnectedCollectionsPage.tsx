import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { InvoiceList } from "@/apps/project-management/pages/ProjectBillingPage";
import { PaymentRequestButton } from "@/shared/payments/PaymentRequests";

type Row = Record<string, any>;
export function InvoicePaymentForm({
  invoice,
  onSaved,
}: {
  invoice: Row;
  onSaved?: () => unknown;
}) {
  const [method,setMethod]=useState("bank_transfer"),[receiptDate,setReceiptDate]=useState(()=>new Date().toISOString().slice(0,10));
  const queryClient = useQueryClient();
  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const [receipt, setReceipt] = useState<number | null>(null);
  const save = useMutation({
    mutationFn: () =>
      api.post(`/srm/business/invoices/${invoice.id}/payments`, {
        request_id: requestId,
        amount,
        reference,
        payment_method: method,
        receipt_date: receiptDate,
      }),
    onSuccess: (response) => {
      setReceipt(response.data.receipt_id);
      setAmount("");
      setReference("");
      setRequestId(crypto.randomUUID());
      onSaved?.();
      for (const key of [
        "collection-invoices",
        "project-billing",
        "shared-invoice",
        "customer-commercial-history",
        "srm",
        "fam",
      ])
        queryClient.invalidateQueries({ queryKey: [key] });
    },
  });
  return (
    <details className="w-full">
      <summary>Payment and collection actions</summary>
      <p className="my-2 text-sm text-muted-foreground">
        Customer #{invoice.customer_id} · {invoice.currency} · Outstanding{" "}
        {invoice.balance_amount}. The receipt uses this invoice's seller and
        currency.
      </p>
      <CompactForm
        className="flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <div>
          <Label htmlFor={`payment-amount-${invoice.id}`}>
            Amount received
          </Label>
          <Input
            id={`payment-amount-${invoice.id}`}
            required
            type="number"
            inputMode="decimal"
            min="0.01"
            max={invoice.balance_amount}
            step="0.01"
            disabled={save.isPending}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor={`payment-reference-${invoice.id}`}>
            Bank / payment reference
          </Label>
          <Input
            id={`payment-reference-${invoice.id}`}
            maxLength={120}
            disabled={save.isPending}
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          />
        </div>
        <><label className="block text-sm">Payment method<NativeSelect className="block w-full rounded-lg border bg-background p-3" value={method} disabled={save.isPending} onChange={e=>setMethod(e.target.value)}>{["bank_transfer","upi","cash","card","cheque"].map(m=><option key={m} value={m}>{m.replace(/_/g,' ')}</option>)}</NativeSelect></label><label className="block text-sm">Received on<Input type="date" value={receiptDate} required disabled={save.isPending} onChange={e=>setReceiptDate(e.target.value)}/></label></>
        <Button type="submit" disabled={save.isPending || !amount}>
          Record received payment
        </Button>
      </CompactForm>
      {save.isError && (
        <p role="alert">
          {(save.error as any)?.response?.data?.detail ||
            "Unable to record payment. Your entries are preserved for retry."}
        </p>
      )}
      {receipt && (
        <p role="status">
          Receipt #{receipt} saved and applied to this invoice.
        </p>
      )}
      <CollectionControls invoice={invoice} onSaved={onSaved} />
    </details>
  );
}

function CollectionControls({ invoice, onSaved }: { invoice: Row; onSaved?: () => unknown }) {
  const cache = useQueryClient();
  const [reason, setReason] = useState("");
  const [resumeAt, setResumeAt] = useState("");
  const control = useMutation({
    mutationFn: () => api.put(`/srm/collections/${invoice.id}/control`, {
      hold: !invoice.collection_hold,
      reason: reason.trim(),
      resume_at: !invoice.collection_hold && resumeAt ? new Date(resumeAt).toISOString() : null,
    }),
    onSuccess: () => {
      setReason("");
      onSaved?.();
      for (const key of ["collection-invoices", "shared-invoice", "customer-commercial-history", "srm", "fam"])
        cache.invalidateQueries({ queryKey: [key] });
    },
  });
  return <section className="mt-4 border-t pt-3" aria-label="Collection controls">
    <p className="text-sm font-medium">{invoice.collection_hold ? "Collections on hold" : "Collection reminders active"}</p>
    {invoice.collection_hold_reason && <p className="text-sm text-muted-foreground">{invoice.collection_hold_reason}</p>}
    {invoice.collection_resume_at && <p className="text-sm">Scheduled resume: {new Date(invoice.collection_resume_at).toLocaleString()}</p>}
    <form className="mt-2 flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); control.mutate(); }}>
      <label className="text-sm">Reason<Input required minLength={3} maxLength={500} value={reason} onChange={e=>setReason(e.target.value)} disabled={control.isPending} /></label>
      {!invoice.collection_hold && <label className="text-sm">Resume at (optional)<Input type="datetime-local" value={resumeAt} onChange={e=>setResumeAt(e.target.value)} disabled={control.isPending}/></label>}
      <Button type="submit" variant="outline" disabled={control.isPending || reason.trim().length < 3}>{invoice.collection_hold ? "Resume reminders" : "Pause collections / dispute"}</Button>
    </form>
    {control.isError && <p role="alert">{(control.error as any)?.response?.data?.detail || "Unable to update collection controls."}</p>}
  </section>;
}

export default function ConnectedCollectionsPage() {
  const uid = useAuthStore((state) => state.user?.id);
  const query = useQuery({
    queryKey: ["collection-invoices", uid],
    queryFn: async () => {
      const {data} = await api.get<{items: Row[]; can_record: boolean}>("/srm/business/collection-invoices");
      if (!data || !Array.isArray(data.items) || typeof data.can_record !== "boolean") throw new Error("Collection invoice choices are unavailable");
      return data;
    },
    refetchInterval: 10000,
  });
  if (query.isPending) return <p>Loading collections…</p>;
  if (query.isError)
    return (
      <p role="alert">
        Collections are unavailable or outside your financial permissions.{" "}
        <Button onClick={() => query.refetch()}>Retry</Button>
      </p>
    );
  return (
    <div className="space-y-5">
      <h1 className="page-title">Collections</h1>
      <p className="text-muted-foreground">
        Record actual customer payments against issued invoices. Project billing
        and customer history use these same receipt records.
      </p>
      <Card>
        <CardHeader>
          <CardTitle>Invoices and outstanding balances</CardTitle>
        </CardHeader>
        <CardContent>
          <InvoiceList
            invoices={query.data.items}
            actions={(row) =>
              query.data.can_record &&
              row.document_status === "issued" &&
              Number(row.balance_amount) > 0 ? (
                <><PaymentRequestButton source="srm_invoice" sourceId={Number(row.id)}/><InvoicePaymentForm
                  key={`${uid}-${row.id}`}
                  invoice={row}
                  onSaved={() => query.refetch()}
                /></>
              ) : null
            }
          />
        </CardContent>
      </Card>
    </div>
  );
}
