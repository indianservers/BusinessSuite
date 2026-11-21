import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import { useRecordScope } from '@/lib/record-scope';
import { useRecordScopeOwner } from '@/hooks/use-record-scope-owner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { dealError } from '@/apps/crm/deals/deal-utils';

export type AnonymousCashConfiguration = { schema_ready: boolean; configured: boolean; enabled: boolean; revision: number; label: string | null };
export default function AnonymousCashSetup({ canConfigure, enabled = true }: { canConfigure: boolean; enabled?: boolean }) {
  const scope = useRecordScope();
  return <Setup key={scope} scope={scope} canConfigure={canConfigure} enabled={enabled}/>;
}
function Setup({ scope, canConfigure, enabled }: { scope: string; canConfigure: boolean; enabled: boolean }) {
  const owns = useRecordScopeOwner();
  const queryClient = useQueryClient();
  const query = useQuery({ enabled, queryKey: ['srm', 'anonymous-cash-configuration', scope], retry: false, queryFn: () => api.get<AnonymousCashConfiguration>('/srm/anonymous-cash/configuration').then(response => response.data) });
  const [open, setOpen] = useState(false), [action, setAction] = useState(''), [label, setLabel] = useState(''), [country, setCountry] = useState(''), [identity, setIdentity] = useState(''), [reason, setReason] = useState(''), [active, setActive] = useState(true);
  const [expectedRevision, setExpectedRevision] = useState(0);
  const mutation = useMutation({ mutationFn: async () => {
    if (!['create', 'select', 'status'].includes(action)) throw new Error('Choose an explicit setup action.');
    if (action !== 'status' && (!label.trim() || !/^[A-Z]{2}$/.test(country))) throw new Error('Enter an account label and an explicit two-letter country code.');
    if (action === 'select' && (!Number.isSafeInteger(Number(identity)) || Number(identity) <= 0)) throw new Error('Enter the existing dedicated counter account ID.');
    if (reason.trim().length < 8) throw new Error('Explain this configuration change using at least eight characters.');
    return api.put('/srm/anonymous-cash/configuration', { action, expected_revision: expectedRevision, active, reason: reason.trim(), ...(action !== 'status' ? {label: label.trim(), jurisdiction_country: country} : {}), ...(action === 'select' ? {customer_id: Number(identity)} : {}) });
  }, onSuccess: () => {
    if (!owns()) return;
    setReason('');
    setOpen(false);
    void query.refetch();
    void queryClient.invalidateQueries({queryKey:["srm","pos-walk-in-configuration"]});
  } });
  return <section className="mt-2 min-w-0 space-y-2 rounded border p-3 text-sm" aria-label="Walk-in counter account">
    {query.isPending ? <p role="status">Checking walk-in counter configuration…</p> : query.isError ? <p role="alert">{dealError(query.error)}</p> : <p>{query.data?.enabled ? `Walk-in counter account enabled: ${query.data.label}` : 'Walk-in counter account is not enabled. A company administrator must explicitly configure it before checkout.'}</p>}
    <p className="text-xs text-muted-foreground">Walk-in checkout requires full payment and supports products or services without appointments or follow-ups.</p>
    <Button type="button" size="sm" variant="outline" className="h-auto max-w-full whitespace-normal py-2" onClick={() => void query.refetch()}>Reload counter configuration</Button>
    {canConfigure && <Button type="button" size="sm" variant="outline" className="h-auto max-w-full whitespace-normal py-2" disabled={query.isFetching || query.isError || mutation.isPending} onClick={() => { if (!open) setExpectedRevision(query.data?.revision ?? 0); setOpen(value => !value); }}>Configure walk-in counter account</Button>}
    {canConfigure && open && <div className="grid gap-2" aria-label="Counter account configuration">
      <label>Action<NativeSelect aria-label="Counter setup action" value={action} onChange={event => setAction(event.target.value)}><option value="">Choose action</option><option value="create">Create dedicated counter ledger account</option><option value="select">Select existing dedicated counter account</option>{query.data?.configured && <option value="status">Change enabled status</option>}</NativeSelect></label>
      {action !== 'status' && <><label>Explicit account label<Input aria-label="Counter account label" value={label} maxLength={180} onChange={event => setLabel(event.target.value)}/></label><label>Country code<Input aria-label="Counter account country code" value={country} maxLength={2} placeholder="Two-letter country code" onChange={event => setCountry(event.target.value.toUpperCase())}/></label></>}
      {action === 'select' && <label>Existing dedicated account ID<Input aria-label="Dedicated counter account ID" type="number" min={1} value={identity} onChange={event => setIdentity(event.target.value)}/></label>}
      <label className="flex gap-2"><input type="checkbox" checked={active} onChange={event => setActive(event.target.checked)}/>Enable this counter account</label>
      <label>Reason<Input aria-label="Counter configuration reason" value={reason} minLength={8} maxLength={1000} onChange={event => setReason(event.target.value)}/></label>
      <Button type="button" disabled={mutation.isPending || query.isPending || query.isError || !query.data?.schema_ready} onClick={() => mutation.mutate()}>Save counter configuration</Button>
      {mutation.isError && <p role="alert">{dealError(mutation.error)}</p>}
    </div>}
  </section>;
}
