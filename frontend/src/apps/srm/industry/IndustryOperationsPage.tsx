import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import { useAuthStore } from '@/store/authStore';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import CompanySelect, { masterScope } from '@/shared/master-data/CompanySelect';
import SmartRecordPicker from '@/shared/records/SmartRecordPicker';
import { catalogApi, catalogError } from '@/shared/catalog/api';
import { dealError } from '@/apps/crm/deals/deal-utils';
import { useMobileDraftGuard } from '@/components/mobile/useMobileDraftGuard';
import DealRecordSelect from '@/apps/crm/deals/DealRecordSelect';

type Row = { id: number; title: string; kind: string; status: string; revision: number; created_by: number; invoice_id?: number; data: Record<string, string | number | number[]> };
type Choice = { id: number; name: string };
type Form = Record<string, string>;
const ROOT = '/srm/industry';
const titles: Record<string, string> = { appointment: 'Appointments', resource: 'Salon resources', boq: 'BOQ', variation: 'Variations', measurement: 'Measurements', site_diary: 'Site diary', subcontract: 'Subcontracts', material_issue: 'Materials consumed' };
const paths: Record<string, string> = { appointment: '/appointments', resource: '/resources', boq: '/boq', variation: '/boq', measurement: '/measurements', site_diary: '/site-diaries', subcontract: '/subcontracts', material_issue: '/material-issues' };
const controls = 'w-full rounded-md border bg-background px-3 py-2 text-sm';
const empty = (): Form => ({ title: '', duration_minutes: '60', resource_type: 'stylist', opens: '09:00', closes: '19:00', weekdays: '0,1,2,3,4,5', timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata', quantity: '', unit_rate: '', unit: '', code: '', tax_rate: '0', retention_percent: '0', workforce: '0' });

function Field({ name, children }: { name: string; children: ReactNode }) {
  return <div className="grid gap-1 text-sm"><span>{name}</span>{children}</div>;
}

function ProjectPicker({ value, change }: { value: string; change: (value: string) => void }) {
  const [search, setSearch] = useState(''), [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Choice>();
  const q = useQuery({ queryKey: ['industry-projects', masterScope(), search, offset], queryFn: async () => (await api.get<{ items: Choice[]; has_more: boolean }>(ROOT + '/project-options', { params: { search, offset } })).data, retry: false });
  return <SmartRecordPicker name="Project" value={value} search={search} onSearch={s => { setSearch(s); setOffset(0); }} items={(q.data?.items || []).map(record => ({ id: String(record.id), label: record.name, record }))} selected={selected ? { id: String(selected.id), label: selected.name, record: selected } : undefined} onSelect={r => { setSelected(r); change(String(r.id)); }} onClear={() => { setSelected(undefined); change(''); }} loading={q.isFetching} error={q.isError ? dealError(q.error) : undefined} retry={() => void q.refetch()} hasMore={q.data?.has_more} loadMore={() => setOffset(s => s + 50)} />;
}

function ServicePicker({ value, change, kind = 'service' }: { value: string; change: (value: string) => void; kind?: 'service' | 'product' }) {
  const [search, setSearch] = useState(''), [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Choice>();
  const q = useQuery({ queryKey: ['industry-services', masterScope(), kind, search, page], queryFn: async () => (await catalogApi.list('srm', { kind, status: 'Active', search, page, per_page: 50 })).data, retry: false });
  return <SmartRecordPicker name={kind === 'service' ? 'Service' : 'Stock item'} value={value} search={search} onSearch={s => { setSearch(s); setPage(1); }} items={(q.data?.items || []).filter(r => r.kind === kind).map(record => ({ id: String(record.id), label: record.name, record }))} selected={selected ? { id: String(selected.id), label: selected.name, record: selected } : undefined} onSelect={r => { setSelected(r); change(String(r.id)); }} onClear={() => { setSelected(undefined); change(''); }} loading={q.isFetching} error={q.isError ? catalogError(q.error) : undefined} retry={() => void q.refetch()} hasMore={!!q.data && page < q.data.pages} loadMore={() => setPage(p => p + 1)} />;
}

function RescheduleForm({ row, resources, saved }: { row: Row; resources: Row[]; saved: (row: Row) => Promise<void> }) {
  const current = new Date(String(row.data.starts_at));
  const [starts, setStarts] = useState(new Date(current.getTime() - current.getTimezoneOffset() * 60000).toISOString().slice(0, 16));
  const [minutes, setMinutes] = useState(String(row.data.duration_minutes));
  const [selected, setSelected] = useState<number[]>(row.data.resource_ids as number[]);
  const mutation = useMutation({ mutationFn: async () => (await api.put<Row>(ROOT + `/appointments/${row.id}/schedule`, { expected_revision: row.revision, starts_at: new Date(starts).toISOString(), duration_minutes: Number(minutes), resource_ids: selected })).data, onSuccess: saved });
  return <details className="rounded-md border p-3"><summary className="cursor-pointer text-sm">Reschedule</summary><form className="mt-3 grid gap-3" aria-label="Reschedule appointment" onSubmit={e => { e.preventDefault(); mutation.mutate(); }}><Field name="New appointment time"><Input aria-label="New appointment time" type="datetime-local" required value={starts} onChange={e => setStarts(e.target.value)} /></Field><Field name="New duration (minutes)"><Input aria-label="New duration (minutes)" type="number" min={5} max={720} required value={minutes} onChange={e => setMinutes(e.target.value)} /></Field>{resources.map(r => <label key={r.id} className="flex gap-2 text-sm"><input type="checkbox" checked={selected.includes(r.id)} onChange={e => setSelected(s => e.target.checked ? [...s, r.id] : s.filter(id => id !== r.id))} />{r.title}</label>)}<Button type="submit" disabled={mutation.isPending}>Save new schedule</Button>{mutation.isError && <p role="alert">{dealError(mutation.error)}</p>}</form></details>;
}

export default function IndustryOperationsPage({ mode }: { mode: 'salon' | 'construction' }) {
  const user = useAuthStore(s => s.user);
  const scope = masterScope();
  return <IndustryWorkspace key={`${scope}:${mode}`} mode={mode} scope={scope} userId={user?.id} />;
}

function IndustryWorkspace({ mode, scope, userId }: { mode: 'salon' | 'construction'; scope: string; userId?: number }) {
  const cache = useQueryClient();
  const [kind, setKind] = useState(mode === 'salon' ? 'appointment' : 'boq');
  const [project, setProject] = useState(''), [form, setForm] = useState<Form>(empty), [resources, setResources] = useState<number[]>([]);
  const [creating, setCreating] = useState(false), [notice, setNotice] = useState(''), [offset, setOffset] = useState(0);
  const [files, setFiles] = useState<number[]>([]), [fileOffset, setFileOffset] = useState(0);
  const [day, setDay] = useState('');
  const requestId = useRef(crypto.randomUUID());
  const update = (key: string, value: string) => setForm(f => ({ ...f, [key]: value }));
  const caps = useQuery({ queryKey: ['industry', scope, 'capabilities', project], retry: false, queryFn: async () => (await api.get<{ manage: boolean; approve: boolean; invoice: boolean; self_approve: boolean }>(ROOT + '/capabilities', { params: { project_id: project || undefined } })).data });
  const rows = useQuery({ queryKey: ['industry', scope, kind, project, offset, day], enabled: mode === 'salon' || !!project, retry: false, queryFn: async () => {
    const from = day && kind === 'appointment' ? new Date(day + 'T00:00:00') : undefined;
    const until = from ? new Date(from) : undefined;
    if (until) until.setDate(until.getDate() + 1);
    return (await api.get<{ items: Row[] }>(ROOT + '/records', { params: { kind, project_id: project || undefined, offset, from_at: from?.toISOString(), until_at: until?.toISOString() } })).data.items;
  } });
  const resourceQuery = useQuery({ queryKey: ['industry', scope, 'resource'], enabled: mode === 'salon', retry: false, queryFn: async () => (await api.get<{ items: Row[] }>(ROOT + '/records', { params: { kind: 'resource', limit: 200 } })).data.items });
  const warehouses = useQuery({ queryKey: ['industry', scope, 'warehouses'], enabled: kind === 'material_issue', retry: false, queryFn: async () => (await api.get<{ items: { id: number; warehouse_name: string }[] }>('/srm/inventory/warehouses')).data.items });
  const projectFiles = useQuery({ queryKey: ['industry', scope, 'files', project, fileOffset], enabled: kind === 'site_diary' && !!project && creating, retry: false, queryFn: async () => (await api.get<{ id: number; original_name: string }[]>('/project-management/files', { params: { project_id: project, skip: fileOffset, limit: 50 } })).data });
  const boqQuery = useQuery({ queryKey: ['industry', scope, 'approved-boq', project], enabled: mode === 'construction' && !!project, retry: false, queryFn: async () => {
    const result = await Promise.all(['boq', 'variation'].map(k => api.get<{ items: Row[] }>(ROOT + '/records', { params: { kind: k, project_id: project, limit: 200 } })));
    return result.flatMap(r => r.data.items).filter(r => r.status === 'approved');
  } });
  const totals = useQuery({ queryKey: ['industry', scope, 'summary', project], enabled: mode === 'construction' && !!project, retry: false, queryFn: async () => (await api.get<Record<string, string>>(ROOT + `/projects/${project}/summary`)).data });
  const refresh = () => cache.invalidateQueries({ queryKey: ['industry', scope] });
  const listKey = ['industry', scope, kind, project, offset, day];
  const accept = async (row: Row) => {
    await cache.cancelQueries({ queryKey: listKey, exact: true });
    cache.setQueryData<Row[]>(listKey, old => [row, ...(old || []).filter(r => r.id !== row.id)]);
  };
  const mutation = useMutation({ mutationFn: async ({ path, body }: { path: string; body: unknown }) => (await api.post(ROOT + path, body)).data, onSuccess: async (result, variables) => {
    if (result.kind) await accept(result);
    else if (variables.path.endsWith('/invoice')) {
      await cache.cancelQueries({ queryKey: listKey, exact: true });
      const id = Number(variables.path.split('/')[2]);
      cache.setQueryData<Row[]>(['industry', scope, kind, project, offset, day], old => old?.map(r => r.id === id ? { ...r, invoice_id: result.id, revision: r.revision + 1 } : r));
    }
    setNotice('Saved successfully.'); void refresh();
  }, onError: () => setNotice('') });
  const clearDraft = () => { setCreating(false); setForm(empty()); setResources([]); setFiles([]); setFileOffset(0); requestId.current = crypto.randomUUID(); };
  useEffect(() => { setOffset(0); clearDraft(); }, [kind, project]);
  const dirty = creating && (JSON.stringify(form) !== JSON.stringify(empty()) || resources.length > 0 || files.length > 0);
  useMobileDraftGuard({ enabled: creating, dirty, draftKey: requestId.current, pending: () => mutation.isPending, onDiscard: clearDraft, message: 'Discard this unsaved operation?', guardHistory: true });
  const canLeave = () => !mutation.isPending && (!dirty || window.confirm('Discard this unsaved operation?'));
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    let body: Record<string, unknown> = { request_id: requestId.current, title: form.title };
    if (kind === 'resource') body = { ...body, resource_type: form.resource_type, timezone: form.timezone, opens: form.opens, closes: form.closes, weekdays: form.weekdays ? form.weekdays.split(',').map(Number) : [] };
    if (kind === 'appointment') body = { ...body, customer_id: Number(form.customer_id), service_id: Number(form.service_id), resource_ids: resources, starts_at: new Date(form.starts_at).toISOString(), duration_minutes: Number(form.duration_minutes), notes: form.notes || '', walk_in: form.walk_in === 'true', ...(form.project_id ? { project_id: Number(form.project_id), create_pms_task: true } : {}), ...(form.link_crm === 'true' && form.deal_id ? { deal_id: Number(form.deal_id) } : {}) };
    if (kind === 'boq' || kind === 'variation') body = { ...body, project_id: Number(project), code: form.code, unit: form.unit, quantity: form.quantity, unit_rate: form.unit_rate, tax_rate: form.tax_rate, ...(kind === 'variation' ? { variation_of: Number(form.parent_id) } : {}) };
    if (kind === 'measurement') body = { ...body, boq_id: Number(form.parent_id), quantity: form.quantity, measured_on: form.measured_on, notes: form.notes || '' };
    if (kind === 'site_diary') body = { ...body, project_id: Number(project), entry_date: form.entry_date, work_done: form.work_done, workforce: Number(form.workforce), weather: form.weather || '', blockers: form.blockers || '', file_ids: files };
    if (kind === 'subcontract') body = { ...body, project_id: Number(project), vendor_id: Number(form.vendor_id), scope: form.scope, amount: form.amount, due_date: form.due_date };
    if (kind === 'material_issue') body = { ...body, project_id: Number(project), product_id: Number(form.product_id), warehouse_id: Number(form.warehouse_id), quantity: form.quantity, issue_date: form.issue_date, notes: form.notes || '' };
    try { await mutation.mutateAsync({ path: paths[kind], body }); setCreating(false); setForm(empty()); setResources([]); requestId.current = crypto.randomUUID(); } catch { /* preserve draft and request identity on retry */ }
  };
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
  return <main className="mx-auto grid max-w-6xl gap-5 p-4 md:p-6">
    <header className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-semibold">{mode === 'salon' ? 'Salon operations' : 'Construction operations'}</h1><p className="text-sm text-muted-foreground">{mode === 'salon' ? 'Book resources, deliver services and bill the same CRM customer.' : 'Approve scope, record site work and bill certified quantities through Sales.'}</p></div><nav className="flex flex-wrap gap-3 text-sm"><Link to="/crm/pipeline-templates">CRM industry packs</Link><Link to="/srm/products-services">Catalog</Link><Link to="/srm/invoices">Invoices</Link><Link to="/srm/collections">Collections</Link><Link to={mode === 'salon' ? '/srm/pos' : '/srm/inventory'}>{mode === 'salon' ? 'Retail POS' : 'Materials & purchasing'}</Link></nav></header>
    {mode === 'construction' && <><Field name="PMS project"><ProjectPicker value={project} change={v => { if (canLeave()) setProject(v); }} /></Field>{project && <div className="flex flex-wrap gap-3 text-sm"><Link to={`/pms/projects/${project}/billing`}>Customer & project billing</Link><Link to={`/pms/projects/${project}`}>PMS schedule, tasks & files</Link></div>}{totals.data && <section className="grid grid-cols-2 gap-4 rounded-lg border p-4 md:grid-cols-4" aria-label="Project commercial summary">{[['Approved scope', 'approved_scope_value'], ['Certified work', 'certified_value'], ['Unbilled work', 'unbilled_certified_value'], ['Committed subcontracts', 'committed_subcontracts']].map(([label, key]) => <div key={key}><p className="text-xs text-muted-foreground">{label}</p><strong>{totals.data.currency} {Number(totals.data[key]).toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></div>)}<p className="col-span-full text-xs text-muted-foreground">Before tax. Materials consumed: {totals.data.material_cost_currency} {Number(totals.data.actual_material_cost).toLocaleString(undefined, { minimumFractionDigits: 2 })}. Retention tracked: {totals.data.currency} {Number(totals.data.retention_tracked).toLocaleString(undefined, { minimumFractionDigits: 2 })}. Retention remains within the full invoice receivable.</p></section>}</>}
    <div className="flex flex-wrap gap-2" role="tablist" aria-label="Operations">{(mode === 'salon' ? ['appointment', 'resource'] : ['boq', 'variation', 'measurement', 'site_diary', 'subcontract', 'material_issue']).map(k => <Button role="tab" aria-selected={kind === k} variant={kind === k ? 'default' : 'outline'} key={k} onClick={() => { if (canLeave()) setKind(k); }}>{titles[k]}</Button>)}</div>
    {(mode === 'salon' || project) && <div className="flex flex-wrap gap-2">{caps.data?.manage && <Button onClick={() => { if (canLeave()) { clearDraft(); setCreating(true); setNotice(''); } }}>New {kind.replace('_', ' ')}</Button>}<Button variant="outline" disabled={rows.isFetching} onClick={() => void refresh()}>Refresh</Button>{kind === 'appointment' && <Field name="Appointment date"><Input aria-label="Appointment date" type="date" value={day} onChange={e => { setDay(e.target.value); setOffset(0); }} /></Field>}</div>}
    {creating && <form onSubmit={e => void submit(e)} className="grid gap-4 rounded-lg border p-4" aria-label="Create operation"><h2 className="font-semibold">New {kind.replace('_', ' ')}</h2><div className="grid gap-4 md:grid-cols-2">{input('title', 'Title')}
      {kind === 'resource' && <><Field name="Resource type"><select className={controls} aria-label="Resource type" value={form.resource_type} onChange={e => update('resource_type', e.target.value)}>{['stylist', 'chair', 'room'].map(v => <option key={v}>{v}</option>)}</select></Field>{input('timezone', 'Timezone')}{input('opens', 'Opens', 'time')}{input('closes', 'Closes', 'time')}<fieldset className="flex flex-wrap gap-3"><legend className="text-sm">Working days</legend>{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d, i) => <label key={d} className="flex gap-1 text-sm"><input type="checkbox" checked={form.weekdays.split(',').includes(String(i))} onChange={e => update('weekdays', e.target.checked ? [...form.weekdays.split(',').filter(Boolean), String(i)].sort().join(',') : form.weekdays.split(',').filter(v => v !== String(i)).join(','))} />{d}</label>)}</fieldset></>}
      {kind === 'appointment' && <><Field name="Customer"><CompanySelect value={form.customer_id || ''} onChange={v => update('customer_id', v)} source="srm" entityKind="all" label="Customer" createRoles={['Customer']} /></Field><Field name="Service"><ServicePicker value={form.service_id || ''} change={v => update('service_id', v)} /></Field>{input('starts_at', 'Appointment time', 'datetime-local')}{input('duration_minutes', 'Duration (minutes)', 'number')}<fieldset className="grid gap-2"><legend className="text-sm">Stylist, chairs & rooms</legend>{resourceQuery.data?.filter(r => r.status === 'active').map(r => <label key={r.id} className="flex gap-2 text-sm"><input type="checkbox" checked={resources.includes(r.id)} onChange={e => setResources(rs => e.target.checked ? [...rs, r.id] : rs.filter(id => id !== r.id))} />{r.title} · {String(r.data.resource_type)}</label>)}{resourceQuery.isError && <p role="alert">{dealError(resourceQuery.error)}</p>}<Link to="/srm/salon?resources=1" onClick={e => { e.preventDefault(); if (canLeave()) setKind('resource'); }}>Manage resources</Link></fieldset><Field name="PMS delivery project (optional)"><ProjectPicker value={form.project_id || ''} change={v => update('project_id', v)} /></Field>{input('notes', 'Visit notes', 'text', false)}<label className="flex gap-2 text-sm"><input type="checkbox" checked={form.link_crm === 'true'} onChange={e => update('link_crm', String(e.target.checked))} />Link an existing CRM opportunity</label>{form.link_crm === 'true' && <Field name="CRM opportunity"><DealRecordSelect resource="deals" name="CRM opportunity" initial={[]} companyId={form.customer_id} value={form.deal_id || ''} onChange={v => update('deal_id', v)} /></Field>}<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.walk_in === 'true'} onChange={e => update('walk_in', String(e.target.checked))} />Walk-in</label></>}
      {(kind === 'boq' || kind === 'variation') && <>{kind === 'variation' && parent}{input('code', 'Item code')}{input('unit', 'Unit')}{input('quantity', 'Quantity', 'number')}{input('unit_rate', 'Unit rate', 'number')}{input('tax_rate', 'Tax (%)', 'number')}</>}
      {kind === 'measurement' && <>{parent}{input('quantity', 'Measured quantity', 'number')}{input('measured_on', 'Measured on', 'date')}{input('notes', 'Measurement notes', 'text', false)}</>}
      {kind === 'site_diary' && <>{input('entry_date', 'Entry date', 'date')}{input('workforce', 'Workforce count', 'number')}{input('weather', 'Weather', 'text', false)}<Field name="Work completed"><textarea className={controls} aria-label="Work completed" required maxLength={10000} value={form.work_done || ''} onChange={e => update('work_done', e.target.value)} /></Field>{input('blockers', 'Blockers', 'text', false)}<fieldset className="grid gap-2"><legend className="text-sm">Project photos & documents</legend>{projectFiles.data?.map(f => <label key={f.id} className="flex gap-2 text-sm"><input type="checkbox" checked={files.includes(f.id)} onChange={e => setFiles(v => e.target.checked ? [...v, f.id] : v.filter(id => id !== f.id))} />{f.original_name}</label>)}{projectFiles.isError && <p role="alert">{dealError(projectFiles.error)}</p>}<div className="flex gap-2"><Button type="button" size="sm" variant="outline" disabled={!fileOffset} onClick={() => setFileOffset(v => Math.max(0, v - 50))}>Previous files</Button><Button type="button" size="sm" variant="outline" disabled={!projectFiles.data || projectFiles.data.length < 50} onClick={() => setFileOffset(v => v + 50)}>More files</Button></div><Link to={`/pms/files?projectId=${project}`}>Upload photos in PMS Files</Link></fieldset></>}
      {kind === 'subcontract' && <><Field name="Vendor"><CompanySelect source="srm" label="Vendor" value={form.vendor_id || ''} onChange={v => update('vendor_id', v)} createRoles={['Vendor']} /></Field>{input('scope', 'Work scope')}{input('amount', 'Commitment amount', 'number')}{input('due_date', 'Due date', 'date')}</>}
      {kind === 'material_issue' && <><Field name="Stock item"><ServicePicker kind="product" value={form.product_id || ''} change={v => update('product_id', v)} /></Field><Field name="Warehouse"><select className={controls} aria-label="Warehouse" required value={form.warehouse_id || ''} onChange={e => update('warehouse_id', e.target.value)}><option value="">Choose warehouse</option>{warehouses.data?.map(w => <option key={w.id} value={w.id}>{w.warehouse_name}</option>)}</select>{warehouses.isError && <p role="alert">{dealError(warehouses.error)}</p>}</Field>{input('quantity', 'Consumed quantity', 'number')}{input('issue_date', 'Issue date', 'date')}{input('notes', 'Issue notes', 'text', false)}<p className="text-sm text-muted-foreground">Posts an actual stock consumption at the warehouse average cost. Insufficient stock is blocked.</p></>}
    </div><div className="flex gap-2"><Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Saving…' : 'Save operation'}</Button><Button type="button" variant="outline" disabled={mutation.isPending} onClick={() => { if (canLeave()) clearDraft(); }}>Cancel</Button></div></form>}
    {notice && <p role="status">{notice}</p>}{mutation.isError && <p role="alert" className="text-sm text-destructive">{dealError(mutation.error)}</p>}{rows.isError && <div role="alert">{dealError(rows.error)} <Button variant="outline" onClick={() => void rows.refetch()}>Retry</Button></div>}{rows.isFetching && <p role="status">Loading operations…</p>}
    {kind === 'measurement' && input('retention_percent', 'Retention to track on new invoices (%)', 'number', false)}
    <section className="grid gap-3" aria-label={titles[kind]}>{rows.data?.map(row => <article key={row.id} className="grid gap-3 rounded-lg border p-4"><div className="flex flex-wrap justify-between gap-2"><h2 className="font-semibold">{row.title}</h2><span className="text-sm">{row.status.replace('_', ' ')}</span></div><p className="text-sm text-muted-foreground">{row.kind === 'appointment' ? `${String(row.data.service_name)} · ${new Date(String(row.data.starts_at)).toLocaleString()} · ${row.data.duration_minutes} min` : row.kind === 'resource' ? `${row.data.resource_type} · ${row.data.opens}–${row.data.closes} · ${row.data.timezone}` : row.kind === 'site_diary' ? `${row.data.entry_date} · ${row.data.work_done}` : row.kind === 'subcontract' ? `${row.data.scope} · ${row.data.amount}` : row.kind === 'material_issue' ? `${row.data.product_name} · ${row.data.quantity} consumed from ${row.data.warehouse_name} · ${row.data.movement_number}` : `${row.data.code || row.data.boq_code || ''} · ${row.data.quantity} ${row.data.unit} × ${row.data.unit_rate}`}</p><div className="flex flex-wrap gap-2">
      {caps.data?.manage && row.kind === 'appointment' && ({ booked: ['checked_in', 'cancelled', 'no_show'], checked_in: ['in_service', 'cancelled'], in_service: ['completed'] } as Record<string, string[]>)[row.status]?.map(s => <Button size="sm" variant="outline" key={s} disabled={mutation.isPending} onClick={() => transition(row, s)}>{s.replace('_', ' ')}</Button>)}
      {caps.data?.approve && (caps.data.self_approve || row.created_by !== userId) && ['boq', 'variation', 'measurement', 'subcontract'].includes(row.kind) && row.status === 'draft' && ['approved', 'rejected'].map(s => <Button key={s} size="sm" variant="outline" disabled={mutation.isPending} onClick={() => transition(row, s)}>{s === 'approved' ? 'Approve' : 'Reject'}</Button>)}
      {!!row.data.deal_id && <Link className="text-sm underline" to={`/crm/deals/${row.data.deal_id}`}>Open CRM opportunity</Link>}{!!row.data.pms_task_id && <Link className="text-sm underline" to={`/pms/tasks/${row.data.pms_task_id}`}>Open PMS delivery task</Link>}{row.invoice_id ? <Link to={`/srm/invoices/${row.invoice_id}`} className="text-sm underline">Open shared invoice</Link> : caps.data?.invoice && ((row.kind === 'appointment' && row.status === 'completed') || (row.kind === 'measurement' && row.status === 'approved')) && <Button size="sm" disabled={mutation.isPending} onClick={() => invoice(row)}>Create invoice draft</Button>}
    </div>{caps.data?.manage && row.kind === 'appointment' && row.status === 'booked' && <RescheduleForm key={row.revision} row={row} resources={resourceQuery.data || []} saved={async updated => { await accept(updated); setNotice('Appointment rescheduled.'); void refresh(); }} />}</article>)}</section>
    {rows.data?.length === 0 && <p className="text-sm text-muted-foreground">No {titles[kind].toLowerCase()} recorded in this branch{mode === 'construction' ? ' and project' : ''}.</p>}
    {!!rows.data?.length && <div className="flex gap-2"><Button variant="outline" disabled={!offset} onClick={() => setOffset(n => Math.max(0, n - 100))}>Previous</Button><Button variant="outline" disabled={rows.data.length < 100} onClick={() => setOffset(n => n + 100)}>Next</Button></div>}
  </main>;
}
