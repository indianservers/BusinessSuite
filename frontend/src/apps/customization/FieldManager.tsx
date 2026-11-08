import RecordDefinitionActions from "@/components/RecordDefinitionActions";
import {useDefinitionPermission} from "@/components/RecordDefinitionActions";
import { useCreateIntent } from "@/hooks/use-create-intent";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import FieldControl from '@/shared/custom-fields/FieldControl';

type Field = Record<string, unknown> & { id: number; module_name: string; field_api_name: string; field_label: string; field_type: string; validation_json?: Record<string, unknown> };
const places = ['create', 'edit', 'quick_create', 'detail'];
const blank = () => ({ module_name: '', field_api_name: '', field_label: '', field_type: 'text', required: false, unique: false, visible: true, editable: true, help_text: '', options: '', places: [...places], lookup_module: '', formula_expression: '', related_module_name: '', lookup_field: '', aggregate_function: 'sum', aggregate_field: '', default_value: '' });
export default function FieldManager() {
  const canCreate=useDefinitionPermission(["customization_manage","customization_fields_manage"],"create"),canEdit=useDefinitionPermission(["customization_manage","customization_fields_manage"],"edit");
  const fields = useQuery({ queryKey: ['customization-fields'], queryFn: () => api.get<{ items: Field[] }>('/customization/fields', { recordCache: false }).then(r => r.data.items) });
  const modules = useQuery({ queryKey: ['customization-modules'], queryFn: () => api.get<{ items: { module_api_name: string; module_label: string }[] }>('/customization/modules').then(r => r.data.items) });
  const [draft, setDraft] = useState(blank), [editing, setEditing] = useState<Field | null>(null), [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [preview, setPreview] = useState<unknown>(null), [search, setSearch] = useState('');
  const automatic = ['formula', 'rollup', 'auto_number'].includes(draft.field_type);
  function edit(field: Field | null) {
    if(field?!canEdit:!canCreate)return;
    const validation = field?.validation_json || {}, rollup = (field?.rollup_config_json || {}) as Record<string, unknown>;
    const options = Array.isArray(validation.options) ? validation.options as { value: string }[] : [];
    setEditing(field);
    setDraft(field ? { ...blank(), module_name: field.module_name, field_api_name: field.field_api_name, field_label: field.field_label, field_type: field.field_type,
      required: Boolean(field.required), unique: Boolean(field.unique), visible: field.visible !== false, editable: field.editable !== false,
      help_text: String(field.help_text || ''), default_value: String(field.default_value ?? ''),
      places: Array.isArray(validation.places) ? validation.places as string[] : [...places], options: options.map(o => o.value).join('\n'),
      lookup_module: String(field.lookup_module || ''), formula_expression: String(field.formula_expression || ''),
      related_module_name: String(rollup.related_module_name || ''), lookup_field: String(rollup.lookup_field || ''), aggregate_function: String(rollup.aggregate_function || 'sum'), aggregate_field: String(rollup.aggregate_field || '') } : blank());
    setPreview(null); setError(''); setOpen(true);
  }
  useCreateIntent(kind => { if (kind === "field") edit(null); });
  const text = (key: keyof ReturnType<typeof blank>, label: string, required = false) => <label className="block space-y-1 text-sm">{label}<Input required={required} value={String(draft[key])} onChange={e => setDraft({ ...draft, [key]: e.target.value })} /></label>;
  const moduleSelect = (key: 'module_name' | 'lookup_module' | 'related_module_name', label: string) => <label className="block space-y-1 text-sm">{label}<NativeSelect aria-label={label} required disabled={!!editing && key !== 'related_module_name'} value={draft[key]} onChange={e => setDraft({ ...draft, [key]: e.target.value })}><option value="">Choose module</option>{modules.data?.map(m => <option key={m.module_api_name} value={m.module_api_name}>{m.module_label}</option>)}</NativeSelect></label>;
  return <section className="space-y-5"><header className="flex flex-wrap justify-between gap-4"><div><h2 className="text-xl font-semibold">Field library</h2><p className="text-sm text-muted-foreground">Configure fields, linked records, formulas and related totals.</p></div><Button disabled={!canCreate} onClick={() => edit(null)}>Add field</Button></header>
    <Input aria-label="Search field library" placeholder="Search fields or modules…" value={search} onChange={e => setSearch(e.target.value)} />
    {fields.isError && <p role="alert">Could not load fields.</p>}
    <GroupedRecords scope="customization-fields" items={(fields.data || []).filter(f=>`${f.field_label} ${f.module_name}`.toLowerCase().includes(search.toLowerCase()))} gridClassName="divide-y rounded-lg border" fields={[{id:"module",label:"Module",value:field=>field.module_name},{id:"type",label:"Field type",value:field=>field.field_type}]} renderItem={f=><article key={f.id} className="flex items-center justify-between gap-4 p-4"><div><h3 className="font-medium">{f.field_label}</h3><p className="text-xs text-muted-foreground">{f.module_name} · {f.field_type}{f.required ? ' · Required' : ''}</p></div><div className="flex items-center gap-2">{f.visible===false&&f.editable===false&&<span className="text-xs text-muted-foreground">Retired</span>}<Button variant="outline" size="sm" disabled={!canEdit} onClick={() => edit(f)}>Edit</Button><RecordDefinitionActions record={f as unknown as Record<string,unknown>} nameField="field_label" endpoint={`/customization/fields/${f.id}`} queryKeys={["customization-fields"]} permissions={["customization_manage","customization_fields_manage"]} canRename={false} canDelete={!(f.visible===false&&f.editable===false)}/></div></article>}/>

    <Dialog open={open} onOpenChange={next => { if (!busy) setOpen(next); }}><DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto"><DialogTitle>{editing ? 'Edit' : 'Add'} field</DialogTitle>
      <form onSubmit={async e => {
        e.preventDefault(); if(busy || (editing?!canEdit:!canCreate))return; setBusy(true); setError('');
        try {
          const options = draft.options.split('\n').map(v => v.trim()).filter(Boolean).map(value => ({ value, label: value }));
          const body = { module_name: draft.module_name, field_api_name: draft.field_api_name, field_label: draft.field_label, field_type: draft.field_type,
            required: !automatic && draft.required, unique: draft.unique, visible: draft.visible, editable: !automatic && draft.editable,
            help_text: draft.help_text, default_value: draft.default_value === '' ? null : draft.default_value,
            lookup_module: draft.lookup_module || null, formula_expression: draft.formula_expression || null,
            rollup_config_json: draft.field_type === 'rollup' ? { related_module_name: draft.related_module_name, lookup_field: draft.lookup_field || undefined, aggregate_function: draft.aggregate_function, aggregate_field: draft.aggregate_field || undefined } : null,
            options, validation_json: { ...editing?.validation_json, options, places: draft.places } };
          if (editing) await api.put(`/customization/fields/${editing.id}`, body); else await api.post('/customization/fields', body);
          await fields.refetch(); setOpen(false);
        } catch (err) { const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail; setError(typeof detail === 'string' ? detail : 'Could not save field'); } finally { setBusy(false); }
      }}><fieldset disabled={busy} className="space-y-5"><div className="grid gap-6 sm:grid-cols-2"><div className="space-y-4">
        {moduleSelect('module_name', 'Module')}
        <label className="block space-y-1 text-sm">Field name<Input required value={draft.field_label} onChange={e => setDraft({ ...draft, field_label: e.target.value, field_api_name: editing ? draft.field_api_name : e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') })} /></label>
        <label className="block space-y-1 text-sm">Type<NativeSelect aria-label="Type" disabled={!!editing} value={draft.field_type} onChange={e => setDraft({ ...draft, field_type: e.target.value })}>{[...new Set([draft.field_type, 'text', 'textarea', 'radio', 'combobox', 'picklist', 'multi_select', 'number', 'decimal', 'currency', 'date', 'datetime', 'checkbox', 'email', 'phone', 'url', 'lookup', 'user_lookup', 'formula', 'rollup', 'auto_number'])].map(t => <option key={t}>{t}</option>)}</NativeSelect></label>
        {['radio', 'combobox', 'picklist', 'multi_select'].includes(draft.field_type) && <label className="block space-y-1 text-sm">Options, one per line<textarea required className="min-h-28 w-full rounded border bg-background p-3" value={draft.options} onChange={e => setDraft({ ...draft, options: e.target.value })} /></label>}
        {draft.field_type === 'lookup' && moduleSelect('lookup_module', 'Link to module')}
        {draft.field_type === 'formula' && <>{text('formula_expression', 'Formula expression', true)}<p className="text-xs text-muted-foreground">Use field identifiers, arithmetic, min, max, round and abs. Values calculate after saving.</p></>}
        {draft.field_type === 'rollup' && <>{moduleSelect('related_module_name', 'Related module')}{text('lookup_field', 'Lookup field on related module', true)}<label className="block text-sm">Aggregate<NativeSelect aria-label="Aggregate" value={draft.aggregate_function} onChange={e => setDraft({ ...draft, aggregate_function: e.target.value })}>{['sum', 'count', 'avg', 'min', 'max'].map(v => <option key={v}>{v}</option>)}</NativeSelect></label>{draft.aggregate_function !== 'count' && text('aggregate_field', 'Numeric field to aggregate', true)}</>}
        {!automatic && text('default_value', 'Default value')}{text('help_text', 'Help text')}
        {(['required', 'unique', 'visible', 'editable'] as const).map(key => <label key={key} className="flex items-center gap-2 text-sm"><input type="checkbox" disabled={automatic && ['required', 'editable'].includes(key)} checked={automatic && ['required', 'editable'].includes(key) ? false : draft[key]} onChange={e => setDraft({ ...draft, [key]: e.target.checked })} />{key}</label>)}
      </div><div className="space-y-4"><h3 className="text-sm font-semibold">Places where shown</h3>{places.map(key => <label key={key} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.places.includes(key)} onChange={e => setDraft({ ...draft, places: e.target.checked ? [...draft.places, key] : draft.places.filter(p => p !== key) })} />{key.replace(/_/g, ' ')}</label>)}
        <section className="space-y-2 rounded-lg border bg-muted/20 p-4"><p className="text-xs font-semibold uppercase text-muted-foreground">Live preview</p><p className="text-sm">{draft.field_label || 'Your field'}</p><FieldControl field={{ label: draft.field_label, field_type: draft.field_type, options: draft.options, lookup_module: draft.lookup_module }} value={preview} onChange={setPreview} /></section>
      </div></div>{error && <p role="alert" className="text-sm text-destructive">{error}</p>}<footer className="flex justify-end gap-2 border-t pt-4"><Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button type="submit" disabled={busy || (editing?!canEdit:!canCreate)}>{busy ? 'Saving…' : 'Save field'}</Button></footer></fieldset></form>
    </DialogContent></Dialog>
  </section>;
}
