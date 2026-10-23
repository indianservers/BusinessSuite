import { useEffect, useState } from "react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { workspaceError } from "../pages/workspaceTypes";

type Field = { id: number; name: string; field_type: string; options: string[]; value: string | number | boolean | null };
type Library = { fields: Field[]; can_edit: boolean; can_manage: boolean };
export default function TaskCustomFields({ taskId, projectId }: { taskId: number; projectId: number }) {
  const [data, setData] = useState<Library | null>(null);
  const [values, setValues] = useState<Record<number, string | boolean>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState("text");
  const [options, setOptions] = useState("");
  async function load() {
    const { data } = await api.get<Library>(`/project-management/tasks/${taskId}/custom-fields`);
    setData(data); setValues(Object.fromEntries(data.fields.map(field => [field.id, field.field_type === "checkbox" ? field.value === true : String(field.value ?? "")])));
  }
  useEffect(() => {
    let active = true; setData(null); setError(""); setNotice("");
    api.get<Library>(`/project-management/tasks/${taskId}/custom-fields`).then(({ data }) => {
      if (!active) return;
      setData(data); setValues(Object.fromEntries(data.fields.map(field => [field.id, field.field_type === "checkbox" ? field.value === true : String(field.value ?? "")])));
    }).catch(error => { if (active) setError(workspaceError(error)); });
    return () => { active = false; };
  }, [taskId]);
  async function save(field: Field) {
    setBusy(true); setError(""); setNotice("");
    const draft = values[field.id];
    const value = field.field_type === "checkbox" ? draft : draft === "" ? null : field.field_type === "number" ? Number(draft) : draft;
    try { await api.put(`/project-management/tasks/${taskId}/custom-fields/${field.id}`, { value }); setNotice(`${field.name} saved`); }
    catch (error) { setError(workspaceError(error)); } finally { setBusy(false); }
  }
  return <section className="space-y-4 rounded-lg border bg-card p-5" aria-label="Task custom fields">
    <h2 className="text-lg font-semibold">Custom fields</h2>
    {error && <p role="alert" className="text-destructive">{error}</p>}{notice && <p role="status" className="text-sm">{notice}</p>}
    {!data && !error && <p role="status">Loading fields…</p>}
    {data?.fields.map(field => <form key={field.id} className="flex flex-wrap items-end gap-3" onSubmit={event => { event.preventDefault(); void save(field); }}>
      <label className="min-w-0 flex-1 text-sm font-medium">{field.name}
        {field.field_type === "dropdown" ? <select aria-label={field.name} disabled={!data.can_edit || busy} className="mt-1 h-10 w-full rounded-md border bg-background px-3" value={String(values[field.id] ?? "")} onChange={event => setValues(current => ({ ...current, [field.id]: event.target.value }))}><option value="">Not set</option>{field.options.map(option => <option key={option}>{option}</option>)}</select>
          : field.field_type === "checkbox" ? <input aria-label={field.name} className="ml-3" type="checkbox" disabled={!data.can_edit || busy} checked={values[field.id] === true} onChange={event => setValues(current => ({ ...current, [field.id]: event.target.checked }))} />
            : <Input aria-label={field.name} className="mt-1" disabled={!data.can_edit || busy} type={field.field_type === "number" ? "number" : field.field_type === "date" ? "date" : "text"} step="any" maxLength={4000} value={String(values[field.id] ?? "")} onChange={event => setValues(current => ({ ...current, [field.id]: event.target.value }))} />}
      </label>{data.can_edit && <Button size="sm" variant="outline" disabled={busy}>Save {field.name}</Button>}
    </form>)}
    {data && !data.fields.length && <p className="text-sm text-muted-foreground">No custom fields in this project yet.</p>}
    {data?.can_manage && <details className="border-t pt-3"><summary className="cursor-pointer text-sm font-medium">Add project field</summary><form className="mt-3 space-y-3" onSubmit={event => {
      event.preventDefault(); setBusy(true); setError(""); setNotice("");
      void api.post(`/project-management/projects/${projectId}/custom-fields`, { name, field_type: type, options: type === "dropdown" ? options.split("\n").map(option => option.trim()).filter(Boolean) : [] })
        .then(async () => { setName(""); setOptions(""); await load(); setNotice("Project field added"); }).catch(error => setError(workspaceError(error))).finally(() => setBusy(false));
    }}><fieldset disabled={busy} className="space-y-3"><label className="block text-sm">Field name<Input required maxLength={120} value={name} onChange={event => setName(event.target.value)} /></label><label className="block text-sm">Field type<select className="ml-2 rounded-md border bg-background p-2" value={type} onChange={event => setType(event.target.value)}>{["text", "number", "date", "checkbox", "dropdown"].map(type => <option key={type}>{type}</option>)}</select></label>{type === "dropdown" && <label className="block text-sm">Options, one per line<textarea required className="mt-1 w-full rounded-md border bg-background p-2" value={options} onChange={event => setOptions(event.target.value)} /></label>}<p className="text-xs text-muted-foreground">Fields are available on every task in this project. Values are optional.</p><Button disabled={busy}>Add field</Button></fieldset></form></details>}
  </section>;
}
