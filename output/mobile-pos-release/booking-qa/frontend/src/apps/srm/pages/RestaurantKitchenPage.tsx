import { useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { api } from '@/services/api';
import { useAuthStore } from '@/store/authStore';
import { useRecordScope, recordScope } from '@/lib/record-scope';
import { useRecordScopeOwner } from '@/hooks/use-record-scope-owner';
import { selectedPackContext } from '@/lib/pack-context';
import { selectedBranch } from '@/lib/branch-context';
import { effectiveOperationalSelection } from '@/lib/effective-operational-selection';
import { securityAuthStamp } from '@/lib/security-auth-stamp';
import { catalogError } from '@/shared/catalog/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import GridTable from '@/shared/data-grid/GridTable';

type DiningTable = { id: number; name: string; capacity: number; revision: number; active: boolean; occupied: boolean };
type Item = { sales_order_line_id: number; item: string; quantity: string; sent_quantity?: string; unit_price?: string; line_total?: string };
type SplitBill = { bill_id: number; invoice_id: number; number: string; total: string; paid: string; balance: string; currency: string; items: { sales_order_line_id: number; quantity: string; total: string }[] };
type SplitBills = { order_id: number; order_revision: number; bills: SplitBill[] };
type Ticket = { id: number; service_order_id: number; state: string; revision: number; items: { id: number; item: string; quantity: string; instruction: string }[] };
type Order = { id: number; table_id: number | null; state: string; revision: number; billing_state: 'paid_pos' | 'unpaid_tab' | 'billed_tab'; customer_assigned?: boolean; currency?: string; total?: string; items: Item[]; tickets: Ticket[] };
type Reservation = { id: number; revision: number; state: string; table_id: number; party_size: number; starts_at: string; ends_at: string; customer_id: number | null; notes: string; order_id: number | null };
type Billing = { order_id: number; checkout: null | { id: number; revision: number; invoice: { number: string; total: string; paid: string; balance: string; currency: string }; receipts: { id: number }[] } };
type ModifierChoice = { group: string; product_id: number; quantity: number; expected_unit_price: string };
type MenuItem = { id: number; name: string; price: string; currency: string; modifier_groups?: { key: string; label: string; min_choices: number; max_choices: number; options: { product_id: number; name: string; price: string; max_quantity: number }[] }[] };
type Caps = Record<'tables_view' | 'tables_manage' | 'orders_view' | 'orders_create' | 'orders_serve' | 'kitchen_view' | 'kitchen_prepare' | 'kitchen_ready' | 'billing_view' | 'billing_prepare' | 'payments_record' | 'anonymous_settle' | 'reports_view' | 'reservations_schedule' | 'orders_remove' | 'sessions_close', boolean>;
type Tender = { payment_key: string; method: 'cash' | 'card' | 'upi' | 'bank_transfer'; amount: string };
type Source = { checkout_id: number; checkout_revision: number; lines: Item[] };
const positive = (value: string) => /^[1-9][0-9]*$/.test(value) && Number.isSafeInteger(Number(value));
const cents = (value: string) => { const match = /^(\d+)(?:\.(\d+))?$/.exec(value), fraction = (match?.[2] || '').replace(/0+$/, ''); return match && fraction.length <= 2 ? BigInt(match[1]) * 100n + BigInt(fraction.padEnd(2, '0')) : null; };
const tender = (): Tender => ({ payment_key: crypto.randomUUID(), method: 'cash', amount: '' });

const decimal = (value: bigint) => `${value / 100n}.${String(value % 100n).padStart(2, '0')}`;
const rounded = (value: bigint, divisor: bigint) => (value * 2n + divisor) / (divisor * 2n);
function quoteSplit(items: Item[], bills: SplitBill[], quantities: Record<number, string>) {
  const lines: { sales_order_line_id: number; quantity: string }[] = [];
  let total = 0n;
  for (const item of items) {
    const raw = quantities[item.sales_order_line_id] || '0', selected = cents(raw.startsWith('.') ? `0${raw}` : raw);
    if (selected === null) return null;
    if (selected === 0n) continue;
    const original = cents(item.quantity), price = cents(item.unit_price || ''), amount = cents(item.line_total || '');
    if (original === null || original <= 0n || price === null || amount === null) return null;
    let used = 0n, usedGross = 0n, usedTax = 0n;
    for (const part of bills.flatMap(bill => bill.items).filter(row => row.sales_order_line_id === item.sales_order_line_id)) {
      const quantity = cents(part.quantity), value = cents(part.total);
      if (quantity === null || value === null) return null;
      const gross = rounded(quantity * price, 100n);
      used += quantity; usedGross += gross; usedTax += value - gross;
    }
    if (used + selected > original) return null;
    const gross = rounded(selected * price, 100n), originalGross = rounded(original * price, 100n);
    if (usedGross + gross + rounded((original - used - selected) * price, 100n) !== originalGross) return null;
    const tax = rounded((amount - originalGross) * (used + selected), original) - usedTax;
    if (tax < 0n || amount < originalGross) return null;
    total += gross + tax;
    lines.push({ sales_order_line_id: item.sales_order_line_id, quantity: decimal(selected) });
  }
  return lines.length && total > 0n ? { lines, total: decimal(total) } : null;
}

/** Reuses existing UI components. The selected context is verified before private queries mount. */
export default function RestaurantKitchenPage() {
  const scope = useRecordScope();
  const [mount] = useState(() => crypto.randomUUID());
  const identity = useQuery({ queryKey: ['restaurant-identity', scope, mount], retry: false, staleTime: 0, gcTime: 0, refetchOnWindowFocus: false,
    queryFn: async ({ signal }) => {
      const user = useAuthStore.getState().user, owner = recordScope(user), selector = selectedPackContext();
      const config = { recordCache: false as const, signal, headers: { 'X-Suite-Pack-Context': selector } };
      const [identity, access, operational] = await Promise.all([api.get('/auth/me', config), api.get('/access/me', config), api.get('/srm/restaurant/capabilities', config)]);
      if (owner !== recordScope(useAuthStore.getState().user)) throw new Error('Restaurant context changed. Reload before continuing.');
      const role = typeof identity.data.role === 'string' ? identity.data.role : identity.data.role?.name || null;
      const fresh = { ...user, ...identity.data, role, primary_role: role, access: access.data };
      if (securityAuthStamp(fresh) !== securityAuthStamp(user)) throw new Error('Your access changed. Reload before continuing.');
      const selection = effectiveOperationalSelection(operational.data?.operational_scope, fresh, selectedBranch(), selector);
      if (selection.pack_key !== 'restaurant' || !selection.context_id) throw new Error('Select an authorized Restaurant workspace.');
      return selection.context_id;
    } });
  if (!identity.data || identity.isError) return <Card><CardContent className="space-y-3 pt-4"><p role={identity.isError ? 'alert' : 'status'}>{identity.isError ? catalogError(identity.error) : 'Verifying restaurant access…'}</p>{identity.isError && <Button onClick={() => window.location.reload()}>Reload access</Button>}</CardContent></Card>;
  return <RestaurantWorkspace key={`${scope}:${mount}`} context={identity.data} />;
}

function RestaurantWorkspace({ context }: { context: number }) {
  const scope = useRecordScope(), owns = useRecordScopeOwner(), [params] = useSearchParams(), navigate = useNavigate();
  const [mount] = useState(() => crypto.randomUUID());
  const [checkout, setCheckout] = useState(params.get('checkout') || ''), [table, setTable] = useState('');
  const [orderId, setOrderId] = useState(''), [tableName, setTableName] = useState(''), [capacity, setCapacity] = useState('4');
  const [quantities, setQuantities] = useState<Record<number, string>>({}), [instructions, setInstructions] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [locked, setLocked] = useState(false);
  const [tabMode, setTabMode] = useState('new'), [tabTable, setTabTable] = useState(''), [currency, setCurrency] = useState('INR');
  const [menuSearch, setMenuSearch] = useState(''), [menuSelection, setMenuSelection] = useState(''), [menuQuantity, setMenuQuantity] = useState('1');
  const [cart, setCart] = useState<{ key: string; item: MenuItem; quantity: string; modifiers: ModifierChoice[] }[]>([]);
  const [modifierQuantities, setModifierQuantities] = useState<Record<string, number>>({});
  const [destination, setDestination] = useState('');
  const [removeIds, setRemoveIds] = useState<number[]>([]), [removeReason, setRemoveReason] = useState('');
  const selectOrder = (value: string) => { setOrderId(value); setRemoveIds([]); setRemoveReason(''); setSplitQuantities({}); setSplitBill(''); setPaymentAmount(''); setPaymentKey(crypto.randomUUID()); };
  const [reservationEdit, setReservationEdit] = useState<Reservation | null>(null), [reservationTable, setReservationTable] = useState(''), [reservationCustomer, setReservationCustomer] = useState('');
  const [reservationStart, setReservationStart] = useState(''), [partySize, setPartySize] = useState('2'), [reservationMinutes, setReservationMinutes] = useState('60'), [reservationNotes, setReservationNotes] = useState('');
  const [reportDay, setReportDay] = useState(() => new Date().toLocaleDateString('en-CA'));

  const [customerSearch, setCustomerSearch] = useState(''), [customer, setCustomer] = useState('');
  const [assignmentCustomer, setAssignmentCustomer] = useState('');
  const [register, setRegister] = useState(''), [paymentAmount, setPaymentAmount] = useState(''), [paymentMethod, setPaymentMethod] = useState('cash');
  const [paymentKey, setPaymentKey] = useState(() => crypto.randomUUID());
  const [splitQuantities, setSplitQuantities] = useState<Record<number, string>>({}), [splitBill, setSplitBill] = useState('');
  const [billingMode, setBillingMode] = useState('named'), [anonymousPayments, setAnonymousPayments] = useState<Tender[]>(() => [tender()]);
  const attempts = useRef(new Map<string, { fingerprint: string; key: string }>());
  const config = { recordCache: false as const, headers: { 'X-Suite-Pack-Context': String(context) } };
  const assertOwner = () => { if (!owns()) throw new Error('Restaurant context changed. Reopen this workspace.'); };
  const caps = useQuery({ queryKey: ['restaurant-caps', scope, context, mount], retry: false, staleTime: 0, gcTime: 0, refetchOnWindowFocus: false,
    queryFn: async ({ signal }) => { assertOwner(); const result = await api.get<Caps>('/srm/restaurant/capabilities', { ...config, signal }); assertOwner(); return result.data; } });
  const summary = useQuery({ queryKey: ['restaurant-summary', scope, context, mount, reportDay], enabled: !locked && !!caps.data?.reports_view && !!reportDay, retry: false,
    queryFn: async ({ signal }) => { assertOwner(); const result = await api.get<{ orders_opened: number; tickets_created: number; reservations_starting: number; orders: Record<string, number>; tickets: Record<string, number> }>('/srm/restaurant/daily-summary', { ...config, signal, params: { day: reportDay, timezone_name: Intl.DateTimeFormat().resolvedOptions().timeZone } }); assertOwner(); return result.data; } });
  const reservations = useInfiniteQuery({ queryKey: ['restaurant-reservations', scope, context, mount], initialPageParam: 0,
    enabled: !locked && !!caps.data?.reservations_schedule, retry: false,
    queryFn: async ({ pageParam, signal }) => { assertOwner(); const response = await api.get<{ items: Reservation[]; next: number | null }>('/srm/restaurant/reservations', { ...config, signal, params: { after: pageParam } }); assertOwner(); return response.data; },
    getNextPageParam: page => page.next ?? undefined });
  const tables = useQuery({ queryKey: ['restaurant-tables', scope, context, mount], enabled: !locked && !!(caps.data?.tables_view || caps.data?.tables_manage), retry: false,
    queryFn: async ({ signal }) => { assertOwner(); const result = await api.get<{ items: DiningTable[] }>('/srm/restaurant/tables', { ...config, signal }); assertOwner(); return result.data; } });
  const source = useQuery({ queryKey: ['restaurant-source', scope, context, mount, checkout], enabled: !locked && !!caps.data?.orders_create && positive(checkout), retry: false,
    queryFn: async ({ signal }) => { assertOwner(); const result = await api.get<Source>(`/srm/restaurant/paid-orders/${checkout}/source`, { ...config, signal }); assertOwner(); return result.data; } });
  const order = useQuery({ queryKey: ['restaurant-order', scope, context, mount, orderId], enabled: !locked && !!(caps.data?.orders_view || caps.data?.orders_create) && positive(orderId), retry: false,
    queryFn: async ({ signal }) => { assertOwner(); const result = await api.get<Order>(`/srm/restaurant/orders/${orderId}`, { ...config, signal }); assertOwner(); return result.data; } });
  const menuCurrency = tabMode === 'add' ? order.data?.currency || currency : currency;
  const menu = useInfiniteQuery({ queryKey: ['restaurant-menu', scope, context, mount, menuSearch, menuCurrency], initialPageParam: 0,
    enabled: !locked && !!caps.data?.orders_create && /^[A-Z]{3}$/.test(menuCurrency) && (tabMode === 'new' || order.data?.billing_state === 'unpaid_tab'), retry: false,
    queryFn: async ({ pageParam, signal }) => { assertOwner(); const result = await api.get<{ items: MenuItem[]; next: number | null }>('/srm/restaurant/menu', { ...config, signal, params: { search: menuSearch, currency: menuCurrency, after: pageParam, limit: 30 } }); assertOwner(); return result.data; },
    getNextPageParam: page => page.next ?? undefined });
  const activeTabs = useInfiniteQuery({ queryKey: ['restaurant-active-tabs', scope, context, mount], initialPageParam: 0,
    enabled: !locked && !!(caps.data?.orders_view || caps.data?.orders_create), retry: false,
    queryFn: async ({ pageParam, signal }) => { assertOwner(); const result = await api.get<{ items: { id: number; table_id: number | null; revision: number; state: string }[]; next: number | null }>('/srm/restaurant/tabs', { ...config, signal, params: { after: pageParam, limit: 30 } }); assertOwner(); return result.data; },
    getNextPageParam: page => page.next ?? undefined });
  const kitchen = useQuery({ queryKey: ['restaurant-kitchen', scope, context, mount], enabled: !locked && !!caps.data?.kitchen_view, retry: false,
    queryFn: async ({ signal }) => { assertOwner(); const result = await api.get<{ items: Ticket[] }>('/srm/restaurant/kitchen', { ...config, signal }); assertOwner(); return result.data; } });
  const customers = useInfiniteQuery({ queryKey: ['restaurant-customers', scope, context, mount, customerSearch], initialPageParam: 0,
    enabled: !locked && !!caps.data?.orders_create && (caps.data.reservations_schedule || tabMode === 'new' || (order.data?.billing_state === 'unpaid_tab' && order.data.customer_assigned === false)), retry: false,
    queryFn: async ({ pageParam, signal }) => { assertOwner(); const result = await api.get<{ items: { id: number; name: string }[]; next: number | null }>('/srm/restaurant/customers', { ...config, signal, params: { search: customerSearch, after: pageParam } }); assertOwner(); return result.data; },
    getNextPageParam: page => page.next ?? undefined });
  const billing = useQuery({ queryKey: ['restaurant-billing', scope, context, mount, orderId], enabled: !locked && !!caps.data?.billing_view && positive(orderId) && !!order.data && order.data.billing_state !== 'paid_pos', retry: false,
    queryFn: async ({ signal }) => { assertOwner(); const result = await api.get<Billing>(`/srm/restaurant/tabs/${orderId}/billing`, { ...config, signal }); assertOwner(); return result.data; } });
  const bills = useQuery({ queryKey: ['restaurant-split-bills', scope, context, mount, orderId], enabled: !locked && !!caps.data?.billing_view && positive(orderId) && !!order.data && order.data.billing_state !== 'paid_pos', retry: false, staleTime: 0, gcTime: 0, refetchOnWindowFocus: false,
    queryFn: async ({ signal }) => { assertOwner(); const result = await api.get<SplitBills>(`/srm/restaurant/tabs/${orderId}/bills`, { ...config, signal }); assertOwner(); if (result.data.order_id !== Number(orderId)) throw new Error('Restaurant bill source changed. Reload this tab.'); return result.data; } });
  const registers = useInfiniteQuery({ queryKey: ['restaurant-registers', scope, context, mount], initialPageParam: 0,
    enabled: !locked && !!(caps.data?.billing_prepare || caps.data?.payments_record) && !!order.data && order.data.billing_state !== 'paid_pos', retry: false,
    queryFn: async ({ pageParam, signal }) => { assertOwner(); const result = await api.get<{ items: { id: number; label: string }[]; next: number | null }>('/srm/restaurant/registers', { ...config, signal, params: { after: pageParam } }); assertOwner(); return result.data; },
    getNextPageParam: page => page.next ?? undefined });
  const anonymousMode = billingMode === 'anonymous' && !!caps.data?.anonymous_settle && order.data?.billing_state === 'unpaid_tab' && order.data.customer_assigned === false;
  const counter = useQuery({ queryKey: ['restaurant-anonymous-configuration', scope, context, mount], enabled: !locked && anonymousMode, retry: false,
    queryFn: async ({ signal }) => { assertOwner(); const result = await api.get<{ configured: boolean; enabled: boolean }>('/srm/anonymous-cash/configuration', { ...config, signal }); assertOwner(); return result.data; } });
  const fullAmount = cents(order.data?.total || ''), tenderAmounts = anonymousPayments.map(row => cents(row.amount));
  const fullTender = fullAmount !== null && fullAmount > 0n && tenderAmounts.every(value => value !== null && value > 0n)
    && tenderAmounts.reduce<bigint>((sum, value) => sum + (value || 0n), 0n) === fullAmount;
  const denied = [reservations, summary, caps, tables, source, order, kitchen, menu, activeTabs, customers, billing, bills, registers, counter].some(query => query.isError && isAxiosError(query.error) && query.error.response?.status === 403);
  const splitRows = bills.data?.bills || [], splitQuote = quoteSplit(order.data?.items || [], splitRows, splitQuantities);
  const selectedBill = splitRows.find(row => String(row.bill_id) === splitBill) || splitRows.find(row => (cents(row.balance) || 0n) > 0n) || splitRows[0];
  function refreshPrivate() {
    if (caps.data?.tables_view || caps.data?.tables_manage) void tables.refetch();
    if ((caps.data?.orders_view || caps.data?.orders_create) && positive(orderId)) void order.refetch();
    if (caps.data?.orders_view || caps.data?.orders_create) void activeTabs.refetch();
    if (caps.data?.kitchen_view) void kitchen.refetch();
    if (caps.data?.reports_view) void summary.refetch();
    if (caps.data?.reservations_schedule) void reservations.refetch();
    if (caps.data?.billing_view && positive(orderId) && order.data && order.data.billing_state !== 'paid_pos') { void billing.refetch(); void bills.refetch(); void registers.refetch(); }
  }
  async function send<T>(action: string, path: string, payload: Record<string, unknown>, complete?: (value: T) => void, method: 'post' | 'put' = 'post') {
    if (busy || locked) return;
    const fingerprint = JSON.stringify({ path, method, payload }), old = attempts.current.get(action);
    const attempt = old?.fingerprint === fingerprint ? old : { fingerprint, key: crypto.randomUUID() };
    attempts.current.set(action, attempt); setBusy(true); setError('');
    try {
      assertOwner(); const response = method === 'put' ? await api.put<T>(path, { ...payload, request_key: attempt.key }, config) : await api.post<T>(path, { ...payload, request_key: attempt.key }, config); assertOwner();
      attempts.current.delete(action); complete?.(response.data);
      refreshPrivate();
    } catch (failure) {
      if (!owns()) return;
      setError(catalogError(failure));
      if (isAxiosError(failure) && failure.response?.status === 403) setLocked(true);
    } finally { if (owns()) setBusy(false); }
  }
  if (locked || denied || caps.isError) return <Card><CardContent className="space-y-3 pt-4"><p role="alert">{error || catalogError(caps.error) || 'Restaurant access changed. Reload before continuing.'}</p><Button onClick={() => window.location.reload()}>Reload restaurant access</Button></CardContent></Card>;
  if (!caps.data) return <p role="status">Loading restaurant actions…</p>;
  const ticketCard = (ticket: Ticket) => <Card key={ticket.id} className="min-w-0"><CardHeader><CardTitle className="text-base">Ticket {ticket.id} · {ticket.state}</CardTitle></CardHeader><CardContent className="space-y-3">
    <ul className="space-y-2">{ticket.items.map(item => <li key={item.id}><span>{item.quantity} × {item.item}</span>{item.instruction && <p className="break-words text-sm text-muted-foreground">{item.instruction}</p>}</li>)}</ul>
    <div className="flex flex-wrap gap-2">{ticket.state === 'queued' && caps.data?.kitchen_prepare && <Button disabled={busy} onClick={() => void send(`prepare:${ticket.id}`, `/srm/restaurant/tickets/${ticket.id}/prepare`, { expected_revision: ticket.revision })}>Start preparation</Button>}
      {ticket.state === 'preparing' && caps.data?.kitchen_ready && <Button disabled={busy} onClick={() => void send(`ready:${ticket.id}`, `/srm/restaurant/tickets/${ticket.id}/ready`, { expected_revision: ticket.revision })}>Mark ready</Button>}
      {ticket.state === 'ready' && caps.data?.orders_serve && <Button disabled={busy} onClick={() => void send(`serve:${ticket.id}`, `/srm/restaurant/tickets/${ticket.id}/serve`, { expected_revision: ticket.revision })}>Mark served</Button>}</div>
  </CardContent></Card>;
  return <div className="min-w-0 space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-xl font-semibold">Restaurant orders & kitchen</h1><div className="flex flex-wrap gap-2">{caps.data.sessions_close && <Button variant="outline" disabled={busy} onClick={() => { if (owns()) navigate('/srm/pos/cashier-closing'); }}>Close register</Button>}<Button variant="outline" disabled={busy} onClick={() => { void caps.refetch(); refreshPrivate(); }}>Refresh</Button></div></div>
    {caps.data.reports_view && <Card><CardHeader><CardTitle className="text-base">Daily operations</CardTitle></CardHeader><CardContent className="space-y-3"><label className="grid gap-1 text-sm">Day<Input type="date" aria-label="Summary day" value={reportDay} onChange={event => setReportDay(event.target.value)} /></label>{summary.isError ? <p role="alert">{catalogError(summary.error)}</p> : summary.data && <><p>{summary.data.orders_opened} orders opened · {summary.data.tickets_created} tickets created · {summary.data.reservations_starting} reservations starting</p><p className="text-sm">Tickets: {Object.entries(summary.data.tickets).map(([state, count]) => `${state}: ${count}`).join(' · ') || 'None'}</p><p className="text-xs text-muted-foreground">Current state of records created on the selected local day.</p></>}</CardContent></Card>}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {(caps.data.tables_view || caps.data.tables_manage) && <Card><CardHeader><CardTitle className="text-base">Tables</CardTitle></CardHeader><CardContent className="min-w-0 space-y-3">
      {caps.data.tables_manage && <form className="flex flex-wrap items-end gap-2" onSubmit={event => { event.preventDefault(); void send('table.create', '/srm/restaurant/tables', { name: tableName, capacity: Number(capacity) }, () => setTableName('')); }}>
        <label className="grid min-w-0 gap-1 text-sm">Table name<Input required maxLength={80} value={tableName} onChange={event => setTableName(event.target.value)} /></label><label className="grid min-w-0 gap-1 text-sm">Seats<Input required type="number" min={1} max={1000} value={capacity} onChange={event => setCapacity(event.target.value)} /></label><Button disabled={busy}>Add table</Button></form>}
      {tables.isError ? <p role="alert">{catalogError(tables.error)}</p> : <div className="overflow-x-auto"><GridTable gridId="apps/srm/restaurant/tables" className="w-full text-left text-sm"><thead><tr><th className="px-3 py-2">Table</th><th className="px-3 py-2">Seats</th><th className="px-3 py-2">Status</th></tr></thead><tbody>{tables.data?.items.map(row => <tr key={row.id} className="border-t"><td className="px-3 py-2">{row.name}</td><td className="px-3 py-2">{row.capacity}</td><td className="px-3 py-2">{!row.active ? 'Inactive' : row.occupied ? 'Occupied' : 'Available'}</td></tr>)}</tbody></GridTable></div>}
    </CardContent></Card>}
    {caps.data.reservations_schedule && <Card><CardHeader><CardTitle className="text-base">Table reservations</CardTitle></CardHeader><CardContent className="space-y-3">
      <form className="grid min-w-0 gap-3 sm:grid-cols-2" onSubmit={event => { event.preventDefault(); const selected = tables.data?.items.find(row => String(row.id) === reservationTable); if (!selected || !reservationStart) return; void send('reservation.save', reservationEdit ? `/srm/restaurant/reservations/${reservationEdit.id}` : '/srm/restaurant/reservations', { table_id: selected.id, expected_table_revision: selected.revision, party_size: Number(partySize), starts_at: new Date(reservationStart).toISOString(), duration_minutes: Number(reservationMinutes), notes: reservationNotes, customer_id: positive(reservationCustomer) ? Number(reservationCustomer) : null, ...(reservationEdit ? { expected_revision: reservationEdit.revision } : {}) }, () => { setReservationEdit(null); setReservationStart(''); setReservationNotes(''); }, reservationEdit ? 'put' : 'post'); }}>
        <label className="grid gap-1 text-sm">Reservation table<NativeSelect required className="w-full min-w-0 max-w-full" aria-label="Reservation table" value={reservationTable} onChange={event => setReservationTable(event.target.value)}><option value="">Choose table</option>{tables.data?.items.filter(row => row.active).map(row => <option key={row.id} value={row.id}>{row.name} · {row.capacity} seats</option>)}</NativeSelect></label>
        <label className="grid gap-1 text-sm">Find reservation customer<Input aria-label="Find reservation customer" value={customerSearch} onChange={event => setCustomerSearch(event.target.value)} /></label>
        <label className="grid gap-1 text-sm">Reservation customer<NativeSelect className="w-full min-w-0 max-w-full" aria-label="Reservation customer" value={reservationCustomer} onChange={event => setReservationCustomer(event.target.value)}><option value="">No named customer</option>{customers.data?.pages.flatMap(page => page.items).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</NativeSelect></label>
        <label className="grid gap-1 text-sm">Reservation time<Input required aria-label="Reservation time" type="datetime-local" value={reservationStart} onChange={event => setReservationStart(event.target.value)} /></label>
        <label className="grid gap-1 text-sm">Guests<Input required aria-label="Reservation guests" type="number" min={1} max={1000} value={partySize} onChange={event => setPartySize(event.target.value)} /></label>
        <label className="grid gap-1 text-sm">Duration (minutes)<Input required aria-label="Reservation duration" type="number" min={5} max={720} value={reservationMinutes} onChange={event => setReservationMinutes(event.target.value)} /></label>
        <label className="grid gap-1 text-sm">Reservation notes<Input maxLength={2000} value={reservationNotes} onChange={event => setReservationNotes(event.target.value)} /></label>
        <div className="flex flex-wrap items-end gap-2"><Button disabled={busy || reservations.isFetching}>{reservationEdit ? 'Save reservation schedule' : 'Book table'}</Button>{reservationEdit && <Button type="button" variant="outline" onClick={() => { setReservationEdit(null); setReservationCustomer(''); }}>New reservation</Button>}</div>
      </form>
      {reservations.isError && <p role="alert">{catalogError(reservations.error)}</p>}
      <div className="overflow-x-auto"><GridTable gridId="apps/srm/restaurant/reservations" className="w-full text-left text-sm"><thead><tr><th className="px-3 py-2">Reservation</th><th className="px-3 py-2">Time</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Actions</th></tr></thead><tbody>{reservations.data?.pages.flatMap(page => page.items).map(row => <tr key={row.id} className="border-t"><td className="px-3 py-2">{tables.data?.items.find(table => table.id === row.table_id)?.name || `Table ${row.table_id}`} · {row.party_size} guests</td><td className="px-3 py-2">{new Date(row.starts_at).toLocaleString()}</td><td className="px-3 py-2">{row.state}</td><td className="px-3 py-2">{row.state === 'booked' && <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy || reservations.isFetching} onClick={() => { setReservationEdit(row); setReservationCustomer(row.customer_id ? String(row.customer_id) : ''); setReservationTable(String(row.table_id)); const local = new Date(row.starts_at); local.setMinutes(local.getMinutes() - local.getTimezoneOffset()); setReservationStart(local.toISOString().slice(0, 16)); setPartySize(String(row.party_size)); setReservationMinutes(String(Math.round((Date.parse(row.ends_at) - Date.parse(row.starts_at)) / 60000))); setReservationNotes(row.notes); }}>Reschedule reservation</Button><Button variant="outline" disabled={busy || reservations.isFetching} onClick={() => void send(`reservation.cancel:${row.id}`, `/srm/restaurant/reservations/${row.id}/transition`, { expected_revision: row.revision, status: 'cancelled', reason: 'Cancelled by restaurant operator' })}>Cancel reservation</Button><Button variant="outline" disabled={busy || reservations.isFetching || Date.parse(row.starts_at) > Date.now()} onClick={() => void send(`reservation.no_show:${row.id}`, `/srm/restaurant/reservations/${row.id}/transition`, { expected_revision: row.revision, status: 'no_show' })}>Mark no-show</Button><Button variant="outline" disabled={busy || reservations.isFetching || !order.data || order.data.table_id !== row.table_id || order.data.state !== 'open'} onClick={() => void send(`reservation.seat:${row.id}`, `/srm/restaurant/reservations/${row.id}/transition`, { expected_revision: row.revision, status: 'seated', order_id: order.data!.id })}>Seat at current tab</Button></div>}</td></tr>)}</tbody></GridTable></div>
      {reservations.hasNextPage && <Button variant="outline" onClick={() => void reservations.fetchNextPage()}>More reservations</Button>}
    </CardContent></Card>}
    {(caps.data.orders_view || caps.data.orders_create) && <Card><CardHeader><CardTitle className="text-base">Open tabs</CardTitle></CardHeader><CardContent className="space-y-3">
      {activeTabs.isError ? <p role="alert">{catalogError(activeTabs.error)}</p> : <div className="flex flex-wrap gap-2">{activeTabs.data?.pages.flatMap(page => page.items).map(row => <Button key={row.id} variant="outline" onClick={() => { selectOrder(String(row.id)); setCart([]); setQuantities({}); setInstructions({}); }}>Tab {row.id}{row.table_id ? ` · table ${row.table_id}` : ' · counter'}</Button>)}</div>}
      {activeTabs.hasNextPage && <Button variant="outline" onClick={() => void activeTabs.fetchNextPage()}>More open tabs</Button>}
    </CardContent></Card>}
    {caps.data.orders_create && <Card><CardHeader><CardTitle className="text-base">Open a tab / add items</CardTitle></CardHeader><CardContent className="space-y-3">
      <p className="text-sm text-muted-foreground">Take the order before payment. Stock is issued when items are sent to the kitchen. Serving items keeps an unpaid table open.</p>
      {tabMode === 'new' && <div className="grid min-w-0 gap-3 sm:grid-cols-2"><label className="grid gap-1 text-sm">Find customer<Input aria-label="Find tab customer" value={customerSearch} onChange={event => setCustomerSearch(event.target.value)} /></label><label className="grid gap-1 text-sm">Customer<NativeSelect aria-label="Tab customer" value={customer} onChange={event => setCustomer(event.target.value)}><option value="">Walk-in · customer assignment required before billing</option>{customers.data?.pages.flatMap(page => page.items).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</NativeSelect></label>{customers.hasNextPage && <Button variant="outline" onClick={() => void customers.fetchNextPage()}>More customers</Button>}{customers.isError && <p role="alert">{catalogError(customers.error)}</p>}</div>}
      <fieldset disabled={busy} className="grid min-w-0 gap-3 sm:grid-cols-2">
        <label className="grid min-w-0 gap-1 text-sm">Order action<NativeSelect aria-label="Tab action" value={tabMode} onChange={event => { setTabMode(event.target.value); setCart([]); setMenuSelection(''); }}><option value="new">Open new tab</option><option value="add" disabled={order.data?.billing_state !== 'unpaid_tab' || order.data.state !== 'open'}>Add to current unpaid tab</option></NativeSelect></label>
        {tabMode === 'new' ? <><label className="grid min-w-0 gap-1 text-sm">Currency<Input aria-label="Tab currency" maxLength={3} value={currency} onChange={event => { setCurrency(event.target.value.toUpperCase()); setCart([]); setMenuSelection(''); }} /></label><label className="grid min-w-0 gap-1 text-sm">Table<NativeSelect aria-label="Tab table" className="w-full min-w-0 max-w-full" value={tabTable} onChange={event => setTabTable(event.target.value)}><option value="">Counter / takeaway</option>{tables.data?.items.filter(row => row.active && !row.occupied).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</NativeSelect></label></> : <p className="text-sm">Adding to service order {order.data?.id} · {menuCurrency}</p>}
        <label className="grid min-w-0 gap-1 text-sm">Find menu item<Input aria-label="Find menu item" value={menuSearch} onChange={event => setMenuSearch(event.target.value)} /></label>
        <label className="grid min-w-0 gap-1 text-sm">Menu item<NativeSelect aria-label="Menu item" className="w-full min-w-0 max-w-full" value={menuSelection} onChange={event => { setMenuSelection(event.target.value); setModifierQuantities({}); }}><option value="">Choose menu item</option>{menu.data?.pages.flatMap(page => page.items).map(row => <option key={row.id} value={row.id}>{row.name} · {row.currency} {row.price}</option>)}</NativeSelect></label>
        {menu.data?.pages.flatMap(page => page.items).find(item => String(item.id) === menuSelection)?.modifier_groups?.map(group => <fieldset key={group.key} className="min-w-0 space-y-2 rounded-md border p-3"><legend className="text-sm">{group.label} · choose {group.min_choices}–{group.max_choices}</legend>{group.options.map(option => <label key={option.product_id} className="grid min-w-0 gap-1 text-sm">{option.name} · {menuCurrency} {option.price}<Input aria-label={`${group.label}: ${option.name}`} type="number" min={0} max={option.max_quantity} value={modifierQuantities[`${group.key}:${option.product_id}`] || 0} onChange={event => setModifierQuantities(current => ({ ...current, [`${group.key}:${option.product_id}`]: Number(event.target.value) }))} /></label>)}</fieldset>)}
        <label className="grid min-w-0 gap-1 text-sm">Quantity<Input aria-label="Menu quantity" inputMode="decimal" value={menuQuantity} onChange={event => setMenuQuantity(event.target.value)} /></label>
        <Button type="button" variant="outline" disabled={!menuSelection || !Number.isFinite(Number(menuQuantity)) || Number(menuQuantity) <= 0} onClick={() => { const item = menu.data?.pages.flatMap(page => page.items).find(row => String(row.id) === menuSelection); if (item) setCart(current => [...current, { key: crypto.randomUUID(), item, quantity: menuQuantity, modifiers: (item.modifier_groups || []).flatMap(group => group.options.filter(option => (modifierQuantities[`${group.key}:${option.product_id}`] || 0) > 0).map(option => ({ group: group.key, product_id: option.product_id, quantity: modifierQuantities[`${group.key}:${option.product_id}`], expected_unit_price: option.price }))) }]); }}>Add menu item</Button>
      </fieldset>
      {menu.isError && <p role="alert">{catalogError(menu.error)}</p>}{menu.hasNextPage && <Button variant="outline" disabled={menu.isFetchingNextPage} onClick={() => void menu.fetchNextPage()}>More menu items</Button>}
      <ul className="space-y-2">{cart.map(row => <li key={row.key} className="flex min-w-0 flex-wrap items-center justify-between gap-2"><span className="break-words text-sm">{row.quantity} × {row.item.name} · {row.item.currency} {row.item.price}</span><Button variant="ghost" disabled={busy} onClick={() => setCart(current => current.filter(item => item.key !== row.key))}>Remove item</Button></li>)}</ul>
      <Button disabled={busy || !cart.length || menu.isFetching || (tabMode === 'add' && (order.data?.billing_state !== 'unpaid_tab' || order.data.state !== 'open'))} onClick={() => {
        const lines = cart.map(row => ({ product_id: row.item.id, quantity: row.quantity, expected_unit_price: row.item.price, modifiers: row.modifiers }));
        const selected = tables.data?.items.find(row => String(row.id) === tabTable);
        const path = tabMode === 'add' ? `/srm/restaurant/tabs/${order.data!.id}/items` : '/srm/restaurant/tabs';
        const payload = tabMode === 'add' ? { expected_revision: order.data!.revision, lines } : { currency, lines, ...(positive(customer) ? { customer_id: Number(customer) } : {}), ...(selected ? { table_id: selected.id, expected_table_revision: selected.revision } : {}) };
        void send<Order>(tabMode === 'add' ? `tab.add:${order.data!.id}` : 'tab.create', path, payload, value => { selectOrder(String(value.id)); setCart([]); setQuantities({}); setInstructions({}); });
      }}>{tabMode === 'add' ? 'Add items to tab' : 'Open unpaid tab'}</Button>
      <p className="text-xs text-muted-foreground">Catalog prices and taxes apply when saved. This tab remains unpaid until it is settled.</p>
    </CardContent></Card>}
    {caps.data.orders_create && <Card><CardHeader><CardTitle className="text-base">Send paid order to kitchen</CardTitle></CardHeader><CardContent className="space-y-3">
      <p className="text-sm text-muted-foreground">Use a fully paid POS checkout. Kitchen preparation keeps its existing invoice, payment and stock movement.</p>
      <label className="grid gap-1 text-sm">Paid POS checkout ID<Input inputMode="numeric" value={checkout} onChange={event => setCheckout(event.target.value)} /></label>
      {source.isError && <p role="alert">{catalogError(source.error)}</p>}
      {source.data && !source.isError && <><ul>{source.data.lines.map(row => <li key={row.sales_order_line_id}>{row.quantity} × {row.item}</li>)}</ul><label className="grid min-w-0 gap-1 text-sm">Table<NativeSelect aria-label="Dining table" className="w-full min-w-0 max-w-full" value={table} onChange={event => setTable(event.target.value)}><option value="">Counter / takeaway</option>{tables.data?.items.filter(row => row.active && !row.occupied).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</NativeSelect></label>
        <Button disabled={busy || source.isFetching} onClick={() => { const selected = tables.data?.items.find(row => String(row.id) === table); void send<Order>('order.open', '/srm/restaurant/paid-orders', { checkout_id: source.data!.checkout_id, expected_checkout_revision: source.data!.checkout_revision, ...(selected ? { table_id: selected.id, expected_table_revision: selected.revision } : {}) }, value => { selectOrder(String(value.id)); setQuantities({}); setInstructions({}); }); }}>Open fulfillment order</Button></>}
    </CardContent></Card>}
    {(caps.data.orders_view || caps.data.orders_create) && <Card><CardHeader><CardTitle className="text-base">Service order</CardTitle></CardHeader><CardContent className="space-y-3">
      <label className="grid gap-1 text-sm">Service order ID<Input inputMode="numeric" value={orderId} onChange={event => { selectOrder(event.target.value); setQuantities({}); setInstructions({}); }} /></label>
      {order.isError && <p role="alert">{catalogError(order.error)}</p>}
      {order.data && !order.isError && <><p>Order {order.data.id} · {order.data.state}{order.data.billing_state === 'unpaid_tab' ? ` · unpaid · ${order.data.currency} ${order.data.total}` : ''}</p>
        {caps.data.tables_manage && order.data.table_id != null && order.data.state === 'open' && order.data.billing_state !== 'paid_pos' && <div className="flex flex-wrap items-end gap-2"><label className="grid min-w-0 gap-1 text-sm">Move to table<NativeSelect className="w-full min-w-0 max-w-full" aria-label="Transfer destination" value={destination} onChange={event => setDestination(event.target.value)}><option value="">Choose available table</option>{tables.data?.items.filter(row => row.active && !row.occupied).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</NativeSelect></label><Button variant="outline" disabled={busy || !positive(destination)} onClick={() => { const selected = tables.data?.items.find(row => String(row.id) === destination); if (selected) void send('tab.transfer', `/srm/restaurant/tabs/${orderId}/transfer`, { expected_revision: order.data!.revision, destination_table_id: selected.id, expected_destination_revision: selected.revision }, () => setDestination('')); }}>Transfer tab</Button></div>}
        {caps.data.orders_remove && order.data.state === 'open' && order.data.billing_state === 'unpaid_tab' && <details className="rounded-md border p-3"><summary className="cursor-pointer text-sm">Remove unissued items</summary><div className="mt-3 space-y-3">{order.data.items.filter(row => Number(row.sent_quantity || '0') === 0).map(row => <label key={row.sales_order_line_id} className="flex gap-2 text-sm"><input type="checkbox" aria-label={`Remove ${row.item}`} checked={removeIds.includes(row.sales_order_line_id)} onChange={event => setRemoveIds(current => event.target.checked ? [...current, row.sales_order_line_id] : current.filter(id => id !== row.sales_order_line_id))} />{row.quantity} × {row.item}</label>)}<label className="grid gap-1 text-sm">Removal reason<Input aria-label="Removal reason" maxLength={2000} value={removeReason} onChange={event => setRemoveReason(event.target.value)} /></label><p className="text-xs text-muted-foreground">Select the menu item and all its modifiers together. Keep at least one item on the tab.</p><Button variant="outline" disabled={busy || !removeIds.length || !removeReason.trim()} onClick={() => void send('tab.remove', `/srm/restaurant/tabs/${orderId}/remove-items`, { expected_revision: order.data!.revision, sales_order_line_ids: removeIds, reason: removeReason }, () => { setRemoveIds([]); setRemoveReason(''); setQuantities({}); })}>Remove selected items</Button></div></details>}
        {caps.data.orders_create && order.data.billing_state === 'unpaid_tab' && order.data.customer_assigned === false && <div className="grid min-w-0 gap-3 sm:grid-cols-2"><p className="text-sm sm:col-span-2">Assign this walk-in tab to a named customer before billing. This records its first customer and cannot reassign an existing customer.</p><label className="grid gap-1 text-sm">Find customer for this tab<Input aria-label="Find assignment customer" value={customerSearch} onChange={event => setCustomerSearch(event.target.value)} /></label><label className="grid gap-1 text-sm">Customer for this tab<NativeSelect aria-label="Assign tab customer" value={assignmentCustomer} onChange={event => setAssignmentCustomer(event.target.value)}><option value="">Choose customer</option>{customers.data?.pages.flatMap(page => page.items).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</NativeSelect></label><Button variant="outline" disabled={busy || !positive(assignmentCustomer) || customers.isFetching} onClick={() => void send('tab.assign_customer', `/srm/restaurant/tabs/${order.data!.id}/customer`, { expected_revision: order.data!.revision, customer_id: Number(assignmentCustomer) }, () => setAssignmentCustomer(''))}>Assign customer to tab</Button>{customers.hasNextPage && <Button variant="outline" onClick={() => void customers.fetchNextPage()}>More assignment customers</Button>}</div>}
        {caps.data.orders_create && order.data.state === 'open' && <form className="space-y-3" onSubmit={event => { event.preventDefault(); const current = order.data!; void send('kitchen.submit', `/srm/restaurant/orders/${current.id}/tickets`, { service_order_id: current.id, expected_revision: current.revision,
        lines: current.items.filter(row => Number(quantities[row.sales_order_line_id] || '0') > 0).map(row => ({ sales_order_line_id: row.sales_order_line_id, quantity: quantities[row.sales_order_line_id], instruction: instructions[row.sales_order_line_id] || '' })) }, () => { setQuantities({}); setInstructions({}); }); }}>
        {order.data.items.map(row => <div key={row.sales_order_line_id} className="grid min-w-0 gap-2 sm:grid-cols-3"><p className="text-sm">{row.item} · {row.sent_quantity || '0'} / {row.quantity} sent</p><label className="grid min-w-0 gap-1 text-sm">Send quantity<Input inputMode="decimal" value={quantities[row.sales_order_line_id] || ''} onChange={event => setQuantities(current => ({ ...current, [row.sales_order_line_id]: event.target.value }))} /></label><label className="grid min-w-0 gap-1 text-sm">Kitchen instruction<Input maxLength={1000} value={instructions[row.sales_order_line_id] || ''} onChange={event => setInstructions(current => ({ ...current, [row.sales_order_line_id]: event.target.value }))} /></label></div>)}
        <Button disabled={busy || order.isFetching || !Object.values(quantities).some(value => Number(value) > 0)}>Send selected items</Button>
      </form>}<div className="grid min-w-0 gap-3 md:grid-cols-2">{order.data.tickets.map(ticketCard)}</div></>}
    </CardContent></Card>}
    {caps.data.billing_view && positive(orderId) && order.data && order.data.billing_state !== 'paid_pos' && <Card><CardHeader><CardTitle className="text-base">Tab billing & payments</CardTitle></CardHeader><CardContent className="space-y-3">
      {billing.isError && <p role="alert">{catalogError(billing.error)}</p>}
      {bills.isError && <p role="alert">{catalogError(bills.error)}</p>}
      {(caps.data.billing_prepare || caps.data.payments_record) && <><label className="grid gap-1 text-sm">Collection register<NativeSelect aria-label="Collection register" value={register} onChange={event => { setRegister(event.target.value); setPaymentKey(crypto.randomUUID()); }}><option value="">Choose open register</option>{registers.data?.pages.flatMap(page => page.items).map(row => <option key={row.id} value={row.id}>{row.label}</option>)}</NativeSelect></label>{registers.hasNextPage && <Button variant="outline" onClick={() => void registers.fetchNextPage()}>More open registers</Button>}{registers.isError && <p role="alert">{catalogError(registers.error)}</p>}</>}
      {!billing.data?.checkout && caps.data.anonymous_settle && order.data.customer_assigned === false && <label className="grid gap-1 text-sm">Billing mode<NativeSelect aria-label="Tab billing mode" value={billingMode} onChange={event => setBillingMode(event.target.value)}><option value="named">Named customer invoice</option><option value="anonymous">Anonymous counter · full payment</option></NativeSelect></label>}
      {anonymousMode ? <div className="space-y-3"><p className="text-sm">No customer details are required. Collect the full {order.data.currency} {order.data.total} bill in this transaction, using one or more payment methods.</p>
        {counter.isError && <p role="alert">{catalogError(counter.error)}</p>}{counter.data && !counter.data.enabled && <p className="text-sm">A company administrator must enable the anonymous counter account before collecting this bill.</p>}
        {anonymousPayments.map((row, index) => <div key={row.payment_key} className="grid min-w-0 gap-3 sm:grid-cols-3"><label className="grid gap-1 text-sm">Payment method<NativeSelect aria-label={`Anonymous payment method ${index + 1}`} value={row.method} onChange={event => setAnonymousPayments(current => current.map(item => item.payment_key === row.payment_key ? { ...item, method: event.target.value as Tender['method'] } : item))}><option value="cash">Cash</option><option value="card">Card</option><option value="upi">UPI</option><option value="bank_transfer">Bank transfer</option></NativeSelect></label><label className="grid gap-1 text-sm">Amount<Input aria-label={`Anonymous payment amount ${index + 1}`} inputMode="decimal" value={row.amount} onChange={event => setAnonymousPayments(current => current.map(item => item.payment_key === row.payment_key ? { ...item, amount: event.target.value } : item))} /></label><Button variant="ghost" disabled={busy || anonymousPayments.length === 1} onClick={() => setAnonymousPayments(current => current.filter(item => item.payment_key !== row.payment_key))}>Remove payment</Button></div>)}
        <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy || anonymousPayments.length >= 10} onClick={() => setAnonymousPayments(current => [...current, tender()])}>Add payment method</Button><Button disabled={busy || !positive(register) || !fullTender || !counter.data?.enabled || counter.isFetching} onClick={() => void send('tab.settle_anonymous', `/srm/restaurant/tabs/${orderId}/anonymous-settlement`, { expected_revision: order.data!.revision, expected_total: order.data!.total, pos_session_id: Number(register), payments: anonymousPayments }, () => { setBillingMode('named'); setAnonymousPayments([tender()]); })}>Collect full payment & issue invoice</Button></div>
      </div> : billing.data?.checkout ? <><p>Invoice {billing.data.checkout.invoice.number} · {billing.data.checkout.invoice.currency} {billing.data.checkout.invoice.total}</p><p>Paid {billing.data.checkout.invoice.paid} · Balance {billing.data.checkout.invoice.balance}</p>
        {caps.data.payments_record && Number(billing.data.checkout.invoice.balance) > 0 && <div className="grid gap-3 sm:grid-cols-2"><label className="grid gap-1 text-sm">Payment method<NativeSelect aria-label="Tab payment method" value={paymentMethod} onChange={event => { setPaymentMethod(event.target.value); setPaymentKey(crypto.randomUUID()); }}><option value="cash">Cash</option><option value="card">Card</option><option value="upi">UPI</option><option value="bank_transfer">Bank transfer</option></NativeSelect></label><label className="grid gap-1 text-sm">Amount<Input aria-label="Tab payment amount" inputMode="decimal" value={paymentAmount} onChange={event => { setPaymentAmount(event.target.value); setPaymentKey(crypto.randomUUID()); }} /></label><Button disabled={busy || !positive(register) || Number(paymentAmount) <= 0 || !Number.isFinite(Number(paymentAmount))} onClick={() => void send('tab.payment', `/srm/restaurant/tabs/${orderId}/payments`, { expected_revision: billing.data!.checkout!.revision, pos_session_id: Number(register), payment: { payment_key: paymentKey, method: paymentMethod, amount: paymentAmount } }, () => { setPaymentAmount(''); setPaymentKey(crypto.randomUUID()); })}>Collect payment</Button><p className="text-xs text-muted-foreground">Collect part of the balance using each payment method. The table stays occupied until the bill is fully paid and all items are served.</p></div>}
      </> : caps.data.billing_prepare && order.data?.billing_state === 'unpaid_tab' && <Button disabled={busy || !positive(register) || billing.isFetching || bills.isFetching || bills.isError || splitRows.length > 0 || !order.data.total} onClick={() => void send('tab.bill', `/srm/restaurant/tabs/${orderId}/bill`, { expected_revision: order.data!.revision, expected_total: order.data!.total, pos_session_id: Number(register) })}>Issue tab invoice</Button>}
      {!billing.data?.checkout && order.data.customer_assigned && order.data.state === 'open' && caps.data.billing_prepare && <details className="space-y-3"><summary className="cursor-pointer text-sm font-medium">Issue a separate item bill</summary>
        <div className="grid min-w-0 gap-3 sm:grid-cols-2">{order.data.items.map((row, index) => {
          const original = cents(row.quantity), used = splitRows.flatMap(bill => bill.items).filter(item => item.sales_order_line_id === row.sales_order_line_id).reduce((sum, item) => sum + (cents(item.quantity) || 0n), 0n);
          const remaining = original === null ? 0n : original - used;
          return <label key={row.sales_order_line_id} className="grid min-w-0 gap-1 text-sm">{row.item} · {decimal(remaining)} available<Input aria-label={`Bill quantity ${row.item} ${index + 1}`} inputMode="decimal" maxLength={13} disabled={busy || bills.isFetching || remaining <= 0n} value={splitQuantities[row.sales_order_line_id] || ''} onChange={event => setSplitQuantities(current => ({ ...current, [row.sales_order_line_id]: event.target.value }))} /></label>;
        })}</div><p className="text-sm" aria-label="Selected bill total">{splitQuote ? `Selected total: ${order.data.currency} ${splitQuote.total}` : 'Select valid remaining quantities for this bill.'}</p>
        <Button disabled={busy || order.isFetching || bills.isFetching || bills.isError || billing.isFetching || !bills.data || !splitQuote} onClick={() => { if (splitQuote && bills.data) void send('tab.split_bill', `/srm/restaurant/tabs/${orderId}/bills`, { expected_revision: bills.data.order_revision, expected_total: splitQuote.total, lines: splitQuote.lines }, () => setSplitQuantities({})); }}>Issue selected item bill</Button>
      </details>}
      {splitRows.length > 0 && <><div className="overflow-x-auto"><GridTable gridId="apps/srm/restaurant/split-bills" className="w-full text-left text-sm"><thead><tr><th className="px-3 py-2">Invoice</th><th className="px-3 py-2">Total</th><th className="px-3 py-2">Paid</th><th className="px-3 py-2">Balance</th></tr></thead><tbody>{splitRows.map(row => <tr key={row.bill_id} className="border-t"><td className="px-3 py-2">{row.number || `Bill ${row.bill_id}`}</td><td className="px-3 py-2">{row.currency} {row.total}</td><td className="px-3 py-2">{row.paid}</td><td className="px-3 py-2">{row.balance}</td></tr>)}</tbody></GridTable></div>
        {caps.data.payments_record && selectedBill && (cents(selectedBill.balance) || 0n) > 0n && <div className="grid min-w-0 gap-3 sm:grid-cols-2"><label className="grid min-w-0 gap-1 text-sm">Invoice to collect<NativeSelect aria-label="Split invoice to collect" className="w-full min-w-0 max-w-full" value={String(selectedBill.bill_id)} onChange={event => { setSplitBill(event.target.value); setPaymentAmount(''); setPaymentKey(crypto.randomUUID()); }}>{splitRows.filter(row => (cents(row.balance) || 0n) > 0n).map(row => <option key={row.bill_id} value={row.bill_id}>{row.number || `Bill ${row.bill_id}`} · {row.currency} {row.balance}</option>)}</NativeSelect></label>
          <label className="grid min-w-0 gap-1 text-sm">Payment method<NativeSelect aria-label="Split payment method" value={paymentMethod} onChange={event => { setPaymentMethod(event.target.value); setPaymentKey(crypto.randomUUID()); }}><option value="cash">Cash</option><option value="card">Card</option><option value="upi">UPI</option><option value="bank_transfer">Bank transfer</option></NativeSelect></label>
          <label className="grid min-w-0 gap-1 text-sm">Amount<Input aria-label="Split payment amount" inputMode="decimal" value={paymentAmount} onChange={event => { setPaymentAmount(event.target.value); setPaymentKey(crypto.randomUUID()); }} /></label><Button disabled={busy || bills.isFetching || bills.isError || order.isFetching || !positive(register) || !bills.data || (cents(paymentAmount) || 0n) <= 0n || (cents(paymentAmount) || 0n) > (cents(selectedBill.balance) || 0n)} onClick={() => { if (bills.data) void send('tab.split_payment', `/srm/restaurant/tabs/${orderId}/bills/${selectedBill.bill_id}/payments`, { expected_revision: bills.data.order_revision, expected_balance: selectedBill.balance, pos_session_id: Number(register), payment: { payment_key: paymentKey, method: paymentMethod, amount: paymentAmount } }, () => { setSplitBill(''); setPaymentAmount(''); setPaymentKey(crypto.randomUUID()); }); }}>Collect split invoice payment</Button>
        </div>}</>}
    </CardContent></Card>}
    {caps.data.kitchen_view && <section className="min-w-0 space-y-3"><h2 className="text-lg font-semibold">Kitchen queue</h2>{kitchen.isError ? <p role="alert">{catalogError(kitchen.error)}</p> : <div className="grid min-w-0 gap-3 md:grid-cols-2 xl:grid-cols-3">{kitchen.data?.items.map(ticketCard)}{kitchen.data?.items.length === 0 && <p className="text-sm text-muted-foreground">No pending kitchen tickets.</p>}</div>}</section>}
  </div>;
}
