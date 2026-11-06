import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { CalendarDays, Clock, PhoneCall, Plus, RefreshCw, Search } from 'lucide-react';
import { api } from '@/services/api';
import { useAuthStore } from '@/store/authStore';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { PhoneInput } from '@/lib/validation/PhoneInput';
import EngagementFollowUp from './EngagementFollowUp';
import { richTextPlainText } from '@/components/rich-text/content';
type Kind = 'meetings' | 'calls';
type Row = {
    id: number;
    title?: string;
    description?: string;
    location?: string;
    start_time?: string;
    end_time?: string;
    call_time?: string;
    direction?: string;
    phone_number?: string;
    phone_number_country_code?: string;
    duration_seconds?: number;
    outcome?: string;
    notes?: string;
    status?: string;
    leadId?: number;
    contactId?: number;
    companyId?: number;
    dealId?: number;
};
type Draft = {
    title: string;
    description: string;
    location: string;
    start: string;
    end: string;
    direction: string;
    phone: string;
    code: string;
    duration: string;
    outcome: string;
    status: string;
    relatedType: string;
    relatedId: string;
};
type Permissions = Record<Kind, {
    view: boolean;
    manage: boolean;
}>;
type Conflict = {
    id: number;
    title: string;
    start: string;
    end: string;
};
const relations = [['lead', 'Lead'], ['contact', 'Contact'], ['company', 'Company'], ['deal', 'Deal']] as const;
function apiDate(value: string) { return new Date(/[zZ]$|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`); }
function localDate(value?: string) { const d = value ? apiDate(value) : new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}T${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; }
function initial(row?: Row): Draft {
    const relation = relations.find(([key]) => row?.[`${key}Id` as keyof Row]);
    return { title: row?.title || '', description: row?.description || row?.notes || '', location: row?.location || '', start: localDate(row?.start_time || row?.call_time), end: row?.end_time ? localDate(row.end_time) : localDate(new Date(Date.now() + 3600000).toISOString()), direction: row?.direction || 'Outbound', phone: row?.phone_number || '', code: row?.phone_number_country_code || '+91', duration: String(row?.duration_seconds ?? 0), outcome: row?.outcome || '', status: row?.status || 'Scheduled', relatedType: relation?.[0] || '', relatedId: relation ? String(row?.[`${relation[0]}Id` as keyof Row]) : '' };
}
function errorText(error: unknown) { const detail = (error as {
    response?: {
        data?: {
            detail?: unknown;
        };
    };
})?.response?.data?.detail; return typeof detail === 'string' ? detail : 'The request failed. Your entries are retained; please try again.'; }
function display(value?: string) { return value ? apiDate(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : 'Not scheduled'; }
export default function EngagementWorkspace({ kind }: {
    kind: Kind;
}) {
    const user = useAuthStore(s => s.user);
    const scope = `${user?.id}:${user?.access?.companyId}`;
    const [followUp, setFollowUp] = useState<Row | null>(null);
    const [permissions, setPermissions] = useState<Permissions>();
    const [rows, setRows] = useState<Row[]>([]), [total, setTotal] = useState(0), [pages, setPages] = useState(0);
    const [search, setSearch] = useState(''), [view, setView] = useState('all'), [status, setStatus] = useState('all'), [mine, setMine] = useState(false), [page, setPage] = useState(1), [revision, setRevision] = useState(0);
    const [loading, setLoading] = useState(true), [error, setError] = useState(''), [notice, setNotice] = useState('');
    const [editing, setEditing] = useState<Row | 'new' | null>(null), [draft, setDraft] = useState<Draft>(initial());
    const [saving, setSaving] = useState(false), [formError, setFormError] = useState('');
    const savingRef = useRef(false);
    const [conflicts, setConflicts] = useState<Conflict[]>([]), [conflictTotal, setConflictTotal] = useState(0), [checking, setChecking] = useState(false), [conflictError, setConflictError] = useState('');
    const [records, setRecords] = useState<{
        id: number;
        name: string;
    }[]>([]), [recordError, setRecordError] = useState('');
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const meeting = kind === 'meetings';
    const canManage = permissions?.[kind]?.manage === true;
    useEffect(() => { setEditing(null); setFollowUp(null); setDraft(initial()); setNotice(''); setSearch(''); setView('all'); setStatus('all'); setMine(false); setPage(1); }, [scope, kind]);
    useEffect(() => { let active = true; setPermissions(undefined); api.get<Permissions>('/crm/engagements/permissions').then(r => { if (active)
        setPermissions(r.data); }).catch(() => { if (active)
        setError('Could not load activity permissions. Refresh to retry.'); }); return () => { active = false; }; }, [scope, revision]);
    useEffect(() => {
        let active = true;
        setLoading(true);
        setError('');
        setRows([]);
        api.get<{
            items: Row[];
            total: number;
            pages: number;
        }>(`/crm/${kind}`, { params: { page, per_page: 25, search, activity_view: view, timezone, status: meeting ? status : undefined, direction: meeting ? undefined : status, owner_id: mine ? user?.id : undefined, sort_by: meeting ? 'start_time' : 'call_time', sort_order: view === 'upcoming' ? 'asc' : 'desc' } })
            .then(({ data }) => { if (active) {
            setRows(data.items);
            setTotal(data.total);
            setPages(data.pages);
            if (page > Math.max(1, data.pages))
                setPage(Math.max(1, data.pages));
        } })
            .catch(e => { if (active) {
            setError(errorText(e));
            setTotal(0);
        } }).finally(() => { if (active)
            setLoading(false); });
        return () => { active = false; };
    }, [kind, search, view, status, mine, page, revision, timezone, scope, user?.id, meeting]);
    useEffect(() => {
        setConflicts([]);
        setConflictTotal(0);
        setConflictError('');
        setChecking(false);
        if (!editing || !meeting || !draft.start || !draft.end || new Date(draft.end) <= new Date(draft.start))
            return;
        const controller = new AbortController();
        setChecking(true);
        const timer = setTimeout(() => {
            api.get<{
                items: Conflict[];
                total: number;
            }>('/crm/engagements/availability', { params: { start: new Date(draft.start).toISOString(), end: new Date(draft.end).toISOString(), exclude_id: editing === 'new' ? undefined : editing.id }, signal: controller.signal })
                .then(r => { if (!controller.signal.aborted) {
                setConflicts(r.data.items);
                setConflictTotal(r.data.total);
            } })
                .catch(e => { if (!controller.signal.aborted)
                setConflictError(errorText(e)); }).finally(() => { if (!controller.signal.aborted)
                setChecking(false); });
        }, 250);
        return () => { clearTimeout(timer); controller.abort(); };
    }, [editing, meeting, draft.start, draft.end, scope]);
    useEffect(() => {
        let active = true;
        setRecords([]);
        setRecordError('');
        if (!editing || !draft.relatedType)
            return;
        const entity = draft.relatedType === 'company' ? 'companies' : `${draft.relatedType}s`;
        api.get<{
            items: Record<string, unknown>[];
        }>(`/crm/${entity}`, { params: { per_page: 100, sort_by: 'id', sort_order: 'desc' } }).then(r => { if (active)
            setRecords(r.data.items.map(row => ({ id: Number(row.id), name: String(row.fullName || row.full_name || row.name || row.title || `#${row.id}`) }))); }).catch(() => { if (active)
            setRecordError('Related records could not be loaded. Your access may be limited.'); });
        return () => { active = false; };
    }, [draft.relatedType, editing, scope]);
    function open(row?: Row) { setDraft(initial(row)); setEditing(row || 'new'); setFormError(''); }
    const field = <K extends keyof Draft>(key: K, value: Draft[K]) => { setDraft(d => ({ ...d, [key]: value })); setFormError(''); };
    async function save(e: FormEvent) {
        e.preventDefault();
        if (!editing || savingRef.current || !canManage)
            return;
        if (meeting && new Date(draft.end) <= new Date(draft.start)) {
            setFormError('Meeting end must be after its start.');
            return;
        }
        if (draft.relatedType && !draft.relatedId) {
            setFormError('Choose the related record or select no link.');
            return;
        }
        savingRef.current = true;
        setSaving(true);
        setFormError('');
        const links = Object.fromEntries(relations.map(([key]) => [`${key}_id`, editing === 'new' ? null : editing[`${key}Id` as keyof Row] ?? null]));
        const previous = editing === 'new' ? undefined : relations.find(([key]) => editing[`${key}Id` as keyof Row])?.[0];
        if (previous && previous !== draft.relatedType)
            links[`${previous}_id`] = null;
        if (draft.relatedType)
            links[`${draft.relatedType}_id`] = Number(draft.relatedId);
        const data = meeting ? { title: draft.title.trim(), description: draft.description, location: draft.location, start_time: new Date(draft.start).toISOString(), end_time: new Date(draft.end).toISOString(), status: draft.status, outcome: draft.outcome, ...links } : { direction: draft.direction, phone_number: draft.phone, phone_number_country_code: draft.code, call_time: new Date(draft.start).toISOString(), duration_seconds: Number(draft.duration), outcome: draft.outcome, notes: draft.description, ...links };
        try {
            if (editing === 'new')
                await api.post(`/crm/${kind}`, data);
            else
                await api.patch(`/crm/${kind}/${editing.id}`, data);
            setEditing(null);
            setNotice(meeting ? 'Meeting saved.' : 'Call saved.');
            setRevision(v => v + 1);
        }
        catch (e) {
            setFormError(errorText(e));
        }
        finally {
            savingRef.current = false;
            setSaving(false);
        }
    }
    return <main className="space-y-5 p-3 sm:p-6" aria-label={`CRM ${kind} workspace`}>
    <header className="flex flex-wrap items-center justify-between gap-4"><div><p className="mb-1 text-xs uppercase tracking-widest text-muted-foreground">Customer conversations</p><h1 className="flex items-center gap-2 text-2xl font-semibold">{meeting ? <CalendarDays /> : <PhoneCall />}{meeting ? 'Meetings' : 'Calls'}</h1><p className="mt-2 text-sm text-muted-foreground">{meeting ? 'Plan a purposeful conversation, check your schedule and capture the outcome.' : 'Keep the call context, duration and outcome together with the customer record.'}</p></div><button className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-primary-foreground disabled:opacity-50" disabled={!canManage} onClick={() => open()}><Plus size={16}/>{meeting ? 'Schedule meeting' : 'Log call'}</button></header>
    <nav className="flex flex-wrap gap-2 text-sm" aria-label="Conversation navigation">{[['/crm/meetings', 'Meetings'], ['/crm/calls', 'Calls'], ['/crm/tasks', 'Tasks'], ['/crm/calendar', 'Calendar'], ['/crm/activities', 'Activity history']].map(([url, label]) => <Link className="rounded-md border px-3 py-2" key={url} to={url}>{label}</Link>)}</nav>
    {notice && <p role="status" className="rounded-md border p-3 text-sm">{notice}</p>}
    {error && <p role="alert" className="rounded-md border border-destructive p-3 text-sm text-destructive">{error} <button className="underline" onClick={() => setRevision(v => v + 1)}>Retry</button></p>}
    <div className="flex flex-wrap gap-2" role="group" aria-label="Conversation period">{[['all', 'All'], ['today', 'Today'], ['upcoming', 'Upcoming'], ['past', 'Past']].map(([key, label]) => <button key={key} aria-pressed={view === key} className={`rounded-md border px-3 py-2 text-sm ${view === key ? 'bg-primary text-primary-foreground' : ''}`} onClick={() => { setView(key); setPage(1); }}>{label}</button>)}</div>
    <div className="flex flex-wrap items-center gap-3 rounded-lg border p-3"><label className="flex min-w-0 flex-[1_1_220px] items-center gap-2"><Search size={16}/><input aria-label={`Search ${kind}`} className="min-w-0 flex-1 bg-transparent p-2 outline-none" placeholder={meeting ? 'Search title, location or notes…' : 'Search number, outcome or notes…'} value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}/></label><select className="rounded border bg-background p-2 text-sm" aria-label={meeting ? 'Meeting status filter' : 'Call direction filter'} value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}><option value="all">{meeting ? 'All statuses' : 'All directions'}</option>{(meeting ? ['Scheduled', 'Completed', 'Cancelled'] : ['Inbound', 'Outbound', 'Missed']).map(v => <option key={v}>{v}</option>)}</select><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={mine} onChange={e => { setMine(e.target.checked); setPage(1); }}/>Assigned to me</label><button aria-label={`Refresh ${kind}`} className="rounded-md border p-2" onClick={() => setRevision(v => v + 1)}><RefreshCw size={17}/></button></div>
    <p className="text-xs text-muted-foreground">{loading ? 'Loading…' : `${total} matching ${kind}`} · Times shown in {timezone}</p>
    <section aria-label={`${meeting ? 'Meeting' : 'Call'} results`} className="space-y-3">{rows.map(row => <article key={row.id} className="flex flex-wrap items-start justify-between gap-4 rounded-lg border bg-card p-4"><div className="min-w-0 flex-[1_1_240px]"><h2 className="break-words font-semibold">{row.title || `${row.direction} call · ${row.phone_number}`}</h2><p className="mt-2 flex items-center gap-2 text-sm text-muted-foreground"><Clock size={14}/>{display(row.start_time || row.call_time)}{meeting && row.end_time ? ` – ${display(row.end_time)}` : ''}</p><p className="mt-2 text-sm">{meeting ? row.status : `${row.duration_seconds || 0} seconds`}{row.location ? ` · ${row.location}` : ''}{row.outcome ? ` · ${row.outcome}` : ''}</p><p className="mt-2 line-clamp-2 whitespace-pre-wrap text-sm text-muted-foreground">{richTextPlainText(row.description || row.notes || '')}</p><div className="mt-2 flex flex-wrap gap-2 text-xs">{relations.filter(([key]) => row[`${key}Id` as keyof Row]).map(([key, label]) => <Link className="underline" key={key} to={`/crm/${key === 'company' ? 'companies' : key + 's'}/${row[`${key}Id` as keyof Row]}`}>{label} #{row[`${key}Id` as keyof Row]}</Link>)}</div></div><button className="rounded-md border px-3 py-2 text-sm disabled:opacity-50" disabled={!canManage} onClick={() => open(row)}>{meeting ? 'Edit / record outcome' : 'Edit call'}</button><button className="rounded-md border px-3 py-2 text-sm disabled:opacity-50" disabled={!canManage} onClick={() => setFollowUp(row)}>Create follow-up</button></article>)}{!loading && !error && !rows.length && <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">No {kind} match this view. Change the filters or add a conversation.</p>}</section>
    <footer className="flex justify-end gap-3 text-sm"><button disabled={loading || page <= 1} onClick={() => setPage(v => v - 1)}>Previous</button><span>Page {page} of {Math.max(1, pages)}</span><button disabled={loading || page >= pages} onClick={() => setPage(v => v + 1)}>Next</button></footer>
    {followUp && <EngagementFollowUp kind={kind} identity={followUp.id} title={followUp.title || followUp.outcome || 'Customer call'} onClose={() => setFollowUp(null)} onSaved={() => { setFollowUp(null); setNotice('Follow-up task saved. Open Tasks to manage the commitment.'); }}/>}
    <Dialog open={!!editing} onOpenChange={open => { if (!open && !saving)
        setEditing(null); }}><DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-2xl"><DialogTitle>{editing === 'new' ? (meeting ? 'Schedule meeting' : 'Log call') : (meeting ? 'Edit meeting' : 'Edit call')}</DialogTitle><DialogDescription>Times use {timezone}. Saving records the conversation in CRM.</DialogDescription><form onSubmit={e => void save(e)} className="space-y-4"><fieldset disabled={saving || !canManage} className="space-y-4">
      {meeting ? <><label className="block text-sm">Meeting title<input className="mt-1 w-full rounded border bg-background p-2" required maxLength={180} value={draft.title} onChange={e => field('title', e.target.value)}/></label><label className="block text-sm">Location or meeting link<input className="mt-1 w-full rounded border bg-background p-2" maxLength={240} value={draft.location} onChange={e => field('location', e.target.value)}/></label></> : <><PhoneInput required value={draft.phone} countryCode={draft.code} onChange={value => field('phone', value)} onCountryCodeChange={value => field('code', value)}/><div className="grid grid-cols-2 gap-3"><label className="text-sm">Direction<select className="mt-1 w-full rounded border bg-background p-2" value={draft.direction} onChange={e => field('direction', e.target.value)}>{['Outbound', 'Inbound', 'Missed'].map(v => <option key={v}>{v}</option>)}</select></label><label className="text-sm">Duration (seconds)<input className="mt-1 w-full rounded border bg-background p-2" type="number" min={0} step={1} required value={draft.duration} onChange={e => field('duration', e.target.value)}/></label></div></>}
      <div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">{meeting ? 'Start time' : 'Call time'}<input className="mt-1 w-full min-w-0 rounded border bg-background p-2" type="datetime-local" required value={draft.start} onChange={e => field('start', e.target.value)}/></label>{meeting && <label className="text-sm">End time<input className="mt-1 w-full min-w-0 rounded border bg-background p-2" type="datetime-local" required min={draft.start} value={draft.end} onChange={e => field('end', e.target.value)}/></label>}</div>
      {meeting && <div className="space-y-2 rounded-md border bg-muted/30 p-3 text-sm" role="status">{checking ? 'Checking your schedule…' : conflictError ? `Availability could not be checked: ${conflictError}` : conflictTotal ? `${conflictTotal} overlapping meetings on your visible schedule. You can adjust the time or keep this slot.` : 'No overlaps found on your visible schedule.'}{conflicts.map(c => <p key={c.id}>{c.title} · {display(c.start)} – {display(c.end)}</p>)}</div>}
      <div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Link to<select className="mt-1 w-full rounded border bg-background p-2" value={draft.relatedType} onChange={e => { field('relatedType', e.target.value); field('relatedId', ''); }}><option value="">No linked record</option>{relations.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>{draft.relatedType && <label className="text-sm">Related record<select required className="mt-1 w-full rounded border bg-background p-2" value={draft.relatedId} onChange={e => field('relatedId', e.target.value)}><option value="">Choose a record</option>{draft.relatedId && !records.some(r => String(r.id) === draft.relatedId) && <option value={draft.relatedId}>Current record #{draft.relatedId}</option>}{records.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select><small>Recent 100 permitted records. {recordError}</small></label>}</div>
      {meeting && <label className="block text-sm">Meeting status<select className="mt-1 w-full rounded border bg-background p-2" value={draft.status} onChange={e => field('status', e.target.value)}>{['Scheduled', 'Completed', 'Cancelled'].map(v => <option key={v}>{v}</option>)}</select></label>}
      <label className="block text-sm">{meeting ? 'Agenda and notes' : 'Call notes'}<textarea className="mt-1 w-full rounded border bg-background p-2" rows={3} value={draft.description} onChange={e => field('description', e.target.value)}/></label><label className="block text-sm">Outcome<input className="mt-1 w-full rounded border bg-background p-2" maxLength={meeting ? 2000 : 160} placeholder="What happened and what comes next?" value={draft.outcome} onChange={e => field('outcome', e.target.value)}/></label>
    </fieldset>{formError && <p role="alert" className="text-sm text-destructive">{formError}</p>}<div className="flex justify-end gap-3"><button type="button" disabled={saving} onClick={() => setEditing(null)}>Cancel</button><button type="submit" disabled={saving || !canManage} className="rounded bg-primary px-4 py-2 text-primary-foreground">{saving ? 'Saving…' : meeting ? 'Save meeting' : 'Save call'}</button></div></form></DialogContent></Dialog>
  </main>;
}
