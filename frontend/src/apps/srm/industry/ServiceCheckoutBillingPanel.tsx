import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { api } from '@/services/api';
import { useRecordScope } from '@/lib/record-scope';
import { financialIntentKey, readFinancialIntent, saveFinancialIntent, clearFinancialIntent } from '@/lib/financial-intent';
import { useRecordScopeOwner } from '@/hooks/use-record-scope-owner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { dealError } from '@/apps/crm/deals/deal-utils';

type Decimal = string | number;
type Checkout = {
  id: number; state: string; revision: number; sales_order_id: number | null;
  invoice: { id: number; number: string; status: string; currency: string; total: Decimal; paid: Decimal; balance: Decimal } | null;
  lines: { id: number; client_line_key: string; kind: string; product_id: number; invoice_line_id: number | null;
    quantity: Decimal; unit_price: Decimal; discount: Decimal; tax: Decimal; total: Decimal; appointment_id: number | null }[];
  receipts: { id: number; payment_key: string; number: string; status: string; method: string; reference?: string | null; amount: Decimal; unallocated: Decimal }[];
};
type Props = { checkoutId: number; serviceCharge?: Decimal; canCollect: boolean; onChanged: () => void };
type Payment = { payment_key: string; method: string; amount: string; reference?: string };
type Attempt = { fingerprint: string; expected_revision: number; payment: Payment; uncertain?: boolean };
// Unresolved attempts are never evicted: the cap fails closed for new payments.
const unresolved = new Map<string, Attempt>();
const MAX_UNRESOLVED = 50;
const isAttempt = (value: Attempt | null | undefined): value is Attempt => !!value && typeof value.payment?.payment_key === "string" && typeof value.payment.amount === "string" && typeof value.payment.method === "string" && Number.isSafeInteger(value.expected_revision);
const words = (value: string) => value.replace(/_/g, ' ');

/** One native checkout invoice/receipt ledger, without inventing paid amounts per service. */
export default function ServiceCheckoutBillingPanel(props: Props) {
  const scope = useRecordScope();
  return <CheckoutBilling key={`${scope}:${props.checkoutId}`} {...props} scope={scope}/>;
}

function CheckoutBilling({ checkoutId, serviceCharge, canCollect, onChanged, scope }: Props & { scope: string }) {
  const owns = useRecordScopeOwner();
  const memoryKey = financialIntentKey("payment", checkoutId);
  const [recovery] = useState(() => readFinancialIntent<Attempt>(memoryKey));
  const [saved] = useState(() => {
    const stored = recovery.payload;
    const valid = isAttempt(stored);
    const current = unresolved.get(memoryKey) || (valid ? stored : undefined);
    if (current) current.uncertain = true;
    return current;
  });
  const [amount, setAmount] = useState(''), [method, setMethod] = useState('cash'), [reference, setReference] = useState('');
  const [unknown, setUnknown] = useState(!!saved || recovery.pending);
  const [notice, setNotice] = useState(''), [validation, setValidation] = useState('');
  const attempt = useRef<Attempt | null>(saved || null);
  const root = `/srm/service-checkout/${checkoutId}`;
  const query = useQuery({ queryKey: ['service-checkout-billing', scope, checkoutId],
    queryFn: async ({ signal }) => {
      const {data}=await api.get<Checkout>(root,{signal,recordCache:false});
      if(!data || data.id!==checkoutId || typeof data.state!=='string' || !Array.isArray(data.receipts) || data.receipts.some(receipt=>typeof receipt.method!=='string'||typeof receipt.status!=='string') || data.invoice && typeof data.invoice.status!=='string')throw new Error('Checkout payment details could not be verified. Reload the confirmed checkout.');
      return data;
    },
    enabled: Number.isSafeInteger(checkoutId) && checkoutId > 0, retry: false, placeholderData: undefined, staleTime:0, refetchOnMount:"always" });
  const capabilities = useQuery({ queryKey: ["checkout-payment-authority", scope, checkoutId], queryFn: ({signal}) => api.get<{collect:boolean}>("/srm/industry/capabilities", {signal,recordCache:false}).then(result=>result.data), enabled: query.isSuccess, retry:false, placeholderData:undefined, staleTime:0, refetchOnMount:"always" });
  const authorizedCollection = canCollect && query.isSuccess && !query.isFetching && capabilities.isSuccess && !capabilities.isFetching && capabilities.data?.collect === true;
  useEffect(() => { if (!authorizedCollection || !owns() || !attempt.current) return; const current = attempt.current; setAmount(current.payment.amount); setMethod(current.payment.method); setReference(current.payment.reference || ""); }, [authorizedCollection]);
  const mutation = useMutation({
    mutationFn: (request: Attempt) => api.post(root + '/payments', {
      expected_revision: request.expected_revision, payment: request.payment,
    }).then(result => result.data), retry: false,
    onSuccess: async (_, request) => {
      if (unresolved.get(memoryKey)?.payment.payment_key === request.payment.payment_key || readFinancialIntent<Attempt>(memoryKey).payload?.payment?.payment_key === request.payment.payment_key) { unresolved.delete(memoryKey); clearFinancialIntent(memoryKey); }
      if (!owns()) return;
      setUnknown(false); attempt.current = null; setAmount(''); setReference(''); setValidation(''); setNotice('Payment recorded against the checkout invoice.');
      await query.refetch();
      if (owns()) onChanged();
    },
    onError: async (error, request) => {
      const status = isAxiosError(error) ? error.response?.status : undefined;
      // A denied retry can happen before the server checks the original key.
      // It cannot disprove an earlier request whose response was lost.
      const rejected = !request.uncertain && status !== undefined && status >= 400 && status < 500;
      if (!rejected) request.uncertain = true;
      if (rejected && (unresolved.get(memoryKey)?.payment.payment_key === request.payment.payment_key || readFinancialIntent<Attempt>(memoryKey).payload?.payment?.payment_key === request.payment.payment_key)) { unresolved.delete(memoryKey); clearFinancialIntent(memoryKey); }
      if (!owns()) return;
      if (rejected) {
        attempt.current = null;
        setNotice('Payment was rejected. Your draft is retained; review the reloaded invoice and receipts before submitting again.');
        await query.refetch();
        if (owns()) { setUnknown(false); onChanged(); }
      } else {
        setUnknown(true);
        setNotice('Payment outcome is unknown. The original payment details are locked. Reload receipts or retry the same payment to resolve it before recording another payment.');
      }
    },
  });
  useEffect(() => {
    const current = attempt.current;
    if (!owns() || !query.isSuccess || query.isFetching || !current || !query.data?.receipts.some(receipt => receipt.payment_key === current.payment.payment_key)) return;
    if (unresolved.get(memoryKey)?.payment.payment_key === current.payment.payment_key || readFinancialIntent<Attempt>(memoryKey).payload?.payment?.payment_key === current.payment.payment_key) { unresolved.delete(memoryKey); clearFinancialIntent(memoryKey); }
    attempt.current = null; setUnknown(false); setAmount(''); setReference(''); setValidation('');
    mutation.reset();
    setNotice('The original payment is confirmed by its receipt.');
  }, [query.data, query.isSuccess, query.isFetching, memoryKey, unknown, mutation.reset]);
  const checkout = query.isSuccess && !query.isFetching ? query.data : undefined, invoice = checkout?.invoice, pending = mutation.isPending;
  const money = (value: Decimal) => {
    const number = Number(value);
    return `${invoice?.currency || ''} ${Number.isFinite(number) ? number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : String(value)}`.trim();
  };
  function collect() {
    if (!authorizedCollection || !checkout || !invoice || pending || !owns()) return;
    setValidation(''); setNotice('');
    if (attempt.current) { attempt.current.uncertain = true; mutation.mutate(attempt.current); return; }
    const stored = readFinancialIntent<Attempt>(memoryKey);
    const outstanding = unresolved.get(memoryKey) || (isAttempt(stored.payload) ? stored.payload : null);
    if (stored.pending && !outstanding) { setValidation("An unresolved payment requires reconciliation before another payment can be recorded."); return; }
    if (outstanding) {
      attempt.current = outstanding; setAmount(outstanding.payment.amount); setMethod(outstanding.payment.method); setReference(outstanding.payment.reference || ''); setUnknown(true);
      setNotice('An unresolved payment already exists for this checkout. Review and retry that same payment before recording another.'); return;
    }
    if (unresolved.size >= MAX_UNRESOLVED) { setValidation('Resolve an outstanding payment before recording another payment. The local unresolved-payment limit has been reached.'); return; }
    const payment = { method, amount: amount.trim(), ...(reference.trim() ? { reference: reference.trim() } : {}) };
    const fingerprint = JSON.stringify(payment);
    if (!/^\d+(\.\d{1,2})?$/.test(payment.amount) || !Number.isFinite(Number(payment.amount)) || Number(payment.amount) <= 0) {
      setValidation('Enter a positive amount with up to two decimal places.'); return;
    }
    if (Number(payment.amount) > Number(invoice.balance)) {
      setValidation('Amount exceeds the current checkout invoice balance. Reload payments to review the latest balance.'); return;
    }
    const request = { fingerprint, expected_revision: checkout.revision, payment: { payment_key: crypto.randomUUID(), ...payment } };
    try { saveFinancialIntent(memoryKey, request); } catch { setValidation("Payment recovery storage is unavailable. No payment was submitted."); return; }
    unresolved.set(memoryKey, request); attempt.current = request; setUnknown(true);
    mutation.mutate(request);
  }
  return <section className="mt-5 grid gap-4 border-t pt-4" aria-label="Service checkout payments">
    <div><h3 className="font-semibold">Checkout charges & payments</h3><p className="text-xs text-muted-foreground">This service belongs to a shared checkout. Payments settle the whole invoice; a paid amount is not allocated to each service here.</p></div>
    {query.isSuccess && !query.isFetching && serviceCharge !== undefined && <div className="rounded border p-3"><p className="text-xs text-muted-foreground">This service charge</p><p className="font-semibold">{money(serviceCharge)}</p></div>}
    {query.isPending && <p role="status">Loading checkout payments…</p>}
    {query.isError && <p role="alert">{dealError(query.error)} <Button variant="outline" disabled={pending || query.isFetching} onClick={() => void query.refetch()}>Retry checkout</Button></p>}
    {checkout && <>
      <p className="text-sm">Checkout #{checkout.id} · {checkout.state === 'committed' ? 'Completed' : words(checkout.state)}{checkout.sales_order_id ? ` · Sales order #${checkout.sales_order_id}` : ''}</p>
      {invoice ? <><dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">{[['Whole checkout total', invoice.total], ['Paid on checkout invoice', invoice.paid], ['Checkout balance', invoice.balance]].map(([label, value]) => <div key={String(label)}><dt className="text-xs text-muted-foreground">{label}</dt><dd className="font-semibold">{money(value)}</dd></div>)}</dl><p className="text-sm">Invoice {invoice.number} · {words(invoice.status)}</p></> : <p className="text-sm">An invoice is not available for this checkout.</p>}
      <Button className="justify-self-start" variant="outline" disabled={pending || query.isFetching} onClick={async () => { await query.refetch(); if (owns()) onChanged(); }}>Reload checkout payments</Button>
      {authorizedCollection && invoice && ((Number(invoice.balance) > 0 && !['cancelled', 'voided'].includes(invoice.status)) || attempt.current) && <form className="grid gap-3 rounded border p-3" aria-label="Collect checkout payment" onSubmit={event => { event.preventDefault(); collect(); }}>
        <h4 className="font-medium">Record checkout payment received</h4>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-sm">Amount<Input aria-label="Checkout payment amount" inputMode="decimal" required maxLength={30} value={amount} disabled={pending || unknown} onChange={event => setAmount(event.target.value)}/></label>
          <label className="text-sm">Method<NativeSelect aria-label="Checkout payment method" className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={method} disabled={pending || unknown} onChange={event => setMethod(event.target.value)}>{['cash', 'card', 'bank_transfer', 'upi'].map(value => <option key={value} value={value}>{words(value)}</option>)}</NativeSelect></label>
          <label className="text-sm">Reference<Input aria-label="Checkout payment reference" maxLength={120} value={reference} disabled={pending || unknown} onChange={event => setReference(event.target.value)}/></label>
        </div>
        <p className="text-xs text-muted-foreground">Record money already received. This does not charge a card or initiate a bank or UPI transfer.</p>
        {validation && <p role="alert" className="text-sm">{validation}</p>}
        <Button className="justify-self-start" type="submit" disabled={pending || query.isFetching || query.isError}>{pending ? 'Recording…' : unknown ? 'Retry same payment' : 'Record checkout payment'}</Button>
      </form>}
      <section aria-label="Checkout receipts"><h4 className="font-medium">Receipts</h4>{!checkout.receipts.length ? <p className="text-sm text-muted-foreground">No receipts recorded for this checkout.</p> : <ul className="grid gap-2">{checkout.receipts.map(receipt => <li key={receipt.id} className="rounded border p-3 text-sm"><strong>{receipt.number}</strong><p>{money(receipt.amount)} · {words(receipt.method)} · {words(receipt.status)}</p>{receipt.reference && <p>Reference: {receipt.reference}</p>}<p className="text-xs text-muted-foreground">Unallocated on receipt: {money(receipt.unallocated)}</p></li>)}</ul>}</section>
    </>}
    {unknown && !pending && <p role="status" className="text-sm">Payment outcome is unresolved. The original amount, method and reference are locked until the same payment is confirmed or rejected. Missing receipts alone do not confirm rejection.</p>}
    {capabilities.isError && <p role="alert">Payment permissions could not be verified. <Button variant="outline" onClick={()=>void capabilities.refetch()}>Reload payment permissions</Button></p>}
    {notice && <p role="status" className="text-sm">{notice}</p>}
    {mutation.isError && <p role="alert" className="text-sm">{dealError(mutation.error)}{attempt.current && ' If the outcome is uncertain, reload receipts or retry the same payment details. A retry of unchanged details uses the same payment key.'}</p>}
  </section>;
}
