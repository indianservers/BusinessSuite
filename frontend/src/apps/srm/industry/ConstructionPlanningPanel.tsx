import ConstructionCustomerSelect from './ConstructionCustomerSelect';
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import ConstructionDependenciesPanel, { ConstructionResourceSelect } from './ConstructionDependenciesPanel';
import AdvancedSchedulingPanel from '@/apps/project-management/components/AdvancedSchedulingPanel';
import { api } from '@/services/api';
import { useAuthStore } from '@/store/authStore';
import { useRecordScope } from '@/lib/record-scope';
import { masterScope } from '@/shared/master-data/CompanySelect';
import { dealError } from '@/apps/crm/deals/deal-utils';
import { decodeDownloadError } from '@/lib/decode-download-error';

const ROOT = '/srm/industry';
const control = 'w-full rounded-md border bg-background px-3 py-2 text-sm';
type Row = { id: number; title: string; kind: string; status: string; revision: number; created_by: number; invoice_id?: number; parent_id?: number; data: Record<string, unknown> };
type Task = { id: number; title: string; task_key?: string; parent_task_id?: number | null; start_date?: string; due_date?: string; status?: string; actual_hours?: string | null; updated_at?: string | null; progress_revision?: number; progress_mode?: string; progress_percent?: number };
type File = { id: number; original_name: string };
type Caps = { workspace_ready?: boolean; workspace_setup_manage?: boolean; commercial_manage?: boolean; cost_budget_manage?: boolean; sites_create?: boolean; wbs_define?: boolean; actuals_task_manage?: boolean; actuals_cost_manage?: boolean; planning_manage?: boolean; planning_approve?: boolean; handover_prepare?: boolean; certificate_prepare?: boolean; delivery_approve?: boolean; reports?: boolean; measurements_certify?: boolean };
type Intent = { scope: string; project: number; path: string; method: 'post' | 'put'; body: Record<string, unknown> };
type Baseline = { id: string; name: string };
type Checklist = { label: string; complete: boolean };
const emptyPackage = { title: '', task_id: '', boq_id: '', quantity: '', budget_cost: '', notes: '' };

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="grid gap-1 text-sm"><span>{label}</span>{children}</label>;
}

function DeliveryEvidence({ row }: { row: Row }) {
  if (row.kind === 'payment_certificate') {
    const snapshot = row.data.source_snapshot as Record<string, unknown> | undefined;
    if (!snapshot) return null;
    return <dl className="grid grid-cols-2 gap-2 text-sm">{[['Invoice', 'invoice_number'], ['Currency', 'currency'], ['Certified quantity', 'quantity'], ['Unit', 'unit'], ['Invoice total', 'invoice_total'], ['Retention tracked', 'retention_amount'], ['Certified net payable', 'certified_net_payable']].map(([label, key]) => <div key={key}><dt className="text-xs text-muted-foreground">{label}</dt><dd>{String(snapshot[key] ?? 'Unavailable')}</dd></div>)}</dl>;
  }
  const checklist = Array.isArray(row.data.checklist) ? row.data.checklist as Checklist[] : [];
  return <div className="grid gap-2 text-sm"><ul className="list-inside list-disc">{checklist.map((item, index) => <li key={index}>{item.complete ? 'Complete' : 'Open'} · {item.label}</li>)}</ul><p>Blockers: {String(row.data.blockers || 'None recorded')}</p><p>Supporting file IDs: {Array.isArray(row.data.file_ids) ? row.data.file_ids.join(', ') : 'None'}</p><p>PMS task IDs: {Array.isArray(row.data.task_ids) ? row.data.task_ids.join(', ') : 'None'}</p></div>;
}

function PerformanceDetails({ data }: { data: Record<string, unknown> }) {
  const productivity = data.certified_quantity_per_workforce_day_by_unit;
  const units = productivity && typeof productivity === 'object' && !Array.isArray(productivity) ? Object.entries(productivity) : [];
  const delays = Array.isArray(data.task_delay_variance) ? data.task_delay_variance as { task_id: number; variance_calendar_days: number }[] : [];
  return <div className="grid gap-2 text-sm"><p className="text-xs text-muted-foreground">BAC: cost budget · PV: planned value · EV: certified earned value · AC: current actual cost.</p>{units.length > 0 && <dl className="grid grid-cols-2 gap-2">{units.map(([unit, value]) => <div key={unit}><dt className="text-xs text-muted-foreground">{unit} per workforce-day</dt><dd>{value == null ? 'Unavailable' : String(value)}</dd></div>)}</dl>}<p className="text-xs text-muted-foreground">{String(data.productivity_basis || '')}</p>{delays.length > 0 && <details><summary className="cursor-pointer">Task delay variance</summary><ul className="mt-2 list-inside list-disc">{delays.map(task => <li key={task.task_id}>Task #{task.task_id}: {task.variance_calendar_days} calendar days</li>)}</ul></details>}</div>;
}

function loadIntent(key: string, scope: string, project: number): Intent | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(key) || 'null') as Intent | null;
    return value && value.scope === scope && value.project === project && ['post', 'put'].includes(value.method)
      && /^\/srm\/industry\/(workspace-definitions|site-projects|projects\/\d+\/(?:commercial-source|wbs-tasks|cost-budget|cost-actuals|task-actuals\/\d+)|work-packages(?:\/\d+)?|planning-baselines(?:\/\d+\/review)?|payment-certificates|measurements\/\d+\/work-package|handovers(?:\/\d+)?|delivery\/\d+\/review)$/.test(value.path)
      && value.body && typeof value.body === 'object' ? value : null;
  } catch { return null; }
}

export default function ConstructionPlanningPanel({ projectId, onSaved }: { projectId: number; onSaved?: () => void }) {
  const generation = useRecordScope();
  return <PlanningWorkspace key={`${generation}:${projectId}`} projectId={projectId} scope={masterScope()} onSaved={onSaved} />;
}

export function ConstructionSiteCreate({ onCreated }: { onCreated?: (project: { id: number; name: string }) => void }) {
  const generation = useRecordScope();
  return <SiteDefinition key={generation} scope={masterScope()} onCreated={onCreated} />;
}

function SiteDefinition({ scope, onCreated }: { scope: string; onCreated?: (project: { id: number; name: string }) => void }) {
  const cache = useQueryClient(), alive = useRef(true), writing = useRef(false);
  const [open, setOpen] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const initial = { workspace_id: '', name: '', project_key: '', description: '', start_date: '', due_date: '', estimated_cost: '', estimated_hours: '' };
  const [workspaceName, setWorkspaceName] = useState('');
  const [form, setForm] = useState(initial), key = `construction-site-intent:${scope}`;
  const [intent, setIntent] = useState<Intent | null>(() => loadIntent(key, scope, 0)), pending = useRef(intent);
  const owns = () => alive.current && scope === masterScope();
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const caps = useQuery({ queryKey: ['construction-site-definition', scope, 'capabilities'], enabled: open, retry: false,
    queryFn: async ({ signal }) => (await api.get<Caps>(ROOT + '/capabilities', { signal })).data });
  const workspaces = useQuery({ queryKey: ['construction-site-definition', scope, 'workspaces'], enabled: open && !!(caps.data?.sites_create || caps.data?.workspace_setup_manage), retry: false,
    queryFn: async ({ signal }) => (await api.get<{ items: { id: number; name: string }[] }>(ROOT + '/definition-workspaces', { signal })).data.items });
  function retain(value: Intent | null) {
    pending.current = value; setIntent(value);
    try { if (value) sessionStorage.setItem(key, JSON.stringify(value)); else sessionStorage.removeItem(key); } catch { /* Keep the in-memory request when session storage is unavailable. */ }
  }
  async function send(saved: Intent) {
    if (!owns() || writing.current) return;
    if (![ROOT + '/site-projects', ROOT + '/workspace-definitions'].includes(saved.path) || saved.method !== 'post') { retain(null); setError('This stored setup request is unsupported. Reload the current setup form.'); return; }
    writing.current = true; setBusy(true); setError(''); setNotice('');
    try {
      const result = await api.post<{ id: number; name: string; role?: 'Owner' }>(saved.path, saved.body);
      if (!owns()) return;
      const workspace = saved.path === ROOT + '/workspace-definitions';
      if (!Number.isSafeInteger(result.data.id) || result.data.id < 1 || !result.data.name?.trim() || (workspace && result.data.role !== 'Owner')) throw new Error('The native setup receipt could not be verified. Retry this same request.');
      retain(null);
      if (workspace) {
        setWorkspaceName(''); setForm(current => ({ ...current, workspace_id: String(result.data.id) })); setNotice('Canonical PMS workspace created.');
        await cache.invalidateQueries({ queryKey: ['construction-site-definition', scope, 'workspaces'] });
      } else {
        setForm(initial); setNotice('Canonical PMS site created.');
        await cache.invalidateQueries({ queryKey: ['industry-projects', scope] });
        if (owns()) onCreated?.({ id: result.data.id, name: result.data.name });
      }
    } catch (failure) {
      if (!owns()) return;
      setError(dealError(failure));
      const status = (failure as { response?: { status?: number } }).response?.status;
      if (status && status >= 400 && status < 500) retain(null);
    } finally { writing.current = false; if (owns()) setBusy(false); }
  }
  return <details className="rounded-lg border p-4" onToggle={event => setOpen(event.currentTarget.open)}><summary className="cursor-pointer font-semibold">Define a Construction site</summary>{open && <div className="mt-3 grid gap-3">
    {caps.isFetching && <p role="status">Checking native site creation access…</p>}{[caps, workspaces].filter(query => query.isError).map((query, index) => <div key={index} role="alert" className="text-sm text-destructive">{dealError(query.error)} <Button variant="outline" onClick={() => void query.refetch()}>Retry source</Button></div>)}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}{notice && <p role="status">{notice}</p>}
    {intent && <div className="grid gap-2 rounded-md border p-3 text-sm"><p>This setup request has not been confirmed. Retry the same request before creating another workspace or site.</p><Button variant="outline" disabled={busy} onClick={() => void send(intent)}>Retry setup request</Button></div>}
    {caps.data && !caps.data.sites_create && <p className="text-sm text-muted-foreground">Site creation requires native project creation and Construction workspace administration access.</p>}
    {caps.data?.workspace_setup_manage && <details className="rounded-md border p-3"><summary className="cursor-pointer font-medium">Create a native Construction workspace</summary><form className="mt-3 grid gap-3" aria-label="Create canonical Construction workspace" onSubmit={event => { event.preventDefault(); if (!owns() || pending.current || writing.current) return; const saved: Intent = { scope, project: 0, method: 'post', path: ROOT + '/workspace-definitions', body: { request_id: crypto.randomUUID(), name: workspaceName.trim() } }; retain(saved); void send(saved); }}><p className="text-sm text-muted-foreground">Create a canonical PMS workspace for this assignment. The native owner membership and Construction scope are recorded together.</p><fieldset disabled={busy || !!intent} className="grid gap-3"><Field label="Workspace name"><Input aria-label="Construction workspace name" required maxLength={180} value={workspaceName} onChange={event => setWorkspaceName(event.target.value)} /></Field></fieldset><Button disabled={busy || !!intent || !workspaceName.trim()}>Create native PMS workspace</Button></form></details>}
    {caps.data?.sites_create && <form className="grid gap-3" aria-label="Define canonical Construction site" onSubmit={event => { event.preventDefault(); if (!owns() || pending.current || writing.current) return; const saved: Intent = { scope, project: 0, method: 'post', path: ROOT + '/site-projects', body: { ...form, workspace_id: Number(form.workspace_id), request_id: crypto.randomUUID() } }; retain(saved); void send(saved); }}><p className="text-sm text-muted-foreground">Create the site in an existing owned PMS workspace. The project and its budget remain canonical PMS records.</p><fieldset disabled={busy || !!intent} className="grid gap-3 md:grid-cols-2">
      <Field label="Owned PMS workspace"><NativeSelect aria-label="Site PMS workspace" className={control} required value={form.workspace_id} onChange={event => setForm({ ...form, workspace_id: event.target.value })}><option value="">Choose native workspace</option>{workspaces.data?.map(workspace => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}</NativeSelect></Field>
      <Field label="Site / project name"><Input aria-label="Site project name" required maxLength={180} value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} /></Field>
      <Field label="Project key"><Input aria-label="Site project key" required maxLength={20} value={form.project_key} onChange={event => setForm({ ...form, project_key: event.target.value })} /></Field>
      <Field label="Project start"><Input aria-label="Site project start" type="date" required value={form.start_date} onChange={event => setForm({ ...form, start_date: event.target.value })} /></Field>
      <Field label="Project due"><Input aria-label="Site project due" type="date" min={form.start_date || undefined} required value={form.due_date} onChange={event => setForm({ ...form, due_date: event.target.value })} /></Field>
      <Field label="Estimated cost budget"><Input aria-label="Site estimated cost" type="number" min="0.01" step="0.01" required value={form.estimated_cost} onChange={event => setForm({ ...form, estimated_cost: event.target.value })} /></Field>
      <Field label="Estimated work hours"><Input aria-label="Site estimated hours" type="number" min="0.01" step="0.01" required value={form.estimated_hours} onChange={event => setForm({ ...form, estimated_hours: event.target.value })} /></Field>
      <Field label="Project description"><textarea aria-label="Site project description" className={control} maxLength={10000} value={form.description} onChange={event => setForm({ ...form, description: event.target.value })} /></Field>
    </fieldset><Button disabled={busy || !!intent || !workspaces.data?.length}>Create native PMS site</Button>{workspaces.data?.length === 0 && <p className="text-sm text-muted-foreground">No owned workspace is available for this assignment. Create one with the authorized workspace setup above, or ask your Construction administrator to complete setup.</p>}</form>}
  </div>}</details>;
}

function PlanningWorkspace({ projectId, scope, onSaved }: { projectId: number; scope: string; onSaved?: () => void }) {
  const cache = useQueryClient(), actorId = useAuthStore(state => state.user?.id);
  const [open, setOpen] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const alive = useRef(true), owner = useRef(scope), storageKey = `construction-planning-intent:${scope}:${projectId}`;
  const [intent, setIntent] = useState<Intent | null>(() => loadIntent(storageKey, scope, projectId));
  const pending = useRef(intent), writing = useRef(false);
  const owns = () => alive.current && owner.current === masterScope();
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const prefix = ['construction-planning', scope, projectId];
  const caps = useQuery({ queryKey: [...prefix, 'capabilities'], enabled: open, retry: false,
    queryFn: async ({ signal }) => (await api.get<Caps>(ROOT + '/capabilities', { params: { project_id: projectId }, signal })).data });
  const ready = open && !!caps.data;
  const commercial = useQuery({ queryKey: [...prefix, 'commercial-source'], enabled: ready && !!caps.data?.commercial_manage, retry: false,
    queryFn: async ({ signal }) => (await api.get<{ customer_id: number | null; seller_id: number | null; currency: string | null; identity_locked: boolean; has_advanced_links: boolean }>(`${ROOT}/projects/${projectId}/commercial-source`, { signal })).data });
  const [customerId, setCustomerId] = useState(''), [commercialCurrency, setCommercialCurrency] = useState('');
  const tasks = useQuery({ queryKey: [...prefix, 'tasks'], enabled: ready, retry: false,
    queryFn: async ({ signal }) => {
      const result = (await api.get<Task[] | { items: Task[] }>(`${ROOT}/projects/${projectId}/planning-tasks`, { signal })).data;
      return Array.isArray(result) ? result : result.items;
    } });
  const packages = useQuery({ queryKey: [...prefix, 'work-packages'], enabled: ready, retry: false,
    queryFn: async ({ signal }) => (await api.get<{ items: Row[] }>(ROOT + '/work-packages', { params: { project_id: projectId }, signal })).data.items });
  const boq = useQuery({ queryKey: [...prefix, 'approved-scope'], enabled: ready, retry: false,
    queryFn: async ({ signal }) => (await Promise.all(['boq', 'variation'].map(kind => api.get<{ items: Row[] }>(ROOT + '/records', { params: { kind, project_id: projectId, limit: 200 }, signal })))).flatMap(result => result.data.items).filter(row => row.status === 'approved') });
  const nativeBaselines = useQuery({ queryKey: [...prefix, 'native-baselines'], enabled: ready, retry: false,
    queryFn: async ({ signal }) => (await api.get<{ baselines: Baseline[] }>(`/project-management/projects/${projectId}/schedule-analysis`, { signal })).data.baselines });
  const baselines = useQuery({ queryKey: [...prefix, 'planning-baselines'], enabled: ready, retry: false,
    queryFn: async ({ signal }) => (await api.get<{ items: Row[] }>(`${ROOT}/projects/${projectId}/planning-baselines`, { signal })).data.items });
  const measurements = useQuery({ queryKey: [...prefix, 'certified-measurements'], enabled: ready && !!(caps.data?.certificate_prepare || caps.data?.measurements_certify), retry: false,
    queryFn: async ({ signal }) => (await api.get<{ items: Row[] }>(ROOT + '/records', { params: { project_id: projectId, kind: 'measurement', limit: 200 }, signal })).data.items.filter(row => row.status === 'approved') });
  const financialDocuments = !!(caps.data?.reports || caps.data?.certificate_prepare);
  const deliveries = useQuery({ queryKey: [...prefix, 'deliveries', financialDocuments], enabled: ready, retry: false,
    queryFn: async ({ signal }) => (await Promise.all((financialDocuments ? ['payment_certificate', 'handover'] : ['handover']).map(kind => api.get<{ items: Row[] }>(ROOT + '/records', { params: { project_id: projectId, kind, limit: 200 }, signal })))).flatMap(result => result.data.items) });
  const files = useQuery({ queryKey: [...prefix, 'owned-files'], enabled: ready && !!caps.data?.handover_prepare, retry: false,
    queryFn: async ({ signal }) => (await api.get<File[]>('/project-management/files', { params: { project_id: projectId }, signal })).data });
  const costSource = useQuery({ queryKey: [...prefix, 'cost-source'], enabled: ready && !!(caps.data?.actuals_cost_manage || caps.data?.cost_budget_manage), retry: false,
    queryFn: async ({ signal }) => (await api.get<{ project_id: number; currency: string; estimated_cost: string | null; actual_cost: string | null }>(`${ROOT}/projects/${projectId}/cost-source`, { signal })).data });
  const [assignedIds, setAssignedIds] = useState<number[]>([]);
  const [definition, setDefinition] = useState({ title: '', task_key: '', description: '', parent_task_id: '', start_date: '', due_date: '', estimated_hours: '' });
  const [actualTask, setActualTask] = useState(''), [actualStatus, setActualStatus] = useState(''), [actualHours, setActualHours] = useState(''), [actualProgress, setActualProgress] = useState(''), [progressNote, setProgressNote] = useState('');
  const [budgetCost, setBudgetCost] = useState(''), [budgetReason, setBudgetReason] = useState('');
  const [actualCost, setActualCost] = useState(''), [costDate, setCostDate] = useState(() => new Date().toLocaleDateString('en-CA')), [costReason, setCostReason] = useState('');
  const [wp, setWp] = useState(emptyPackage), [editing, setEditing] = useState<number | null>(null);
  const [baselineTitle, setBaselineTitle] = useState(''), [nativeBaseline, setNativeBaseline] = useState('');
  const [selectedBaseline, setSelectedBaseline] = useState(''), [asOf, setAsOf] = useState(() => new Date().toLocaleDateString('en-CA'));
  const [certificateTitle, setCertificateTitle] = useState(''), [measurement, setMeasurement] = useState('');
  const [attributionMeasurement, setAttributionMeasurement] = useState(''), [attributionPackage, setAttributionPackage] = useState(''), [attributionReason, setAttributionReason] = useState('');
  const [handoverTitle, setHandoverTitle] = useState(''), [handoverEdit, setHandoverEdit] = useState<number | null>(null);
  const [checklist, setChecklist] = useState<Checklist[]>([{ label: 'Site work reviewed', complete: false }]), [newCheck, setNewCheck] = useState('');
  const [fileIds, setFileIds] = useState<number[]>([]), [taskIds, setTaskIds] = useState<number[]>([]), [blockers, setBlockers] = useState('');
  const [reasons, setReasons] = useState<Record<number, string>>({});
  const [performanceRequest, setPerformanceRequest] = useState<{ baseline: string; date: string } | null>(null);
  const performance = useQuery({ queryKey: [...prefix, 'performance', performanceRequest], enabled: ready && !!performanceRequest, retry: false,
    queryFn: async ({ signal }) => (await api.get<Record<string, unknown>>(`${ROOT}/projects/${projectId}/performance`, {
      params: { baseline_id: performanceRequest?.baseline, as_of: performanceRequest?.date }, signal })).data });
  const frozen = busy || !!intent;
  function retain(value: Intent | null) {
    pending.current = value; setIntent(value);
    try { if (value) sessionStorage.setItem(storageKey, JSON.stringify(value)); else sessionStorage.removeItem(storageKey); } catch { /* The in-memory key remains valid when browser storage is unavailable. */ }
  }
  async function refresh() {
    await cache.invalidateQueries({ queryKey: prefix });
    await cache.invalidateQueries({ queryKey: ['industry', scope] });
    if (owns()) onSaved?.();
  }
  async function send(saved: Intent) {
    if (!owns() || writing.current) return;
    writing.current = true; setBusy(true); setError(''); setNotice('');
    try {
      if (saved.path === `${ROOT}/projects/${projectId}/cost-budget`) {
        setPerformanceRequest(null);
        await cache.cancelQueries({ queryKey: [...prefix, 'performance'] });
      }
      await api[saved.method](saved.path, saved.body);
      if (!owns()) return;
      retain(null); setNotice('Saved successfully.');
      if (saved.path === ROOT + '/work-packages' || saved.path.includes('/work-packages/')) { setWp(emptyPackage); setEditing(null); }
      if (saved.path === ROOT + '/planning-baselines') { setBaselineTitle(''); setNativeBaseline(''); }
      if (saved.path.includes('/measurements/') && saved.path.endsWith('/work-package')) { setAttributionMeasurement(''); setAttributionPackage(''); setAttributionReason(''); }
      if (saved.path.endsWith('/wbs-tasks')) setDefinition({ title: '', task_key: '', description: '', parent_task_id: '', start_date: '', due_date: '', estimated_hours: '' });
      if (saved.path.includes('/task-actuals/')) { setActualTask(''); setActualStatus(''); setActualHours(''); setActualProgress(''); setProgressNote(''); }
      if (saved.path.endsWith('/cost-actuals')) { setActualCost(''); setCostReason(''); }
      if (saved.path === ROOT + '/payment-certificates') { setCertificateTitle(''); setMeasurement(''); }
      if (saved.path === ROOT + '/handovers' || saved.path.includes('/handovers/')) { setHandoverTitle(''); setHandoverEdit(null); setFileIds([]); setTaskIds([]); setBlockers(''); setChecklist([{ label: 'Site work reviewed', complete: false }]); }
      await refresh();
    } catch (failure) {
      if (!owns()) return;
      setError(dealError(failure));
      const status = (failure as { response?: { status?: number } }).response?.status;
      if (status && status >= 400 && status < 500) { retain(null); if (status === 409) void refresh(); }
    } finally { writing.current = false; if (owns()) setBusy(false); }
  }
  function write(path: string, body: Record<string, unknown>, method: 'post' | 'put' = 'post', newRequest = true) {
    if (!owns() || writing.current || pending.current) return;
    const saved: Intent = { scope, project: projectId, path: ROOT + path, method,
      body: { ...body, ...(newRequest ? { request_id: crypto.randomUUID() } : {}) } };
    retain(saved); void send(saved);
  }
  async function download(path: string, name: string, params: Record<string, string | number>) {
    if (!owns() || busy) return;
    setBusy(true); setError('');
    try {
      const result = await api.get(path, { params, responseType: 'blob', recordCache: false });
      if (!owns()) return;
      const url = URL.createObjectURL(result.data), link = document.createElement('a');
      link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (failure) { if (owns()) setError(dealError(await decodeDownloadError(failure))); }
    finally { if (owns()) setBusy(false); }
  }
  function submitPackage(event: FormEvent) {
    event.preventDefault();
    if (!caps.data?.planning_manage) return;
    if (editing) {
      const row = packages.data?.find(item => item.id === editing); if (!row) return;
      write(`/work-packages/${row.id}`, { expected_revision: row.revision, quantity: wp.quantity, budget_cost: wp.budget_cost, notes: wp.notes }, 'put', false);
    } else write('/work-packages', { project_id: projectId, task_id: Number(wp.task_id), boq_id: Number(wp.boq_id), title: wp.title, quantity: wp.quantity, budget_cost: wp.budget_cost, notes: wp.notes });
  }
  function review(row: Row, baseline: boolean, status: 'approved' | 'rejected') {
    if ((baseline ? !caps.data?.planning_approve : !caps.data?.delivery_approve) || row.created_by === actorId) return;
    write(baseline ? `/planning-baselines/${row.id}/review` : `/delivery/${row.id}/review`,
      { expected_revision: row.revision, status, reason: reasons[row.id] || '' }, 'post', false);
  }
  const attributionSource = measurements.data?.find(row => row.id === Number(attributionMeasurement));
  const actualTaskSource = tasks.data?.find(task => task.id === Number(actualTask));
  const metrics = performance.data;
  const errors = [caps, tasks, packages, boq, nativeBaselines, baselines, measurements, deliveries, files, costSource, commercial].filter(query => query.isError);
  const choose = (ids: number[], id: number, checked: boolean) => checked ? [...ids, id] : ids.filter(value => value !== id);
  return <details className="rounded-lg border p-4" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary className="cursor-pointer font-semibold">Project planning &amp; handover tools</summary>
    {open && <div className="mt-4 grid gap-4">
      {caps.isPending && <p role="status">Checking project planning access…</p>}
      {errors.map((query, index) => <div key={index} role="alert" className="text-sm text-destructive">{dealError(query.error)} <Button variant="outline" disabled={busy} onClick={() => void query.refetch()}>Retry source</Button></div>)}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}{notice && <p role="status" className="text-sm">{notice}</p>}
      {intent && <div className="grid gap-2 rounded-md border p-3 text-sm"><p>{busy ? 'Saving this request…' : 'This request has not been confirmed. Retry the same request before starting another change.'}</p><Button variant="outline" disabled={busy} onClick={() => void send(intent)}>Retry this request</Button></div>}
      {ready && <>
        {caps.data?.workspace_ready === false && <p role="status" className="text-sm text-muted-foreground">This project’s native workspace needs reviewed Construction setup before planning or cost changes. An administrator must complete that setup.</p>}
        {caps.data?.commercial_manage && <details className="rounded-md border p-3"><summary className="cursor-pointer font-medium">Native project customer &amp; billing currency</summary><div className="mt-3 grid gap-3"><p className="text-sm text-muted-foreground">Set the existing customer before preparing BOQ quantities. The seller is this assignment’s company. Customer, seller and currency become fixed once project pricing begins.</p>{commercial.data?.customer_id && <p className="text-sm">Customer #{commercial.data.customer_id} · Seller #{commercial.data.seller_id} · {commercial.data.currency}</p>}{commercial.data?.identity_locked || commercial.data?.has_advanced_links ? <p className="text-sm text-muted-foreground">The existing native commercial identity is preserved. Changes require its reviewed reconciliation workflow.</p> : <form className="grid gap-3" aria-label="Configure Construction commercial identity" onSubmit={event => { event.preventDefault(); write(`/projects/${projectId}/commercial-source`, { customer_id: Number(customerId), currency: commercialCurrency }); }}><fieldset disabled={frozen || commercial.isPending} className="grid gap-3 md:grid-cols-2"><ConstructionCustomerSelect value={customerId} onChange={setCustomerId} /><Field label="Billing currency"><Input aria-label="Construction billing currency" required pattern="[A-Z]{3}" maxLength={3} placeholder={commercial.data?.currency || 'Currency code'} value={commercialCurrency} onChange={event => setCommercialCurrency(event.target.value.toUpperCase())} /></Field></fieldset><Button disabled={frozen || commercial.isPending || !customerId || !/^[A-Z]{3}$/.test(commercialCurrency)}>Save native commercial identity</Button></form>}</div></details>}
        {caps.data?.cost_budget_manage && <details className="rounded-md border p-3"><summary className="cursor-pointer font-medium">Canonical project cost budget</summary><form className="mt-3 grid gap-3" aria-label="Revise Construction cost budget" onSubmit={event => { event.preventDefault(); if (!costSource.data) return; write(`/projects/${projectId}/cost-budget`, { expected_estimated_cost: costSource.data.estimated_cost, estimated_cost: budgetCost, reason: budgetReason }); }}><p className="text-sm text-muted-foreground">Current PMS estimate: {costSource.data?.estimated_cost ?? 'Unset'} {costSource.data?.currency}. Existing approved baselines remain historical snapshots.</p><fieldset disabled={frozen || !costSource.data} className="grid gap-3 md:grid-cols-2"><Field label="Revised estimated cost"><Input aria-label="Construction estimated cost budget" type="number" required min="0.01" step="0.01" value={budgetCost} onChange={event => setBudgetCost(event.target.value)} /></Field><Field label="Budget revision reason"><Input aria-label="Construction budget revision reason" required maxLength={4000} value={budgetReason} onChange={event => setBudgetReason(event.target.value)} /></Field></fieldset><Button disabled={frozen || !costSource.data}>Revise native PMS budget</Button></form></details>}
        <details className="rounded-md border p-3"><summary className="cursor-pointer font-medium">Native schedule, dependencies &amp; resources</summary><div className="mt-3"><AdvancedSchedulingPanel projectId={projectId} showDeliverySchedule={false} canManage={!!caps.data?.planning_manage} onApplied={() => { void refresh(); }} /></div></details>
        <ConstructionDependenciesPanel projectId={projectId} scope={scope} canDefine={!!caps.data?.wbs_define} onChanged={() => { void refresh(); }} />
        <details className="rounded-md border p-3"><summary className="cursor-pointer font-medium">WBS work packages</summary><div className="mt-3 grid gap-3">
          <p className="text-sm text-muted-foreground">Map approved quantities to existing PMS tasks. Cost budgets are allocations of the PMS estimated cost.</p>
          {caps.data?.wbs_define && <details className="rounded-md border p-3"><summary className="cursor-pointer text-sm font-medium">Define a native WBS task</summary><form className="mt-3 grid gap-3" aria-label="Define native Construction WBS task" onSubmit={event => { event.preventDefault(); write(`/projects/${projectId}/wbs-tasks`, { ...definition, assignee_user_ids: assignedIds, parent_task_id: definition.parent_task_id ? Number(definition.parent_task_id) : null }); }}><fieldset disabled={frozen} className="grid gap-3 md:grid-cols-2"><Field label="PMS task title"><Input aria-label="New WBS task title" required maxLength={220} value={definition.title} onChange={event => setDefinition({ ...definition, title: event.target.value })} /></Field><Field label="Task key"><Input aria-label="New WBS task key" required maxLength={30} value={definition.task_key} onChange={event => setDefinition({ ...definition, task_key: event.target.value })} /></Field><Field label="Parent PMS task (optional)"><NativeSelect aria-label="New WBS parent task" className={control} value={definition.parent_task_id} onChange={event => setDefinition({ ...definition, parent_task_id: event.target.value })}><option value="">Top-level task</option>{tasks.data?.map(task => <option key={task.id} value={task.id}>{task.task_key || task.id} · {task.title}</option>)}</NativeSelect></Field><Field label="Planned task start"><Input aria-label="New WBS task start" type="date" required value={definition.start_date} onChange={event => setDefinition({ ...definition, start_date: event.target.value })} /></Field><Field label="Planned task due"><Input aria-label="New WBS task due" type="date" min={definition.start_date || undefined} required value={definition.due_date} onChange={event => setDefinition({ ...definition, due_date: event.target.value })} /></Field><Field label="Estimated task hours"><Input aria-label="New WBS estimated hours" type="number" min="0.01" step="0.01" required value={definition.estimated_hours} onChange={event => setDefinition({ ...definition, estimated_hours: event.target.value })} /></Field><ConstructionResourceSelect projectId={projectId} scope={scope} value={assignedIds} onChange={setAssignedIds} disabled={frozen} /><Field label="Task description"><textarea aria-label="New WBS task description" className={control} maxLength={10000} value={definition.description} onChange={event => setDefinition({ ...definition, description: event.target.value })} /></Field></fieldset><Button disabled={frozen}>Create native PMS task</Button></form></details>}
          {caps.data?.planning_manage && <form aria-label="Map Construction work package" onSubmit={submitPackage} className="grid gap-3"><fieldset disabled={frozen} className="grid gap-3 md:grid-cols-2">
            <Field label="Work package title"><Input aria-label="Work package title" required maxLength={220} disabled={!!editing} value={wp.title} onChange={event => setWp({ ...wp, title: event.target.value })} /></Field>
            <Field label="Canonical PMS task"><NativeSelect aria-label="Work package PMS task" className={control} required disabled={!!editing || tasks.isFetching} value={wp.task_id} onChange={event => setWp({ ...wp, task_id: event.target.value })}><option value="">Choose existing task</option>{tasks.data?.map(task => <option key={task.id} value={task.id}>{task.task_key || task.id} · {task.title}</option>)}</NativeSelect></Field>
            <Field label="Approved BOQ or variation"><NativeSelect aria-label="Work package approved scope" className={control} required disabled={!!editing || boq.isFetching} value={wp.boq_id} onChange={event => setWp({ ...wp, boq_id: event.target.value })}><option value="">Choose approved scope</option>{boq.data?.map(row => <option key={row.id} value={row.id}>{String(row.data.code || row.id)} · {row.title}</option>)}</NativeSelect></Field>
            <Field label="Allocated quantity"><Input aria-label="Work package allocated quantity" type="number" min="0.0001" step="0.0001" required value={wp.quantity} onChange={event => setWp({ ...wp, quantity: event.target.value })} /></Field>
            <Field label="Allocated cost budget"><Input aria-label="Work package cost budget" type="number" min="0" step="0.01" required value={wp.budget_cost} onChange={event => setWp({ ...wp, budget_cost: event.target.value })} /></Field>
            <Field label="Planning notes"><Input aria-label="Work package notes" maxLength={4000} value={wp.notes} onChange={event => setWp({ ...wp, notes: event.target.value })} /></Field>
          </fieldset><div className="flex flex-wrap gap-2"><Button disabled={frozen || !tasks.data || !boq.data}>{editing ? 'Save work package allocation' : 'Map work package'}</Button>{editing && <Button type="button" variant="outline" disabled={frozen} onClick={() => { setEditing(null); setWp(emptyPackage); }}>Cancel edit</Button>}</div></form>}
          {packages.data?.map(row => <article className="grid gap-2 rounded-md border p-3 text-sm" key={row.id}><strong>{row.title}</strong><p>Task #{String(row.data.task_id)} · {String(row.data.quantity)} {String(row.data.unit)} · Cost budget {String(row.data.currency)} {String(row.data.budget_cost)}</p>{caps.data?.planning_manage && <Button variant="outline" disabled={frozen} onClick={() => { setEditing(row.id); setWp({ title: row.title, task_id: String(row.data.task_id), boq_id: String(row.data.boq_id), quantity: String(row.data.quantity), budget_cost: String(row.data.budget_cost), notes: String(row.data.notes || '') }); }}>Edit allocation</Button>}</article>)}
          {caps.data?.measurements_certify && <form className="grid gap-3 rounded-md border p-3" aria-label="Attribute earlier certified work" onSubmit={event => { event.preventDefault(); if (!attributionSource || attributionSource.created_by === actorId) return; write(`/measurements/${attributionSource.id}/work-package`, { expected_revision: attributionSource.revision, work_package_id: Number(attributionPackage), reason: attributionReason }); }}><p className="text-sm font-medium">Attribute earlier certified work</p><p className="text-xs text-muted-foreground">Independently connect earlier certified quantities to a work package. Original quantities, invoice amounts and retention remain unchanged.</p><fieldset disabled={frozen} className="grid gap-3 md:grid-cols-2"><Field label="Earlier certified measurement"><NativeSelect aria-label="Earlier certified measurement" className={control} required value={attributionMeasurement} onChange={event => { setAttributionMeasurement(event.target.value); setAttributionPackage(''); }}><option value="">Choose unattributed certified work</option>{measurements.data?.filter(row => row.data.work_package_id == null && row.created_by !== actorId).map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</NativeSelect></Field><Field label="Matching approved work package"><NativeSelect aria-label="Attribution work package" className={control} required value={attributionPackage} onChange={event => setAttributionPackage(event.target.value)}><option value="">Choose matching allocation</option>{packages.data?.filter(row => attributionSource && Number(row.data.boq_id) === attributionSource.parent_id).map(row => <option key={row.id} value={row.id}>{row.title} · {String(row.data.quantity)} {String(row.data.unit)}</option>)}</NativeSelect></Field><Field label="Independent attribution reason"><Input aria-label="Independent attribution reason" required maxLength={2000} value={attributionReason} onChange={event => setAttributionReason(event.target.value)} /></Field></fieldset><Button disabled={frozen || !attributionSource || !attributionPackage || !attributionReason.trim()}>Attribute certified work</Button></form>}
        </div></details>
        {(caps.data?.actuals_task_manage || caps.data?.actuals_cost_manage) && <details className="rounded-md border p-3"><summary className="cursor-pointer font-medium">Native task progress &amp; actual costs</summary><div className="mt-3 grid gap-3"><p className="text-sm text-muted-foreground">Task progress uses native PMS work updates. Earned value uses independently certified quantities. Actual project costs remain in the canonical PMS project.</p>
          {caps.data?.actuals_task_manage && <form className="grid gap-3 rounded-md border p-3" aria-label="Record native Construction task actuals" onSubmit={event => { event.preventDefault(); if (!actualTaskSource || !Object.prototype.hasOwnProperty.call(actualTaskSource, 'updated_at')) return; const body: Record<string, unknown> = { expected_updated_at: actualTaskSource.updated_at }; if (actualStatus) body.status = actualStatus; if (actualHours !== '') body.actual_hours = actualHours; if (actualProgress !== '') { if (actualTaskSource.progress_revision == null) return; body.progress = Number(actualProgress); body.progress_revision = actualTaskSource.progress_revision; body.progress_note = progressNote; } write(`/projects/${projectId}/task-actuals/${actualTaskSource.id}`, body); }}><fieldset disabled={frozen} className="grid gap-3 md:grid-cols-2"><Field label="Canonical PMS task"><NativeSelect aria-label="Task actuals PMS task" className={control} required value={actualTask} onChange={event => { setActualTask(event.target.value); setActualStatus(''); setActualHours(''); setActualProgress(''); setProgressNote(''); }}><option value="">Choose current native task</option>{tasks.data?.map(task => <option key={task.id} value={task.id}>{task.task_key || task.id} · {task.title}</option>)}</NativeSelect></Field><Field label="New task status (optional)"><NativeSelect aria-label="Task actual status" className={control} value={actualStatus} onChange={event => setActualStatus(event.target.value)}><option value="">Keep current status</option>{['Backlog', 'To Do', 'In Progress', 'In Review', 'Blocked', 'Done', 'Completed', 'Closed'].map(status => <option key={status} value={status}>{status}</option>)}</NativeSelect></Field><Field label="Cumulative actual hours (optional)"><Input aria-label="Task cumulative actual hours" type="number" min="0" step="0.01" value={actualHours} onChange={event => setActualHours(event.target.value)} /></Field><Field label="Reported PMS progress (%) (optional)"><Input aria-label="Task reported progress" type="number" min="0" max="100" step="1" disabled={!actualTaskSource || actualTaskSource.progress_revision == null || actualTaskSource.progress_mode === 'checklist'} value={actualProgress} onChange={event => setActualProgress(event.target.value)} /></Field>{actualProgress !== '' && <Field label="Native progress update note"><Input aria-label="Task progress update note" required maxLength={4000} value={progressNote} onChange={event => setProgressNote(event.target.value)} /></Field>}</fieldset>{actualTaskSource && <p className="text-xs text-muted-foreground">Current status: {actualTaskSource.status || 'Unavailable'} · Hours: {actualTaskSource.actual_hours ?? 'Not recorded'} · PMS progress: {actualTaskSource.progress_percent ?? 'Unavailable'}%{actualTaskSource.progress_mode === 'checklist' ? ' · Checklist-driven progress is maintained by the native PMS checklist.' : ''}</p>}<Button disabled={frozen || !actualTaskSource || !Object.prototype.hasOwnProperty.call(actualTaskSource, 'updated_at') || (!actualStatus && actualHours === '' && actualProgress === '') || (actualProgress !== '' && !progressNote.trim())}>Save native task actuals</Button></form>}
          {caps.data?.actuals_cost_manage && <form className="grid gap-3 rounded-md border p-3" aria-label="Record canonical Construction actual cost" onSubmit={event => { event.preventDefault(); if (!costSource.data) return; write(`/projects/${projectId}/cost-actuals`, { expected_actual_cost: costSource.data.actual_cost, cumulative_actual_cost: actualCost, currency: costSource.data.currency, as_of: costDate, reason: costReason }); }}><p className="text-sm">Current canonical actual cost: {costSource.data ? `${costSource.data.currency} ${costSource.data.actual_cost ?? 'Not recorded'}` : 'Loading cost source…'}</p><fieldset disabled={frozen || !costSource.data} className="grid gap-3 md:grid-cols-2"><Field label="Cumulative actual cost"><Input aria-label="Cumulative project actual cost" type="number" min="0" step="0.01" required value={actualCost} onChange={event => setActualCost(event.target.value)} /></Field><Field label="Cost actuals as of"><Input aria-label="Project cost actuals as of" type="date" required max={new Date().toLocaleDateString('en-CA')} value={costDate} onChange={event => setCostDate(event.target.value)} /></Field><Field label="Cost update or correction reason"><Input aria-label="Project actual cost reason" required maxLength={2000} value={costReason} onChange={event => setCostReason(event.target.value)} /></Field></fieldset><Button disabled={frozen || !costSource.data || !costReason.trim()}>Save canonical project actual cost</Button></form>}
        </div></details>}
        <details className="rounded-md border p-3"><summary className="cursor-pointer font-medium">Approved cost baseline &amp; performance</summary><div className="mt-3 grid gap-3">
          {caps.data?.planning_manage && <form className="grid gap-3" aria-label="Prepare Construction cost baseline" onSubmit={event => { event.preventDefault(); write('/planning-baselines', { project_id: projectId, title: baselineTitle, native_baseline_id: nativeBaseline }); }}><fieldset disabled={frozen} className="grid gap-3 md:grid-cols-2"><Field label="Cost baseline title"><Input aria-label="Cost baseline title" required maxLength={220} value={baselineTitle} onChange={event => setBaselineTitle(event.target.value)} /></Field><Field label="Native schedule baseline"><NativeSelect aria-label="Native schedule baseline" className={control} required value={nativeBaseline} onChange={event => setNativeBaseline(event.target.value)}><option value="">Choose captured native baseline</option>{nativeBaselines.data?.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</NativeSelect></Field></fieldset><div className="flex flex-wrap gap-2"><Button disabled={frozen || !nativeBaseline}>Prepare cost baseline</Button><Button type="button" variant="outline" disabled={busy} onClick={() => void nativeBaselines.refetch()}>Refresh native baselines</Button></div></form>}
          {baselines.data?.map(row => { const native = row.data.native_baseline as { author_id?: number } | undefined; return <article key={row.id} className="grid gap-2 rounded-md border p-3 text-sm"><strong>{row.title} · {row.status}</strong>{row.status === 'draft' && caps.data?.planning_approve && row.created_by !== actorId && native?.author_id !== actorId && <><Input aria-label={`Baseline review reason ${row.id}`} placeholder="Review reason (required for rejection)" value={reasons[row.id] || ''} maxLength={2000} onChange={event => setReasons({ ...reasons, [row.id]: event.target.value })} /><div className="flex flex-wrap gap-2"><Button variant="outline" disabled={frozen} onClick={() => review(row, true, 'approved')}>Approve cost baseline</Button><Button variant="outline" disabled={frozen || !reasons[row.id]?.trim()} onClick={() => review(row, true, 'rejected')}>Reject cost baseline</Button></div></>}</article>; })}
          <form className="grid gap-3" aria-label="Construction performance report" onSubmit={event => { event.preventDefault(); setPerformanceRequest({ baseline: selectedBaseline, date: asOf }); }}><fieldset disabled={busy} className="grid gap-3 md:grid-cols-2"><Field label="Independently approved cost baseline"><NativeSelect aria-label="Performance cost baseline" className={control} required value={selectedBaseline} onChange={event => { setSelectedBaseline(event.target.value); setPerformanceRequest(null); }}><option value="">Choose approved baseline</option>{baselines.data?.filter(row => row.status === 'approved').map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</NativeSelect></Field><Field label="Performance as of"><Input aria-label="Performance as of" type="date" required value={asOf} onChange={event => { setAsOf(event.target.value); setPerformanceRequest(null); }} /></Field></fieldset><div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy || !selectedBaseline}>Load project performance</Button>{caps.data?.reports && ['json', 'csv'].map(format => <Button key={format} type="button" variant="outline" disabled={busy || !selectedBaseline || !asOf} onClick={() => void download(`${ROOT}/projects/${projectId}/client-report`, `construction-client-report-${projectId}.${format}`, { baseline_id: selectedBaseline, as_of: asOf, format })}>Download client report {format.toUpperCase()}</Button>)}</div></form>
          {performance.isFetching && <p role="status">Loading certified project performance…</p>}{performance.isError && <div role="alert" className="text-sm text-destructive">{dealError(performance.error)} <Button variant="outline" onClick={() => void performance.refetch()}>Retry performance</Button></div>}
          {metrics && <div className="grid gap-3 rounded-md border p-3"><dl className="grid grid-cols-2 gap-3 md:grid-cols-4">{['BAC', 'PV', 'EV', 'AC', 'CPI', 'SPI', 'CV', 'SV', 'EAC', 'ETC', 'VAC', 'physical_progress_percent', 'forecast_completion', 'workforce_days'].map(key => <div key={key}><dt className="text-xs text-muted-foreground">{key.replace(/_/g, ' ')}</dt><dd className="text-sm font-medium">{metrics[key] == null ? 'Unavailable' : String(metrics[key])}</dd></div>)}</dl><p className="text-xs text-muted-foreground">{String(metrics.actual_cost_source || '')}</p>{!!metrics.cost_unavailable_reason && <p className="text-xs text-muted-foreground">{String(metrics.cost_unavailable_reason)}</p>}<p className="text-xs text-muted-foreground">{String(metrics.forecast_basis || '')}</p><PerformanceDetails data={metrics} /></div>}
        </div></details>
        <details className="rounded-md border p-3"><summary className="cursor-pointer font-medium">Payment certificates &amp; handover</summary><div className="mt-3 grid gap-3">
          {caps.data?.certificate_prepare && <form className="grid gap-3" aria-label="Prepare Construction payment certificate" onSubmit={event => { event.preventDefault(); write('/payment-certificates', { title: certificateTitle, measurement_id: Number(measurement) }); }}><fieldset disabled={frozen} className="grid gap-3 md:grid-cols-2"><Field label="Payment certificate title"><Input aria-label="Payment certificate title" required maxLength={220} value={certificateTitle} onChange={event => setCertificateTitle(event.target.value)} /></Field><Field label="Certified and invoiced measurement"><NativeSelect aria-label="Payment certificate measurement" className={control} required value={measurement} onChange={event => setMeasurement(event.target.value)}><option value="">Choose certified measurement</option>{measurements.data?.filter(row => !!row.invoice_id).map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</NativeSelect></Field></fieldset><Button disabled={frozen || !measurement}>Prepare payment certificate</Button></form>}
          {caps.data?.handover_prepare && <form className="grid gap-3 rounded-md border p-3" aria-label="Prepare Construction handover" onSubmit={event => { event.preventDefault(); const data = { checklist, file_ids: fileIds, task_ids: taskIds, blockers }; const row = deliveries.data?.find(item => item.id === handoverEdit); if (row) write(`/handovers/${row.id}`, { ...data, expected_revision: row.revision }, 'put', false); else write('/handovers', { ...data, title: handoverTitle, project_id: projectId }); }}><fieldset disabled={frozen} className="grid gap-3"><Field label="Handover title"><Input aria-label="Handover title" required disabled={!!handoverEdit} maxLength={220} value={handoverTitle} onChange={event => setHandoverTitle(event.target.value)} /></Field><fieldset className="grid gap-2"><legend className="text-sm font-medium">Completion checklist</legend>{checklist.map((item, index) => <label key={index} className="flex items-start gap-2 text-sm"><input type="checkbox" checked={item.complete} onChange={event => setChecklist(checklist.map((value, position) => position === index ? { ...value, complete: event.target.checked } : value))} />{item.label}</label>)}<div className="flex flex-wrap gap-2"><Input aria-label="New handover checklist item" maxLength={500} value={newCheck} onChange={event => setNewCheck(event.target.value)} /><Button type="button" variant="outline" disabled={!newCheck.trim() || checklist.length >= 100} onClick={() => { setChecklist([...checklist, { label: newCheck.trim(), complete: false }]); setNewCheck(''); }}>Add checklist item</Button></div></fieldset><Field label="Outstanding blockers"><Input aria-label="Handover blockers" maxLength={4000} value={blockers} onChange={event => setBlockers(event.target.value)} /></Field><fieldset className="grid gap-2"><legend className="text-sm font-medium">Supporting PMS documents</legend>{files.data?.map(file => <label key={file.id} className="flex gap-2 text-sm"><input type="checkbox" checked={fileIds.includes(file.id)} onChange={event => setFileIds(choose(fileIds, file.id, event.target.checked))} />{file.original_name}</label>)}<Link className="text-sm underline" to={`/pms/files?constructionProject=${projectId}`}>Open native PMS Files</Link></fieldset><fieldset className="grid gap-2"><legend className="text-sm font-medium">PMS tasks for handover</legend>{tasks.data?.map(task => <label key={task.id} className="flex gap-2 text-sm"><input type="checkbox" checked={taskIds.includes(task.id)} onChange={event => setTaskIds(choose(taskIds, task.id, event.target.checked))} />{task.title}</label>)}</fieldset></fieldset><div className="flex flex-wrap gap-2"><Button disabled={frozen || !fileIds.length || !checklist.length}>{handoverEdit ? 'Save draft handover' : 'Prepare handover'}</Button>{handoverEdit && <Button type="button" variant="outline" disabled={frozen} onClick={() => { setHandoverEdit(null); setHandoverTitle(''); }}>Cancel handover edit</Button>}</div></form>}
          {deliveries.data?.map(row => <article key={row.id} className="grid gap-2 rounded-md border p-3 text-sm"><strong>{row.title} · {row.status}</strong><p>{row.kind === 'payment_certificate' ? 'Payment certificate' : 'Handover evidence'}</p><DeliveryEvidence row={row} />{row.kind === 'handover' && row.status === 'draft' && caps.data?.handover_prepare && <Button variant="outline" disabled={frozen} onClick={() => { setHandoverEdit(row.id); setHandoverTitle(row.title); setChecklist((row.data.checklist as Checklist[]) || []); setFileIds((row.data.file_ids as number[]) || []); setTaskIds((row.data.task_ids as number[]) || []); setBlockers(String(row.data.blockers || '')); }}>Revise draft handover</Button>}{row.status === 'draft' && caps.data?.delivery_approve && row.created_by !== actorId && <><Input aria-label={`Delivery review reason ${row.id}`} placeholder="Review reason (required for rejection)" value={reasons[row.id] || ''} maxLength={2000} onChange={event => setReasons({ ...reasons, [row.id]: event.target.value })} /><div className="flex flex-wrap gap-2"><Button variant="outline" disabled={frozen} onClick={() => review(row, false, 'approved')}>Approve {row.kind === 'handover' ? 'handover' : 'payment certificate'}</Button><Button variant="outline" disabled={frozen || !reasons[row.id]?.trim()} onClick={() => review(row, false, 'rejected')}>Reject {row.kind === 'handover' ? 'handover' : 'payment certificate'}</Button></div></>}{row.status === 'approved' && (row.kind === 'handover' || financialDocuments) && ['json', 'csv'].map(format => <Button key={format} variant="outline" disabled={busy} onClick={() => void download(`${ROOT}/delivery/${row.id}/export`, `construction-${row.kind}-${row.id}.${format}`, { format })}>Download {row.kind === 'handover' ? 'handover' : 'certificate'} {format.toUpperCase()}</Button>)}</article>)}
        </div></details>
      </>}
    </div>}
  </details>;
}
