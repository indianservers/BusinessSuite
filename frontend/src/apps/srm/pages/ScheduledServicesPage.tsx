import MobileWorkflowPages from "../components/MobileWorkflowPages";
import MobileScheduleAgenda from "../components/MobileScheduleAgenda";
import { useMobile } from "@/components/mobile/useMobile";
import type { BookingSlot } from '@/shared/scheduling/PrebookingFields';
import { CalendarDays, SlidersHorizontal } from 'lucide-react';
import SchedulingFrame, { schedulingIcons } from '@/shared/scheduling/SchedulingFrame';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { api } from '@/services/api';
import { useRecordScope } from '@/lib/record-scope';
import { defaultText } from '@/lib/form-defaults';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';

type Booking = {
  resources?: {id:number;name:string;resource_type:string}[]; employee_categories?: string[];
  appointment_id: number; revision: number; employee_id: number; employee_name: string; employee_code: string;
  service_id: number | null; service_name: string; starts_at: string; ends_at: string;
  planned_minutes: number; status: string; blocks_availability: boolean;
};
type Projection = {
  company_id: number; pack_context_id: number | null; timezone: string; from_at: string; until_at: string;
  items: Booking[]; next_cursor: string | null;
  filter_options: { employees: { id: number; name: string; code: string }[]; services: { id: number; name: string }[]; employees_complete: boolean; services_complete: boolean };
};
type Mode = 'List' | 'Calendar' | 'Gantt';
const MINUTE = 60_000, DAY = 86_400_000;
function validZone(zone: string) { try { new Intl.DateTimeFormat('en', { timeZone: zone }).format(); return !!zone; } catch { return false; } }
function wall(instant: number, zone: string) {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(instant);
  const part = (key: string) => parts.find(value => value.type === key)?.value || '';
  return `${part('year')}-${part('month')}-${part('day')}T${part('hour')}:${part('minute')}`;
}
/** Round-trip offsets: reject DST gaps and ambiguous wall times instead of guessing. */
function instants(value: string, zone: string) {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return [];
  const nominal = Date.parse(`${value}:00Z`);
  if (!Number.isFinite(nominal)) return [];
  const offsets = new Set<number>();
  for (let hour = -36; hour <= 36; hour += 6) {
    const sample = nominal + hour * 60 * MINUTE;
    offsets.add(Date.parse(`${wall(sample, zone)}:00Z`) - sample);
  }
  return [...offsets].map(offset => nominal - offset).filter(instant => wall(instant, zone) === value).sort((a, b) => a - b);
}
function shiftDay(value: string, days: number) { const stamp = Date.parse(`${value}T12:00:00Z`); return Number.isFinite(stamp) ? new Date(stamp + days * DAY).toISOString().slice(0, 10) : ''; }
function dayBoundary(day: string, zone: string) {
  // Some zones skip midnight. The day starts at its first valid local minute.
  for (let minute = 0; minute < 1440; minute++) {
    const value = `${day}T${String(Math.floor(minute / 60)).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')}`;
    const matches = instants(value, zone);
    if (matches.length) return matches[0];
  }
  return NaN;
}
function label(instant: string | number, zone: string) {
  return new Intl.DateTimeFormat(undefined, { timeZone: zone, month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' }).format(new Date(instant));
}
function description(item: Booking, zone: string) { return `${item.employee_name}: ${item.service_name}, ${label(item.starts_at, zone)} to ${label(item.ends_at, zone)}, ${item.status}${item.resources?.length ? ', '+item.resources.map(resource=>resource.name).join(', ') : ''}`; }
function lanes(items: Booking[]) {
  const ends: number[] = [];
  const placed = [...items].sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at) || a.appointment_id - b.appointment_id).map(item => {
    let lane = ends.findIndex(end => end <= Date.parse(item.starts_at));
    if (lane < 0) lane = ends.length;
    ends[lane] = Date.parse(item.ends_at);
    return { item, lane };
  });
  return { placed, count: Math.max(1, ends.length) };
}

export default function ScheduledServicesPage({ packContextId, embedded = false, onSlot }: { packContextId?: number; embedded?: boolean; onSlot?: (slot: BookingSlot) => void }) {
  const scope = useRecordScope(), location = useLocation();
  const base = location.pathname.startsWith('/crm') ? '/crm' : location.pathname.startsWith('/hrms') ? '/hrms' : '/srm';
  const content = <Services key={`${scope}:${packContextId || ''}`} scope={scope} packContextId={packContextId} onSlot={onSlot}/>;
  if (embedded) return content;
  return <SchedulingFrame title="Appointment Scheduler" subtitle="Plan services, people and resources." nav={[
    {label:'Schedule & Gantt',icon:schedulingIcons.calendar,active:true,to:base==='/crm'?`${base}/service-scheduling?view=schedule`:`${base}/scheduled-services`},
    {label:'Appointments',icon:schedulingIcons.timeline,to:`${base==='/crm'?'/crm':'/srm'}/appointments`},
    {label:'Available resources',icon:schedulingIcons.resources,to:`${base}/service-scheduling?view=availability`},
    {label:'Service types',icon:schedulingIcons.services,to:'/srm/inventory/products?kind=service'},
    {label:'Employees',icon:schedulingIcons.employees,to:'/employees'},
    {label:'Setup guide',icon:schedulingIcons.guide,to:`${base}/service-scheduling?view=guide`},
  ]} actions={<Button asChild><Link to="/srm/pos/terminal">POS</Link></Button>}>{content}</SchedulingFrame>;
}

function Services({ scope, packContextId, onSlot }: { scope: string; packContextId?: number; onSlot?: (slot: BookingSlot) => void }) {
  const mobile=useMobile();
  const [params] = useSearchParams();
  const focusId=Number(params.get('focus_booking')) || undefined;
  const requestedDate=params.get('date') || '';
  const requestedZone=params.get('timezone') || '';
  const [focusMessage,setFocusMessage]=useState('');
  const focusGeneration=useRef('');
  const [zone, setZone] = useState(() => {
    const configured = defaultText('timezone', 'hrms');
    return validZone(configured) ? configured : Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  });
  const [from, setFrom] = useState(() => `${wall(Date.now(), zone).slice(0, 10)}T00:00`);
  const [until, setUntil] = useState(() => `${shiftDay(wall(Date.now(), zone).slice(0, 10), 1)}T00:00`);
  const [employee, setEmployee] = useState<{ id: string; name: string }>({ id: /^[1-9][0-9]*$/.test(params.get('employee_id') || '') ? params.get('employee_id')! : '', name: 'Selected employee' });
  const [service, setService] = useState<{ id: string; name: string }>({ id: '', name: '' });
  const [status, setStatus] = useState('');
  const [mode, setMode] = useState<Mode>(params.get('mode') === 'Gantt' ? 'Gantt' : params.get('mode') === 'Calendar' ? 'Calendar' : params.get('mode') === 'List' ? 'List' : window.matchMedia('(max-width: 760px)').matches ? 'List' : 'Gantt');
  const [filtersOpen,setFiltersOpen] = useState(false);
  const [range, setRange] = useState<1 | 7>(1);
  const [search, setSearch] = useState('');
  const [groupBy, setGroupBy] = useState<'employees' | 'resources'>('employees');
  const [day, setDay] = useState(from.slice(0, 10));
  const [zoom, setZoom] = useState('2.4');
  const [selected, setSelected] = useState<Booking | null>(null);
  const [readGeneration] = useState(() => crypto.randomUUID());
  const starts = useMemo(() => instants(from, zone), [from, zone]);
  const ends = useMemo(() => instants(until, zone), [until, zone]);
  const start = starts[0], end = ends[0];
  const valid = starts.length === 1 && ends.length === 1 && end > start && end - start <= 93 * DAY;
  const query = useInfiniteQuery({
    queryKey: ['scheduled-services', scope, readGeneration, packContextId, start, end, employee.id, service.id, status],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) => api.get<Projection>('/employees/planned-services', { signal, recordCache: false, params: {
      from_at: new Date(start).toISOString(), until_at: new Date(end).toISOString(),
      employee_id: employee.id || undefined, service_id: service.id || undefined, statuses: status || undefined,
      pack_context_id: packContextId, limit: 100, cursor: pageParam,
    } }).then(result => result.data),
    getNextPageParam: page => page.next_cursor || undefined, enabled: valid, retry: false, gcTime: 0,
  });
  const items = useMemo(() => query.isError ? [] : [...new Map((query.data?.pages.flatMap(page => page.items) || []).map(item => [`${item.appointment_id}:${item.employee_id}`, item])).values()], [query.data, query.isError]);
  const visibleItems = items.filter(item => `${item.employee_name} ${item.service_name} ${item.resources?.map(r => r.name).join(' ')}`.toLowerCase().includes(search.toLowerCase()));
  function navigateDate(next: string, days: 1 | 7 = range) { setFrom(`${next}T00:00`); setUntil(`${shiftDay(next, days)}T00:00`); setDay(next); }
  useEffect(()=>{if(!focusId || !/^\d{4}-\d{2}-\d{2}$/.test(requestedDate) || !Number.isFinite(Date.parse(`${requestedDate}T12:00Z`)))return;const key=`${focusId}:${requestedDate}:${requestedZone}`;if(focusGeneration.current===key)return;focusGeneration.current=key;if(validZone(requestedZone))setZone(requestedZone);setEmployee({id:'',name:''});setService({id:'',name:''});setStatus('');setSearch('');setMode('Gantt');setFrom(`${requestedDate}T00:00`);setUntil(`${shiftDay(requestedDate,1)}T00:00`);setDay(requestedDate);setFocusMessage(`Locating booking #${focusId}…`);},[focusId,requestedDate,requestedZone]);
  useEffect(()=>{if(!focusId || query.isFetching)return;if(query.isError || query.isFetchNextPageError){setFocusMessage(`Booking #${focusId} could not be located because the schedule failed to load. Retry the schedule to continue.`);return;}const found=items.find(item=>item.appointment_id===focusId);if(found){setFocusMessage(`Booking #${focusId} highlighted in the schedule.`);requestAnimationFrame(()=>{const element=document.querySelector<HTMLElement>(`[data-appointment-id="${focusId}"]`);element?.setAttribute('data-highlighted','true');element?.focus();element?.scrollIntoView({block:'nearest',inline:'center',behavior:'auto'});});}else if(query.hasNextPage && (query.data?.pages.length || 0)<10)void query.fetchNextPage();else setFocusMessage(`Booking #${focusId} is not available in the loaded permitted schedule.${query.hasNextPage?' Load more bookings to continue.':''}`);},[focusId,items,query.isFetching,query.hasNextPage,query.data?.pages.length,query.isError,query.isFetchNextPageError]);
  const options = !query.isError ? query.data?.pages[0]?.filter_options : undefined;
  useEffect(() => { setSelected(null); }, [start, end, employee.id, service.id, status, query.isError]);
  const employees = options?.employees || [], services = options?.services || [];
  const zones = [...new Set([zone, query.data?.pages[0]?.timezone, Intl.DateTimeFormat().resolvedOptions().timeZone, 'UTC'].filter((value): value is string => !!value && validZone(value)))];
  function changeZone(next: string) {
    if (starts.length === 1) setFrom(wall(start, next));
    if (ends.length === 1) setUntil(wall(end, next));
    setDay(starts.length === 1 ? wall(start, next).slice(0, 10) : day); setZone(next);
  }
  const error = isAxiosError(query.error) && typeof query.error.response?.data?.detail === 'string' ? query.error.response.data.detail : 'Scheduled services could not load.';
  const filters=(<div className="bookings-filter-panel">
      <label className="space-y-1 text-sm">From<Input type="datetime-local" value={from} onChange={event => { setFrom(event.target.value); setDay(event.target.value.slice(0, 10)); }}/></label>
      <label className="space-y-1 text-sm">Until (exclusive)<Input type="datetime-local" value={until} onChange={event => setUntil(event.target.value)}/></label>
      <label className="space-y-1 text-sm">Time zone<NativeSelect aria-label="Time zone" className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={zone} onChange={event => changeZone(event.target.value)}>{zones.map(value => <option key={value}>{value}</option>)}</NativeSelect></label>
      <label className="space-y-1 text-sm">Employee<NativeSelect aria-label="Employee" className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={employee.id} onChange={event => setEmployee({ id: event.target.value, name: event.target.selectedOptions[0].text })}><option value="">All authorized employees with bookings</option>{!query.isError && employee.id && !employees.some(item => String(item.id) === employee.id) && <option value={employee.id}>{employee.name}</option>}{employees.map(item => <option key={item.id} value={item.id}>{item.name}{item.code ? ` (${item.code})` : ''}</option>)}</NativeSelect></label>
      <label className="space-y-1 text-sm">Service<NativeSelect aria-label="Service" className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={service.id} onChange={event => setService({ id: event.target.value, name: event.target.selectedOptions[0].text })}><option value="">All services</option>{!query.isError && service.id && !services.some(item => String(item.id) === service.id) && <option value={service.id}>{service.name}</option>}{services.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</NativeSelect></label>
      <label className="space-y-1 text-sm">Status<NativeSelect aria-label="Status" className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={status} onChange={event => setStatus(event.target.value)}><option value="">All statuses</option>{['booked', 'checked_in', 'in_service', 'completed', 'cancelled', 'no_show'].map(value => <option key={value} value={value}>{value.replace(/_/g, ' ')}</option>)}</NativeSelect></label>
    </div>);
  const details=(<Dialog open={valid && !query.isError && !!selected} onOpenChange={open => { if (!open) setSelected(null); }}><DialogContent className="bookings-details-sheet mobile-workflow-dialog"><DialogTitle>Scheduled service</DialogTitle><DialogDescription>Planned booking details; this does not record actual worked time.</DialogDescription><MobileWorkflowPages>{selected && <dl className="grid grid-cols-2 gap-3 text-sm">{[['Employee', selected.employee_name], ['Categories', selected.employee_categories?.join(', ') || 'Unassigned'], ['Room / equipment', selected.resources?.map(resource=>`${resource.name} (${resource.resource_type})`).join(', ') || 'No room/equipment assigned'], ['Service', selected.service_name], ['From', label(selected.starts_at, zone)], ['To', label(selected.ends_at, zone)], ['Planned minutes', selected.planned_minutes], ['Status', selected.status.replace(/_/g, ' ')], ['Blocks availability', selected.blocks_availability ? 'Yes' : 'No']].map(([key, value]) => <div key={key}><dt className="text-muted-foreground">{key}</dt><dd>{value}</dd></div>)}</dl>}{selected && <Button asChild variant="outline"><Link to={`/employees/${selected.employee_id}?tab=schedule`}>Open employee schedule</Link></Button>}</MobileWorkflowPages></DialogContent></Dialog>);
  if(mobile)return <><MobileScheduleAgenda items={items} zone={zone} day={day} onDay={setDay} onSelect={setSelected} filters={filters} loading={query.isFetching} error={query.isError?error:undefined} onRefresh={()=>void query.refetch()} hasMore={query.hasNextPage} onMore={()=>void query.fetchNextPage()}/>{details}</>;
  return <section className="bookings-schedule">{focusId && <p role="status" className="prebooking-schedule-focus">{focusMessage}</p>}
    <div className="scheduler-summary" aria-label="Planned engagement summary">
      <div><CalendarDays size={25}/><span>Bookings in selected range<strong>{query.isPending ? '…' : query.isError ? '—' : new Set(items.map(item => item.appointment_id)).size}{query.hasNextPage ? '+' : ''}</strong></span></div>
      <div><span>Employees engaged<strong>{query.isError ? '—' : new Set(items.filter(item => item.blocks_availability).map(item => item.employee_id)).size}{query.hasNextPage ? '+' : ''}</strong></span></div>
      <div><span>Planned employee hours<strong>{query.isError ? '—' : (items.filter(item => item.blocks_availability).reduce((sum, item) => sum + item.planned_minutes, 0) / 60).toFixed(1)}{query.hasNextPage ? '+' : ''}</strong></span></div>
      <p>{zone}<br/>{query.hasNextPage ? 'Loaded bookings · load more for full totals' : 'Selected range · planned service work'}</p>
    </div>
    <div className="scheduler-toolbar">
      <Button variant="outline" aria-label="Previous date" onClick={() => navigateDate(shiftDay(day, -range))}>←</Button>
      <Input aria-label="Selected date" type="date" value={day} onChange={e => navigateDate(e.target.value)}/>
      <Button variant="outline" aria-label="Next date" onClick={() => navigateDate(shiftDay(day, range))}>→</Button>
      <Button variant="outline" onClick={() => navigateDate(wall(Date.now(), zone).slice(0, 10))}>Today</Button>
      <div className="bookings-view-tabs">{([1, 7] as const).map(days => <Button key={days} aria-pressed={range === days} variant={range === days ? 'default' : 'ghost'} onClick={() => { setRange(days); navigateDate(day, days); }}>{days === 1 ? 'Day' : 'Week'}</Button>)}</div>
      <Button variant="outline" aria-expanded={filtersOpen} onClick={() => setFiltersOpen(value => !value)}><SlidersHorizontal size={14}/>Filters</Button>
      <Input aria-label="Search schedule" placeholder="Search employee, service or resource…" value={search} onChange={e => setSearch(e.target.value)}/>
      <Button variant="outline" disabled={query.isFetching || !valid} onClick={() => void query.refetch()}>Refresh</Button>
    </div>
    {filtersOpen&&filters}
    {!valid && <p role="alert" className="text-sm">Choose an unambiguous time range of up to 93 days. A skipped or repeated daylight-saving time cannot be used; choose another time or UTC.</p>}
    {options && (!options.employees_complete || !options.services_complete) && <p className="text-sm text-muted-foreground">Filter choices are limited to 200 matching employees or services. Narrow the date range to find more choices.</p>}
    <div className="bookings-view-toolbar"><div className="bookings-view-tabs" role="group" aria-label="Schedule view">{(['List', 'Calendar', 'Gantt'] as const).map(value => <Button key={value} variant={mode === value ? 'default' : 'outline'} aria-pressed={mode === value} onClick={() => setMode(value)}>{value === 'Gantt' ? 'Timeline' : value}</Button>)}</div><div className="bookings-view-tabs">{(['employees', 'resources'] as const).map(value => <Button key={value} variant={groupBy === value ? 'default' : 'ghost'} aria-pressed={groupBy === value} onClick={() => setGroupBy(value)}>{value === 'employees' ? 'Employees' : 'Resources'}</Button>)}</div><span className="bookings-count">{items.length} bookings loaded{query.hasNextPage ? ' · More results available; views show loaded bookings only.' : ''}</span></div>
    {query.isPending && valid && <p role="status">Loading scheduled services…</p>}
    {query.isError && <p role="alert">{error} <Button variant="outline" onClick={() => void query.refetch()}>Retry</Button></p>}
    {valid && !query.isPending && !query.isError && !items.length && mode !== 'Gantt' && <div className="bookings-empty"><CalendarDays size={35}/><strong>No bookings in this view</strong><p>No scheduled services match this range and your access.</p><Button asChild variant="outline"><Link to="/srm/pos/terminal">Book a service in POS</Link></Button></div>}
    {valid && (items.length > 0 || mode === 'Gantt') && (mode === 'List' ? <div className="bookings-list"><table><caption className="sr-only">Loaded planned services. Times in {zone}.</caption><thead className="bg-muted/50"><tr>{['Employee', 'Categories', 'Service', 'Room / equipment', 'From', 'To', 'Planned minutes', 'Status'].map(value => <th key={value} className="p-3">{value}</th>)}</tr></thead><tbody>{visibleItems.map(item => <tr tabIndex={-1} data-appointment-id={item.appointment_id} key={`${item.appointment_id}:${item.employee_id}`} className="border-t"><td className="p-3">{item.employee_name}<span className="block text-xs text-muted-foreground">{item.employee_code}</span></td><td className="p-3">{item.employee_categories?.join(", ") || "Unassigned"}</td><td className="p-3"><button className="text-left underline underline-offset-4" onClick={() => setSelected(item)}>{item.service_name}</button></td><td className="p-3">{item.resources?.map(resource=>resource.name).join(", ") || "No room/equipment assigned"}</td><td className="whitespace-nowrap p-3">{label(item.starts_at, zone)}</td><td className="whitespace-nowrap p-3">{label(item.ends_at, zone)}</td><td className="p-3">{item.planned_minutes}</td><td className="p-3"><span className="bookings-status" data-status={item.status}>{item.status.replace(/_/g, ' ')}</span></td></tr>)}</tbody></table></div> : mode === 'Calendar' ? <MinuteCalendar groupBy={groupBy} items={visibleItems} zone={zone} day={day} setDay={setDay} onSelect={setSelected}/> : <MinuteGantt onSlot={onSlot} employees={employees} groupBy={groupBy} items={visibleItems} zone={zone} start={range === 1 ? Math.min(instants(`${day}T09:00`, zone)[0] || start, ...visibleItems.map(item => Date.parse(item.starts_at))) : start} end={range === 1 ? Math.max(instants(`${day}T18:00`, zone)[0] || end, ...visibleItems.map(item => Date.parse(item.ends_at))) : end} zoom={zoom} setZoom={setZoom} onSelect={setSelected}/>)}
    {valid && !query.isError && <section className="scheduler-upcoming"><h3><CalendarDays size={17}/> Upcoming appointments <small>(next 3 in loaded range)</small></h3><div className="bookings-list"><table><thead><tr><th>Time</th><th>Service</th><th>Employee</th><th>Resource</th><th>Status</th></tr></thead><tbody>{visibleItems.filter(item => Date.parse(item.starts_at) >= Date.now() && ['booked', 'checked_in'].includes(item.status)).sort((a,b) => Date.parse(a.starts_at) - Date.parse(b.starts_at)).slice(0,3).map(item => <tr tabIndex={-1} data-appointment-id={item.appointment_id} key={`${item.appointment_id}:${item.employee_id}`}><td>{label(item.starts_at, zone)}</td><td><button onClick={() => setSelected(item)}>{item.service_name}</button></td><td>{item.employee_name}</td><td>{item.resources?.map(r => r.name).join(', ') || '—'}</td><td><span className="bookings-status" data-status={item.status}>{item.status.replace(/_/g,' ')}</span></td></tr>)}</tbody></table></div></section>}
    {valid && query.hasNextPage && <Button variant="outline" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? 'Loading…' : 'Load more bookings'}</Button>}
    {details}
  </section>;
}

function useBookingScroll(first: number, start: number, scale: number, axis: 'top' | 'left') {
  const viewport = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!viewport.current || !Number.isFinite(first) || !Number.isFinite(start)) return;
    const offset = Math.max(0, (first - start) / MINUTE * scale - (axis === 'top' ? 80 : 24));
    if (axis === 'top') viewport.current.scrollTop = offset;
    else viewport.current.scrollLeft = offset;
  }, [first, start, scale, axis]);
  return viewport;
}

function MinuteCalendar({ groupBy, items, zone, day, setDay, onSelect }: { groupBy: 'employees' | 'resources'; items: Booking[]; zone: string; day: string; setDay: (day: string) => void; onSelect: (item: Booking) => void }) {
  const bounds = useMemo(() => day ? [dayBoundary(day, zone), dayBoundary(shiftDay(day, 1), zone)] : [NaN, NaN], [day, zone]);
  const [start, end] = bounds, scale = 0.8;
  const visible = items.filter(item => Date.parse(item.starts_at) < end && Date.parse(item.ends_at) > start);
  const viewport = useBookingScroll(Math.min(...visible.map(item => Date.parse(item.starts_at))), start, scale, 'top');
  const groups = groupBy === 'employees' ? [...new Set(visible.map(item => item.employee_id))].map(id => ({ id, name: visible.find(item => item.employee_id === id)!.employee_name, ...lanes(visible.filter(item => item.employee_id === id)) })) : [...new Map(visible.flatMap(item => item.resources || []).map(r => [r.id, r])).values()].map(r => ({ id:r.id, name:r.name, ...lanes([...new Map(visible.filter(item => item.resources?.some(resource => resource.id === r.id)).map(item => [item.appointment_id,item])).values()]) }));
  const ticks = Number.isFinite(end - start) ? Array.from({ length: Math.ceil((end - start) / (60 * MINUTE)) }, (_, index) => start + index * 60 * MINUTE) : [];
  return <div className="min-w-0 space-y-3"><div className="bookings-calendar-tools"><Button variant="outline" onClick={() => setDay(shiftDay(day, -1))}>Previous day</Button><Input className="w-auto" aria-label="Calendar day" type="date" value={day} onChange={event => setDay(event.target.value)}/><Button variant="outline" onClick={() => setDay(shiftDay(day, 1))}>Next day</Button><span className="text-xs text-muted-foreground">{zone} · Use List for an accessible alternative.</span></div>{!ticks.length ? <p>Choose a valid calendar day.</p> : !visible.length ? <p className="text-sm">No loaded bookings on this day.</p> : <div className="bookings-calendar-grid max-h-[650px] max-w-full overflow-auto rounded-lg border" ref={viewport} tabIndex={0} aria-label="Minute calendar, scroll to explore"><div style={{ minWidth: 100 + groups.length * 220 }}><div className="sticky top-0 z-20 flex border-b bg-card"><div className="w-[100px] shrink-0 p-2 text-xs">Time</div>{groups.map(group => <div key={group.id} className="flex-1 p-2 text-sm font-medium">{group.name}</div>)}</div><div className="relative flex" style={{ height: (end - start) / MINUTE * scale }}><div className="sticky left-0 z-10 w-[100px] shrink-0 bg-card">{ticks.map(tick => <div key={tick} className="absolute text-xs text-muted-foreground" style={{ top: (tick - start) / MINUTE * scale }}>{label(tick, zone)}</div>)}</div>{groups.map(group => <div key={group.id} className="relative flex-1 border-l">{ticks.map(tick => <div key={tick} className="absolute w-full border-t" style={{ top: (tick - start) / MINUTE * scale }}/>) }{group.placed.map(({ item, lane }) => <button data-appointment-id={item.appointment_id} key={`${item.appointment_id}:${item.employee_id}`} onClick={() => onSelect(item)} aria-label={description(item, zone)} title={description(item, zone)} data-status={item.status} className="bookings-calendar-event absolute overflow-hidden rounded border border-primary/40 bg-primary/10 px-1 text-left text-xs text-primary focus-visible:z-20 focus-visible:outline focus-visible:outline-2" style={{ minHeight: 0, top: (Math.max(start, Date.parse(item.starts_at)) - start) / MINUTE * scale, height: Math.max(2, (Math.min(end, Date.parse(item.ends_at)) - Math.max(start, Date.parse(item.starts_at))) / MINUTE * scale), left: `${lane / group.count * 100}%`, width: `${100 / group.count}%` }}>{item.service_name}<span className="block">{label(item.starts_at, zone)} · {item.status.replace(/_/g, ' ')}</span></button>)}</div>)}</div></div></div>}</div>;
}

function MinuteGantt({ onSlot, employees, groupBy, items, zone, start, end, zoom, setZoom, onSelect }: { onSlot?: (slot: BookingSlot) => void; employees: {id:number;name:string}[]; groupBy: 'employees' | 'resources'; items: Booking[]; zone: string; start: number; end: number; zoom: string; setZoom: (value: string) => void; onSelect: (item: Booking) => void }) {
  const scale = Number(zoom), width = Math.max(760, (end - start) / MINUTE * scale);
  const effectiveScale = width / ((end - start) / MINUTE);
  const viewport = useBookingScroll(Math.min(...items.map(item => Date.parse(item.starts_at))), start, effectiveScale, 'left');
  const step = Math.max(30, Math.ceil(70 / effectiveScale / 30) * 30);
  const ticks = Array.from({ length: Math.ceil((end - start) / MINUTE / step) }, (_, index) => start + index * step * MINUTE);
  const groups = groupBy === 'employees' ? [...new Map([...employees, ...items.map(item => ({id:item.employee_id,name:item.employee_name}))].map(e => [e.id,e])).values()].map(person => ({ id:person.id, name:person.name, ...lanes(items.filter(item => item.employee_id === person.id)) })) : [...new Map(items.flatMap(item => item.resources || []).map(resource => [resource.id, resource])).values()].map(resource => ({ id: resource.id, name: resource.name, ...lanes([...new Map(items.filter(item => item.resources?.some(r => r.id === resource.id)).map(item => [item.appointment_id, item])).values()]) }));
  return <div className="min-w-0 space-y-3"><label className="flex items-center gap-2 text-sm">Timeline zoom<NativeSelect className="w-auto" value={zoom} onChange={event => setZoom(event.target.value)}><option value="0.2">Compact</option><option value="0.6">Standard</option><option value="1.2">Detailed</option><option value="2.4">Readable</option><option value="4.8">Close up</option></NativeSelect></label><p className="text-xs text-muted-foreground">Times in {zone}. Select an empty slot to prebook; final availability depends on the selected service.</p><div className="bookings-calendar-grid max-h-[650px] max-w-full overflow-auto rounded-lg border" ref={viewport} tabIndex={0} aria-label="Minute Gantt timeline, scroll to explore"><div style={{ width: width + 180 }}><div className="sticky top-0 z-20 flex h-14 border-b bg-card"><div className="sticky left-0 z-20 w-[180px] shrink-0 bg-card p-3 text-sm">Employee</div><div className="relative" style={{ width }}>{ticks.map(tick => <div key={tick} className="absolute w-36 p-1 text-xs text-muted-foreground" style={{ left: (tick - start) / MINUTE * effectiveScale }}>{new Intl.DateTimeFormat(undefined, {timeZone:zone, ...(end-start > DAY ? {month:'short',day:'numeric'} as const : {}),hour:'numeric',minute:'2-digit'}).format(new Date(tick))}</div>)}</div></div>{groups.map(group => <div key={group.id} className="flex border-b" style={{ height: group.count * 62 + 8 }}><div className="sticky left-0 z-10 w-[180px] shrink-0 border-r bg-card p-3 text-sm"><span className="scheduler-avatar" aria-hidden="true">{group.name.split(' ').map(part => part[0]).slice(0,2).join('')}</span>{group.name}</div><div className="relative" style={{ width }}>{onSlot && Array.from({length: Math.ceil((end-start)/(30*MINUTE))},(_,index) => start+index*30*MINUTE).filter(at => at >= Date.now() && !group.placed.some(({item}) => item.blocks_availability && Date.parse(item.starts_at) < at+30*MINUTE && Date.parse(item.ends_at) > at)).map(at => <button type="button" key={`slot-${at}`} className="scheduler-empty-slot" aria-label={`Prebook ${group.name} at ${label(at,zone)}`} title="Start a prebooking here; service duration and availability are checked in the panel" style={{left:(at-start)/MINUTE*effectiveScale,width:Math.min(30,(end-at)/MINUTE)*effectiveScale}} onClick={() => onSlot({startsAt:new Date(at).toISOString(),...(groupBy === 'employees' ? {employeeId:group.id} : {resourceId:group.id}),key:crypto.randomUUID()})}/>)}{Date.now() >= start && Date.now() < end && end-start <= DAY && <div className="scheduler-now" aria-label="Current time" style={{left:(Date.now()-start)/MINUTE*effectiveScale}}/>}{ticks.map(tick => <div key={tick} className="absolute h-full border-l" style={{ left: (tick - start) / MINUTE * effectiveScale }}/>) }{group.placed.map(({ item, lane }) => <button data-appointment-id={item.appointment_id} key={`${item.appointment_id}:${item.employee_id}`} onClick={() => onSelect(item)} aria-label={description(item, zone)} title={description(item, zone)} data-status={item.status} className="bookings-calendar-event absolute h-14 overflow-hidden rounded border border-primary/40 bg-primary/10 px-1 text-left text-xs text-primary focus-visible:z-20 focus-visible:outline focus-visible:outline-2" style={{ minHeight: 0, top: lane * 62 + 4, left: (Math.max(start, Date.parse(item.starts_at)) - start) / MINUTE * effectiveScale, width: Math.max(2, (Math.min(end, Date.parse(item.ends_at)) - Math.max(start, Date.parse(item.starts_at))) / MINUTE * effectiveScale) }}>{item.service_name}<span className="block">{new Intl.DateTimeFormat(undefined,{timeZone:zone,hour:'numeric',minute:'2-digit'}).format(new Date(item.starts_at))} – {new Intl.DateTimeFormat(undefined,{timeZone:zone,hour:'numeric',minute:'2-digit'}).format(new Date(item.ends_at))}</span><span className="block">{item.status.replace(/_/g, ' ')}</span></button>)}</div></div>)}</div></div></div>;
}
