import { useRef, useState } from 'react';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { api } from '@/services/api';
import { useAuthStore } from '@/store/authStore';
import { recordScope, useRecordScope } from '@/lib/record-scope';
import { useRecordScopeOwner } from '@/hooks/use-record-scope-owner';
import { selectedPackContext } from '@/lib/pack-context';
import { selectedBranch } from '@/lib/branch-context';
import { effectiveOperationalSelection } from '@/lib/effective-operational-selection';
import { securityAuthStamp } from '@/lib/security-auth-stamp';
import { catalogError } from '@/shared/catalog/api';
import { Card, CardHeader, CardContent, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import GridTable from '@/shared/data-grid/GridTable';
import { AccountsDeliveryActions, AccountsEngagementCreator } from './AccountsDeliveryActions';

type Period = { id: number; title: string; engagement_id: number; client_id: number; starts_on: string; ends_on: string; due_on: string; state: string; revision: number; work_revision: number; work_summary: string; review_reason: string; preparer_employee_id: number; reviewer_employee_id: number; approved_work_revision: number | null };
type Caps = { employee_id: number | null; engagements_manage: boolean; assignments_manage: boolean; work_prepare: boolean; work_review: boolean; work_return: boolean };
type Options = { engagements: { id: number; name: string; client_id: number; client_name: string }[]; preparers: { id: number; name: string }[]; reviewers: { id: number; name: string }[]; next: { engagements: number | null; preparers: number | null; reviewers: number | null } };
const base = '/srm/accounts';

/** Keeps the existing suite controls and verifies context before loading private work. */
export default function AccountsPeriodsPage() {
  const scope = useRecordScope();
  const [mount] = useState(() => crypto.randomUUID());
  const identity = useQuery({ queryKey: ['accounts-identity', scope, mount], retry: false, staleTime: 0, gcTime: 0, refetchOnWindowFocus: false,
    queryFn: async ({ signal }) => {
      const user = useAuthStore.getState().user, owner = recordScope(user), selector = selectedPackContext();
      const config = { recordCache: false as const, signal, headers: { 'X-Suite-Pack-Context': selector } };
      const [identity, access, operational] = await Promise.all([api.get('/auth/me', config), api.get('/access/me', config), api.get('/srm/industry/capabilities', config)]);
      if (owner !== recordScope(useAuthStore.getState().user)) throw new Error('Accounts context changed. Reload before continuing.');
      const role = typeof identity.data.role === 'string' ? identity.data.role : identity.data.role?.name || null;
      const fresh = { ...user, ...identity.data, role, primary_role: role, access: access.data };
      if (securityAuthStamp(fresh) !== securityAuthStamp(user)) throw new Error('Your access changed. Reload before continuing.');
      const selection = effectiveOperationalSelection(operational.data?.operational_scope, fresh, selectedBranch(), selector);
      if (selection.pack_key !== 'accounting_firm' || !selection.context_id) throw new Error('Select an authorized Accounts Company workspace.');
      return selection.context_id;
    } });
  if (!identity.data || identity.isError) return <Card><CardContent className="space-y-3 pt-4"><p role={identity.isError ? 'alert' : 'status'}>{identity.isError ? catalogError(identity.error) : 'Verifying Accounts access...'}</p>{identity.isError && <Button onClick={() => window.location.reload()}>Reload access</Button>}</CardContent></Card>;
  return <AccountsWorkspace key={`${scope}:${mount}`} context={identity.data} />;
}

function AccountsWorkspace({ context }: { context: number }) {
  const scope = useRecordScope(), owns = useRecordScopeOwner();
  const [mount] = useState(() => crypto.randomUUID());
  const [selected, setSelected] = useState<number | null>(null), [after, setAfter] = useState(0);
  const [engagement, setEngagement] = useState(''), [preparer, setPreparer] = useState(''), [reviewer, setReviewer] = useState('');
  const [title, setTitle] = useState(''), [starts, setStarts] = useState(''), [ends, setEnds] = useState(''), [due, setDue] = useState('');
  const [occurrences, setOccurrences] = useState('1'), [intervalMonths, setIntervalMonths] = useState('1');
  const [summary, setSummary] = useState(''), [reason, setReason] = useState('');
  const [assignedPreparer, setAssignedPreparer] = useState(''), [assignedReviewer, setAssignedReviewer] = useState('');
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [locked, setLocked] = useState(false);
  const attempts = useRef(new Map<string, { fingerprint: string; key: string }>());
  const config = { recordCache: false as const, headers: { 'X-Suite-Pack-Context': String(context) } };
  const assertOwner = () => { if (!owns()) throw new Error('Accounts context changed. Reopen this workspace.'); };
  const queryConfig = { retry: false as const, staleTime: 0, gcTime: 0, refetchOnWindowFocus: false };
  const caps = useQuery({ ...queryConfig, queryKey: ['accounts-caps', scope, context, mount], queryFn: async ({ signal }) => { assertOwner(); const response = await api.get<Caps>(base + '/capabilities', { ...config, signal }); assertOwner(); return response.data; } });
  const optionPages = useInfiniteQuery({ ...queryConfig, queryKey: ['accounts-options', scope, context, mount], enabled: !locked && !!caps.data?.engagements_manage,
    initialPageParam: { engagement_after: 0, preparer_after: 0, reviewer_after: 0 },
    getNextPageParam: (page: Options, _pages, cursor) => Object.values(page.next).every(value => value === null) ? undefined : {
      engagement_after: page.next.engagements ?? cursor.engagement_after,
      preparer_after: page.next.preparers ?? cursor.preparer_after,
      reviewer_after: page.next.reviewers ?? cursor.reviewer_after },
    queryFn: async ({ signal, pageParam }) => { assertOwner(); const response = await api.get<Options>(base + '/options', { ...config, signal, params: pageParam }); assertOwner(); return response.data; } });
  const unique = <T extends { id: number },>(items: T[]) => [...new Map(items.map(item => [item.id, item])).values()];
  const options = { ...optionPages, data: optionPages.data ? {
    engagements: unique(optionPages.data.pages.flatMap(page => page.engagements)),
    preparers: unique(optionPages.data.pages.flatMap(page => page.preparers)),
    reviewers: unique(optionPages.data.pages.flatMap(page => page.reviewers)) } : undefined };
  async function selectCreatedEngagement(id: number) {
    let result = await optionPages.refetch(); assertOwner();
    while (!result.isError && !result.data?.pages.some(page => page.engagements.some(item => item.id === id))
      && Object.values(result.data?.pages.at(-1)?.next ?? {}).some(value => value !== null)) {
      result = await optionPages.fetchNextPage(); assertOwner();
    }
    if (result.isError) { setError(catalogError(result.error)); return; }
    setEngagement(String(id));
  }
  const periods = useQuery({ ...queryConfig, queryKey: ['accounts-periods', scope, context, mount, after], enabled: !locked && !!caps.data, queryFn: async ({ signal }) => { assertOwner(); const response = await api.get<{ items: Period[]; next: number | null }>(base + '/periods', { ...config, signal, params: { after, limit: 50 } }); assertOwner(); return response.data; } });
  const current = useQuery({ ...queryConfig, queryKey: ['accounts-period', scope, context, mount, selected], enabled: !locked && !!caps.data && selected !== null, queryFn: async ({ signal }) => { assertOwner(); const response = await api.get<Period>(`${base}/periods/${selected}`, { ...config, signal }); assertOwner(); return response.data; } });
  const denied = [caps, options, periods, current].some(query => query.isError && isAxiosError(query.error) && query.error.response?.status === 403);
  async function send(path: string, payload: Record<string, unknown>, method: 'post' | 'put' = 'post') {
    if (busy || locked) return;
    const fingerprint = JSON.stringify(payload), old = attempts.current.get(path);
    const attempt = old?.fingerprint === fingerprint ? old : { fingerprint, key: crypto.randomUUID() };
    attempts.current.set(path, attempt); setBusy(true); setError('');
    try {
      assertOwner(); const response = await api[method]<Period>(base + path, { ...payload, request_key: attempt.key }, config); assertOwner();
      attempts.current.delete(path); setSelected(response.data.id); setSummary(''); setReason(''); setAssignedPreparer(''); setAssignedReviewer('');
      await Promise.all([periods.refetch(), selected === response.data.id ? current.refetch() : Promise.resolve()]);
    } catch (failure) {
      if (!owns()) return;
      setError(catalogError(failure));
      if (isAxiosError(failure) && failure.response?.status === 403) setLocked(true);
      if (isAxiosError(failure) && failure.response?.status === 409) { void current.refetch(); void periods.refetch(); }
    } finally { if (owns()) setBusy(false); }
  }
  if (locked || denied || caps.isError) return <Card><CardContent className="space-y-3 pt-4"><p role="alert">{error || catalogError(caps.error) || 'Accounts access changed.'}</p><Button onClick={() => window.location.reload()}>Reload Accounts access</Button></CardContent></Card>;
  if (!caps.data) return <p role="status">Loading Accounts actions...</p>;
  const row = current.isError || current.isFetching ? null : current.data;
  const chosen = options.data?.engagements.find(item => String(item.id) === engagement);
  return <div className="min-w-0 space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-xl font-semibold">Client service periods</h1><Button variant="outline" disabled={busy} onClick={() => { void caps.refetch(); void periods.refetch(); if (selected) void current.refetch(); }}>Refresh</Button></div>
    <p className="text-sm text-muted-foreground">Prepare and independently review client work. Client accounting books require separate company access.</p>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {caps.data.engagements_manage && <Card><CardHeader><CardTitle className="text-base">New service period</CardTitle></CardHeader><CardContent className="space-y-3">
      <div><AccountsEngagementCreator context={context} onDenied={() => setLocked(true)} onCreated={selectCreatedEngagement} /></div>
      {options.isError ? <p role="alert">{catalogError(options.error)}</p> : !options.data ? <p role="status">Loading available engagements and employees...</p> : <form className="grid min-w-0 gap-3 sm:grid-cols-2" onSubmit={event => { event.preventDefault(); if (chosen) void send('/periods', { engagement_id: chosen.id, client_id: chosen.client_id, title, starts_on: starts, ends_on: ends, due_on: due, preparer_employee_id: Number(preparer), reviewer_employee_id: Number(reviewer), occurrences: Number(occurrences), interval_months: Number(intervalMonths) }); }}>
        <label className="grid min-w-0 gap-1 text-sm">Client engagement<NativeSelect aria-label="Client engagement" required className="w-full min-w-0 max-w-full" value={engagement} onChange={event => setEngagement(event.target.value)}><option value="">Select engagement</option>{options.data.engagements.map(item => <option key={item.id} value={item.id}>{item.client_name} - {item.name}</option>)}</NativeSelect></label>
        <label className="grid gap-1 text-sm">Period title<Input required maxLength={200} value={title} onChange={event => setTitle(event.target.value)} /></label>
        <label className="grid gap-1 text-sm">Period starts<Input required type="date" value={starts} onChange={event => setStarts(event.target.value)} /></label>
        <label className="grid gap-1 text-sm">Period ends<Input required type="date" min={starts} value={ends} onChange={event => setEnds(event.target.value)} /></label>
        <label className="grid gap-1 text-sm">Due date<Input required type="date" min={starts} value={due} onChange={event => setDue(event.target.value)} /></label>
        <label className="grid min-w-0 gap-1 text-sm">Preparer<NativeSelect aria-label="Preparer" required className="w-full min-w-0 max-w-full" value={preparer} onChange={event => setPreparer(event.target.value)}><option value="">Select preparer</option>{options.data.preparers.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</NativeSelect></label>
        <label className="grid min-w-0 gap-1 text-sm">Independent reviewer<NativeSelect aria-label="Independent reviewer" required className="w-full min-w-0 max-w-full" value={reviewer} onChange={event => setReviewer(event.target.value)}><option value="">Select reviewer</option>{options.data.reviewers.filter(item => String(item.id) !== preparer).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</NativeSelect></label>
        <details className="space-y-3"><summary className="cursor-pointer text-sm font-medium">Recurring periods</summary><div className="grid min-w-0 gap-3 sm:grid-cols-2">
          <label className="grid gap-1 text-sm">Occurrences<Input aria-label="Occurrences" type="number" min={1} max={36} step={1} required value={occurrences} onChange={event => setOccurrences(event.target.value)} /></label>
          <label className="grid gap-1 text-sm">Interval months<Input aria-label="Interval months" type="number" min={1} max={12} step={1} required value={intervalMonths} onChange={event => setIntervalMonths(event.target.value)} /></label>
        </div></details>
          {options.hasNextPage && <Button type="button" variant="outline" disabled={options.isFetchingNextPage} onClick={() => void options.fetchNextPage()}>More engagements and staff</Button>}
          <div className="flex items-end"><Button type="submit" disabled={busy || !chosen || !preparer || !reviewer}>Create period</Button></div>
      </form>}
    </CardContent></Card>}
    <Card><CardHeader><CardTitle className="text-base">Service periods</CardTitle></CardHeader><CardContent className="space-y-3">
      {periods.isError ? <p role="alert">{catalogError(periods.error)}</p> : <div className="overflow-x-auto"><GridTable gridId="apps/srm/accounts/periods" className="w-full text-left text-sm"><thead><tr><th className="px-3 py-2">Period</th><th className="px-3 py-2">Dates</th><th className="px-3 py-2">Due</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Actions</th></tr></thead><tbody>{periods.data?.items.map(item => <tr key={item.id} className="border-t"><td className="px-3 py-2">{item.title}</td><td className="px-3 py-2">{item.starts_on} - {item.ends_on}</td><td className="px-3 py-2">{item.due_on}</td><td className="px-3 py-2">{item.state}</td><td className="px-3 py-2"><Button variant="outline" disabled={busy} onClick={() => { setSelected(item.id); setSummary(''); setReason(''); setAssignedPreparer(''); setAssignedReviewer(''); }}>Open period</Button></td></tr>)}</tbody></GridTable></div>}
      <div className="flex flex-wrap gap-2">{after > 0 && <Button variant="outline" onClick={() => setAfter(0)}>First page</Button>}{periods.data?.next && <Button variant="outline" onClick={() => setAfter(periods.data!.next!)}>Next page</Button>}</div>
    </CardContent></Card>
    {current.isError && <p role="alert">{catalogError(current.error)}</p>}
    {row && <Card><CardHeader><CardTitle className="break-words text-base">{row.title}</CardTitle></CardHeader><CardContent className="space-y-3">
      <p className="text-sm">Status: {row.state} | Work revision: {row.work_revision}</p><p className="whitespace-pre-wrap break-words text-sm">{row.work_summary || 'No prepared work yet.'}</p>
      {row.review_reason && <p className="whitespace-pre-wrap break-words text-sm">Review notes: {row.review_reason}</p>}
      <AccountsDeliveryActions key={row.id} context={context} period={row} onDenied={() => setLocked(true)} />
      {caps.data.assignments_manage && options.data && <div className="grid min-w-0 gap-3 sm:grid-cols-2">
        <label className="grid min-w-0 gap-1 text-sm">Replacement preparer<NativeSelect aria-label="Replacement preparer" className="w-full min-w-0 max-w-full" value={assignedPreparer} onChange={event => setAssignedPreparer(event.target.value)}><option value="">Select replacement preparer</option>{options.data.preparers.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</NativeSelect></label>
        <label className="grid min-w-0 gap-1 text-sm">Replacement reviewer<NativeSelect aria-label="Replacement reviewer" className="w-full min-w-0 max-w-full" value={assignedReviewer} onChange={event => setAssignedReviewer(event.target.value)}><option value="">Select replacement reviewer</option>{options.data.reviewers.filter(item => String(item.id) !== assignedPreparer).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</NativeSelect></label>
        <p className="text-sm text-muted-foreground">Changing assignments requires the work to be submitted and reviewed again.</p><div><Button variant="outline" disabled={busy || !assignedPreparer || !assignedReviewer} onClick={() => void send(`/periods/${row.id}/assignment`, { expected_revision: row.revision, preparer_employee_id: Number(assignedPreparer), reviewer_employee_id: Number(assignedReviewer) }, 'put')}>Change assignments</Button></div>
      </div>}
      {caps.data.work_prepare && caps.data.employee_id === row.preparer_employee_id && <><label className="grid gap-1 text-sm">Updated work summary<Input aria-label="Updated work summary" maxLength={4000} value={summary} onChange={event => setSummary(event.target.value)} /></label><div className="flex flex-wrap gap-2"><Button disabled={busy || !summary.trim()} onClick={() => void send(`/periods/${row.id}/work`, { expected_revision: row.revision, summary }, 'put')}>Save work</Button>{['draft', 'returned'].includes(row.state) && row.work_revision > 0 && <Button disabled={busy || !!summary.trim()} onClick={() => void send(`/periods/${row.id}/submit`, { expected_revision: row.revision })}>Submit for review</Button>}</div></>}
      {row.state === 'submitted' && caps.data.employee_id === row.reviewer_employee_id && (caps.data.work_review || caps.data.work_return) && <><label className="grid gap-1 text-sm">Review notes<Input aria-label="Review notes" maxLength={2000} value={reason} onChange={event => setReason(event.target.value)} /></label><div className="flex flex-wrap gap-2">{caps.data.work_review && <Button disabled={busy} onClick={() => void send(`/periods/${row.id}/approve`, { expected_revision: row.revision, expected_work_revision: row.work_revision, reason })}>Approve work</Button>}{caps.data.work_return && <Button variant="outline" disabled={busy || !reason.trim()} onClick={() => void send(`/periods/${row.id}/return`, { expected_revision: row.revision, expected_work_revision: row.work_revision, reason })}>Return for changes</Button>}</div></>}
    </CardContent></Card>}
  </div>;
}
