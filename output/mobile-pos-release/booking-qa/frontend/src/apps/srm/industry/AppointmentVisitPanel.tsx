import MobileWorkflowPages from "../components/MobileWorkflowPages";
import { bookingLabel, validZone } from "@/shared/scheduling/booking-view";
import { PaymentAmounts } from "@/shared/scheduling/BookingUX";
import { defaultText } from "@/lib/form-defaults";
import { useRef, useState, type ReactNode } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { api } from '@/services/api';
import { useBusinessTerms } from '@/hooks/use-business-terms';
import { masterScope } from '@/shared/master-data/CompanySelect';
import { dealError } from '@/apps/crm/deals/deal-utils';
import ServiceCheckoutBillingPanel from './ServiceCheckoutBillingPanel';

type Visit = { id: number; title: string; status: string; revision: number; customer_id?: number; data: Record<string, string | number | number[]> };
type Billing = { revision: number; currency: string; total: string | number; paid: string | number; advance: string | number; balance: string | number;
  invoice: { id: number; number: string; status: string; balance: string | number } | null;
  receipts: { id: number; number: string; amount: string | number; status: string; method: string; reference?: string }[] };
type GroupBilling = { revision: number; group_checkout: { id: number; line_id: number; service_charge: string } };

export default function AppointmentVisitPanel({ row, canViewBilling, canCollect, canInvoice, canApprove, actions, onChanged, providers = [], triggerLabel, timezone, defaultOpen = false, onClosed }: {
  row: Visit; canViewBilling: boolean; canCollect: boolean; canInvoice: boolean; canApprove: boolean;
  actions?: ReactNode; onChanged: () => void; providers?: string[]; timezone?:string; triggerLabel?: string; defaultOpen?: boolean; onClosed?:()=>void;
}) {
  const { term } = useBusinessTerms();
  const zone=validZone(timezone || defaultText('timezone','srm'));
  const [open, setOpen] = useState(defaultOpen);
  const [amount, setAmount] = useState(''), [method, setMethod] = useState('cash'), [reference, setReference] = useState('');
  const [notice, setNotice] = useState('');
  const request = useRef(crypto.randomUUID());
  const root = `/srm/industry/appointments/${row.id}`;
  const query = useQuery({ queryKey: ['appointment-billing', masterScope(), row.id, row.revision], enabled: open && canViewBilling,
    queryFn: async () => (await api.get<Billing | GroupBilling>(root + '/billing',{recordCache:false})).data, retry: false });
  const mutation = useMutation({ mutationFn: async (action: 'payment' | 'invoice' | 'approve' | 'apply') => {
    const billing = query.data;
    if (billing && 'group_checkout' in billing) throw new Error('Use the linked checkout for this service invoice and payment.');
    if (action === 'payment') return (await api.post(root + '/payments', { request_id: request.current, expected_revision: billing?.revision ?? row.revision, amount, payment_method: method, reference_number: reference })).data;
    if (action === 'invoice') return (await api.post(`/srm/industry/records/${row.id}/invoice`, { expected_revision: billing?.revision ?? row.revision })).data;
    if (action === 'approve' && billing?.invoice) return (await api.post(`/srm/invoices/${billing.invoice.id}/approve`)).data;
    if (action === 'apply') return (await api.post(root + '/apply-advances', { expected_revision: billing?.revision ?? row.revision })).data;
    throw new Error('Refresh the visit before continuing.');
  }, onMutate: () => setNotice(''), onSuccess: async (_, action) => {
    if (action === 'payment') { request.current = crypto.randomUUID(); setAmount(''); setReference(''); }
    setNotice(action === 'payment' ? 'Payment recorded.' : action === 'apply' ? 'Advance applied to the invoice.' : action === 'invoice' ? 'Invoice draft created.' : 'Invoice approved.');
    onChanged(); await query.refetch();
  } });
  const grouped = query.data && 'group_checkout' in query.data ? query.data : undefined;
  const billing = query.data && !('group_checkout' in query.data) ? query.data : undefined, pending = mutation.isPending;
  const money = (value: string | number) => `${billing?.currency || row.data.currency || ''} ${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return <><Button size="sm" variant="outline" onClick={() => setOpen(true)}>{triggerLabel || 'Open visit & payments'}</Button><Dialog open={open} onOpenChange={value => { if (!pending) {setOpen(value);if(!value)onClosed?.();} }}><DialogContent className="mobile-workflow-dialog max-h-[90vh] max-w-3xl overflow-y-auto">
    <DialogHeader><DialogTitle>{[row.data.service_name,row.data.customer_name].filter(Boolean).join(' · ')||row.title}</DialogTitle><DialogDescription>{term('appointment')} details, scheduling and payments.</DialogDescription></DialogHeader>
    <MobileWorkflowPages><section className="grid gap-2 text-sm" aria-label="Visit details"><p><strong>{term('customer')}:</strong> {row.data.customer_name || `#${row.customer_id ?? row.id}`}</p><p><strong>{term('service')}:</strong> {row.data.service_name}</p>{providers.length > 0 && <p><strong>{term('provider', true)} / {term('resource', true)}:</strong> {providers.join(', ')}</p>}<p>{`${bookingLabel(String(row.data.starts_at),zone)} – ${bookingLabel(Date.parse(String(row.data.starts_at))+Number(row.data.duration_minutes)*60000,zone,false)} (${zone})`} · {row.data.duration_minutes} min</p><p><strong>Visit status:</strong> {row.status.replace(/_/g, ' ')}</p>{row.data.notes && <p>{String(row.data.notes)}</p>}{actions}</section>
    {canViewBilling && <section className="mt-5 grid gap-4 border-t pt-4" aria-label="Visit payments"><h3 className="font-semibold">Charges & payments</h3>
      {query.isPending && <p role="status">Loading payments…</p>}{query.isError && <p role="alert">{dealError(query.error)} <Button variant="outline" onClick={() => void query.refetch()}>Retry payments</Button></p>}
      {grouped && <ServiceCheckoutBillingPanel checkoutId={grouped.group_checkout.id} serviceCharge={grouped.group_checkout.service_charge} canCollect={canCollect} onChanged={() => { onChanged(); void query.refetch(); }}/>}
      {billing && <><PaymentAmounts value={{currency:billing.currency,total:billing.total,paid:Number(billing.paid)+Number(billing.advance),balance:billing.balance}}/>{Number(billing.advance)>0 && <small>Includes {money(billing.advance)} advance held.</small>}
        <p className="text-sm">Invoice: {billing.invoice ? `${billing.invoice.number} · ${billing.invoice.status.replace(/_/g, ' ')}` : 'Not created yet'}. Visit and payment statuses are tracked separately.</p>
        <div className="flex flex-wrap gap-2">{!billing.invoice && row.status === 'completed' && canInvoice && <Button disabled={pending} onClick={() => mutation.mutate('invoice')}>Create invoice draft</Button>}{billing.invoice && ['draft', 'pending_approval'].includes(billing.invoice.status) && canApprove && <Button disabled={pending} onClick={() => mutation.mutate('approve')}>Approve invoice</Button>}{billing.invoice && !['draft', 'pending_approval', 'cancelled'].includes(billing.invoice.status) && Number(billing.advance) > 0 && Number(billing.invoice.balance) > 0 && canCollect && <Button disabled={pending} onClick={() => mutation.mutate('apply')}>Apply advance to invoice</Button>}<Button variant="outline" disabled={pending || query.isFetching} onClick={() => { onChanged(); void query.refetch(); }}>Refresh payments</Button></div>
        {['cancelled', 'no_show'].includes(row.status) && Number(billing.advance) > 0 && <p className="text-sm">The advance remains on the customer account. Cancellation does not automatically refund or forfeit it.</p>}
        {canCollect && !['cancelled', 'no_show'].includes(row.status) && billing.invoice?.status !== 'cancelled' && Number(billing.balance) > 0 && <form className="grid gap-3 rounded border p-3" aria-label="Collect visit payment" onSubmit={event => { event.preventDefault(); setNotice(''); mutation.mutate('payment'); }}><h4 className="font-medium">Record payment received</h4><div className="grid gap-3 sm:grid-cols-3"><label className="text-sm">Amount<Input type="number" aria-label="Payment amount" min="0.01" step="0.01" max={Number(billing.balance)} required value={amount} disabled={pending} onChange={event => setAmount(event.target.value)}/></label><label className="text-sm">Method<select className="w-full rounded border bg-background p-2" aria-label="Payment method" value={method} disabled={pending} onChange={event => setMethod(event.target.value)}>{['cash', 'upi', 'card', 'bank_transfer', 'cheque', 'other'].map(value => <option key={value} value={value}>{value.replace(/_/g, ' ')}</option>)}</select></label><label className="text-sm">Reference<Input aria-label="Payment reference" maxLength={120} value={reference} disabled={pending} onChange={event => setReference(event.target.value)}/></label></div><p className="text-xs text-muted-foreground">Record money already received by cash, UPI, card or bank. This action does not charge a card or initiate a transfer.</p><Button type="submit" disabled={pending}>{pending ? 'Recording…' : 'Record payment'}</Button></form>}
        {!!billing.receipts.length && <section aria-label="Payment receipts"><h4 className="font-medium">Receipts</h4><ul className="grid gap-2">{billing.receipts.map(receipt => <li key={receipt.id} className="rounded border p-2 text-sm"><strong>{receipt.number}</strong><p>{money(receipt.amount)} · {receipt.method} · {receipt.status.replace(/_/g, ' ')}</p>{receipt.reference && <p>{receipt.reference}</p>}</li>)}</ul></section>}
      </>}
      {notice && <p role="status">{notice}</p>}{mutation.isError && <p role="alert">{dealError(mutation.error)} Retry the same payment details if its outcome is uncertain.</p>}
    </section>}
  </MobileWorkflowPages></DialogContent></Dialog></>;
}
