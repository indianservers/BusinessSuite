import { SlotGroups } from "./BookingUX";
import { useDeferredValue, useEffect, useMemo, useRef, useState, type MutableRefObject } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { useRecordScope } from '@/lib/record-scope';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import type { BookingSelection, Options, Specialist } from '@/apps/srm/industry/POSServiceScheduling';
import SmartRecordPicker from '@/shared/records/SmartRecordPicker';
import { Link } from 'react-router-dom';
import { useBusinessTerms } from '@/hooks/use-business-terms';
import { defaultText } from '@/lib/form-defaults';
import type {ScheduleDraft} from './prebooking-state';
import { candidates, wall } from './booking-time';

export type BookingSlot = { startsAt: string; employeeId?: number; resourceId?: number; key: string };
type Availability = {checked_at?:string; selection_available: boolean | null; conflicts?: { resource_id: number; name: string; message: string }[]; resources: { id: number; available: boolean; capacity?:number; remaining_capacity?:number }[]; slots: { starts_at: string; label: string }[] };
export type BookingDisplay = {employee:string;timezone:string;resources:string[];startsAt?:string;minutes?:number};
type Props = {initialDraft?:ScheduleDraft;onDraftChange?:(draft:ScheduleDraft)=>void;validateRef?:MutableRefObject<(()=>Promise<BookingSelection|undefined>)|null>;onDisplay?: (display:BookingDisplay)=>void; serviceId: number; prefill?: BookingSlot; onChange: (value: BookingSelection | undefined) => void; onAvailability: (value: boolean | null) => void; onReason: (reason: string) => void };

/** Uses the same authoritative options and availability endpoints as POS. */
export default function PrebookingFields({ serviceId, prefill, onChange, onAvailability, onReason, onDisplay, initialDraft, onDraftChange, validateRef }: Props) {
  const scope = useRecordScope();
  const {term} = useBusinessTerms();
  const callbacks = useRef({ onChange, onAvailability, onReason, onDisplay, onDraftChange });
  callbacks.current = { onChange, onAvailability, onReason, onDisplay, onDraftChange };
  const [employee, setEmployee] = useState(''), [date, setDate] = useState(initialDraft?.date || ''), [time, setTime] = useState(initialDraft?.time || '');
  const [duration, setDuration] = useState(initialDraft?.duration || ''), [resources, setResources] = useState<number[]>(initialDraft?.resources || []);
  const [editDuration, setEditDuration] = useState(false), [employeeSearch, setEmployeeSearch] = useState(''), [category, setCategory] = useState('');
  const [chosenEmployee, setChosenEmployee] = useState<Specialist>();
  const [resourceSearch, setResourceSearch] = useState<Record<string,string>>({});
  const [anyStaff,setAnyStaff]=useState(false),[discoveryRequested,setDiscoveryRequested]=useState(false),[employeeOffset,setEmployeeOffset]=useState(0),[resourceOffset,setResourceOffset]=useState(0),[searchDays,setSearchDays]=useState(1);
  const [carryNotice,setCarryNotice]=useState(''),[clock,setClock]=useState(Date.now());
  const rememberedEmployee=useRef(initialDraft?.employeeId),carryInstant=useRef<string>();
  const sectionRef=useRef<HTMLElement>(null),lastService=useRef<number>();
  useEffect(()=>{const id=setInterval(()=>setClock(Date.now()),10000);return()=>clearInterval(id);},[]);
  const deferredSearch = useDeferredValue(employeeSearch);
  const options = useQuery({ queryKey: ['prebooking-options', scope, serviceId], enabled: serviceId > 0, retry: false,
    queryFn: ({ signal }) => api.get<Options>('/srm/service-checkout/options', { signal, recordCache: false, params: { service_id: serviceId } }).then(r => r.data) });
  const employeeResults = useQuery({queryKey:['prebooking-employee-search',scope,serviceId,deferredSearch],enabled:serviceId>0 && !!deferredSearch.trim(),retry:false,
    queryFn:({signal})=>api.get<Options>('/srm/service-checkout/options',{signal,recordCache:false,params:{service_id:serviceId,search:deferredSearch}}).then(r=>r.data)});
  const choices = employeeSearch.trim() ? employeeResults.data?.specialists || [] : options.data?.specialists || [];
  const policy = options.data?.policy, specialist = options.data?.specialists.find(s => String(s.eligibility_id) === employee) || (String(chosenEmployee?.eligibility_id) === employee ? chosenEmployee : undefined);
  const branchZone=options.data?.branch_timezone || defaultText('timezone','srm') || 'UTC';
  const zone = specialist?.timezone || branchZone;
  const today=wall(clock,zone).slice(0,10),lastDay=new Date(Date.parse(`${today}T12:00:00Z`)+90*86400000).toISOString().slice(0,10);
  const dateValid=!!date && date>=today && date<=lastDay;
  const matches = zone && date && time ? candidates(`${date}T${time}`, zone) : [];
  const minutes = Number(duration || policy?.default_duration_minutes || 0);
  const durationValid = !!policy && Number.isInteger(minutes) && minutes >= policy.min_duration_minutes && minutes <= policy.max_duration_minutes && (policy.allow_duration_override || minutes === policy.default_duration_minutes);
  const instant = matches.length === 1 ? new Date(matches[0]).toISOString() : '';
  const missingTypes = (policy?.required_resource_types || []).filter(type => !options.data?.resources?.some(r => resources.includes(r.id) && r.resource_type === type));
  const valid = !!policy?.active && !!specialist && !!instant && durationValid && !missingTypes.length && dateValid && Date.parse(instant)>clock && resources.length<=9;
  async function check(eligibility: string, startsAt: string, ids: number[], timezone: string, signal?: AbortSignal) {
    const params = new URLSearchParams({ service_id: String(serviceId), eligibility_id: eligibility, day: wall(Date.parse(startsAt), timezone).slice(0, 10), duration_minutes: String(minutes), starts_at: startsAt });
    ids.forEach(id => params.append('resource_ids', String(id)));
    return (await api.get<Availability>('/srm/service-checkout/options/availability', { params, signal, recordCache: false })).data;
  }
  const availability = useQuery({ queryKey: ['prebooking-availability', scope, serviceId, employee, instant, minutes, resources.join(',')], enabled: valid, retry: false, staleTime: 0, refetchInterval:30000,
    queryFn: ({ signal }) => check(employee, instant, resources, zone!, signal) });
  const defaulted = useRef(false);
  useEffect(()=>{if(defaulted.current || initialDraft?.employeeId || prefill || !options.data?.policy?.active || !options.data.specialists.length)return;defaulted.current=true;const first=options.data.specialists[0];setEmployee(String(first.eligibility_id));setChosenEmployee(first);if(!date)setDate(wall(Date.now(),first.timezone).slice(0,10));if(!duration)setDuration(String(options.data.policy.default_duration_minutes));if(!resources.length)setResources([...new Set((options.data.policy.required_resource_types || []).flatMap(type=>{const resource=options.data?.resources?.find(r=>r.resource_type===type);return resource?[resource.id]:[];}))]);},[options.data,prefill,initialDraft]);
  const suggestedTime=useQuery({queryKey:['prebooking-default-slot',scope,serviceId,employee,date,minutes,resources.join(',')],enabled:!!specialist && !!date && !time && durationValid && !missingTypes.length,retry:false,staleTime:0,queryFn:async({signal})=>{const params=new URLSearchParams({service_id:String(serviceId),eligibility_id:employee,day:date,duration_minutes:String(minutes)});resources.forEach(id=>params.append('resource_ids',String(id)));return (await api.get<Availability>('/srm/service-checkout/options/availability',{params,signal,recordCache:false})).data;}});
  useEffect(()=>{if(!time && zone && suggestedTime.data?.slots.length){const first=wall(Date.parse(suggestedTime.data.slots[0].starts_at),zone);setDate(first.slice(0,10));setTime(first.slice(11));}},[suggestedTime.data,time,zone]);
  const current = valid && !availability.isFetching && availability.isSuccess && !options.isFetching;
  const fresh=current && clock-availability.dataUpdatedAt<45000;
  const conflicts = current ? availability.data.conflicts || [] : [];
  const unavailable = current && availability.data.selection_available === false;
  const employeeConflict = conflicts.find(c => c.resource_id === specialist?.provider_resource_id);
  const resourceConflicts = conflicts.filter(c => resources.includes(c.resource_id));
  const reason = !serviceId ? 'Choose a service.' : options.isPending ? 'Loading service options…' : options.isError ? 'Service options could not load. Retry below.' : !policy?.active ? 'This service needs an active scheduling policy.' : !specialist ? anyStaff ? 'Find an available qualified employee below.' : 'Choose an eligible employee.' : !date || !time ? 'Choose a date and start time.' : !dateValid ? 'Choose a date from today through the next 90 days.' : !instant ? 'Choose an unambiguous local date and time.' : Date.parse(instant)<=clock ? 'Choose a future start time.' : resources.length>9 ? 'Select no more than 9 additional resources.' : !durationValid ? 'Choose a duration allowed by this service.' : missingTypes.length ? `Choose required resources: ${missingTypes.join(', ')}.` : availability.isFetching || availability.isPending || options.isFetching ? 'Checking employee and resource availability…' : availability.isError ? 'Availability could not be verified. Retry below.' : current && !fresh ? 'Availability has expired. Refresh before confirming.' : unavailable ? 'Resolve the employee or resource conflict.' : availability.data?.selection_available !== true ? 'Choose a valid available interval.' : '';
  const ready = current && fresh && !reason && availability.data.selection_available === true;
  const selection = useMemo(() => ready && specialist && policy ? { additional_resource_ids: resources, policy_id: policy.id, expected_policy_revision: policy.revision, eligibility_id: specialist.eligibility_id, expected_eligibility_revision: specialist.eligibility_revision, provider_resource_id: specialist.provider_resource_id, employee_id: specialist.employee_id, starts_at: instant, duration_minutes: minutes } satisfies BookingSelection : undefined, [ready, specialist, policy, resources, instant, minutes]);
  useEffect(() => { callbacks.current.onChange(selection); callbacks.current.onAvailability(ready ? true : null); callbacks.current.onReason(reason); }, [selection, ready, reason]);
  const display = useMemo(()=>({employee:specialist?.employee_name || '',timezone:zone || 'UTC',startsAt:instant || undefined,minutes,resources:options.data?.resources?.filter(r=>resources.includes(r.id)).map(r=>r.name) || []}),[specialist?.employee_name,zone,instant,minutes,options.data?.resources,resources]);
  useEffect(()=>{callbacks.current.onDisplay?.(display);},[display]);
  const restoredVersion=useRef(initialDraft?.versionKey);
  useEffect(()=>{if(!initialDraft?.versionKey || restoredVersion.current===initialDraft.versionKey)return;restoredVersion.current=initialDraft.versionKey;rememberedEmployee.current=initialDraft.employeeId;setDate(initialDraft.date);setTime(initialDraft.time);setDuration(initialDraft.duration);setResources(initialDraft.resources);const person=options.data?.specialists.find(s=>s.employee_id===initialDraft.employeeId);setChosenEmployee(person);setEmployee(person?String(person.eligibility_id):'');lastService.current=undefined;},[initialDraft,options.data]);
  useEffect(()=>{if(instant && specialist)carryInstant.current=instant;},[instant,specialist]);
  const draft=useMemo(()=>({versionKey:initialDraft?.versionKey,serviceId,employeeId:specialist?.employee_id || rememberedEmployee.current,date,time,timezone:zone,duration,resources}),[initialDraft?.versionKey,serviceId,specialist?.employee_id,date,time,zone,duration,resources]);
  useEffect(()=>{callbacks.current.onDraftChange?.(draft);},[draft]);
  useEffect(()=>{
    if(!serviceId || !options.data || lastService.current===serviceId)return;
    lastService.current=serviceId;
    const person=options.data.specialists.find(s=>s.employee_id===rememberedEmployee.current);
    if(person){setEmployee(String(person.eligibility_id));setChosenEmployee(person);if(carryInstant.current){const local=wall(Date.parse(carryInstant.current),person.timezone);setDate(local.slice(0,10));setTime(local.slice(11));}}
    else if(rememberedEmployee.current){setEmployee('');setChosenEmployee(undefined);rememberedEmployee.current=undefined;setCarryNotice('The previous employee is not qualified for this service. Your date and time are retained.');}
    setResources(ids=>{const kept=ids.filter(id=>options.data!.resources?.some(r=>r.id===id));if(kept.length!==ids.length)setCarryNotice('Compatible schedule details were retained; unavailable resources were removed.');return kept;});
    if(!options.data.policy?.allow_duration_override || Number(duration)<options.data.policy.min_duration_minutes || Number(duration)>options.data.policy.max_duration_minutes)setDuration('');
  },[serviceId,options.data,duration]);
  useEffect(()=>{if(!validateRef)return;validateRef.current=async()=>{
    if(!valid || !specialist)return;
    const latest=await options.refetch();
    const person=latest.data?.specialists.find(s=>s.employee_id===specialist.employee_id) || (latest.isSuccess && chosenEmployee?.employee_id===specialist.employee_id?chosenEmployee:undefined);
    const rules=latest.data?.policy;
    if(!latest.isSuccess || !person || !rules?.active || minutes<rules.min_duration_minutes || minutes>rules.max_duration_minutes || !rules.allow_duration_override && minutes!==rules.default_duration_minutes)return;
    const verified=await check(String(person.eligibility_id),instant,resources,person.timezone);
    if(verified.selection_available!==true){void availability.refetch();return;}
    return {policy_id:rules.id,expected_policy_revision:rules.revision,eligibility_id:person.eligibility_id,expected_eligibility_revision:person.eligibility_revision,provider_resource_id:person.provider_resource_id,employee_id:person.employee_id,starts_at:instant,duration_minutes:minutes,additional_resource_ids:resources};
  };return()=>{validateRef.current=null;};},[validateRef,valid,specialist,chosenEmployee,options.refetch,availability.refetch,minutes,instant,resources]);
  function invalidate() { callbacks.current.onChange(undefined); callbacks.current.onAvailability(null); callbacks.current.onReason('Checking your updated booking details…'); }
  const prefilled = useRef('');
  useEffect(() => {
    if (!prefill || !options.data || prefilled.current === prefill.key) return;
    const person = options.data.specialists.find(s => s.employee_id === prefill.employeeId);
    if (person) { rememberedEmployee.current=person.employee_id;setEmployee(String(person.eligibility_id)); setChosenEmployee(person); }
    else if (prefill.employeeId) setEmployee('');
    const tz = person?.timezone || zone;
    if (tz) { const local = wall(Date.parse(prefill.startsAt), tz); setDate(local.slice(0,10)); setTime(local.slice(11)); }
    if (prefill.resourceId && options.data.resources?.some(r => r.id === prefill.resourceId)) setResources([prefill.resourceId]);
    prefilled.current = prefill.key;
  }, [prefill, options.data, zone]);
  function chooseEmployee(id: string) {
    invalidate();
    const next = [...choices, ...(options.data?.specialists || [])].find(s => String(s.eligibility_id) === id);
    setChosenEmployee(next);rememberedEmployee.current=next?.employee_id;setAnyStaff(false);
    if (next) {
      const at = instant || carryInstant.current || prefill?.startsAt;
      const local = wall(at ? Date.parse(at) : Date.now(), next.timezone);
      setDate(local.slice(0,10)); if (at) setTime(local.slice(11));
    }
    setEmployee(id);
  }
  const [alternativeLimit,setAlternativeLimit]=useState(8),[alternativeDays,setAlternativeDays]=useState(7);
  async function checkedParallel<T>(jobs:(()=>Promise<T>)[]) {
    const output:T[]=[];let cursor=0,failed=false;
    await Promise.all(Array.from({length:Math.min(4,jobs.length)},async()=>{while(cursor<jobs.length){const index=cursor++;try{output.push(await jobs[index]());}catch{failed=true;}}}));
    return {output,failed};
  }
  const employeeAlternatives=useQuery({queryKey:['prebooking-employee-alternatives',scope,serviceId,employee,instant,minutes,resources.join(','),alternativeLimit],enabled:unavailable,retry:false,
    queryFn:async({signal})=>checkedParallel((options.data?.specialists || []).filter(s=>String(s.eligibility_id)!==employee).slice(0,alternativeLimit).map(person=>async()=>({person,available:(await check(String(person.eligibility_id),instant,resources,person.timezone,signal)).selection_available===true}))) });
  const resourceAlternatives=useQuery({queryKey:['prebooking-resource-alternatives',scope,serviceId,employee,instant,minutes,resources.join(','),alternativeLimit],enabled:unavailable,retry:false,
    queryFn:async({signal})=>checkedParallel(resourceConflicts.flatMap(conflict=>{const type=options.data?.resources?.find(r=>r.id===conflict.resource_id)?.resource_type;return (options.data?.resources || []).filter(r=>r.resource_type===type&&!resources.includes(r.id)).slice(0,alternativeLimit).map(room=>async()=>{const ids=resources.map(id=>id===conflict.resource_id?room.id:id);return {ids,name:room.name,available:(await check(employee,instant,ids,zone,signal)).selection_available===true};});})) });
  const timeAlternatives=useQuery({queryKey:['prebooking-next-time',scope,serviceId,employee,instant,minutes,resources.join(','),alternativeDays],enabled:unavailable,retry:false,
    queryFn:async({signal})=>{let next=availability.data?.slots.find(s=>Date.parse(s.starts_at)>Date.parse(instant)),failed=false;
      for(let offset=1;!next&&offset<=alternativeDays;offset++){const day=new Date(Date.parse(`${date}T12:00:00Z`)+offset*86400000).toISOString().slice(0,10);if(day>lastDay)break;const start=candidates(`${day}T12:00`,zone)[0];if(!start)continue;try{next=(await check(employee,new Date(start).toISOString(),resources,zone,signal)).slots.find(s=>Date.parse(s.starts_at)>Date.parse(instant));}catch{if(signal.aborted)throw new Error('Cancelled');failed=true;}}
      return {next,failed};} });
  type Choice=Specialist & {starts_at:string;resource_ids:number[];resources:string[];changed_resources:number};
  const discovery=useQuery({queryKey:['prebooking-discovery',scope,serviceId,anyStaff,employee,date,instant,minutes,resources.join(','),employeeOffset,resourceOffset,searchDays],enabled:discoveryRequested&&!!policy?.active&&dateValid&&durationValid,retry:false,
    queryFn:({signal})=>{const params=new URLSearchParams({service_id:String(serviceId),day:date,duration_minutes:String(minutes),discover:'true',auto_resources:'true',employee_offset:String(employeeOffset),resource_offset:String(resourceOffset),search_days:String(searchDays)});if(!anyStaff&&employee)params.set('eligibility_id',employee);if(time&&instant)params.set('starts_at',instant);resources.forEach(id=>params.append('resource_ids',String(id)));return api.get<{choices:Choice[];checked_combinations:number;partial:boolean;next_employee_offset:number|null;next_resource_offset:number|null;searched_days:number}>('/srm/service-checkout/options/availability',{params,signal,recordCache:false}).then(r=>r.data);} });
  function chooseCombination(choice:Choice){invalidate();setChosenEmployee({...choice,provider_name:choice.employee_name});rememberedEmployee.current=choice.employee_id;setEmployee(String(choice.eligibility_id));setAnyStaff(false);const local=wall(Date.parse(choice.starts_at),choice.timezone);setDate(local.slice(0,10));setTime(local.slice(11));setResources(choice.resource_ids);setDiscoveryRequested(false);}
  function chooseTime(startsAt: string) { invalidate(); const local = wall(Date.parse(startsAt), zone!); setDate(local.slice(0,10)); setTime(local.slice(11)); }
  const issues=[...(!specialist?[{text:'Choose an eligible employee or find any qualified employee',selector:'[aria-label="Prebooking employee"]'}]:[]),...(!date||!dateValid?[{text:'Choose a date within 90 days',selector:'[aria-label="Prebooking date"]'}]:[]),...(!time||!instant||Date.parse(instant)<=clock?[{text:'Choose a valid future start time',selector:'[aria-label="Prebooking start time"]'}]:[]),...(!durationValid?[{text:'Correct the service duration',selector:'[aria-label="Prebooking duration"]'}]:[]),...missingTypes.map(type=>({text:`Choose required ${type}`,selector:`[aria-label="Search ${type}"]`})),...conflicts.map(c=>({text:c.message,selector:c.resource_id===specialist?.provider_resource_id?'[aria-label="Prebooking employee"]':'[aria-invalid=true] input'}))];
  const disabled = !serviceId || !policy?.active || options.isFetching;
  return <section ref={sectionRef} className="prebooking-fields" aria-label="Prebooking schedule" aria-busy={options.isFetching || availability.isFetching}>
    {!!serviceId && !!issues.length && <details className="prebooking-issues"><summary>{issues.length} things to complete or review</summary><ul>{issues.map((issue,index)=><li key={index}><button type="button" onClick={()=>{if(issue.selector.includes('duration'))setEditDuration(true);requestAnimationFrame(()=>sectionRef.current?.querySelector<HTMLElement>(issue.selector)?.focus());}}>{issue.text}</button></li>)}</ul></details>}
    {carryNotice && <p role="status">{carryNotice}</p>}
    {!serviceId && <p className="prebooking-hint">Select a service to unlock qualified employees, times and resources.</p>}
    {prefill?.employeeId && options.isSuccess && !specialist && !options.data.specialists.some(s => s.employee_id === prefill.employeeId) && <p className="prebooking-hint">The selected timeline employee is not eligible for this service. Choose a qualified employee; the selected instant will be retained.</p>}
    <div className="prebooking-employee-filters"><label>Find {term('provider').toLowerCase()}<Input aria-label="Find prebooking employee" placeholder="Employee name or code" disabled={disabled} maxLength={100} value={employeeSearch} onChange={e=>setEmployeeSearch(e.target.value)}/></label><label>{term('provider')} category<NativeSelect aria-label="Employee category" disabled={disabled} value={category} onChange={e=>{setCategory(e.target.value);if(specialist && e.target.value && !specialist.work_categories?.includes(e.target.value)){invalidate();setEmployee('');setChosenEmployee(undefined);}}}><option value="">All qualified categories</option>{[...new Set([...(policy?.employee_categories || []),...(options.data?.specialists.flatMap(s=>s.work_categories || []) || []),...(employeeResults.data?.specialists.flatMap(s=>s.work_categories || []) || [])])].map(c=><option key={c}>{c}</option>)}</NativeSelect></label></div>
    {!!policy?.active && <Button type="button" variant="outline" aria-pressed={anyStaff} onClick={()=>{invalidate();setAnyStaff(true);setEmployee('');setChosenEmployee(undefined);rememberedEmployee.current=undefined;setDiscoveryRequested(true);}}>Any qualified employee · find times</Button>}
    <label>{term('provider')}<NativeSelect aria-label="Prebooking employee" disabled={disabled || employeeResults.isFetching} value={employee} aria-invalid={!!employeeConflict} aria-describedby={employeeConflict ? 'prebooking-employee-conflict' : undefined} onChange={e => chooseEmployee(e.target.value)}><option value="">Choose eligible employee</option>{specialist && !choices.some(s=>s.eligibility_id===specialist.eligibility_id) && <option value={employee}>{specialist.employee_name}</option>}{choices.filter(s=>!category || s.work_categories?.includes(category)).map(s => <option key={s.eligibility_id} value={s.eligibility_id}>{s.employee_name}{s.work_categories?.length ? ` · ${s.work_categories.join(', ')}` : ''}{String(s.eligibility_id)===employee ? ready ? ' · Available' : unavailable ? ' · Unavailable' : ' · Checking' : ' · Select to check availability'}</option>)}</NativeSelect></label>
    {employeeResults.isError && <p role="alert">Employee search failed. <Button type="button" variant="outline" onClick={()=>void employeeResults.refetch()}>Retry employee search</Button></p>}
    {options.data?.has_more && <small>Search by name to find additional qualified employees.</small>}
    {specialist && <div className="prebooking-person-card" aria-label="Selected employee"><span className="prebooking-initials" aria-hidden="true">{specialist.employee_name.split(' ').map(w=>w[0]).slice(0,2).join('')}</span><div><strong>{specialist.employee_name}</strong><small>{specialist.work_categories?.join(', ') || specialist.provider_name}</small></div><span className="prebooking-availability-badge" data-state={ready?'available':unavailable?'unavailable':'checking'}>{ready?'Available':unavailable?'Unavailable':valid?'Checking':'Choose details'}</span></div>}
    {employeeConflict && <p id="prebooking-employee-conflict" role="alert" className="prebooking-conflict">{employeeConflict.message}</p>}
    {options.data && !options.data.specialists.length && <p>No qualified employees are configured for this service.</p>}
    <p className="prebooking-zone" aria-label="Booking timezone">Booking timezone: <strong>{zone || 'Choose an employee'}</strong></p>
    {zone && (options.data?.branch_timezone || defaultText('timezone','srm')) && zone !== (options.data?.branch_timezone || defaultText('timezone','srm')) && <p role="status" className="prebooking-zone-warning">Employee timezone {zone} differs from branch timezone {options.data?.branch_timezone || defaultText('timezone','srm')}. Date and time below use {zone}; changing employees preserves the same instant.</p>}
    <div className="prebooking-date-time"><label>Date<Input aria-label="Prebooking date" type="date" disabled={disabled || !specialist&&!anyStaff} min={today} max={lastDay} value={date} onChange={e => { invalidate(); setDate(e.target.value); }}/></label><label>Start time<Input aria-label="Prebooking start time" type="time" disabled={disabled || !specialist&&!anyStaff} value={time} onChange={e => { invalidate(); setTime(e.target.value); }}/></label></div>
    {!!policy?.active && <section className="prebooking-discovery" aria-label="Find available combinations"><Button type="button" variant="outline" disabled={!dateValid || !durationValid} onClick={()=>setDiscoveryRequested(true)}>Find any available required resource{anyStaff?' and employee':''}</Button>
      {anyStaff && <p>Choose a date, optionally a time, then select a verified employee/resource combination.</p>}
      {discovery.isFetching && <p role="status">Finding eligible employees, resources and times…</p>}
      {discovery.isError && <p role="alert">Combinations could not be verified. <Button type="button" variant="outline" onClick={()=>void discovery.refetch()}>Retry combination search</Button></p>}
      {!discovery.isFetching && discovery.data && <><p>{discovery.data.checked_combinations} combinations checked over {discovery.data.searched_days} day(s).{discovery.data.partial?' Partial search; expand or narrow your criteria.':''}</p>{discovery.data.choices.length?discovery.data.choices.map(c=><Button type="button" variant="outline" key={`${c.eligibility_id}:${c.starts_at}:${c.resource_ids.join(',')}`} onClick={()=>chooseCombination(c)}>Choose {c.employee_name} · {wall(Date.parse(c.starts_at),c.timezone).replace('T',' ')} · {c.resources.join(', ')} · {c.timezone}</Button>):<p>No verified combinations in this search batch.</p>}
      {discovery.data.next_employee_offset!==null && <Button type="button" variant="outline" onClick={()=>setEmployeeOffset(discovery.data!.next_employee_offset!)}>Check next employees</Button>}
      {discovery.data.next_resource_offset!==null && <Button type="button" variant="outline" onClick={()=>setResourceOffset(discovery.data!.next_resource_offset!)}>Check next resources</Button>}
      {searchDays<30 && <Button type="button" variant="outline" onClick={()=>setSearchDays(n=>Math.min(30,n+7))}>Search next {Math.min(30,searchDays+7)} days</Button>}</>}
    </section>}
    <div className="prebooking-end"><strong>{instant && durationValid ? `Ends ${wall(Date.parse(instant) + minutes * 60000, zone!).replace('T',' ')} · ${minutes} minutes` : policy ? `${policy.default_duration_minutes} minutes · choose a start time` : 'End time calculated after selecting a service'}</strong>{policy?.allow_duration_override && <Button type="button" variant="ghost" aria-expanded={editDuration} onClick={()=>setEditDuration(v=>!v)}>Edit duration</Button>}</div>
    {editDuration && policy?.allow_duration_override && <label>Duration (minutes)<Input aria-label="Prebooking duration" type="number" disabled={disabled} min={policy.min_duration_minutes} max={policy.max_duration_minutes} value={duration || policy.default_duration_minutes} onChange={e => { invalidate(); setDuration(e.target.value); }}/></label>}
    <p className="prebooking-hint">Reserved time: {minutes || 0} minutes of service. No extra setup/cleanup buffer is configured. Additional resources: {resources.length} / 9 maximum; each required type needs at least one.</p>
    <fieldset disabled={disabled || !specialist}><legend>Rooms &amp; equipment</legend>{!options.data?.resources?.length && !policy?.required_resource_types?.length ? <NativeSelect aria-label="Prebooking resource" disabled><option>{serviceId ? 'No additional resources configured' : 'Choose a service first'}</option></NativeSelect> : [...new Set([...(policy?.required_resource_types || []),...(options.data?.resources || []).map(r=>r.resource_type)])].map(type => {
      const required = policy?.required_resource_types?.includes(type), selected = (options.data?.resources || []).filter(r=>r.resource_type===type && resources.includes(r.id));
      return <div className="prebooking-resource-group" role="group" aria-label={`${type} resources`} aria-invalid={!!required && !selected.length || resourceConflicts.some(c=>selected.some(r=>r.id===c.resource_id))} key={type}><span>{type.charAt(0).toUpperCase()+type.slice(1)} <small>{required ? 'Required · choose at least one' : 'Optional'}</small></span>
        <SmartRecordPicker name={type} placeholder={`Find ${type} by resource name`} emptyMessage={`No matching ${type}. Try another resource name or ask an administrator to configure it.`} value="" search={resourceSearch[type] || ''} onSearch={value=>setResourceSearch(s=>({...s,[type]:value}))} items={(options.data?.resources || []).filter(r=>r.resource_type===type && !resources.includes(r.id)).map(r=>({id:String(r.id),label:r.name,description:r.resource_type,record:r}))} onSelect={r=>{if(resources.length>=9){setCarryNotice('You can select at most 9 additional resources. Remove one before adding another.');return;}invalidate();setResources(ids=>[...ids,r.id]);setResourceSearch(s=>({...s,[type]:''}));}} onClear={()=>setResourceSearch(s=>({...s,[type]:''}))}/>
        <div className="prebooking-selected-resources">{selected.map(r=>{const conflict=resourceConflicts.find(c=>c.resource_id===r.id);return <div key={r.id} className="prebooking-resource-chip" data-resource-id={r.id} data-conflict={!!conflict}><span>{r.name}{(()=>{const state=availability.data?.resources.find(item=>item.id===r.id);return state?.capacity && state.capacity>1?<small className="resource-capacity"> · {state.remaining_capacity} of {state.capacity} places available</small>:null;})()}</span><Button type="button" variant="ghost" aria-label={`Remove ${r.name}`} onClick={()=>{invalidate();setResources(ids=>ids.filter(id=>id!==r.id));}}>×</Button>{conflict && <p id={`prebooking-resource-${r.id}`} role="alert" className="prebooking-conflict">{conflict.message}</p>}</div>;})}</div>
        {required && !selected.length && <p className="prebooking-hint">Select a {type} to continue.</p>}
      </div>;
    })}</fieldset>
    <p role="status" aria-live="polite" aria-atomic="true" data-availability-state={ready ? 'available' : unavailable ? 'unavailable' : options.isFetching || availability.isFetching ? 'checking' : options.isError || availability.isError ? 'error' : 'incomplete'} className={unavailable ? 'prebooking-conflict' : 'prebooking-hint'}>{ready ? 'Employee and selected resources are available. Rechecked when you confirm.' : reason}</p>
    {!!availability.dataUpdatedAt && valid && <small>Availability checked {new Date(availability.dataUpdatedAt).toLocaleTimeString()} · {fresh?'current':'refresh required'}. Final confirmation rechecks it.</small>}
    {valid && !availability.isError && <Button type="button" variant="outline" disabled={availability.isFetching} onClick={() => void availability.refetch()}>Refresh availability</Button>}
    {(options.isError || availability.isError) && <Button type="button" variant="outline" disabled={options.isFetching || availability.isFetching} onClick={() => { if (options.isError) void options.refetch(); else void availability.refetch(); }}>Retry availability</Button>}
    {unavailable && <section className="prebooking-alternatives" aria-label="Available alternatives"><strong>Available alternatives · ranked by fewest changes</strong>
      {employeeAlternatives.isFetching && <p role="status">Checking other employees…</p>}
      {employeeAlternatives.data?.output.filter(r=>r.available).map(r=><Button type="button" variant="outline" key={r.person.eligibility_id} onClick={()=>chooseEmployee(String(r.person.eligibility_id))} className="booking-alternative-card"><span className="changed">Change employee: {r.person.employee_name}</span><span>{display.resources.join(', ') || 'No additional resources'} · {instant?wall(Date.parse(instant),r.person.timezone).replace('T',' '):''}</span><small>Time and resources unchanged.</small></Button>)}
      {resourceAlternatives.isFetching && <p role="status">Checking replacement resources…</p>}
      {resourceAlternatives.data?.output.filter(r=>r.available).sort((a,b)=>a.name.localeCompare(b.name)).map(r=><Button type="button" variant="outline" key={r.ids.join(',')} onClick={()=>{invalidate();setResources(r.ids);}} className="booking-alternative-card"><span>{specialist?.employee_name} · {instant?wall(Date.parse(instant),zone).replace('T',' '):''}</span><span className="changed">Change resources: {r.name}</span><small>Employee and time unchanged.</small></Button>)}
      {timeAlternatives.isFetching && <p role="status">Checking later times…</p>}
      {timeAlternatives.data?.next && <Button type="button" variant="outline" onClick={()=>chooseTime(timeAlternatives.data!.next!.starts_at)}>Next available: {wall(Date.parse(timeAlternatives.data.next.starts_at),zone).replace('T',' ')}</Button>}
      <small>Same-time employee and resource replacements are shown before later times. Up to {alternativeLimit} candidates per type and {alternativeDays} days checked; this is not an exhaustive search.</small>
      {alternativeLimit<100 && <Button type="button" variant="outline" onClick={()=>setAlternativeLimit(n=>Math.min(100,n+8))}>Check more employees/resources</Button>}
      {alternativeDays<30 && <Button type="button" variant="outline" onClick={()=>setAlternativeDays(n=>Math.min(30,n+7))}>Search beyond {alternativeDays} days</Button>}
      {(employeeAlternatives.data?.failed||resourceAlternatives.data?.failed||timeAlternatives.data?.failed||employeeAlternatives.isError||resourceAlternatives.isError||timeAlternatives.isError) && <p role="alert">Some alternatives could not be checked; they are not offered as available.</p>}
    </section>}
    {options.data?.can_configure && <Link className="prebooking-manage" to="/srm/inventory/products?kind=service">Manage service scheduling and eligibility</Link>}
    {current && !!availability.data.slots.length && <section aria-label="Available times"><strong>Available times · {zone}</strong><SlotGroups slots={availability.data.slots} zone={zone} minutes={minutes} selected={instant} onSelect={chooseTime}/></section>}

  </section>;
}
