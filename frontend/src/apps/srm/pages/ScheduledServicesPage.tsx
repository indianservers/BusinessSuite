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
function description(item: Booking, zone: string) { return `${item.employee_name}: ${item.service_name}, ${label(item.starts_at, zone)} to ${label(item.ends_at, zone)}, ${item.status}`; }
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

export default function ScheduledServicesPage({ packContextId }: { packContextId?: number }) {
  const scope = useRecordScope();
  return <Services key={`${scope}:${packContextId || ''}`} scope={scope} packContextId={packContextId}/>;
}

function Services({ scope, packContextId }: { scope: string; packContextId?: number }) {
  const [zone, setZone] = useState(() => {
    const configured = defaultText('timezone', 'hrms');
    return validZone(configured) ? configured : Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  });
  const [from, setFrom] = useState(() => `${wall(Date.now(), zone).slice(0, 10)}T00:00`);
  const [until, setUntil] = useState(() => `${shiftDay(wall(Date.now(), zone).slice(0, 10), 7)}T00:00`);
  const [employee, setEmployee] = useState<{ id: string; name: string }>({ id: '', name: '' });
  const [service, setService] = useState<{ id: string; name: string }>({ id: '', name: '' });
  const [status, setStatus] = useState('');
  const [mode, setMode] = useState<Mode>('List');
  const [day, setDay] = useState(from.slice(0, 10));
  const [zoom, setZoom] = useState('0.6');
  const [selected, setSelected] = useState<Booking | null>(null);
  const starts = useMemo(() => instants(from, zone), [from, zone]);
  const ends = useMemo(() => instants(until, zone), [until, zone]);
  const start = starts[0], end = ends[0];
  const valid = starts.length === 1 && ends.length === 1 && end > start && end - start <= 93 * DAY;
  const query = useInfiniteQuery({
    queryKey: ['scheduled-services', scope, packContextId, start, end, employee.id, service.id, status],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) => api.get<Projection>('/employees/planned-services', { signal, params: {
      from_at: new Date(start).toISOString(), until_at: new Date(end).toISOString(),
      employee_id: employee.id || undefined, service_id: service.id || undefined, statuses: status || undefined,
      pack_context_id: packContextId, limit: 100, cursor: pageParam,
    } }).then(result => result.data),
    getNextPageParam: page => page.next_cursor || undefined, enabled: valid, retry: false,
  });
  const items = useMemo(() => [...new Map((query.data?.pages.flatMap(page => page.items) || []).map(item => [`${item.appointment_id}:${item.employee_id}`, item])).values()], [query.data]);
  const options = query.data?.pages[0]?.filter_options;
  const employees = options?.employees || [], services = options?.services || [];
  const zones = [...new Set([zone, query.data?.pages[0]?.timezone, Intl.DateTimeFormat().resolvedOptions().timeZone, 'UTC'].filter((value): value is string => !!value && validZone(value)))];
  function changeZone(next: string) {
    if (starts.length === 1) setFrom(wall(start, next));
    if (ends.length === 1) setUntil(wall(end, next));
    setDay(starts.length === 1 ? wall(start, next).slice(0, 10) : day); setZone(next);
  }
  const error = isAxiosError(query.error) && typeof query.error.response?.data?.detail === 'string' ? query.error.response.data.detail : 'Scheduled services could not load.';
  return <div className="min-w-0 space-y-4 p-4">
    <div><h1 className="text-2xl font-semibold">Scheduled Services</h1><p className="text-sm text-muted-foreground">Booked service plans for employees you may view. Actual worked hours remain in Timesheets.</p></div>
    <div className="grid gap-3 rounded-lg border bg-card p-4 sm:grid-cols-2 lg:grid-cols-3">
      <label className="space-y-1 text-sm">From<Input type="datetime-local" value={from} onChange={event => { setFrom(event.target.value); setDay(event.target.value.slice(0, 10)); }}/></label>
      <label className="space-y-1 text-sm">Until (exclusive)<Input type="datetime-local" value={until} onChange={event => setUntil(event.target.value)}/></label>
      <label className="space-y-1 text-sm">Time zone<NativeSelect aria-label="Time zone" className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={zone} onChange={event => changeZone(event.target.value)}>{zones.map(value => <option key={value}>{value}</option>)}</NativeSelect></label>
      <label className="space-y-1 text-sm">Employee<NativeSelect aria-label="Employee" className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={employee.id} onChange={event => setEmployee({ id: event.target.value, name: event.target.selectedOptions[0].text })}><option value="">All authorized employees with bookings</option>{employee.id && !employees.some(item => String(item.id) === employee.id) && <option value={employee.id}>{employee.name}</option>}{employees.map(item => <option key={item.id} value={item.id}>{item.name}{item.code ? ` (${item.code})` : ''}</option>)}</NativeSelect></label>
      <label className="space-y-1 text-sm">Service<NativeSelect aria-label="Service" className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={service.id} onChange={event => setService({ id: event.target.value, name: event.target.selectedOptions[0].text })}><option value="">All services</option>{service.id && !services.some(item => String(item.id) === service.id) && <option value={service.id}>{service.name}</option>}{services.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</NativeSelect></label>
      <label className="space-y-1 text-sm">Status<NativeSelect aria-label="Status" className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={status} onChange={event => setStatus(event.target.value)}><option value="">All statuses</option>{['booked', 'checked_in', 'in_service', 'completed', 'cancelled', 'no_show'].map(value => <option key={value} value={value}>{value.replace(/_/g, ' ')}</option>)}</NativeSelect></label>
    </div>
    {!valid && <p role="alert" className="text-sm">Choose an unambiguous time range of up to 93 days. A skipped or repeated daylight-saving time cannot be used; choose another time or UTC.</p>}
    {options && (!options.employees_complete || !options.services_complete) && <p className="text-sm text-muted-foreground">Filter choices are limited to 200 matching employees or services. Narrow the date range to find more choices.</p>}
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Schedule view">{(['List', 'Calendar', 'Gantt'] as const).map(value => <Button key={value} variant={mode === value ? 'default' : 'outline'} aria-pressed={mode === value} onClick={() => setMode(value)}>{value}</Button>)}<span className="text-sm text-muted-foreground">{items.length} bookings loaded{query.hasNextPage ? ' · More results available; views show loaded bookings only.' : ''}</span></div>
    {query.isPending && valid && <p role="status">Loading scheduled services…</p>}
    {query.isError && <p role="alert">{error} <Button variant="outline" onClick={() => void query.refetch()}>Retry</Button></p>}
    {valid && !query.isPending && !query.isError && !items.length && <p className="rounded-lg border p-6 text-sm">No scheduled services match this range and your access.</p>}
    {valid && items.length > 0 && (mode === 'List' ? <div className="max-w-full overflow-auto rounded-lg border"><table className="w-full text-left text-sm"><caption className="sr-only">Loaded planned services. Times in {zone}.</caption><thead className="bg-muted/50"><tr>{['Employee', 'Service', 'Start', 'End', 'Planned minutes', 'Status'].map(value => <th key={value} className="p-3">{value}</th>)}</tr></thead><tbody>{items.map(item => <tr key={`${item.appointment_id}:${item.employee_id}`} className="border-t"><td className="p-3">{item.employee_name}<span className="block text-xs text-muted-foreground">{item.employee_code}</span></td><td className="p-3"><button className="text-left underline underline-offset-4" onClick={() => setSelected(item)}>{item.service_name}</button></td><td className="whitespace-nowrap p-3">{label(item.starts_at, zone)}</td><td className="whitespace-nowrap p-3">{label(item.ends_at, zone)}</td><td className="p-3">{item.planned_minutes}</td><td className="p-3">{item.status.replace(/_/g, ' ')}</td></tr>)}</tbody></table></div> : mode === 'Calendar' ? <MinuteCalendar items={items} zone={zone} day={day} setDay={setDay} onSelect={setSelected}/> : <MinuteGantt items={items} zone={zone} start={start} end={end} zoom={zoom} setZoom={setZoom} onSelect={setSelected}/>)}
    {valid && query.hasNextPage && <Button variant="outline" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? 'Loading…' : 'Load more bookings'}</Button>}
    <Dialog open={!!selected} onOpenChange={open => { if (!open) setSelected(null); }}><DialogContent><DialogTitle>Scheduled service</DialogTitle><DialogDescription>Planned booking details; this does not record actual worked time.</DialogDescription>{selected && <dl className="grid grid-cols-2 gap-3 text-sm">{[['Employee', selected.employee_name], ['Service', selected.service_name], ['Start', label(selected.starts_at, zone)], ['End', label(selected.ends_at, zone)], ['Planned minutes', selected.planned_minutes], ['Status', selected.status.replace(/_/g, ' ')], ['Blocks availability', selected.blocks_availability ? 'Yes' : 'No']].map(([key, value]) => <div key={key}><dt className="text-muted-foreground">{key}</dt><dd>{value}</dd></div>)}</dl>}</DialogContent></Dialog>
  </div>;
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

function MinuteCalendar({ items, zone, day, setDay, onSelect }: { items: Booking[]; zone: string; day: string; setDay: (day: string) => void; onSelect: (item: Booking) => void }) {
  const bounds = useMemo(() => day ? [dayBoundary(day, zone), dayBoundary(shiftDay(day, 1), zone)] : [NaN, NaN], [day, zone]);
  const [start, end] = bounds, scale = 0.8;
  const visible = items.filter(item => Date.parse(item.starts_at) < end && Date.parse(item.ends_at) > start);
  const viewport = useBookingScroll(Math.min(...visible.map(item => Date.parse(item.starts_at))), start, scale, 'top');
  const groups = [...new Set(visible.map(item => item.employee_id))].map(id => ({ id, name: visible.find(item => item.employee_id === id)!.employee_name, ...lanes(visible.filter(item => item.employee_id === id)) }));
  const ticks = Number.isFinite(end - start) ? Array.from({ length: Math.ceil((end - start) / (60 * MINUTE)) }, (_, index) => start + index * 60 * MINUTE) : [];
  return <div className="min-w-0 space-y-3"><div className="flex flex-wrap items-center gap-2"><Button variant="outline" onClick={() => setDay(shiftDay(day, -1))}>Previous day</Button><Input className="w-auto" aria-label="Calendar day" type="date" value={day} onChange={event => setDay(event.target.value)}/><Button variant="outline" onClick={() => setDay(shiftDay(day, 1))}>Next day</Button><span className="text-xs text-muted-foreground">{zone} · Use List for an accessible alternative.</span></div>{!ticks.length ? <p>Choose a valid calendar day.</p> : !visible.length ? <p className="text-sm">No loaded bookings on this day.</p> : <div className="max-h-[650px] max-w-full overflow-auto rounded-lg border" ref={viewport} tabIndex={0} aria-label="Minute calendar, scroll to explore"><div style={{ minWidth: 100 + groups.length * 220 }}><div className="sticky top-0 z-20 flex border-b bg-card"><div className="w-[100px] shrink-0 p-2 text-xs">Time</div>{groups.map(group => <div key={group.id} className="flex-1 p-2 text-sm font-medium">{group.name}</div>)}</div><div className="relative flex" style={{ height: (end - start) / MINUTE * scale }}><div className="sticky left-0 z-10 w-[100px] shrink-0 bg-card">{ticks.map(tick => <div key={tick} className="absolute text-xs text-muted-foreground" style={{ top: (tick - start) / MINUTE * scale }}>{label(tick, zone)}</div>)}</div>{groups.map(group => <div key={group.id} className="relative flex-1 border-l">{ticks.map(tick => <div key={tick} className="absolute w-full border-t" style={{ top: (tick - start) / MINUTE * scale }}/>) }{group.placed.map(({ item, lane }) => <button key={`${item.appointment_id}:${item.employee_id}`} onClick={() => onSelect(item)} aria-label={description(item, zone)} title={description(item, zone)} className="absolute overflow-hidden rounded border border-primary/40 bg-primary/10 px-1 text-left text-xs text-primary focus-visible:z-20 focus-visible:outline focus-visible:outline-2" style={{ minHeight: 0, top: (Math.max(start, Date.parse(item.starts_at)) - start) / MINUTE * scale, height: Math.max(2, (Math.min(end, Date.parse(item.ends_at)) - Math.max(start, Date.parse(item.starts_at))) / MINUTE * scale), left: `${lane / group.count * 100}%`, width: `${100 / group.count}%` }}>{item.service_name}<span className="block">{label(item.starts_at, zone)} · {item.status.replace(/_/g, ' ')}</span></button>)}</div>)}</div></div></div>}</div>;
}

function MinuteGantt({ items, zone, start, end, zoom, setZoom, onSelect }: { items: Booking[]; zone: string; start: number; end: number; zoom: string; setZoom: (value: string) => void; onSelect: (item: Booking) => void }) {
  const scale = Number(zoom), width = Math.max(600, (end - start) / MINUTE * scale);
  const effectiveScale = width / ((end - start) / MINUTE);
  const viewport = useBookingScroll(Math.min(...items.map(item => Date.parse(item.starts_at))), start, effectiveScale, 'left');
  const step = Math.max(30, Math.ceil(150 / effectiveScale / 30) * 30);
  const ticks = Array.from({ length: Math.ceil((end - start) / MINUTE / step) }, (_, index) => start + index * step * MINUTE);
  const groups = [...new Set(items.map(item => item.employee_id))].map(id => ({ id, name: items.find(item => item.employee_id === id)!.employee_name, ...lanes(items.filter(item => item.employee_id === id)) }));
  return <div className="min-w-0 space-y-3"><label className="flex items-center gap-2 text-sm">Timeline zoom<NativeSelect className="w-auto" value={zoom} onChange={event => setZoom(event.target.value)}><option value="0.2">Compact</option><option value="0.6">Standard</option><option value="1.2">Detailed</option></NativeSelect></label><p className="text-xs text-muted-foreground">Positions and lengths use elapsed minutes; labels use {zone}. Use List for an accessible alternative.</p><div className="max-h-[650px] max-w-full overflow-auto rounded-lg border" ref={viewport} tabIndex={0} aria-label="Minute Gantt timeline, scroll to explore"><div style={{ width: width + 180 }}><div className="sticky top-0 z-20 flex h-14 border-b bg-card"><div className="sticky left-0 z-20 w-[180px] shrink-0 bg-card p-3 text-sm">Employee</div><div className="relative" style={{ width }}>{ticks.map(tick => <div key={tick} className="absolute w-36 p-1 text-xs text-muted-foreground" style={{ left: (tick - start) / MINUTE * effectiveScale }}>{label(tick, zone)}</div>)}</div></div>{groups.map(group => <div key={group.id} className="flex border-b" style={{ height: group.count * 42 + 8 }}><div className="sticky left-0 z-10 w-[180px] shrink-0 border-r bg-card p-3 text-sm">{group.name}</div><div className="relative" style={{ width }}>{ticks.map(tick => <div key={tick} className="absolute h-full border-l" style={{ left: (tick - start) / MINUTE * effectiveScale }}/>) }{group.placed.map(({ item, lane }) => <button key={`${item.appointment_id}:${item.employee_id}`} onClick={() => onSelect(item)} aria-label={description(item, zone)} title={description(item, zone)} className="absolute h-9 overflow-hidden rounded border border-primary/40 bg-primary/10 px-1 text-left text-xs text-primary focus-visible:z-20 focus-visible:outline focus-visible:outline-2" style={{ minHeight: 0, top: lane * 42 + 4, left: (Math.max(start, Date.parse(item.starts_at)) - start) / MINUTE * effectiveScale, width: Math.max(2, (Math.min(end, Date.parse(item.ends_at)) - Math.max(start, Date.parse(item.starts_at))) / MINUTE * effectiveScale) }}>{item.service_name}<span className="block">{item.status.replace(/_/g, ' ')}</span></button>)}</div></div>)}</div></div></div>;
}

