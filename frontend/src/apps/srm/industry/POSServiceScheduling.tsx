import { useDeferredValue, useEffect, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { useRecordScope } from '@/lib/record-scope';
import { useRecordScopeOwner } from '@/hooks/use-record-scope-owner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { dealError } from '@/apps/crm/deals/deal-utils';

export type BookingSelection = {
  policy_id: number; expected_policy_revision: number; eligibility_id: number; expected_eligibility_revision: number;
  provider_resource_id: number; employee_id: number; starts_at: string; duration_minutes: number;
};
type Provider = { provider_resource_id: number; employee_id: number; employee_name: string; provider_name: string; timezone: string };
type Specialist = Provider & { eligibility_id: number; eligibility_revision: number };
type Policy = { id: number; revision: number; booking_required: boolean; default_duration_minutes: number; min_duration_minutes: number; max_duration_minutes: number; allow_duration_override: boolean; active: boolean };
type Options = { policy: Policy | null; specialists: Specialist[]; has_more: boolean };
type PolicyDraft = { service_product_id: number; expected_revision?: number; default_duration_minutes: number; min_duration_minutes: number; max_duration_minutes: number; booking_required: boolean; allow_duration_override: boolean; active: boolean };
type Props = { productId: number; lineKey: string; value?: BookingSelection; onChange: (value: BookingSelection | undefined) => void; onRequirement?: (required: boolean) => void; context?: 'checkout' | 'reschedule'; configurationOnly?: boolean };
const fields = 'h-10 w-full rounded-md border bg-background px-3 text-sm';
function wall(instant: number, zone: string) {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(instant);
  const part = (key: string) => parts.find(item => item.type === key)?.value || '';
  return `${part('year')}-${part('month')}-${part('day')}T${part('hour')}:${part('minute')}`;
}
function candidates(value: string, zone: string) {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return [];
  const nominal = Date.parse(`${value}:00Z`); if (!Number.isFinite(nominal)) return [];
  try {
    const offsets = new Set<number>();
    for (let hour = -36; hour <= 36; hour += 6) { const sample = nominal + hour * 3600000; offsets.add(Date.parse(`${wall(sample, zone)}:00Z`) - sample); }
    return [...offsets].map(offset => nominal - offset).filter(instant => wall(instant, zone) === value);
  } catch { return []; }
}

/** Draft configuration only. Native checkout creates the actual appointment. */
export default function POSServiceScheduling(props: Props) {
  const scope = useRecordScope();
  return <Scheduling key={`${scope}:${props.productId}:${props.lineKey}`} {...props} scope={scope}/>;
}
function Scheduling({ productId, lineKey, value, onChange, onRequirement, scope, context = 'checkout', configurationOnly = false }: Props & { scope: string }) {
  const owns = useRecordScopeOwner();
  const [enabled, setEnabled] = useState(!!value), [selected, setSelected] = useState(String(value?.eligibility_id || ''));
  const [date, setDate] = useState(''), [time, setTime] = useState(''), [duration, setDuration] = useState(String(value?.duration_minutes || ''));
  const [edited, setEdited] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [search, setSearch] = useState(''), deferredSearch = useDeferredValue(search);
  const [config, setConfig] = useState<PolicyDraft | null>(null), [providerSearch, setProviderSearch] = useState(''), [candidate, setCandidate] = useState('');
  const deferredProvider = useDeferredValue(providerSearch), hydrated = useRef(''), invalidated = useRef('');
  const requirementCallback = useRef(onRequirement);
  requirementCallback.current = onRequirement;
  const options = useQuery({ queryKey: ['pos-service-scheduling', scope, productId, deferredSearch], queryFn: ({ signal }) => api.get<Options>('/srm/service-checkout/options', { signal, params: { service_id: productId, search: deferredSearch || undefined } }).then(result => result.data), retry: false });
  const policy = options.data?.policy;
  const specialist = options.data?.specialists.find(item => String(item.eligibility_id) === selected);
  const heldSpecialist = options.data?.specialists.find(item => item.eligibility_id === value?.eligibility_id);
  const providers = useQuery({ queryKey: ['pos-service-provider-options', scope, deferredProvider], queryFn: ({ signal }) => api.get<{ providers: Provider[]; has_more: boolean }>('/srm/service-checkout/options/providers', { signal, params: { search: deferredProvider || undefined } }).then(result => result.data), enabled: !!config, retry: false });
  useEffect(() => { if (options.isSuccess) requirementCallback.current?.(!!policy?.booking_required); }, [options.isSuccess, policy?.booking_required]);
  useEffect(() => {
    if (!value || !heldSpecialist) return;
    const key = JSON.stringify(value);
    if (hydrated.current === key) return;
    try { const local = wall(Date.parse(value.starts_at), heldSpecialist.timezone); setDate(local.slice(0, 10)); setTime(local.slice(11)); setDuration(String(value.duration_minutes)); setSelected(String(value.eligibility_id)); setEnabled(true); setEdited(false); hydrated.current = key; } catch { setError('The saved booking time or provider timezone is invalid. Select fresh booking details.'); }
  }, [value, heldSpecialist]);
  useEffect(() => {
    if (!value || !options.isSuccess) return;
    const stale = !policy || value.policy_id !== policy.id || value.expected_policy_revision !== policy.revision || !policy.active || (!heldSpecialist && !options.data?.has_more && !deferredSearch) || (heldSpecialist && (value.expected_eligibility_revision !== heldSpecialist.eligibility_revision || value.provider_resource_id !== heldSpecialist.provider_resource_id || value.employee_id !== heldSpecialist.employee_id));
    const key = JSON.stringify(value);
    if (stale && invalidated.current !== key) { invalidated.current = key; setSelected(''); setEdited(true); setError('Scheduling rules or specialist eligibility changed. Choose the specialist again and apply fresh booking details.'); onChange(undefined); }
  }, [value, policy, heldSpecialist, options.isSuccess, options.data?.has_more, deferredSearch, onChange]);
  function edit() { setEdited(true); setError(''); setNotice(''); onChange(undefined); }
  const configure = useMutation({ mutationFn: (draft: PolicyDraft) => api.put('/srm/service-checkout/policies', draft), onSuccess: async () => {
    if (!owns()) return; onChange(undefined); setSelected(''); setEdited(true); setConfig(null); await options.refetch(); if (owns()) setNotice('Scheduling policy saved. Choose a specialist and apply fresh booking details.');
  } });
  const eligible = useMutation({ mutationFn: async () => {
    const provider = providers.data?.providers.find(item => String(item.provider_resource_id) === candidate);
    if (!provider || !policy) throw new Error('Choose a current provider and save the policy first.');
    const previous = options.data?.specialists.find(item => item.provider_resource_id === provider.provider_resource_id && item.employee_id === provider.employee_id);
    return api.put('/srm/service-checkout/eligibility', { policy_id: policy.id, expected_policy_revision: policy.revision, provider_resource_id: provider.provider_resource_id, employee_id: provider.employee_id, active: true, ...(previous ? { expected_revision: previous.eligibility_revision } : {}) });
  }, onSuccess: async () => { if (!owns()) return; await options.refetch(); if (owns()) setNotice(context === 'reschedule' ? 'Existing HRMS provider enabled for this service. Select the specialist for the new schedule.' : 'Existing HRMS provider enabled for this service. Select the specialist to schedule this cart line.'); } });
  const busy = configure.isPending || eligible.isPending;
  function apply() {
    if (!policy?.active || !specialist || !owns()) { setError('Choose an active service policy and an eligible specialist.'); return; }
    const minutes = policy.allow_duration_override ? Number(duration || policy.default_duration_minutes) : policy.default_duration_minutes;
    if (!Number.isInteger(minutes) || minutes < policy.min_duration_minutes || minutes > policy.max_duration_minutes || (!policy.allow_duration_override && minutes !== policy.default_duration_minutes)) { setError(`Duration must follow the service policy (${policy.min_duration_minutes}–${policy.max_duration_minutes} minutes).`); return; }
    if (!edited && value && value.expected_policy_revision === policy.revision && value.expected_eligibility_revision === specialist.eligibility_revision) { onChange(value); return; }
    const matches = candidates(`${date}T${time}`, specialist.timezone);
    if (matches.length !== 1) { setError(matches.length > 1 ? 'This local time repeats during daylight saving. Choose an unambiguous time.' : 'Choose a valid local date and time. Skipped daylight-saving times cannot be booked.'); return; }
    onChange({ policy_id: policy.id, expected_policy_revision: policy.revision, eligibility_id: specialist.eligibility_id, expected_eligibility_revision: specialist.eligibility_revision, provider_resource_id: specialist.provider_resource_id, employee_id: specialist.employee_id, starts_at: new Date(matches[0]).toISOString(), duration_minutes: minutes });
    setEdited(false); setNotice(context === 'reschedule' ? 'Booking details applied. Save the new schedule to update the appointment.' : 'Booking details applied to this cart line. The appointment is created when checkout succeeds.');
  }
  const required = !!policy?.booking_required, show = required || enabled || !!value;
  return <section className="min-w-0 space-y-3 rounded border p-3 text-sm" aria-label={`Service scheduling ${lineKey}`}>
    {options.isPending && <p role="status">Loading service scheduling…</p>}
    {options.isError && <p role="alert">{dealError(options.error)} <Button type="button" variant="outline" size="sm" onClick={() => void options.refetch()}>Retry scheduling</Button></p>}
    {options.isSuccess && !configurationOnly && <>
      {required ? <p className="font-medium">Appointment required for this service</p> : <label className="flex items-center gap-2"><input type="checkbox" checked={show} disabled={!policy?.active || busy} onChange={event => { setEnabled(event.target.checked); edit(); }}/><span>Schedule this service</span></label>}
      {!policy?.active && <p className="text-xs text-muted-foreground">{policy ? 'Scheduling is inactive for this service.' : 'This service has no scheduling policy yet.'}</p>}
      {show && policy?.active && <div className="grid gap-3 sm:grid-cols-2">
        <label>Find eligible specialist<Input aria-label={`Find specialist ${lineKey}`} maxLength={100} value={search} onChange={event => setSearch(event.target.value)}/></label>
        <label>Specialist<NativeSelect aria-label={`Specialist ${lineKey}`} className={fields} value={selected} disabled={busy || options.isFetching} onChange={event => { setSelected(event.target.value); const next = options.data?.specialists.find(item => String(item.eligibility_id) === event.target.value); if (value && next) { try { const local = wall(Date.parse(value.starts_at), next.timezone); setDate(local.slice(0, 10)); setTime(local.slice(11)); } catch { setError('Provider timezone is invalid. Choose another specialist.'); } } if (!duration) setDuration(String(policy.default_duration_minutes)); edit(); }}><option value="">Choose eligible specialist</option>{selected && !specialist && <option value={selected}>Previously selected specialist · search or reselect to verify</option>}{options.data?.specialists.map(item => <option key={item.eligibility_id} value={item.eligibility_id}>{item.employee_name} · {item.provider_name} · {item.timezone}</option>)}</NativeSelect></label>
        {options.data?.has_more && <p className="text-xs text-muted-foreground sm:col-span-2">Showing at most 100 eligible specialists. Narrow the specialist search to find another match.</p>}
        <label>Date<Input aria-label={`Booking date ${lineKey}`} type="date" value={date} onChange={event => { setDate(event.target.value); edit(); }}/></label>
        <label>Time<Input aria-label={`Booking time ${lineKey}`} type="time" value={time} onChange={event => { setTime(event.target.value); edit(); }}/></label>
        <label>Duration (minutes)<Input aria-label={`Booking duration ${lineKey}`} type="number" min={policy.min_duration_minutes} max={policy.max_duration_minutes} step={1} disabled={!policy.allow_duration_override} value={policy.allow_duration_override ? duration || policy.default_duration_minutes : policy.default_duration_minutes} onChange={event => { setDuration(event.target.value); edit(); }}/></label>
        <p className="self-center text-xs text-muted-foreground">Times use {specialist?.timezone || 'the selected provider’s timezone'}. Planned service time is separate from actual timesheet hours.</p>
        <Button type="button" className="justify-self-start" size="sm" variant="outline" disabled={!specialist || busy || options.isFetching} onClick={apply}>Use these booking details</Button>
      </div>}
    </>}
    <div className="flex flex-wrap gap-2"><Button type="button" size="sm" variant="outline" disabled={options.isPending || busy} onClick={() => setConfig(config ? null : { service_product_id: productId, ...(policy ? { expected_revision: policy.revision } : {}), default_duration_minutes: policy?.default_duration_minutes || 30, min_duration_minutes: policy?.min_duration_minutes || 5, max_duration_minutes: policy?.max_duration_minutes || 720, booking_required: policy?.booking_required ?? true, allow_duration_override: policy?.allow_duration_override ?? false, active: policy?.active ?? true })}>{config ? 'Close scheduling configuration' : 'Configure service scheduling'}</Button><Button type="button" size="sm" variant="outline" disabled={options.isFetching || busy} onClick={() => void options.refetch()}>Reload scheduling options</Button></div>
    {config && <div className="space-y-3 rounded border p-3" aria-label={`Scheduling configuration ${lineKey}`}>
      <p className="text-xs text-muted-foreground">Service policy and specialist eligibility are saved for this service. The server checks your configuration permissions.</p>
      <div className="grid gap-3 sm:grid-cols-3">{(['default_duration_minutes', 'min_duration_minutes', 'max_duration_minutes'] as const).map(key => <label key={key}>{key.replace(/_/g, ' ')}<Input type="number" aria-label={`${key} ${lineKey}`} min={5} max={720} step={1} value={config[key]} disabled={busy} onChange={event => setConfig({ ...config, [key]: Number(event.target.value) })}/></label>)}</div>
      <div className="flex flex-wrap gap-3">{(['booking_required', 'allow_duration_override', 'active'] as const).map(key => <label key={key} className="flex items-center gap-2"><input type="checkbox" checked={config[key]} disabled={busy} onChange={event => setConfig({ ...config, [key]: event.target.checked })}/>{key.replace(/_/g, ' ')}</label>)}</div>
      <Button type="button" size="sm" disabled={busy} onClick={() => { if (config.min_duration_minutes < 5 || config.max_duration_minutes > 720 || config.default_duration_minutes < config.min_duration_minutes || config.default_duration_minutes > config.max_duration_minutes || ![config.default_duration_minutes, config.min_duration_minutes, config.max_duration_minutes].every(Number.isInteger)) { setError('Use whole-minute durations between 5 and 720, with the default inside the minimum and maximum.'); return; } configure.mutate(config); }}>{configure.isPending ? 'Saving…' : 'Save service policy'}</Button>
      {policy && <div className="space-y-2 border-t pt-3"><label>Find existing HRMS provider<Input aria-label={`Find provider ${lineKey}`} maxLength={100} value={providerSearch} onChange={event => { setProviderSearch(event.target.value); setCandidate(''); }}/></label><NativeSelect aria-label={`Eligible provider candidate ${lineKey}`} className={fields} value={candidate} loading={providers.isFetching} error={providers.isError} onChange={event => setCandidate(event.target.value)}><option value="">Choose existing provider</option>{providers.data?.providers.map(item => <option key={item.provider_resource_id} value={item.provider_resource_id}>{item.employee_name} · {item.provider_name} · {item.timezone}</option>)}</NativeSelect>{providers.data?.has_more && <p className="text-xs text-muted-foreground">Showing at most 100 providers. Narrow the search for more choices.</p>}{providers.isError && <p role="alert">{dealError(providers.error)} <Button type="button" size="sm" variant="outline" onClick={() => void providers.refetch()}>Retry providers</Button></p>}<Button type="button" size="sm" disabled={!candidate || busy || providers.isFetching} onClick={() => eligible.mutate()}>{eligible.isPending ? 'Saving…' : 'Enable specialist for this service'}</Button></div>}
    </div>}
    {error && <p role="alert">{error}</p>}{configure.isError && <p role="alert">{dealError(configure.error)} Reload service scheduling and review the policy before retrying.</p>}{eligible.isError && <p role="alert">{dealError(eligible.error)} Reload service scheduling before retrying eligibility.</p>}{notice && <p role="status">{notice}</p>}
  </section>;
}
