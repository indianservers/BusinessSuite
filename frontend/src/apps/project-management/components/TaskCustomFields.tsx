import { PhoneInput } from "@/lib/validation/PhoneInput";
import { useEffect, useState } from "react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { customFieldTypes, numericFieldTypes } from "./customFieldTypes";
import { workspaceError } from "../pages/workspaceTypes";

type Field = { id: number; name: string; field_type: string; options: string[]; country_code?: string | null; value: string | number | boolean | null };
type Library = { fields: Field[]; can_edit: boolean; can_manage: boolean };
export default function TaskCustomFields({ taskId, projectId }: { taskId: number; projectId: number }) {
  const [data, setData] = useState<Library | null>(null);
  const [values, setValues] = useState<Record<number, string | boolean>>({});
  const [codes,setCodes]=useState<Record<number,string>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState("text");
  const [options, setOptions] = useState("");
  const [editing, setEditing] = useState<Field | null>(null);
  const [editName, setEditName] = useState("");
  const [editOptions, setEditOptions] = useState("");
  const [hideEmpty, setHideEmpty] = useState(false);
  async function editDefinition() {
    if (!editing || !editName.trim() || busy) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const { data: updated } = await api.put<Field>(`/project-management/projects/${projectId}/custom-fields/${editing.id}`, {
        name: editName.trim(), options: editing.field_type === "dropdown" ? editOptions.split("\n").map(option => option.trim()).filter(Boolean) : [],
      });
      setData(current => current ? { ...current, fields: current.fields.map(field => field.id === updated.id ? { ...field, ...updated } : field) } : current);
      setNotice(`${updated.name} definition updated`); setEditing(null);
    } catch (error) { setError(workspaceError(error)); } finally { setBusy(false); }
  }
  async function load() {
    const { data } = await api.get<Library>(`/project-management/tasks/${taskId}/custom-fields`);
    setCodes(Object.fromEntries(data.fields.map(field=>[field.id,field.country_code || (field.value ? '' : '+91')])));
    setData(data); setValues(Object.fromEntries(data.fields.map(field => [field.id, field.field_type === "checkbox" ? field.value === true : String(field.value ?? "")])));
  }
  useEffect(() => {
    let active = true; setData(null); setError(""); setNotice("");
    api.get<Library>(`/project-management/tasks/${taskId}/custom-fields`).then(({ data }) => {
      if (!active) return;
      setCodes(Object.fromEntries(data.fields.map(field=>[field.id,field.country_code || (field.value ? '' : '+91')])));
    setData(data); setValues(Object.fromEntries(data.fields.map(field => [field.id, field.field_type === "checkbox" ? field.value === true : String(field.value ?? "")])));
    }).catch(error => { if (active) setError(workspaceError(error)); });
    return () => { active = false; };
  }, [taskId]);
  async function save(field: Field) {
    setBusy(true); setError(""); setNotice("");
    const draft = values[field.id];
    const value = field.field_type === "checkbox" ? draft : draft === "" ? null : numericFieldTypes.includes(field.field_type) ? Number(draft) : draft;
    try { await api.put(`/project-management/tasks/${taskId}/custom-fields/${field.id}`, { value, ...(field.field_type==='phone'?{country_code:codes[field.id]}:{}) }); setNotice(`${field.name} saved`); }
    catch (error) { setError(workspaceError(error)); } finally { setBusy(false); }
  }
  return <section className="space-y-4 rounded-lg border bg-card p-5" aria-label="Task custom fields">
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-lg font-semibold">Custom fields</h2><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={hideEmpty} onChange={event => setHideEmpty(event.target.checked)} />Collapse empty fields</label></div>
    {error && <p role="alert" className="text-destructive">{error}</p>}{notice && <p role="status" className="text-sm">{notice}</p>}
    {!data && !error && <p role="status">Loading fields…</p>}
    {data?.fields.filter(field => !hideEmpty || (values[field.id] !== "" && values[field.id] !== false && values[field.id] != null)).map(field => <form key={field.id} className="flex flex-wrap items-end gap-3" onSubmit={event => { event.preventDefault(); void save(field); }}>
      <label className="min-w-0 flex-1 text-sm font-medium">{field.name}
        {field.field_type === "dropdown" ? <select aria-label={field.name} disabled={!data.can_edit || busy} className="mt-1 h-10 w-full rounded-md border bg-background px-3" value={String(values[field.id] ?? "")} onChange={event => setValues(current => ({ ...current, [field.id]: event.target.value }))}><option value="">Not set</option>{field.options.map(option => <option key={option}>{option}</option>)}</select>
          : field.field_type === "checkbox" ? <input aria-label={field.name} className="ml-3" type="checkbox" disabled={!data.can_edit || busy} checked={values[field.id] === true} onChange={event => setValues(current => ({ ...current, [field.id]: event.target.checked }))} />
            : field.field_type === "phone" ? <PhoneInput label={field.name} disabled={!data.can_edit || busy} value={String(values[field.id] ?? "")} countryCode={codes[field.id] ?? ""} onChange={value=>setValues(current=>({...current,[field.id]:value}))} onCountryCodeChange={code=>setCodes(current=>({...current,[field.id]:code}))} /> : field.field_type === "long_text" ? <textarea aria-label={field.name} disabled={!data.can_edit || busy} maxLength={20000} className="mt-1 min-h-24 w-full rounded-md border bg-background p-2" value={String(values[field.id] ?? "")} onChange={event => setValues(current => ({ ...current, [field.id]: event.target.value }))} /> : <Input aria-label={field.name} className="mt-1" disabled={!data.can_edit || busy} type={numericFieldTypes.includes(field.field_type) ? "number" : field.field_type === "date" ? "date" : field.field_type === "email" ? "email" : field.field_type === "website" ? "url" : field.field_type === "phone" ? "tel" : "text"} min={field.field_type === "rating" || field.field_type === "progress" ? 0 : undefined} max={field.field_type === "rating" ? 5 : field.field_type === "progress" ? 100 : undefined} step={field.field_type === "rating" ? "1" : "any"} maxLength={4000} value={String(values[field.id] ?? "")} onChange={event => setValues(current => ({ ...current, [field.id]: event.target.value }))} />}
      </label>{data.can_manage && <Button type="button" size="sm" variant="ghost" disabled={busy} aria-label={`Edit ${field.name} definition`} onClick={() => { setEditing(field); setEditName(field.name); setEditOptions(field.options.join("\n")); setError(""); }}>Edit field</Button>}{data.can_edit && <Button size="sm" variant="outline" disabled={busy}>Save {field.name}</Button>}
    </form>)}
    {editing && <form aria-label="Edit custom field definition" className="space-y-3 rounded-lg border bg-muted/20 p-4" onSubmit={event => { event.preventDefault(); void editDefinition(); }}>
      <h3 className="font-medium">Edit field definition</h3>
      <p className="text-xs text-muted-foreground">Changes apply to all tasks using this project field. Existing values are preserved. The field type stays unchanged.</p>
      <label className="block text-sm">Field name<Input aria-label="Edit field name" required maxLength={120} disabled={busy} value={editName} onChange={event => setEditName(event.target.value)} /></label>
      {editing.field_type === "dropdown" && <label className="block text-sm">Options, one per line<textarea aria-label="Edit field options" required disabled={busy} className="mt-1 min-h-24 w-full rounded border bg-background p-2" value={editOptions} onChange={event => setEditOptions(event.target.value)} /></label>}
      <div className="flex gap-2"><Button disabled={busy || !editName.trim()}>Save field definition</Button><Button type="button" variant="outline" disabled={busy} onClick={() => setEditing(null)}>Cancel</Button></div>
    </form>}
    {data && !data.fields.length && <p className="text-sm text-muted-foreground">No custom fields in this project yet.</p>}
    {data?.can_manage && <details className="border-t pt-3"><summary className="cursor-pointer text-sm font-medium">Add project field</summary><form className="mt-3 space-y-3" onSubmit={event => {
      event.preventDefault(); setBusy(true); setError(""); setNotice("");
      void api.post(`/project-management/projects/${projectId}/custom-fields`, { name, field_type: type, options: type === "dropdown" ? options.split("\n").map(option => option.trim()).filter(Boolean) : [] })
        .then(async () => { setName(""); setOptions(""); await load(); setNotice("Project field added"); }).catch(error => setError(workspaceError(error))).finally(() => setBusy(false));
    }}><fieldset disabled={busy} className="space-y-3"><label className="block text-sm">Field name<Input required maxLength={120} value={name} onChange={event => setName(event.target.value)} /></label><label className="block text-sm">Field type<select className="ml-2 rounded-md border bg-background p-2" value={type} onChange={event => setType(event.target.value)}>{customFieldTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>{type === "dropdown" && <label className="block text-sm">Options, one per line<textarea required className="mt-1 w-full rounded-md border bg-background p-2" value={options} onChange={event => setOptions(event.target.value)} /></label>}<p className="text-xs text-muted-foreground">Fields are available on every task in this project. Values are optional.</p><Button disabled={busy}>Add field</Button></fieldset></form></details>}
  </section>;
}
