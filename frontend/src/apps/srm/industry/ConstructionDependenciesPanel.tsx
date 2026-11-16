import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { api } from '@/services/api';
import { masterScope } from '@/shared/master-data/CompanySelect';
import { dealError } from '@/apps/crm/deals/deal-utils';

const ROOT = '/srm/industry';
const control = 'w-full rounded-md border bg-background px-3 py-2 text-sm';
type Task = { id: number; task_key?: string; title: string };
type Intent = { scope: string; project: number; body: { request_id: string; source_task_id: number; target_task_id: number; dependency_type: string; lag_days: number } };

export function ConstructionResourceSelect({ projectId, scope, value, onChange, disabled = false }: {
  projectId: number; scope: string; value: number[]; onChange: (value: number[]) => void; disabled?: boolean;
}) {
  const options = useQuery({ queryKey: ['construction-resources', scope, projectId], retry: false,
    queryFn: async ({ signal }) => (await api.get<{ items: { id: number; name: string }[] }>(
      `${ROOT}/projects/${projectId}/resource-options`, { signal })).data.items });
  return <label className="grid gap-1 text-sm"><span>Native Construction resources</span>
    <NativeSelect multiple aria-label="WBS native resources" className={control} value={value.map(String)}
      disabled={disabled || options.isFetching || options.isError}
      onChange={event => { if (scope === masterScope()) onChange(Array.from(event.target.selectedOptions, option => Number(option.value))); }}>
      {options.data?.map(resource => <option key={resource.id} value={resource.id}>{resource.name}</option>)}
    </NativeSelect><span className="text-xs text-muted-foreground">Choose existing project collaborators with their own Construction access. Leave empty for unassigned work.</span>
    {options.isError && <span role="alert" className="text-destructive">{dealError(options.error)} <Button type="button" variant="outline" onClick={() => void options.refetch()}>Retry resources</Button></span>}
  </label>;
}

function readIntent(key: string, scope: string, project: number): Intent | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(key) || 'null') as Intent | null;
    const body = value?.body;
    return value?.scope === scope && value.project === project && body && typeof body.request_id === 'string'
      && Number.isInteger(body.source_task_id) && Number.isInteger(body.target_task_id)
      && ['FS', 'SS', 'FF', 'SF'].includes(body.dependency_type) && Number.isInteger(body.lag_days) ? value : null;
  } catch { return null; }
}

export default function ConstructionDependenciesPanel({ projectId, scope, canDefine, onChanged }: {
  projectId: number; scope: string; canDefine: boolean; onChanged?: () => void;
}) {
  const cache = useQueryClient(), alive = useRef(true), writing = useRef(false);
  const [open, setOpen] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const initial = { source: '', target: '', type: 'FS', lag: '0' };
  const [form, setForm] = useState(initial), key = `construction-dependency-intent:${scope}:${projectId}`;
  const [intent, setIntent] = useState<Intent | null>(() => readIntent(key, scope, projectId)), pending = useRef(intent);
  const owns = () => alive.current && scope === masterScope();
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const tasks = useQuery({ queryKey: ['construction-planning', scope, projectId, 'dependency-task-options'],
    enabled: open && canDefine, retry: false,
    queryFn: async ({ signal }) => (await api.get<{ items: Task[] }>(`${ROOT}/projects/${projectId}/planning-tasks`, { signal })).data.items });
  function retain(value: Intent | null) {
    pending.current = value; setIntent(value);
    try { if (value) sessionStorage.setItem(key, JSON.stringify(value)); else sessionStorage.removeItem(key); } catch { /* Preserve in memory if storage is unavailable. */ }
  }
  async function send(saved: Intent) {
    if (!owns() || writing.current || !canDefine) return;
    writing.current = true; setBusy(true); setError(''); setNotice('');
    try {
      await api.post(`${ROOT}/projects/${projectId}/task-dependencies`, saved.body);
      if (!owns()) return;
      retain(null); setForm(initial); setNotice('Native PMS dependency created.');
      await cache.invalidateQueries({ queryKey: ['construction-planning', scope, projectId] });
      if (owns()) onChanged?.();
    } catch (failure) {
      if (!owns()) return;
      setError(dealError(failure));
      const status = (failure as { response?: { status?: number } }).response?.status;
      if (status && status >= 400 && status < 500) retain(null);
    } finally { writing.current = false; if (owns()) setBusy(false); }
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!owns() || !canDefine || pending.current || writing.current) return;
    const saved: Intent = { scope, project: projectId, body: { request_id: crypto.randomUUID(),
      source_task_id: Number(form.source), target_task_id: Number(form.target), dependency_type: form.type, lag_days: Number(form.lag) } };
    retain(saved); void send(saved);
  }
  if (!canDefine) return null;
  return <details className="rounded-lg border p-4" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary className="cursor-pointer font-semibold">Native task dependencies</summary>{open && <div className="mt-3 grid gap-3">
      <p className="text-sm text-muted-foreground">Link existing project tasks, then use the native schedule preview to review dates and resource capacity.</p>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}{notice && <p role="status">{notice}</p>}
      {tasks.isError && <p role="alert" className="text-sm text-destructive">{dealError(tasks.error)} <Button variant="outline" onClick={() => void tasks.refetch()}>Retry task source</Button></p>}
      {intent && <div className="grid gap-2 rounded-md border p-3 text-sm"><p>This dependency request has not been confirmed. Retry the same request before adding another link.</p><Button variant="outline" disabled={busy} onClick={() => void send(intent)}>Retry dependency request</Button></div>}
      <form onSubmit={submit} aria-label="Define native task dependency" className="grid gap-3">
        <fieldset className="grid gap-3 md:grid-cols-2" disabled={busy || !!intent || tasks.isFetching || tasks.isError}>
          <label className="grid gap-1 text-sm"><span>Predecessor task</span><NativeSelect aria-label="Dependency predecessor" className={control} required value={form.source} onChange={event => setForm({ ...form, source: event.target.value })}><option value="">Choose task</option>{tasks.data?.map(task => <option key={task.id} value={task.id}>{task.task_key || task.id} · {task.title}</option>)}</NativeSelect></label>
          <label className="grid gap-1 text-sm"><span>Successor task</span><NativeSelect aria-label="Dependency successor" className={control} required value={form.target} onChange={event => setForm({ ...form, target: event.target.value })}><option value="">Choose task</option>{tasks.data?.filter(task => String(task.id) !== form.source).map(task => <option key={task.id} value={task.id}>{task.task_key || task.id} · {task.title}</option>)}</NativeSelect></label>
          <label className="grid gap-1 text-sm"><span>Dependency type</span><NativeSelect aria-label="Dependency type" className={control} value={form.type} onChange={event => setForm({ ...form, type: event.target.value })}><option value="FS">Finish to start</option><option value="SS">Start to start</option><option value="FF">Finish to finish</option><option value="SF">Start to finish</option></NativeSelect></label>
          <label className="grid gap-1 text-sm"><span>Lag in days</span><Input aria-label="Dependency lag days" type="number" min={-365} max={365} step={1} required value={form.lag} onChange={event => setForm({ ...form, lag: event.target.value })} /></label>
        </fieldset><Button disabled={busy || !!intent || tasks.isFetching || tasks.isError || !tasks.data?.length}>Create native dependency</Button>
      </form>
    </div>}</details>;
}
