import * as Dialog from "@radix-ui/react-dialog";
import { CalendarDays, X } from "lucide-react";
import { wall, candidates } from '@/shared/scheduling/booking-time';
import EmployeeCategories from "@/shared/EmployeeCategories";
import { Link } from 'react-router-dom';
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
  additional_resource_ids?: number[];
  policy_id: number; expected_policy_revision: number; eligibility_id: number; expected_eligibility_revision: number;
  provider_resource_id: number; employee_id: number; starts_at: string; duration_minutes: number;
};
type Provider = { provider_resource_id: number; employee_id: number; employee_name: string; provider_name: string; timezone: string; work_categories?: string[] };
type Specialist = Provider & { eligibility_id: number; eligibility_revision: number };
type Policy = { employee_categories?: string[]; id: number; revision: number; booking_required: boolean; default_duration_minutes: number; min_duration_minutes: number; max_duration_minutes: number; allow_duration_override: boolean; active: boolean };
type Options = { resources?: {id: number; name: string; resource_type: string}[]; policy: Policy | null; specialists: Specialist[]; has_more: boolean };
type PolicyDraft = { employee_categories: string[]; service_product_id: number; expected_revision?: number; default_duration_minutes: number; min_duration_minutes: number; max_duration_minutes: number; booking_required: boolean; allow_duration_override: boolean; active: boolean };
type Props = { compactSummary?: string; productId: number; lineKey: string; value?: BookingSelection; onChange: (value: BookingSelection | undefined) => void; onRequirement?: (required: boolean) => void; onSummary?: (summary:string)=>void; onAvailability?: (available:boolean|null)=>void; context?: 'checkout' | 'reschedule'; configurationOnly?: boolean };
const fields = 'h-10 w-full rounded-md border bg-background px-3 text-sm';
/** Draft configuration only. Native checkout creates the actual appointment. */
export default function POSServiceScheduling(props: Props) {
  const scope=useRecordScope(),[open,setOpen]=useState(false);
  const content=<Scheduling key={`${scope}:${props.productId}:${props.lineKey}`} {...props} onChange={value=>{props.onChange(value);if(value)setOpen(false);}} scope={scope}/>;
  if(!props.compactSummary)return content;
  return <><Button type="button" variant="outline" className="pos-booking-trigger" onClick={()=>setOpen(true)}><CalendarDays size={16}/><span>{props.compactSummary}</span><span aria-hidden="true">›</span></Button><Dialog.Root modal={false} open={open} onOpenChange={setOpen}><Dialog.Portal forceMount><Dialog.Overlay forceMount hidden={!open} className="fixed inset-0 z-[10000] bg-black/40"/><Dialog.Content forceMount hidden={!open} className="pos-mobile-booking-dialog fixed left-1/2 top-1/2 z-[10001] w-[calc(100vw-24px)] max-w-2xl max-h-[85dvh] -translate-x-1/2 -translate-y-1/2 overflow-auto rounded-2xl bg-white p-4 shadow-xl"><div className="flex justify-between gap-3"><Dialog.Title className="font-semibold">Service booking</Dialog.Title><Dialog.Close aria-label="Close service booking"><X size={20}/></Dialog.Close></div><Dialog.Description className="text-sm text-slate-500">Choose an employee, time and resources for this sale.</Dialog.Description>{content}</Dialog.Content></Dialog.Portal></Dialog.Root></>;
}

function Scheduling({ productId, lineKey, value, onChange, onRequirement, onSummary, onAvailability, scope, context = 'checkout', configurationOnly = false }: Props & { scope: string }) {
  const owns = useRecordScopeOwner();
  const [categoryFilters,setCategoryFilters] = useState<string[]>([]);
  const [enabled, setEnabled] = useState(!!value), [selected, setSelected] = useState(String(value?.eligibility_id || ''));
  const [date, setDate] = useState(''), [time, setTime] = useState(''), [duration, setDuration] = useState(String(value?.duration_minutes || ''));
  const [endDate, setEndDate] = useState(''), [endTime, setEndTime] = useState(''), [resourceIds, setResourceIds] = useState<number[]>(value?.additional_resource_ids || []);
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
  const summaryCallback = useRef(onSummary);summaryCallback.current=onSummary;
  useEffect(()=>{if(!value || !heldSpecialist)return;const format=new Intl.DateTimeFormat(undefined,{timeZone:heldSpecialist.timezone,dateStyle:'medium',timeStyle:'short'});summaryCallback.current?.(`${heldSpecialist.employee_name} - ${format.format(new Date(value.starts_at))} to ${format.format(new Date(Date.parse(value.starts_at)+value.duration_minutes*60000))} (${heldSpecialist.timezone})${value.additional_resource_ids?.map(id=>` - ${options.data?.resources?.find(resource=>resource.id===id)?.name || `Resource ${id}`}`).join('') || ''}`);},[value,heldSpecialist,options.data?.resources]);
  const providers = useQuery({ queryKey: ['pos-service-provider-options', scope, deferredProvider], queryFn: ({ signal }) => api.get<{ providers: Provider[]; has_more: boolean }>('/srm/service-checkout/options/providers', { signal, params: { search: deferredProvider || undefined } }).then(result => result.data), enabled: !!config, retry: false });
  const startMatches = specialist && date && time ? candidates(`${date}T${time}`,specialist.timezone) : [];
  const endMatches = specialist && endDate && endTime ? candidates(`${endDate}T${endTime}`,specialist.timezone) : [];
  const requestedMinutes = startMatches.length===1 && endMatches.length===1 ? (endMatches[0]-startMatches[0])/60000 : Number(duration || policy?.default_duration_minutes || 30);
  type Availability = {slots:{starts_at:string;label:string}[];timezone:string;selection_available:boolean|null;resources:{id:number;available:boolean}[]};
  const availability = useQuery({queryKey:['pos-service-availability',scope,productId,selected,date,time,requestedMinutes,resourceIds.join(',')],
    enabled:context==='checkout' && !configurationOnly && !!specialist && !!date && !!policy?.active && Number.isInteger(requestedMinutes) && requestedMinutes>=5 && requestedMinutes<=720,
    queryFn:({signal})=>{const params=new URLSearchParams({service_id:String(productId),eligibility_id:selected,day:date,duration_minutes:String(requestedMinutes)});resourceIds.forEach(id=>params.append('resource_ids',String(id)));if(startMatches.length===1)params.set('starts_at',new Date(startMatches[0]).toISOString());return api.get<Availability>('/srm/service-checkout/options/availability',{signal,params,recordCache:false}).then(response=>response.data);},retry:false,staleTime:15000});
  const availabilityCallback=useRef(onAvailability);availabilityCallback.current=onAvailability;
  useEffect(()=>{availabilityCallback.current?.(value && availability.isSuccess ? availability.data.selection_available : null);},[value,availability.isSuccess,availability.data?.selection_available]);
  useEffect(()=>{
    if(!specialist || !date || !time || endDate || endTime)return;
    const matches=candidates(`${date}T${time}`,specialist.timezone),minutes=policy?.allow_duration_override ? Number(duration || policy.default_duration_minutes) : policy?.default_duration_minutes;
    if(matches.length!==1 || !minutes || !Number.isFinite(minutes))return;
    const end=wall(matches[0]+minutes*60000,specialist.timezone);setEndDate(end.slice(0,10));setEndTime(end.slice(11));
  },[date,time,duration,specialist,policy,endDate,endTime]);

  useEffect(() => { if (options.isSuccess) requirementCallback.current?.(!!policy?.booking_required); }, [options.isSuccess, policy?.booking_required]);
  useEffect(() => {
    if (!value || !heldSpecialist) return;
    const key = JSON.stringify(value);
    if (hydrated.current === key) return;
    try { const local = wall(Date.parse(value.starts_at), heldSpecialist.timezone); setDate(local.slice(0, 10)); setTime(local.slice(11)); setDuration(String(value.duration_minutes)); const end = wall(Date.parse(value.starts_at) + value.duration_minutes * 60000, heldSpecialist.timezone); setEndDate(end.slice(0, 10)); setEndTime(end.slice(11)); setResourceIds(value.additional_resource_ids || []); setSelected(String(value.eligibility_id)); setEnabled(true); setEdited(false); hydrated.current = key; } catch { setError('The saved booking time or provider timezone is invalid. Select fresh booking details.'); }
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
    if (availability.data?.selection_available === false && context === 'checkout') {setError('This employee or resource is unavailable for the selected interval. Choose another slot or resource.');return;}
    if (!policy?.active || !specialist || !owns()) { setError('Choose an active service policy and an eligible specialist.'); return; }
    let minutes = policy.allow_duration_override ? Number(duration || policy.default_duration_minutes) : policy.default_duration_minutes;
    if (endDate || endTime) {
      const starts = candidates(`${date}T${time}`, specialist.timezone), ends = candidates(`${endDate}T${endTime}`, specialist.timezone);
      if (starts.length !== 1 || ends.length !== 1) { setError('Choose valid, unambiguous From and To dates and times.'); return; }
      minutes = (ends[0] - starts[0]) / 60000;
    }
    if (!Number.isInteger(minutes) || minutes < policy.min_duration_minutes || minutes > policy.max_duration_minutes || (!policy.allow_duration_override && minutes !== policy.default_duration_minutes)) { setError(`Duration must follow the service policy (${policy.min_duration_minutes}–${policy.max_duration_minutes} minutes).`); return; }
    if (!edited && value && value.expected_policy_revision === policy.revision && value.expected_eligibility_revision === specialist.eligibility_revision) { onChange(value); return; }
    const matches = candidates(`${date}T${time}`, specialist.timezone);
    if (matches.length !== 1) { setError(matches.length > 1 ? 'This local time repeats during daylight saving. Choose an unambiguous time.' : 'Choose a valid local date and time. Skipped daylight-saving times cannot be booked.'); return; }
    onChange({ additional_resource_ids: resourceIds, policy_id: policy.id, expected_policy_revision: policy.revision, eligibility_id: specialist.eligibility_id, expected_eligibility_revision: specialist.eligibility_revision, provider_resource_id: specialist.provider_resource_id, employee_id: specialist.employee_id, starts_at: new Date(matches[0]).toISOString(), duration_minutes: minutes });
    setEdited(false); setNotice(context === 'reschedule' ? 'Booking details applied. Save the new schedule to update the appointment.' : 'Booking details applied to this cart line. The appointment is created when checkout succeeds.');
  }
  const required = !!policy?.booking_required, show = required || enabled || !!value;
  return <section className="min-w-0 space-y-3 rounded border p-3 text-sm" aria-label={`Service scheduling ${lineKey}`}>
    {!configurationOnly && <p className="text-xs text-muted-foreground">Choose an employee for this appointment. Add the service again to book another employee or time.</p>}
    {options.isPending && <p role="status">Loading service scheduling…</p>}
    {options.isError && <p role="alert">{dealError(options.error)} <Button type="button" variant="outline" size="sm" onClick={() => void options.refetch()}>Retry scheduling</Button></p>}
    {options.isSuccess && !configurationOnly && <>
      {required ? <p className="font-medium">Appointment required for this service</p> : <label className="flex items-center gap-2"><input type="checkbox" checked={show} disabled={!policy?.active || busy} onChange={event => { setEnabled(event.target.checked); edit(); }}/><span>Schedule this service</span></label>}
      {!policy?.active && <p className="text-xs text-muted-foreground">{policy ? 'Scheduling is inactive for this service.' : 'This service has no scheduling policy yet.'}</p>}
      {!!policy?.employee_categories?.length && <p className="text-xs text-muted-foreground">Employee categories: {policy.employee_categories.join(", ")}</p>}
      {show && policy?.active && <div className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2"><EmployeeCategories value={categoryFilters} options={[...new Set([...(policy.employee_categories || []),...(options.data?.specialists.flatMap(item=>item.work_categories || []) || [])])]} onChange={values=>{setCategoryFilters(values);if(specialist && values.length && !specialist.work_categories?.some(category=>values.includes(category))){setSelected('');edit();}}}/></div>
        <label>Find employee<Input aria-label={`Find specialist ${lineKey}`} maxLength={100} value={search} onChange={event => setSearch(event.target.value)}/></label>
        <label>Employee<NativeSelect aria-label={`Specialist ${lineKey}`} className={fields} value={selected} disabled={busy || options.isFetching} onChange={event => { setSelected(event.target.value); const next = options.data?.specialists.find(item => String(item.eligibility_id) === event.target.value); if (value && next) { try { const local = wall(Date.parse(value.starts_at), next.timezone); setDate(local.slice(0, 10)); setTime(local.slice(11)); } catch { setError('Provider timezone is invalid. Choose another specialist.'); } } if (!duration) setDuration(String(policy.default_duration_minutes)); if(next && !date)setDate(wall(Date.now(),next.timezone).slice(0,10)); setEndDate('');setEndTime('');edit(); }}><option value="">Choose eligible employee</option>{selected && !specialist && <option value={selected}>Previously selected specialist · search or reselect to verify</option>}{options.data?.specialists.filter(item=>!categoryFilters.length || item.work_categories?.some(category=>categoryFilters.includes(category))).map(item => <option key={item.eligibility_id} value={item.eligibility_id}>{item.employee_name} · {item.provider_name} · {item.timezone}</option>)}</NativeSelect></label>
        {options.data?.has_more && <p className="text-xs text-muted-foreground sm:col-span-2">Showing at most 100 eligible specialists. Narrow the specialist search to find another match.</p>}
        <label>From date<Input aria-label={`Booking date ${lineKey}`} type="date" value={date} onChange={event => { setDate(event.target.value); setEndDate(''); setEndTime(''); edit(); }}/></label>
        <label>From time<Input aria-label={`Booking time ${lineKey}`} type="time" value={time} onChange={event => { setTime(event.target.value); setEndDate(''); setEndTime(''); edit(); }}/></label>
        <label>To date<Input aria-label={`Booking end date ${lineKey}`} type="date" disabled={!policy.allow_duration_override} value={endDate} onChange={event => { setEndDate(event.target.value); edit(); }}/></label>
        <label>To time<Input aria-label={`Booking end time ${lineKey}`} type="time" disabled={!policy.allow_duration_override} value={endTime} onChange={event => { setEndTime(event.target.value); edit(); }}/></label>
        {context==='checkout' && specialist && date && <div className="sm:col-span-2 space-y-2" aria-label="Available appointment slots"><div className="flex items-center justify-between"><strong>Available times ({specialist.timezone})</strong><Button type="button" size="sm" variant="outline" disabled={availability.isFetching} onClick={()=>void availability.refetch()}>Refresh availability</Button></div>{availability.isFetching && <p role="status">Checking employee and resource availability...</p>}{availability.isError && <p role="alert">Availability could not be verified. {dealError(availability.error)} Refresh or choose a valid date and duration.</p>}{availability.data && <><div className="flex max-h-40 flex-wrap gap-2 overflow-auto">{availability.data.slots.map(slot=><Button type="button" key={slot.starts_at} size="sm" variant={startMatches[0]===Date.parse(slot.starts_at)?'default':'outline'} onClick={()=>{const start=wall(Date.parse(slot.starts_at),specialist.timezone);setDate(start.slice(0,10));setTime(start.slice(11));setEndDate('');setEndTime('');edit();}}>{slot.label}</Button>)}</div>{!availability.data.slots.length && <p>No available slots for these resources and duration. Choose another employee, resource or day.</p>}{availability.data.selection_available!==null && <p role="status">{availability.data.selection_available ? 'Selected interval is available. It will be checked again at checkout.' : 'Selected interval is unavailable. Choose another time or resource.'}</p>}</>}</div>}
        <p className="text-xs text-muted-foreground sm:col-span-2">Choose a To time or use the service duration. The interval must follow the configured duration limits.</p>
        {context === 'checkout' && !!options.data?.resources?.length && <fieldset className="space-y-2 sm:col-span-2"><legend>Rooms &amp; equipment (optional)</legend>{options.data.resources.map(resource => <label key={resource.id} className="flex items-center gap-2"><input type="checkbox" checked={resourceIds.includes(resource.id)} onChange={event => { setResourceIds(ids => event.target.checked ? [...ids, resource.id] : ids.filter(id => id !== resource.id)); edit(); }}/>{resource.name} - {resource.resource_type}{availability.data?.resources.find(item=>item.id===resource.id) ? availability.data.resources.find(item=>item.id===resource.id)!.available ? ' - Available' : ' - Unavailable for this appointment' : ' - Choose a time to check'}</label>)}</fieldset>}
        <label>Duration (minutes)<Input aria-label={`Booking duration ${lineKey}`} type="number" min={policy.min_duration_minutes} max={policy.max_duration_minutes} step={1} disabled={!policy.allow_duration_override} value={policy.allow_duration_override ? duration || policy.default_duration_minutes : policy.default_duration_minutes} onChange={event => { setDuration(event.target.value); setEndDate(''); setEndTime(''); edit(); }}/></label>
        <p className="self-center text-xs text-muted-foreground">Times use {specialist?.timezone || 'the selected provider’s timezone'}. Planned service time is separate from actual timesheet hours.</p>
        <Button type="button" className="justify-self-start" size="sm" variant="outline" disabled={!specialist || busy || options.isFetching || context==='checkout' && availability.data?.selection_available===false} onClick={apply}>Use these booking details</Button>
      </div>}
    </>}
    <div className="flex flex-wrap gap-2"><Button type="button" size="sm" variant="outline" disabled={options.isPending || busy} onClick={() => setConfig(config ? null : { employee_categories: policy?.employee_categories || [], service_product_id: productId, ...(policy ? { expected_revision: policy.revision } : {}), default_duration_minutes: policy?.default_duration_minutes || 30, min_duration_minutes: policy?.min_duration_minutes || 5, max_duration_minutes: policy?.max_duration_minutes || 720, booking_required: policy?.booking_required ?? false, allow_duration_override: policy?.allow_duration_override ?? false, active: policy?.active ?? true })}>{config ? 'Close scheduling configuration' : 'Configure service scheduling'}</Button><Button type="button" size="sm" variant="outline" disabled={options.isFetching || busy} onClick={() => void options.refetch()}>Reload scheduling options</Button></div>
    {configurationOnly && <Link className="inline-block text-primary underline" to="/srm/appointments">Manage appointments, employees, rooms &amp; equipment</Link>}
    {config && <div className="space-y-3 rounded border p-3" aria-label={`Scheduling configuration ${lineKey}`}>
      <p className="text-xs text-muted-foreground">Enable optional scheduling, set duration limits, and assign eligible employees for this service. Rooms and equipment are chosen with the booking.</p>
      <EmployeeCategories value={config.employee_categories} onChange={employee_categories=>setConfig({...config,employee_categories})}/>
      <div className="grid gap-3 sm:grid-cols-3">{(['default_duration_minutes', 'min_duration_minutes', 'max_duration_minutes'] as const).map(key => <label key={key}>{key.replace(/_/g, ' ')}<Input type="number" aria-label={`${key} ${lineKey}`} min={5} max={720} step={1} value={config[key]} disabled={busy} onChange={event => setConfig({ ...config, [key]: Number(event.target.value) })}/></label>)}</div>
      <div className="flex flex-wrap gap-3">{(['booking_required', 'allow_duration_override', 'active'] as const).map(key => <label key={key} className="flex items-center gap-2"><input type="checkbox" checked={config[key]} disabled={busy} onChange={event => setConfig({ ...config, [key]: event.target.checked })}/>{key.replace(/_/g, ' ')}</label>)}</div>
      <Button type="button" size="sm" disabled={busy} onClick={() => { if (config.min_duration_minutes < 5 || config.max_duration_minutes > 720 || config.default_duration_minutes < config.min_duration_minutes || config.default_duration_minutes > config.max_duration_minutes || ![config.default_duration_minutes, config.min_duration_minutes, config.max_duration_minutes].every(Number.isInteger)) { setError('Use whole-minute durations between 5 and 720, with the default inside the minimum and maximum.'); return; } configure.mutate(config); }}>{configure.isPending ? 'Saving…' : 'Save service policy'}</Button>
      {!!options.data?.specialists.length && <div className="space-y-1"><p className="font-medium">Eligible employees</p>{options.data.specialists.map(item => <p key={item.eligibility_id}>{item.employee_name} · {item.provider_name}</p>)}<p className="text-xs text-muted-foreground">Enable multiple employees below; choose one per appointment in the cart.</p></div>}
      {policy && <div className="space-y-2 border-t pt-3"><label>Find existing HRMS provider<Input aria-label={`Find provider ${lineKey}`} maxLength={100} value={providerSearch} onChange={event => { setProviderSearch(event.target.value); setCandidate(''); }}/></label><NativeSelect aria-label={`Eligible provider candidate ${lineKey}`} className={fields} value={candidate} loading={providers.isFetching} error={providers.isError} onChange={event => setCandidate(event.target.value)}><option value="">Choose existing provider</option>{providers.data?.providers.filter(item=>!config.employee_categories.length || item.work_categories?.some(category=>config.employee_categories.some(selected=>selected.toLowerCase()===category.toLowerCase()))).map(item => <option key={item.provider_resource_id} value={item.provider_resource_id}>{item.employee_name} · {item.provider_name} · {item.timezone}</option>)}</NativeSelect>{providers.data?.has_more && <p className="text-xs text-muted-foreground">Showing at most 100 providers. Narrow the search for more choices.</p>}{providers.isError && <p role="alert">{dealError(providers.error)} <Button type="button" size="sm" variant="outline" onClick={() => void providers.refetch()}>Retry providers</Button></p>}<Button type="button" size="sm" disabled={!candidate || busy || providers.isFetching} onClick={() => eligible.mutate()}>{eligible.isPending ? 'Saving…' : 'Enable specialist for this service'}</Button></div>}
    </div>}
    {value && <p role="status" className="rounded bg-muted p-2">Scheduled: {new Date(value.starts_at).toLocaleString()} – {new Date(Date.parse(value.starts_at) + value.duration_minutes * 60000).toLocaleString()} · {heldSpecialist?.employee_name || 'Assigned specialist'}{value.additional_resource_ids?.map(id => ` · ${options.data?.resources?.find(resource => resource.id === id)?.name || `Resource ${id}`}`).join('')}</p>}
    {error && <p role="alert">{error}</p>}{configure.isError && <p role="alert">{dealError(configure.error)} Reload service scheduling and review the policy before retrying.</p>}{eligible.isError && <p role="alert">{dealError(eligible.error)} Reload service scheduling before retrying eligibility.</p>}{notice && <p role="status">{notice}</p>}
  </section>;
}
