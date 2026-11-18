import { useEffect, useRef, useState } from 'react';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { NativeSelect } from '@/components/ui/native-select';
import { EvidenceLinks, type EvidenceSource } from './DailyBriefing';

type Step = { tool: string; record_id?: number; payload: Record<string, unknown> };
type Report = { groups: Record<string, string | number>[]; sources: EvidenceSource[]; complete: boolean; matched_records: number; scanned_records: number; date_basis: string; note: string; retrieved_at: string };
const list = (value: any): any[] => Array.isArray(value) ? value : value?.items || value?.data || [];
const inputClass = 'w-full rounded border bg-background p-2 text-sm';
const kinds = { 'crm.create_task': 'CRM task', 'pms.create_task': 'PMS task', 'pms.create_milestone': 'PMS milestone', 'hrms.request_leave': 'Leave request', 'hrms.create_ticket': 'HR helpdesk ticket', 'srm.draft_invoice': 'Invoice draft' };

export default function NativeOperations({ workspace, project, busy, onPrepare }: { workspace: string; project: string; busy: boolean; onPrepare: (summary: string, module: string, steps: Step[]) => Promise<void> }) {
  const [tab, setTab] = useState('reports');
  const [module, setModule] = useState('CRM');
  const [entity, setEntity] = useState('tasks');
  const [status, setStatus] = useState('');
  const [search, setSearch] = useState('');
  const [from, setFrom] = useState('');
  const [through, setThrough] = useState('');
  const [owner, setOwner] = useState('');
  const [reportCustomer, setReportCustomer] = useState('');
  const [group, setGroup] = useState('status');
  const [amount, setAmount] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [kind, setKind] = useState<keyof typeof kinds>('crm.create_task');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [due, setDue] = useState('');
  const [start, setStart] = useState('');
  const [priority, setPriority] = useState('Medium');
  const [reminder, setReminder] = useState('');
  const [assignee, setAssignee] = useState('');
  const [customers, setCustomers] = useState<any[]>([]);
  const [people, setPeople] = useState<any[]>([]);
  const [peopleQuery, setPeopleQuery] = useState('');
  const [members, setMembers] = useState<any[]>([]);
  const [options, setOptions] = useState<any[]>([]);
  const [option, setOption] = useState('');
  const [customer, setCustomer] = useState('');
  const [currency, setCurrency] = useState('INR');
  const [lines, setLines] = useState([{ description: '', quantity: '1', unit_price: '0', tax_amount: '0', discount_amount: '0' }]);
  const epoch = useRef(0);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const reset = () => { epoch.current++; setReport(null); setCustomers([]); setPeople([]); setPeopleQuery(''); setMembers([]); setOptions([]); setTitle(''); setDescription(''); setAssignee(''); setCustomer(''); setOwner(''); setReportCustomer(''); setError(''); setRevision(value => value + 1); };
    window.addEventListener('suite:organization-changed', reset); window.addEventListener('suite:branch-changed', reset);
    return () => { epoch.current++; window.removeEventListener('suite:organization-changed', reset); window.removeEventListener('suite:branch-changed', reset); };
  }, []);
  useEffect(() => { epoch.current++; setReport(null); setError(''); }, [workspace, project, module, entity, status, search, from, through, owner, reportCustomer, group, amount]);
  useEffect(() => {
    let active = true; setOptions([]); setOption(''); setAssignee('');
    const path = kind === 'hrms.request_leave' ? '/leave/types' : kind === 'hrms.create_ticket' ? '/helpdesk/categories' : null;
    if (path) api.get(path).then(response => { if (active) setOptions(list(response.data)); }).catch(() => { if (active) setError('Unable to load the available HR options. Check access.'); });
    return () => { active = false; };
  }, [kind, revision]);
  useEffect(() => {
    let active = true; setCustomers([]);
    api.get('/crm/companies', { params: { per_page: 50 } }).then(response => { if (active) setCustomers(list(response.data)); }).catch(() => {});
    return () => { active = false; };
  }, [workspace, revision]);
  useEffect(() => {
    let active = true; setMembers([]); setAssignee(''); setOwner('');
    if (project) api.get('/ai-operator/local-context', { params: { project_id: project } }).then(response => { if (active) setMembers(response.data.collaborators || []); }).catch(() => {});
    return () => { active = false; };
  }, [project, workspace, revision]);
  useEffect(() => {
    let active=true;setPeople([]);setOwner('');setAssignee('');const timer=setTimeout(()=>{api.get('/users/search',{params:{q:peopleQuery,limit:25}}).then(response=>{if(active)setPeople(list(response.data));}).catch(()=>{});},250);
    return()=>{active=false;clearTimeout(timer);};
  },[peopleQuery,workspace,revision]);
  const params = () => ({ entity, workspace_id: workspace || undefined, project_id: module === 'PMS' ? project || undefined : undefined,
    status: status || undefined, search: search || undefined, date_from: from || undefined, date_to: through || undefined,
    owner_id: owner || undefined, customer_id: reportCustomer || undefined,
    group_by: amount && group !== 'currency' ? `${group},currency` : group, measures: amount ? 'count,amount' : 'count', max_records: 200, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone });
  async function load(exportCsv = false) {
    const current = epoch.current; setLoading(true); setError('');
    try {
      const response = await api.get(`/ai-operator/suite/reports/${module}`, { params: { ...params(), format: exportCsv ? 'csv' : 'json' }, ...(exportCsv ? { responseType: 'blob' as const } : {}) });
      if (current !== epoch.current) return;
      if (exportCsv) {
        const url = URL.createObjectURL(new Blob([response.data], { type: 'text/csv' }));
        const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${module.toLowerCase()}-${entity}-report.csv`; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      } else setReport(response.data);
    } catch (reason: any) { if (current === epoch.current) setError(typeof reason?.response?.data?.detail === 'string' ? reason.response.data.detail : 'The report could not load. Check filters and report/export permissions.'); }
    finally { setLoading(false); }
  }
  async function prepare() {
    setError('');
    try {
      if (!title.trim() && kind !== 'srm.draft_invoice') throw new Error('Enter a title or reason.');
      let payload: Record<string, unknown>;
      if (kind === 'hrms.request_leave') {
        if (!option || !start || !due) throw new Error('Choose a leave type and date range.');
        payload = { leave_type_id: Number(option), from_date: start, to_date: due, reason: title };
      } else if (kind === 'hrms.create_ticket') {
        if (!option) throw new Error('Choose a helpdesk category.');
        payload = { subject: title, description: description || title, category_id: Number(option), priority };
      } else if (kind === 'srm.draft_invoice') {
        if (!customer || lines.some(line => !line.description.trim())) throw new Error('Choose a customer and describe every invoice line.');
        payload = { customer_id: Number(customer), currency, lines, ...(start ? { issue_date: start } : {}), ...(due ? { due_date: due } : {}) };
      } else {
        payload = { ...(kind === 'pms.create_milestone' ? { name: title } : { title }), ...(description ? { description } : {}),
          ...(kind !== 'pms.create_milestone' ? { priority } : {}), ...(due ? { due_date: kind === 'crm.create_task' ? new Date(`${due}T17:00:00`).toISOString() : due } : {}),
          ...(start && kind !== 'crm.create_task' ? { start_date: start } : {}),
          ...(kind === 'pms.create_task' ? { task_key: `AI-${crypto.randomUUID().replace(/-/g, '').slice(0, 16)}`, ...(assignee ? { assignee_user_ids: [Number(assignee)] } : {}) } : {}),
          ...(kind === 'crm.create_task' && assignee ? {owner_user_id:Number(assignee)} : {}),
          ...(kind === 'crm.create_task' && reminder ? { reminder_at: new Date(reminder).toISOString() } : {}) };
      }
      if (kind.startsWith('pms.') && !project) throw new Error('Select a project in Context first.');
      await onPrepare(`Prepare ${kinds[kind].toLowerCase()} for review`, kind.startsWith('pms.') ? 'PMS' : kind.startsWith('hrms.') ? 'HRMS' : kind.startsWith('srm.') ? 'SRM' : 'CRM',
        [{ tool: kind, ...(kind.startsWith('pms.') ? { record_id: Number(project) } : {}), payload }]);
    } catch (reason: any) { setError(reason.message || 'The action could not be prepared.'); }
  }
  return <section className="space-y-4 rounded-xl border bg-card p-5" aria-label="Native reports and reviewed actions">
    <div className="flex flex-wrap items-center gap-3"><h2 className="mr-auto text-lg font-semibold">Reports & native actions</h2><Button variant={tab === 'reports' ? 'default' : 'outline'} onClick={() => setTab('reports')}>Reports</Button><Button variant={tab === 'actions' ? 'default' : 'outline'} onClick={() => setTab('actions')}>Prepare action</Button></div>
    {(tab==='reports'&&module==='CRM'||tab==='actions'&&kind==='crm.create_task')&&<label className="block text-sm">Find people<input aria-label="Find report or task owner" className={inputClass} value={peopleQuery} onChange={event=>setPeopleQuery(event.target.value)} placeholder="Search authorized company people"/></label>}
    {tab === 'reports' ? <>
      <p className="text-xs text-muted-foreground">Deterministic calculations over authorized records. Partial coverage stays visible. CSV downloads require export permission.</p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label className="text-sm">Report module<NativeSelect aria-label="Report module" className={inputClass} value={module} onChange={event => { const value = event.target.value; setModule(value); setEntity(value === 'HRMS' ? 'leave' : value === 'SRM' ? 'invoices' : 'tasks'); setAmount(false); setGroup('status'); setOwner(''); setReportCustomer(''); }}>{['CRM', 'PMS', 'HRMS', 'SRM'].map(value => <option key={value}>{value}</option>)}</NativeSelect></label>
        <label className="text-sm">Records<NativeSelect aria-label="Report entity" className={inputClass} value={entity} onChange={event => { setEntity(event.target.value); setAmount(false); setGroup('status'); }}>{(module === 'CRM' ? ['tasks', 'deals'] : [entity]).map(value => <option key={value}>{value}</option>)}</NativeSelect></label>
        <label className="text-sm">Group by<NativeSelect aria-label="Report group" className={inputClass} value={group} onChange={event => setGroup(event.target.value)}><option value="status">Status</option>{entity === 'tasks' && <option value="priority">Priority</option>}{['deals', 'invoices'].includes(entity) && <option value="currency">Currency</option>}</NativeSelect></label>
        <label className="text-sm">Status<input aria-label="Report status" className={inputClass} value={status} onChange={event => setStatus(event.target.value)} placeholder="All statuses" /></label>
        <label className="text-sm">Search<input aria-label="Report search" className={inputClass} value={search} onChange={event => setSearch(event.target.value)} /></label>
        <label className="text-sm">From<input aria-label="Report from" type="date" className={inputClass} value={from} onChange={event => setFrom(event.target.value)} /></label>
        <label className="text-sm">Through<input aria-label="Report through" type="date" className={inputClass} value={through} onChange={event => setThrough(event.target.value)} /></label>
        {['CRM','PMS'].includes(module) && <label className="text-sm">Owner<NativeSelect aria-label="Report owner" className={inputClass} value={owner} onChange={event => setOwner(event.target.value)}><option value="">All visible owners</option>{(module==='CRM'?people:members).map(member => <option key={member.id} value={member.id}>{member.displayName || member.name || member.email}</option>)}</NativeSelect></label>}
        {['CRM', 'SRM'].includes(module) && <label className="text-sm">Customer<NativeSelect aria-label="Report customer" className={inputClass} value={reportCustomer} onChange={event => setReportCustomer(event.target.value)}><option value="">All visible customers</option>{customers.map(row => <option key={row.id} value={row.id}>{row.name || row.company_name}</option>)}</NativeSelect></label>}
      </div>
      {['deals', 'invoices'].includes(entity) && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={amount} onChange={event => setAmount(event.target.checked)} />Include amounts, grouped by currency</label>}
      <div className="flex gap-2"><Button disabled={loading || busy} onClick={() => void load()}>Run report</Button><Button variant="outline" disabled={loading || busy || !report} onClick={() => void load(true)}>Download CSV</Button></div>
      {report && <div className="space-y-3"><p className="text-sm">{report.matched_records} matching / {report.scanned_records} scanned · {report.complete ? 'Complete source scan' : 'Partial source scan'} · Date filter: {report.date_basis.replace(/_/g, ' ')}</p><p className="text-xs text-muted-foreground">{report.note}</p>{report.groups.length ? <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{Object.keys(report.groups[0]).map(key => <th className="border-b p-2" key={key}>{key.replace(/_/g, ' ')}</th>)}</tr></thead><tbody>{report.groups.map((row, index) => <tr key={index}>{Object.entries(row).map(([key, value]) => <td className="border-b p-2" key={key}>{String(value)}</td>)}</tr>)}</tbody></table></div> : <p className="text-sm">No matching records in this scan.</p>}<details><summary className="cursor-pointer text-sm">Report sources</summary><EvidenceLinks sources={report.sources} /></details></div>}
    </> : <>
      <p className="text-xs text-muted-foreground">Prepare a typed draft without a cloud request. Nothing changes until you approve the exact plan below. Existing module permissions and business approvals still apply.</p>
      <label className="block text-sm">Action<NativeSelect aria-label="Native action" className={inputClass} value={kind} disabled={busy} onChange={event => { setKind(event.target.value as keyof typeof kinds); setError(''); }}>{Object.entries(kinds).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</NativeSelect></label>
      {kind !== 'srm.draft_invoice' && <label className="block text-sm">{kind === 'hrms.request_leave' ? 'Reason' : 'Title'}<input aria-label="Action title" className={inputClass} maxLength={180} value={title} onChange={event => setTitle(event.target.value)} /></label>}
      {!['srm.draft_invoice', 'hrms.request_leave'].includes(kind) && <label className="block text-sm">Description<textarea aria-label="Action description" className={inputClass} value={description} onChange={event => setDescription(event.target.value)} /></label>}
      {kind.startsWith('hrms.') && <label className="block text-sm">{kind === 'hrms.request_leave' ? 'Leave type' : 'Category'}<NativeSelect aria-label="HR action category" className={inputClass} value={option} onChange={event => setOption(event.target.value)}><option value="">Choose an available option</option>{options.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</NativeSelect></label>}
      <div className="grid gap-3 sm:grid-cols-2">{kind !== 'crm.create_task' && kind !== 'hrms.create_ticket' && <label className="text-sm">Start / issue date<input aria-label="Action start" type="date" className={inputClass} value={start} onChange={event => setStart(event.target.value)} /></label>}{kind !== 'hrms.create_ticket' && <label className="text-sm">Due / end date<input aria-label="Action due" type="date" className={inputClass} value={due} onChange={event => setDue(event.target.value)} /></label>}</div>
      {['crm.create_task', 'pms.create_task', 'hrms.create_ticket'].includes(kind) && <label className="block text-sm">Priority<NativeSelect aria-label="Action priority" className={inputClass} value={priority} onChange={event => setPriority(event.target.value)}>{['Low', 'Medium', 'High', 'Urgent'].map(value => <option key={value}>{value}</option>)}</NativeSelect></label>}
      {kind === 'crm.create_task' && <label className="block text-sm">Reminder time<input aria-label="Action reminder" type="datetime-local" className={inputClass} value={reminder} onChange={event => setReminder(event.target.value)} /><span className="text-xs text-muted-foreground">Stores a task reminder time. Scheduled outbound delivery follows in Phase 3.</span></label>}
      {['pms.create_task','crm.create_task'].includes(kind) && <label className="block text-sm">Assignee<NativeSelect aria-label="Task assignee" className={inputClass} value={assignee} onChange={event => setAssignee(event.target.value)}><option value="">Unassigned</option>{(kind==='crm.create_task'?people:members).map(member => <option key={member.id} value={member.id}>{member.displayName || member.name || member.email}</option>)}</NativeSelect></label>}
      {kind === 'srm.draft_invoice' && <div className="space-y-3"><label className="block text-sm">Customer<NativeSelect aria-label="Invoice customer" className={inputClass} value={customer} onChange={event => setCustomer(event.target.value)}><option value="">Choose a visible customer</option>{customers.map(row => <option key={row.id} value={row.id}>{row.name || row.company_name}</option>)}</NativeSelect></label><label className="block text-sm">Currency<input aria-label="Invoice currency" className={inputClass} maxLength={3} value={currency} onChange={event => setCurrency(event.target.value.toUpperCase())} /></label>{lines.map((line, index) => <fieldset className="grid gap-3 rounded border p-3 sm:grid-cols-2" key={index}><legend className="text-sm">Invoice line {index + 1}</legend>{Object.entries(line).map(([key, value]) => <label key={key} className="text-sm">{key.replace(/_/g, ' ')}<input aria-label={`Invoice line ${index + 1} ${key}`} className={inputClass} type={key === 'description' ? 'text' : 'number'} min={key === 'quantity' ? '0.0001' : '0'} step="0.0001" value={value} onChange={event => setLines(old => old.map((row, position) => position === index ? { ...row, [key]: event.target.value } : row))} /></label>)}{lines.length > 1 && <Button variant="outline" onClick={() => setLines(old => old.filter((_, position) => position !== index))}>Remove line</Button>}</fieldset>)}<Button variant="outline" disabled={lines.length >= 50} onClick={() => setLines(old => [...old, { description: '', quantity: '1', unit_price: '0', tax_amount: '0', discount_amount: '0' }])}>Add invoice line</Button><p className="text-xs text-muted-foreground">Creates a draft only. Sending, issuance, posting and payment are separate actions.</p></div>}
      <Button disabled={busy || loading} onClick={() => void prepare()}>Preview exact action</Button>
    </>}
    {loading && <p role="status" className="text-sm">Preparing report…</p>}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
  </section>;
}
