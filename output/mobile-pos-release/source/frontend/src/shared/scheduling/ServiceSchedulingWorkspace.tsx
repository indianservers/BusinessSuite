import { Info } from 'lucide-react';
import SchedulingFrame, { schedulingIcons } from './SchedulingFrame';
import { useDeferredValue, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { useRecordScope } from '@/lib/record-scope';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import EmployeeCategories from '@/shared/EmployeeCategories';
import { catalogApi } from '@/shared/catalog/api';
import { dealError } from '@/apps/crm/deals/deal-utils';
import ScheduledServicesPage from '@/apps/srm/pages/ScheduledServicesPage';
import { candidates, wall } from './booking-time';

type Employee = { eligibility_id: number; employee_id: number; employee_name: string; timezone: string; work_categories?: string[] };
type Resource = { id: number; name: string; resource_type: string; timezone?: string; opens?: string; closes?: string; weekdays?: number[] };
type Options = { policy: { active: boolean; default_duration_minutes: number; employee_categories?: string[] } | null; specialists: Employee[]; has_more: boolean; resources: Resource[] };
type Availability = { timezone: string; checked_at: string; slots: { starts_at: string; label: string }[]; selection_available: boolean | null; resources: { id: number; available: boolean }[] };
const selectClass = 'h-10 w-full min-w-0 rounded-md border bg-background px-3 text-sm';

export default function ServiceSchedulingWorkspace() {
  const scope = useRecordScope();
  return <Workspace key={scope} scope={scope}/>;
}

function Workspace({ scope }: { scope: string }) {
  const location = useLocation();
  const initial = new URLSearchParams(location.search).get('view');
  const [view, setView] = useState(initial === 'schedule' || initial === 'availability' ? initial : 'guide');
  const module = location.pathname.startsWith('/hrms') ? 'hrms' : location.pathname.startsWith('/crm') ? 'crm' : 'srm';
  const appointments = `/${module === 'crm' ? 'crm' : 'srm'}/appointments`;
  return <main className="min-w-0"><SchedulingFrame title="Service scheduling" subtitle="Connect employee categories, service stock and resource availability." nav={[
    {label:'Setup guide',icon:schedulingIcons.guide,active:view==='guide',onClick:()=>setView('guide')},
    {label:'Available resources',icon:schedulingIcons.resources,active:view==='availability',onClick:()=>setView('availability')},
    {label:'Schedule & Gantt',icon:schedulingIcons.calendar,active:view==='schedule',onClick:()=>setView('schedule')},
    {label:'Service types',icon:schedulingIcons.services,to:'/srm/inventory/products?kind=service'},
    {label:'Employees',icon:schedulingIcons.employees,to:'/employees'},
    {label:'Appointments',icon:schedulingIcons.timeline,to:appointments},
  ]} actions={<><Button asChild variant="outline"><Link to={`${appointments}?resources=1`}>Manage resources</Link></Button><Button asChild><Link to="/srm/pos/terminal">New POS booking</Link></Button></>}>
    {view === 'guide' && <section className="space-y-4" aria-label="Service booking setup guide">
      <p className="bookings-guide-note"><Info size={17}/><span>Select one branch in the top bar. Use the same branch and Business Pack context throughout setup and booking. Your permissions determine which employees and resources are visible.</span></p>
      <ol className="bookings-setup-grid">
        <Step number={1} title="Create and assign employee categories" to="/employees" action="Open HRMS employees">Open an employee → Job → Edit → Employee categories. Enter a category, click Add category, select one or more categories, then save the employee. Categories such as Stylist or Consultant become available for other employees and service rules after saving.</Step>
        <Step number={2} title="Add employees and rooms as resources" to={`/${module === 'crm' ? 'crm' : 'srm'}/appointments?resources=1`} action="Manage employees & rooms">Create an Employee/provider resource linked to the existing HRMS employee. Set timezone, opening and closing time, and working days. Create each Room, Chair or Equipment resource with its own working hours.</Step>
        <Step number={3} title="Configure the service stock" to="/srm/inventory/products?kind=service" action="Open service stock">Add a Service with name, code, rate and tax. Click Save and configure scheduling. Set default/minimum/maximum duration, optional or required booking, and multiple HRMS employee categories. Save the scheduling policy, then enable each eligible employee for this service.</Step>
        <Step number={4} title="Book from the POS cart" to="/srm/pos/terminal" action="Open POS">Open a register, select a registered customer and add the service. Enable appointment scheduling in the cart line, choose an eligible employee and room, and enter From and To date/time in the displayed timezone. Apply appointment details, then complete checkout. Add the service again for another employee or time.</Step>
      </ol>
      <div className="bookings-detail-note"><h2 className="font-semibold">Where to see the details</h2><p className="mt-2">HRMS Employees: use Table/Sheet for employee categories and open an employee’s Schedule tab for their service bookings. HRMS Timesheets → Planned services shows planned work separately from recorded actual hours. Schedule &amp; Gantt here provides List, Calendar and Gantt views; select a booking to see employee, categories, room/equipment, From, To and status. CRM/SRM Appointment Scheduler handles visit details and rescheduling.</p><div className="mt-3 flex flex-wrap gap-2"><Button variant="outline" onClick={() => setView('availability')}>Check available resources</Button><Button variant="outline" onClick={() => setView('schedule')}>View booked services</Button><Button asChild variant="outline"><Link to="/timesheets">Open HRMS timesheets</Link></Button></div></div>
      <p className="text-xs text-muted-foreground">Applying cart details prepares a booking. The appointment is created when checkout succeeds. Availability is checked again at checkout; planned bookings do not create attendance, payroll or actual timesheet hours.</p>
    </section>}
    {view === 'availability' && <ResourceAvailability scope={scope}/>}
    {view === 'schedule' && <ScheduledServicesPage embedded/>}
  </SchedulingFrame></main>;
}

function Step({ number, title, to, action, children }: { number: number; title: string; to: string; action: string; children: React.ReactNode }) {
  return <li className="bookings-step"><span className="bookings-step-number" aria-hidden="true">{number.toString().padStart(2,'0')}</span><h2>{number}. {title}</h2><p>{children}</p><Button asChild variant="outline"><Link to={to}>{action}</Link></Button></li>;
}

function ResourceAvailability({ scope }: { scope: string }) {
  const [search, setSearch] = useState(''), deferred = useDeferredValue(search), [page, setPage] = useState(1);
  const [service, setService] = useState(''), [employee, setEmployee] = useState(''), [categories, setCategories] = useState<string[]>([]);
  const [from, setFrom] = useState(''), [to, setTo] = useState(''), [resources, setResources] = useState<number[]>([]);
  const catalog = useQuery({ queryKey: ['availability-service-stock', scope, deferred, page], queryFn: ({ signal }) => api.get<Awaited<ReturnType<typeof catalogApi.list>>['data']>('/catalog/items', { signal, recordCache: false, params: { source: 'srm', kind: 'service', status: 'Active', search: deferred, page, per_page: 50 } }).then(r => r.data), retry: false });
  const options = useQuery({ queryKey: ['availability-service-options', scope, service], enabled: !!service, queryFn: ({ signal }) => api.get<Options>('/srm/service-checkout/options', { signal, recordCache: false, params: { service_id: service } }).then(r => r.data), retry: false });
  const specialist = options.data?.specialists.find(item => String(item.eligibility_id) === employee);
  const zone = specialist?.timezone;
  const starts = zone && from ? candidates(from, zone) : [], ends = zone && to ? candidates(to, zone) : [];
  const minutes = starts.length === 1 && ends.length === 1 ? (ends[0] - starts[0]) / 60000 : 0;
  const valid = !!specialist && !!options.data?.policy?.active && Number.isInteger(minutes) && minutes >= 5 && minutes <= 720;
  const availability = useQuery({ queryKey: ['service-resource-availability', scope, service, employee, from, to, resources.join(',')], enabled: valid,
    queryFn: ({ signal }) => { const params = new URLSearchParams({ service_id: service, eligibility_id: employee, day: from.slice(0, 10), duration_minutes: String(minutes), starts_at: new Date(starts[0]).toISOString() }); resources.forEach(id => params.append('resource_ids', String(id))); return api.get<Availability>('/srm/service-checkout/options/availability', { signal, params, recordCache: false }).then(r => r.data); }, retry: false, staleTime: 15000 });
  function chooseEmployee(value: string) {
    setEmployee(value); setResources([]);
    const item = options.data?.specialists.find(item => String(item.eligibility_id) === value);
    if (item) { const begin = Math.ceil((Date.now() + 3600000) / 900000) * 900000; setFrom(wall(begin, item.timezone)); setTo(wall(begin + (options.data?.policy?.default_duration_minutes || 30) * 60000, item.timezone)); }
    else { setFrom(''); setTo(''); }
  }
  return <section className="bookings-resource-check space-y-4" aria-label="Service resource availability">
    <p className="text-sm text-muted-foreground">Choose a service and employee to check rooms and equipment for an exact time range. This check does not reserve a booking.</p>
    <div className="grid gap-3 rounded-lg border bg-card p-4 sm:grid-cols-2">
      <label className="space-y-1 text-sm">Search service stock<Input value={search} onChange={e => { setSearch(e.target.value); setPage(1); setService(''); chooseEmployee(''); }}/></label>
      <label className="space-y-1 text-sm">Service<NativeSelect className={selectClass} aria-label="Availability service" value={service} loading={catalog.isFetching} onChange={e => { setService(e.target.value); chooseEmployee(''); setCategories([]); }}><option value="">Choose a service</option>{catalog.data?.items.filter(item => item.kind === 'service').map(item => <option key={item.id} value={item.id}>{item.name} · {item.code}</option>)}</NativeSelect></label>
      <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={page === 1} onClick={() => { setPage(page - 1); setService(''); chooseEmployee(''); }}>Previous services</Button><Button variant="outline" disabled={!catalog.data || page >= catalog.data.pages} onClick={() => { setPage(page + 1); setService(''); chooseEmployee(''); }}>More services</Button></div>
      {catalog.isError && <p role="alert">{dealError(catalog.error)} <Button variant="outline" onClick={() => void catalog.refetch()}>Retry services</Button></p>}
      {options.isError && <p role="alert">{dealError(options.error)} <Button variant="outline" onClick={() => void options.refetch()}>Retry options</Button></p>}
      {options.data && <><div className="sm:col-span-2"><EmployeeCategories options={[...new Set(options.data.specialists.flatMap(item => item.work_categories || []))]} value={categories} onChange={value => { setCategories(value); chooseEmployee(''); }}/></div>
        <label className="text-sm">Employee<NativeSelect aria-label="Availability employee" className={selectClass} value={employee} onChange={e => chooseEmployee(e.target.value)}><option value="">Choose eligible employee</option>{options.data.specialists.filter(item => !categories.length || item.work_categories?.some(category => categories.includes(category))).map(item => <option key={item.eligibility_id} value={item.eligibility_id}>{item.employee_name} · {item.work_categories?.join(', ')}</option>)}</NativeSelect></label>
        <p className="text-sm">{!options.data.policy?.active ? 'Configure an active service scheduling policy in service stock first.' : !options.data.specialists.length ? 'No eligible employees. Assign HRMS categories, create employee resources and enable them in the service scheduling policy.' : 'Only employees enabled for this service and its HRMS category rules appear here.'}{options.data.has_more && ' More than 100 employees match; use the POS employee search for additional choices.'}</p>
      </>}
      {specialist && <><label className="text-sm">From date &amp; time<Input aria-label="Availability from" type="datetime-local" value={from} onChange={e => setFrom(e.target.value)}/></label><label className="text-sm">To date &amp; time<Input aria-label="Availability to" type="datetime-local" value={to} onChange={e => setTo(e.target.value)}/></label><p className="text-sm sm:col-span-2">Timezone: {zone} · {minutes > 0 ? `${minutes} minutes` : 'Choose an end after the start.'}</p></>}
    </div>
    {specialist && !valid && <p role="alert">Enter an unambiguous From/To range between 5 minutes and 12 hours. The service’s duration rules also apply.</p>}
    {valid && <div className="flex flex-wrap items-center gap-3"><Button variant="outline" disabled={availability.isFetching} onClick={() => void availability.refetch()}>Refresh availability</Button>{availability.isFetching ? <p role="status">Checking employee and resources…</p> : availability.isError ? <p role="alert">{dealError(availability.error)}</p> : availability.data && <p role="status">{availability.data.selection_available ? 'Employee and selected resources are available.' : 'Employee or a selected resource is unavailable at this time.'}</p>}</div>}
    {options.data && <div className="space-y-3"><h2 className="font-semibold">Rooms, chairs &amp; equipment</h2><p className="text-xs text-muted-foreground">Availability below includes the chosen employee’s leave, other bookings and working hours. Select multiple resources to check them together. Displayed times are each resource’s local working hours.</p><div className="grid gap-3 md:grid-cols-2">{options.data.resources.map(resource => {
      const state = !availability.isFetching && !availability.isError && valid ? availability.data?.resources.find(item => item.id === resource.id) : undefined;
      return <label key={resource.id} className="bookings-resource-card flex min-w-0 items-start gap-3 rounded-lg border bg-card p-4"><input className="mt-1" type="checkbox" checked={resources.includes(resource.id)} disabled={!specialist || !resources.includes(resource.id) && resources.length >= 9} onChange={e => setResources(ids => e.target.checked ? [...ids, resource.id] : ids.filter(id => id !== resource.id))}/><span className="min-w-0 text-sm"><strong className="block break-words">{resource.name}</strong><span className="block">{resource.resource_type} · {resource.opens || '—'}–{resource.closes || '—'} · {resource.timezone || 'Timezone unavailable'}</span><span className="block">{resource.weekdays?.map(day => ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][day]).filter(Boolean).join(', ') || 'Working days not supplied'}</span><span className="block">{state ? state.available ? 'Available with this employee' : 'Unavailable with this employee' : 'Choose employee and time to check'}</span></span></label>;
    })}</div>{!options.data.resources.length && <p className="text-sm">No active room or equipment resources in this branch and context. Create them in Appointment Scheduler → Resources.</p>}<p className="text-xs text-muted-foreground">Up to 100 active resources are shown. Availability can change before checkout.</p></div>}
    {valid && availability.data && !availability.isError && !availability.isFetching && <div className="space-y-2"><h2 className="font-semibold">Available start times on {from.slice(0, 10)}</h2><div className="bookings-resource-slots flex flex-wrap gap-2">{availability.data.slots.map(slot => <Button variant="outline" key={slot.starts_at} onClick={() => { const begin = Date.parse(slot.starts_at); setFrom(wall(begin, zone!)); setTo(wall(begin + minutes * 60000, zone!)); }}>{slot.label}</Button>)}</div>{!availability.data.slots.length && <p className="text-sm">No available slots for this employee, duration and selected resources.</p>}<p className="text-xs text-muted-foreground">Checked {new Date(availability.data.checked_at).toLocaleString()}. To reserve, choose these details in the POS cart and complete checkout.</p></div>}
  </section>;
}
