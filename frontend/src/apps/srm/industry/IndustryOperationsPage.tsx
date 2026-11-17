import { candidates, wall } from "@/shared/scheduling/booking-time";
import PrebookingCustomerContext from '@/shared/scheduling/PrebookingCustomerContext';
import {draftKey,readDraft,saveDraft,clearDraftStorage,bookingError,type ScheduleDraft,type BookingAttempt} from '@/shared/scheduling/prebooking-state';
import AppointmentPaymentStatus from "@/shared/scheduling/BookingUX";
import { bookingDay, bookingLabel, bookingRange, validZone } from "@/shared/scheduling/booking-view";
import { defaultText } from "@/lib/form-defaults";
import PrebookingSurface from '@/shared/scheduling/PrebookingSurface';
import PrebookingCustomer from '@/shared/scheduling/PrebookingCustomer';
import PrebookingServicePicker from '@/shared/scheduling/PrebookingServicePicker';
import PrebookingSuccess, {type ConfirmedPrebooking} from '@/shared/scheduling/PrebookingSuccess';
import AppointmentTimeline from "./AppointmentTimeline";
import { type BookingSelection } from "./POSServiceScheduling";
import PrebookingFields, { type BookingSlot, type BookingDisplay } from "@/shared/scheduling/PrebookingFields";
import SchedulingFrame, { schedulingIcons } from '@/shared/scheduling/SchedulingFrame';
import ConstructionWarehouseSelect from './ConstructionWarehouseSelect';
import AppointmentBookingLink from './AppointmentBookingLink';
import AppointmentVisitPanel from './AppointmentVisitPanel';
import GroupedServiceReschedule from './GroupedServiceReschedule';
import { lazy, Suspense, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import { useBusinessTerms } from '@/hooks/use-business-terms';
import { useAuthStore } from '@/store/authStore';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import CompanySelect, { masterScope, type Company } from '@/shared/master-data/CompanySelect';
import SmartRecordPicker from '@/shared/records/SmartRecordPicker';
import { catalogApi, catalogError, type CatalogItem } from '@/shared/catalog/api';
import { dealError } from '@/apps/crm/deals/deal-utils';
import { useMobileDraftGuard } from '@/components/mobile/useMobileDraftGuard';
import DealRecordSelect from '@/apps/crm/deals/DealRecordSelect';

const ConstructionPlanningPanel = lazy(() => import('./ConstructionPlanningPanel'));
const ConstructionSiteCreate = lazy(() => import('./ConstructionPlanningPanel').then(module => ({ default: module.ConstructionSiteCreate })));

type Row = { parent_id?: number; id: number; title: string; kind: string; status: string; revision: number; created_by: number; customer_id?: number; invoice_id?: number; data: Record<string, string | number | number[]> };
type Choice = { id: number; name: string };
function choicePage(data:{items:Choice[];has_more:boolean}){
  if(!Array.isArray(data?.items))throw new Error('Record choices could not load');
  return data;
}
type Form = Record<string, string>;
const ROOT = '/srm/industry';
const titles: Record<string, string> = { appointment: 'Appointments', resource: 'Salon resources', boq: 'BOQ', variation: 'Variations', measurement: 'Measurements', site_diary: 'Site diary', subcontract: 'Subcontracts', material_issue: 'Materials consumed' };
const paths: Record<string, string> = { appointment: '/appointments', resource: '/resources', boq: '/boq', variation: '/boq', measurement: '/measurements', site_diary: '/site-diaries', subcontract: '/subcontracts', material_issue: '/material-issues' };
const controls = 'w-full rounded-md border bg-background px-3 py-2 text-sm';
const empty = (): Form => ({ title: '', capacity: '1', duration_minutes: '60', resource_type: 'provider', opens: '09:00', closes: '19:00', weekdays: '0,1,2,3,4,5', timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata', quantity: '', unit_rate: '', unit: '', code: '', tax_rate: '0', retention_percent: '0', workforce: '0' });

function Field({ name, children }: { name: string; children: ReactNode }) {
  return <div className="grid gap-1 text-sm"><span>{name}</span>{children}</div>;
}

export function ProjectPicker({ value, change, hint }: { value: string; change: (value: string) => void; hint?: Choice }) {
  const { term } = useBusinessTerms();
  const [search, setSearch] = useState(''), [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Choice>();
  const q = useQuery({ queryKey: ['industry-projects', masterScope(), search, offset], queryFn: async () => choicePage((await api.get<{ items: Choice[]; has_more: boolean }>(ROOT + '/project-options', { params: { search, offset } })).data), retry: false });
  const current = selected && String(selected.id) === value ? selected : hint && String(hint.id) === value ? hint : q.data?.items?.find(item => String(item.id) === value);
  return <SmartRecordPicker name={term('project')} value={value} search={search} onSearch={s => { setSearch(s); setOffset(0); }} items={(q.data?.items || []).map(record => ({ id: String(record.id), label: record.name, record }))} selected={current ? { id: String(current.id), label: current.name, record: current } : undefined} onSelect={r => { setSelected(r); change(String(r.id)); }} onClear={() => { setSelected(undefined); change(''); }} loading={q.isFetching} error={q.isError ? dealError(q.error) : undefined} retry={() => void q.refetch()} hasMore={q.data?.has_more} loadMore={() => setOffset(s => s + 50)} />;
}

export function StaffPicker({ value, change, employee = false }: { value: string; change: (value: string) => void; employee?: boolean }) {
  const [search, setSearch] = useState(''), [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Choice>();
  const q = useQuery({ queryKey: ['industry-staff', masterScope(), employee, search, offset], retry: false, queryFn: async () => choicePage((await api.get<{ items: Choice[]; has_more: boolean }>(ROOT + (employee ? '/employee-options' : '/staff-options'), { params: { search, offset } })).data) });
  const current=selected&&String(selected.id)===value?selected:q.data?.items?.find(item=>String(item.id)===value);
  return <SmartRecordPicker name={employee ? 'HRMS employee' : 'Staff account'} value={value} search={search} onSearch={s => { setSearch(s); setOffset(0); }} items={(q.data?.items || []).map(record => ({ id: String(record.id), label: record.name, record }))} selected={current ? { id: String(current.id), label: current.name, record: current } : undefined} onSelect={r => { setSelected(r); change(String(r.id)); }} onClear={() => { setSelected(undefined); change(''); }} loading={q.isFetching} error={q.isError ? dealError(q.error) : undefined} retry={() => void q.refetch()} hasMore={q.data?.has_more} loadMore={() => setOffset(o => o + 50)} />;
}

export function ServicePicker({ value, change, kind = 'service' }: { value: string; change: (value: string) => void; kind?: 'service' | 'product' }) {
  const { term } = useBusinessTerms();
  const [search, setSearch] = useState(''), [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Choice>();
  const q = useQuery({ queryKey: ['industry-services', masterScope(), kind, search, page], queryFn: async () => {const response=await catalogApi.list('srm', { kind, status: 'Active', search, page, per_page: 50 });if(!Array.isArray(response.data?.items))throw new Error('Catalog choices could not load');return response.data;}, retry: false });
  const current=selected&&String(selected.id)===value?selected:q.data?.items?.find(item=>String(item.id)===value);
  return <SmartRecordPicker name={kind === 'service' ? term('service') : 'Stock item'} value={value} search={search} onSearch={s => { setSearch(s); setPage(1); }} items={(q.data?.items || []).filter(r => r.kind === kind).map(record => ({ id: String(record.id), label: record.name, record }))} selected={current ? { id: String(current.id), label: current.name, record: current } : undefined} onSelect={r => { setSelected(r); change(String(r.id)); }} onClear={() => { setSelected(undefined); change(''); }} loading={q.isFetching} error={q.isError ? catalogError(q.error) : undefined} retry={() => void q.refetch()} hasMore={!!q.data && page < q.data.pages} loadMore={() => setPage(p => p + 1)} />;
}

function RescheduleForm({ row, resources, saved }: { row: Row; resources: Row[]; saved: (row: Row) => Promise<void> }) {
  const { term } = useBusinessTerms();
  const zone=validZone(String(resources.find(resource=>(row.data.resource_ids as number[]).includes(resource.id) && ['provider','doctor','stylist','technician','employee'].includes(String(resource.data.resource_type)))?.data.timezone || defaultText('timezone','srm')));
  const current = new Date(String(row.data.starts_at));
  const [starts, setStarts] = useState(wall(current.getTime(),zone));
  const [minutes, setMinutes] = useState(String(row.data.duration_minutes));
  const [selected, setSelected] = useState<number[]>(row.data.resource_ids as number[]);
  const [grouped, setGrouped] = useState(!!row.data.pos_checkout_id);
  const mutation = useMutation({ mutationFn: async () => {const instant=candidates(starts,zone);if(instant.length!==1)throw new Error('Choose an unambiguous date and time in '+zone);return (await api.put<Row>(ROOT + `/appointments/${row.id}/schedule`, { expected_revision: row.revision, starts_at: new Date(instant[0]).toISOString(), duration_minutes: Number(minutes), resource_ids: selected })).data;}, onSuccess: saved, onError: error => {
    const response = (error as { response?: { status?: number; data?: { detail?: { code?: string } } } }).response;
    if (response?.status === 409 && response.data?.detail?.code === 'grouped_service_schedule') setGrouped(true);
  } });
  if (grouped) return <GroupedServiceReschedule row={row} resources={resources} saved={saved}/>;
  return <details className="rounded-md border p-3"><summary className="cursor-pointer text-sm">Reschedule</summary><p className="text-xs">Timezone: {zone}</p><form className="mt-3 grid gap-3" aria-label={`Reschedule ${term('appointment').toLowerCase()}`} onSubmit={e => { e.preventDefault(); mutation.mutate(); }}><Field name={`New ${term('appointment').toLowerCase()} time`}><Input aria-label={`New ${term('appointment').toLowerCase()} time`} type="datetime-local" required value={starts} onChange={e => setStarts(e.target.value)} /></Field><Field name="New duration (minutes)"><Input aria-label="New duration (minutes)" type="number" min={5} max={720} required value={minutes} onChange={e => setMinutes(e.target.value)} /></Field>{resources.map(r => <label key={r.id} className="flex gap-2 text-sm"><input type="checkbox" checked={selected.includes(r.id)} onChange={e => setSelected(s => e.target.checked ? [...s, r.id] : s.filter(id => id !== r.id))} />{r.title}</label>)}<Button type="submit" disabled={mutation.isPending}>Save new schedule</Button>{mutation.isError && <p role="alert">{dealError(mutation.error)}</p>}</form></details>;
}

export default function IndustryOperationsPage({ mode, bookingOnly = false, prefill, onClose, onDiscard, panelOpen = true }: { mode: 'salon' | 'appointments' | 'construction'; bookingOnly?: boolean; prefill?: BookingSlot; onClose?: () => void; onDiscard?: () => void; panelOpen?: boolean }) {
  const user = useAuthStore(s => s.user);
  const scope = masterScope();
  return <IndustryWorkspace key={`${scope}:${mode}`} mode={mode} bookingOnly={bookingOnly} prefill={prefill} onClose={onClose} onDiscard={onDiscard} panelOpen={panelOpen} scope={scope} userId={user?.id} />;
}

function IndustryWorkspace({ mode, scope, userId, bookingOnly = false, prefill, onClose, onDiscard, panelOpen = true }: { mode: 'salon' | 'appointments' | 'construction'; scope: string; userId?: number; bookingOnly?: boolean; prefill?: BookingSlot; onClose?: () => void; onDiscard?: () => void; panelOpen?: boolean }) {
  const cache = useQueryClient();
  const location = useLocation();
  const bookingWorkspace = new URLSearchParams(location.search).get('space') || undefined;
  const { term } = useBusinessTerms();
  const resourceTypeLabel = (type: string) => ['provider', 'doctor', 'stylist', 'consultant', 'technician', 'employee'].includes(type) ? term('provider') : type;
  const storageKey=draftKey(scope,bookingWorkspace || 'default');
  const [restorable]=useState(()=>readDraft(storageKey));
  const firstEditorMount=useRef(true);
  const [scheduleDraft,setScheduleDraft]=useState<ScheduleDraft|undefined>(restorable?.schedule);
  const [attempt,setAttempt]=useState<BookingAttempt|undefined>(restorable?.attempt);
  const attemptRef=useRef<BookingAttempt|undefined>(restorable?.attempt);
  const [checkingFinal,setCheckingFinal]=useState(false),[recoveryMessage,setRecoveryMessage]=useState('');
  const submitLock=useRef(false),knownFailed=useRef(false),lastDefinitiveAttempt=useRef<BookingAttempt>();
  const [quoteReady,setQuoteReady]=useState(false),[draftStorageFailed,setDraftStorageFailed]=useState(false);
  const validateSchedule=useRef<(()=>Promise<BookingSelection|undefined>)|null>(null);
  const validateQuote=useRef<(()=>Promise<CatalogItem|undefined>)|null>(null);
  const labels: Record<string, string> = { ...titles, appointment: term('appointment', true), resource: `${term('provider', true)} & ${term('resource', true)}` };
  const resourceTypes = mode === 'salon' ? ['stylist', 'chair', 'room'] : ['provider', 'room', 'chair', 'equipment', 'location'];
  const [kind, setKind] = useState(mode === 'construction' ? 'boq' : new URLSearchParams(location.search).get('resources') === '1' ? 'resource' : 'appointment');
  const [project, setProject] = useState(''), [form, setForm] = useState<Form>(() => ({ ...empty(), title: bookingOnly ? 'Service prebooking' : '', resource_type: mode === 'salon' ? 'stylist' : 'provider' })), [resources, setResources] = useState<number[]>([]);
  const [booking, setBooking] = useState<BookingSelection>();
  const [chosenCustomer, setChosenCustomer] = useState<Company>(), [chosenService, setChosenService] = useState<CatalogItem>();
  const [display, setDisplay] = useState<BookingDisplay>({employee:'',timezone:'UTC',resources:[]});
  const [confirmation, setConfirmation] = useState<ConfirmedPrebooking>();
  const submittedDisplay = useRef<Omit<ConfirmedPrebooking,'row'>>();
  const bookingFormRef = useRef<HTMLFormElement>(null);
  const [formClosed, setFormClosed] = useState(false);
  const [slot, setSlot] = useState<BookingSlot>();
  const [bookingReason, setBookingReason] = useState('Choose a service.');
  const [bookingAvailable, setBookingAvailable] = useState<boolean | null>(null);
  const [selectedProject, setSelectedProject] = useState<Choice>();
  const [creating, setCreating] = useState(bookingOnly), [notice, setNotice] = useState(''), [offset, setOffset] = useState(0);
  const [files, setFiles] = useState<number[]>([]), [fileOffset, setFileOffset] = useState(0);
  const [zone,setZone] = useState(()=>validZone(defaultText('timezone','srm')));
  const [day, setDay] = useState(()=>bookingDay(Date.now(),zone)),[week,setWeek]=useState(false);
  const requestId = useRef(restorable?.requestId || crypto.randomUUID());
  const update = (key: string, value: string) => setForm(f => ({ ...f, [key]: value }));
  const caps = useQuery({ queryKey: ['industry', scope, 'capabilities', project], retry: false, queryFn: async () => (await api.get<{ manage: boolean; approve: boolean; invoice: boolean; self_approve: boolean; projects_enabled?: boolean; crm_enabled?: boolean; billing?: boolean; collect?: boolean; approve_invoice?: boolean; appointment_actions?: string[]; operational_scope?: { pack_key?: string } }>(ROOT + '/capabilities', { params: { project_id: project || undefined } })).data });
  const rows = useQuery({ queryKey: ['industry', scope, kind, project, offset, day, week, zone], enabled: mode !== 'construction' || !!project, retry: false, queryFn: async () => {
    const range = kind === 'appointment' ? bookingRange(day,week?7:1,zone) : undefined;
    return (await api.get<{ items: Row[] }>(ROOT + '/records', { params: { kind, project_id: project || undefined, offset, from_at: range?.from, until_at: range?.until } })).data.items;
  } });
  const canTransition = (status: string) => {
    const action = ({ checked_in: 'check_in', in_service: 'start', completed: 'complete', cancelled: 'cancel', no_show: 'no_show' } as Record<string, string>)[status];
    return caps.data?.appointment_actions ? caps.data.appointment_actions.includes(action) : !!caps.data?.manage;
  };
  const resourceQuery = useQuery({ queryKey: ['industry', scope, 'resource'], enabled: mode !== 'construction' && !!caps.data?.manage, retry: false, queryFn: async () => (await api.get<{ items: Row[] }>(ROOT + '/records', { params: { kind: 'resource', limit: 200 } })).data.items });
  useEffect(()=>{const resource=resourceQuery.data?.find(r=>['provider','doctor','stylist','employee','technician'].includes(String(r.data.resource_type)));if(resource?.data.timezone)setZone(validZone(String(resource.data.timezone)));},[resourceQuery.data]);
  const projectFiles = useQuery({ queryKey: ['industry', scope, 'files', project, fileOffset], enabled: kind === 'site_diary' && !!project && creating && !!caps.data, retry: false, queryFn: async () => {
    if (caps.data?.operational_scope?.pack_key === 'construction') {
      return (await api.get<{ project_files: { id: number; original_name: string }[] }>(ROOT + '/records', { params: { kind: 'site_diary', project_id: project, offset: fileOffset, limit: 50, include_files: true } })).data.project_files;
    }
    return (await api.get<{ id: number; original_name: string }[]>('/project-management/files', { params: { project_id: project, skip: fileOffset, limit: 50 } })).data;
  } });
  const boqQuery = useQuery({ queryKey: ['industry', scope, 'approved-boq', project], enabled: mode === 'construction' && !!project, retry: false, queryFn: async () => {
    const result = await Promise.all(['boq', 'variation'].map(k => api.get<{ items: Row[] }>(ROOT + '/records', { params: { kind: k, project_id: project, limit: 200 } })));
    return result.flatMap(r => r.data.items).filter(r => r.status === 'approved');
  } });
  const workPackages = useQuery({ queryKey: ['industry', scope, 'work-packages', project], enabled: mode === 'construction' && kind === 'measurement' && !!project, retry: false, queryFn: async () => (await api.get<{items: Row[]}>(ROOT + '/work-packages', {params:{project_id:project}})).data.items });
  const totals = useQuery({ queryKey: ['industry', scope, 'summary', project], enabled: mode === 'construction' && !!project, retry: false, queryFn: async () => (await api.get<Record<string, string>>(ROOT + `/projects/${project}/summary`)).data });
  const refresh = () => { void cache.invalidateQueries({queryKey:['appointment-payment-summary']}); void cache.invalidateQueries({ queryKey: ['scheduled-services'] }); return cache.invalidateQueries({ queryKey: ['industry', scope] }); };
  const listKey = ['industry', scope, kind, project, offset, day, week, zone];
  const accept = async (row: Row) => {
    await cache.cancelQueries({ queryKey: listKey, exact: true });
    cache.setQueryData<Row[]>(listKey, old => [row, ...(old || []).filter(r => r.id !== row.id)]);
  };
  const mutation = useMutation({ mutationFn: async ({ path, body }: { path: string; body: unknown }) => (await api.post(ROOT + path, body)).data, onSuccess: async (result, variables) => {
    if (result.kind) await accept(result);
    if (variables.path === '/appointments' && submittedDisplay.current) { setConfirmation({...submittedDisplay.current,row:result}); attemptRef.current=undefined;setAttempt(undefined);clearDraftStorage(storageKey); }
    else if (variables.path.endsWith('/invoice')) {
      await cache.cancelQueries({ queryKey: listKey, exact: true });
      const id = Number(variables.path.split('/')[2]);
      cache.setQueryData<Row[]>(listKey, old => old?.map(r => r.id === id ? { ...r, invoice_id: result.id, revision: r.revision + 1 } : r));
    }
    setNotice('Saved successfully.'); void refresh();
  }, onError: error => { const state=bookingError(error);setNotice(state.message);if(kind==='appointment' && state.uncertain && attemptRef.current){setAttempt(attemptRef.current);}else{lastDefinitiveAttempt.current=attemptRef.current;attemptRef.current=undefined;setAttempt(undefined);knownFailed.current=true;}  setBookingAvailable(null); setBookingReason('Confirmation failed. Review the latest availability and retry.'); void cache.invalidateQueries({queryKey:['prebooking-availability']}); } });
  const clearDraft = () => { clearDraftStorage(storageKey);setScheduleDraft(undefined);attemptRef.current=undefined;setAttempt(undefined);setRecoveryMessage('');setConfirmation(undefined); setChosenCustomer(undefined); setChosenService(undefined); setFormClosed(false); setBooking(undefined); setBookingAvailable(null); setCreating(false); setForm({ ...empty(), title: bookingOnly ? 'Service prebooking' : '', resource_type: mode === 'salon' ? 'stylist' : 'provider' }); setResources([]); setFiles([]); setFileOffset(0); requestId.current = crypto.randomUUID(); };
  useEffect(() => {
    setOffset(0);
    if(firstEditorMount.current){firstEditorMount.current=false;if(kind==='appointment' && restorable){setForm(f=>({...f,...restorable.form}));setCreating(true);if(restorable.attempt)setRecoveryMessage('A previous save has an unknown outcome. Check its status before editing.');else setNotice('Draft restored after refresh. Availability and pricing will be rechecked.');return;}}
    clearDraft();if(bookingOnly)setCreating(true);
  }, [kind, project]);
  useEffect(()=>{
    if(kind!=='appointment')return;
    if(!creating && !attempt){clearDraftStorage(storageKey);return;}
    const hasContent=!!form.customer_id || !!form.service_id || !!form.notes || !!attempt;
    if(hasContent && !saveDraft(storageKey,{version:1,form,schedule:scheduleDraft,requestId:requestId.current,attempt,savedAt:Date.now()}))setDraftStorageFailed(true);
  },[storageKey,kind,creating,form,scheduleDraft,attempt]);
  const [scopeNotice]=useState(()=>{try{const key=`prebooking-last-context:${userId}`;const previous=sessionStorage.getItem(key);sessionStorage.setItem(key,storageKey);return previous && previous!==storageKey ? 'Booking context changed. The previous draft is kept separately and has not been applied in this context.' : '';}catch{return '';}});
  useEffect(() => { if (prefill) { setConfirmation(undefined); setCreating(true); setFormClosed(false); } }, [prefill?.key]);
  const dirty = creating && (JSON.stringify(form) !== JSON.stringify({ ...empty(), title: bookingOnly ? 'Service prebooking' : '', resource_type: mode === 'salon' ? 'stylist' : 'provider' }) || resources.length > 0 || files.length > 0);
  useMobileDraftGuard({ enabled: creating, dirty, draftKey: requestId.current, pending: () => mutation.isPending || checkingFinal || !!attemptRef.current, onDiscard: clearDraft, message: 'Discard this unsaved operation?', guardHistory: true });
  const canLeave = () => !mutation.isPending && !checkingFinal && !attemptRef.current && (!dirty || window.confirm('Discard this unsaved operation?'));
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (e.target !== e.currentTarget || mutation.isPending || submitLock.current || attempt) return;
    let body: Record<string, unknown> = { request_id: requestId.current, title: kind === 'appointment' ? form.title || 'Service prebooking' : form.title };
    if (kind === 'resource') body = { ...body, resource_type: form.resource_type, capacity: Number(form.capacity || 1), timezone: form.timezone, opens: form.opens, closes: form.closes, weekdays: form.weekdays ? form.weekdays.split(',').map(Number) : [], ...(form.employee_id ? { employee_id: Number(form.employee_id) } : form.user_id ? { user_id: Number(form.user_id) } : {}) };
    if (kind === 'appointment' && (!form.customer_id || !form.service_id || !booking || bookingAvailable !== true)) { setNotice('Choose an eligible employee and an available time before confirming.'); requestAnimationFrame(()=>{
      const root = bookingFormRef.current;
      const employee = root?.querySelector<HTMLSelectElement>('[aria-label="Prebooking employee"]');
      const date = root?.querySelector<HTMLInputElement>('[aria-label="Prebooking date"]');
      const time = root?.querySelector<HTMLInputElement>('[aria-label="Prebooking start time"]');
      const target = !form.customer_id ? root?.querySelector<HTMLElement>('[data-customer-field] [role=combobox]') : !form.service_id ? root?.querySelector<HTMLElement>('[data-service-field] [role=combobox]') : !employee?.value ? employee : !date?.value ? date : !time?.value ? time : root?.querySelector<HTMLElement>('[aria-invalid=true] input:not(:disabled), [aria-invalid=true] select:not(:disabled), input:invalid, select:invalid, input[aria-invalid=true], select[aria-invalid=true]') || root?.querySelector<HTMLElement>('#prebooking-confirm-reason');
      target?.focus();
    }); return; }
    let currentBooking=booking;
    if(kind==='appointment'){
      submitLock.current=true;setCheckingFinal(true);
      try{
        const freshService=await validateQuote.current?.();
        const freshBooking=freshService && await validateSchedule.current?.();
        if(!freshService || !freshBooking){setNotice('The latest quote or availability could not be confirmed. Review the refreshed details.');return;}
        currentBooking=freshBooking;setBooking(freshBooking);
      }catch(error){setNotice(bookingError(error).uncertain?'Availability could not be checked. No booking was submitted.':bookingError(error).message);return;}
      finally{setCheckingFinal(false);submitLock.current=false;}
    }
    if (kind === 'appointment') body = { ...body, customer_id: Number(form.customer_id), service_id: Number(form.service_id), booking:currentBooking, resource_ids: currentBooking ? [currentBooking.provider_resource_id, ...(currentBooking.additional_resource_ids || [])] : resources, starts_at: currentBooking?.starts_at, duration_minutes: currentBooking?.duration_minutes, notes: form.notes || '', walk_in: form.walk_in === 'true', ...(form.project_id ? { project_id: Number(form.project_id), create_pms_task: true } : {}), ...(form.link_crm === 'true' && form.deal_id ? { deal_id: Number(form.deal_id) } : {}) };
    if (kind === 'boq' || kind === 'variation') body = { ...body, project_id: Number(project), code: form.code, unit: form.unit, quantity: form.quantity, unit_rate: form.unit_rate, tax_rate: form.tax_rate, ...(kind === 'variation' ? { variation_of: Number(form.parent_id) } : {}) };
    if (kind === 'measurement') body = { ...body, boq_id: Number(form.parent_id), quantity: form.quantity, measured_on: form.measured_on, notes: form.notes || '', ...(form.work_package_id ? {work_package_id:Number(form.work_package_id)} : {}) };
    if (kind === 'site_diary') body = { ...body, project_id: Number(project), entry_date: form.entry_date, work_done: form.work_done, workforce: Number(form.workforce), weather: form.weather || '', blockers: form.blockers || '', file_ids: files };
    if (kind === 'subcontract') body = { ...body, project_id: Number(project), vendor_id: Number(form.vendor_id), scope: form.scope, amount: form.amount, due_date: form.due_date };
    if (kind === 'material_issue') body = { ...body, project_id: Number(project), product_id: Number(form.product_id), warehouse_id: Number(form.warehouse_id), quantity: form.quantity, issue_date: form.issue_date, notes: form.notes || '' };
    if (kind === 'appointment' && currentBooking) submittedDisplay.current = {customerId:Number(form.customer_id),serviceId:Number(form.service_id),booking:currentBooking,email:chosenCustomer?.email,phone:chosenCustomer?.phone,customer:chosenCustomer?.name || `Customer #${form.customer_id}`,service:chosenService?.name || 'Service',employee:display.employee,timezone:display.timezone,resources:display.resources,startsAt:currentBooking.starts_at,minutes:currentBooking.duration_minutes};
    if(kind==='appointment'){
      if(knownFailed.current){const prior={...lastDefinitiveAttempt.current?.body,request_id:undefined},next={...body,request_id:undefined};if(JSON.stringify(prior)!==JSON.stringify(next))requestId.current=crypto.randomUUID();body.request_id=requestId.current;knownFailed.current=false;}
      attemptRef.current={body,display:submittedDisplay.current as unknown as Record<string,unknown>};
      if(!saveDraft(storageKey,{version:1,form,schedule:scheduleDraft,requestId:requestId.current,attempt:attemptRef.current,savedAt:Date.now()})){attemptRef.current=undefined;setNotice('Recovery storage is unavailable. Free browser storage before confirming.');setDraftStorageFailed(true);return;}
    }
    if(kind==='appointment')setAttempt(attemptRef.current);
    submitLock.current=true;
    try { await mutation.mutateAsync({ path: paths[kind], body }); setCreating(false); setForm({ ...empty(), title: bookingOnly ? 'Service prebooking' : '', resource_type: mode === 'salon' ? 'stylist' : 'provider' }); setResources([]); requestId.current = crypto.randomUUID(); } catch { /* Retain the exact request on uncertain outcomes. */ } finally {submitLock.current=false;}
  };
  const recovery=useMutation({mutationFn:async()=>{const pending=attempt || attemptRef.current;if(!pending)throw new Error('No request to check');return (await api.get<{state:string;appointment?:Row}>(ROOT+`/appointments/requests/${pending.body.request_id}`,{recordCache:false})).data;},onSuccess:result=>{const pending=attempt || attemptRef.current;if(result.state==='confirmed' && result.appointment && pending){setConfirmation({...pending.display,row:result.appointment} as unknown as ConfirmedPrebooking);setCreating(false);setAttempt(undefined);attemptRef.current=undefined;clearDraftStorage(storageKey);void refresh();}else setRecoveryMessage('No confirmed booking was found yet. The original request can be retried safely; its details remain locked.');}});
  async function retryOriginal(){const pending=attempt || attemptRef.current;if(!pending || mutation.isPending)return;submittedDisplay.current=pending.display as unknown as Omit<ConfirmedPrebooking,'row'>;submitLock.current=true;try{const result=await mutation.mutateAsync({path:'/appointments',body:pending.body});setCreating(false);setConfirmation({...pending.display,row:result} as unknown as ConfirmedPrebooking);clearDraftStorage(storageKey);}catch{/* Keep original immutable intent until a definitive result. */}finally{submitLock.current=false;}}
  async function repeatAppointment(id:number){
    if(!canLeave())return;
    try{const record=(await api.get<Row>(ROOT+`/appointments/${id}`,{recordCache:false})).data;const serviceId=Number(record.data.service_id);if(!serviceId)throw new Error('Service identity unavailable');const options=(await api.get<import('./POSServiceScheduling').Options>('/srm/service-checkout/options',{params:{service_id:serviceId},recordCache:false})).data;const ids=record.data.resource_ids as number[] || [];const person=options.specialists.find(p=>ids.includes(p.provider_resource_id));const tz=person?.timezone || options.branch_timezone || 'UTC';const oldLocal=wall(Date.parse(String(record.data.starts_at)),tz);const tomorrow=wall(Date.now()+86400000,tz).slice(0,10);clearDraft();setForm(f=>({...f,customer_id:String(record.customer_id || ''),service_id:String(serviceId)}));setScheduleDraft({versionKey:crypto.randomUUID(),serviceId,employeeId:person?.employee_id,date:tomorrow,time:oldLocal.slice(11),timezone:tz,duration:String(record.data.duration_minutes),resources:ids.filter(i=>options.resources?.some(r=>r.id===i))});setCreating(true);setNotice('Copied into a new draft for tomorrow. Review the date, latest price and availability; nothing has been booked yet.');}catch{setNotice('This appointment could not be copied. Check access and the service setup.');}
  }
  function bookAnother(mode?:'same_customer'|'repeat'){
    const saved=confirmation;if(!saved)return;clearDraft();setSlot(undefined);setCreating(true);
    if(mode){setForm(f=>({...f,customer_id:String(saved.customerId || saved.row.customer_id || ''),...(mode==='repeat'?{service_id:String(saved.serviceId || '')}:{})}));setChosenCustomer({id:saved.customerId || saved.row.customer_id || 0,name:saved.customer,email:saved.email,phone:saved.phone});}
    if(mode==='repeat' && saved.booking){const local=wall(Date.parse(saved.startsAt),saved.timezone);setScheduleDraft({versionKey:crypto.randomUUID(),serviceId:saved.serviceId!,employeeId:saved.booking.employee_id,date:wall(Date.now()+86400000,saved.timezone).slice(0,10),time:local.slice(11),timezone:saved.timezone,duration:String(saved.minutes),resources:saved.booking.additional_resource_ids || []});setNotice('Repeated as a draft for tomorrow. Review and confirm its availability.');}
  }
  useEffect(()=>()=>{if(!useAuthStore.getState().isAuthenticated){try{for(const key of Object.keys(sessionStorage))if(key.startsWith('suite-prebooking-v4:'))sessionStorage.removeItem(key);}catch{/* Session storage can be disabled. */}}},[]);
  const transition = (row: Row, status: string) => {
    const reason = ['cancelled', 'no_show', 'rejected'].includes(status) ? window.prompt('Reason') : '';
    if (reason === null) return;
    void mutation.mutateAsync({ path: `/records/${row.id}/transition`, body: { expected_revision: row.revision, status, reason } }).catch(() => {});
  };
  const invoice = (row: Row) => {
    void mutation.mutateAsync({ path: `/records/${row.id}/invoice`, body: { expected_revision: row.revision, retention_percent: row.kind === 'measurement' ? form.retention_percent : 0 } }).catch(() => {});
  };
  const input = (key: string, label: string, type = 'text', required = true) => <Field name={label}><Input aria-label={label} type={type} required={required} value={form[key] || ''} min={type === 'number' ? 0 : undefined} step={type === 'number' ? 'any' : undefined} maxLength={type === 'text' ? 220 : undefined} onChange={e => update(key, e.target.value)} /></Field>;
  const parent = <Field name="Approved BOQ item"><select className={controls} aria-label="Approved BOQ item" required value={form.parent_id || ''} onChange={e => update('parent_id', e.target.value)}><option value="">Choose item</option>{boqQuery.data?.map(r => <option key={r.id} value={r.id}>{String(r.data.code)} · {r.title}</option>)}</select>{boqQuery.isError && <p role="alert">{dealError(boqQuery.error)}</p>}</Field>;
  const bookingForm = creating && <form ref={bookingFormRef} style={formClosed ? {display:'none'} : undefined} onInvalidCapture={e=>{const field=e.target as HTMLElement; const detail=field.closest('details'); if(detail)detail.open=true; requestAnimationFrame(()=>field.focus());}} onSubmit={e => void submit(e)} className={`${mode !== 'construction' ? 'bookings-operation-form ' : ''}grid gap-4 rounded-lg border p-4`} aria-label="Create operation"><h2 className="font-semibold">New {kind === 'appointment' ? bookingOnly ? 'prebooking' : term('appointment').toLowerCase() : kind === 'resource' ? `${term('provider').toLowerCase()} / ${term('resource').toLowerCase()}` : kind.replace('_', ' ')}</h2>{kind === 'appointment' && !bookingOnly && <Button type="button" variant="ghost" onClick={() => setFormClosed(true)}>Close prebooking panel</Button>}<fieldset disabled={mutation.isPending || checkingFinal || !!attempt} className="grid gap-4 md:grid-cols-2">{!bookingOnly && kind !== 'appointment' && input('title', 'Title')}
      {kind === 'resource' && <><Field name="Resource type"><select className={controls} aria-label="Resource type" value={form.resource_type} onChange={e => update('resource_type', e.target.value)}>{resourceTypes.map(v => <option key={v} value={v}>{resourceTypeLabel(v)}</option>)}</select></Field>{['provider', 'doctor', 'stylist', 'consultant', 'technician', 'employee'].includes(form.resource_type) && <><Field name="HRMS employee (optional)"><StaffPicker employee value={form.employee_id || ''} change={v => { update('employee_id', v); update('user_id', ''); }}/></Field>{!form.employee_id && <Field name="Linked staff account (optional)"><StaffPicker value={form.user_id || ''} change={v => update('user_id', v)}/></Field>}</>}{!['provider','doctor','stylist','consultant','technician','employee'].includes(form.resource_type) && input('capacity', 'Simultaneous capacity', 'number')}{input('timezone', 'Timezone')}{input('opens', 'Opens', 'time')}{input('closes', 'Closes', 'time')}<fieldset className="flex flex-wrap gap-3"><legend className="text-sm">Working days</legend>{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d, i) => <label key={d} className="flex gap-1 text-sm"><input type="checkbox" checked={form.weekdays.split(',').includes(String(i))} onChange={e => update('weekdays', e.target.checked ? [...form.weekdays.split(',').filter(Boolean), String(i)].sort().join(',') : form.weekdays.split(',').filter(v => v !== String(i)).join(','))} />{d}</label>)}</fieldset></>}
      {kind === 'appointment' && <>{(!form.customer_id || !form.service_id) && <section className="md:col-span-2 prebooking-issues" aria-label="Booking details to complete"><strong>Complete booking details</strong>{[...(!form.customer_id?[{label:'Choose a customer',selector:'[data-customer-field] [role=combobox]'}]:[]),...(!form.service_id?[{label:'Choose a service',selector:'[data-service-field] [role=combobox]'}]:[])].map(issue=><div key={issue.label}><button type="button" onClick={()=>bookingFormRef.current?.querySelector<HTMLElement>(issue.selector)?.focus()}>{issue.label}</button></div>)}</section>}<div className="md:col-span-2" data-customer-field><Field name={term('customer')}><PrebookingCustomer value={form.customer_id || ''} onChange={v=>update('customer_id',v)} onSelected={setChosenCustomer}/></Field></div><div className="md:col-span-2"><PrebookingCustomerContext customerId={Number(form.customer_id)||0} serviceId={Number(form.service_id)||undefined} startsAt={display.startsAt} onRepeat={id=>void repeatAppointment(id)}/></div><div className="md:col-span-2" data-service-field><PrebookingServicePicker validateRef={validateQuote} onQuoteReady={setQuoteReady} value={form.service_id || ''} onSelected={setChosenService} onChange={v=>{update('service_id',v);setBooking(undefined);setBookingAvailable(null);}}/></div><div className="md:col-span-2"><PrebookingFields initialDraft={scheduleDraft} onDraftChange={setScheduleDraft} validateRef={validateSchedule} serviceId={Number(form.service_id) || 0} prefill={prefill || slot} onChange={setBooking} onAvailability={setBookingAvailable} onReason={setBookingReason} onDisplay={setDisplay}/></div><details className="prebooking-more md:col-span-2"><summary>More details</summary><div className="prebooking-more-body">{caps.data?.projects_enabled !== false && <Field name={`PMS delivery ${term('project').toLowerCase()} (optional)`}><ProjectPicker value={form.project_id || ''} change={v => update('project_id', v)} /></Field>}{input('notes', 'Visit notes', 'text', false)}{caps.data?.crm_enabled !== false && <label className="flex gap-2 text-sm"><input type="checkbox" checked={form.link_crm === 'true'} onChange={e => update('link_crm', String(e.target.checked))} />Link an existing CRM opportunity</label>}{form.link_crm === 'true' && <Field name="CRM opportunity"><DealRecordSelect resource="deals" name="CRM opportunity" initial={[]} companyId={form.customer_id} value={form.deal_id || ''} onChange={v => update('deal_id', v)} /></Field>}<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.walk_in === 'true'} onChange={e => update('walk_in', String(e.target.checked))} />Walk-in</label>{kind === 'appointment' && caps.data?.manage && <details className="scheduler-private-link"><summary>Private booking link</summary><AppointmentBookingLink key={`${form.customer_id}:${form.service_id}:${booking?.additional_resource_ids?.join(',') || ''}:${booking?.duration_minutes || ''}`} customerId={Number(form.customer_id)} serviceId={Number(form.service_id)} resourceIds={booking ? [booking.provider_resource_id,...(booking.additional_resource_ids || [])] : []} durationMinutes={booking?.duration_minutes || 30} workspaceId={bookingWorkspace}/></details>}</div></details></>}
      {(kind === 'boq' || kind === 'variation') && <>{kind === 'variation' && parent}{input('code', 'Item code')}{input('unit', 'Unit')}{input('quantity', 'Quantity', 'number')}{input('unit_rate', 'Unit rate', 'number')}{input('tax_rate', 'Tax (%)', 'number')}</>}
      {kind === 'measurement' && <>{parent}<Field name="WBS work package (optional)"><select className={controls} aria-label="WBS work package (optional)" value={form.work_package_id || ''} onChange={e => update('work_package_id', e.target.value)}><option value="">Choose work package for earned-value tracking</option>{workPackages.data?.filter(row => row.parent_id === Number(form.parent_id)).map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select>{workPackages.isError && <p role="alert">{dealError(workPackages.error)}</p>}</Field>{input('quantity', 'Measured quantity', 'number')}{input('measured_on', 'Measured on', 'date')}{input('notes', 'Measurement notes', 'text', false)}</>}
      {kind === 'site_diary' && <>{input('entry_date', 'Entry date', 'date')}{input('workforce', 'Workforce count', 'number')}{input('weather', 'Weather', 'text', false)}<Field name="Work completed"><textarea className={controls} aria-label="Work completed" required maxLength={10000} value={form.work_done || ''} onChange={e => update('work_done', e.target.value)} /></Field>{input('blockers', 'Blockers', 'text', false)}<fieldset className="grid gap-2"><legend className="text-sm">{term('project')} photos &amp; documents</legend>{projectFiles.data?.map(f => <label key={f.id} className="flex gap-2 text-sm"><input type="checkbox" checked={files.includes(f.id)} onChange={e => setFiles(v => e.target.checked ? [...v, f.id] : v.filter(id => id !== f.id))} />{f.original_name}</label>)}{projectFiles.isError && <p role="alert">{dealError(projectFiles.error)}</p>}<div className="flex gap-2"><Button type="button" size="sm" variant="outline" disabled={!fileOffset} onClick={() => setFileOffset(v => Math.max(0, v - 50))}>Previous files</Button><Button type="button" size="sm" variant="outline" disabled={!projectFiles.data || projectFiles.data.length < 50} onClick={() => setFileOffset(v => v + 50)}>More files</Button></div><Link to={`/pms/files?constructionProject=${project}`}>Upload photos in PMS Files</Link></fieldset></>}
      {kind === 'subcontract' && <><Field name="Vendor"><CompanySelect source="srm" label="Vendor" value={form.vendor_id || ''} onChange={v => update('vendor_id', v)} createRoles={['Vendor']} /></Field>{input('scope', 'Work scope')}{input('amount', 'Commitment amount', 'number')}{input('due_date', 'Due date', 'date')}</>}
      {kind === 'material_issue' && <><Field name="Stock item"><ServicePicker kind="product" value={form.product_id || ''} change={v => update('product_id', v)} /></Field><Field name="Warehouse"><ConstructionWarehouseSelect value={form.warehouse_id || ''} onChange={value => update('warehouse_id', value)} /></Field>{input('quantity', 'Consumed quantity', 'number')}{input('issue_date', 'Issue date', 'date')}{input('notes', 'Issue notes', 'text', false)}<p className="text-sm text-muted-foreground">Posts an actual stock consumption at the warehouse average cost. Insufficient stock is blocked.</p></>}
    </fieldset>{kind==='appointment' && form.service_id && <section className="prebooking-review" aria-label="Review prebooking"><strong>Review before confirming</strong><p>{chosenCustomer?.name || 'Choose customer'} · {chosenService?.name || 'Service'}</p><p>{display.employee || 'Choose employee'} · {display.startsAt?new Date(display.startsAt).toLocaleString(undefined,{timeZone:display.timezone}):'Choose time'} · {display.timezone}</p><p>{display.resources.join(', ') || 'No additional resources'} · {display.minutes || ''} minutes</p><small>Estimated price before tax; final amount is confirmed in POS. No payment is collected here.</small></section>}<footer className={kind === 'appointment' ? 'prebooking-footer' : ''}>{kind === 'appointment' && <><p id="prebooking-confirm-reason" tabIndex={-1} role="status">{!form.customer_id ? 'Choose a customer before confirming.' : !form.service_id ? 'Choose a service.' : bookingAvailable !== true || !booking ? bookingReason || 'Review booking details.' : mutation.isPending ? 'Confirming your prebooking…' : checkingFinal ? 'Rechecking the latest price and availability…' : !quoteReady ? 'Review the latest service quote.' : 'Ready to confirm your prebooking.'}</p><p className="text-xs text-muted-foreground">No payment collected. Collect later in POS.</p></>}<div className="flex gap-2"><Button type="submit" aria-describedby={kind === 'appointment' ? 'prebooking-confirm-reason' : undefined} disabled={mutation.isPending || checkingFinal || !!attempt || (kind === 'appointment' && !quoteReady) || (kind === 'material_issue' && !form.warehouse_id) || (kind === 'appointment' && (!form.customer_id || !form.service_id || !booking || bookingAvailable !== true))}>{mutation.isPending ? 'Saving…' : kind === 'appointment' ? 'Confirm prebooking' : 'Save operation'}</Button><Button type="button" variant="outline" disabled={mutation.isPending || checkingFinal || !!attempt} onClick={() => { if (canLeave()) { clearDraft(); setSlot(undefined); onDiscard?.(); } }}>{kind === 'appointment' ? 'Cancel prebooking' : 'Cancel'}</Button></div></footer></form>;
  const recoveryPanel=kind==='appointment' && attempt && <section className="prebooking-recovery" role="alert"><strong>Save outcome needs checking</strong><p>{recoveryMessage || 'The original request is retained and editing is locked to prevent a duplicate booking.'}</p><Button type="button" variant="outline" disabled={recovery.isPending || mutation.isPending} onClick={()=>recovery.mutate()}>Check booking status</Button><Button type="button" disabled={mutation.isPending || recovery.isPending} onClick={()=>void retryOriginal()}>Retry original request</Button>{recovery.isError && <p>Booking status could not be checked. Keep this draft and try again.</p>}</section>;
  const draftNotice=kind==='appointment' && <div className="prebooking-draft-status">{scopeNotice && <p role="status">{scopeNotice}</p>}{draftStorageFailed?<p role="alert">Draft recovery storage is unavailable. Your in-memory edits remain; confirmation is blocked until recovery storage works.</p>:creating && (form.customer_id || form.service_id || form.notes)?<small>Draft preserved for refresh in this tab and this booking context.</small>:null}</div>;
  const success = confirmation && <PrebookingSuccess saved={confirmation} capabilities={caps.data || {}} onChanged={()=>void refresh()} onAnother={bookAnother}/>;
  const formSurface = <PrebookingSurface open={(creating || !!confirmation) && !formClosed} onClose={()=>setFormClosed(true)}>{draftNotice}{bookingForm}{recoveryPanel}{success}</PrebookingSurface>;
  if (bookingOnly && !caps.data?.manage) return <aside className="scheduler-prebooking"><p>{caps.isPending ? 'Checking booking permissions…' : caps.isError ? 'Booking permissions could not load.' : 'Your access allows viewing planned engagement. Booking requires appointment management permission.'}</p></aside>;
  if (bookingOnly) return <PrebookingSurface open={panelOpen} onClose={()=>onClose?.()}><aside className="scheduler-prebooking" aria-label="New prebooking">{onClose && <Button type="button" variant="ghost" aria-label="Close prebooking panel" onClick={onClose}>Close</Button>}{!creating && !confirmation && <Button onClick={()=>{clearDraft();setCreating(true);}}>New prebooking</Button>}{draftNotice}{bookingForm}{recoveryPanel}{success}{notice && !confirmation && <p role="status">{notice}</p>}{mutation.isError && <p role="alert">{dealError(mutation.error)}</p>}</aside></PrebookingSurface>;
  const content = <main className={mode === 'construction' ? "mx-auto grid max-w-6xl gap-5 p-4 md:p-6" : "bookings-operations min-w-0 grid gap-4"}>
    {mode === 'construction' && <header className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-semibold">{mode !== 'construction' ? term('appointment', true) : 'Construction operations'}</h1><p className="text-sm text-muted-foreground">{mode !== 'construction' ? 'Schedule people, services and resources for your business.' : 'Approve scope, record site work and bill certified quantities through Sales.'}</p></div><nav className="flex flex-wrap gap-3 text-sm"><Link to="/crm/pipeline-templates">CRM industry packs</Link><Link to="/srm/products-services">Catalog</Link><Link to="/srm/invoices">Invoices</Link><Link to="/srm/collections">Collections</Link><Link to={mode !== 'construction' ? '/srm/pos' : '/srm/inventory'}>{mode !== 'construction' ? 'Retail POS' : 'Materials & purchasing'}</Link></nav></header>}
    {mode === 'construction' && <><Suspense fallback={null}><ConstructionSiteCreate onCreated={created => { void cache.invalidateQueries({ queryKey: ['industry-projects', scope] }); if (canLeave()) { setSelectedProject(created); setProject(String(created.id)); } }} /></Suspense><Field name={`PMS ${term('project').toLowerCase()}`}><ProjectPicker value={project} hint={selectedProject} change={v => { if (canLeave()) { setSelectedProject(undefined); setProject(v); } }} /></Field>{project && <div className="flex flex-wrap gap-3 text-sm"><Link to={`/pms/projects/${project}/billing`}>{term('customer')} &amp; {term('project').toLowerCase()} billing</Link><Link to={`/pms/projects/${project}`}>PMS schedule, tasks & files</Link></div>}{totals.data && <section className="grid grid-cols-2 gap-4 rounded-lg border p-4 md:grid-cols-4" aria-label="Project commercial summary">{[['Approved scope', 'approved_scope_value'], ['Certified work', 'certified_value'], ['Unbilled work', 'unbilled_certified_value'], ['Committed subcontracts', 'committed_subcontracts']].map(([label, key]) => <div key={key}><p className="text-xs text-muted-foreground">{label}</p><strong>{totals.data.currency} {Number(totals.data[key]).toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></div>)}<p className="col-span-full text-xs text-muted-foreground">Before tax. Materials consumed: {totals.data.material_cost_currency} {Number(totals.data.actual_material_cost).toLocaleString(undefined, { minimumFractionDigits: 2 })}. Retention tracked: {totals.data.currency} {Number(totals.data.retention_tracked).toLocaleString(undefined, { minimumFractionDigits: 2 })}. Retention remains within the full invoice receivable.</p></section>}</>}
    <div hidden={kind==='appointment'} className={mode === 'construction' ? "flex flex-wrap gap-2" : "bookings-operation-tabs"} role="tablist" aria-label="Operations">{(mode !== 'construction' ? ['appointment', 'resource'] : ['boq', 'variation', 'measurement', 'site_diary', 'subcontract', 'material_issue']).map(k => <Button role="tab" aria-selected={kind === k} variant={kind === k ? 'default' : 'outline'} key={k} onClick={() => { if (canLeave()) setKind(k); }}>{labels[k]}</Button>)}</div>
    {(mode !== 'construction' || project) && <div className={mode === 'construction' ? "flex flex-wrap gap-2" : kind === 'appointment' ? 'appointment-actions-source' : 'bookings-operation-controls'}>{caps.data?.manage && <Button onClick={() => { if (canLeave()) { clearDraft(); setCreating(true); setNotice(''); } }}>New {kind === 'appointment' ? bookingOnly ? 'prebooking' : term('appointment').toLowerCase() : kind === 'resource' ? `${term('provider').toLowerCase()} / ${term('resource').toLowerCase()}` : kind.replace('_', ' ')}</Button>}<Button variant="outline" disabled={rows.isFetching} onClick={() => void refresh()}>Refresh</Button></div>}
    <div className={kind === 'appointment' ? 'appointment-booking-layout' : ''}>
    {kind === 'appointment' && <AppointmentTimeline showPayments={!!caps.data?.billing} day={day} week={week} zone={zone} onWeek={value=>{setWeek(value);setOffset(0);}} onDay={value=>{setDay(value);setOffset(0);}} actions={<><Button disabled={!caps.data?.manage} onClick={()=>{if(canLeave()){clearDraft();setCreating(true);setFormClosed(false);}}}>New {term('appointment').toLowerCase()}</Button><Button variant="outline" disabled={rows.isFetching} onClick={()=>void refresh()}>Refresh</Button></>} onSlot={caps.data?.manage ? next => { setSlot(next); setCreating(true); setFormClosed(false); setNotice(''); } : undefined} rows={rows.data || []} resources={resourceQuery.data || []} onSelect={id=>document.getElementById(`booking-record-${id}`)?.scrollIntoView({behavior:'smooth',block:'start'})}/>}
    {(creating || !!confirmation) && formClosed && <Button onClick={() => setFormClosed(false)}>Resume prebooking</Button>}
    {kind === 'appointment' ? formSurface : bookingForm}
    </div>
    {notice && <p role="status">{notice}</p>}{mutation.isError && <p role="alert" className="text-sm text-destructive">{dealError(mutation.error)}</p>}{rows.isError && <div role="alert">{dealError(rows.error)} <Button variant="outline" onClick={() => void rows.refetch()}>Retry</Button></div>}{rows.isFetching && <p role="status">Loading operations…</p>}
    {kind === 'measurement' && input('retention_percent', 'Retention to track on new invoices (%)', 'number', false)}
    {mode !== 'construction' && rows.isSuccess && <div className="bookings-agenda-strip" aria-label="Loaded schedule summary"><div><strong>{rows.data.length}</strong><span>Loaded {kind === 'resource' ? 'resources' : 'appointments'}</span></div><div><strong>{rows.data.filter(row=>kind==='resource'?row.status==='active':['booked','checked_in','in_service'].includes(row.status)).length}</strong><span>{kind==='resource'?'Active resources':'Booked / in progress'}</span></div><div><strong>{rows.data.filter(row=>kind==='resource'?['room','chair','equipment','location'].includes(String(row.data.resource_type)):row.status==='completed').length}</strong><span>{kind==='resource'?'Rooms & equipment':'Completed in loaded view'}</span></div><p className="self-center text-xs text-muted-foreground">{day ? `Selected date: ${day}` : 'Current branch  /  loaded records only'}</p></div>}
    <section className={mode === 'construction' ? "grid gap-3" : "bookings-operation-cards"} aria-label={labels[kind]}>{rows.data?.map(row => <article id={`booking-record-${row.id}`} key={row.id} className={mode === 'construction' ? "grid gap-3 rounded-lg border p-4" : "bookings-operation-card"}><div className="flex flex-wrap justify-between gap-2"><h2 className="font-semibold">{row.title}</h2>{row.kind==='appointment' && <AppointmentPaymentStatus id={row.id} revision={row.revision} enabled={!!caps.data?.billing}/>}<span className={mode==='construction'?"text-sm":"bookings-status"} data-status={row.status}>{row.status.replace('_', ' ')}</span></div><p className="text-sm text-muted-foreground">{row.kind === 'appointment' ? `${String(row.data.service_name)} · ${bookingLabel(String(row.data.starts_at),zone)} · ${row.data.duration_minutes} min` : row.kind === 'resource' ? `${resourceTypeLabel(String(row.data.resource_type))} · ${row.data.opens}–${row.data.closes} · ${row.data.timezone}` : row.kind === 'site_diary' ? `${row.data.entry_date} · ${row.data.work_done}` : row.kind === 'subcontract' ? `${row.data.scope} · ${row.data.amount}` : row.kind === 'material_issue' ? `${row.data.product_name} · ${row.data.quantity} consumed from ${row.data.warehouse_name} · ${row.data.movement_number}` : `${row.data.code || row.data.boq_code || ''} · ${row.data.quantity} ${row.data.unit} × ${row.data.unit_rate}`}</p>{mode !== 'construction' && row.kind === 'appointment' && <div className="bookings-resource-pills" aria-label="Assigned employees and resources">{(row.data.resource_ids as number[] || []).map(id=><span key={id}>{resourceQuery.data?.find(resource=>resource.id===id)?.title || `Resource #${id}`}</span>)}<span>To {`${bookingLabel(Date.parse(String(row.data.starts_at))+Number(row.data.duration_minutes || 0)*60000,zone)} (${zone})`}</span></div>}<div className="flex flex-wrap gap-2">
      {row.kind === 'appointment' && ({ booked: ['checked_in', 'cancelled', 'no_show'], checked_in: ['in_service', 'cancelled'], in_service: ['completed'] } as Record<string, string[]>)[row.status]?.filter(canTransition).map(s => <Button size="sm" variant="outline" key={s} disabled={mutation.isPending || (s === 'no_show' && new Date(String(row.data.starts_at)).getTime() > Date.now())} title={s === 'no_show' ? 'Record a no-show after the appointment starts' : undefined} onClick={() => transition(row, s)}>{s.replace('_', ' ')}</Button>)}
      {row.kind === 'appointment' && <AppointmentVisitPanel timezone={zone} row={row} providers={(row.data.resource_ids as number[] || []).map(id => resourceQuery.data?.find(resource => resource.id === id)?.title || `#${id}`)} canViewBilling={!!caps.data?.billing} canCollect={!!caps.data?.collect} canInvoice={!!caps.data?.invoice} canApprove={!!caps.data?.approve_invoice} onChanged={() => void refresh()} actions={<><div className="flex flex-wrap gap-2">{({ booked: ['checked_in', 'cancelled', 'no_show'], checked_in: ['in_service', 'cancelled'], in_service: ['completed'] } as Record<string, string[]>)[row.status]?.filter(canTransition).map(status => <Button key={status} size="sm" variant="outline" disabled={mutation.isPending || (status === 'no_show' && new Date(String(row.data.starts_at)).getTime() > Date.now())} onClick={() => transition(row, status)}>{status.replace(/_/g, ' ')}</Button>)}</div>{caps.data?.manage && row.status === 'booked' && <RescheduleForm key={row.revision} row={row} resources={resourceQuery.data || []} saved={async updated => { await accept(updated); void refresh(); }}/>}</>}/>}
      {caps.data?.approve && (caps.data.self_approve || row.created_by !== userId) && ['boq', 'variation', 'measurement', 'subcontract'].includes(row.kind) && row.status === 'draft' && ['approved', 'rejected'].map(s => <Button key={s} size="sm" variant="outline" disabled={mutation.isPending} onClick={() => transition(row, s)}>{s === 'approved' ? 'Approve' : 'Reject'}</Button>)}
      {!!row.data.deal_id && <Link className="text-sm underline" to={`/crm/deals/${row.data.deal_id}`}>Open CRM opportunity</Link>}{!!row.data.pms_task_id && <Link className="text-sm underline" to={`/pms/tasks/${row.data.pms_task_id}`}>Open PMS delivery task</Link>}{row.invoice_id ? <Link to={`/srm/invoices/${row.invoice_id}`} className="text-sm underline">Open shared invoice</Link> : caps.data?.invoice && ((row.kind === 'appointment' && row.status === 'completed') || (row.kind === 'measurement' && row.status === 'approved')) && <Button size="sm" disabled={mutation.isPending} onClick={() => invoice(row)}>Create invoice draft</Button>}
    </div>{caps.data?.manage && row.kind === 'appointment' && row.status === 'booked' && <RescheduleForm key={row.revision} row={row} resources={resourceQuery.data || []} saved={async updated => { await accept(updated); setNotice(`${term('appointment')} rescheduled.`); void refresh(); }} />}</article>)}</section>
    {rows.data?.length === 0 && <p className="text-sm text-muted-foreground">No {labels[kind].toLowerCase()} recorded in this branch{mode === 'construction' ? ' and project' : ''}.</p>}
    {!!rows.data?.length && <div className="flex gap-2"><Button variant="outline" disabled={!offset} onClick={() => setOffset(n => Math.max(0, n - 100))}>Previous</Button><Button variant="outline" disabled={rows.data.length < 100} onClick={() => setOffset(n => n + 100)}>Next</Button></div>}
    {mode === 'construction' && !!project && <Suspense fallback={<p role="status">Loading project planning tools...</p>}><ConstructionPlanningPanel projectId={Number(project)} onSaved={() => { void refresh(); }} /></Suspense>}
  </main>;
  if (mode === 'construction') return content;
  const base = location.pathname.startsWith('/crm') ? '/crm' : '/srm';
  return <SchedulingFrame title={kind === 'resource' ? 'Employees & resources' : term('appointment', true)} subtitle="Manage service appointments, staff availability and your working day." nav={[
    {label:'Appointments',icon:schedulingIcons.calendar,active:kind==='appointment',onClick:()=>{if(canLeave())setKind('appointment');}},
    {label:'Employees & resources',icon:schedulingIcons.resources,active:kind==='resource',onClick:()=>{if(canLeave())setKind('resource');}},
    {label:'Calendar & Gantt',icon:schedulingIcons.timeline,to:`${base}/service-scheduling?view=schedule&mode=Calendar`},
    {label:'Service types',icon:schedulingIcons.services,to:'/srm/inventory/products?kind=service'},
    {label:'Availability',icon:schedulingIcons.time,to:`${base}/service-scheduling?view=availability`},
    {label:'Setup guide',icon:schedulingIcons.guide,to:`${base}/service-scheduling?view=guide`},
  ]}>{content}</SchedulingFrame>;
}
