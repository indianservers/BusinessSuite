import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { NativeSelect } from '@/components/ui/native-select';

export type EvidenceSource = { id: string; tool: string; record_id: number; label: string; href: string; retrieved_at: string };
type BriefItem = { module: string; title: string; reasons: string[]; due_date: string | null; source: EvidenceSource; project_id: number | null; client_id: number | null };
type Brief = { today: string; generated_at: string; priorities: BriefItem[]; delivery_risks: BriefItem[]; coverage: { tool: string; record_id?: number; status: string; sampled?: number; limited?: boolean }[]; limited: boolean; note: string };

export function EvidenceLinks({ sources }: { sources: EvidenceSource[] }) {
  return <ul className="space-y-2 text-sm">{sources.map(source => <li key={source.id}>
    <Link className="underline" to={source.href}>{source.label}</Link>
    <span className="ml-2 text-xs text-muted-foreground">{source.tool} #{source.record_id} · retrieved {new Date(source.retrieved_at).toLocaleString()}</span>
  </li>)}</ul>;
}

export default function DailyBriefing({ workspace, project, onDraft }: { workspace: string; project: string; onDraft: (text: string, module: string) => void }) {
  const [module, setModule] = useState('');
  const [mine, setMine] = useState(true);
  const [horizon, setHorizon] = useState('7');
  const [revision, setRevision] = useState(0);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    const reset = () => { setBrief(null); setRevision(value => value + 1); };
    window.addEventListener('suite:organization-changed', reset);
    window.addEventListener('suite:branch-changed', reset);
    return () => { window.removeEventListener('suite:organization-changed', reset); window.removeEventListener('suite:branch-changed', reset); };
  }, []);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setBrief(null); setError(''); setLoading(true);
    api.get<Brief>('/ai-operator/suite/briefing', { signal: controller.signal, params: {
      workspace_id: workspace || undefined, project_id: (!module || module === 'PMS') ? project || undefined : undefined,
      module: module || undefined, mine, horizon_days: Number(horizon), timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    } }).then(response => { if (active) setBrief(response.data); }).catch(() => {
      if (active) setError('The briefing could not load. Check access and refresh.');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [workspace, project, module, mine, horizon, revision]);
  const item = (row: BriefItem) => <li key={row.source.id} className="space-y-2 border-b pb-3 last:border-0">
    <div className="flex flex-wrap justify-between gap-2"><Link className="text-sm font-medium underline" to={row.source.href}>{row.title}</Link><span className="text-xs text-muted-foreground">{row.module} · {row.due_date || 'No deadline'}</span></div>
    <p className="text-xs">{row.reasons.join(' · ')}</p>
    <p className="text-xs text-muted-foreground">{row.source.tool} #{row.source.record_id}{row.client_id ? ` · linked PMS client #${row.client_id}` : ''}</p>
  </li>;
  return <section className="space-y-4 rounded-xl border bg-card p-5" aria-label="Daily priorities and delivery risk">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">Daily priorities & delivery risk</h2><p className="text-xs text-muted-foreground">Live native records · local analysis · no model request</p></div><Button variant="outline" disabled={loading} onClick={() => setRevision(value => value + 1)}>Refresh briefing</Button></div>
    <div className="flex flex-wrap items-center gap-4 text-sm">
      <label>Module <NativeSelect aria-label="Briefing module" value={module} onChange={event => setModule(event.target.value)}><option value="">CRM, HRMS & PMS</option><option>CRM</option><option>HRMS</option><option>PMS</option></NativeSelect></label>
      <label>Horizon <NativeSelect aria-label="Briefing horizon" value={horizon} onChange={event => setHorizon(event.target.value)}><option value="7">7 days</option><option value="14">14 days</option><option value="30">30 days</option></NativeSelect></label>
      <label className="flex items-center gap-2"><input type="checkbox" checked={mine} onChange={event => setMine(event.target.checked)} />My task priorities</label>
    </div>
    {loading && <p role="status" className="text-sm">Reading authorized sources…</p>}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {brief && <>
      <p className="text-xs text-muted-foreground">{brief.today} · retrieved {new Date(brief.generated_at).toLocaleString()}. {brief.limited ? 'Coverage is partial; review source status below.' : 'Results cover the sampled sources.'}</p>
      <div className="grid gap-6 lg:grid-cols-2"><div><h3 className="mb-3 font-medium">{mine ? 'My priorities' : 'Visible priorities'}</h3>{brief.priorities.length ? <ul className="space-y-3">{brief.priorities.map(item)}</ul> : <p className="text-sm text-muted-foreground">No matching priorities in the available sample.</p>}</div>
        <div><h3 className="mb-3 font-medium">Project delivery signals</h3><p className="mb-3 text-xs text-muted-foreground">Visible project work, including other owners. Customer attribution requires an explicit project/client link.</p>{brief.delivery_risks.length ? <ul className="space-y-3">{brief.delivery_risks.map(item)}</ul> : <p className="text-sm text-muted-foreground">No overdue or blocked delivery signals in the available sample.</p>}</div></div>
      <details><summary className="cursor-pointer text-sm">Source coverage & report filters</summary><p className="mt-2 text-xs text-muted-foreground">{brief.note}</p><ul className="mt-2 space-y-1 text-xs">{brief.coverage.map((source, index) => <li key={index}>{source.tool}{source.record_id ? ` #${source.record_id}` : ''}: {source.status.replace(/_/g, ' ')}{source.sampled != null ? ` · ${source.sampled} sampled` : ''}{source.limited ? ' · bounded sample' : ''}</li>)}</ul></details>
    </>}
    <div className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => onDraft('Create CRM task: ', 'CRM')}>Prepare CRM task</Button><Button variant="outline" onClick={() => onDraft('Create PMS task: ', 'PMS')}>Prepare PMS task</Button></div>
  </section>;
}
