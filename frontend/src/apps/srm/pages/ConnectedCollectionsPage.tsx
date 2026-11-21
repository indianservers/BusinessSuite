import { randomUUID } from "@/lib/random-uuid";
import { useBusinessTerms } from '@/hooks/use-business-terms';
import { useRecordScope } from '@/lib/record-scope';
import { useRecordScopeOwner } from '@/hooks/use-record-scope-owner';
import {useModuleAction} from "@/hooks/use-module-action";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import { useRef, useState } from "react";
import { isAxiosError } from 'axios';
import { financialIntentKey, readFinancialIntent, saveFinancialIntent, clearFinancialIntent } from '@/lib/financial-intent';
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { InvoiceList } from "@/apps/project-management/pages/ProjectBillingPage";
import { PaymentRequestButton } from "@/shared/payments/PaymentRequests";
import "../sales-record-list.css";
import { collectionFormError, localReceiptDate } from '../collection-form-utils';

type Row = Record<string, any>;
type InvoicePaymentAttempt = {path: string; body: {request_id: string; amount: string; reference: string; payment_method: string; receipt_date: string}; uncertain?: boolean};
export function InvoicePaymentForm({
  invoice,
  onSaved,
}: {
  invoice: Row;
  onSaved?: () => unknown;
}) {
  const scope = useRecordScope();
  return <InvoicePaymentSurface key={`${scope}-${invoice.id}`} invoice={invoice} onSaved={onSaved} scope={scope} />;
}

function InvoicePaymentSurface({ invoice, onSaved, scope }: { invoice: Row; onSaved?: () => unknown; scope: string }) {
  const owns = useRecordScopeOwner();
  const { term } = useBusinessTerms();
  const canCreate=useModuleAction("create") && invoice.can_record_payment !== false;
  const measurement = invoice.construction_measurement_id;
  const path = Number.isSafeInteger(measurement) && measurement > 0
    ? `/srm/industry/records/${measurement}/payments` : `/srm/business/invoices/${invoice.id}/payments`;
  const key = financialIntentKey('invoice_payment', invoice.id);
  const [recovery] = useState(() => readFinancialIntent<InvoicePaymentAttempt>(key));
  const [restored] = useState(() => {
    const value = recovery.payload;
    return canCreate && value?.path === path && typeof value.body?.request_id === 'string' && /^[0-9a-f-]{36}$/i.test(value.body.request_id)
      && typeof value.body.amount === 'string' && Number(value.body.amount) > 0 && Number.isFinite(Number(value.body.amount))
      && typeof value.body.reference === 'string' && ['bank_transfer','upi','cash','card','cheque'].includes(value.body.payment_method)
      && typeof value.body.receipt_date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value.body.receipt_date)
      ? {...value, uncertain: true} : null;
  });
  const attempt = useRef<InvoicePaymentAttempt | null>(restored), sending = useRef(false);
  const [locked, setLocked] = useState(recovery.pending), [storageError, setStorageError] = useState('');
  const [method,setMethod]=useState(restored?.body.payment_method || "bank_transfer"),[receiptDate,setReceiptDate]=useState(()=>restored?.body.receipt_date || localReceiptDate());
  const queryClient = useQueryClient();
  const [amount, setAmount] = useState(restored?.body.amount || "");
  const [reference, setReference] = useState(restored?.body.reference || "");
  const [receipt, setReceipt] = useState<number | null>(null);
  const save = useMutation({
    mutationFn: (request: InvoicePaymentAttempt) => {
      if (!owns()) throw new Error('The payment workspace changed. Reload this invoice.');
      if (request.path !== path) throw new Error('The invoice payment destination changed.');
      return api.post(request.path, request.body);
    },
    onSuccess: (response, request) => {
      try { if (readFinancialIntent<InvoicePaymentAttempt>(key).payload?.body?.request_id === request.body.request_id) clearFinancialIntent(key); } catch { if (owns()) setStorageError('Payment saved, but recovery storage could not be cleared. Retry the same payment to resolve it.'); return; }
      if (!owns()) return;
      attempt.current = null; setLocked(false); setStorageError('');
      setReceipt(response.data.receipt_id);
      setAmount("");
      setReference("");
      onSaved?.();
      for (const key of [
        "collection-invoices",
        "project-billing",
        "shared-invoice",
        "customer-commercial-history",
        "srm",
        "fam",
      ])
        queryClient.invalidateQueries({ queryKey: ['collection-invoices', 'shared-invoice'].includes(key) ? [key, scope] : [key] });
    },
    onError: (error, request) => {
      const status = isAxiosError(error) ? error.response?.status : undefined;
      if (!request.uncertain && status !== undefined && status >= 400 && status < 500) {
        try { if (readFinancialIntent<InvoicePaymentAttempt>(key).payload?.body?.request_id === request.body.request_id) clearFinancialIntent(key); } catch { request.uncertain = true; return; }
        if (owns()) { attempt.current = null; setLocked(false); }
      } else request.uncertain = true;
    },
    onSettled: () => { sending.current = false; },
  });
  return (
    <details className="srm-invoice-payment w-full">
      <summary>Payment and collection actions</summary>
      <p className="my-2 text-sm text-muted-foreground">
        {term('customer')} #{invoice.customer_id} · {invoice.currency} · Outstanding{" "}
        {invoice.balance_amount}. The receipt uses this invoice's seller and
        currency.
      </p>
      <CompactForm
        className="srm-collection-form flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (!canCreate || !owns() || sending.current || save.isPending || locked && !attempt.current) return;
          if (!attempt.current && readFinancialIntent<InvoicePaymentAttempt>(key).pending) {
            setLocked(true); setStorageError('Another saved payment exists for this invoice. Reload to recover it before recording another.'); return;
          }
          const request = attempt.current || {path, body: {request_id: randomUUID(), amount, reference, payment_method: method, receipt_date: receiptDate}};
          try { saveFinancialIntent(key, request); } catch { setStorageError('Payment was not sent. Recovery storage is unavailable; restore browser storage before trying again.'); return; }
          sending.current = true; attempt.current = request; setLocked(true); setStorageError(''); save.mutate(request);
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
            disabled={save.isPending || locked || !canCreate}
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
            disabled={save.isPending || locked || !canCreate}
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          />
        </div>
        <><label className="block text-sm">Payment method<NativeSelect className="block w-full rounded-lg border bg-background p-3" value={method} disabled={save.isPending || locked || !canCreate} onChange={e=>setMethod(e.target.value)}>{["bank_transfer","upi","cash","card","cheque"].map(m=><option key={m} value={m}>{m.replace(/_/g,' ')}</option>)}</NativeSelect></label><label className="block text-sm">Received on<Input type="date" value={receiptDate} required disabled={save.isPending || locked || !canCreate} onChange={e=>setReceiptDate(e.target.value)}/></label></>
        <Button type="submit" disabled={!canCreate||save.isPending || locked && !attempt.current || !amount}>
          {locked ? 'Retry same payment' : 'Record received payment'}
        </Button>
      </CompactForm>
      {locked && <p role="status">Resolve the saved payment before recording another. Its original amount, method, date and reference are locked.{!attempt.current && ' Recovery data cannot be read; ask an authorized administrator to reconcile this invoice.'}</p>}
      {storageError && <p role="alert">{storageError}</p>}
      {save.isError && (
        <p role="alert">
          {collectionFormError(save.error, "Unable to record payment. Your entries are preserved for retry.")}
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
  const owns = useRecordScopeOwner();
  const canEdit=useModuleAction("edit");
  const cache = useQueryClient();
  const [reason, setReason] = useState("");
  const [resumeAt, setResumeAt] = useState("");
  const control = useMutation({
    mutationFn: () => {
      if (!owns()) throw new Error('The collection workspace changed.');
      return api.put(`/srm/collections/${invoice.id}/control`, {
        hold: !invoice.collection_hold,
        reason: reason.trim(),
        resume_at: !invoice.collection_hold && resumeAt ? new Date(resumeAt).toISOString() : null,
      });
    },
    onSuccess: () => {
      if (!owns()) return;
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
    <form className="srm-collection-form mt-2 flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); if(canEdit)control.mutate(); }}>
      <label className="text-sm">Reason<Input required minLength={3} maxLength={500} value={reason} onChange={e=>setReason(e.target.value)} disabled={control.isPending} /></label>
      {!invoice.collection_hold && <label className="text-sm">Resume at (optional)<Input type="datetime-local" value={resumeAt} onChange={e=>setResumeAt(e.target.value)} disabled={control.isPending}/></label>}
      <Button type="submit" variant="outline" disabled={!canEdit||control.isPending || reason.trim().length < 3}>{invoice.collection_hold ? "Resume reminders" : "Pause collections / dispute"}</Button>
    </form>
    {control.isError && <p role="alert">{collectionFormError(control.error, "Unable to update collection controls.")}</p>}
  </section>;
}

export default function ConnectedCollectionsPage() {
  const scope = useRecordScope();
  return <CollectionsWorkspace key={scope} scope={scope} />;
}

function CollectionsWorkspace({ scope }: { scope: string }) {
  const { term } = useBusinessTerms();
  const canCreate=useModuleAction("create"),canEdit=useModuleAction("edit");
  const uid = useAuthStore((state) => state.user?.id);
  const query = useQuery({
    queryKey: ["collection-invoices", scope, uid],
    queryFn: async ({ signal }) => {
      const {data} = await api.get<{items: Row[]; can_record: boolean}>("/srm/business/collection-invoices", { signal });
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
    <div className="srm-collections-workspace space-y-5">
      <h1 className="page-title">Collections</h1>
      <p className="text-muted-foreground">
        Record actual {term('customer').toLowerCase()} payments against issued invoices. {term('project')} billing
        and {term('customer').toLowerCase()} history use these same receipt records.
      </p>
      <Card>
        <CardHeader>
          <CardTitle>Invoices and outstanding balances</CardTitle>
        </CardHeader>
        <CardContent>
          <InvoiceList
            invoices={query.data.items}
            actions={(row) =>
              query.data.can_record && (canCreate||canEdit) &&
              row.document_status === "issued" &&
              Number(row.balance_amount) > 0 ? (
                <>{canCreate&&<PaymentRequestButton source="srm_invoice" sourceId={Number(row.id)}/>}<InvoicePaymentForm
                  key={`${scope}-${row.id}`}
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
