import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import ModuleRecords from './ModuleRecords';

type Kind = 'modules' | 'buttons' | 'validation-rules' | 'related-lists';
type Item = Record<string, unknown> & { id: number };
const titles: Record<Kind, string> = { modules: 'Modules', buttons: 'Record actions', 'validation-rules': 'Validation rules', 'related-lists': 'Related lists' };
const blank = () => ({ module_name: '', name: '', identifier: '', plural: '', action_type: 'timeline_event', config: '{"title":"Record reviewed"}', related_module_name: '', lookup_field: '', error_message: '', condition: '{"field":"amount","operator":"less_than","value":0}' });

export default function RuntimeConfiguration({ kind }: { kind: Kind }) {
  const qc = useQueryClient();
  const rows = useQuery({ queryKey: ['customization', kind], queryFn: () => api.get<{ items: Item[] }>(`/customization/${kind}`, { recordCache: false }).then(r => r.data.items) });
  const modules = useQuery({ queryKey: ['customization-modules'], queryFn: () => api.get<{ items: Item[] }>('/customization/modules', { recordCache: false }).then(r => r.data.items) });
  const [open, setOpen] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState(''), [draft, setDraft] = useState(blank);
  const text = (key: keyof ReturnType<typeof blank>, label: string, required = true) => <label className="block space-y-1 text-sm">{label}<Input value={draft[key]} required={required} onChange={e => setDraft({ ...draft, [key]: e.target.value })} /></label>;
  const moduleSelect = (key: 'module_name' | 'related_module_name', label: string) => <label className="block space-y-1 text-sm">{label}<NativeSelect aria-label={label} required value={draft[key]} onChange={e => setDraft({ ...draft, [key]: e.target.value })}><option value="">Choose module</option>{modules.data?.filter(m => m.enabled !== false).map(m => <option key={m.id} value={String(m.module_api_name)}>{String(m.module_label)}</option>)}</NativeSelect></label>;
  return <section className="space-y-4"><header className="flex flex-wrap justify-between gap-3"><div><h2 className="text-xl font-semibold">{titles[kind]}</h2><p className="text-sm text-muted-foreground">{kind === 'buttons' ? 'Configure actions here, then run them on a selected record. Native module permissions still apply.' : 'Configure your own business records and rules.'}</p></div><Button onClick={() => { setDraft(blank()); setError(''); setOpen(true); }}>Add {kind === 'modules' ? 'module' : kind === 'buttons' ? 'action' : kind === 'related-lists' ? 'related list' : 'rule'}</Button></header>
    {rows.isError && <p role="alert">Configuration could not be loaded.</p>}
    <div className="divide-y rounded-lg border">{rows.data?.map(row => <article key={row.id} className="flex flex-wrap items-center justify-between gap-3 p-4"><div><h3 className="font-medium">{String(row.module_label || row.label || row.name)}</h3><p className="text-xs text-muted-foreground">{String(row.module_api_name || row.module_name)}{row.action_type ? ` · ${row.action_type}` : ''}</p>{row.action_config_json ? <pre className="mt-2 max-w-lg overflow-auto text-xs">{JSON.stringify(row.action_config_json, null, 2)}</pre> : null}</div>{kind === 'modules' && row.enabled !== false && <ModuleRecords module={String(row.module_api_name)} label={String(row.module_label)} />}</article>)}</div>
    <Dialog open={open} onOpenChange={next => { if (!busy) setOpen(next); }}><DialogContent className="max-h-[90vh] overflow-auto"><DialogTitle>Add {titles[kind].toLowerCase()}</DialogTitle><form onSubmit={async e => {
      e.preventDefault(); setBusy(true); setError('');
      try {
        let payload: Record<string, unknown>;
        if (kind === 'modules') payload = { module_api_name: draft.identifier, module_label: draft.name, plural_label: draft.plural };
        else if (kind === 'buttons') payload = { module_name: draft.module_name, label: draft.name, action_type: draft.action_type, action_config_json: JSON.parse(draft.config) };
        else if (kind === 'validation-rules') payload = { module_name: draft.module_name, name: draft.name, condition_json: JSON.parse(draft.condition), error_message: draft.error_message };
        else payload = { module_name: draft.module_name, label: draft.name, related_module_name: draft.related_module_name, lookup_field: draft.lookup_field };
        await api.post(`/customization/${kind}`, payload);
        await qc.invalidateQueries({ queryKey: ['customization', kind] });
        await qc.invalidateQueries({ queryKey: ['customization-modules'] });
        await qc.invalidateQueries({ queryKey: ['custom-module-buttons'] });
        setOpen(false);
      } catch (err) { const detail = (err as { response?: { data?: { detail?: unknown } }; message?: string }).response?.data?.detail; setError(typeof detail === 'string' ? detail : err instanceof SyntaxError ? 'Enter valid JSON configuration.' : 'Could not save configuration.'); } finally { setBusy(false); }
    }}><fieldset disabled={busy} className="space-y-4">
      {kind !== 'modules' && moduleSelect('module_name', 'Module')}{text('name', 'Name')}
      {kind === 'modules' && <>{text('identifier', 'Identifier (lowercase letters, numbers and underscores)')}{text('plural', 'Plural name')}</>}
      {kind === 'buttons' && <><label className="block space-y-1 text-sm">Action<NativeSelect aria-label="Action" value={draft.action_type} onChange={e => { const action = e.target.value; setDraft({ ...draft, action_type: action, config: JSON.stringify(action === 'open_url' ? { url: 'https://example.com' } : action === 'submit_approval' ? { title: 'Review record', assigned_to_user_id: null } : action === 'webhook' ? { connection_id: null, operation: '', payload: {} } : { title: 'Follow up' }, null, 2) }); }}>{['timeline_event', 'create_task', 'submit_approval', 'open_url', 'webhook'].map(a => <option key={a}>{a}</option>)}</NativeSelect></label><label className="block space-y-1 text-sm">Action configuration<textarea required className="min-h-40 w-full rounded border bg-background p-3 font-mono" value={draft.config} onChange={e => setDraft({ ...draft, config: e.target.value })} /></label><p className="text-xs text-muted-foreground">Use a saved connection for webhooks. To use a record value, enter {JSON.stringify({ '$record': 'values.field_identifier' })} as a configuration value.</p></>}
      {kind === 'validation-rules' && <><label className="block space-y-1 text-sm">Reject when this condition matches<textarea required className="min-h-28 w-full rounded border bg-background p-3 font-mono" value={draft.condition} onChange={e => setDraft({ ...draft, condition: e.target.value })} /></label>{text('error_message', 'Message shown to the user')}</>}
      {kind === 'related-lists' && <>{moduleSelect('related_module_name', 'Related module')}{text('lookup_field', 'Lookup field on related module')}</>}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}<footer className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button type="submit">{busy ? 'Saving…' : 'Save configuration'}</Button></footer>
    </fieldset></form></DialogContent></Dialog>
  </section>;
}
