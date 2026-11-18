import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import FieldControl, { fieldShown, type FieldDefinition } from '@/shared/custom-fields/FieldControl';
import { useAuthStore } from '@/store/authStore';
import RelatedRecords from './RelatedRecords';

type RecordRow = { id: number; values_json: Record<string, unknown> };
type Field = FieldDefinition & { id: number; module_name: string; field_api_name: string; field_label: string; field_type: string; validation_json?: { options?: { value: string }[]; places?: string[] } };
type Action = { id: number; module_name: string; label: string; active: boolean };
const controlField = (field: Field) => ({ ...field, options: { values: (field.validation_json?.options || []).map(o => o.value), ui: { places: field.validation_json?.places } } });
const computed = (field: Field) => ['formula', 'rollup', 'auto_number'].includes(field.field_type);
function message(error: unknown) {
  const err = error as { response?: { data?: { detail?: unknown } }; message?: string };
  return typeof err.response?.data?.detail === 'string' ? err.response.data.detail : err.message || 'Action failed';
}

export default function ModuleRecords({ module, label }: { module: string; label: string }) {
  const user = useAuthStore(s => s.user);
  const permissions = Object.values(user?.access?.grants || {}).filter(g => g.enabled).flatMap(g => g.permissions);
  const canEdit = Boolean(user?.is_superuser || permissions.includes('customization_manage'));
  const canExecute = canEdit || permissions.includes('customization_buttons_manage');
  const [open, setOpen] = useState(false), [editing, setEditing] = useState<RecordRow | null>(null);
  const [draft, setDraft] = useState<Record<string, unknown>>({}), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [editor, setEditor] = useState(false), [search, setSearch] = useState(''), [page, setPage] = useState(1);
  const [actionKeys, setActionKeys] = useState<Record<string, string>>({}), [notice, setNotice] = useState('');
  const records = useQuery({ queryKey: ['custom-module-records', module, search, page], enabled: open,
    queryFn: () => api.get<{ items: RecordRow[]; total: number }>(`/custom/${module}`, { params: { search, page, per_page: 20 }, recordCache: false }).then(r => r.data) });
  const fields = useQuery({ queryKey: ['custom-module-fields', module], enabled: open,
    queryFn: () => api.get<{ items: Field[] }>('/customization/fields', { recordCache: false }).then(r => r.data.items.filter(f => f.module_name === module)) });
  const actions = useQuery({ queryKey: ['custom-module-buttons', module], enabled: open,
    queryFn: () => api.get<{ items: Action[] }>('/customization/buttons').then(r => r.data.items.filter(a => a.module_name === module && a.active)) });
  const relations = useQuery({ queryKey: ['custom-module-relations', module], enabled: open,
    queryFn: () => api.get<{ items: { id: number; module_name: string; label: string; active: boolean }[] }>('/customization/related-lists').then(r => r.data.items.filter(r => r.module_name === module && r.active)) });
  function edit(row: RecordRow | null) { setEditing(row); setDraft({ ...row?.values_json }); setError(''); setEditor(true); }
  async function run(action: Action, row: RecordRow) {
    const name = `${action.id}:${row.id}`, key = actionKeys[name] || crypto.randomUUID();
    setActionKeys(keys => ({ ...keys, [name]: key })); setBusy(true); setError(''); setNotice('');
    try {
      const { data } = await api.post<{ status: string; task_id?: number; approval_id?: number; url?: string }>(`/customization/buttons/${action.id}/execute`, { record_id: row.id, request_key: key });
      if (data.url) window.open(data.url, '_blank', 'noopener,noreferrer');
      setNotice(`${action.label}: ${data.status}${data.task_id ? ` · Task #${data.task_id}` : ''}${data.approval_id ? ` · Approval #${data.approval_id}` : ''}`);
      await records.refetch();
    } catch (err) { setError(message(err)); } finally { setBusy(false); }
  }
  return <><Button size="sm" variant="outline" onClick={() => setOpen(true)}>Open records</Button>
    <Dialog open={open} onOpenChange={next => { if (!busy) setOpen(next); }}><DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto"><DialogTitle>{label} records</DialogTitle>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}{notice && <p role="status">{notice}</p>}
      {!editor ? <>
        <div className="flex flex-wrap gap-3"><Input aria-label="Search records" placeholder="Search records…" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} />{canEdit && <Button disabled={fields.isPending || fields.isError || busy} onClick={() => edit(null)}>Add record</Button>}</div>
        {(records.isError || fields.isError) && <p role="alert">Could not load records or field definitions.</p>}
        {records.isPending && <p role="status">Loading records…</p>}
        {records.data?.items.map(row => <article key={row.id} className="min-w-0 space-y-3 rounded-lg border p-4"><header className="flex justify-between"><h3 className="font-medium">Record #{row.id}</h3>{canEdit && <Button size="sm" variant="outline" disabled={busy} onClick={() => edit(row)}>Edit</Button>}</header>
          <dl className="grid gap-3 sm:grid-cols-2">{fields.data?.filter(f => fieldShown(controlField(f), 'detail')).map(f => <div key={f.id}><dt className="text-xs text-muted-foreground">{f.field_label}</dt><dd className="break-words text-sm">{Array.isArray(row.values_json[f.field_api_name]) ? (row.values_json[f.field_api_name] as unknown[]).join(', ') : String(row.values_json[f.field_api_name] ?? '—')}</dd></div>)}</dl>
          {canExecute && <div className="flex flex-wrap gap-2">{actions.data?.map(a => <Button key={a.id} variant="outline" size="sm" disabled={busy} onClick={() => void run(a, row)}>{a.label}</Button>)}</div>}
          {relations.data?.map(r => <RelatedRecords key={r.id} module={module} record={row.id} relation={r.id} label={r.label} />)}
        </article>)}
        <footer className="flex flex-wrap items-center justify-between gap-3"><span className="text-sm">{records.data?.total ?? 0} records · Page {page}</span><div className="flex gap-2"><Button variant="outline" disabled={page === 1 || busy || records.isFetching} onClick={() => setPage(p => p - 1)}>Previous</Button><Button variant="outline" disabled={page * 20 >= (records.data?.total || 0) || busy || records.isFetching} onClick={() => setPage(p => p + 1)}>Next</Button></div></footer>
      </> : <form onSubmit={async e => {
        e.preventDefault(); setBusy(true); setError('');
        try {
          const values: Record<string, unknown> = {};
          for (const f of fields.data || []) {
            if (computed(f) || f.editable === false || !fieldShown(controlField(f), editing ? 'edit' : 'create')) continue;
            const value = draft[f.field_api_name];
            if (value === undefined) continue;
            if (f.field_type === 'phone' && value && typeof value === 'object') { const pair = value as Record<string, unknown>; values[f.field_api_name] = pair.national_number; values[f.field_api_name + '_country_code'] = pair.country_code; }
            else values[f.field_api_name] = value;
          }
          if (editing) await api.put(`/custom/${module}/${editing.id}`, { values }); else await api.post(`/custom/${module}`, { values });
          await records.refetch(); setEditor(false);
        } catch (err) { setError(message(err)); } finally { setBusy(false); }
      }}><fieldset disabled={busy} className="space-y-4"><div className="grid gap-4 sm:grid-cols-2">{fields.data?.filter(f => fieldShown(controlField(f), editing ? 'edit' : 'create')).map(f => {
        const value = draft[f.field_api_name];
        return <div key={f.id} className="space-y-1"><p className="text-sm font-medium">{f.field_label}{f.required ? ' *' : ''}</p><FieldControl field={controlField(f)} value={f.field_type === 'phone' && typeof value !== 'object' ? { national_number: value || '', country_code: draft[f.field_api_name + '_country_code'] || '+91' } : value} disabled={f.editable === false || computed(f)} onChange={value => setDraft(current => ({ ...current, [f.field_api_name]: value }))} />{Boolean(f.help_text) && <p className="text-xs text-muted-foreground">{String(f.help_text)}</p>}</div>;
      })}</div><footer className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setEditor(false)}>Cancel</Button><Button type="submit">{busy ? 'Saving…' : 'Save record'}</Button></footer></fieldset></form>}
    </DialogContent></Dialog></>;
}
