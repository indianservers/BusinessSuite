import { matchesCategory } from "@/shared/employee-category-taxonomy";
import POSAvailableTimes from './POSAvailableTimes';
import './pos-service-booking.css';
import BookingAlternatives, { type BookingChoice } from "@/shared/scheduling/BookingAlternatives";
import { SlotGroups } from "@/shared/scheduling/BookingUX";
import * as Dialog from "@radix-ui/react-dialog";
import { CalendarDays, Pencil, X } from "lucide-react";
import { useBusinessTerms } from "@/hooks/use-business-terms";
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
type Provider = { avatar_url?: string; provider_resource_id: number; employee_id: number; employee_name: string; provider_name: string; timezone: string; work_categories?: string[] };
export type Specialist = Provider & { eligibility_id: number; eligibility_revision: number };
export type Policy = { required_resource_types?: string[]; employee_categories?: string[]; id: number; revision: number; booking_required: boolean; default_duration_minutes: number; min_duration_minutes: number; max_duration_minutes: number; allow_duration_override: boolean; active: boolean };
export type Options = { can_configure?: boolean; branch_timezone?: string; service?: {name:string;price:string;currency:string;category:string}; resources?: {id: number; name: string; resource_type: string; capacity?: number; timezone?:string; opens?:string; closes?:string; weekdays?:number[]; location?:string; accessibility?:string; facilities?:string}[]; policy: Policy | null; specialists: Specialist[]; has_more: boolean };
type PolicyDraft = { required_resource_types?: string[]; employee_categories: string[]; service_product_id: number; expected_revision?: number; default_duration_minutes: number; min_duration_minutes: number; max_duration_minutes: number; booking_required: boolean; allow_duration_override: boolean; active: boolean };
type Props = { presentation?: 'cart' | 'dialog'; onResourceCapacities?: (capacities:Record<number,number>)=>void; compactSummary?: string; productId: number; lineKey: string; value?: BookingSelection; onChange: (value: BookingSelection | undefined) => void; onRequirement?: (required: boolean) => void; onSummary?: (summary:string)=>void; onAvailability?: (available:boolean|null)=>void; context?: 'checkout' | 'reschedule'; configurationOnly?: boolean };
const fields = 'h-10 w-full rounded-md border bg-background px-3 text-sm';
/** Draft configuration only. Native checkout creates the actual appointment. */
export default function POSServiceScheduling(props: Props) {
  const scope = useRecordScope();
  return <Scheduling key={`${scope}:${props.productId}:${props.lineKey}`} {...props} scope={scope}/>;
}
function Scheduling({ onResourceCapacities, compactSummary, productId, lineKey, value, onChange, onRequirement, onSummary, onAvailability, scope, context = 'checkout', configurationOnly = false, presentation = 'dialog' }: Props & { scope: string }) {
  const owns = useRecordScopeOwner();
  const { term } = useBusinessTerms();
  const [windowOpen, setWindowOpen] = useState(false);
  const [inlineExpanded,setInlineExpanded]=useState(!value);
  const [compactTab,setCompactTab]=useState<'booking'|'times'|'resources'|'staff'>('booking');
  const [resourcePage,setResourcePage]=useState(0);
  useEffect(()=>{setCompactTab('booking');setResourcePage(0);},[presentation]);
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
  const resourceCallback = useRef(onResourceCapacities); resourceCallback.current = onResourceCapacities;
  useEffect(()=>{if(options.data?.resources) resourceCallback.current?.(Object.fromEntries(options.data.resources.map(resource=>[resource.id,resource.capacity || 1])));},[options.data?.resources]);
  const [alternative,setAlternative]=useState<BookingChoice>();
  const policy = options.data?.policy;
  const specialist = options.data?.specialists.find(item => String(item.eligibility_id) === selected) || (String(alternative?.eligibility_id)===selected?alternative:undefined);
  const heldSpecialist = options.data?.specialists.find(item => item.eligibility_id === value?.eligibility_id) || (alternative?.eligibility_id===value?.eligibility_id?alternative:undefined);
  const summaryCallback = useRef(onSummary);summaryCallback.current=onSummary;
  useEffect(()=>{if(!value || !heldSpecialist)return;const format=new Intl.DateTimeFormat(undefined,{timeZone:heldSpecialist.timezone,dateStyle:'medium',timeStyle:'short'});summaryCallback.current?.(`${heldSpecialist.employee_name} - ${format.format(new Date(value.starts_at))} to ${format.format(new Date(Date.parse(value.starts_at)+value.duration_minutes*60000))} (${heldSpecialist.timezone})${value.additional_resource_ids?.map(id=>` - ${options.data?.resources?.find(resource=>resource.id===id)?.name || `Resource ${id}`}`).join('') || ''}`);},[value,heldSpecialist,options.data?.resources]);
  const providers = useQuery({ queryKey: ['pos-service-provider-options', scope, deferredProvider], queryFn: ({ signal }) => api.get<{ providers: Provider[]; has_more: boolean }>('/srm/service-checkout/options/providers', { signal, params: { search: deferredProvider || undefined } }).then(result => result.data), enabled: !!config, retry: false });
  const startMatches = specialist && date && time ? candidates(`${date}T${time}`,specialist.timezone) : [];
  const endMatches = specialist && endDate && endTime ? candidates(`${endDate}T${endTime}`,specialist.timezone) : [];
  const requestedMinutes = startMatches.length===1 && endMatches.length===1 ? (endMatches[0]-startMatches[0])/60000 : Number(duration || policy?.default_duration_minutes || 30);
  const durationValid=!!policy&&Number.isInteger(requestedMinutes)&&requestedMinutes>=policy.min_duration_minutes&&requestedMinutes<=policy.max_duration_minutes&&(policy.allow_duration_override||requestedMinutes===policy.default_duration_minutes);
  const selectionProof = useRef(''), mounted = useRef(true);
  selectionProof.current = JSON.stringify([productId, selected, date, time, duration, endDate, endTime, resourceIds, policy?.revision]);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  type Availability = {conflicts?: {resource_id:number;name:string;message:string}[];slots:{starts_at:string;label:string}[];timezone:string;selection_available:boolean|null;resources:{id:number;available:boolean;capacity?:number;remaining_capacity?:number}[]};
  const availability = useQuery({queryKey:['pos-service-availability',scope,productId,selected,date,time,requestedMinutes,resourceIds.join(',')],
    enabled:context==='checkout' && !configurationOnly && !!specialist && !!date && !!policy?.active && durationValid,
    queryFn:({signal})=>{const params=new URLSearchParams({service_id:String(productId),eligibility_id:selected,day:date,duration_minutes:String(requestedMinutes)});resourceIds.forEach(id=>params.append('resource_ids',String(id)));if(startMatches.length===1)params.set('starts_at',new Date(startMatches[0]).toISOString());return api.get<Availability>('/srm/service-checkout/options/availability',{signal,params,recordCache:false}).then(response=>response.data);},retry:false,staleTime:0,placeholderData:(previous,query)=>[1,2,3,4,6,7].every(index=>query?.queryKey[index]===['pos-service-availability',scope,productId,selected,date,time,requestedMinutes,resourceIds.join(',')][index])?previous:undefined});
  const availabilityContext=JSON.stringify([scope,productId,selected,date,requestedMinutes,resourceIds]);
  const retainedSlots=useRef<{context:string;slots:Availability['slots']}>();
  useEffect(()=>{if(availability.isSuccess&&!availability.isPlaceholderData)retainedSlots.current={context:availabilityContext,slots:availability.data.slots};},[availability.isSuccess,availability.isPlaceholderData,availability.data,availabilityContext]);
  const visibleSlots=availability.data?.slots ?? (retainedSlots.current?.context===availabilityContext?retainedSlots.current.slots:[]);
  const suggested = useRef(!!value);
  useEffect(()=>{if(suggested.current || value || !options.data?.policy?.active || !options.data.specialists.length)return;suggested.current=true;const first=options.data.specialists[0];setSelected(String(first.eligibility_id));setDate(wall(Date.now(),first.timezone).slice(0,10));setDuration(String(options.data.policy.default_duration_minutes));setResourceIds([...new Set((options.data.policy.required_resource_types || []).flatMap(type=>{const resource=options.data?.resources?.find(r=>r.resource_type===type);return resource?[resource.id]:[];}))]);},[options.data,value]);
  useEffect(()=>{if(value || time || !specialist || !availability.data?.slots.length)return;const first=wall(Date.parse(availability.data.slots[0].starts_at),specialist.timezone);setDate(first.slice(0,10));setTime(first.slice(11));},[availability.data?.slots,specialist,value,time]);
  const availabilityCallback=useRef(onAvailability);availabilityCallback.current=onAvailability;
  useEffect(()=>{availabilityCallback.current?.(value && availability.isSuccess && !availability.isFetching && !availability.isPlaceholderData ? availability.data.selection_available : null);},[value,availability.isSuccess,availability.isFetching,availability.isPlaceholderData,availability.data?.selection_available]);
  useEffect(()=>{
    if(!specialist || !date || !time || endDate || endTime)return;
    const matches=candidates(`${date}T${time}`,specialist.timezone),minutes=policy?.allow_duration_override ? Number(duration || policy.default_duration_minutes) : policy?.default_duration_minutes;
    if(matches.length!==1 || !minutes || !Number.isFinite(minutes))return;
    const end=wall(matches[0]+minutes*60000,specialist.timezone);setEndDate(end.slice(0,10));setEndTime(end.slice(11));
  },[date,time,duration,specialist,policy,endDate,endTime]);

  useEffect(() => { if (options.isSuccess) requirementCallback.current?.(!!policy?.booking_required || enabled || !!value); }, [options.isSuccess, policy?.booking_required, enabled, value]);
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
  const eligible = useMutation({ mutationFn: async (remove?: Specialist) => {
    const provider = remove ?? providers.data?.providers.find(item => String(item.provider_resource_id) === candidate);
    if (!provider || !policy) throw new Error('Choose a current provider and save the policy first.');
    const previous = options.data?.specialists.find(item => item.provider_resource_id === provider.provider_resource_id && item.employee_id === provider.employee_id);
    return api.put('/srm/service-checkout/eligibility', { policy_id: policy.id, expected_policy_revision: policy.revision, provider_resource_id: provider.provider_resource_id, employee_id: provider.employee_id, active: !remove, ...(previous ? { expected_revision: previous.eligibility_revision } : {}) });
  }, onSuccess: async (_, remove) => { if (!owns()) return; await options.refetch(); if (owns()) setNotice(remove ? "Employee removed from this service." : configurationOnly ? "Employee enabled for this service." : context === 'reschedule' ? 'Existing HRMS provider enabled for this service. Select the specialist for the new schedule.' : 'Existing HRMS provider enabled for this service. Select the specialist to schedule this cart line.'); } });
  const busy = configure.isPending || eligible.isPending;
  async function apply() {
    if (context === 'checkout') {
      const proof = selectionProof.current;
      const checked = await availability.refetch();
      if (!mounted.current || !owns() || proof !== selectionProof.current) return;
      if (checked.isError) {setError('Could not verify times. Refresh to retry.');return;}
      if (checked.data?.selection_available !== true) {setError('Time or resource unavailable.');return;}
    }
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
    setWindowOpen(false); setInlineExpanded(false); setEdited(false); setNotice(context === 'reschedule' ? 'Booking details applied. Save the new schedule to update the appointment.' : 'Booking details applied to this cart line. The appointment is created when checkout succeeds.');
  }
  const required = !!policy?.booking_required, show = required || enabled || !!value;
  const panel = <section className="min-w-0 space-y-3 rounded border p-3 text-sm" aria-label={`Service scheduling ${lineKey}`}>
    {!configurationOnly && <p className="text-xs text-muted-foreground">Choose an eligible provider, time and required resources.</p>}
    {options.isPending && <p role="status">Loading service scheduling…</p>}
    {options.isError && <p role="alert">{dealError(options.error)} <Button type="button" variant="outline" size="sm" onClick={() => void options.refetch()}>Retry scheduling</Button></p>}
    {options.isSuccess && !configurationOnly && <>
      {required ? <p className="font-medium">Appointment required for this service</p> : <label className="flex items-center gap-2"><input type="checkbox" checked={show} disabled={!policy?.active || busy} onChange={event => { setEnabled(event.target.checked); edit(); }}/><span>Schedule this service</span></label>}
      {!policy?.active && <p className="text-xs text-muted-foreground">{policy ? 'Scheduling is inactive for this service.' : 'This service has no scheduling policy yet.'}</p>}
      {!!policy?.employee_categories?.length && <p className="text-xs text-muted-foreground">Employee categories: {policy.employee_categories.join(", ")}</p>}
      {show && policy?.active && <div className="grid gap-3 sm:grid-cols-2">
        <details className="sm:col-span-2 pos-eligible-filters"><summary>Filter eligible staff</summary>        <div className="sm:col-span-2"><EmployeeCategories value={categoryFilters} options={[...new Set([...(policy.employee_categories || []),...(options.data?.specialists.flatMap(item=>item.work_categories || []) || [])])]} onChange={values=>{setCategoryFilters(values);if(specialist && values.length && !specialist.work_categories?.some(category=>values.includes(category))){setSelected('');edit();}}}/></div>
        <label>Find {term("provider").toLowerCase()}<Input aria-label={`Find specialist ${lineKey}`} maxLength={100} value={search} onChange={event => setSearch(event.target.value)}/></label>
</details>
        <label>{term("provider")}<NativeSelect aria-label={`Specialist ${lineKey}`} className={fields} value={selected} disabled={busy || options.isFetching} onChange={event => { setSelected(event.target.value); const next = options.data?.specialists.find(item => String(item.eligibility_id) === event.target.value); if (value && next) { try { const local = wall(Date.parse(value.starts_at), next.timezone); setDate(local.slice(0, 10)); setTime(local.slice(11)); } catch { setError('Provider timezone is invalid. Choose another specialist.'); } } if (!duration) setDuration(String(policy.default_duration_minutes)); if(next && !date)setDate(wall(Date.now(),next.timezone).slice(0,10)); setEndDate('');setEndTime('');edit(); }}><option value="">Choose eligible employee</option>{selected && !specialist && <option value={selected}>Previously selected specialist · search or reselect to verify</option>}{options.data?.specialists.filter(item=>!categoryFilters.length || categoryFilters.some(category=>matchesCategory(item.work_categories,category))).map(item => <option key={item.eligibility_id} value={item.eligibility_id}>{item.employee_name} · {item.provider_name} · {item.timezone}</option>)}</NativeSelect>{specialist && <span className="pos-provider-identity"><span className="pos-provider-avatar">{specialist.avatar_url ? <img src={specialist.avatar_url} alt="" referrerPolicy="no-referrer"/> : specialist.employee_name.split(' ').slice(0,2).map(part=>part[0]).join('')}</span><span><strong>{specialist.employee_name}</strong><small>{specialist.work_categories?.join(', ') || specialist.provider_name}</small></span></span>}</label>
        {options.data?.has_more && <p className="text-xs text-muted-foreground sm:col-span-2">Showing at most 100 eligible specialists. Narrow the specialist search to find another match.</p>}
        <label>From date<Input aria-label={`Booking date ${lineKey}`} type="date" value={date} onChange={event => { setDate(event.target.value); setEndDate(''); setEndTime(''); edit(); }}/></label>
        <label>From time<Input aria-label={`Booking time ${lineKey}`} type="time" value={time} onChange={event => { setTime(event.target.value); setEndDate(''); setEndTime(''); edit(); }}/></label>
        <details className="sm:col-span-2"><summary>Custom end time</summary><div className="grid gap-3 sm:grid-cols-2">        <label>To date<Input aria-label={`Booking end date ${lineKey}`} type="date" disabled={!policy.allow_duration_override} value={endDate} onChange={event => { setEndDate(event.target.value); edit(); }}/></label>
        <label>To time<Input aria-label={`Booking end time ${lineKey}`} type="time" disabled={!policy.allow_duration_override} value={endTime} onChange={event => { setEndTime(event.target.value); edit(); }}/></label>
</div></details>
        {context==='checkout' && specialist && date && <div className="sm:col-span-2 space-y-2" aria-label="Available appointment slots"><div className="flex items-center justify-between"><strong>Available times ({specialist.timezone})</strong><Button type="button" size="sm" variant="outline" disabled={availability.isFetching} onClick={()=>{setError('');void availability.refetch();}}>Refresh availability</Button></div>{availability.isFetching && <p role="status">Checking employee and resource availability...</p>}{availability.isError && <p role="alert">Availability could not be verified. {dealError(availability.error)} Refresh or choose a valid date and duration.</p>}{availability.data && <><SlotGroups slots={availability.data.slots} zone={specialist.timezone} minutes={requestedMinutes} selected={startMatches.length===1?new Date(startMatches[0]).toISOString():undefined} onSelect={instant=>{const start=wall(Date.parse(instant),specialist.timezone);setDate(start.slice(0,10));setTime(start.slice(11));setEndDate('');setEndTime('');edit();}}/>{!availability.data.slots.length && <p>No available slots for these resources and duration. Choose another employee, resource or day.</p>}{availability.data.selection_available!==null && <p role="status">{availability.data.selection_available ? 'Selected interval is available. It will be checked again at checkout.' : 'Selected interval is unavailable. Choose another time or resource.'}</p>}</>}</div>}
        <p className="text-xs text-muted-foreground sm:col-span-2">Choose a To time or use the service duration. The interval must follow the configured duration limits.</p>
        {context === 'checkout' && !!options.data?.resources?.length && <fieldset className="space-y-2 sm:col-span-2"><legend>Rooms &amp; equipment</legend><p className="text-xs text-muted-foreground">{policy.required_resource_types?.length ? `Required: ${policy.required_resource_types.join(', ')}. Other types are optional.` : 'Additional resources are optional for this service.'}</p>{options.data.resources.map(resource => <label key={resource.id} className="flex items-center gap-2"><input type="checkbox" checked={resourceIds.includes(resource.id)} onChange={event => { setResourceIds(ids => event.target.checked ? [...ids, resource.id] : ids.filter(id => id !== resource.id)); edit(); }}/>{resource.name} - {resource.resource_type}{(() => {const state=availability.data?.resources.find(r=>r.id===resource.id);return state?.capacity && state.capacity>1 ? <small className="resource-capacity"> · {state.remaining_capacity} of {state.capacity} places available</small> : null;})()}{availability.data?.resources.find(item=>item.id===resource.id) ? availability.data.resources.find(item=>item.id===resource.id)!.available ? ' - Available' : ' - Unavailable for this appointment' : ' - Choose a time to check'}</label>)}</fieldset>}
        <label>Duration (minutes)<Input aria-label={`Booking duration ${lineKey}`} type="number" min={policy.min_duration_minutes} max={policy.max_duration_minutes} step={1} disabled={!policy.allow_duration_override} value={policy.allow_duration_override ? duration || policy.default_duration_minutes : policy.default_duration_minutes} onChange={event => { setDuration(event.target.value); setEndDate(''); setEndTime(''); edit(); }}/></label>
        <p className="self-center text-xs text-muted-foreground">Timezone: {specialist?.timezone || 'choose a provider'}.</p>
        <p id={`booking-apply-reason-${lineKey}`} className="sm:col-span-2 text-xs" role="status">{!specialist ? 'Choose an eligible provider.' : !date || !time ? 'Choose a date and available time.' : availability.isFetching ? 'Checking availability…' : availability.isError ? 'Retry the availability check.' : availability.data?.selection_available===false ? 'Resolve the resource or employee conflict.' : 'Suggested details are not reserved until you confirm the sale.'}</p>
        <Button aria-describedby={`booking-apply-reason-${lineKey}`} type="button" className="justify-self-start" size="sm" variant="outline" disabled={!specialist || busy || options.isFetching || context==='checkout' && (availability.isFetching || !availability.isSuccess || availability.data.selection_available!==true)} onClick={apply}>Use these booking details</Button>
      </div>}
    </>}
    <details className="pos-scheduling-setup"><summary>Scheduling setup</summary>    <div className="flex flex-wrap gap-2"><Button type="button" size="sm" variant="outline" disabled={options.isPending || busy} onClick={() => setConfig(config ? null : { required_resource_types: policy?.required_resource_types || [], employee_categories: policy?.employee_categories || [], service_product_id: productId, ...(policy ? { expected_revision: policy.revision } : {}), default_duration_minutes: policy?.default_duration_minutes || 30, min_duration_minutes: policy?.min_duration_minutes || 5, max_duration_minutes: policy?.max_duration_minutes || 720, booking_required: policy?.booking_required ?? false, allow_duration_override: policy?.allow_duration_override ?? false, active: policy?.active ?? true })}>{config ? 'Close scheduling configuration' : 'Configure service scheduling'}</Button><Button type="button" size="sm" variant="outline" disabled={options.isFetching || busy} onClick={() => void options.refetch()}>Reload scheduling options</Button></div>
</details>
    {availability.data?.selection_available===false && specialist && startMatches.length===1 && <BookingAlternatives zone={specialist.timezone} serviceId={productId} start={new Date(startMatches[0]).toISOString()} minutes={requestedMinutes} employeeId={specialist.employee_id} resourceIds={resourceIds} onChoose={choice=>{setAlternative(choice);setSelected(String(choice.eligibility_id));const local=wall(Date.parse(choice.starts_at),choice.timezone);setDate(local.slice(0,10));setTime(local.slice(11));setResourceIds(choice.resource_ids);setEndDate('');setEndTime('');edit();}}/>}
    {configurationOnly && <Link className="inline-block text-primary underline" to="/srm/appointments">Manage appointments, employees, rooms &amp; equipment</Link>}
    {config && <div className="space-y-3 rounded border p-3" aria-label={`Scheduling configuration ${lineKey}`}>
      <p className="text-xs text-muted-foreground">Enable optional scheduling, set duration limits, and assign eligible employees for this service. Rooms and equipment are chosen with the booking.</p>
      <fieldset className="flex flex-wrap gap-3"><legend>Required resource types</legend>{['room','chair','equipment','location'].map(type => <label key={type}><input type="checkbox" checked={config.required_resource_types?.includes(type) || false} onChange={e => setConfig({...config,required_resource_types:e.target.checked ? [...(config.required_resource_types || []),type] : (config.required_resource_types || []).filter(t => t !== type)})}/>{type}</label>)}</fieldset>
      <EmployeeCategories value={config.employee_categories} onChange={employee_categories=>setConfig({...config,employee_categories})}/>
      <div className="grid gap-3 sm:grid-cols-3">{(['default_duration_minutes', 'min_duration_minutes', 'max_duration_minutes'] as const).map(key => <label key={key}>{key.replace(/_/g, ' ')}<Input type="number" aria-label={`${key} ${lineKey}`} min={5} max={720} step={1} value={config[key]} disabled={busy} onChange={event => setConfig({ ...config, [key]: Number(event.target.value) })}/></label>)}</div>
      <div className="flex flex-wrap gap-3">{(['booking_required', 'allow_duration_override', 'active'] as const).map(key => <label key={key} className="flex items-center gap-2"><input type="checkbox" checked={config[key]} disabled={busy} onChange={event => setConfig({ ...config, [key]: event.target.checked })}/>{key.replace(/_/g, ' ')}</label>)}</div>
      <Button type="button" size="sm" disabled={busy} onClick={() => { if (config.min_duration_minutes < 5 || config.max_duration_minutes > 720 || config.default_duration_minutes < config.min_duration_minutes || config.default_duration_minutes > config.max_duration_minutes || ![config.default_duration_minutes, config.min_duration_minutes, config.max_duration_minutes].every(Number.isInteger)) { setError('Use whole-minute durations between 5 and 720, with the default inside the minimum and maximum.'); return; } configure.mutate(config); }}>{configure.isPending ? 'Saving…' : 'Save service policy'}</Button>
      {!!options.data?.specialists.length && <div className="space-y-1"><p className="font-medium">Eligible employees</p>{options.data.specialists.map(item => <div className="flex flex-wrap items-center justify-between gap-2" key={item.eligibility_id}>
          <span>{item.employee_name} / {item.provider_name}</span>
          {configurationOnly && <Button type="button" size="sm" variant="outline" disabled={busy || options.isFetching} aria-label={`Remove ${item.employee_name} from this service`} onClick={() => eligible.mutate(item)}>Remove</Button>}
        </div>)}<p className="text-xs text-muted-foreground">Enable multiple employees below; choose one per appointment in the cart.</p></div>}
      {policy && <div className="space-y-2 border-t pt-3"><label>Find existing HRMS provider<Input aria-label={`Find provider ${lineKey}`} maxLength={100} value={providerSearch} onChange={event => { setProviderSearch(event.target.value); setCandidate(''); }}/></label><NativeSelect aria-label={`Eligible provider candidate ${lineKey}`} className={fields} value={candidate} loading={providers.isFetching} error={providers.isError} onChange={event => setCandidate(event.target.value)}><option value="">Choose existing provider</option>{providers.data?.providers.filter(item=>!config.employee_categories.length || config.employee_categories.some(selected=>matchesCategory(item.work_categories,selected))).map(item => <option key={item.provider_resource_id} value={item.provider_resource_id}>{item.employee_name} · {item.provider_name} · {item.timezone}</option>)}</NativeSelect>{providers.data?.has_more && <p className="text-xs text-muted-foreground">Showing at most 100 providers. Narrow the search for more choices.</p>}{providers.isError && <p role="alert">{dealError(providers.error)} <Button type="button" size="sm" variant="outline" onClick={() => void providers.refetch()}>Retry providers</Button></p>}<Button type="button" size="sm" disabled={!candidate || busy || providers.isFetching} onClick={() => eligible.mutate(undefined)}>{eligible.isPending ? 'Saving…' : 'Enable specialist for this service'}</Button></div>}
    </div>}
    {value && <p role="status" className="rounded bg-muted p-2">Scheduled: {new Date(value.starts_at).toLocaleString()} – {new Date(Date.parse(value.starts_at) + value.duration_minutes * 60000).toLocaleString()} · {heldSpecialist?.employee_name || 'Assigned specialist'}{value.additional_resource_ids?.map(id => ` · ${options.data?.resources?.find(resource => resource.id === id)?.name || `Resource ${id}`}`).join('')}</p>}
    {error && <p role="alert">{error}</p>}{configure.isError && <p role="alert">{dealError(configure.error)} Reload service scheduling and review the policy before retrying.</p>}{eligible.isError && <p role="alert">{dealError(eligible.error)} Reload service scheduling before retrying eligibility.</p>}{notice && <p role="status">{notice}</p>}
  </section>;
  const compactSlotsKey=availabilityContext;
  const resourcePageSize=presentation==='cart'?2:6;
  const chooseSlot=(instant:string)=>{if(!specialist)return;const start=wall(Date.parse(instant),specialist.timezone);setDate(start.slice(0,10));setTime(start.slice(11));setEndDate('');setEndTime('');edit();};
  const compactPanel=<section className="pos-compact-booking" aria-label={`Service scheduling ${lineKey}`} data-presentation={presentation} data-step={compactTab}>
    {presentation==='cart'&&<strong className="pos-compact-title">Service booking</strong>}
    {options.isPending?<p role="status">Loading service scheduling…</p>:options.isError?<p role="alert">{dealError(options.error)} <Button type="button" size="sm" onClick={()=>void options.refetch()}>Retry scheduling</Button></p>:<>
      {!required&&<label className="pos-compact-enable"><input type="checkbox" checked={show} disabled={!policy?.active||busy} onChange={event=>{setEnabled(event.target.checked);edit();}}/>Schedule this service</label>}
      {!policy?.active?<p>No active scheduling policy. <Link to="/srm/service-scheduling?view=guide">Open scheduling setup</Link></p>:show&&<>
        <nav className="pos-compact-tabs" aria-label="Booking sections">{(presentation==='cart'?['booking','times','resources','staff'] as const:['booking','resources','staff'] as const).filter(tab=>tab!=='resources'||!!options.data?.resources?.length).map(tab=><button type="button" key={tab} aria-pressed={compactTab===tab} onClick={()=>setCompactTab(tab)}>{tab==='booking'?(presentation==='cart'?'Employee':'Employee & time'):tab==='times'?'Time':tab==='resources'?(presentation==='cart'?'Resources':`Resources (${resourceIds.length})`):'Find staff'}</button>)}</nav>
        {(compactTab==='booking'||compactTab==='times')&&<>
          <div className="pos-compact-fields">
            {(presentation!=='cart'||compactTab==='booking')&&<><label>Employee<NativeSelect aria-label={`Specialist ${lineKey}`} value={selected} disabled={busy||options.isFetching} onChange={event=>{setSelected(event.target.value);setEndDate('');setEndTime('');edit();}}><option value="">Choose employee</option>{options.data?.specialists.filter(item=>!categoryFilters.length||categoryFilters.some(category=>matchesCategory(item.work_categories,category))).map(item=><option key={item.eligibility_id} value={item.eligibility_id}>{item.employee_name}</option>)}</NativeSelect></label>
            <label>Duration (minutes)<Input aria-label={`Booking duration ${lineKey}`} type="number" min={policy.min_duration_minutes} max={policy.max_duration_minutes} disabled={!policy.allow_duration_override} value={duration||policy.default_duration_minutes} onChange={event=>{setDuration(event.target.value);setEndDate('');setEndTime('');edit();}}/></label></>}
            {(presentation!=='cart'||compactTab==='times')&&<><label>Date<Input aria-label={`Booking date ${lineKey}`} type="date" value={date} onChange={event=>{setDate(event.target.value);setTime('');setEndDate('');setEndTime('');edit();}}/></label>
            {presentation==='cart'?<label>Available times<NativeSelect aria-label={`Available times ${lineKey}`} value={startMatches.length===1?new Date(startMatches[0]).toISOString():''} onChange={event=>{if(event.target.value)chooseSlot(event.target.value);}}><option value="">Choose a time</option>{time&&startMatches.length===1&&!visibleSlots.some(slot=>Date.parse(slot.starts_at)===startMatches[0])&&<option value={new Date(startMatches[0]).toISOString()}>{time}</option>}{visibleSlots.map(slot=><option key={slot.starts_at} value={new Date(slot.starts_at).toISOString()}>{slot.label}</option>)}</NativeSelect></label>:<label>Time<Input aria-label={`Booking time ${lineKey}`} type="time" value={time} onChange={event=>{setTime(event.target.value);setEndDate('');setEndTime('');edit();}}/></label>}</>}
          </div>
          <section className="pos-compact-availability" aria-label="Available appointment slots" aria-busy={availability.isFetching}>
            {(presentation!=='cart'||compactTab==='times')&&<div className="pos-compact-availability-heading"><strong>Available times</strong><button type="button" disabled={!specialist||!date||availability.isFetching} onClick={()=>{setError('');void availability.refetch();}}>Refresh</button></div>}
            <small>{presentation==='cart'&&specialist&&startMatches.length===1?`${new Intl.DateTimeFormat(undefined,{timeZone:specialist.timezone,dateStyle:'medium',timeStyle:'short'}).format(startMatches[0])} · ${specialist.timezone}`:specialist?.timezone||'Choose an employee and date'}</small>
            {presentation!=='cart'&&<POSAvailableTimes slots={visibleSlots} selected={startMatches.length===1?new Date(startMatches[0]).toISOString():undefined} minutes={requestedMinutes} zone={specialist?.timezone||'UTC'} contextKey={compactSlotsKey} onSelect={chooseSlot}/>}
            <p className="pos-compact-availability-state" role={error||availability.isError||!durationValid?'alert':'status'}>{error || (availability.isFetching?'Checking availability…':availability.isError?'Could not verify times. Refresh to retry.':!specialist?'Choose an eligible employee.':!date?'Choose a date.':!durationValid?`Use ${policy.min_duration_minutes}–${policy.max_duration_minutes} minutes.`:availability.data?.selection_available===false?'Time unavailable. Choose another.':availability.data?.selection_available===true?'Employee and resources are available.':availability.isSuccess&&!availability.data.slots.length?'No available times. Try another day.':'Choose an available time.')}</p>
          </section>
        </>}
        {compactTab==='resources'&&<div className="pos-compact-resources"><strong>Rooms & equipment</strong><small>{policy.required_resource_types?.length?`Required: ${policy.required_resource_types.join(', ')}`:'Optional resources'}</small><div>{options.data?.resources?.slice(resourcePage*resourcePageSize,(resourcePage+1)*resourcePageSize).map(resource=><label key={resource.id}><input type="checkbox" checked={resourceIds.includes(resource.id)} onChange={event=>{setResourceIds(ids=>event.target.checked?[...ids,resource.id]:ids.filter(id=>id!==resource.id));edit();}}/><span title={resource.name}>{resource.name}</span></label>)}</div>{(options.data?.resources?.length||0)>resourcePageSize&&<nav><Button type="button" variant="ghost" size="sm" disabled={resourcePage===0} onClick={()=>setResourcePage(page=>page-1)}>Previous resources</Button><Button type="button" variant="ghost" size="sm" disabled={(resourcePage+1)*resourcePageSize>=(options.data?.resources?.length||0)} onClick={()=>setResourcePage(page=>page+1)}>Next resources</Button></nav>}</div>}
        {compactTab==='staff'&&<div className="pos-compact-staff"><label>Find eligible employee<Input aria-label={`Find specialist ${lineKey}`} value={search} maxLength={100} onChange={event=>setSearch(event.target.value)}/></label><label>Employee category<NativeSelect value={categoryFilters[0]||''} onChange={event=>{const categories=event.target.value?[event.target.value]:[];setCategoryFilters(categories);if(specialist&&categories.length&&!categories.some(category=>matchesCategory(specialist.work_categories,category))){setSelected('');edit();}}}><option value="">All eligible categories</option>{[...new Set([...(policy.employee_categories||[]),...(options.data?.specialists.flatMap(item=>item.work_categories||[])||[])])].map(category=><option key={category}>{category}</option>)}</NativeSelect></label><p>Search, then choose an employee.</p></div>}
        <footer className="pos-compact-booking-footer"><Button type="button" size="sm" disabled={!specialist||!date||!time||!durationValid||busy||options.isFetching||availability.isFetching||!availability.isSuccess||availability.data.selection_available!==true} onClick={apply}>Use these booking details</Button>{value&&!edited&&<small>Applied to cart</small>}</footer>
      </>}
    </>}
    {error&&compactTab!=='booking'&&compactTab!=='times'&&<p role="alert" className="pos-compact-error">{error}</p>}
  </section>;
  if (!compactSummary) return panel;
  if(presentation==='cart'&&context==='checkout'&&!configurationOnly){if(value&&!inlineExpanded)return <button type="button" className="pos-inline-booking-edit" onClick={()=>{setInlineExpanded(true);setCompactTab('booking');}}>Edit employee &amp; time</button>;return compactPanel;}
  return <Dialog.Root open={windowOpen} onOpenChange={setWindowOpen}>
    <Dialog.Trigger asChild><button type="button" className="pos-booking-trigger">{compactSummary==='Edit'?<Pencil size={18}/>:<CalendarDays size={18}/>}<span>{compactSummary}</span><span>Edit</span></button></Dialog.Trigger>
    <Dialog.Portal><Dialog.Overlay className="pos-booking-overlay"/><Dialog.Content className="pos-booking-window" aria-describedby={undefined}>
      <div className="pos-booking-window-heading"><Dialog.Title>Service booking</Dialog.Title><Dialog.Close asChild><Button variant="ghost" size="icon" aria-label="Close service booking"><X size={18}/></Button></Dialog.Close></div>
      {context==='checkout'&&!configurationOnly?compactPanel:panel}
    </Dialog.Content></Dialog.Portal>
  </Dialog.Root>;

}
