import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';

const ROOT = '/ai-operator/suite/operations';
const input = 'rounded border bg-background p-2 text-sm';

export default function OperationsPanel({ workspace, project }: { workspace: string; project: string }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [delivery, setDelivery] = useState<any>(null), [capacity, setCapacity] = useState<any>(null), [health, setHealth] = useState<any>(null);
  const [items, setItems] = useState<any[]>([]), [book, setBook] = useState('');
  const [routing, setRouting] = useState<any>(null), [reviewRun, setReviewRun] = useState(''), [supported, setSupported] = useState(false), [correct, setCorrect] = useState(false), [reviewed, setReviewed] = useState(false);
  const [week, setWeek] = useState(new Date().toLocaleDateString('en-CA'));
  const [person, setPerson] = useState(''), [hours, setHours] = useState('0');
  const [skills, setSkills] = useState('');
  const [trigger, setTrigger] = useState('blocked'), [expiry, setExpiry] = useState(new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 16)), [maximum, setMaximum] = useState('20');
  const generation = useRef(0);
  useEffect(() => () => { generation.current++; }, []);
  async function run(work: (epoch: number) => Promise<void>) {
    setBusy(true); setError(''); const epoch = generation.current;
    try { await work(epoch); } catch (reason: any) {
      if (epoch === generation.current) setError(typeof reason?.response?.data?.detail === 'string' ? reason.response.data.detail : 'Unable to load this view. Check access and selected project.');
    } finally { if (epoch === generation.current) setBusy(false); }
  }
  async function loadItems(epoch: number) {
    const response = await api.get('/ai-operator/workbench/items', { params: { project_id: Number(project) } });
    if (epoch === generation.current) setItems(response.data.items || []);
  }
  return <section aria-label="Business operations" className="space-y-5 rounded-lg border p-4">
    <div><h2 className="font-semibold">Business operations</h2><p className="text-sm text-muted-foreground">Live delivery links, capacity projections and bounded project playbooks. Projections make no changes.</p></div>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    <div className="flex flex-wrap gap-2">
      <Button variant="outline" disabled={busy || !project} onClick={() => void run(async epoch => {
        const response = await api.get(`${ROOT}/delivery`, { params: { workspace_id: workspace ? Number(workspace) : undefined, project_id: Number(project) } });
        if (epoch === generation.current) setDelivery(response.data);
      })}>Load customer delivery</Button>
      <Button variant="outline" disabled={busy} onClick={() => void run(async epoch => {
        const response = await api.get(`${ROOT}/health`, { params: { workspace_id: workspace ? Number(workspace) : undefined } });
        if (epoch === generation.current) setHealth(response.data);
      })}>Load assistant health</Button>
      <Button variant="outline" disabled={busy || !project} onClick={() => void run(loadItems)}>Inspect playbooks and memory</Button>
      <Button variant="outline" disabled={busy || !project} onClick={() => void run(async epoch => {
        const response = await api.get(`${ROOT}/routing`, { params: { project_id: Number(project), workspace_id: workspace ? Number(workspace) : undefined } });
        if (epoch === generation.current) setRouting(response.data);
      })}>Inspect measured routing</Button>
    </div>
    {delivery && <article className="space-y-2 rounded border p-3"><h3 className="font-medium">Customer delivery trail</h3>
      <p className="text-xs text-muted-foreground">Retrieved {delivery.retrieved_at}. Tasks: {delivery.task_coverage}; invoices: {delivery.invoice_coverage}.</p>
      <div className="flex flex-wrap gap-2">{delivery.nodes?.map((node: any) => <Link className="rounded border p-2 text-sm underline" key={`${node.kind}:${node.id}`} to={node.source.href}>{node.kind}: {node.label}{node.status && ` · ${node.status}`}</Link>)}</div>
      {delivery.edges?.map((edge: any, index: number) => <p className="text-xs" key={index}>{edge.from} → {edge.to} · {edge.basis}</p>)}
      {delivery.delivery_signals?.map((signal: any, index: number) => <p className="text-sm" key={index}>{signal.reason}: <Link className="underline" to={signal.source.href}>{signal.source.label}</Link></p>)}
      {delivery.invoice_totals?.map((total: any) => <p className="text-sm" key={total.currency}>Visible invoice face value: {total.currency} {total.amount}</p>)}
      {delivery.gaps?.map((gap: string) => <p className="text-sm" key={gap}>{gap}</p>)}
      {delivery.coverage?.map((entry: any) => <p className="text-xs text-muted-foreground" key={entry.source}>{entry.source}: {entry.status}</p>)}
      <p className="text-xs text-muted-foreground">{delivery.note}</p>
    </article>}
    <article className="space-y-3 rounded border p-3"><h3 className="font-medium">Capacity scenario</h3>
      <div className="flex flex-wrap items-end gap-2"><label className="text-sm">Week containing<input aria-label="Scenario week" className={`${input} block`} type="date" value={week} onChange={event => setWeek(event.target.value)} /></label>
        {capacity && <><label className="text-sm">Person<select aria-label="Scenario person" className={`${input} block`} value={person} onChange={event => setPerson(event.target.value)}><option value="">Baseline only</option>{capacity.items?.map((row: any) => <option key={row.user_id} value={row.user_id}>Person #{row.user_id}</option>)}</select></label><label className="text-sm">Additional hours<input aria-label="Additional scenario hours" className={`${input} block`} type="number" min="0" max="168" value={hours} onChange={event => setHours(event.target.value)} /></label></>}
        <label className="text-sm">Required skills<input aria-label="Scenario required skills" placeholder="Comma separated" className={`${input} block`} value={skills} onChange={event => setSkills(event.target.value)} /></label>
        <Button disabled={busy || !project || !week} onClick={() => void run(async epoch => {
          const response = await api.post(`${ROOT}/capacity-scenario`, { workspace_id: workspace ? Number(workspace) : undefined, project_id: Number(project), week_start: week, additional_hours: person ? { [person]: Number(hours) } : {}, required_skills: skills.split(',').map(value => value.trim()).filter(Boolean) });
          if (epoch === generation.current) setCapacity(response.data);
        })}>Preview capacity scenario</Button></div>
      {capacity && <><p className="text-sm">Projection for {capacity.week_start}; {capacity.omitted_people} people omitted by source budget.{capacity.workload_partial && ' Workload sample is partial.'}</p>{capacity.items?.map((row: any) => <p className="text-sm" key={row.user_id}>Person #{row.user_id}: visible allocation {row.allocated_hours}h + scenario {row.additional_hours}h; availability {row.available_hours === null ? 'unavailable' : `${row.available_hours}h`}; overload {row.overload_hours === null ? 'unknown' : `${row.overload_hours}h`}; {row.unscheduled_tasks} tasks missing scheduling evidence.{row.missing_skills?.length > 0 && ` Missing skill evidence: ${row.missing_skills.join(', ')}.`}</p>)}{capacity.dependency_conflicts?.map((edge: any) => <p className="text-sm" key={`${edge.source_task_id}:${edge.target_task_id}`}>Dependency date conflict: task #{edge.source_task_id} → #{edge.target_task_id}, {edge.relationship}, lag {edge.lag_days} days.</p>)}{capacity.unknown_dependencies > 0 && <p className="text-sm">{capacity.unknown_dependencies} dependencies lack dates.</p>}{capacity.assumptions?.map((text: string) => <p className="text-xs text-muted-foreground" key={text}>{text}</p>)}</>}
    </article>
    {items.length > 0 && <article className="space-y-3 rounded border p-3"><h3 className="font-medium">Inspectable project memory and playbooks</h3>
      {items.filter(item => ['memory', 'playbook', 'rule', 'policy'].includes(item.kind)).map(item => <details key={item.id} className="rounded border p-2"><summary className="text-sm">{item.kind}: {item.title} · revision {item.revision}</summary><pre className="overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(item.payload, null, 2)}</pre>{item.kind === 'rule' && item.payload.enabled && <Button variant="outline" disabled={busy} onClick={() => void run(async epoch => { await api.delete(`/ai-operator/workbench/items/${item.id}`); await loadItems(epoch); })}>Stop rule #{item.id}</Button>}</details>)}
      <p className="text-xs text-muted-foreground">A rule prepares the saved task plan for review. It pauses at expiry, run limit or an unresolved previous outcome. Administrator standing consent remains a separate setting.</p>
      <div className="flex flex-wrap gap-2"><select aria-label="Operational playbook" className={input} value={book} onChange={event => setBook(event.target.value)}><option value="">Choose saved playbook</option>{items.filter(item => item.kind === 'playbook').map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select>
        <select aria-label="Playbook trigger" className={input} value={trigger} onChange={event => setTrigger(event.target.value)}><option value="blocked">Blocked task</option><option value="overdue">Overdue task</option><option value="status_changed">Status change</option><option value="task_created">New task</option></select>
        <label className="text-sm">Expires (UTC)<input aria-label="Rule expiry UTC" className={`${input} block`} type="datetime-local" value={expiry} onChange={event => setExpiry(event.target.value)} /></label>
        <label className="text-sm">Maximum proposals<input aria-label="Rule proposal limit" className={`${input} block`} type="number" min="1" max="100" value={maximum} onChange={event => setMaximum(event.target.value)} /></label>
        <Button disabled={busy || !book || !expiry} onClick={() => void run(async epoch => {
          await api.post('/ai-operator/workbench/items', { project_id: Number(project), kind: 'rule', title: `Follow ${trigger} with playbook ${book}`, payload: { playbook_id: Number(book), trigger, enabled: true, autonomous: false, expires_at: new Date(`${expiry}:00Z`).toISOString(), max_runs: Number(maximum) } });
          await loadItems(epoch);
        })}>Enable reviewed proposals</Button></div>
    </article>}
    {health && <article className="space-y-2 rounded border p-3"><h3 className="font-medium">Assistant health</h3><p className="text-xs text-muted-foreground">{health.scope} · {health.retrieved_at}{health.partial && ' · partial sample'}</p>
      {Object.entries(health.run_counts || {}).map(([status, count]) => <p className="text-sm" key={status}>{status}: {String(count)}</p>)}
      {health.attention?.map((row: any) => <p className="text-sm" key={row.id}>Run #{row.id}: {row.status}; {row.receipt_count} receipts; {row.error_code || 'review required'}</p>)}
      {health.providers?.map((row: any) => <p className="text-sm" key={`${row.provider}:${row.model}`}>{row.provider} / {row.model}: {row.successes}/{row.calls} successful; {row.mean_duration_ms}ms average; known cost {row.known_cost} across {row.priced_calls} priced calls; quality {row.quality}.</p>)}
      <p className="text-xs text-muted-foreground">{health.note}</p>
    </article>}
    <article className="space-y-3 rounded border p-3"><h3 className="font-medium">Review an assistant outcome</h3><p className="text-xs text-muted-foreground">Rate a cloud answer or plan from this project using its request ID in Recent requests. Owner ratings guide optional measured routing; they are not independent factual verification.</p>
      <div className="flex flex-wrap items-center gap-3"><label className="text-sm">Request ID<input aria-label="Outcome request ID" type="number" min="1" className={`${input} block`} value={reviewRun} onChange={event => { setReviewRun(event.target.value); setReviewed(false); }} /></label><label className="text-sm"><input type="checkbox" checked={supported} onChange={event => setSupported(event.target.checked)} /> Claims supported by cited sources</label><label className="text-sm"><input type="checkbox" checked={correct} onChange={event => setCorrect(event.target.checked)} /> Answer or workflow correct</label><Button disabled={busy || !reviewRun || !project} onClick={() => void run(async epoch => { await api.post(`${ROOT}/reviews`, { suite_run_id: Number(reviewRun), supported, correct }); if (epoch === generation.current) setReviewed(true); })}>Record outcome review</Button>{reviewed && <span className="text-sm">Review recorded.</span>}</div>
      {routing && <><p className="text-xs text-muted-foreground">{routing.policy}</p>{routing.items?.map((row: any) => <p key={`${row.provider}:${row.model}`} className="text-sm">{row.provider} / {row.model}: {row.reviews} reviews; quality {row.review_pass_rate === null ? 'unknown' : `${Math.round(row.review_pass_rate * 100)}%`}; technical success {Math.round(row.success_rate * 100)}%; mean configured cost {row.mean_cost ?? 'unknown'}.</p>)}</>}
    </article>
  </section>;
}
