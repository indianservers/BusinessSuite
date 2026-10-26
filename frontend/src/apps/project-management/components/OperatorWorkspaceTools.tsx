import { RichTextContent } from "@/components/rich-text/RichTextContent";
import { useState } from 'react';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import type { OperatorProviderName } from '@/services/aiOperatorApi';

type SetupProposal = { id: number; status: string; plan_hash: string; result?: { project_id: number; receipts: unknown[] };
  payload: { plan: { summary: string; clarification?: string; name: string; project_key: string;
    milestones: { key: string; name: string; due_date?: string }[];
    tasks: { key: string; title: string; description?: string; estimated_hours?: number; start_date?: string; due_date?: string; parent_key?: string; milestone_key?: string; blocked_by: string[] }[] } } };
type Monitor = { id: number; project_id: number; name: string; enabled: boolean; interval_minutes: number; error_code?: string;
  findings?: { task_id: number; task_key: string; title: string; reasons: string[] }[]; checked_at?: string };

export function OperatorWorkspaceTools({ projectId, workspaceId, command, provider }: {
  projectId: number; workspaceId?: number | null; command: string; provider: OperatorProviderName;
}) {
  const [proposal, setProposal] = useState<SetupProposal | null>(null);
  const [newProject, setNewProject] = useState(true);
  const [templateId, setTemplateId] = useState('');
  const [monitors, setMonitors] = useState<Monitor[]>([]);
  const [capacity, setCapacity] = useState<{ assumptions: string; items: { user_id: number; email: string; allocated_hours: number; capacity_hours: number; overload_hours: number; unscheduled_tasks: number }[] } | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState('');
  const [entities, setEntities] = useState<{ type: string; id: number; label: string }[]>([]);
  async function action(work: () => Promise<void>) {
    setBusy(true); setError('');
    try { await work(); } catch (e: any) { setError(typeof e?.response?.data?.detail === 'string' ? e.response.data.detail : 'Request failed. Check access, provider configuration and input.'); }
    finally { setBusy(false); }
  }
  async function loadMonitors() { setMonitors((await api.get('/ai-operator/monitors', { params: { project_id: projectId } })).data.items); }
  return <details className="rounded-lg border p-4" key={projectId}>
    <summary className="cursor-pointer font-semibold">Project setup, capacity and goal monitors</summary>
    <div className="space-y-5 pt-4">
      {error && <p role="alert" className="text-destructive">{error}</p>}
      <section className="space-y-3">
        <h2 className="font-semibold">Turn a brief or meeting notes into delivery work</h2>
        <p className="text-sm">Use the Command text above as the source brief. This workflow calls the selected LLM, then shows every task and milestone for review.</p>
        <label className="block"><input type="checkbox" checked={newProject} disabled={busy} onChange={e => setNewProject(e.target.checked)} /> Create a new project in the selected project’s workspace</label>
        <label className="block">Optional template project ID<input aria-label="Operator template ID" type="number" min="1" className="ml-2 rounded border bg-background p-2" value={templateId} onChange={e => setTemplateId(e.target.value)} /></label>
        <Button disabled={busy || !projectId || command.trim().length < 3} onClick={() => void action(async () => {
          const data = (await api.post('/ai-operator/setup/preview', { brief: command, provider, request_key: crypto.randomUUID(),
            workspace_id: workspaceId || null, project_id: newProject ? null : projectId, template_id: templateId ? Number(templateId) : null }, { timeout: 65000 })).data;
          setProposal(data);
        })}>Preview project setup</Button>
        {proposal && <div className="rounded border p-3 space-y-2" aria-label="Project setup preview">
          <p>Proposal #{proposal.id} · {proposal.status}</p><h3 className="font-semibold">{proposal.payload.plan.name} · {proposal.payload.plan.project_key}</h3>
          <p>{proposal.payload.plan.summary}</p>{proposal.payload.plan.clarification && <p>{proposal.payload.plan.clarification}</p>}
          {proposal.payload.plan.milestones.map(m => <p key={m.key}>Milestone {m.key}: {m.name} · {m.due_date || 'unscheduled'}</p>)}
          <ol className="list-decimal pl-5">{proposal.payload.plan.tasks.map(t => <li key={t.key} className="py-2"><strong>{t.key}: {t.title}</strong>
            {t.description && <div className="whitespace-pre-wrap"><RichTextContent value={t.description}/></div>}
            <p className="text-sm">{t.estimated_hours ?? 'Unestimated'} hours · {t.start_date || 'unscheduled'} → {t.due_date || 'unscheduled'}
              {t.parent_key && ` · parent ${t.parent_key}`}{t.milestone_key && ` · milestone ${t.milestone_key}`}{t.blocked_by.length > 0 && ` · blocked by ${t.blocked_by.join(', ')}`}</p></li>)}</ol>
          {proposal.status === 'awaiting_approval' && <Button disabled={busy} onClick={() => void action(async () => setProposal((await api.post(`/ai-operator/proposals/${proposal.id}/approve`, { plan_hash: proposal.plan_hash })).data))}>Approve project setup</Button>}
          {proposal.result && <p>Created work in project #{proposal.result.project_id} · {proposal.result.receipts.length} receipts. Refresh the project list to open it.</p>}
        </div>}
      </section>
      <section className="space-y-3"><h2 className="font-semibold">Delivery goal monitors</h2><p className="text-sm">Checks overdue, blocked and unassigned tasks hourly. Findings are updated when they change. These checks do not call an LLM or modify tasks.</p>
        <div className="flex gap-3"><Button variant="outline" disabled={busy || !projectId} onClick={() => void action(async () => { await api.post('/ai-operator/monitors', { project_id: projectId, name: 'Delivery health', interval_minutes: 60 }); await loadMonitors(); })}>Create delivery monitor</Button>
          <Button variant="outline" disabled={busy || !projectId} onClick={() => void action(loadMonitors)}>Refresh monitors</Button></div>
        {monitors.map(m => <div className="rounded border p-3" key={m.id}><strong>{m.name}</strong> · {m.enabled ? 'active' : 'paused'} · {m.checked_at ? new Date(m.checked_at).toLocaleString() : 'waiting for worker'}
          {m.error_code && <p>{m.error_code}</p>}{m.findings?.map(f => <p key={f.task_id}>{f.task_key}: {f.title} · {f.reasons.join(', ')}</p>)}
          <Button variant="outline" disabled={busy} onClick={() => void action(async () => { await api.put(`/ai-operator/monitors/${m.id}`, { project_id: projectId, name: m.name, interval_minutes: m.interval_minutes, enabled: !m.enabled }); await loadMonitors(); })}>{m.enabled ? 'Pause' : 'Resume'} monitor</Button></div>)}
      </section>
      <section className="space-y-3"><h2 className="font-semibold">Capacity and entity lookup</h2>
        <Button variant="outline" disabled={busy || !projectId} onClick={() => void action(async () => setCapacity((await api.get('/ai-operator/capacity', { params: { project_id: projectId, week_start: new Date().toISOString().slice(0,10) } })).data))}>Check this week’s capacity</Button>
        {capacity && <div><p className="text-sm">{capacity.assumptions}</p>{capacity.items.map(p => <p key={p.user_id}>{p.email}: {p.allocated_hours} / {p.capacity_hours} hours · overload {p.overload_hours}h · {p.unscheduled_tasks} tasks need estimates or dates</p>)}</div>}
        <label className="block">Find a task key, title or collaborator email<input aria-label="Operator entity search" className="ml-2 rounded border bg-background p-2" value={query} onChange={e => setQuery(e.target.value)} /></label>
        <Button variant="outline" disabled={busy || !projectId || !query.trim()} onClick={() => void action(async () => setEntities((await api.get('/ai-operator/resolve', { params: { project_id: projectId, q: query } })).data.items))}>Find matches</Button>
        {entities.map(e => <p key={`${e.type}:${e.id}`}>{e.type} #{e.id}: {e.label}</p>)}
      </section>
    </div>
  </details>;
}
