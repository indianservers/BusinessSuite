import { useRef, useState } from 'react';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { Link } from 'react-router-dom';
import { api } from '@/services/api';
import { useRecordScope } from '@/lib/record-scope';
import { useRecordScopeOwner } from '@/hooks/use-record-scope-owner';
import { catalogError } from '@/shared/catalog/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';

const base = '/srm/accounts';
const fresh = { retry: false as const, staleTime: 0, gcTime: 0, refetchOnWindowFocus: false };
type Page<T> = { items: T[]; next: number | null };
type Period = { id: number; title: string; starts_on: string; ends_on: string; due_on: string; revision: number; work_revision: number; state: string };
type Delivery = { project: { id: number; name: string; currency: string } | null; engagement_status: string;
  capabilities: { project_link: boolean; documents_view: boolean; documents_request: boolean; documents_upload: boolean;
    time_record: boolean; billing_prepare: boolean; billing_view: boolean; payments_record: boolean; invoice_issue: boolean } };
type Document = { document_key: string; title: string; due_on: string; revision: number; status: string;
  file: { file_id: number; name: string; size_bytes: number; version_number: number } | null };
type Billing = { invoice: { id: number; number: string; status: string; currency: string;
  total_amount: string; paid_amount: string; balance_amount: string } | null };

function useCommand(context: number, onDenied: () => void) {
  const owns = useRecordScopeOwner();
  const pending = useRef(false);
  const attempts = useRef(new Map<string, { fingerprint: string; key: string }>());
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [status, setStatus] = useState('');
  const config = { recordCache: false as const, headers: { 'X-Suite-Pack-Context': String(context) } };
  const check = () => { if (!owns()) throw new Error('Accounts context changed. Reopen this workspace.'); };
  async function run<T>(path: string, values: Record<string, unknown>, options: {
    keyField?: 'request_key' | 'request_id' | 'none'; form?: FormData; fingerprint?: string; message?: string;
  } = {}): Promise<T | undefined> {
    if (pending.current) return;
    check(); pending.current = true; setBusy(true); setError(''); setStatus('');
    const fingerprint = options.fingerprint ?? JSON.stringify(values), old = attempts.current.get(path);
    const attempt = old?.fingerprint === fingerprint ? old : { fingerprint, key: crypto.randomUUID() };
    attempts.current.set(path, attempt);
    const keyField = options.keyField ?? 'request_key';
    const data = keyField === 'none' ? values : { ...values, [keyField]: attempt.key };
    try {
      if (options.form) options.form.set('data', JSON.stringify(data));
      check(); const response = await api.post<T>(path, options.form ?? data, config); check();
      attempts.current.delete(path); setStatus(options.message ?? 'Saved.');
      return response.data;
    } catch (failure) {
      if (!owns()) return;
      setError(catalogError(failure));
      if (isAxiosError(failure) && failure.response?.status === 403) onDenied();
    } finally { pending.current = false; if (owns()) setBusy(false); }
  }
  return { run, busy, error, status, config, check, owns };
}

export function AccountsEngagementCreator({ context, onCreated, onDenied }: {
  context: number; onCreated: (id: number) => Promise<void>; onDenied: () => void;
}) {
  const scope = useRecordScope(), command = useCommand(context, onDenied);
  const [open, setOpen] = useState(false), [search, setSearch] = useState('');
  const [client, setClient] = useState(''), [name, setName] = useState(''), [currency, setCurrency] = useState('INR');
  const clients = useInfiniteQuery({ ...fresh, queryKey: ['accounts-client-picker', scope, context, search], enabled: open,
    initialPageParam: 0, getNextPageParam: (page: Page<{ id: number; name: string }>) => page.next ?? undefined,
    queryFn: async ({ signal, pageParam }) => {
      command.check(); const result = await api.get<Page<{ id: number; name: string }>>(base + '/clients', {
        ...command.config, signal, params: { search, after: pageParam, limit: 50 } }); command.check(); return result.data;
    } });
  return <><Button variant="outline" onClick={() => setOpen(true)}>Create engagement</Button>
    <Dialog open={open} onOpenChange={value => { if (!command.busy) setOpen(value); }}><DialogContent>
      <DialogHeader><DialogTitle>Create engagement</DialogTitle></DialogHeader>
      <p className="text-sm text-muted-foreground">Choose an existing client for this service engagement.</p>
      <form className="space-y-3" onSubmit={event => { event.preventDefault(); void command.run<{ id: number }>(base + '/engagements', {
        client_id: Number(client), name, currency }, { message: 'Engagement created.' }).then(async result => {
        if (result && command.owns()) { await onCreated(result.id); if (command.owns()) { setOpen(false); setName(''); setClient(''); } }
      }); }}><fieldset disabled={command.busy} className="space-y-3">
        <label className="grid gap-1 text-sm">Find client<Input value={search} onChange={event => setSearch(event.target.value)} maxLength={100} /></label>
        <label className="grid min-w-0 gap-1 text-sm">Engagement client<NativeSelect aria-label="Engagement client" required value={client} onChange={event => setClient(event.target.value)} className="w-full min-w-0 max-w-full"><option value="">Select client</option>{clients.data?.pages.flatMap(page => page.items).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</NativeSelect></label>
        {clients.hasNextPage && <Button type="button" variant="outline" disabled={clients.isFetchingNextPage} onClick={() => void clients.fetchNextPage()}>More clients</Button>}
        {clients.isError && <p role="alert">{catalogError(clients.error)}</p>}
        <label className="grid gap-1 text-sm">Engagement name<Input aria-label="Engagement name" required maxLength={220} value={name} onChange={event => setName(event.target.value)} /></label>
        <label className="grid gap-1 text-sm">Engagement currency<Input aria-label="Engagement currency" required pattern="[A-Z]{3}" maxLength={3} value={currency} onChange={event => setCurrency(event.target.value.toUpperCase())} /></label>
        <Button type="submit" disabled={!client || !name.trim()}>Save engagement</Button>
      </fieldset></form>
      {command.error && <p role="alert" className="text-sm text-destructive">{command.error}</p>}
    </DialogContent></Dialog>
  </>;
}

export function AccountsDeliveryActions({ context, period, onDenied }: { context: number; period: Period; onDenied: () => void }) {
  const scope = useRecordScope(), command = useCommand(context, onDenied);
  const [project, setProject] = useState(''), [task, setTask] = useState('');
  const [projectSearch, setProjectSearch] = useState(''), [taskSearch, setTaskSearch] = useState('');
  const [documentTitle, setDocumentTitle] = useState(''), [documentDue, setDocumentDue] = useState(period.due_on);
  const [file, setFile] = useState<File | null>(null), fileInput = useRef<HTMLInputElement>(null);
  const hashPending = useRef(false);
  const [hashing, setHashing] = useState(false), [fileError, setFileError] = useState('');
  const [workDate, setWorkDate] = useState(''), [minutes, setMinutes] = useState(''), [description, setDescription] = useState('');
  const [fee, setFee] = useState(''), [amount, setAmount] = useState(''), [method, setMethod] = useState('bank_transfer'), [reference, setReference] = useState('');
  const [downloadError, setDownloadError] = useState(''), [downloading, setDownloading] = useState(false);
  const path = `${base}/periods/${period.id}`;
  async function get<T>(url: string, signal?: AbortSignal, params?: Record<string, unknown>) {
    command.check(); const response = await api.get<T>(url, { ...command.config, signal, params }); command.check(); return response.data;
  }
  const delivery = useQuery({ ...fresh, queryKey: ['accounts-delivery', scope, context, period.id, period.revision],
    queryFn: ({ signal }) => get<Delivery>(path + '/delivery', signal) });
  const caps = delivery.data?.capabilities;
  const documents = useQuery({ ...fresh, queryKey: ['accounts-documents', scope, context, period.id, period.revision], enabled: !!caps?.documents_view,
    queryFn: ({ signal }) => get<{ items: Document[] }>(path + '/documents', signal) });
  const billing = useQuery({ ...fresh, queryKey: ['accounts-period-billing', scope, context, period.id, period.revision], enabled: !!caps?.billing_view,
    queryFn: ({ signal }) => get<Billing>(path + '/billing', signal) });
  const projects = useInfiniteQuery({ ...fresh, queryKey: ['accounts-project-picker', scope, context, period.id, projectSearch], enabled: !!caps?.project_link,
    initialPageParam: 0, getNextPageParam: (page: Page<{ id: number; name: string }>) => page.next ?? undefined,
    queryFn: ({ signal, pageParam }) => get<Page<{ id: number; name: string }>>(path + '/project-options', signal, { after: pageParam, limit: 50, search: projectSearch }) });
  const tasks = useInfiniteQuery({ ...fresh, queryKey: ['accounts-task-picker', scope, context, period.id, delivery.data?.project?.id, taskSearch], enabled: !!caps?.documents_upload,
    initialPageParam: 0, getNextPageParam: (page: Page<{ id: number; title: string }>) => page.next ?? undefined,
    queryFn: ({ signal, pageParam }) => get<Page<{ id: number; title: string }>>(path + '/task-options', signal, { after: pageParam, limit: 50, search: taskSearch }) });
  const queries = [delivery, documents, billing, projects, tasks];
  const denied = queries.some(query => query.isError && isAxiosError(query.error) && query.error.response?.status === 403);
  async function refresh() {
    command.check(); const next = await delivery.refetch(); command.check();
    await Promise.all([next.data?.capabilities.documents_view ? documents.refetch() : Promise.resolve(),
      next.data?.capabilities.billing_view ? billing.refetch() : Promise.resolve()]);
  }
  async function upload(document: Document) {
    if (!file || !task || command.busy || hashPending.current) return;
    hashPending.current = true; setHashing(true); setFileError('');
    const selected = file;
    try {
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await selected.arrayBuffer())))
        .map(value => value.toString(16).padStart(2, '0')).join('');
      command.check();
      const form = new FormData(); form.set('file', selected);
      const values = { expected_revision: period.revision, expected_document_revision: document.revision, task_id: Number(task) };
      const result = await command.run(path + `/documents/${document.document_key}/upload`, values, {
        form, fingerprint: JSON.stringify({ ...values, filename: selected.name, type: selected.type, size: selected.size, hash }), message: 'Document uploaded.' });
      if (result && command.owns()) { setFile(null); if (fileInput.current) fileInput.current.value = ''; await refresh(); }
    } catch (failure) { if (command.owns()) setFileError(catalogError(failure)); }
    finally { hashPending.current = false; if (command.owns()) setHashing(false); }
  }
  async function download(document: Document) {
    if (!document.file || downloading) return;
    setDownloading(true); setDownloadError('');
    try {
      command.check(); const response = await api.get(path + `/documents/${document.document_key}/download`, { ...command.config, responseType: 'blob' }); command.check();
      const url = URL.createObjectURL(response.data as Blob), link = window.document.createElement('a');
      link.href = url; link.download = document.file.name; window.document.body.appendChild(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (failure) { if (command.owns()) { setDownloadError(catalogError(failure)); if (isAxiosError(failure) && failure.response?.status === 403) onDenied(); } }
    finally { if (command.owns()) setDownloading(false); }
  }
  if (denied) return <p role="alert" className="text-sm text-destructive">Accounts delivery access changed. Reload access before continuing.</p>;
  if (delivery.isError) return <p role="alert">{catalogError(delivery.error)}</p>;
  if (!delivery.data || !caps) return <p role="status">Loading delivery actions...</p>;
  const invoice = billing.data?.invoice;
  return <div className="space-y-3">
    {command.error && <p role="alert" className="text-sm text-destructive">{command.error}</p>}
    {command.status && <p role="status" className="text-sm">{command.status}</p>}
    {delivery.data.project && <p className="text-sm">Delivery project: <Link className="text-primary hover:underline" to={`/pms/projects/${delivery.data.project.id}`}>{delivery.data.project.name}</Link></p>}
    {caps.project_link && <details open className="space-y-3"><summary className="cursor-pointer text-sm font-medium">Delivery project</summary>
      <form className="grid min-w-0 gap-3 sm:grid-cols-2" onSubmit={event => { event.preventDefault(); void command.run(path + '/project', { expected_revision: period.revision, project_id: Number(project) }, { message: 'Delivery project linked.' }).then(result => { if (result) void refresh(); }); }}>
        <label className="grid gap-1 text-sm">Find delivery project<Input maxLength={100} value={projectSearch} disabled={command.busy} onChange={event => { setProjectSearch(event.target.value); setProject(''); }} /></label>
        <label className="grid min-w-0 gap-1 text-sm">Delivery project<NativeSelect aria-label="Delivery project" required value={project} disabled={command.busy} onChange={event => setProject(event.target.value)} className="w-full min-w-0 max-w-full"><option value="">Select existing project</option>{projects.data?.pages.flatMap(page => page.items).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</NativeSelect></label>
        <div className="flex items-end"><Button variant="outline" disabled={command.busy || !project}>Link delivery project</Button></div>
        {projects.hasNextPage && <Button type="button" variant="outline" disabled={projects.isFetchingNextPage} onClick={() => void projects.fetchNextPage()}>More projects</Button>}
        {projects.isError && <p role="alert">{catalogError(projects.error)}</p>}
      </form></details>}
    {caps.documents_view && <details open className="space-y-3"><summary className="cursor-pointer text-sm font-medium">Documents</summary>
      {caps.documents_request && <form className="grid min-w-0 gap-3 sm:grid-cols-2" onSubmit={event => { event.preventDefault(); void command.run(path + '/documents', { expected_revision: period.revision, title: documentTitle, due_on: documentDue }, { message: 'Document requested.' }).then(result => { if (result) { setDocumentTitle(''); void refresh(); } }); }}>
        <label className="grid gap-1 text-sm">Document title<Input aria-label="Document title" required maxLength={200} disabled={command.busy} value={documentTitle} onChange={event => setDocumentTitle(event.target.value)} /></label>
        <label className="grid gap-1 text-sm">Document due date<Input aria-label="Document due date" required type="date" min={period.starts_on} disabled={command.busy} value={documentDue} onChange={event => setDocumentDue(event.target.value)} /></label>
        <div><Button variant="outline" disabled={command.busy || !documentTitle.trim()}>Request document</Button></div>
      </form>}
      {caps.documents_upload && <div className="grid min-w-0 gap-3 sm:grid-cols-2">
        <label className="grid gap-1 text-sm">Find delivery task<Input maxLength={100} value={taskSearch} disabled={command.busy || hashing} onChange={event => { setTaskSearch(event.target.value); setTask(''); }} /></label>
        <label className="grid min-w-0 gap-1 text-sm">Delivery task<NativeSelect aria-label="Delivery task" value={task} disabled={command.busy} onChange={event => setTask(event.target.value)} className="w-full min-w-0 max-w-full"><option value="">Select existing task</option>{tasks.data?.pages.flatMap(page => page.items).map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</NativeSelect></label>
        <label className="grid min-w-0 gap-1 text-sm">Document file<Input ref={fileInput} aria-label="Document file" type="file" disabled={command.busy || hashing} onChange={event => setFile(event.target.files?.[0] ?? null)} /></label>
        {tasks.hasNextPage && <Button variant="outline" disabled={tasks.isFetchingNextPage} onClick={() => void tasks.fetchNextPage()}>More tasks</Button>}
        {tasks.isError && <p role="alert">{catalogError(tasks.error)}</p>}
      </div>}
      {documents.isError && <p role="alert">{catalogError(documents.error)}</p>}
      {documents.data?.items.map(document => <div key={document.document_key} className="space-y-2 rounded-md border p-3 text-sm">
        <p className="break-words">{document.title} — {document.status} — Due: {document.due_on}</p>
        {document.file && <p className="break-words">{document.file.name} · version {document.file.version_number}</p>}
        <div className="flex flex-wrap gap-2">{caps.documents_upload && <Button variant="outline" disabled={command.busy || hashing || !file || !task} onClick={() => void upload(document)}>Upload document</Button>}
          {document.file && <Button variant="outline" disabled={downloading || command.busy} onClick={() => void download(document)}>Download document</Button>}</div>
      </div>)}
      {downloadError && <p role="alert" className="text-sm text-destructive">{downloadError}</p>}
      {fileError && <p role="alert" className="text-sm text-destructive">{fileError}</p>}
    </details>}
    {caps.time_record && <details open className="space-y-3"><summary className="cursor-pointer text-sm font-medium">Actual time</summary>
      <p className="text-sm text-muted-foreground">Record work already performed. Planned service time is recorded separately.</p>
      <form className="grid min-w-0 gap-3 sm:grid-cols-2" onSubmit={event => { event.preventDefault(); void command.run(path + '/time', { expected_revision: period.revision, log_date: workDate, duration_minutes: Number(minutes), description }, { message: `Recorded ${minutes} minutes` }).then(result => { if (result) { setMinutes(''); setDescription(''); void refresh(); } }); }}>
        <label className="grid gap-1 text-sm">Actual work date<Input aria-label="Actual work date" type="date" min={period.starts_on} max={period.ends_on} required disabled={command.busy} value={workDate} onChange={event => setWorkDate(event.target.value)} /></label>
        <label className="grid gap-1 text-sm">Actual minutes<Input aria-label="Actual minutes" type="number" min={1} max={1440} step={1} required disabled={command.busy} value={minutes} onChange={event => setMinutes(event.target.value)} /></label>
        <label className="grid gap-1 text-sm">Actual work description<Input aria-label="Actual work description" required maxLength={4000} disabled={command.busy} value={description} onChange={event => setDescription(event.target.value)} /></label>
        <div className="flex items-end"><Button variant="outline" disabled={command.busy}>Record actual time</Button></div>
      </form></details>}
    {(caps.billing_view || caps.billing_prepare || caps.payments_record) && <details open className="space-y-3"><summary className="cursor-pointer text-sm font-medium">Service billing</summary>
      {billing.isError && <p role="alert">{catalogError(billing.error)}</p>}
      {caps.billing_prepare && <form className="grid min-w-0 gap-3 sm:grid-cols-2" onSubmit={event => { event.preventDefault(); void command.run(path + '/invoice', { expected_revision: period.revision, expected_work_revision: period.work_revision, amount: fee }, { message: 'Service invoice created.' }).then(result => { if (result) void refresh(); }); }}>
        <label className="grid gap-1 text-sm">Service fee<Input aria-label="Service fee" type="number" step="0.01" min="0.01" required disabled={command.busy} value={fee} onChange={event => setFee(event.target.value)} /></label>
        <div className="flex items-end"><Button variant="outline" disabled={command.busy}>Create service invoice</Button></div>
      </form>}
      {invoice && <><p className="text-sm"><Link className="text-primary hover:underline" to={`/srm/invoices/${invoice.id}`}>{invoice.number}</Link> · {invoice.status}</p>
        <p className="text-sm">Outstanding: {invoice.balance_amount} {invoice.currency}</p>
        {caps.invoice_issue && <Button variant="outline" disabled={command.busy} onClick={() => void command.run(`/srm/invoices/${invoice.id}/approve`, {}, { keyField: 'none', message: 'Service invoice issued.' }).then(result => { if (result) void refresh(); })}>Issue service invoice</Button>}
        {caps.payments_record && Number(invoice.balance_amount) > 0 && !['draft', 'pending_approval', 'cancelled'].includes(invoice.status) && <form className="grid min-w-0 gap-3 sm:grid-cols-2" onSubmit={event => { event.preventDefault(); void command.run(path + '/payments', { amount, payment_method: method, reference }, { keyField: 'request_id', message: 'Collection recorded.' }).then(result => { if (result) { setAmount(''); setReference(''); void refresh(); } }); }}>
          <label className="grid gap-1 text-sm">Collection amount<Input aria-label="Collection amount" type="number" min="0.01" step="0.01" max={invoice.balance_amount} required disabled={command.busy} value={amount} onChange={event => setAmount(event.target.value)} /></label>
          <label className="grid gap-1 text-sm">Payment method<NativeSelect aria-label="Payment method" value={method} disabled={command.busy} onChange={event => setMethod(event.target.value)}><option value="bank_transfer">Bank transfer</option><option value="cash">Cash</option><option value="card">Card</option></NativeSelect></label>
          <label className="grid gap-1 text-sm">Payment reference<Input aria-label="Payment reference" maxLength={120} disabled={command.busy} value={reference} onChange={event => setReference(event.target.value)} /></label>
          <div className="flex items-end"><Button variant="outline" disabled={command.busy}>Record collection</Button></div>
        </form>}</>}
    </details>}
  </div>;
}
